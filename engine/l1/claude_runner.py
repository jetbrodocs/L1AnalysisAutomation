"""Invocation of `claude -p` as a subprocess, one call per stage.

Auth posture (PRD §7): the engine is auth-agnostic. It invokes `claude` and does
not inspect how authentication resolves. No code here reads ANTHROPIC_API_KEY,
checks for a config file, or branches on auth context. Only the environment
differs between a developer's subscription and a worker's API key.

VERIFIED EMPIRICALLY on Claude Code 2.1.215 (see README):
  - `--json-schema` works and returns the parsed object in the result JSON under
    the `structured_output` key.
  - `--output-format json` wraps everything in a result envelope carrying
    `total_cost_usd`, `is_error`, and `usage`.
  - `--bare` fails with "Not logged in" when ANTHROPIC_API_KEY is unset, which
    confirms it is worker-context only. The engine therefore does not use it.
  - There is NO citations flag on the CLI. See README for the consequence.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from .errors import BudgetExceededError, StageFailureError
from .telemetry import model_from_envelope, tokens_from_envelope, zero_tokens

DEFAULT_TIMEOUT_S = 1800


@dataclass
class ClaudeResult:
    text: str
    structured: dict | None
    cost_usd: float
    duration_ms: int
    session_id: str | None
    raw: dict
    # True when structured output failed and the text-mode fallback produced this
    # object. Surfaced into the artifact so a degraded run is visible, not silent.
    used_fallback: bool = False

    # ---- telemetry (PRD §3) ----
    # All of this was already in the result envelope and was being thrown away.
    # See l1/telemetry.py for the envelope shape and why `total` sums four
    # counters rather than two.
    tokens: dict = field(default_factory=zero_tokens)
    # The RESOLVED model id, read from the envelope's `modelUsage` keys. Never
    # the string "default": a run recorded as having used "the default" cannot
    # be reproduced once the default moves.
    model: str | None = None
    # Subprocess invocations this logical call consumed, INCLUDING failed ones.
    # A stage that succeeded on attempt 4 is a different health signal from one
    # that succeeded first time at the same cost, and only this number
    # distinguishes them.
    attempts: int = 1
    retry_reasons: list[str] = field(default_factory=list)
    # Seconds spent inside `claude` subprocesses, summed over every attempt.
    # Failed attempts count: they consumed real time and real tokens, and a
    # billable figure that excluded them would understate a retry storm exactly
    # when it matters most.
    billable_s: float = 0.0


class BudgetTracker:
    """Cumulative spend ceiling across all stages of a run.

    `claude --max-budget-usd` bounds a single invocation; it has no notion of the
    run. Five stages each under the per-call ceiling can still blow a run budget,
    so the ceiling is enforced here across calls as well as passed down.
    """

    def __init__(self, max_usd: float | None):
        self.max_usd = max_usd
        self.spent_usd = 0.0

    def remaining(self) -> float | None:
        if self.max_usd is None:
            return None
        return max(0.0, self.max_usd - self.spent_usd)

    def check_before(self, stage: str) -> None:
        if self.max_usd is None:
            return
        if self.spent_usd >= self.max_usd:
            raise BudgetExceededError(
                f"budget of ${self.max_usd:.2f} already exhausted "
                f"(${self.spent_usd:.4f} spent) before stage '{stage}'",
                {"stage": stage, "spent_usd": self.spent_usd, "max_usd": self.max_usd},
            )

    def record(self, cost: float, stage: str) -> None:
        self.spent_usd += cost or 0.0
        if self.max_usd is not None and self.spent_usd > self.max_usd:
            raise BudgetExceededError(
                f"budget of ${self.max_usd:.2f} exceeded during stage '{stage}' "
                f"(${self.spent_usd:.4f} spent)",
                {"stage": stage, "spent_usd": self.spent_usd, "max_usd": self.max_usd},
            )


def claude_available() -> bool:
    return shutil.which("claude") is not None


def run_claude(
    prompt: str,
    *,
    stage: str,
    system_prompt: str | None = None,
    json_schema: dict | None = None,
    model: str | None = None,
    budget: BudgetTracker | None = None,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    cwd: Path | None = None,
    max_attempts: int = 4,
    ctx=None,
) -> ClaudeResult:
    """One logical `claude -p` call, retried on transient structured-output failure.

    MEASURED FAILURE MODE (see README): a structured-output request intermittently
    returns `is_error: true` with "The model's tool call could not be parsed
    (retry also failed)" or subtype `error_max_structured_output_retries`. Measured
    at roughly 2 failures in 8 identical calls on trivial schemas, so it is a
    property of the runtime rather than of schema complexity or prompt size.

    Two things were tested and found NOT to be the cause, so do not "fix" them:
      - Schema nullable encoding. `{"type":["string","null"]}` vs an anyOf
        equivalent measured 6/8 both ways. An early n=5 sample suggested anyOf was
        better; it was noise.
      - Schema size / depth / prompt length. A 25KB schema over 52 pages of deck
        text succeeds routinely.

    Because an identical request can fail identically, the retry is NOT
    byte-identical: attempt 2+ appends a short clarifying instruction nudging the
    model to emit the tool call cleanly. Each failed attempt is logged to
    errors.jsonl with its raw output so the next failure is diagnosable without
    bisection.

    The prompt goes in on stdin rather than argv. Deck text runs to hundreds of
    kilobytes and would exceed ARG_MAX as an argument; stdin has no such limit.
    """
    last_error: str | None = None
    # Telemetry accumulated ACROSS attempts. A failed attempt consumed tokens,
    # money and wall-clock before it failed, so its cost is already recorded on
    # the budget; its time and its reason are recorded here so the run record
    # shows a retry storm as a retry storm rather than as one slow call.
    retry_reasons: list[str] = []
    billable_s = 0.0

    for attempt in range(1, max_attempts + 1):
        started = time.monotonic()
        try:
            result = _run_claude_once(
                prompt,
                stage=stage,
                system_prompt=system_prompt,
                json_schema=json_schema,
                model=model,
                budget=budget,
                timeout_s=timeout_s,
                cwd=cwd,
                attempt=attempt,
            )
        except TransientClaudeError as exc:
            billable_s += time.monotonic() - started
            # The envelope subtype is the precise, machine-comparable reason —
            # `error_max_structured_output_retries` is the measured ~2-in-8
            # failure mode (§7), and recording the subtype rather than the prose
            # message is what makes that rate trackable as it changes. The prose
            # message varies; the subtype does not.
            retry_reasons.append(
                exc.detail.get("envelope_subtype")
                or _classify_retry_reason(exc.message)
            )
            last_error = exc.message
            if ctx is not None:
                ctx.warn(
                    f"stage '{stage}': attempt {attempt}/{max_attempts} failed "
                    f"({exc.message}); retrying",
                    {
                        "stage": stage,
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "error": exc.message,
                        "raw_head": exc.detail.get("raw_head", "")[:500],
                    },
                )
            if attempt == max_attempts:
                break
            # Exponential backoff: 2s, 4s, 8s. NOT counted as billable — the
            # sleep is engine-local waiting, not model time, and folding it into
            # billable_s would make backoff look like inference.
            time.sleep(2 ** attempt)
            continue

        # Success. Attach the telemetry accumulated across every attempt this
        # logical call took, so the caller sees one call that cost N attempts
        # rather than a clean call with the failures invisible.
        billable_s += time.monotonic() - started
        result.attempts = attempt
        result.retry_reasons = retry_reasons
        result.billable_s = round(billable_s, 3)
        return result

    # Structured output exhausted its attempts. Fall back to plain text and parse
    # the JSON ourselves, then validate against the same schema. Slower and less
    # reliable, but better than losing a 52-page analysis to a flaky tool call.
    # The fallback is FLAGGED on the result so it is visible, never silent.
    if json_schema is not None:
        if ctx is not None:
            ctx.warn(
                f"stage '{stage}': structured output failed {max_attempts} times; "
                "falling back to text-mode JSON parsing",
                {"stage": stage, "last_error": last_error},
            )
        fb_started = time.monotonic()
        result = _run_text_fallback(
            prompt,
            stage=stage,
            system_prompt=system_prompt,
            json_schema=json_schema,
            model=model,
            budget=budget,
            timeout_s=timeout_s,
            cwd=cwd,
            ctx=ctx,
        )
        billable_s += time.monotonic() - fb_started
        if result is not None:
            # The fallback is itself an attempt, so it is counted. A stage that
            # needed 4 structured attempts plus a fallback shows 5 attempts for
            # 1 model call — which is the signal, not an accounting artifact.
            result.attempts = max_attempts + 1
            result.retry_reasons = retry_reasons
            result.billable_s = round(billable_s, 3)
            return result

    raise StageFailureError(
        f"stage '{stage}': failed after {max_attempts} structured-output attempts "
        f"and a text-mode fallback. Last error: {last_error}",
        {"stage": stage, "attempts": max_attempts, "last_error": last_error},
    )


class TransientClaudeError(StageFailureError):
    """A failure worth retrying: a malformed tool call, not a bad request."""


# Error signatures that indicate a transient structured-output failure rather
# than a permanent problem with the request.
_TRANSIENT_MARKERS = (
    "could not be parsed",
    "error_max_structured_output_retries",
    "max_structured_output",
    "overloaded",
    "rate limit",
    "429",
    "500",
    "502",
    "503",
    "529",
    "timeout",
    "econnreset",
)


def _is_transient(message: str, subtype: str = "") -> bool:
    probe = f"{message} {subtype}".lower()
    return any(marker in probe for marker in _TRANSIENT_MARKERS)


# Coarse buckets for retries that carried no envelope subtype — a timeout or a
# non-zero exit never reaches the envelope, so there is no subtype to record.
# Deliberately few and deliberately coarse: the purpose is a countable category,
# and a long tail of one-off prose messages would defeat that.
_REASON_BUCKETS = (
    ("timed out", "timeout"),
    ("timeout", "timeout"),
    ("not valid json", "invalid_json_output"),
    ("no structured_output", "missing_structured_output"),
    ("could not be parsed", "unparseable_tool_call"),
    ("overloaded", "overloaded"),
    ("rate limit", "rate_limit"),
    ("429", "rate_limit"),
    ("econnreset", "connection_reset"),
)


def _classify_retry_reason(message: str) -> str:
    """Bucket a retry's prose message into a countable reason.

    Used only when the envelope carried no `subtype`. The subtype is always
    preferred where present because it is the runtime's own name for the
    failure, and §7's ~2-in-8 `error_max_structured_output_retries` rate is only
    trackable if the same failure is always counted under the same name.
    """
    probe = (message or "").lower()
    for marker, bucket in _REASON_BUCKETS:
        if marker in probe:
            return bucket
    if "exited" in probe:
        return "nonzero_exit"
    return "unknown"


def _run_claude_once(
    prompt: str,
    *,
    stage: str,
    system_prompt: str | None,
    json_schema: dict | None,
    model: str | None,
    budget: BudgetTracker | None,
    timeout_s: int,
    cwd: Path | None,
    attempt: int,
) -> ClaudeResult:
    """A single subprocess invocation."""
    if not claude_available():
        raise StageFailureError(
            "the `claude` executable was not found on PATH. The engine invokes "
            "Claude Code as a subprocess and cannot run without it."
        )

    if budget is not None:
        budget.check_before(stage)

    cmd = ["claude", "--print", "--output-format", "json"]

    # Tools are unnecessary for every stage the engine currently runs: each is a
    # pure text-in/JSON-out transform over page text already on disk. Denying
    # them removes filesystem and network reach from the subprocess entirely,
    # and removes the permission prompt that would otherwise hang a
    # non-interactive run.
    cmd += ["--permission-mode", "dontAsk", "--disallowed-tools", "Bash,Edit,Write,Read,WebFetch,WebSearch"]

    if model:
        cmd += ["--model", model]
    if system_prompt:
        cmd += ["--append-system-prompt", system_prompt]

    if json_schema is not None:
        # VERIFIED EMPIRICALLY: --json-schema accepts ONLY a literal JSON string,
        # not a file path. Passing a path yields:
        #   "Error: --json-schema is not valid JSON: JSON Parse error:
        #    Unrecognized token '/'"
        # so the schema goes on argv. Serialised compactly to stay well inside
        # ARG_MAX (~1MB on macOS); the extraction schema is ~6KB, so there is
        # ample headroom, but the guard below makes the failure legible if a
        # future schema grows pathologically.
        schema_json = json.dumps(json_schema, separators=(",", ":"))
        if len(schema_json) > 128_000:
            raise StageFailureError(
                f"stage '{stage}': JSON schema is {len(schema_json)} bytes, too large "
                "to pass on the command line. Split the stage into smaller schemas."
            )
        cmd += ["--json-schema", schema_json]

    if budget is not None:
        remaining = budget.remaining()
        if remaining is not None:
            cmd += ["--max-budget-usd", f"{remaining:.4f}"]

    # Vary the request on retry. An identical request can fail identically, so a
    # byte-for-byte replay is a weak retry.
    effective_prompt = prompt
    if attempt > 1:
        effective_prompt = (
            f"{prompt}\n\n"
            f"[Attempt {attempt}. The previous attempt's structured response could "
            "not be parsed. Emit exactly one well-formed result conforming to the "
            "schema, with no commentary before or after it.]"
        )

    try:
        proc = subprocess.run(
            cmd,
            input=effective_prompt.encode("utf-8"),
            capture_output=True,
            timeout=timeout_s,
            cwd=str(cwd) if cwd else None,
        )
    except subprocess.TimeoutExpired as exc:
        raise TransientClaudeError(
            f"stage '{stage}': claude invocation timed out after {timeout_s}s",
            {"stage": stage, "attempt": attempt, "raw_head": ""},
        ) from exc

    stdout = proc.stdout.decode("utf-8", errors="replace")
    stderr = proc.stderr.decode("utf-8", errors="replace")

    # A non-zero exit is decided on BEFORE looking at stdout. An invocation error
    # (unknown flag, malformed schema) writes its message to stderr and may still
    # emit something JSON-shaped on stdout; keying off "stdout is empty" let the
    # real error be masked and then retried four times.
    #
    # The distinction that matters is WHY it exited non-zero:
    #   - stderr names a usage/validation problem ("Error: --json-schema is not
    #     valid JSON") -> permanent. Retrying a bad flag can never succeed, and
    #     four retries of a 2-minute call wastes eight minutes to reach the same
    #     answer. Fail immediately with the real message.
    #   - stderr is empty, or names a known transient -> the process died without
    #     explaining itself. MEASURED: the extraction stage exits 1 with empty
    #     stderr intermittently, while the byte-identical invocation succeeds on
    #     retry. Treat as transient.
    if proc.returncode != 0:
        msg = f"claude exited {proc.returncode}. stderr: {stderr[:2000] or '<empty>'}"
        payload = {"stage": stage, "attempt": attempt, "raw_head": (stderr or stdout)[:500]}
        looks_like_usage_error = bool(stderr.strip()) and not _is_transient(stderr)
        if looks_like_usage_error:
            raise StageFailureError(f"stage '{stage}': {msg}", payload)
        raise TransientClaudeError(f"stage '{stage}': {msg}", payload)

    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise TransientClaudeError(
            f"stage '{stage}': claude output was not valid JSON despite "
            f"--output-format json",
            {"stage": stage, "attempt": attempt, "raw_head": stdout[:500]},
        ) from exc

    # Cost is recorded for every attempt, including failed ones. A failed
    # structured-output attempt still consumed tokens, and a budget that ignored
    # retries would understate real spend.
    cost = float(envelope.get("total_cost_usd") or 0.0)
    if budget is not None:
        budget.record(cost, stage)

    if envelope.get("is_error"):
        detail = str(envelope.get("result") or envelope.get("subtype") or "")
        subtype = str(envelope.get("subtype") or "")
        err = f"stage '{stage}': claude reported an error: {detail}"
        payload = {
            "stage": stage,
            "attempt": attempt,
            "envelope_subtype": subtype,
            "raw_head": stdout[:500],
        }
        if _is_transient(detail, subtype):
            raise TransientClaudeError(err, payload)
        raise StageFailureError(err, payload)

    structured = envelope.get("structured_output")
    text = envelope.get("result") or ""

    # A schema was requested but no structured_output came back — the model
    # answered in prose. Salvage a well-formed object if one is there, otherwise
    # treat as transient and retry rather than parsing prose into an artifact.
    if json_schema is not None and structured is None:
        salvaged = _salvage_json(text)
        if salvaged is None:
            raise TransientClaudeError(
                f"stage '{stage}': --json-schema was requested but claude returned "
                f"no structured_output",
                {"stage": stage, "attempt": attempt, "raw_head": text[:500]},
            )
        structured = salvaged

    return ClaudeResult(
        text=text,
        structured=structured,
        cost_usd=cost,
        duration_ms=int(envelope.get("duration_ms") or 0),
        session_id=envelope.get("session_id"),
        raw=envelope,
        tokens=tokens_from_envelope(envelope),
        model=model_from_envelope(envelope),
    )


def _run_text_fallback(
    prompt: str,
    *,
    stage: str,
    system_prompt: str | None,
    json_schema: dict,
    model: str | None,
    budget: BudgetTracker | None,
    timeout_s: int,
    cwd: Path | None,
    ctx=None,
) -> ClaudeResult | None:
    """Last resort: ask for JSON as plain text and parse it ourselves.

    This exists so a 52-page analysis is not lost to one flaky tool call. It is
    strictly worse than structured output — nothing enforces the schema on the
    model's side — so the parsed object is still validated by the calling stage,
    and `used_fallback` is set on the result so the degradation is visible in the
    artifact rather than silent.
    """
    schema_json = json.dumps(json_schema, indent=2)
    fallback_prompt = (
        f"{prompt}\n\n"
        "---\n"
        "Respond with a single JSON object conforming EXACTLY to this JSON Schema. "
        "Output only the JSON object — no prose, no explanation, no markdown fence.\n\n"
        f"{schema_json}"
    )

    cmd = ["claude", "--print", "--output-format", "json"]
    cmd += [
        "--permission-mode", "dontAsk",
        "--disallowed-tools", "Bash,Edit,Write,Read,WebFetch,WebSearch",
    ]
    if model:
        cmd += ["--model", model]
    if system_prompt:
        cmd += ["--append-system-prompt", system_prompt]
    if budget is not None:
        remaining = budget.remaining()
        if remaining is not None:
            cmd += ["--max-budget-usd", f"{remaining:.4f}"]

    try:
        proc = subprocess.run(
            cmd,
            input=fallback_prompt.encode("utf-8"),
            capture_output=True,
            timeout=timeout_s,
            cwd=str(cwd) if cwd else None,
        )
        envelope = json.loads(proc.stdout.decode("utf-8", errors="replace"))
    except (subprocess.TimeoutExpired, json.JSONDecodeError, ValueError):
        return None

    cost = float(envelope.get("total_cost_usd") or 0.0)
    if budget is not None:
        budget.record(cost, stage)

    if envelope.get("is_error"):
        return None

    text = envelope.get("result") or ""
    parsed = _salvage_json(text)
    if parsed is None:
        if ctx is not None:
            ctx.warn(
                f"stage '{stage}': text-mode fallback returned no parseable JSON object",
                {"stage": stage, "raw_head": text[:500]},
            )
        return None

    return ClaudeResult(
        text=text,
        structured=parsed,
        cost_usd=cost,
        duration_ms=int(envelope.get("duration_ms") or 0),
        session_id=envelope.get("session_id"),
        raw=envelope,
        used_fallback=True,
        tokens=tokens_from_envelope(envelope),
        model=model_from_envelope(envelope),
    )


def _salvage_json(text: str) -> dict | None:
    """Last-resort parse of a fenced or bare JSON object in prose output.

    Deliberately narrow: it only recovers a well-formed object, and returns None
    rather than guessing. This exists because a transient absence of
    structured_output should not discard an otherwise complete stage, not because
    prose parsing is an acceptable primary path.
    """
    text = text.strip()
    if text.startswith("```"):
        body = text.split("```", 2)
        if len(body) >= 2:
            candidate = body[1]
            if candidate.startswith("json"):
                candidate = candidate[4:]
            try:
                obj = json.loads(candidate.strip())
                return obj if isinstance(obj, dict) else None
            except json.JSONDecodeError:
                pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            obj = json.loads(text[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None
    return None
