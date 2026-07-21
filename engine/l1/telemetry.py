"""Run telemetry — token accounting, model identity, retry and fallback records.

PRD 06 §3 "Run telemetry". `run.json` originally recorded only a total
`cost_usd` and a per-stage `duration_s`. That is not enough to diagnose a system
whose cost varies 7x on identical input (§7): a cost figure alone cannot tell
you whether an expensive run was a large document or a retry storm, and it
cannot tell you whether a cheap run was well-cached or simply truncated.

Everything here was ALREADY AVAILABLE and being discarded. Claude Code's
`--output-format json` result envelope carries:

    "usage": {
      "input_tokens": 2,
      "output_tokens": 4,
      "cache_creation_input_tokens": 22404,
      "cache_read_input_tokens": 0,
      ...
    },
    "modelUsage": {
      "claude-opus-4-8[1m]": {"inputTokens": 2, "outputTokens": 4, ...}
    }

VERIFIED EMPIRICALLY on Claude Code 2.1.215 by capturing a live envelope. Two
things about that shape are load-bearing and non-obvious:

1. **The resolved model id is a KEY of `modelUsage`, not a scalar field.** There
   is no top-level `model` in the envelope. `--model` may be unset, in which
   case the engine previously recorded the literal string `"default"` — which is
   unreproducible, because "default" means different things on different days.
   `modelUsage` is the only place the actually-served model id appears, so that
   is where it is read from.

2. **`usage.cache_creation_input_tokens` is disjoint from `usage.input_tokens`.**
   In the captured envelope `input_tokens` is 2 while `cache_creation_input_tokens`
   is 22404 — the cached prefix is NOT counted in `input_tokens`. So a `total`
   computed as `input + output` would understate a cached run by four orders of
   magnitude. `total` here is therefore the sum of all four counters, which is
   the number that actually corresponds to work done.

The other half of this module is the accounting the envelope does NOT carry:
attempts, retry reasons, fallback use, wall-clock vs billable time, and quote
verification tallies. Those are engine facts, recorded by the engine.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------
# Token counters
# --------------------------------------------------------------------------

# The four counters the CLI reports, mapped to the names the PRD's run.json
# schema uses. Kept as an explicit table rather than string-munging the CLI's
# names, so a rename upstream surfaces as a zero rather than as a silent
# mis-attribution into the wrong bucket.
_USAGE_KEYS = (
    ("input", "input_tokens"),
    ("output", "output_tokens"),
    ("cache_creation", "cache_creation_input_tokens"),
    ("cache_read", "cache_read_input_tokens"),
)

TOKEN_FIELDS = ("input", "output", "cache_creation", "cache_read")


def zero_tokens() -> dict:
    return {name: 0 for name in TOKEN_FIELDS} | {"total": 0}


def tokens_from_envelope(envelope: dict | None) -> dict:
    """Extract the four token counters from a `--output-format json` envelope.

    Returns zeros rather than raising when `usage` is absent or malformed.
    Telemetry must never be the reason a run fails: a missing counter is a
    reporting gap, and reporting gaps are recorded as zero and moved past. The
    analysis itself is unaffected by whether we could count its tokens.
    """
    if not isinstance(envelope, dict):
        return zero_tokens()
    usage = envelope.get("usage")
    if not isinstance(usage, dict):
        return zero_tokens()

    out: dict = {}
    for name, key in _USAGE_KEYS:
        raw = usage.get(key)
        out[name] = int(raw) if isinstance(raw, (int, float)) else 0

    # Sum of ALL FOUR counters — see module docstring. `input_tokens` excludes
    # the cached prefix, so input+output alone understates a cached call
    # dramatically and would make cache efficiency look like a cost saving that
    # never happened.
    out["total"] = sum(out[name] for name in TOKEN_FIELDS)
    return out


def add_tokens(a: dict, b: dict) -> dict:
    """Element-wise sum of two token dicts."""
    keys = set(TOKEN_FIELDS) | {"total"}
    return {k: int(a.get(k, 0)) + int(b.get(k, 0)) for k in sorted(keys)}


def model_from_envelope(envelope: dict | None) -> str | None:
    """The RESOLVED model id, read from `modelUsage`'s keys.

    Never returns "default". The point of this field is reproducibility: knowing
    a run used "the default" tells you nothing a month later, when the default
    has moved. If the envelope does not name a model we return None, which reads
    honestly as "not recorded" rather than falsely as a model name.

    When a single call somehow spans more than one model, all of them are
    reported joined by "+", rather than silently picking the first.
    """
    if not isinstance(envelope, dict):
        return None
    model_usage = envelope.get("modelUsage")
    if isinstance(model_usage, dict) and model_usage:
        names = sorted(str(k) for k in model_usage.keys() if k)
        if names:
            return "+".join(names)
    # Fallbacks for envelope shapes that do carry a scalar. Checked after
    # modelUsage because modelUsage is the one verified to be present.
    for key in ("model", "modelId"):
        val = envelope.get(key)
        if isinstance(val, str) and val.strip() and val.strip() != "default":
            return val.strip()
    return None


# --------------------------------------------------------------------------
# Per-stage accumulator
# --------------------------------------------------------------------------


@dataclass
class StageTelemetry:
    """Everything recorded about one stage's execution.

    A stage may make several model calls (scoring makes two — lenient and
    strict), and each of those may take several attempts. The distinction
    matters: `model_calls` counts logical calls, `attempts` counts subprocess
    invocations including failed ones. One expensive call and many cheap ones
    are different problems with different fixes, and a stage that succeeded on
    the fourth attempt is a different health signal from one that succeeded
    first time at the same cost.
    """

    stage: str
    started_at: str | None = None
    completed_at: str | None = None
    wall_clock_s: float = 0.0
    # Time spent inside `claude` subprocesses. The complement of wall_clock is
    # local work: PDF extraction, quote verification, invariant sweeps, I/O.
    # Separating them answers "was this slow run the model or the machine",
    # which a single duration cannot.
    billable_s: float = 0.0
    cost_usd: float = 0.0
    tokens: dict = field(default_factory=zero_tokens)
    models: list[str] = field(default_factory=list)
    model_calls: int = 0
    attempts: int = 0
    retry_reasons: list[str] = field(default_factory=list)
    fallback_used: bool = False
    quotes_verified: int = 0
    quotes_total: int = 0
    _monotonic_start: float | None = None

    def start(self) -> None:
        self._monotonic_start = time.monotonic()
        self.started_at = _utc_now_iso()

    def finish(self) -> None:
        if self._monotonic_start is not None:
            self.wall_clock_s = round(time.monotonic() - self._monotonic_start, 2)
        self.completed_at = _utc_now_iso()

    def record_call(self, result) -> None:
        """Fold one completed `run_claude` result into this stage's totals.

        Takes the ClaudeResult rather than the raw envelope so that the
        engine-side facts (attempts made, fallback used) travel with the
        model-side facts (tokens, cost, resolved model) and cannot be recorded
        out of step with each other.
        """
        self.model_calls += 1
        self.cost_usd += float(getattr(result, "cost_usd", 0.0) or 0.0)
        self.tokens = add_tokens(self.tokens, getattr(result, "tokens", None) or zero_tokens())
        self.attempts += int(getattr(result, "attempts", 1) or 1)
        self.billable_s += float(getattr(result, "billable_s", 0.0) or 0.0)

        for reason in getattr(result, "retry_reasons", None) or []:
            self.retry_reasons.append(str(reason))

        if getattr(result, "used_fallback", False):
            self.fallback_used = True

        model = getattr(result, "model", None)
        if model and model not in self.models:
            self.models.append(model)

    def record_quotes(self, verified: int, total: int) -> None:
        """The grounding metric (§7). Additive — a stage may verify in batches."""
        self.quotes_verified += int(verified or 0)
        self.quotes_total += int(total or 0)

    @property
    def model(self) -> str | None:
        """The resolved model for this stage, or None if nothing was recorded.

        Never the string "default" — see `model_from_envelope`. A stage with no
        model calls at all (diligence is pure network work) legitimately has no
        model, and None says that.
        """
        if not self.models:
            return None
        return "+".join(self.models) if len(self.models) > 1 else self.models[0]

    def as_dict(self) -> dict:
        return {
            "stage": self.stage,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "wall_clock_s": round(self.wall_clock_s, 2),
            "billable_s": round(self.billable_s, 2),
            "cost_usd": round(self.cost_usd, 4),
            "tokens": dict(self.tokens),
            "model": self.model,
            "model_calls": self.model_calls,
            "attempts": self.attempts,
            "retry_reasons": list(self.retry_reasons),
            "fallback_used": self.fallback_used,
            "quotes_verified": self.quotes_verified,
            "quotes_total": self.quotes_total,
        }


def totals_from_stages(stages: list[StageTelemetry]) -> dict:
    """Roll per-stage telemetry into the run-level totals block.

    `retries` is attempts-beyond-the-first summed across stages, NOT the length
    of retry_reasons: a retry whose reason could not be classified still counts
    as a retry, and undercounting retries is precisely the blindness this field
    exists to remove.
    """
    tokens = zero_tokens()
    for st in stages:
        tokens = add_tokens(tokens, st.tokens)

    models: list[str] = []
    for st in stages:
        for m in st.models:
            if m not in models:
                models.append(m)

    return {
        "wall_clock_s": round(sum(st.wall_clock_s for st in stages), 2),
        "billable_s": round(sum(st.billable_s for st in stages), 2),
        "cost_usd": round(sum(st.cost_usd for st in stages), 4),
        "tokens": tokens,
        "models": models,
        "model_calls": sum(st.model_calls for st in stages),
        "attempts": sum(st.attempts for st in stages),
        "retries": sum(max(0, st.attempts - st.model_calls) for st in stages),
        "retry_reasons": [r for st in stages for r in st.retry_reasons],
        "fallbacks_used": sum(1 for st in stages if st.fallback_used),
        "quotes_verified": sum(st.quotes_verified for st in stages),
        "quotes_total": sum(st.quotes_total for st in stages),
    }


# --------------------------------------------------------------------------
# Run-header reproducibility fields
# --------------------------------------------------------------------------


def engine_git_sha() -> str | None:
    """Short SHA of the engine checkout, or None if this is not a git checkout.

    `engine_version` alone is too coarse — "0.1.0" covers every commit between
    two releases, which is most of them during development. This is what makes
    "which build produced this run" answerable.

    MUST NOT fail the run. A distributed copy of the engine is legitimately not
    a git checkout, `git` may be absent from PATH, and a corrupt index must not
    take down an analysis. Every failure path here returns None, which reads as
    "not a git checkout" — honest, and distinguishable from a real SHA.
    """
    try:
        repo_dir = Path(__file__).resolve().parent.parent
        proc = subprocess.run(
            ["git", "-C", str(repo_dir), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            timeout=5,
        )
        if proc.returncode != 0:
            return None
        sha = proc.stdout.decode("utf-8", errors="replace").strip()
        return sha or None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def criteria_status(version) -> str:
    """`ACTIVE` or `DRAFT`, stated explicitly.

    PRD §3: a null `criteria.version` previously had to be INTERPRETED by every
    consumer as "draft". Leaving a semantic distinction to be re-derived from a
    null is the kind of implicit contract that breaks silently — one consumer
    reads null as draft, another as "unknown", and the draft banner appears in
    one place and not another. So the engine states it.
    """
    return "ACTIVE" if version is not None else "DRAFT"


# Where the run executed, as seen from outside. The SEBI geo-fence (overview
# §8a) makes this a first-class diagnostic: the same run from an Indian IP
# produces materially different diligence results, so a run record that omits
# egress location cannot explain why two runs of the same deck disagree.
_EGRESS_TIMEOUT_S = 1.5
_EGRESS_URL = "https://ipinfo.io/country"


def egress_country(timeout_s: float = _EGRESS_TIMEOUT_S) -> str | None:
    """Best-effort ISO country code of this machine's egress. None on any failure.

    THREE CONSTRAINTS, all of which the PRD states and all of which are load
    bearing:

      - It must NOT fail the run. Every exception is swallowed and becomes None.
      - It must NOT add meaningful latency. The timeout is 1.5s, once per run,
        against a cheap plaintext endpoint that returns a two-letter code.
      - It must be honest when it does not know. None means "not determined",
        never a guessed or defaulted country.

    Set `L1_EGRESS_COUNTRY` to override — for an offline run, an air-gapped
    deployment, or a test that must not touch the network. Set it to the empty
    string to disable the lookup entirely and record null.
    """
    override = os.environ.get("L1_EGRESS_COUNTRY")
    if override is not None:
        return override.strip().upper() or None

    try:
        import urllib.request

        with urllib.request.urlopen(_EGRESS_URL, timeout=timeout_s) as resp:
            body = resp.read(16).decode("utf-8", errors="replace").strip().upper()
    except Exception:
        # Deliberately bare: DNS failure, TLS failure, timeout, proxy refusal,
        # a captive portal returning HTML — none of them are worth a stack
        # trace, and none of them are worth failing an analysis over.
        return None

    # Only a plausible ISO-3166 alpha-2 is accepted. A captive portal returning
    # "<!DOCTYPE" must record null, not a country called "<!".
    return body if len(body) == 2 and body.isalpha() else None


def environment_block() -> dict:
    return {"egress_country": egress_country()}


def page_extraction_method(pages: list[str], *, ocr_used: bool = False) -> str:
    """`text_layer` / `ocr` / `mixed` — how much extraction output can be trusted.

    The engine currently requires a text layer (`extract_pages` fails a PDF that
    yields no text anywhere), so `ocr` is reachable only when an OCR path is
    added. `mixed` is reachable TODAY and is the interesting case: a deck whose
    text layer covers 45 of 52 pages and leaves 7 image-only slides silently
    empty. Every claim about those 7 pages is unfalsifiable, and a consumer that
    saw only `text_layer` would never know to discount them.

    The threshold is any empty page at all, not a percentage. One image-only
    slide is enough to make "absent from the document" a weaker statement than
    it looks, and that is exactly what this field is for.
    """
    if ocr_used:
        return "ocr" if all(not (p or "").strip() for p in pages) else "mixed"
    if not pages:
        return "text_layer"
    empty = sum(1 for p in pages if not (p or "").strip())
    if empty == 0:
        return "text_layer"
    if empty == len(pages):
        # Unreachable through extract_pages today, which raises on a fully empty
        # extraction. Kept so the classification is total rather than relying on
        # a caller-side invariant that may later change.
        return "ocr"
    return "mixed"


def _utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------
# Rendering — `l1 inspect`
# --------------------------------------------------------------------------


def _fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}k"
    return str(n)


def render_telemetry(run: dict) -> list[str]:
    """Human-readable telemetry summary for `l1 inspect`.

    PRD §0, the Standalone Principle: this command is how a CLI-only user reads
    their telemetry. Everything Phlo would compute from `run.json` has to be
    legible here too, or the CLI is not a complete product.

    Returns lines rather than printing, so the caller controls the stream and
    the function stays testable without capturing stdout.
    """
    lines: list[str] = []
    tel = run.get("telemetry") or {}
    totals = tel.get("totals") or {}
    stages = tel.get("stages") or []

    if not totals and not stages:
        lines.append("\n  telemetry: not recorded (run predates telemetry, or no stage ran)")
        return lines

    tok = totals.get("tokens") or {}
    lines.append("\n  ── telemetry ──────────────────────────────────────────")

    wall = totals.get("wall_clock_s") or 0.0
    bill = totals.get("billable_s") or 0.0
    local = max(0.0, wall - bill)
    lines.append(
        f"  time     : {wall:.1f}s wall, {bill:.1f}s in model calls, "
        f"{local:.1f}s local work"
    )
    lines.append(f"  cost     : ${totals.get('cost_usd', 0):.4f}")

    total_tok = tok.get("total", 0)
    lines.append(
        f"  tokens   : {_fmt_tokens(total_tok)} total — "
        f"{_fmt_tokens(tok.get('input', 0))} in, "
        f"{_fmt_tokens(tok.get('output', 0))} out, "
        f"{_fmt_tokens(tok.get('cache_creation', 0))} cache-write, "
        f"{_fmt_tokens(tok.get('cache_read', 0))} cache-read"
    )

    # Cache reuse is the largest controllable cost lever (PRD §3), so it is
    # stated as a rate rather than left for the reader to divide.
    cached = tok.get("cache_read", 0)
    cache_base = cached + tok.get("cache_creation", 0) + tok.get("input", 0)
    if cache_base:
        lines.append(f"  cache    : {100.0 * cached / cache_base:.1f}% of input tokens served from cache")

    models = totals.get("models") or []
    lines.append(f"  model    : {', '.join(models) if models else 'not recorded'}")

    calls = totals.get("model_calls", 0)
    attempts = totals.get("attempts", 0)
    retries = totals.get("retries", 0)
    retry_line = f"  calls    : {calls} model call(s), {attempts} attempt(s), {retries} retr{'y' if retries == 1 else 'ies'}"
    lines.append(retry_line)

    reasons = totals.get("retry_reasons") or []
    if reasons:
        counted: dict[str, int] = {}
        for r in reasons:
            counted[r] = counted.get(r, 0) + 1
        for reason, n in sorted(counted.items(), key=lambda kv: -kv[1]):
            lines.append(f"             ! {n}x {reason}")

    fallbacks = totals.get("fallbacks_used", 0)
    if fallbacks:
        # Not a footnote. Text-mode fallback means schema conformance was not
        # enforced by the runtime, so the artifact is lower-confidence and the
        # reader must be told without having to go looking in errors.jsonl.
        lines.append(
            f"  fallback : {fallbacks} stage(s) used the text-mode fallback — "
            "schema was NOT enforced by the runtime; treat those stages as lower confidence"
        )

    qv, qt = totals.get("quotes_verified", 0), totals.get("quotes_total", 0)
    if qt:
        lines.append(
            f"  grounding: {qv}/{qt} quotes verified against their cited page "
            f"({100.0 * qv / qt:.1f}%)"
        )

    if stages:
        lines.append("")
        lines.append(
            f"  {'stage':<15} {'wall':>8} {'model':>8} {'cost':>9} {'tokens':>9} "
            f"{'calls':>6} {'retry':>6}  quotes"
        )
        for st in stages:
            stok = (st.get("tokens") or {}).get("total", 0)
            st_retries = max(0, st.get("attempts", 0) - st.get("model_calls", 0))
            q = ""
            if st.get("quotes_total"):
                q = f"{st['quotes_verified']}/{st['quotes_total']}"
            flag = " FALLBACK" if st.get("fallback_used") else ""
            lines.append(
                f"  {st.get('stage', '?'):<15} "
                f"{st.get('wall_clock_s', 0):>7.1f}s "
                f"{st.get('billable_s', 0):>7.1f}s "
                f"${st.get('cost_usd', 0):>8.4f} "
                f"{_fmt_tokens(stok):>9} "
                f"{st.get('model_calls', 0):>6} "
                f"{st_retries:>6}  {q}{flag}"
            )
        # Per-stage model identity, printed only when it differs from the run's
        # single model — repeating one model id on every row is noise, but a
        # stage served by a different model is exactly what this field exists to
        # make visible.
        stage_models = {st.get("model") for st in stages if st.get("model")}
        if len(stage_models) > 1:
            lines.append("")
            for st in stages:
                if st.get("model"):
                    lines.append(f"    {st.get('stage', '?'):<15} model: {st['model']}")

    return lines
