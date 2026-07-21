"""Tests for `l1 test-criterion` (single-criterion dry run).

THE PROPERTY THAT MATTERS MOST is not that the command works — it is that it
does NOT fork the scoring stage. A dry run that behaves differently from
production is worse than no dry run, because the author tunes their guidance
against a harness that scores differently from the engine, and the rule then
misbehaves in the run that actually matters.

`test_reuses_the_scoring_stages_own_code_path` pins that structurally: it
monkeypatches each scoring function and asserts the dry run called it. If
someone later reimplements reconciliation or quote verification locally "to
avoid the import", these tests fail — which is the point.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from l1 import testcriterion as tc
from l1.criteria import load_criteria
from l1.errors import InvalidInputError

CRITERIA = Path(__file__).resolve().parents[1] / "criteria" / "default"


@pytest.fixture
def criteria_set():
    return load_criteria(CRITERIA)


class TestSingleCriterionSet:
    def test_narrows_to_exactly_one_criterion(self, criteria_set):
        single, crit = tc._single_criterion_set(criteria_set, "CR-0010")
        assert len(single.criteria) == 1
        assert len(single.active_criteria) == 1
        assert crit.criterion_code == "CR-0010"

    def test_preserves_set_metadata_verbatim(self, criteria_set):
        """The content hash must NOT be recomputed. The author needs to see
        WHICH rule text was tested; a hash invented here names a set that does
        not exist."""
        single, _ = tc._single_criterion_set(criteria_set, "CR-0010")
        assert single.content_hash == criteria_set.content_hash
        assert single.set_code == criteria_set.set_code
        assert single.version == criteria_set.version

    def test_the_prompt_payload_carries_only_that_criterion(self, criteria_set):
        """as_prompt_payload is what the model sees — it must be narrowed too,
        or the dry run would evaluate the whole set at full cost."""
        single, _ = tc._single_criterion_set(criteria_set, "CR-0010")
        payload = single.as_prompt_payload()
        assert len(payload) == 1
        assert payload[0]["criterion_code"] == "CR-0010"

    def test_unknown_code_names_the_available_ones(self, criteria_set):
        with pytest.raises(InvalidInputError) as exc:
            tc._single_criterion_set(criteria_set, "CR-9999")
        assert "CR-9999" in exc.value.message
        assert "CR-0010" in exc.value.message  # lists what IS available


class TestRunDirectoryValidation:
    def test_missing_directory_is_invalid_input(self, tmp_path):
        with pytest.raises(InvalidInputError):
            tc.test_criterion("CR-0010", tmp_path / "nope", criteria_dir=CRITERIA)

    def test_a_directory_without_run_json_is_rejected_by_name(self, tmp_path):
        with pytest.raises(InvalidInputError) as exc:
            tc.test_criterion("CR-0010", tmp_path, criteria_dir=CRITERIA)
        assert "run.json" in exc.value.message

    def test_a_run_missing_extraction_says_so_actionably(self, tmp_path):
        (tmp_path / "run.json").write_text('{"run_id": "x"}')
        with pytest.raises(InvalidInputError) as exc:
            tc.test_criterion("CR-0010", tmp_path, criteria_dir=CRITERIA)
        assert "extraction" in exc.value.message.lower()


class TestNoFork:
    """The dry run must call the scoring stage's own functions, not copies."""

    def test_reuses_the_scoring_stages_own_code_path(self, tmp_path, monkeypatch, criteria_set):
        from l1.stages import scoring as scoring_stage

        called: list[str] = []

        # A minimal but VALID run directory. Building it by hand rather than
        # running the pipeline keeps this test fast and offline; the artifacts
        # go through the real validating loader, so a shape error still fails.
        _write_minimal_run(tmp_path)

        def spy(name, real):
            def wrapper(*a, **kw):
                called.append(name)
                return real(*a, **kw)

            return wrapper

        monkeypatch.setattr(
            scoring_stage, "_build_prompt", spy("_build_prompt", scoring_stage._build_prompt)
        )
        monkeypatch.setattr(
            scoring_stage, "_reconcile", spy("_reconcile", scoring_stage._reconcile)
        )
        monkeypatch.setattr(
            scoring_stage,
            "_verify_evidence_quotes",
            spy("_verify_evidence_quotes", scoring_stage._verify_evidence_quotes),
        )
        monkeypatch.setattr(
            scoring_stage,
            "_repair_absence_evidence",
            spy("_repair_absence_evidence", scoring_stage._repair_absence_evidence),
        )
        monkeypatch.setattr(
            scoring_stage,
            "_enforce_blocked_criteria",
            spy("_enforce_blocked_criteria", scoring_stage._enforce_blocked_criteria),
        )

        # Stub only the model call. Everything between the prompt and the
        # verdict is the real scoring code.
        passes: list[str] = []

        def fake_pass(ctx, pass_name, standard, prompt, pages, budget, model):
            passes.append(pass_name)
            # The standard handed in must be the real one, not a paraphrase.
            assert standard in (scoring_stage.LENIENT_STANDARD, scoring_stage.STRICT_STANDARD)
            assert "CR-0010" in prompt
            return (
                {
                    "CR-0010": {
                        "criterion_code": "CR-0010",
                        "fired": True,
                        "evaluable": True,
                        "confidence": "high",
                        "evidence": [{"page": 1, "quote": "Gross Returns 18-20% p.a."}],
                        "absence_evidence": "Searched all 2 pages for 'net', 'net IRR'.",
                        "reasoning": "Gross only.",
                        "remediation": "Ask for net IRR.",
                    }
                },
                [],
                0.01,
            )

        monkeypatch.setattr(scoring_stage, "_run_pass", fake_pass)

        res = tc.test_criterion("CR-0010", tmp_path, criteria_dir=CRITERIA)

        # Every scoring function on the production path was exercised.
        assert "_build_prompt" in called
        assert "_reconcile" in called
        assert "_verify_evidence_quotes" in called
        assert "_repair_absence_evidence" in called
        assert "_enforce_blocked_criteria" in called

        # BOTH passes ran, independently — not one pass approximating two.
        assert passes == ["lenient", "strict"]

        assert res["criterion_code"] == "CR-0010"
        assert res["finding"]["fired"] is True
        assert res["finding"]["status"] == "fired"

    def test_reports_disagreement_as_contested_exactly_as_production_does(
        self, tmp_path, monkeypatch
    ):
        """Contested detection is scoring's, not a local approximation."""
        from l1.stages import scoring as scoring_stage

        _write_minimal_run(tmp_path)

        def fake_pass(ctx, pass_name, standard, prompt, pages, budget, model):
            fired = pass_name == "lenient"  # lenient fires, strict does not
            return (
                {
                    "CR-0010": {
                        "criterion_code": "CR-0010",
                        "fired": fired,
                        "evaluable": True,
                        "confidence": "high",
                        "evidence": [{"page": 1, "quote": "Gross Returns 18-20% p.a."}]
                        if fired
                        else [],
                        "absence_evidence": None,
                        "reasoning": f"{pass_name} reading",
                        "remediation": "Ask for net IRR." if fired else None,
                    }
                },
                [],
                0.01,
            )

        monkeypatch.setattr(scoring_stage, "_run_pass", fake_pass)
        res = tc.test_criterion("CR-0010", tmp_path, criteria_dir=CRITERIA)

        assert res["finding"]["contested"] is True
        assert res["finding"]["status"] == "contested"
        # Confidence is forced low on a contested finding — the disagreement IS
        # the uncertainty, whatever either pass claimed.
        assert res["finding"]["confidence"] == "low"
        assert res["lenient"]["fired"] is True
        assert res["strict"]["fired"] is False

        out = "\n".join(tc.render_result(res))
        assert "CONTESTED" in out
        assert "DISAGREE" in out

    def test_a_fired_veto_does_not_raise_because_this_is_an_authoring_tool(
        self, tmp_path, monkeypatch, criteria_set
    ):
        """run_scoring raises VetoError so the pipeline exits 11. A dry run must
        report a fired veto and return normally — an author is testing a rule,
        not deciding on a fund."""
        from l1.stages import scoring as scoring_stage

        veto = next((c for c in criteria_set.active_criteria if c.is_veto), None)
        if veto is None:
            pytest.skip("no veto-tier criterion in the default set")

        _write_minimal_run(tmp_path)

        def fake_pass(ctx, pass_name, standard, prompt, pages, budget, model):
            return (
                {
                    veto.criterion_code: {
                        "criterion_code": veto.criterion_code,
                        "fired": True,
                        "evaluable": True,
                        "confidence": "high",
                        "evidence": [{"page": 1, "quote": "Gross Returns 18-20% p.a."}],
                        "absence_evidence": None,
                        "reasoning": "veto condition met",
                        "remediation": "escalate",
                    }
                },
                [],
                0.01,
            )

        monkeypatch.setattr(scoring_stage, "_run_pass", fake_pass)
        res = tc.test_criterion(veto.criterion_code, tmp_path, criteria_dir=CRITERIA)
        assert res["finding"]["fired"] is True
        assert res["finding"]["tier"] == "VETO"


