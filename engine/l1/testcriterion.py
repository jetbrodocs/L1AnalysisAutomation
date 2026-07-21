"""`l1 test-criterion <CODE> --against <run-dir>` — single-criterion dry run.

WHY THIS EXISTS. Authoring `detection_guidance` is currently write-and-hope: the
only way to find out whether a rule fires on a real document is a full pipeline
run, which is 8-16 minutes and roughly $2.30 (PRD §7). For a product whose
entire pitch is "encode your own investment judgement", that is a bad authoring
experience — an author who cannot see the effect of an edit will stop editing.

This evaluates ONE criterion against an ALREADY-EXTRACTED run. Classification,
extraction and diligence are read from disk; only the two scoring passes run.
Seconds and cents rather than minutes and dollars.

**THE CENTRAL CONSTRAINT: this must not be a simplified approximation.** A
dry-run that behaves differently from production is worse than no dry-run,
because it teaches the author the wrong thing — they tune guidance against a
harness that scores differently from the engine, and the rule then misbehaves in
the run that matters. So this module contains NO evaluation logic of its own. It
builds a one-criterion CriteriaSet and calls the scoring stage's own functions:

    scoring._build_prompt      the identical prompt, over the identical artifacts
    scoring._run_pass          the identical dual-pass invocation, both standards
    scoring._reconcile         the identical merge, contested detection included
    scoring._verify_evidence_quotes   the identical three-tier quote verification
    scoring._repair_absence_evidence  the identical §6.3 downgrade
    scoring._enforce_blocked_criteria the identical unreachable-source policy

If scoring's behaviour changes, this changes with it — that is the design, and
it is why nothing here is reimplemented. The one deliberate difference is that
the criteria set handed to `_build_prompt` contains a single criterion, which is
the entire point of the command.

**A veto does not halt here.** `run_scoring` raises VetoError so the pipeline can
exit 11; this is an authoring tool, so a fired veto is reported as a fired veto
and the command exits 0. The author is testing the rule, not making a decision.

`--criteria <dir>` points at a MODIFIED criteria set, so the loop is: edit
guidance, re-test against the same extracted run, read the evidence, repeat.
That loop is the feature; the speed is only what makes it usable.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .artifacts import load_stage_artifact
from .claude_runner import BudgetTracker
from .criteria import CriteriaSet, load_criteria
from .errors import InvalidInputError
from .fsutil import read_json
from .pdf import load_pages
from .telemetry import StageTelemetry, add_tokens, zero_tokens


class _DryRunContext:
    """The minimal RunContext surface the scoring functions actually use.

    Scoring calls `stage_progress`, `warn`, and `stage_telemetry` on its ctx. It
    is given a real object implementing exactly those, rather than a mock: a
    mock that silently swallowed a warning would hide precisely the diagnostics
    an author needs — `_enforce_blocked_criteria` and `_repair_absence_evidence`
    both report their decisions through `warn`, and those decisions are often
    the answer to "why did my criterion not fire".

    Nothing here writes to the run directory. A dry run must not mutate the run
    it is testing against, or the author's next test would be against artifacts
    this one edited.
    """

    def __init__(self, out_dir: Path, criteria_set: CriteriaSet, verbose: bool):
        self.out_dir = out_dir
        self.criteria_set = criteria_set
        self.verbose = verbose
        self.warnings: list[dict] = []
        self.progress: list[str] = []
        self._telemetry: dict[str, StageTelemetry] = {}

    def stage_telemetry(self, stage: str) -> StageTelemetry:
        if stage not in self._telemetry:
            self._telemetry[stage] = StageTelemetry(stage=stage)
        return self._telemetry[stage]

    def stage_progress(self, stage: str, detail: str) -> None:
        self.progress.append(detail)
        if self.verbose:
            print(f"     {detail}", flush=True)

    def warn(self, message: str, detail: dict | None = None) -> None:
        # Collected AND printed. These are the engine explaining itself, and in
        # an authoring tool that explanation is the primary output.
        self.warnings.append({"message": message, "detail": detail or {}})
        print(f"  ! {message}", flush=True)

    # Present so scoring's ctx surface is fully satisfied even if it grows a
    # call to one of these; a dry run never starts or completes a real stage.
    def stage_started(self, stage: str) -> None:  # pragma: no cover - unused
        pass

    def stage_completed(self, stage: str, artifact: str, cost: float = 0.0) -> None:  # pragma: no cover
        pass


def _single_criterion_set(criteria_set: CriteriaSet, code: str) -> tuple[CriteriaSet, object]:
    """A CriteriaSet containing exactly the requested criterion.

    Built with `dataclasses.replace` over the real loaded set so that set-level
    metadata (set_code, version, content_hash) is preserved verbatim. The
    content hash in particular must not be recomputed: the author needs to see
    WHICH rule text was tested, and a hash invented by this module would name a
    set that does not exist.
    """
    crit = criteria_set.by_code(code)
    if crit is None:
        available = ", ".join(c.criterion_code for c in criteria_set.criteria)
        raise InvalidInputError(
            f"criterion {code!r} is not in criteria set {criteria_set.set_code}. "
            f"Available: {available}",
            {"criterion_code": code},
        )
    if not crit.is_active:
        # Reported rather than silently tested. An inactive criterion never runs
        # in production, so testing it without saying so would mislead.
        raise InvalidInputError(
            f"criterion {code!r} is present but INACTIVE in {criteria_set.set_code}. "
            "An inactive criterion is not evaluated by a real run either. Activate "
            "it in criteria.yaml to test it.",
            {"criterion_code": code},
        )
    return replace(criteria_set, criteria=[crit]), crit


def test_criterion(
    code: str,
    run_dir: Path,
    *,
    criteria_dir: Path | None = None,
    model: str | None = None,
    max_budget_usd: float | None = None,
    verbose: bool = False,
) -> dict:
    """Evaluate one criterion against a completed run's artifacts.

    Returns a result dict; the caller renders it. Raises InvalidInputError when
    the run directory is not usable, which is exit 30 — the same code a real run
    gives for bad input, because that is what this is.
    """
    # Import here rather than at module scope. The dry run reuses scoring's
    # internals by design (see module docstring), and a top-level import would
    # make `l1.scoring` and `l1.testcriterion` mutually reachable at import time
    # for no benefit.
    from .stages import scoring as scoring_stage

    run_dir = Path(run_dir).expanduser().resolve()
    if not run_dir.is_dir():
        raise InvalidInputError(f"run directory not found: {run_dir}")

    run_json_path = run_dir / "run.json"
    if not run_json_path.exists():
        raise InvalidInputError(
            f"{run_dir} does not look like a run directory (no run.json). "
            "test-criterion evaluates against an ALREADY-COMPLETED run's artifacts."
        )
    run_meta = read_json(run_json_path)

    # PRD §6.1 in spirit: the same three artifacts the real scoring stage
    # declares as inputs, loaded through the same validating loader. A dry run
    # that accepted a malformed artifact would score against something the real
    # engine would have refused.
    try:
        cls = load_stage_artifact(run_dir, "classification")
        ext = load_stage_artifact(run_dir, "extraction")
    except Exception as exc:
        raise InvalidInputError(
            f"{run_dir}: classification and extraction artifacts are required to "
            f"test a criterion, and could not be loaded ({exc}). Run the pipeline "
            "at least as far as extraction first."
        ) from exc

    # Diligence is optional — the real scoring stage tolerates its absence and
    # renders "not run" into the prompt. Matching that tolerance matters:
    # forcing diligence here would make the dry run stricter than production.
    dil = None
    if (run_dir / "03-diligence.json").exists():
        try:
            dil = load_stage_artifact(run_dir, "diligence")
        except Exception:
            dil = None

    pages = load_pages(run_dir / "00-pages")

    # The criteria set under test. When --criteria is given it is a MODIFIED set
    # the author is iterating on; when omitted, fall back to the set the run
    # itself used so the command works with no extra arguments.
    if criteria_dir is not None:
        criteria_set = load_criteria(Path(criteria_dir))
    else:
        recorded = (run_meta.get("criteria") or {}).get("source_dir")
        if not recorded:
            raise InvalidInputError(
                "--criteria is required: the run record does not name the criteria "
                "directory it used, so there is nothing to fall back to. Point "
                "--criteria at the set you are authoring."
            )
        criteria_set = load_criteria(Path(recorded))

    single, crit = _single_criterion_set(criteria_set, code)

    ctx = _DryRunContext(run_dir, single, verbose)
    budget = BudgetTracker(max_budget_usd)

    # The analysis date the run itself used, not today's. Date-sensitive
    # criteria (CR-0017's staleness threshold) must be tested against the same
    # arithmetic the run performed, or the author sees a verdict that depends on
    # when they happened to run the test rather than on their guidance.
    from datetime import date

    today = date.today()
    sco_path = run_dir / "04-scoring.json"
    if sco_path.exists():
        try:
            recorded_date = (read_json(sco_path).get("result") or {}).get("analysis_date")
            if recorded_date:
                today = date.fromisoformat(recorded_date)
        except (ValueError, OSError):
            pass

    # ---- the identical prompt the real scoring stage builds ----
    prompt = scoring_stage._build_prompt(single, cls, ext, dil, pages, today)

    # ---- the identical dual pass, both standards, independent invocations ----
    lenient, l_unresolved, l_cost = scoring_stage._run_pass(
        ctx, "lenient", scoring_stage.LENIENT_STANDARD, prompt, pages, budget, model
    )
    strict, s_unresolved, s_cost = scoring_stage._run_pass(
        ctx, "strict", scoring_stage.STRICT_STANDARD, prompt, pages, budget, model
    )

    # ---- the identical reconciliation, quote verification and policy passes ----
    findings = scoring_stage._reconcile(ctx, single, lenient, strict)
    checked, verified = scoring_stage._verify_evidence_quotes(ctx, findings, pages)
    scoring_stage._repair_absence_evidence(ctx, findings)
    # The unreachable-source policy applies here too. If the author's criterion
    # depends on a check the run recorded as unavailable, the dry run must show
    # it forced to unevaluated — exactly as production would — rather than
    # showing a verdict production will never produce.
    blocked_notes = scoring_stage._enforce_blocked_criteria(ctx, findings, dil)

    finding = findings[0] if findings else None
    tel = ctx.stage_telemetry("scoring")
    tokens = zero_tokens()
    for t in ctx._telemetry.values():
        tokens = add_tokens(tokens, t.tokens)

    return {
        "criterion_code": code,
        "criterion": {
            "name": crit.name,
            "tier": crit.tier,
            "category": crit.category,
            "severity": crit.severity,
            "weight": crit.weight,
            "detection_guidance": crit.detection_guidance,
            "evidence_requirement": crit.evidence_requirement,
        },
        "criteria_set": {
            "set_code": criteria_set.set_code,
            "version": criteria_set.version,
            "content_hash": criteria_set.content_hash,
            "source_dir": str(criteria_dir) if criteria_dir else None,
        },
        "run": {
            "run_dir": str(run_dir),
            "run_id": run_meta.get("run_id"),
            "source": (run_meta.get("source") or {}).get("filename"),
            "page_count": len(pages),
            "analysis_date": today.isoformat(),
            "diligence_present": dil is not None,
        },
        "finding": finding,
        # Both raw readings, unreconciled. An author debugging a rule needs to
        # see WHICH standard rejected it — a criterion that fires lenient and
        # not strict usually means the guidance asks for something the document
        # implies rather than states, which is a fixable guidance problem.
        "lenient": lenient.get(code),
        "strict": strict.get(code),
        "quotes_verified": verified,
        "quotes_total": checked,
        "warnings": ctx.warnings,
        "blocked": bool(blocked_notes),
        "unresolved": list(l_unresolved) + list(s_unresolved),
        "cost_usd": round(l_cost + s_cost, 4),
        "tokens": tokens,
        "model": tel.model,
        "model_calls": tel.model_calls,
        "attempts": tel.attempts,
        "retry_reasons": list(tel.retry_reasons),
        "fallback_used": tel.fallback_used,
    }


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

_VERDICT_LABEL = {
    "fired": "FIRED",
    "not_fired": "did not fire",
    "contested": "CONTESTED",
    "unevaluated": "UNEVALUATED",
    "veto_unevaluated": "VETO UNEVALUATED",
}


def render_result(res: dict) -> list[str]:
    """Human-readable dry-run report.

    Ordered by what an author needs first: the verdict, then whether the two
    passes agreed, then the evidence with its verification verdicts, then what
    it cost. The evidence is the part that makes the tool useful — a verdict
    alone does not tell you why your guidance did or did not match.
    """
    out: list[str] = []
    crit = res["criterion"]
    f = res.get("finding") or {}

    out.append("")
    out.append(f"  {res['criterion_code']} — {crit['name']}")
    out.append(f"  {crit['tier']} / {crit['severity']} / {crit['category']} (weight {crit['weight']})")
    out.append("")
    out.append(f"  against  : {res['run']['source']} ({res['run']['page_count']} pages)")
    out.append(f"  run      : {res['run']['run_dir']}")
    cs = res["criteria_set"]
    out.append(
        f"  criteria : {cs['set_code']} "
        f"{'v' + str(cs['version']) if cs['version'] is not None else '(DRAFT)'} "
        f"{(cs['content_hash'] or '')[:23]}…"
    )
    if not res["run"]["diligence_present"]:
        # Stated explicitly. A criterion depending on an external check will
        # behave differently in a run that HAS diligence, and an author must not
        # mistake this run's verdict for the production one.
        out.append(
            "             ! no diligence artifact in this run — criteria depending "
            "on external checks are evaluated as if diligence had not run"
        )

    status = f.get("status", "unknown")
    verdict = _VERDICT_LABEL.get(status, status)
    out.append("")
    out.append(f"  VERDICT  : {verdict}   (confidence: {f.get('confidence', '?')})")

    l, s = res.get("lenient") or {}, res.get("strict") or {}
    l_fired = l.get("fired")
    s_fired = s.get("fired")
    agree = l_fired == s_fired
    out.append(
        f"  passes   : lenient {'fires' if l_fired else 'does not fire'}, "
        f"strict {'fires' if s_fired else 'does not fire'}"
        + ("  — agreed" if agree else "  — DISAGREE (contested)")
    )
    if not agree:
        # This is the most actionable output the tool produces. Lenient-only
        # firing almost always means the guidance asks for something the
        # document implies rather than states.
        out.append(
            "             the two standards read this rule differently. A rule that "
            "fires only under the lenient standard is usually asking for something "
            "the document implies rather than states."
        )

    if status in ("unevaluated", "veto_unevaluated"):
        out.append(f"  reason   : {f.get('unevaluated_reason') or f.get('reasoning')}")
        if res.get("blocked"):
            out.append(
                "             this criterion was forced to unevaluated because an "
                "external check it depends on was unavailable. An unreachable source "
                "is never an adverse finding — production does the same thing."
            )

    reasoning = (f.get("reasoning") or "").strip()
    if reasoning:
        out.append("")
        out.append("  reasoning:")
        for line in _wrap(reasoning, 76):
            out.append(f"    {line}")

    evidence = f.get("evidence") or []
    out.append("")
    if evidence:
        out.append(f"  evidence ({len(evidence)}):")
        for item in evidence:
            # The three-tier verdict, shown per quote. `layout` means the tokens
            # were found in order across a column splice; `unverified` means the
            # quote was NOT found on its cited page and is retained flagged
            # rather than dropped.
            tier = item.get("verification", "?")
            mark = {"exact": "✓", "layout": "≈", "unverified": "✗"}.get(tier, "?")
            out.append(f"    {mark} p.{item.get('page')} [{tier}]")
            for line in _wrap((item.get("quote") or "").strip(), 72):
                out.append(f"        {line}")
    else:
        out.append("  evidence : none (this finding rests on absence, or did not fire)")

    absence = (f.get("absence_evidence") or "").strip()
    if absence:
        out.append("")
        out.append("  absence_evidence (what was searched):")
        for line in _wrap(absence, 76):
            out.append(f"    {line}")
    elif f.get("fired") and not evidence:
        out.append(
            "  ! fired on absence with NO absence_evidence — production downgrades "
            "this to unevaluated (§6.3)"
        )

    if f.get("remediation"):
        out.append("")
        out.append("  ask:")
        for line in _wrap(f["remediation"], 76):
            out.append(f"    {line}")

    qv, qt = res.get("quotes_verified", 0), res.get("quotes_total", 0)
    out.append("")
    if qt:
        out.append(f"  grounding: {qv}/{qt} evidence quotes verified against their cited page")

    tok = res.get("tokens") or {}
    out.append(
        f"  cost     : ${res.get('cost_usd', 0):.4f} — "
        f"{tok.get('total', 0):,} tokens, {res.get('model_calls', 0)} model call(s), "
        f"{res.get('attempts', 0)} attempt(s)"
    )
    out.append(f"  model    : {res.get('model') or 'not recorded'}")
    if res.get("fallback_used"):
        out.append(
            "  ! text-mode fallback was used — schema was not enforced by the runtime"
        )
    for reason in res.get("retry_reasons") or []:
        out.append(f"  ! retry: {reason}")

    return out


def _wrap(text: str, width: int) -> list[str]:
    import textwrap

    collapsed = " ".join((text or "").split())
    return textwrap.wrap(collapsed, width=width) or [""]
