"""Tests for retry robustness in the claude subprocess runner.

Background: structured-output requests intermittently fail with "The model's
tool call could not be parsed" or subtype `error_max_structured_output_retries`.
Measured at ~2 failures in 8 identical trivial calls, so it is a property of the
runtime, not of schema complexity or prompt size. These tests pin the recovery
behaviour without making network calls.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from l1 import claude_runner
from l1.claude_runner import BudgetTracker, run_claude
from l1.errors import BudgetExceededError, StageFailureError

SCHEMA = {"type": "object", "required": ["a"], "properties": {"a": {"type": "string"}}}


class FakeCtx:
    """Captures warnings the way RunContext does, without touching disk."""

    def __init__(self):
        self.warnings = []

    def warn(self, message, detail=None):
        self.warnings.append((message, detail or {}))


def _envelope(**over):
    base = {
        "type": "result",
        "is_error": False,
        "result": "",
        "total_cost_usd": 0.01,
        "duration_ms": 100,
        "session_id": "s",
        "structured_output": {"a": "ok"},
    }
    base.update(over)
    return base


def _completed(envelope, returncode=0, stderr=b""):
    return subprocess.CompletedProcess(
        args=["claude"], returncode=returncode,
        stdout=json.dumps(envelope).encode(), stderr=stderr,
    )


def _patch_runs(monkeypatch, sequence):
    """Feed a scripted sequence of subprocess results; record the prompts sent."""
    calls = {"n": 0, "prompts": [], "cmds": []}

    def fake_run(cmd, input=None, capture_output=None, timeout=None, cwd=None):
        i = calls["n"]
        calls["n"] += 1
        calls["prompts"].append((input or b"").decode())
        calls["cmds"].append(cmd)
        item = sequence[min(i, len(sequence) - 1)]
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(claude_runner.subprocess, "run", fake_run)
    monkeypatch.setattr(claude_runner.time, "sleep", lambda s: None)  # no real backoff
    monkeypatch.setattr(claude_runner, "claude_available", lambda: True)
    return calls


class TestRetryOnTransientFailure:

    def test_recovers_from_a_single_tool_call_parse_failure(self, monkeypatch):
        """The exact observed failure, recovered on attempt 2."""
        calls = _patch_runs(monkeypatch, [
            _completed(_envelope(is_error=True,
                                 result="The model's tool call could not be parsed (retry also failed).")),
            _completed(_envelope()),
        ])
        ctx = FakeCtx()
        res = run_claude("p", stage="classification", json_schema=SCHEMA, ctx=ctx)
        assert res.structured == {"a": "ok"}
        assert res.used_fallback is False
        assert calls["n"] == 2

    def test_recovers_from_max_structured_output_retries_subtype(self, monkeypatch):
        """The other observed signature — seen on the 25KB extraction schema."""
        calls = _patch_runs(monkeypatch, [
            _completed(_envelope(is_error=True, subtype="error_max_structured_output_retries",
                                 result="error_max_structured_output_retries")),
            _completed(_envelope()),
        ])
        res = run_claude("p", stage="extraction", json_schema=SCHEMA, ctx=FakeCtx())
        assert res.structured == {"a": "ok"}
        assert calls["n"] == 2

    def test_makes_four_attempts_before_giving_up(self, monkeypatch):
        failure = _completed(_envelope(is_error=True, result="could not be parsed"))
        calls = _patch_runs(monkeypatch, [failure])
        with pytest.raises(StageFailureError):
            run_claude("p", stage="classification", json_schema=SCHEMA, ctx=FakeCtx())
        # 4 structured attempts + 1 text-mode fallback
        assert calls["n"] == 5

    def test_retry_is_not_byte_identical(self, monkeypatch):
        """An identical request can fail identically, so the replay must differ."""
        calls = _patch_runs(monkeypatch, [
            _completed(_envelope(is_error=True, result="could not be parsed")),
            _completed(_envelope()),
        ])
        run_claude("ORIGINAL", stage="classification", json_schema=SCHEMA, ctx=FakeCtx())
        assert calls["prompts"][0] != calls["prompts"][1]
        assert "Attempt 2" in calls["prompts"][1]
        assert "ORIGINAL" in calls["prompts"][1], "retry dropped the original prompt"

    def test_every_failed_attempt_is_logged_with_raw_output(self, monkeypatch):
        """Invariant from the diagnosis: the next failure must be diagnosable
        from errors.jsonl without bisection."""
        _patch_runs(monkeypatch, [
            _completed(_envelope(is_error=True, result="could not be parsed")),
            _completed(_envelope(is_error=True, result="could not be parsed")),
            _completed(_envelope()),
        ])
        ctx = FakeCtx()
        run_claude("p", stage="classification", json_schema=SCHEMA, ctx=ctx)
        assert len(ctx.warnings) == 2
        for msg, detail in ctx.warnings:
            assert "attempt" in msg.lower()
            assert detail["attempt"] in (1, 2)
            assert "raw_head" in detail, "raw output not captured for diagnosis"

    def test_cost_of_failed_attempts_is_still_charged(self, monkeypatch):
        """A failed structured-output attempt still burns tokens. A budget that
        ignored retries would understate real spend."""
        _patch_runs(monkeypatch, [
            _completed(_envelope(is_error=True, result="could not be parsed", total_cost_usd=0.05)),
            _completed(_envelope(total_cost_usd=0.05)),
        ])
        budget = BudgetTracker(10.0)
        run_claude("p", stage="classification", json_schema=SCHEMA, budget=budget, ctx=FakeCtx())
        assert budget.spent_usd == pytest.approx(0.10)


class TestNonTransientFailuresDoNotRetry:

    def test_bad_flag_fails_immediately(self, monkeypatch):
        """A malformed invocation will fail identically forever; retrying wastes
        minutes. This is the --json-schema-as-filepath bug we actually hit."""
        calls = _patch_runs(monkeypatch, [
            _completed({}, returncode=1,
                       stderr=b"Error: --json-schema is not valid JSON: Unrecognized token '/'"),
        ])
        with pytest.raises(StageFailureError, match="not valid JSON"):
            run_claude("p", stage="classification", json_schema=SCHEMA, ctx=FakeCtx())
        assert calls["n"] == 1, "a permanent invocation error was retried"

    def test_crash_with_empty_stderr_IS_retried(self, monkeypatch):
        """The counterpart to the test above, and the distinction is subtle.

        MEASURED: extraction intermittently exits 1 with completely empty stderr,
        while the byte-identical invocation succeeds on retry. A process that died
        without explaining itself is transient; a process that printed a usage
        error is not. Getting this backwards either wastes minutes retrying a bad
        flag, or fails a 52-page analysis on a recoverable crash.
        """
        calls = _patch_runs(monkeypatch, [
            _completed({}, returncode=1, stderr=b""),
            _completed(_envelope()),
        ])
        res = run_claude("p", stage="extraction", json_schema=SCHEMA, ctx=FakeCtx())
        assert res.structured == {"a": "ok"}
        assert calls["n"] == 2

    def test_budget_exceeded_is_not_retried(self, monkeypatch):
        _patch_runs(monkeypatch, [_completed(_envelope(total_cost_usd=99.0))])
        with pytest.raises(BudgetExceededError):
            run_claude("p", stage="classification", json_schema=SCHEMA,
                       budget=BudgetTracker(1.0), ctx=FakeCtx())


class TestTextModeFallback:

    def test_falls_back_and_flags_the_degradation(self, monkeypatch):
        """After N structured failures, parse JSON from prose — but never silently."""
        failure = _completed(_envelope(is_error=True, result="could not be parsed"))
        fallback = _completed(_envelope(
            structured_output=None,
            result='Here is the object:\n```json\n{"a": "from-text"}\n```',
        ))
        _patch_runs(monkeypatch, [failure, failure, failure, failure, fallback])
        ctx = FakeCtx()
        res = run_claude("p", stage="classification", json_schema=SCHEMA, ctx=ctx)
        assert res.structured == {"a": "from-text"}
        assert res.used_fallback is True, "fallback must be visible, not silent"
        assert any("falling back" in m.lower() for m, _ in ctx.warnings)

    def test_raises_when_even_the_fallback_yields_no_json(self, monkeypatch):
        failure = _completed(_envelope(is_error=True, result="could not be parsed"))
        prose = _completed(_envelope(structured_output=None, result="I cannot help with that."))
        _patch_runs(monkeypatch, [failure, failure, failure, failure, prose])
        with pytest.raises(StageFailureError):
            run_claude("p", stage="classification", json_schema=SCHEMA, ctx=FakeCtx())


class TestSalvageJson:

    @pytest.mark.parametrize("text,expected", [
        ('{"a": 1}', {"a": 1}),
        ('```json\n{"a": 1}\n```', {"a": 1}),
        ('Sure! {"a": 1} hope that helps', {"a": 1}),
        ("no json here", None),
        ("[1,2,3]", None),  # array is not a valid stage payload
    ])
    def test_salvage(self, text, expected):
        assert claude_runner._salvage_json(text) == expected


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