class TestDoesNotMutateTheRun:
    def test_a_dry_run_writes_nothing_into_the_run_directory(self, tmp_path, monkeypatch):
        """The author's next test must be against the same artifacts, not ones
        this run edited."""
        from l1.stages import scoring as scoring_stage

        _write_minimal_run(tmp_path)
        before = {p: p.read_bytes() for p in sorted(tmp_path.rglob("*")) if p.is_file()}

        def fake_pass(ctx, pass_name, standard, prompt, pages, budget, model):
            return (
                {
                    "CR-0010": {
                        "criterion_code": "CR-0010", "fired": False, "evaluable": True,
                        "confidence": "high", "evidence": [], "absence_evidence": None,
                        "reasoning": "no", "remediation": None,
                    }
                },
                [],
                0.01,
            )

        monkeypatch.setattr(scoring_stage, "_run_pass", fake_pass)
        tc.test_criterion("CR-0010", tmp_path, criteria_dir=CRITERIA)

        after = {p: p.read_bytes() for p in sorted(tmp_path.rglob("*")) if p.is_file()}
        assert after == before, "the dry run modified the run directory"


class TestRendering:
    def test_renders_evidence_with_per_quote_verification_verdicts(self):
        res = {
            "criterion_code": "CR-0010",
            "criterion": {"name": "Gross-only return disclosure", "tier": "RED_FLAG",
                          "category": "disclosure", "severity": "HIGH", "weight": 1.0,
                          "detection_guidance": "x", "evidence_requirement": "y"},
            "criteria_set": {"set_code": "CS-2026-0001", "version": 3,
                             "content_hash": "sha256:abc", "source_dir": None},
            "run": {"run_dir": "/tmp/r", "run_id": "x", "source": "deck.pdf",
                    "page_count": 52, "analysis_date": "2026-07-21",
                    "diligence_present": True},
            "finding": {
                "fired": True, "status": "fired", "confidence": "high",
                "evidence": [
                    {"page": 5, "quote": "Gross Returns ~ 18-20% p.a.", "verification": "exact"},
                    {"page": 27, "quote": "Total team size 33 members", "verification": "layout"},
                    {"page": 9, "quote": "not on this page", "verification": "unverified"},
                ],
                "absence_evidence": "Searched all 52 pages for 'net IRR'.",
                "reasoning": "Returns stated gross.",
                "remediation": "Request net-to-investor IRR.",
            },
            "lenient": {"fired": True}, "strict": {"fired": True},
            "quotes_verified": 2, "quotes_total": 3, "warnings": [], "blocked": False,
            "unresolved": [], "cost_usd": 0.0412,
            "tokens": {"total": 48210}, "model": "claude-opus-4-8[1m]",
            "model_calls": 2, "attempts": 2, "retry_reasons": [], "fallback_used": False,
        }
        out = "\n".join(tc.render_result(res))

        assert "FIRED" in out
        assert "agreed" in out
        # All three verdict tiers are distinguishable, per §7.
        assert "[exact]" in out
        assert "[layout]" in out
        assert "[unverified]" in out
        # absence_evidence is shown — it is what makes an absence claim falsifiable.
        assert "absence_evidence" in out
        assert "Searched all 52 pages" in out
        assert "2/3 evidence quotes verified" in out
        assert "$0.0412" in out
        assert "48,210 tokens" in out
        assert "claude-opus-4-8[1m]" in out

    def test_a_blocked_criterion_explains_the_unreachable_source_policy(self):
        res = {
            "criterion_code": "CR-0001",
            "criterion": {"name": "No verifiable SEBI registration", "tier": "VETO",
                          "category": "regulatory", "severity": "CRITICAL", "weight": 1.0,
                          "detection_guidance": "x", "evidence_requirement": "y"},
            "criteria_set": {"set_code": "CS", "version": None,
                             "content_hash": "sha256:abc", "source_dir": None},
            "run": {"run_dir": "/tmp/r", "run_id": "x", "source": "d.pdf",
                    "page_count": 52, "analysis_date": "2026-07-21",
                    "diligence_present": True},
            "finding": {
                "fired": None, "status": "veto_unevaluated", "confidence": "low",
                "evidence": [], "absence_evidence": None,
                "unevaluated_reason": "SEBI register unreachable (geo_fence)",
                "reasoning": "SEBI register unreachable (geo_fence)",
            },
            "lenient": {"fired": True}, "strict": {"fired": True},
            "quotes_verified": 0, "quotes_total": 0, "warnings": [], "blocked": True,
            "unresolved": [], "cost_usd": 0.01, "tokens": {"total": 100},
            "model": "m", "model_calls": 2, "attempts": 2,
            "retry_reasons": [], "fallback_used": False,
        }
        out = "\n".join(tc.render_result(res))
        assert "VETO UNEVALUATED" in out
        assert "unreachable source is never an adverse finding" in out
        assert "(DRAFT)" in out  # draft-criteria visibility


