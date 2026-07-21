"""Run context: run.json, status.jsonl, errors.jsonl, and source ingestion.

run.json is written first and updated last. The Phlo worker tails status.jsonl
to emit stage events in near-real-time rather than only at completion, so status
lines are flushed as they happen and never buffered to the end.
"""

from __future__ import annotations

import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from . import __version__, SCHEMA_VERSION
from .artifacts import utc_now_iso
from .criteria import CriteriaSet
from .fsutil import (
    append_jsonl,
    atomic_write_json,
    copy_file_atomic,
    detect_sync_path,
    sha256_file,
)
from .pdf import assert_readable_pdf, extract_pages, page_count_of
from .telemetry import (
    StageTelemetry,
    criteria_status,
    engine_git_sha,
    environment_block,
    page_extraction_method,
    totals_from_stages,
)


@dataclass
class RunContext:
    run_id: str
    out_dir: Path
    pdf_path: Path
    criteria_set: CriteriaSet
    model: str | None
    json_mode: bool
    source_sha256: str = ""
    page_count: int = 0
    source_bytes: int = 0
    started_at: str = field(default_factory=utc_now_iso)
    stages_completed: list[str] = field(default_factory=list)
    cost_usd: float = 0.0
    # PRD §3 run telemetry. Per-stage records in execution order, plus the
    # run-header reproducibility fields that were missing. These are resolved
    # ONCE in prepare_run rather than on every run.json write: the git SHA
    # cannot change mid-run, and the egress lookup is a network call that must
    # not be repeated on each of the six writes a run performs.
    telemetry: dict = field(default_factory=dict)
    engine_git_sha: str | None = None
    environment: dict = field(default_factory=dict)
    page_extraction_method: str | None = None
    criteria_dir: str | None = None
    _stage_started: dict = field(default_factory=dict)

    # ---------------- telemetry ----------------

    def stage_telemetry(self, stage: str) -> StageTelemetry:
        """The telemetry accumulator for a stage, created on first request.

        Stages fetch this and fold their model calls into it. Keyed by stage
        name so a re-run of a single stage (`--stage scoring`) replaces that
        stage's record rather than appending a second one — two records for one
        stage would double-count in the totals.
        """
        existing = self.telemetry.get(stage)
        if existing is None:
            existing = StageTelemetry(stage=stage)
            self.telemetry[stage] = existing
        return existing

    def _telemetry_block(self) -> dict:
        """Assemble the telemetry block for run.json.

        Stage order follows the canonical pipeline order rather than dict
        insertion order, so a `--resume` run that re-ran only scoring still
        reads top-to-bottom in the order the pipeline executes.
        """
        from .artifacts import STAGES

        ordered = [self.telemetry[s] for s in STAGES if s in self.telemetry]
        ordered += [t for k, t in self.telemetry.items() if k not in STAGES]
        return {
            "totals": totals_from_stages(ordered),
            "stages": [t.as_dict() for t in ordered],
        }

    # ---------------- progress reporting ----------------

    @property
    def status_path(self) -> Path:
        return self.out_dir / "status.jsonl"

    @property
    def errors_path(self) -> Path:
        return self.out_dir / "errors.jsonl"

    def _emit(self, obj: dict) -> None:
        append_jsonl(self.status_path, obj)
        if self.json_mode:
            import json as _json

            print(_json.dumps(obj), flush=True)

    def stage_started(self, stage: str) -> None:
        self._stage_started[stage] = time.monotonic()
        self.stage_telemetry(stage).start()
        self._emit({"ts": utc_now_iso(), "stage": stage, "event": "started"})
        if not self.json_mode:
            print(f"  → {stage} …", file=sys.stderr, flush=True)

    def stage_progress(self, stage: str, detail: str) -> None:
        self._emit(
            {"ts": utc_now_iso(), "stage": stage, "event": "progress", "detail": detail}
        )
        if not self.json_mode:
            print(f"     {detail}", file=sys.stderr, flush=True)

    def stage_completed(self, stage: str, artifact: str, cost: float = 0.0) -> None:
        duration = round(time.monotonic() - self._stage_started.get(stage, time.monotonic()), 1)
        self.cost_usd += cost
        if stage not in self.stages_completed:
            self.stages_completed.append(stage)

        tel = self.stage_telemetry(stage)
        tel.finish()
        # The cost the stage REPORTS is authoritative over the sum the telemetry
        # accumulated. They normally agree, but a stage that spends outside
        # run_claude (or reports a partial figure) must not have its headline
        # cost silently rewritten by the accumulator — and vice versa, the
        # accumulator is the only source of the token counts.
        if cost and abs(tel.cost_usd - cost) > 1e-9:
            tel.cost_usd = cost

        self._emit(
            {
                "ts": utc_now_iso(),
                "stage": stage,
                "event": "completed",
                "artifact": artifact,
                "duration_s": duration,
                "cost_usd": round(cost, 4),
                # Tokens on the progress stream too, so a worker tailing
                # status.jsonl gets telemetry in near-real-time rather than only
                # from the final run.json.
                "tokens": dict(tel.tokens),
                "model": tel.model,
                "attempts": tel.attempts,
                "fallback_used": tel.fallback_used,
            }
        )
        if not self.json_mode:
            tok = tel.tokens.get("total", 0)
            extra = f", {tok/1000:.1f}k tok" if tok else ""
            retries = max(0, tel.attempts - tel.model_calls)
            if retries:
                extra += f", {retries} retr{'y' if retries == 1 else 'ies'}"
            if tel.fallback_used:
                extra += ", FALLBACK"
            print(
                f"  ✓ {stage} → {artifact} ({duration}s, ${cost:.3f}{extra})",
                file=sys.stderr,
                flush=True,
            )
        self.write_run_json(status="running")

    def stage_failed(self, stage: str, message: str) -> None:
        self._emit(
            {"ts": utc_now_iso(), "stage": stage, "event": "failed", "error": message}
        )
        if not self.json_mode:
            print(f"  ✗ {stage}: {message}", file=sys.stderr, flush=True)

    def stage_vetoed(self, stage: str, message: str) -> None:
        """A veto is a terminal FINDING, not a failure. It gets its own event so
        the worker can emit DEAL_SCORED-with-veto rather than a failure event."""
        self._emit(
            {"ts": utc_now_iso(), "stage": stage, "event": "vetoed", "detail": message}
        )

    def stage_skipped(self, stage: str, reason: str) -> None:
        if stage not in self.stages_completed:
            self.stages_completed.append(stage)
        self._emit(
            {"ts": utc_now_iso(), "stage": stage, "event": "skipped", "reason": reason}
        )
        if not self.json_mode:
            print(f"  ⟳ {stage} skipped ({reason})", file=sys.stderr, flush=True)

    def warn(self, message: str, detail: dict | None = None) -> None:
        """Non-fatal warning → errors.jsonl. Never swallowed silently."""
        append_jsonl(
            self.errors_path,
            {"ts": utc_now_iso(), "level": "warning", "message": message, "detail": detail or {}},
        )
        if not self.json_mode:
            print(f"  ! {message}", file=sys.stderr, flush=True)

    # ---------------- run.json ----------------

    def write_run_json(self, status: str, completed: bool = False) -> None:
        payload = {
            "run_id": self.run_id,
            "engine_version": __version__,
            "schema_version": SCHEMA_VERSION,
            "source": {
                "filename": self.pdf_path.name,
                "sha256": self.source_sha256,
                "page_count": self.page_count,
                "bytes": self.source_bytes,
            },
            # PRD §3 — which build produced this run. `engine_version` alone is
            # too coarse: "0.1.0" spans every commit between two releases.
            # Null when this is not a git checkout, which is a legitimate state
            # for a distributed copy and never a reason to fail a run.
            "engine_git_sha": self.engine_git_sha,
            "criteria": {
                "set_id": self.criteria_set.set_id,
                "set_code": self.criteria_set.set_code,
                "version": self.criteria_set.version,
                "content_hash": self.criteria_set.content_hash,
                # Stated, not left to be inferred from a null version. A
                # consumer that has to interpret null as "draft" is a consumer
                # that can interpret it differently from the next one.
                "criteria_status": criteria_status(self.criteria_set.version),
                # Where the set was loaded from, so `l1 test-criterion --against
                # <run-dir>` can re-load it without the author re-typing the
                # path. Advisory only — the directory may have moved or been
                # edited since, which is exactly why --criteria overrides it.
                "source_dir": self.criteria_dir,
            },
            "criteria_status": criteria_status(self.criteria_set.version),
            # The RESOLVED model, taken from what the runtime actually served,
            # falling back to the explicit --model override. Never "default" —
            # a run recorded as "default" is not reproducible once the default
            # moves, which was the whole defect this replaces.
            "model": self._resolved_model(),
            "model_requested": self.model,
            "environment": dict(self.environment),
            # text_layer / ocr / mixed — governs how much extraction output can
            # be trusted. `mixed` means some pages yielded no text at all, so
            # any claim of absence is weaker than it appears.
            "page_extraction_method": self.page_extraction_method,
            "started_at": self.started_at,
            "completed_at": utc_now_iso() if completed else None,
            "status": status,
            "stages_completed": list(self.stages_completed),
            "cost_usd": round(self.cost_usd, 4),
            "telemetry": self._telemetry_block(),
        }
        atomic_write_json(self.out_dir / "run.json", payload)

    def _resolved_model(self) -> str | None:
        """The model actually served, preferred over the one requested.

        Order matters. The runtime's reported id is authoritative because
        `--model sonnet` is an alias that resolves to a dated model id, and the
        alias is not reproducible while the id is. The requested value is used
        only when nothing ran (a validate-only or fully-resumed invocation), and
        None is returned rather than "default" when neither is known.
        """
        served: list[str] = []
        for tel in self.telemetry.values():
            for m in getattr(tel, "models", []):
                if m not in served:
                    served.append(m)
        if served:
            return "+".join(served)
        return self.model or None


