"""`l1` command-line interface (PRD 06 §2)."""

from __future__ import annotations

import argparse
import json
import signal
import sys
from pathlib import Path

from . import SCHEMA_VERSION, __version__
from .unresolved import OWNER_LABEL
from .artifacts import ARTIFACT_FILENAMES, STAGES, load_stage_artifact
from .claude_runner import BudgetTracker, claude_available
from .criteria import load_criteria
from .errors import (
    ExitCode,
    InvalidInputError,
    L1Error,
    StageFailureError,
    VetoError,
)
from .fsutil import read_json
from .pdf import load_pages
from .run import prepare_run
from .telemetry import render_telemetry
from .testcriterion import render_result, test_criterion
from .stages import (
    run_classification,
    run_diligence,
    run_extraction,
    run_memo,
    run_scoring,
)

# All five PRD stages are implemented.
IMPLEMENTED_STAGES = (
    "classification",
    "extraction",
    "diligence",
    "scoring",
    "memo",
)


def _install_sigterm_handler(ctx_holder: dict) -> None:
    """Exit 143 on SIGTERM so the worker knows to requeue rather than treat the
    run as failed. The partial run remains resumable via --resume."""

    def handler(signum, frame):
        ctx = ctx_holder.get("ctx")
        if ctx is not None:
            ctx.write_run_json(status="terminated")
            ctx.stage_failed("run", "received SIGTERM")
        sys.exit(ExitCode.TERMINATED)

    signal.signal(signal.SIGTERM, handler)


def cmd_analyze(args: argparse.Namespace) -> int:
    if not claude_available():
        print(
            "error: the `claude` executable is not on PATH. The engine invokes "
            "Claude Code as a subprocess.",
            file=sys.stderr,
        )
        return ExitCode.INVALID_INPUT

    criteria_set = load_criteria(Path(args.criteria))

    requested = args.stage
    if requested and requested not in STAGES:
        raise InvalidInputError(
            f"--stage {requested!r} is not one of {list(STAGES)}"
        )
    if requested and requested not in IMPLEMENTED_STAGES:
        raise InvalidInputError(
            f"--stage {requested!r} is specified in the PRD but not implemented in "
            f"engine {__version__}. Implemented: {list(IMPLEMENTED_STAGES)}"
        )

    ctx_holder: dict = {}
    _install_sigterm_handler(ctx_holder)

    ctx = prepare_run(
        Path(args.pdf),
        criteria_set,
        Path(args.out),
        model=args.model,
        json_mode=args.json,
        resume=args.resume,
        criteria_dir=args.criteria,
    )
    ctx_holder["ctx"] = ctx

    if not args.json:
        print(
            f"l1 {__version__} — run {ctx.run_id}\n"
            f"  source : {ctx.pdf_path.name}\n"
            f"  sha256 : {ctx.source_sha256}\n"
            f"  pages  : {ctx.page_count}\n"
            f"  criteria: {criteria_set.set_code} "
            f"({len(criteria_set.active_criteria)} active) {criteria_set.content_hash[:23]}…\n"
            f"  out    : {ctx.out_dir}",
            file=sys.stderr,
        )

    budget = BudgetTracker(args.max_budget_usd)
    pages = load_pages(ctx.out_dir / "00-pages")

    to_run = [requested] if requested else list(IMPLEMENTED_STAGES)

    def _diligence(c, p, b, m):
        return run_diligence(c, p, b, m, live=not args.no_live_diligence)

    runners = {
        "classification": run_classification,
        "extraction": run_extraction,
        "diligence": _diligence,
        "scoring": run_scoring,
        "memo": run_memo,
    }

    try:
        for stage in to_run:
            artifact = ctx.out_dir / ARTIFACT_FILENAMES[stage]
            if args.resume and artifact.exists():
                try:
                    load_stage_artifact(ctx.out_dir, stage)
                    ctx.stage_skipped(stage, "artifact exists and validates")
                    continue
                except L1Error:
                    ctx.warn(
                        f"existing {stage} artifact failed validation; re-running the stage"
                    )
            runners[stage](ctx, pages, budget, args.model)

        ctx.cost_usd = budget.spent_usd
        complete = set(IMPLEMENTED_STAGES).issubset(set(ctx.stages_completed))
        ctx.write_run_json(
            status="completed" if complete and not requested else "partial",
            completed=True,
        )
        if not args.json:
            print(
                f"\ndone — ${budget.spent_usd:.3f} spent, "
                f"stages: {', '.join(ctx.stages_completed)}",
                file=sys.stderr,
            )
        return ExitCode.SUCCESS

    except VetoError as exc:
        # Exit 11 is a SUCCESSFUL analysis with a terminal finding, not a failure
        # (PRD §2). The scoring artifact was written before the veto was raised,
        # so the run directory holds a complete scorecard — the run is marked
        # `vetoed`, never `failed`, and the worker branches on the exit code.
        ctx.stage_vetoed("scoring", exc.message)

        # PRD §5 stage 4: "scoring halts, THE MEMO IS GENERATED IN VETO FORM, and
        # the engine exits 11." A veto that produced no memo would leave the
        # analyst with an exit code and nothing to read — the memo is where the
        # veto reason, its evidence, and section 11's open items actually live.
        # The memo stage renders the veto banner from the scorecard it is handed,
        # so no separate "veto form" code path is needed.
        memo_requested = requested in (None, "memo")
        if memo_requested and not args.json:
            print("  generating memo in veto form …", file=sys.stderr)
        if memo_requested:
            try:
                run_memo(ctx, pages, budget, args.model)
            except L1Error as memo_exc:
                # A memo failure must not mask the veto. The veto is the finding;
                # the missing memo is a secondary problem, recorded and reported.
                ctx.warn(
                    f"memo generation failed after a veto: {memo_exc.message}. The "
                    "veto stands and the scorecard is on disk.",
                    {"error": memo_exc.message},
                )

        ctx.cost_usd = budget.spent_usd
        ctx.write_run_json(status="vetoed", completed=True)
        if not args.json:
            print(f"\nVETOED — {exc.message}", file=sys.stderr)
            print(
                f"analysis is complete and the scorecard is written; "
                f"${budget.spent_usd:.3f} spent",
                file=sys.stderr,
            )
        return ExitCode.VETOED

    except L1Error as exc:
        ctx.stage_failed("run", exc.message)
        ctx.cost_usd = budget.spent_usd
        ctx.write_run_json(status="failed", completed=True)
        print(f"error: {exc.message}", file=sys.stderr)
        return exc.exit_code