def _write_minimal_run(d: Path) -> None:
    """A valid-enough run directory: run.json, two pages, classification and
    extraction envelopes that pass the real validating loader."""
    import json

    from l1 import SCHEMA_VERSION

    (d / "run.json").write_text(json.dumps({"run_id": "test", "source": {"filename": "d.pdf"}}))

    pages = d / "00-pages"
    pages.mkdir(exist_ok=True)
    (pages / "page-001.txt").write_text("Gross Returns 18-20% p.a. Target IRR stated gross.")
    (pages / "page-002.txt").write_text("Fund terms and other content.")

    def env(stage, result):
        return json.dumps(
            {
                "stage": stage,
                "schema_version": SCHEMA_VERSION,
                "generated_at": "2026-07-21T00:00:00Z",
                "inputs_hash": None,
                "result": result,
                "unresolved": [],
                "citations": [],
            }
        )

    (d / "01-classification.json").write_text(
        env("classification", {
            "document_type": "pitch_deck", "is_analysable": True,
            "fund_name": "Test Fund", "manager_name": "Test AMC",
            "aif_category": "CAT_II", "aif_category_confidence": "stated",
            "structure": "close_ended", "strategy": "credit",
            "sebi_registration": None, "document_date": "February 2026",
        })
    )
    (d / "02-extraction.json").write_text(
        env("extraction", {
            "economics": {
                "target_return": {
                    "value": "18-20% gross", "page": 1,
                    "quote": "Gross Returns 18-20% p.a.", "confidence": "high",
                }
            }
        })
    )
