"""Tests for run telemetry (PRD 06 §3) and the single-criterion dry run.

The tests that matter most here are the ones pinning the two non-obvious facts
about the CLI's usage envelope, both verified against a live envelope:

  1. `input_tokens` EXCLUDES the cached prefix, so `total` must sum all four
     counters. A total of input+output understates a cached call by orders of
     magnitude, and that error would silently make cache efficiency look like a
     cost saving that never happened.
  2. The resolved model id is a KEY of `modelUsage`, not a scalar field. There
     is no top-level `model`. Recording the literal "default" — which is what
     the engine did before — is unreproducible.

The rest pin the failure-safety properties: telemetry must never fail a run, so
every collector returns a benign value rather than raising on malformed input.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from l1 import telemetry as t


# A REAL envelope captured from Claude Code 2.1.215 with
#   echo "say OK" | claude --print --output-format json
# Trimmed of fields the engine does not read. The numbers are genuine and are
# what make the cache-accounting test meaningful: input_tokens is 2 while
# cache_creation_input_tokens is 22404.
LIVE_ENVELOPE = {
    "type": "result",
    "subtype": "success",
    "is_error": False,
    "duration_ms": 1562,
    "result": "OK",
    "session_id": "2f8b1c29-c432-4398-b58f-ab443d07464a",
    "total_cost_usd": 0.22415000000000002,
    "usage": {
        "input_tokens": 2,
        "cache_creation_input_tokens": 22404,
        "cache_read_input_tokens": 0,
        "output_tokens": 4,
        "service_tier": "standard",
    },
    "modelUsage": {
        "claude-opus-4-8[1m]": {
            "inputTokens": 2,
            "outputTokens": 4,
            "cacheReadInputTokens": 0,
            "cacheCreationInputTokens": 22404,
            "costUSD": 0.22415000000000002,
        }
    },
}


class TestTokenAccounting:
    def test_extracts_all_four_counters_from_a_live_envelope(self):
        tok = t.tokens_from_envelope(LIVE_ENVELOPE)
        assert tok["input"] == 2
        assert tok["output"] == 4
        assert tok["cache_creation"] == 22404
        assert tok["cache_read"] == 0

    def test_total_sums_all_four_counters_not_just_input_and_output(self):
        """THE central accounting fact. `input_tokens` excludes the cached prefix.

        In the live envelope input+output is 6 while the real work was 22410
        tokens. A `total` of 6 would understate this call by ~3700x, and every
        cache-efficiency and cost-per-deal figure built on it would be wrong.
        """
        tok = t.tokens_from_envelope(LIVE_ENVELOPE)
        assert tok["input"] + tok["output"] == 6  # the WRONG total
        assert tok["total"] == 22410  # the right one
        assert tok["total"] == sum(tok[k] for k in t.TOKEN_FIELDS)

    def test_missing_usage_yields_zeros_rather_than_raising(self):
        """Telemetry must never be the reason a run fails."""
        for bad in ({}, {"usage": None}, {"usage": "nonsense"}, None, "not a dict"):
            assert t.tokens_from_envelope(bad) == t.zero_tokens()

    def test_non_numeric_counters_become_zero_not_a_crash(self):
        tok = t.tokens_from_envelope({"usage": {"input_tokens": "many", "output_tokens": 7}})
        assert tok["input"] == 0
        assert tok["output"] == 7

    def test_add_tokens_is_elementwise(self):
        a = t.tokens_from_envelope(LIVE_ENVELOPE)
        summed = t.add_tokens(a, a)
        assert summed["cache_creation"] == 44808
        assert summed["total"] == 44820


class TestModelResolution:
    def test_reads_the_resolved_id_from_modelusage_keys(self):
        """There is no top-level `model` in the envelope — the id is a KEY."""
        assert "model" not in LIVE_ENVELOPE
        assert t.model_from_envelope(LIVE_ENVELOPE) == "claude-opus-4-8[1m]"

    def test_never_returns_the_string_default(self):
        """The defect this field replaces. "default" is unreproducible."""
        assert t.model_from_envelope({"model": "default"}) is None
        assert t.model_from_envelope({}) is None
        assert t.model_from_envelope(None) is None

    def test_multiple_models_are_all_reported_not_silently_first(self):
        env = {"modelUsage": {"claude-b": {}, "claude-a": {}}}
        assert t.model_from_envelope(env) == "claude-a+claude-b"


class TestStageTelemetry:
    def _result(self, **kw):
        from l1.claude_runner import ClaudeResult

        base = dict(
            text="", structured={}, cost_usd=0.5, duration_ms=100,
            session_id=None, raw=LIVE_ENVELOPE,
            tokens=t.tokens_from_envelope(LIVE_ENVELOPE),
            model="claude-opus-4-8[1m]", attempts=1, retry_reasons=[], billable_s=1.5,
        )
        base.update(kw)
        return ClaudeResult(**base)

    def test_two_calls_accumulate_into_one_stage(self):
        """Scoring makes two logical calls — lenient and strict."""
        st = t.StageTelemetry(stage="scoring")
        st.record_call(self._result())
        st.record_call(self._result())
        assert st.model_calls == 2
        assert st.tokens["total"] == 44820
        assert st.cost_usd == 1.0
        assert st.billable_s == 3.0
        assert st.model == "claude-opus-4-8[1m]"

    def test_attempts_counts_failed_subprocess_invocations(self):
        """A stage that succeeded on attempt 4 is a different health signal from
        one that succeeded first time at the same cost."""
        st = t.StageTelemetry(stage="extraction")
        st.record_call(
            self._result(attempts=3, retry_reasons=["error_max_structured_output_retries", "timeout"])
        )
        assert st.model_calls == 1
        assert st.attempts == 3
        assert st.retry_reasons == ["error_max_structured_output_retries", "timeout"]

    def test_fallback_is_sticky_across_calls(self):
        """One fallback in a multi-call stage taints the stage. Lower-confidence
        output must be visible in the run record, not just in logs."""
        st = t.StageTelemetry(stage="scoring")
        st.record_call(self._result(used_fallback=True))
        st.record_call(self._result(used_fallback=False))
        assert st.fallback_used is True

    def test_a_stage_with_no_model_calls_has_model_none_not_default(self):
        """Diligence is pure network work. None says that honestly."""
        st = t.StageTelemetry(stage="diligence")
        assert st.model is None
        assert st.as_dict()["model"] is None

    def test_quotes_accumulate_additively(self):
        st = t.StageTelemetry(stage="scoring")
        st.record_quotes(45, 45)
        st.record_quotes(23, 26)
        assert (st.quotes_verified, st.quotes_total) == (68, 71)


class TestTotals:
    def test_retries_is_attempts_beyond_the_first_per_call(self):
        """NOT len(retry_reasons): a retry whose reason could not be classified
        still counts, and undercounting retries is the blindness this removes."""
        a = t.StageTelemetry(stage="classification", model_calls=1, attempts=3)
        b = t.StageTelemetry(stage="scoring", model_calls=2, attempts=2)
        totals = t.totals_from_stages([a, b])
        assert totals["model_calls"] == 3
        assert totals["attempts"] == 5
        assert totals["retries"] == 2  # 3-1 from a, 2-2 from b

    def test_fallbacks_used_counts_stages_not_calls(self):
        a = t.StageTelemetry(stage="a", fallback_used=True)
        b = t.StageTelemetry(stage="b", fallback_used=True)
        c = t.StageTelemetry(stage="c")
        assert t.totals_from_stages([a, b, c])["fallbacks_used"] == 2

    def test_totals_over_no_stages_is_zeros_not_an_error(self):
        totals = t.totals_from_stages([])
        assert totals["cost_usd"] == 0
        assert totals["tokens"]["total"] == 0


class TestRunHeaderFields:
    def test_git_sha_is_a_short_sha_or_none_and_never_raises(self):
        sha = t.engine_git_sha()
        assert sha is None or (4 <= len(sha) <= 40 and all(c in "0123456789abcdef" for c in sha))

    def test_criteria_status_is_stated_not_inferred_from_null(self):
        assert t.criteria_status(3) == "ACTIVE"
        assert t.criteria_status(None) == "DRAFT"
        assert t.criteria_status(0) == "ACTIVE"  # version 0 is a version

    def test_egress_country_honours_the_override_without_touching_the_network(self, monkeypatch):
        monkeypatch.setenv("L1_EGRESS_COUNTRY", "in")
        assert t.egress_country() == "IN"

    def test_egress_empty_override_disables_the_lookup(self, monkeypatch):
        """An air-gapped or offline run records null rather than hanging."""
        monkeypatch.setenv("L1_EGRESS_COUNTRY", "")
        assert t.egress_country() is None

    def test_egress_returns_none_on_any_network_failure(self, monkeypatch):
        """Must NOT fail the run. Every exception becomes None."""
        monkeypatch.delenv("L1_EGRESS_COUNTRY", raising=False)
        import urllib.request

        def boom(*a, **kw):
            raise OSError("no network")

        monkeypatch.setattr(urllib.request, "urlopen", boom)
        assert t.egress_country() is None

    def test_egress_rejects_a_captive_portal_html_response(self, monkeypatch):
        """A portal returning '<!DOCTYPE' must record null, not a country '<!'."""
        monkeypatch.delenv("L1_EGRESS_COUNTRY", raising=False)
        import urllib.request

        class FakeResp:
            def read(self, n):
                return b"<!DOCTYPE html>"[:n]

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: FakeResp())
        assert t.egress_country() is None


class TestPageExtractionMethod:
    def test_complete_text_layer(self):
        assert t.page_extraction_method(["a", "b", "c"]) == "text_layer"

    def test_any_empty_page_makes_it_mixed(self):
        """One image-only slide is enough to weaken every claim of absence."""
        assert t.page_extraction_method(["a", "   \n ", "c"]) == "mixed"

    def test_all_pages_empty_is_ocr_territory(self):
        assert t.page_extraction_method(["", "  "]) == "ocr"


class TestInspectRendering:
    def test_a_run_without_telemetry_renders_a_notice_not_a_crash(self):
        """Runs predating telemetry must still inspect cleanly."""
        lines = t.render_telemetry({"run_id": "x"})
        assert any("not recorded" in l for l in lines)

    def test_renders_tokens_cache_rate_retries_and_grounding(self):
        run = {
            "telemetry": {
                "totals": {
                    "wall_clock_s": 525.4, "billable_s": 498.1, "cost_usd": 2.30,
                    "tokens": {"input": 412330, "output": 38104,
                               "cache_creation": 86200, "cache_read": 301880,
                               "total": 838514},
                    "models": ["claude-opus-4-8[1m]"], "model_calls": 6,
                    "attempts": 8, "retries": 2,
                    "retry_reasons": ["error_max_structured_output_retries"] * 2,
                    "fallbacks_used": 0, "quotes_verified": 68, "quotes_total": 71,
                },
                "stages": [
                    {"stage": "extraction", "wall_clock_s": 123.3, "billable_s": 120.0,
                     "cost_usd": 0.418, "tokens": {"total": 194600},
                     "model": "claude-opus-4-8[1m]", "model_calls": 1, "attempts": 2,
                     "quotes_verified": 45, "quotes_total": 45, "fallback_used": False},
                ],
            }
        }
        out = "\n".join(t.render_telemetry(run))
        assert "838.5k" in out                    # token total, humanised
        assert "claude-opus-4-8[1m]" in out       # resolved model, not "default"
        assert "2 retries" in out
        assert "error_max_structured_output_retries" in out
        assert "68/71" in out                     # grounding metric
        assert "local work" in out                # wall vs billable split
        assert "% of input tokens served from cache" in out
        assert "extraction" in out                # per-stage table

    def test_a_fallback_is_rendered_prominently_not_as_a_footnote(self):
        run = {"telemetry": {"totals": {"fallbacks_used": 1, "tokens": {}}, "stages": []}}
        out = "\n".join(t.render_telemetry(run))
        assert "FALLBACK" in out.upper()
        assert "lower confidence" in out


class TestRetryReasonClassification:
    def test_subtype_is_preferred_over_prose(self):
        """§7's ~2-in-8 rate is only trackable if the same failure is always
        counted under the same name. The subtype is the runtime's own name."""
        from l1.claude_runner import _classify_retry_reason

        assert _classify_retry_reason("claude invocation timed out after 1800s") == "timeout"
        assert _classify_retry_reason("output was not valid JSON") == "invalid_json_output"
        assert _classify_retry_reason("returned no structured_output") == "missing_structured_output"
        assert _classify_retry_reason("claude exited 1. stderr: <empty>") == "nonzero_exit"
        assert _classify_retry_reason("something novel") == "unknown"
