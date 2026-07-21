"""Tests for the PRD §6 invariants.

The point of these tests is NOT that the happy path works. It is that each
invariant demonstrably FAILS when violated. An invariant that has never been
observed to fail is indistinguishable from a comment.

Run: python3 -m pytest engine/tests/ -v      (or: python3 engine/tests/test_invariants.py)
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from l1 import SCHEMA_VERSION
from l1.artifacts import (
    ARTIFACT_FILENAMES,
    STAGE_INPUTS,
    assert_inputs_present,
    build_envelope,
    validate_envelope,
    validate_extraction_fields,
    validate_finding_evidence,
    write_artifact,
)
from l1.criteria import load_criteria
from l1.errors import ExitCode, InvalidInputError, InvariantViolation, MissingInputError
from l1.fsutil import atomic_write_json, detect_sync_path, sha256_text

CRITERIA_DIR = Path(__file__).resolve().parents[1] / "criteria" / "default"


@pytest.fixture
def tmp_out():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


_UNSET = object()


def _valid_envelope(stage: str, result=_UNSET) -> dict:
    """Sentinel default, not None — passing result=None must yield a genuinely
    null result, since that is the corrupt-input case invariant 6.1 rejects."""
    return {
        "stage": stage,
        "schema_version": SCHEMA_VERSION,
        "generated_at": "2026-07-20T00:00:00Z",
        "inputs_hash": None,
        "result": {"ok": True} if result is _UNSET else result,
        "unresolved": [],
        "citations": [],
    }


# =====================================================================
# INVARIANT 6.1 — no stage proceeds on missing input
# =====================================================================

class TestInvariant61MissingInput:
    """Each of these asserts the engine REFUSES to proceed. A passing test here
    means a stage failed loudly where a null-tolerant system would have
    continued and produced a memo contradicting its own scorecard."""

    def test_extraction_refuses_when_classification_absent(self, tmp_out):
        with pytest.raises(MissingInputError) as exc:
            assert_inputs_present(tmp_out, "extraction")
        assert "classification" in str(exc.value)
        assert exc.value.exit_code == ExitCode.STAGE_FAILURE

    def test_memo_refuses_when_scoring_absent(self, tmp_out):
        """The documented failure mode: memo generated without the scoring result."""
        for stage in ("classification", "extraction", "diligence"):
            atomic_write_json(tmp_out / ARTIFACT_FILENAMES[stage], _valid_envelope(stage))
        with pytest.raises(MissingInputError) as exc:
            assert_inputs_present(tmp_out, "memo")
        assert "scoring" in str(exc.value)

    def test_memo_declares_all_four_prior_stages_as_inputs(self):
        assert STAGE_INPUTS["memo"] == ("classification", "extraction", "diligence", "scoring")

    def test_refuses_null_result_rather_than_treating_as_empty(self, tmp_out):
        env = _valid_envelope("classification", result=None)
        assert env["result"] is None, "fixture failed to produce a null result"
        atomic_write_json(tmp_out / ARTIFACT_FILENAMES["classification"], env)
        with pytest.raises(MissingInputError, match="null"):
            assert_inputs_present(tmp_out, "extraction")

    def test_refuses_artifact_missing_mandatory_unresolved(self, tmp_out):
        env = _valid_envelope("classification")
        del env["unresolved"]
        atomic_write_json(tmp_out / ARTIFACT_FILENAMES["classification"], env)
        with pytest.raises(MissingInputError, match="unresolved"):
            assert_inputs_present(tmp_out, "extraction")

    def test_refuses_wrong_stage_in_envelope(self, tmp_out):
        """A scoring artifact written into the classification slot must not pass."""
        atomic_write_json(
            tmp_out / ARTIFACT_FILENAMES["classification"], _valid_envelope("scoring")
        )
        with pytest.raises(MissingInputError, match="declares stage"):
            assert_inputs_present(tmp_out, "extraction")

    def test_refuses_schema_version_mismatch(self, tmp_out):
        env = _valid_envelope("classification")
        env["schema_version"] = 99
        atomic_write_json(tmp_out / ARTIFACT_FILENAMES["classification"], env)
        with pytest.raises(MissingInputError, match="schema_version"):
            assert_inputs_present(tmp_out, "extraction")

    def test_refuses_corrupt_json(self, tmp_out):
        (tmp_out / ARTIFACT_FILENAMES["classification"]).write_text("{not json")
        with pytest.raises(MissingInputError, match="not readable JSON"):
            assert_inputs_present(tmp_out, "extraction")

    def test_accepts_a_genuinely_complete_input_set(self, tmp_out):
        """Control: the invariant must not reject valid input, or it proves nothing."""
        for stage in ("classification", "extraction", "diligence"):
            atomic_write_json(tmp_out / ARTIFACT_FILENAMES[stage], _valid_envelope(stage))
        inputs = assert_inputs_present(tmp_out, "scoring")
        assert set(inputs) == {"classification", "extraction", "diligence"}

    def test_there_is_no_null_tolerant_escape_hatch(self):
        """assert_inputs_present must expose no way to proceed on missing input."""
        import inspect

        sig = inspect.signature(assert_inputs_present)
        assert set(sig.parameters) == {"out_dir", "stage"}, (
            "assert_inputs_present grew a parameter; if it is a strict/force flag "
            "it defeats invariant 6.1"
        )


# =====================================================================
# INVARIANT 6.3 — every finding cites evidence
# =====================================================================

class TestInvariant63EvidenceRequired:

    def test_fired_finding_with_no_evidence_at_all_is_rejected(self):
        findings = [{"criterion_code": "CR-0010", "fired": True, "evidence": []}]
        with pytest.raises(InvariantViolation, match="CR-0010"):
            validate_finding_evidence(findings, "<test>")

    def test_fired_finding_with_absence_evidence_only_is_accepted(self):
        """Absence-based firing is legitimate — if the search is stated."""
        findings = [
            {
                "criterion_code": "CR-0010",
                "fired": True,
                "evidence": [],
                "absence_evidence": "No net-to-investor IRR figure located in any of 52 pages.",
            }
        ]
        validate_finding_evidence(findings, "<test>")

    def test_evidence_without_a_page_number_is_rejected(self):
        findings = [
            {
                "criterion_code": "CR-0011",
                "fired": True,
                "evidence": [{"quote": "NIIOF-I is still deploying capital"}],
            }
        ]
        with pytest.raises(InvariantViolation, match="no valid page number"):
            validate_finding_evidence(findings, "<test>")

    def test_evidence_with_empty_quote_is_rejected(self):
        findings = [
            {"criterion_code": "CR-0033", "fired": True, "evidence": [{"page": 37, "quote": "   "}]}
        ]
        with pytest.raises(InvariantViolation, match="empty quote"):
            validate_finding_evidence(findings, "<test>")

    def test_evidence_with_page_zero_is_rejected(self):
        findings = [
            {"criterion_code": "CR-0017", "fired": True, "evidence": [{"page": 0, "quote": "Feb 2026"}]}
        ]
        with pytest.raises(InvariantViolation, match="no valid page number"):
            validate_finding_evidence(findings, "<test>")

    def test_non_fired_finding_needs_no_evidence(self):
        """A criterion that did not fire has nothing to evidence."""
        validate_finding_evidence([{"criterion_code": "CR-0001", "fired": False}], "<test>")

    def test_write_artifact_refuses_to_persist_unevidenced_finding(self, tmp_out):
        """The check gates the WRITE, not just a helper. An invalid artifact must
        never reach disk, because anything on disk is treated as valid input by
        the next stage."""
        env = build_envelope(
            "scoring",
            {"findings": [{"criterion_code": "CR-0010", "fired": True, "evidence": []}]},
            [],
        )
        with pytest.raises(InvariantViolation):
            write_artifact(tmp_out, "scoring", env)
        assert not (tmp_out / ARTIFACT_FILENAMES["scoring"]).exists(), (
            "an invalid artifact reached disk — the next stage would consume it as valid"
        )

    def test_extraction_field_with_value_but_no_page_is_rejected(self):
        result = {
            "fund_terms": {
                "fund_size": {"value": "INR 5000 crore", "page": None, "quote": "x", "confidence": "high"}
            }
        }
        with pytest.raises(InvariantViolation, match="no valid page reference"):
            validate_extraction_fields(result, "<test>")

    def test_extraction_field_with_null_value_is_exempt(self):
        """Not-found is legitimate and belongs in unresolved, not in a page cite."""
        result = {
            "fund_terms": {
                "fund_size": {"value": None, "page": None, "quote": None, "confidence": "low"}
            }
        }
        validate_extraction_fields(result, "<test>")

    def test_write_artifact_refuses_unpaged_extraction_field(self, tmp_out):
        env = build_envelope(
            "extraction",
            {"economics": {"carry": {"value": "20%", "page": None, "quote": "q", "confidence": "high"}}},
            [],
        )
        with pytest.raises(InvariantViolation):
            write_artifact(tmp_out, "extraction", env)
        assert not (tmp_out / ARTIFACT_FILENAMES["extraction"]).exists()


# =====================================================================
# `unresolved` is mandatory (PRD §3)
# =====================================================================

class TestUnresolvedMandatory:

    def test_build_envelope_rejects_none(self):
        with pytest.raises(InvariantViolation, match="unresolved"):
            build_envelope("classification", {"a": 1}, None)

    def test_empty_unresolved_is_present_not_omitted(self):
        env = build_envelope("classification", {"a": 1}, [])
        assert "unresolved" in env and env["unresolved"] == []
        assert json.loads(json.dumps(env))["unresolved"] == []


# =====================================================================
# INVARIANT 6.6 — content addressing, hostile filesystem
# =====================================================================

class TestInvariant66Filesystem:

    def test_atomic_write_leaves_no_partial_file_on_serialisation_failure(self, tmp_out):
        dest = tmp_out / "artifact.json"
        with pytest.raises(TypeError):
            atomic_write_json(dest, {"bad": object()})
        assert not dest.exists(), "a partial artifact survived a failed write"

    def test_atomic_write_leaves_no_temp_files_behind(self, tmp_out):
        atomic_write_json(tmp_out / "a.json", {"ok": 1})
        assert [p.name for p in tmp_out.iterdir()] == ["a.json"]

    def test_case_collision_does_not_silently_merge_content(self, tmp_out):
        """Documents the APFS hazard the content-addressing rule exists for.

        On a case-insensitive filesystem these are one file; on a case-sensitive
        one they are two. Either way the engine must never derive a destination
        path from a user-supplied filename — which is why 00-source.pdf is a
        fixed engine-chosen name and identity comes from sha256."""
        atomic_write_json(tmp_out / "Report.json", {"which": "upper"})
        atomic_write_json(tmp_out / "report.json", {"which": "lower"})
        names = {p.name for p in tmp_out.iterdir()}
        if len(names) == 1:
            content = json.loads((tmp_out / names.pop()).read_text())
            assert content["which"] == "lower"  # second write won, silently

    def test_sync_path_detection_fires_on_known_trees(self):
        assert detect_sync_path(Path("/Users/x/Dropbox/runs")) is not None
        assert detect_sync_path(Path("/Users/x/Library/Mobile Documents/runs")) is not None
        assert detect_sync_path(Path("/tmp/runs")) is None

    def test_content_hash_is_stable_and_sensitive(self):
        assert sha256_text("abc") == sha256_text("abc")
        assert sha256_text("abc") != sha256_text("abd")


# =====================================================================
# Criteria loading and lint (PRD §4)
# =====================================================================

class TestCriteria:

    def test_seed_set_loads_with_all_17_criteria(self):
        cs = load_criteria(CRITERIA_DIR)
        assert len(cs.criteria) == 17, f"expected 17 seed criteria, got {len(cs.criteria)}"
        assert cs.set_code == "CS-2026-0001"

    def test_seed_set_tier_distribution_matches_prd_section_11(self):
        """PRD §11 seeds 3 VETO / 8 RED_FLAG / 6 GREEN_FLAG.

        The set now carries 2/9/6: CR-0003 ("no attributable prior track record")
        was moved from VETO to RED_FLAG as CR-0018 on 2026-07-21 by stakeholder
        decision, with the rationale recorded inline in `criteria.yaml` — a veto
        would silently reject every genuinely first-time manager, and a veto is
        invisible in a way a red flag is not, because the analysis stops rather
        than surfacing the concern for judgement.

        The assertion pins the CURRENT set and names the deviation, rather than
        pinning the PRD and failing forever on a deliberate decision.
        """
        cs = load_criteria(CRITERIA_DIR)
        tiers = {}
        for c in cs.criteria:
            tiers[c.tier] = tiers.get(c.tier, 0) + 1
        assert tiers == {"VETO": 2, "RED_FLAG": 9, "GREEN_FLAG": 6}
        assert not any(c.criterion_code == "CR-0003" for c in cs.criteria), (
            "CR-0003 was retired in favour of CR-0018 at RED_FLAG tier"
        )
        assert any(c.criterion_code == "CR-0018" for c in cs.criteria)

    def test_seed_set_contains_the_acceptance_criteria_codes(self):
        """PRD §8 names these four specifically as the acceptance test."""
        cs = load_criteria(CRITERIA_DIR)
        for code in ("CR-0010", "CR-0011", "CR-0033", "CR-0017"):
            assert cs.by_code(code) is not None, f"{code} missing from seed set"

    def test_content_hash_is_deterministic(self):
        assert load_criteria(CRITERIA_DIR).content_hash == load_criteria(CRITERIA_DIR).content_hash

    def test_seed_set_lints_clean(self):
        assert load_criteria(CRITERIA_DIR).warnings == []

    def test_rejects_short_detection_guidance(self, tmp_out):
        _write_criteria(tmp_out, [_crit(detection_guidance="bad disclosure")])
        with pytest.raises(InvalidInputError, match="detection_guidance"):
            load_criteria(tmp_out)

    def test_rejects_duplicate_criterion_code(self, tmp_out):
        _write_criteria(tmp_out, [_crit(), _crit()])
        with pytest.raises(InvalidInputError, match="duplicate"):
            load_criteria(tmp_out)

    def test_rejects_invalid_tier(self, tmp_out):
        _write_criteria(tmp_out, [_crit(tier="MAYBE_FLAG")])
        with pytest.raises(InvalidInputError, match="tier"):
            load_criteria(tmp_out)

    def test_rejects_zero_weight(self, tmp_out):
        _write_criteria(tmp_out, [_crit(weight=0)])
        with pytest.raises(InvalidInputError, match="weight"):
            load_criteria(tmp_out)

    def test_prompt_payload_excludes_rationale(self):
        """Rationale justifies a finding in the memo; it must not be an input to
        detecting one, or the model fires on persuasive prose."""
        payload = load_criteria(CRITERIA_DIR).as_prompt_payload()
        assert all("rationale" not in row for row in payload)


def _crit(**overrides):
    base = {
        "criterion_code": "CR-9001",
        "name": "Test criterion",
        "tier": "RED_FLAG",
        "category": "disclosure",
        "severity": "HIGH",
        "weight": 1.0,
        "detection_guidance": "Returns are stated gross with no net-to-investor figure anywhere in the fund document.",
        "evidence_requirement": "Quote the page stating gross returns.",
        "rationale": "Gross overstates investor outcome.",
        "remediation_prompt": "Request net IRR.",
    }
    base.update(overrides)
    return base


def _write_criteria(d: Path, criteria: list[dict]) -> None:
    import yaml

    (d / "set.yaml").write_text(
        yaml.safe_dump(
            {
                "set_id": "test-id",
                "set_code": "CS-TEST-0001",
                "name": "Test set",
                "version": 1,
                "asset_class_scope": ["CAT_II"],
                "schema_version": 1,
            }
        )
    )
    (d / "criteria.yaml").write_text(yaml.safe_dump({"criteria": criteria}))


# =====================================================================
# Envelope conformance
# =====================================================================

class TestEnvelope:

    def test_round_trips_through_validation(self, tmp_out):
        from l1.unresolved import make_entry
        env = build_envelope(
            "classification",
            {"document_type": "pitch_deck"},
            [make_entry("x", "DOCUMENT_ANSWERABLE", "classification",
                        "Searched all pages; not found.", typical_source="ppm")],
        )
        path = write_artifact(tmp_out, "classification", env)
        assert validate_envelope(json.loads(path.read_text()), "classification", "<t>")

    def test_a_string_unresolved_entry_never_reaches_disk(self, tmp_out):
        """PRD §3: entries are structured objects. Validation sits in
        `write_artifact` for the same reason §6.3 does — a malformed entry must
        not land where the next stage reads it as valid."""
        from l1.errors import InvariantViolation
        env = build_envelope("classification", {"a": 1}, ["x — not found"])
        with pytest.raises(InvariantViolation):
            write_artifact(tmp_out, "classification", env)
        assert not (tmp_out / "01-classification.json").exists()

    def test_engine_accepts_the_artifacts_it_produces(self, tmp_out):
        """An artifact this engine writes must be one it would read back."""
        write_artifact(tmp_out, "classification", build_envelope("classification", {"a": 1}, []))
        write_artifact(tmp_out, "extraction", build_envelope("extraction", {"b": 2}, []))
        assert set(assert_inputs_present(tmp_out, "diligence")) == {"classification", "extraction"}


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