def cmd_validate(args: argparse.Namespace) -> int:
    cs = load_criteria(Path(args.criteria_dir))
    print(f"{cs.set_code} — {cs.name}")
    print(f"  version      : {cs.version if cs.version is not None else 'null (DRAFT)'}")
    print(f"  schema       : {cs.schema_version}")
    print(f"  scope        : {', '.join(cs.asset_class_scope) or 'all'}")
    print(f"  content_hash : {cs.content_hash}")
    by_tier: dict[str, int] = {}
    for c in cs.active_criteria:
        by_tier[c.tier] = by_tier.get(c.tier, 0) + 1
    print(f"  criteria     : {len(cs.active_criteria)} active of {len(cs.criteria)}")
    for tier in ("VETO", "RED_FLAG", "GREEN_FLAG"):
        print(f"      {tier:<11}: {by_tier.get(tier, 0)}")
    if cs.warnings:
        print(f"\n  {len(cs.warnings)} warning(s):")
        for w in cs.warnings:
            print(f"      ! {w}")
    else:
        print("\n  no warnings")
    return ExitCode.SUCCESS


def cmd_inspect(args: argparse.Namespace) -> int:
    out_dir = Path(args.output_dir)
    run_path = out_dir / "run.json"
    if not run_path.exists():
        raise InvalidInputError(f"no run.json in {out_dir}")
    run = read_json(run_path)

    print(f"run {run['run_id']} — {run['status']}")
    engine_line = f"  engine   : {run['engine_version']} (schema {run['schema_version']})"
    # Which build produced this. Null when the engine is not a git checkout,
    # which is stated rather than left blank.
    sha = run.get("engine_git_sha")
    engine_line += f" @ {sha}" if sha else " @ not a git checkout"
    print(engine_line)
    print(f"  source   : {run['source']['filename']}")
    print(f"  sha256   : {run['source']['sha256']}")
    method = run.get("page_extraction_method")
    print(f"  pages    : {run['source']['page_count']}" + (f" ({method})" if method else ""))
    if method == "mixed":
        # Not a footnote. `mixed` means some pages yielded no text at all, so
        # every claim of absence in this run is weaker than it reads.
        print(
            "             ! some pages yielded no text; claims of absence are "
            "weaker for this document"
        )

    crit = run["criteria"]
    status = run.get("criteria_status") or crit.get("criteria_status")
    crit_line = f"  criteria : {crit['set_code']} {crit['content_hash'][:23]}…"
    if crit.get("version") is not None:
        crit_line += f" v{crit['version']}"
    print(crit_line + (f" [{status}]" if status else ""))
    if status == "DRAFT":
        # The draft-criteria banner. A score produced against unversioned rules
        # is not a reproducible score, and the reader must be told so here as
        # well as in the memo.
        print(
            "             ! DRAFT criteria set — no version was assigned, so this "
            "score is not reproducible against a pinned rule set"
        )

    print(f"  cost     : ${run.get('cost_usd', 0):.3f}")
    env = run.get("environment") or {}
    country = env.get("egress_country")
    # Where the run executed. The SEBI geo-fence makes this a first-class
    # diagnostic: the same run from an Indian IP produces materially different
    # diligence results, so "not determined" is worth printing too.
    print(f"  egress   : {country or 'not determined'}")
    print(f"  stages   : {', '.join(run.get('stages_completed') or []) or 'none'}")

    for line in render_telemetry(run):
        print(line)

    for stage in STAGES:
        path = out_dir / ARTIFACT_FILENAMES[stage]
        if not path.exists():
            continue
        try:
            art = load_stage_artifact(out_dir, stage)
        except L1Error as exc:
            print(f"\n  {stage}: INVALID — {exc.message}")
            continue
        unresolved = art.get("unresolved", [])
        cites = art.get("citations", [])
        print(f"\n  {stage}: {len(cites)} citation(s), {len(unresolved)} unresolved")
        # Entries are structured objects (PRD §3). Print the routing, not the raw
        # dict: `inspect` is a CLI-only surface, and under §0 a CLI user must get
        # the same routing information a management-system user would.
        for item in unresolved:
            if not isinstance(item, dict):
                print(f"      ? {item}")
                continue
            kind = item.get("kind", "?")
            marker = "BLOCKED" if kind == "EXTERNALLY_BLOCKED" else kind
            owner = item.get("unblock_owner")
            source = item.get("typical_source")
            tag = f" [{OWNER_LABEL.get(owner, owner)}]" if owner else (
                f" [ask for: {source}]" if source else ""
            )
            account = " ".join((item.get("account") or "").split())
            if len(account) > 160:
                account = account[:157] + "…"
            print(f"      ? {marker}{tag} {item.get('field_path', '?')}: {account}")

    errors_path = out_dir / "errors.jsonl"
    if errors_path.exists():
        lines = [l for l in errors_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        if lines:
            print(f"\n  {len(lines)} warning(s) in errors.jsonl")
            for line in lines[:20]:
                try:
                    print(f"      ! {json.loads(line)['message']}")
                except Exception:
                    pass
    return ExitCode.SUCCESS


def cmd_test_criterion(args: argparse.Namespace) -> int:
    """Single-criterion dry run against an already-completed run (PRD §3).

    Exit 0 whatever the verdict, INCLUDING a fired veto. This is an authoring
    tool: a veto that fires is a successful test of a veto rule, not a decision
    about a fund. Mapping it to exit 11 would make an author's shell think their
    criteria edit had halted an analysis.
    """
    if not claude_available():
        print(
            "error: the `claude` executable is not on PATH. test-criterion runs the "
            "same two scoring passes a real run does, so it needs the CLI.",
            file=sys.stderr,
        )
        return ExitCode.INVALID_INPUT

    res = test_criterion(
        args.criterion_code,
        Path(args.against),
        criteria_dir=Path(args.criteria) if args.criteria else None,
        model=args.model,
        max_budget_usd=args.max_budget_usd,
        verbose=not args.json,
    )

    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        for line in render_result(res):
            print(line)
    return ExitCode.SUCCESS


def cmd_version(args: argparse.Namespace) -> int:
    print(f"l1 analysis engine {__version__}")
    print(f"  artifact schema version : {SCHEMA_VERSION}")
    print(f"  criteria schema version : 1")
    print(f"  model                   : {args.model or 'claude default (unset)'}")
    print(f"  claude on PATH          : {'yes' if claude_available() else 'NO'}")
    print(f"  stages implemented      : {', '.join(IMPLEMENTED_STAGES)}")
    print(f"  stages specified        : {', '.join(STAGES)}")
    return ExitCode.SUCCESS


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="l1",
        description="L1 Analysis Engine — fund marketing document to evidence-grounded IC memo.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("analyze", help="run the analysis pipeline over a PDF")
    a.add_argument("pdf", help="source PDF path")
    a.add_argument("--criteria", required=True, help="criteria set directory")
    a.add_argument("--out", required=True, help="output directory (created if absent)")
    a.add_argument("--stage", help="run a single stage only")
    a.add_argument("--resume", action="store_true", help="skip stages whose artifacts exist and validate")
    a.add_argument("--model", help="model override")
    a.add_argument("--max-budget-usd", type=float, dest="max_budget_usd", help="hard spend ceiling")
    a.add_argument("--json", action="store_true", help="machine-readable progress on stdout")
    a.add_argument(
        "--no-live-diligence",
        action="store_true",
        dest="no_live_diligence",
        help=(
            "skip network calls in the diligence stage; every remote check is "
            "recorded as unavailable with that as the stated reason"
        ),
    )
    a.set_defaults(func=cmd_analyze)

    v = sub.add_parser("validate", help="lint a criteria set without running analysis")
    v.add_argument("criteria_dir")
    v.set_defaults(func=cmd_validate)

    i = sub.add_parser("inspect", help="summarise a completed run")
    i.add_argument("output_dir")
    i.set_defaults(func=cmd_inspect)

    tc = sub.add_parser(
        "test-criterion",
        help="evaluate ONE criterion against a completed run, without re-extracting",
        description=(
            "Runs the SAME dual-pass (lenient + strict) evaluation the scoring "
            "stage runs, over an already-extracted run's artifacts. Seconds and "
            "cents rather than the 8-16 minutes and ~$2.30 a full run costs. "
            "Point --criteria at a modified criteria set to iterate on "
            "detection_guidance against the same extracted run."
        ),
    )
    tc.add_argument("criterion_code", help="e.g. CR-0010")
    tc.add_argument(
        "--against",
        required=True,
        help="output directory of a completed run (must contain 00-pages/ and the "
        "classification + extraction artifacts)",
    )
    tc.add_argument(
        "--criteria",
        help="criteria set directory to test — typically a MODIFIED set you are "
        "authoring. Defaults to the directory the run recorded.",
    )
    tc.add_argument("--model", help="model override")
    tc.add_argument(
        "--max-budget-usd", type=float, dest="max_budget_usd", help="hard spend ceiling"
    )
    tc.add_argument("--json", action="store_true", help="machine-readable result on stdout")
    tc.set_defaults(func=cmd_test_criterion)

    ver = sub.add_parser("version", help="engine version + model + criteria schema version")
    ver.add_argument("--model", help=argparse.SUPPRESS)
    ver.set_defaults(func=cmd_version)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except L1Error as exc:
        print(f"error: {exc.message}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return ExitCode.TERMINATED
    except BrokenPipeError:
        return ExitCode.SUCCESS


if __name__ == "__main__":
    sys.exit(main())