def prepare_run(
    pdf_path: Path,
    criteria_set: CriteriaSet,
    out_dir: Path,
    *,
    model: str | None,
    json_mode: bool,
    resume: bool,
    criteria_dir: Path | str | None = None,
) -> RunContext:
    """Validate input, set up the output directory, ingest the source PDF.

    Content addressing (PRD §6.6): the source is copied to a fixed name
    `00-source.pdf` chosen by the engine, and identified by sha256. The input
    path is never a destination path, so a case-colliding filename on APFS
    cannot cause one run to overwrite another's source.
    """
    pdf_path = Path(pdf_path).expanduser().resolve()
    out_dir = Path(out_dir).expanduser().resolve()

    source_bytes = assert_readable_pdf(pdf_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    ctx = RunContext(
        run_id=str(uuid.uuid4()),
        out_dir=out_dir,
        pdf_path=pdf_path,
        criteria_set=criteria_set,
        model=model,
        json_mode=json_mode,
        source_bytes=source_bytes,
        # Resolved once, here, for the whole run. Both are best-effort and both
        # return None rather than raising: telemetry must never be the reason an
        # analysis fails. The egress lookup in particular is bounded at 1.5s and
        # happens exactly once, not on each of the six run.json writes a run
        # performs.
        engine_git_sha=engine_git_sha(),
        environment=environment_block(),
        criteria_dir=(
            str(Path(criteria_dir).expanduser().resolve()) if criteria_dir else None
        ),
    )

    marker = detect_sync_path(out_dir)
    if marker:
        ctx.warn(
            f"output directory appears to be inside a sync client tree ('{marker}'). "
            "Sync clients write conflicted copies and can leave dataless placeholders "
            "where stat() succeeds but reads block. Prefer a local, unsynced path.",
            {"out_dir": str(out_dir), "marker": marker},
        )

    for warning in criteria_set.warnings:
        ctx.warn(f"criteria lint: {warning}")

    ctx.source_sha256 = sha256_file(pdf_path)

    dest_pdf = out_dir / "00-source.pdf"
    if not (resume and dest_pdf.exists() and sha256_file(dest_pdf) == ctx.source_sha256):
        copy_file_atomic(pdf_path, dest_pdf)

    pages_dir = out_dir / "00-pages"
    existing = sorted(pages_dir.glob("page-*.txt")) if pages_dir.exists() else []
    pages: list[str] = []
    if resume and existing:
        ctx.page_count = len(existing)
        # Re-read on resume so `page_extraction_method` is classified from the
        # same text every stage will see. Deriving it only on a fresh extraction
        # would leave a resumed run's run.json claiming a method it never
        # measured.
        pages = [p.read_text(encoding="utf-8", errors="replace") for p in existing]
        ctx.stage_skipped("ingest", f"{ctx.page_count} pages already extracted")
    else:
        # Extract from the run-local copy, not the user-supplied path. The copy
        # is the one whose hash we recorded; re-reading the original invites a
        # race where the file changed between hashing and extraction.
        pages = extract_pages(dest_pdf, pages_dir)
        ctx.page_count = len(pages)

    # PRD §3 — text_layer / ocr / mixed. `mixed` fires on ANY page that yielded
    # no text: one image-only slide is enough to make "absent from the document"
    # a weaker claim than it reads as, and a consumer must be able to see that.
    ctx.page_extraction_method = page_extraction_method(pages)
    if ctx.page_extraction_method == "mixed":
        empty = [i for i, p in enumerate(pages, start=1) if not (p or "").strip()]
        ctx.warn(
            f"{len(empty)} page(s) yielded no extractable text "
            f"(pages {', '.join(str(p) for p in empty[:20])}"
            f"{' …' if len(empty) > 20 else ''}). Claims of absence are weaker "
            "for this document than for one with a complete text layer.",
            {"empty_pages": empty, "page_extraction_method": "mixed"},
        )

    if ctx.page_count != page_count_of(dest_pdf):
        ctx.warn(
            "extracted page count disagrees with the PDF's reported page count",
            {"extracted": ctx.page_count, "reported": page_count_of(dest_pdf)},
        )

    ctx.write_run_json(status="running")
    return ctx
