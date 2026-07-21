"""Fast tests for scoring reconciliation, diligence outcomes, and memo invariants.

No API calls, no network. Everything here is the deterministic half of stages 3,
4 and 5 — the reconciliation logic, the unreachable-source policy, and the two
invariants (§6.2, §6.4) that only became checkable once the memo existed.

As with test_invariants.py, the point is not that the happy path works. It is
that each rule demonstrably FAILS when violated.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from l1.criteria import Criterion, load_criteria
from l1.diligence_sources import (
    FAILED,
    PASSED,
    UNAVAILABLE,
    CheckResult,
    address_match_check,
    key_person_match_check,
)
from l1.errors import ExitCode, InvariantViolation
from l1.memo_checks import (
    build_traceable_corpus,
    assert_numerics_traceable,
    assert_recommendation_agrees,
    assert_recommendation_rendered,
    assert_sections_complete,
    assert_unresolved_carried,
    assert_veto_consistency,
    collect_extraction_numbers,
)
from l1.stages.memo import render_fund_facts, render_open_questions
from l1.unresolved import assert_entries_valid, coerce_entry, enforce_kind_safety
from l1.stages.scoring import (
    _check_exclusive_pairs,
    _enforce_blocked_criteria,
    _lower_confidence,
    _reconcile,
    _repair_absence_evidence,
    _summarise,
)

CRITERIA_DIR = Path(__file__).resolve().parents[1] / "criteria" / "default"


class FakeCtx:
    """Records warnings instead of writing them, so tests can assert on them."""

    def __init__(self):
        self.warnings: list[str] = []
        self.progress: list[str] = []

    def warn(self, message, detail=None):
        self.warnings.append(message)

    def stage_progress(self, stage, detail):
        self.progress.append(detail)


def _crit(code, tier="RED_FLAG", severity="HIGH", name=None) -> Criterion:
    return Criterion(
        criterion_code=code,
        name=name or f"test {code}",
        tier=tier,
        category="test",
        severity=severity,
        weight=1.0,
        detection_guidance="x" * 50,
        evidence_requirement="quote the page",
        rationale="because",
        remediation_prompt=f"ask about {code}",
    )


class FakeSet:
    def __init__(self, criteria):
        self.criteria = criteria
        self.set_code = "CS-TEST"
        self.version = 1
        self.content_hash = "sha256:test"

    @property
    def active_criteria(self):
        return self.criteria


def _pass(code, fired, confidence="high", evidence=None, absence=None, evaluable=True):
    return {
        "criterion_code": code,
        "fired": fired,
        "evaluable": evaluable,
        "confidence": confidence,
        "evidence": evidence if evidence is not None else ([{"page": 1, "quote": "q"}] if fired else []),
        "absence_evidence": absence,
        "reasoning": f"{code} reasoning",
        "remediation": None,
    }


# =====================================================================
# Dual-pass reconciliation
# =====================================================================


class TestDualPassReconciliation:
    def test_agreement_on_fired_is_not_contested(self):
        cs = FakeSet([_crit("CR-0010")])
        findings = _reconcile(
            FakeCtx(), cs, {"CR-0010": _pass("CR-0010", True)}, {"CR-0010": _pass("CR-0010", True)}
        )
        assert findings[0]["fired"] is True
        assert findings[0]["contested"] is False
        assert findings[0]["status"] == "fired"

    def test_disagreement_is_contested_and_records_both_readings(self):
        """The core of the dual-pass design: disagreement is preserved, not resolved."""
        cs = FakeSet([_crit("CR-0034", tier="GREEN_FLAG")])
        findings = _reconcile(
            FakeCtx(),
            cs,
            {"CR-0034": _pass("CR-0034", True, "high")},
            {"CR-0034": _pass("CR-0034", False, "high")},
        )
        f = findings[0]
        assert f["contested"] is True
        assert f["status"] == "contested"
        assert f["lenient"]["fired"] is True
        assert f["strict"]["fired"] is False
        assert f["contested_reason"]

    def test_contested_finding_is_never_high_confidence(self):
        """Two standards disagreeing IS the uncertainty, whatever either pass
        claimed about its own certainty."""
        cs = FakeSet([_crit("CR-0034")])
        findings = _reconcile(
            FakeCtx(),
            cs,
            {"CR-0034": _pass("CR-0034", True, "high")},
            {"CR-0034": _pass("CR-0034", False, "high")},
        )
        assert findings[0]["confidence"] == "low"

    def test_contested_headline_takes_the_strict_verdict(self):
        cs = FakeSet([_crit("CR-0034")])
        findings = _reconcile(
            FakeCtx(),
            cs,
            {"CR-0034": _pass("CR-0034", True)},
            {"CR-0034": _pass("CR-0034", False)},
        )
        assert findings[0]["fired"] is False

    def test_agreement_takes_the_lower_confidence(self):
        cs = FakeSet([_crit("CR-0010")])
        findings = _reconcile(
            FakeCtx(),
            cs,
            {"CR-0010": _pass("CR-0010", True, "low")},
            {"CR-0010": _pass("CR-0010", True, "high")},
        )
        assert findings[0]["confidence"] == "low"

    def test_either_pass_unevaluable_makes_the_criterion_unevaluated(self):
        cs = FakeSet([_crit("CR-0001", tier="VETO")])
        findings = _reconcile(
            FakeCtx(),
            cs,
            {"CR-0001": _pass("CR-0001", False, evaluable=False)},
            {"CR-0001": _pass("CR-0001", True)},
        )
        assert findings[0]["fired"] is None
        assert findings[0]["status"] == "veto_unevaluated"

    def test_unevaluated_fired_is_null_not_false(self):
        """A consumer filtering on `fired == False` must not sweep up checks that
        were never performed."""
        cs = FakeSet([_crit("CR-0001", tier="VETO")])
        findings = _reconcile(
            FakeCtx(),
            cs,
            {"CR-0001": _pass("CR-0001", False, evaluable=False)},
            {"CR-0001": _pass("CR-0001", False, evaluable=False)},
        )
        assert findings[0]["fired"] is None
        assert findings[0]["fired"] is not False

    def test_criterion_missing_from_one_pass_is_contested_not_settled(self):
        cs = FakeSet([_crit("CR-0010")])
        ctx = FakeCtx()
        findings = _reconcile(ctx, cs, {}, {"CR-0010": _pass("CR-0010", True)})
        assert findings[0]["contested"] is True
        assert any("only by the" in w for w in ctx.warnings)

    def test_criterion_missing_from_both_passes_is_unevaluated_not_clean(self):
        cs = FakeSet([_crit("CR-0010")])
        ctx = FakeCtx()
        findings = _reconcile(ctx, cs, {}, {})
        assert findings[0]["fired"] is None
        assert any("neither pass" in w for w in ctx.warnings)

    def test_every_active_criterion_yields_exactly_one_finding(self):
        cs = FakeSet([_crit(f"CR-{i:04d}") for i in range(10, 20)])
        findings = _reconcile(FakeCtx(), cs, {}, {})
        assert len(findings) == 10
        assert len({f["criterion_code"] for f in findings}) == 10

    def test_lower_confidence_helper(self):
        assert _lower_confidence("high", "low") == "low"
        assert _lower_confidence("medium", "high") == "medium"
        assert _lower_confidence(None, None) == "low"


# =====================================================================
# The unreachable-source policy — the bug found on the reference run
# =====================================================================


class TestUnreachableSourcePolicy:
    """MEASURED: the strict pass fired CR-0001 (a VETO) at high confidence
    because the SEBI register was unreachable, exiting 11 on a fund whose
    registration status is simply unknown. These tests pin the code-level fix."""

    def _dil(self, blocked, check="sebi_registration_active"):
        return {
            "result": {
                "criteria_blocked_by_unavailable_source": blocked,
                "checks": [
                    {
                        "check": check,
                        "source": "SEBI intermediary register",
                        "outcome": "unavailable",
                        "reason": "geo-fenced from this egress",
                    }
                ],
            }
        }

    def test_fired_veto_on_unavailable_source_is_forced_to_unevaluated(self):
        findings = [
            {
                "criterion_code": "CR-0001",
                "criterion_name": "No verifiable SEBI registration",
                "tier": "VETO",
                "fired": True,
                "status": "fired",
                "confidence": "high",
                "reasoning": "unverified from both directions",
            }
        ]
        ctx = FakeCtx()
        notes = _enforce_blocked_criteria(ctx, findings, self._dil(["CR-0001"]))
        assert findings[0]["fired"] is None
        assert findings[0]["status"] == "veto_unevaluated"
        assert notes, "forcing a fired veto to unevaluated must be recorded"

    def test_the_model_reading_is_preserved_for_inspection(self):
        """Policy overrides the verdict; it must not erase the reasoning."""
        findings = [
            {
                "criterion_code": "CR-0001",
                "criterion_name": "x",
                "tier": "VETO",
                "fired": True,
                "status": "fired",
                "confidence": "high",
                "reasoning": "the original chain of reasoning",
            }
        ]
        _enforce_blocked_criteria(FakeCtx(), findings, self._dil(["CR-0001"]))
        assert findings[0]["model_reading_before_policy"]["fired"] is True
        assert "original chain" in findings[0]["model_reading_before_policy"]["reasoning"]

    def test_blocked_criterion_can_never_reach_the_veto_halt(self):
        """The end-to-end property: an unreachable regulator cannot exit 11."""
        findings = [
            {
                "criterion_code": "CR-0001",
                "criterion_name": "x",
                "tier": "VETO",
                "severity": "CRITICAL",
                "weight": 1.0,
                "fired": True,
                "status": "fired",
                "confidence": "high",
                "reasoning": "r",
            }
        ]
        _enforce_blocked_criteria(FakeCtx(), findings, self._dil(["CR-0001"]))
        summary = _summarise(findings)
        assert summary["veto_fired"] == []
        assert summary["veto_unevaluated"] == ["CR-0001"]
        assert summary["recommendation"] != "pass"

    def test_unblocked_criteria_are_untouched(self):
        findings = [
            {
                "criterion_code": "CR-0010",
                "criterion_name": "x",
                "tier": "RED_FLAG",
                "fired": True,
                "status": "fired",
                "confidence": "high",
                "reasoning": "r",
            }
        ]
        _enforce_blocked_criteria(FakeCtx(), findings, self._dil(["CR-0001"]))
        assert findings[0]["fired"] is True

    def test_summary_notes_the_gap_when_a_veto_could_not_be_evaluated(self):
        findings = [
            {
                "criterion_code": "CR-0001", "criterion_name": "x", "tier": "VETO",
                "severity": "CRITICAL", "weight": 1.0, "fired": None,
                "status": "veto_unevaluated", "confidence": "low", "reasoning": "r",
            }
        ]
        summary = _summarise(findings)
        assert "could not be evaluated" in summary["recommendation_basis"]


# =====================================================================
# Absence evidence — invariant 6.3 at the scoring layer
# =====================================================================


class TestAbsenceEvidence:
    def test_fired_with_no_evidence_at_all_is_downgraded_not_asserted(self):
        """The engine never asserts a search it cannot show was performed."""
        findings = [
            {
                "criterion_code": "CR-0012",
                "tier": "RED_FLAG",
                "fired": True,
                "status": "fired",
                "evidence": [],
                "absence_evidence": None,
                "reasoning": "",
            }
        ]
        ctx = FakeCtx()
        _repair_absence_evidence(ctx, findings)
        assert findings[0]["fired"] is None
        assert findings[0]["status"] == "unevaluated"
        assert any("absence_evidence" in w for w in ctx.warnings)

    def test_fired_on_absence_with_a_stated_search_is_kept(self):
        findings = [
            {
                "criterion_code": "CR-0012",
                "tier": "RED_FLAG",
                "fired": True,
                "status": "fired",
                "evidence": [],
                "absence_evidence": "searched all 52 pages for 'key person'; zero hits",
                "reasoning": "r",
            }
        ]
        _repair_absence_evidence(FakeCtx(), findings)
        assert findings[0]["fired"] is True

    def test_downgraded_veto_becomes_veto_unevaluated(self):
        findings = [
            {
                "criterion_code": "CR-0001", "tier": "VETO", "fired": True,
                "status": "fired", "evidence": [], "absence_evidence": None, "reasoning": "",
            }
        ]
        _repair_absence_evidence(FakeCtx(), findings)
        assert findings[0]["status"] == "veto_unevaluated"


class TestExclusivePairs:
    def test_inverse_criteria_both_firing_is_flagged_not_silently_resolved(self):
        findings = [
            {"criterion_code": "CR-0015", "fired": True, "contested": False},
            {"criterion_code": "CR-0033", "fired": True, "contested": False},
        ]
        ctx = FakeCtx()
        notes = _check_exclusive_pairs(ctx, findings)
        assert notes
        assert all(f["contested"] for f in findings), "both must be retained for review"


# =====================================================================
# Diligence — three outcomes, and unavailable is never passed
# =====================================================================


class TestDiligenceOutcomes:
    def test_unavailable_without_a_reason_is_rejected(self):
        with pytest.raises(ValueError, match="states no reason"):
            CheckResult(check="x", source="y", outcome=UNAVAILABLE)

    def test_there_is_no_fourth_outcome(self):
        with pytest.raises(ValueError, match="not one of"):
            CheckResult(check="x", source="y", outcome="probably_fine")

    def test_the_three_outcomes_are_distinct_values(self):
        assert len({PASSED, FAILED, UNAVAILABLE}) == 3
        assert UNAVAILABLE != PASSED

    def test_address_check_without_both_sides_is_unavailable_not_failed(self):
        """A comparison that could not be made is not a comparison that failed."""
        r = address_match_check("Mumbai 400013", None)
        assert r.outcome == UNAVAILABLE
        assert r.reason

    def test_address_match_is_deterministic_not_a_judgement(self):
        a = address_match_check("903 B-Wing Marathon Futurex Lower Parel Mumbai 400013",
                                "903, B Wing, Marathon Futurex, Lower Parel, Mumbai 400013")
        assert a.outcome == PASSED
        assert "overlap" in a.data

    def test_key_person_check_without_filed_directors_is_unavailable(self):
        r = key_person_match_check(["Varun Bajpai"], [])
        assert r.outcome == UNAVAILABLE
        assert "not a finding" in r.reason

    def test_sebi_lookup_always_reports_the_geofence_as_the_reason(self):
        from l1.diligence_sources import sebi_registration_lookup

        r = sebi_registration_lookup("Neo Asset Management Private Limited", None)
        assert r.outcome == UNAVAILABLE
        assert "geo-fence" in r.reason or "TLS Client Hello" in r.reason

    def test_ifsca_empty_table_over_http_is_unavailable_never_a_negative(self, monkeypatch):
        """THE TRAP: a plain GET returns HTTP 200 with a table shell and zero
        entity rows, which mimics a legitimate 'no match'. It must not be
        reported as one."""
        import l1.diligence_sources as ds

        shell = "<table>" + "".join(
            f"<tr><td>{label}</td><td></td></tr>"
            for label in ("Registered Address", "Validity From", "Email ID")
        ) + "</table>"
        monkeypatch.setattr(ds, "http_get", lambda url, timeout=20: (200, shell, None))
        r = ds.ifsca_directory_lookup("Neo Asset Management Private Limited")
        assert r.outcome == UNAVAILABLE
        assert r.outcome != FAILED, "an empty scrape was reported as 'not registered'"
        assert r.data["rows_populated"] == 0


# =====================================================================
# Invariant 6.2 — the memo cannot contradict its scorecard
# =====================================================================


class TestInvariant62:
    def test_agreement_passes(self):
        assert_recommendation_agrees("pursue", {"recommendation": "pursue"})

    def test_disagreement_is_a_hard_failure(self):
        with pytest.raises(InvariantViolation) as exc:
            assert_recommendation_agrees("pursue", {"recommendation": "pass"})
        assert exc.value.exit_code == ExitCode.STAGE_FAILURE
        assert "contradicts" in str(exc.value).lower() or "recommends" in str(exc.value)

    def test_a_memo_with_no_recommendation_fails(self):
        with pytest.raises(InvariantViolation):
            assert_recommendation_agrees(None, {"recommendation": "pass"})

    def test_veto_status_cannot_be_dropped_between_stages(self):
        with pytest.raises(InvariantViolation):
            assert_veto_consistency({"vetoed": False}, {"vetoed": True})

    def test_veto_status_cannot_be_invented(self):
        with pytest.raises(InvariantViolation):
            assert_veto_consistency({"vetoed": True}, {"vetoed": False})


# =====================================================================
# Invariant 6.4 — numeric traceability
# =====================================================================


class TestInvariant64:
    EXTRACTION = {
        "fund_terms": {
            "fund_size": {"as_written": "~ INR 5,000 crores", "page": 37},
            "target_return": {"as_written": "~ 18-20% p.a.", "page": 37},
        },
        "economics": {
            "management_fee": {"as_written": "2.00% / 1.75% / 1.50% / 1.25%", "normalised": None},
            "hurdle_rate": {"as_written": "10%", "normalised": {"amount": 10}},
        },
    }

    def test_traceable_numbers_pass(self):
        allowed = collect_extraction_numbers(self.EXTRACTION)
        assert_numerics_traceable("Fund size is ~ INR 5,000 crores with a 10% hurdle.", allowed)

    def test_an_invented_number_fails_the_run(self):
        allowed = collect_extraction_numbers(self.EXTRACTION)
        with pytest.raises(InvariantViolation) as exc:
            assert_numerics_traceable("The fund targets INR 7,250 crores.", allowed)
        assert "7,250" in str(exc.value)

    def test_tiered_fee_matches_against_as_written(self):
        """README item 6: `normalised` is legitimately null for a tiered fee, so
        a memo quoting '2.00%' must match against `as_written`."""
        allowed = collect_extraction_numbers(self.EXTRACTION)
        assert_numerics_traceable("Management fee begins at 2.00% and steps to 1.25%.", allowed)

    def test_reformatted_thousands_separator_still_matches(self):
        allowed = collect_extraction_numbers(self.EXTRACTION)
        assert_numerics_traceable("Fund size 5000 crore.", allowed)

    def test_page_citations_are_not_treated_as_claims(self):
        allowed = collect_extraction_numbers(self.EXTRACTION)
        assert_numerics_traceable("Stated on p. 37 and page 52; see CR-0010.", allowed)

    def test_the_check_names_the_offending_number(self):
        allowed = collect_extraction_numbers(self.EXTRACTION)
        with pytest.raises(InvariantViolation) as exc:
            assert_numerics_traceable("An IRR of 34,567 is claimed.", allowed)
        assert "34,567" in str(exc.value)
        assert exc.value.detail["untraceable"]


class TestInvariant64FalsePositives:
    """MEASURED false positives from a full-pipeline run. Each of these numbers
    was genuinely traceable and the check failed the run anyway. §6.4 must be
    precise in both directions: a check that cries wolf gets switched off."""

    def test_a_number_in_unresolved_prose_is_traceable(self):
        """Failed on '2,222' and '1,860' — both appeared in `unresolved` entries
        on the extraction and scoring artifacts, recording a real document
        inconsistency the engine had itself caught (p.25's headline says ~1,900
        crore while its own table totals 1,860). The memo was propagating a
        genuine finding and being punished for it."""
        artifacts = {
            "extraction": {
                "result": {},
                "unresolved": [
                    "predecessor_returns — Rs 2,222 Cr of Rs 2,985 Cr is still merely 'Committed'"
                ],
            },
            "scoring": {
                "result": {},
                "unresolved": [
                    "page 25 headline reads 'Pipeline of Rs ~1,900 crore' but the "
                    "table Grand Total states 1,860 across six deals"
                ],
            },
        }
        corpus = build_traceable_corpus(artifacts=artifacts)
        assert_numerics_traceable("Rs 2,222 Cr remains committed; the table totals 1,860.", corpus)

    def test_a_number_in_absence_evidence_is_traceable(self):
        artifacts = {
            "scoring": {
                "result": {
                    "findings": [
                        {
                            "criterion_code": "CR-0010",
                            "absence_evidence": "searched all 52 pages; only gross figures of 18-20% appear",
                        }
                    ]
                },
                "unresolved": [],
            }
        }
        corpus = build_traceable_corpus(artifacts=artifacts)
        assert_numerics_traceable("Returns are quoted at 18-20% gross.", corpus)

    def test_a_number_in_an_evidence_quote_is_traceable(self):
        artifacts = {
            "scoring": {
                "result": {
                    "findings": [
                        {"evidence": [{"page": 13, "quote": "Rs 2,985 crore completed or committed"}]}
                    ]
                },
                "unresolved": [],
            }
        }
        corpus = build_traceable_corpus(artifacts=artifacts)
        assert_numerics_traceable("The predecessor deployed Rs 2,985 crore.", corpus)

    def test_a_number_printed_in_the_deck_is_traceable_by_definition(self):
        corpus = build_traceable_corpus(
            artifacts={}, pages=["Grand Total 1,860", "Pipeline of Rs ~1,900 crore"]
        )
        assert_numerics_traceable("The table totals 1,860 against a ~1,900 headline.", corpus)

    def test_engine_computed_section_12_tallies_are_traceable(self):
        """Failed on '114' — the citation count section 12 computes about its own
        artifacts. Supplied explicitly via the corpus rather than exempted by a
        magnitude rule, so a fabricated number of the same size still fails."""
        from l1.stages.memo import _section_12_counts

        artifacts = {
            "extraction": {
                "result": {},
                "unresolved": [],
                "citations": [
                    {"page": i % 22 + 1, "quote": "q", "quote_verified": i % 7 != 0}
                    for i in range(114)
                ],
            }
        }
        counts = _section_12_counts(artifacts)
        assert "114" in counts, "the citation total must be derived, not guessed"
        corpus = build_traceable_corpus(artifacts=artifacts, extra=counts)
        assert_numerics_traceable("114 citation(s) across 22 page(s).", corpus)

    def test_widening_the_corpus_did_not_weaken_the_invariant(self):
        """The whole point. A number appearing in NO artifact and NOT in the deck
        must still fail, at any magnitude."""
        artifacts = {
            "extraction": {"result": {"fund_size": {"as_written": "~ INR 5,000 crores"}}, "unresolved": []}
        }
        corpus = build_traceable_corpus(artifacts=artifacts, pages=["the deck says 5,000 crores"])
        for fabricated in ("9,999", "7,777,777", "12,345"):
            with pytest.raises(InvariantViolation):
                assert_numerics_traceable(f"The fund targets INR {fabricated} crores.", corpus)


# =====================================================================
# Section 11 completeness
# =====================================================================


def _entry(field_path, kind, account, **kw):
    """Build a valid structured unresolved entry for tests."""
    from l1.unresolved import make_entry
    return make_entry(field_path, kind, kw.pop("stage_origin", "extraction"), account, **kw)


class TestSection11:
    """§11 completeness, against structured entries (PRD §3, 2026-07-21)."""

    def test_missing_section_11_fails_when_unresolved_items_exist(self):
        with pytest.raises(InvariantViolation) as exc:
            assert_unresolved_carried(
                "",
                [_entry("sebi_registration", "DOCUMENT_ANSWERABLE", "Searched, not found.")],
            )
        assert "could not establish" in str(exc.value).lower() or "omits" in str(exc.value).lower()

    def test_a_dropped_entry_fails(self):
        body = (
            "# 11. Open Questions\n\n**sebi_registration**\n\n"
            "Searched all 52 pages for a registration number and found only prose.\n"
        )
        with pytest.raises(InvariantViolation) as exc:
            assert_unresolved_carried(
                body,
                [
                    _entry("sebi_registration", "DOCUMENT_ANSWERABLE",
                           "Searched all 52 pages for a registration number and found only prose."),
                    _entry("gp_commitment", "DOCUMENT_ANSWERABLE", "No sponsor figure anywhere."),
                ],
            )
        assert "omits" in str(exc.value)

    def test_matching_is_on_field_path_so_reformatting_is_allowed(self):
        """`field_path` exists precisely so this check does not depend on the
        wording of `account`. The memo groups and re-headers entries; that must
        not be a completeness failure."""
        account = (
            "Searched all 52 pages for 'sponsor commitment', 'GP commitment' and "
            "'continuing interest', including pages 37 and 38. No figure appears."
        )
        body = (
            "# 11. Open Questions\n\n"
            "## Answerable from a document we do not have — 1\n\n"
            "### From extraction — 1\n\n"
            f"**gp_commitment** · usually answered by the PPM\n\n{account}\n"
        )
        assert_unresolved_carried(body, [_entry("gp_commitment", "DOCUMENT_ANSWERABLE", account)])

    def test_carrying_the_identifier_but_dropping_the_account_fails(self):
        """The account is the part that records what was already ruled out.
        Naming the field while summarising its account away would satisfy the
        letter of this invariant and defeat its purpose."""
        account = (
            "Searched all 52 pages for 'sponsor commitment', 'GP commitment' and "
            "'continuing interest', including pages 37 and 38. No figure appears "
            "anywhere in the deck, so the field was set to null."
        )
        body = "# 11. Open Questions\n\n**gp_commitment**\n\nNot stated.\n"
        with pytest.raises(InvariantViolation) as exc:
            assert_unresolved_carried(body, [_entry("gp_commitment", "DOCUMENT_ANSWERABLE", account)])
        assert "search account" in str(exc.value)

    def test_all_entries_present_passes(self):
        a1 = "Searched all 52 pages for a registration number; only prose on page 37."
        a2 = "Searched pages 37 and 38 for sponsor commitment language; nothing found."
        body = (
            "# 11. Open Questions\n\n"
            f"**sebi_registration**\n\n{a1}\n\n**gp_commitment**\n\n{a2}\n"
        )
        assert_unresolved_carried(
            body,
            [
                _entry("sebi_registration", "DOCUMENT_ANSWERABLE", a1),
                _entry("gp_commitment", "DOCUMENT_ANSWERABLE", a2),
            ],
        )


class TestSection11GroupsByKind:
    """PRD §3 + §0: a CLI-only reader must get the same routing a Phlo user gets."""

    def _mixed(self):
        return {
            "extraction": [
                _entry("team.key_person_clause", "DOCUMENT_ANSWERABLE",
                       "Searched all 52 pages for 'key person' and 'key man'. No provision described.",
                       typical_source="ppm", criterion_codes=["CR-0012"]),
            ],
            "diligence": [
                _entry("sebi_registration_active", "EXTERNALLY_BLOCKED",
                       "[SEBI intermediary register] could not be checked: unreachable from this egress.",
                       stage_origin="diligence", blocker_class="geo_fence",
                       unblock_owner="infrastructure", criterion_codes=["CR-0001"]),
            ],
            "scoring": [
                _entry("CR-0014", "ANALYST_ANSWERABLE",
                       "Contested between the lenient and strict passes on concentration policy.",
                       stage_origin="scoring", criterion_codes=["CR-0014"]),
            ],
        }

    def test_every_kind_gets_its_own_group(self):
        from l1.unresolved import KIND_LABEL
        rendered = render_open_questions(self._mixed())
        for kind in ("DOCUMENT_ANSWERABLE", "ANALYST_ANSWERABLE", "EXTERNALLY_BLOCKED"):
            assert KIND_LABEL[kind] in rendered, f"{kind} has no group"

    def test_blocked_items_name_their_unblock_owner(self):
        rendered = render_open_questions(self._mixed())
        assert "Infrastructure" in rendered

    def test_blocked_items_are_marked_do_not_ask_the_manager(self):
        """The routing error this contract exists to prevent: sending an analyst
        or a manager a question whose check could not be performed at all."""
        rendered = render_open_questions(self._mixed())
        assert "Do not ask the manager" in rendered or "not be sent as manager questions" in rendered

    def test_document_answerable_items_name_their_source(self):
        rendered = render_open_questions(self._mixed())
        assert "Private Placement Memorandum" in rendered

    def test_the_full_search_account_survives_grouping(self):
        rendered = render_open_questions(self._mixed())
        for fragment in ("key person", "key man", "No provision described",
                         "unreachable from this egress"):
            assert fragment in rendered, f"lost {fragment!r}"

    def test_criterion_codes_are_carried(self):
        rendered = render_open_questions(self._mixed())
        for code in ("CR-0012", "CR-0001", "CR-0014"):
            assert code in rendered

    def test_no_entry_is_dropped_by_grouping(self):
        entries = self._mixed()
        rendered = render_open_questions(entries)
        for group in entries.values():
            for e in group:
                assert e["field_path"] in rendered


class TestUnresolvedContract:
    """The structured entry contract itself (PRD §3)."""

    def test_a_valid_entry_set_passes(self):
        assert_entries_valid([
            _entry("a.b", "DOCUMENT_ANSWERABLE", "account text", typical_source="ppm"),
            _entry("c", "EXTERNALLY_BLOCKED", "blocked", blocker_class="geo_fence",
                   unblock_owner="infrastructure"),
        ], "<t>")

    def test_a_bare_string_entry_is_rejected(self):
        """Entries are objects since 2026-07-21. A string cannot be routed."""
        with pytest.raises(InvariantViolation) as exc:
            assert_entries_valid(["sebi_registration — not found"], "<t>")
        assert "not an object" in str(exc.value)

    @pytest.mark.parametrize("key", ["field_path", "kind", "stage_origin", "account"])
    def test_every_required_key_is_required(self, key):
        e = _entry("a.b", "ANALYST_ANSWERABLE", "account text")
        e[key] = None
        with pytest.raises(InvariantViolation):
            assert_entries_valid([e], "<t>")

    def test_an_unknown_kind_is_rejected(self):
        e = _entry("a.b", "ANALYST_ANSWERABLE", "account")
        e["kind"] = "PROBABLY_FINE"
        with pytest.raises(InvariantViolation):
            assert_entries_valid([e], "<t>")

    def test_a_blocked_entry_may_not_name_a_document_source(self):
        """This is the routing error the contract exists to prevent: a blocked
        check presented as answerable by a document sends the analyst to the
        manager for something no manager can supply."""
        e = _entry("c", "EXTERNALLY_BLOCKED", "blocked", blocker_class="geo_fence",
                   unblock_owner="infrastructure")
        e["typical_source"] = "ppm"
        with pytest.raises(InvariantViolation) as exc:
            assert_entries_valid([e], "<t>")
        assert "not answerable from a document" in str(exc.value)

    def test_a_blocked_entry_must_name_an_owner(self):
        e = _entry("c", "EXTERNALLY_BLOCKED", "blocked", blocker_class="geo_fence")
        e["unblock_owner"] = None
        with pytest.raises(InvariantViolation) as exc:
            assert_entries_valid([e], "<t>")
        assert "nobody's problem" in str(exc.value)

    def test_an_answerable_entry_may_not_carry_blocker_fields(self):
        e = _entry("a.b", "DOCUMENT_ANSWERABLE", "account", typical_source="ppm")
        e["blocker_class"] = "geo_fence"
        with pytest.raises(InvariantViolation):
            assert_entries_valid([e], "<t>")


class TestKindSafetyIsEnforcedInCode:
    """The safety-first classification rule, forced deterministically.

    Same principle as `_enforce_blocked_criteria`: where a safety property must
    hold, a prompt is not a mechanism. The prompt lowers the misclassification
    rate; only the code makes it invariant.
    """

    def test_an_unrecognised_kind_is_forced_to_blocked(self):
        out = enforce_kind_safety(
            [{"field_path": "x", "kind": "MAYBE", "stage_origin": "extraction",
              "account": "something"}],
            "extraction",
        )
        assert out[0]["kind"] == "EXTERNALLY_BLOCKED"

    def test_a_missing_kind_is_forced_to_blocked(self):
        out = enforce_kind_safety(
            [{"field_path": "x", "stage_origin": "extraction", "account": "something"}],
            "extraction",
        )
        assert out[0]["kind"] == "EXTERNALLY_BLOCKED"

    @pytest.mark.parametrize("account", [
        "sebi.gov.in is unreachable from this network egress",
        "the external check could not be performed",
        "could not be checked: the directory renders client-side",
        "gated by a CAPTCHA on submit",
        "requires an authenticated MCA account",
    ])
    def test_an_account_describing_an_unperformed_check_is_forced_to_blocked(self, account):
        """MEASURED analogue: a model that is told an unreachable source is never
        an adverse finding still returned one. The prompt reduces the rate; the
        code makes it invariant. Here the same shape of error would route a
        question no manager can answer to the manager."""
        out = enforce_kind_safety(
            [{"field_path": "x", "kind": "DOCUMENT_ANSWERABLE",
              "stage_origin": "extraction", "account": account,
              "typical_source": "ppm"}],
            "extraction",
        )
        assert out[0]["kind"] == "EXTERNALLY_BLOCKED"
        assert out[0]["typical_source"] is None, "a blocked entry must not name a document source"
        assert out[0]["unblock_owner"], "a blocked entry must name an owner"

    def test_a_genuine_document_question_is_NOT_forced(self):
        """The rule must only ever move entries toward blocked. If it swept up
        ordinary document questions it would empty the actionable list, which is
        the failure mode opposite to the one it guards."""
        out = enforce_kind_safety(
            [{"field_path": "team.key_person_clause", "kind": "DOCUMENT_ANSWERABLE",
              "stage_origin": "extraction", "typical_source": "ppm",
              "account": "Searched all 52 pages for 'key person'. No provision described."}],
            "extraction",
        )
        assert out[0]["kind"] == "DOCUMENT_ANSWERABLE"
        assert out[0]["typical_source"] == "ppm"

    def test_nothing_is_ever_forced_from_blocked_to_answerable(self):
        out = enforce_kind_safety(
            [{"field_path": "x", "kind": "EXTERNALLY_BLOCKED", "stage_origin": "diligence",
              "account": "a perfectly ordinary sentence with no markers",
              "blocker_class": "geo_fence", "unblock_owner": "infrastructure"}],
            "diligence",
        )
        assert out[0]["kind"] == "EXTERNALLY_BLOCKED"

    def test_a_bare_string_keeps_its_account_and_defaults_to_blocked(self):
        """A legacy or malformed entry still carries the search account, which is
        the valuable part. Discarding it to punish the shape would lose real
        content; defaulting the kind to blocked is the safe direction."""
        e = coerce_entry("gp_commitment — searched pages 37 and 38, nothing found", "extraction")
        assert "searched pages 37 and 38" in e["account"]
        assert enforce_kind_safety([e], "extraction")[0]["kind"] == "EXTERNALLY_BLOCKED"


class TestCoercionNormalisesPartialModelOutput:
    """A model returning a partial entry must not fail the whole run.

    The engine holds a perfectly good search account in every one of these cases,
    and discarding it to punish a shape detail would lose real content. What
    coercion must NEVER do is invent a confident `kind` — every ambiguous shape
    lands on EXTERNALLY_BLOCKED, the safe side.
    """

    def _norm(self, raw):
        e = enforce_kind_safety([coerce_entry(raw, "extraction")], "extraction")[0]
        assert_entries_valid([e], "<t>")
        return e

    def test_missing_nullable_keys_are_filled(self):
        e = self._norm({
            "field_path": "a.b", "kind": "DOCUMENT_ANSWERABLE",
            "account": "Searched pages 37 and 38 for the sponsor figure; found none.",
        })
        assert e["kind"] == "DOCUMENT_ANSWERABLE"
        assert "typical_source" in e and "blocker_class" in e and "unblock_owner" in e

    def test_a_missing_field_path_is_recovered_from_the_account(self):
        e = self._norm({
            "kind": "ANALYST_ANSWERABLE",
            "account": "gp_commitment — searched the whole deck; nothing found.",
        })
        assert e["field_path"] == "gp_commitment"

    def test_a_blocked_entry_without_an_owner_gets_one(self):
        e = self._norm({
            "field_path": "x", "kind": "EXTERNALLY_BLOCKED",
            "account": "could not be checked: geo-fenced at the TLS layer.",
        })
        assert e["unblock_owner"] == "manual_analyst_check"

    def test_stray_blocker_fields_are_cleared_from_answerable_entries(self):
        """Otherwise a consumer reading `blocker_class` finds stale data on an
        entry that is not blocked at all."""
        e = self._norm({
            "field_path": "y", "kind": "DOCUMENT_ANSWERABLE",
            "account": "Searched the deck for a key-person clause; no provision.",
            "blocker_class": "geo_fence", "unblock_owner": "infrastructure",
        })
        assert e["blocker_class"] is None and e["unblock_owner"] is None

    def test_an_entry_with_no_account_at_all_still_fails_loudly(self):
        """Coercion is tolerant of shape, not of emptiness. An entry with no
        search account carries nothing worth keeping, and silently accepting it
        would let a stage report a gap it never described."""
        e = enforce_kind_safety([coerce_entry({}, "extraction")], "extraction")[0]
        with pytest.raises(InvariantViolation):
            assert_entries_valid([e], "<t>")


class TestMemoPromptKeepsItsLoadBearingInstructions:
    """Several behaviours live only in prompt text, and prompt text is the
    easiest thing in the system to delete by accident during a refactor. These
    pin the instructions whose loss would be invisible in every structural check
    — the output would still be well-formed, just worse.
    """

    def test_section_2_must_explain_compounding_not_list_findings(self):
        from l1.stages.memo import NARRATIVE_SCHEMA
        desc = NARRATIVE_SCHEMA["properties"]["rationale"]["description"].lower()
        assert "compound" in desc, "the compounding instruction was lost"
        assert "inventory" in desc or "not be a list" in desc

    def test_the_unavailable_is_not_clean_rule_survives(self):
        from l1.stages.memo import SYSTEM_PROMPT
        flat = " ".join(SYSTEM_PROMPT.split())
        assert "UNAVAILABLE IS NOT CLEAN" in flat
        assert "did not run" in flat

    def test_contested_findings_are_not_to_be_resolved(self):
        from l1.stages.memo import SYSTEM_PROMPT
        # Whitespace-normalised: these prompts are hard-wrapped, so a literal
        # match on a phrase spanning a line break is testing the wrapping, not
        # the instruction.
        flat = " ".join(SYSTEM_PROMPT.split())
        assert "Do not pick a winner" in flat
        assert "CONTESTED FINDINGS ARE NOT PROBLEMS TO SOLVE" in flat

    def test_sections_are_told_they_stand_alone(self):
        """With one file per section, a section written to be read in sequence
        is a section that reads wrong for the audience that opens it directly."""
        from l1.stages.memo import _build_prompt
        from l1.criteria import load_criteria
        cls = {"result": {"fund_name": "F", "manager_name": "M"}}
        ext = {"result": {"team": {}, "track_record": {}}}
        sco = {"result": {"recommendation": "hold", "recommendation_basis": "b",
                          "findings": [], "vetoed": False}}
        prompt = _build_prompt(cls, ext, {}, sco, load_criteria(CRITERIA_DIR))
        flat = " ".join(prompt.split())
        assert "ONLY that file" in flat
        assert "as noted above" in flat, "the cross-section deixis ban was lost"

    def test_depth_is_declared_free_but_not_licence_to_pad(self):
        from l1.stages.memo import _build_prompt
        from l1.criteria import load_criteria
        cls = {"result": {"fund_name": "F", "manager_name": "M"}}
        ext = {"result": {"team": {}, "track_record": {}}}
        sco = {"result": {"recommendation": "hold", "recommendation_basis": "b",
                          "findings": [], "vetoed": False}}
        prompt = _build_prompt(cls, ext, {}, sco, load_criteria(CRITERIA_DIR))
        flat = " ".join(prompt.split())
        assert "DEPTH IS NOW FREE" in flat
        assert "speculate" in flat or "pad" in flat, (
            "telling the model depth is free without the anti-padding guard "
            "invites longer output rather than deeper output"
        )


class TestIndexCostFigureIsTraceable:
    """The index prints a run cost, and that figure must survive §6.4.

    The trap this pins: the index prints `budget.spent_usd` at memo time, but
    `run.json` records the FINAL total after the memo call is billed. They are
    different numbers. A consumer — including the acceptance test — that
    re-derives the figure from `run.json` fails §6.4 on a number the engine
    itself wrote, which is a false positive of exactly the kind that gets a check
    switched off.

    The fix is that the memo records the figure it printed, so nobody re-derives
    it. These tests pin both halves.
    """

    def test_the_printed_cost_is_in_the_corpus_it_declares(self):
        from l1.stages.memo import _index_numbers
        nums = _index_numbers({"red_flag_weight": 1.0, "green_flag_weight": 0.0}, 3.8149)
        assert "3.81" in nums, "the printed 2dp cost is not declared to the corpus"

    def test_a_later_total_would_not_match_the_printed_figure(self):
        """Demonstrates why the figure must be recorded rather than re-derived."""
        from l1.stages.memo import _index_numbers
        at_memo_time = _index_numbers({}, 3.24)
        final_total = "3.81"
        assert final_total not in at_memo_time, (
            "if these matched, the trap would not exist and this test is "
            "no longer testing anything"
        )

    def test_no_cost_means_no_cost_line_and_no_stray_number(self):
        from l1.stages.memo import _index_numbers
        assert _index_numbers({}, None) == set()


class TestDiligenceBlockerAttribution:
    """Every unavailable check must name why it is blocked and who unblocks it.

    Declared per check rather than inferred from the reason prose: diligence
    established these causes empirically, so reading them back records a measured
    fact instead of re-deriving it badly from a sentence.
    """

    def test_every_known_check_has_a_blocker_and_owner(self):
        from l1.stages.diligence import CHECK_TO_BLOCKER, CHECK_TO_CRITERIA
        missing = set(CHECK_TO_CRITERIA) - set(CHECK_TO_BLOCKER)
        assert not missing, f"checks with no blocker attribution: {missing}"

    def test_every_blocker_and_owner_is_a_valid_enum_member(self):
        from l1.stages.diligence import CHECK_TO_BLOCKER
        from l1.unresolved import BLOCKER_CLASSES, UNBLOCK_OWNERS
        for check, (blocker, owner) in CHECK_TO_BLOCKER.items():
            assert blocker in BLOCKER_CLASSES, f"{check}: bad blocker {blocker}"
            assert owner in UNBLOCK_OWNERS, f"{check}: bad owner {owner}"

    def test_the_sebi_geofence_is_owned_by_infrastructure_not_an_analyst(self):
        """VERIFIED as a block below the HTTP layer — a real browser fails
        identically to curl. No analyst effort resolves it, so routing it to an
        analyst would be handing someone an impossible task."""
        from l1.stages.diligence import CHECK_TO_BLOCKER
        for check in ("sebi_registration_active", "sebi_enforcement_actions"):
            assert CHECK_TO_BLOCKER[check] == ("geo_fence", "infrastructure")

    def test_a_browser_only_source_is_owned_by_an_analyst_not_infrastructure(self):
        """ZaubaCorp and IFSCA work in a real browser today, so a person can do
        the check by hand. That is a different owner from a network-level block."""
        from l1.stages.diligence import CHECK_TO_BLOCKER
        for check in ("corporate_identity", "ifsca_gift_city_registration"):
            assert CHECK_TO_BLOCKER[check][1] == "manual_analyst_check"

    def test_scoring_inherits_the_blocker_from_the_check_that_caused_it(self):
        from l1.stages.scoring import _blocker_for_criterion, _owner_for_criterion
        dil = {"result": {"checks": [{
            "check": "sebi_registration_active", "outcome": "unavailable",
            "source": "SEBI", "reason": "geo-fenced",
        }]}}
        assert _blocker_for_criterion("CR-0001", dil) == "geo_fence"
        assert _owner_for_criterion("CR-0001", dil) == "infrastructure"

    def test_an_unattributable_blocker_still_names_an_owner(self):
        """An unattributed blocker reads as nobody's problem, so the fallback is
        an owner who at least sees it — never no owner at all."""
        from l1.stages.scoring import _owner_for_criterion
        assert _owner_for_criterion("CR-9999", None) == "manual_analyst_check"


class TestMechanicalRenders:
    def test_fund_facts_renders_without_a_model_and_marks_absences(self):
        cls = {
            "result": {
                "fund_name": "Neo Infra Income Opportunities Fund II",
                "manager_name": "Neo Asset Management Private Limited",
                "aif_category": "CAT_II",
                "aif_category_confidence": "stated",
                "structure": "close_ended",
                "sebi_registration": None,
                "document_date": "February 2026",
            }
        }
        ext = {
            "result": {
                "fund_terms": {"fund_size": {"as_written": "~ INR 5,000 crores", "page": 37}},
                "portfolio_construction": {},
                "track_record": {},
                "service_providers": [],
            }
        }
        out = render_fund_facts(cls, ext)
        assert "~ INR 5,000 crores (p.37)" in out
        assert "no registration number appears" in out
        assert "not stated in the document" in out


class TestDraftCriteriaSetIsUnmissable:
    """A memo produced from unsigned-off rules is a materially different artifact
    from one produced against an approved house view. The seed set is
    deliberately `version: null`, so this must be impossible to skim past."""

    def _files(self, version):
        """Build the whole split memo — index plus 12 sections."""
        from l1.stages.memo import build_index, build_sections
        cls = {"result": {"fund_name": "F", "manager_name": "M"}, "unresolved": []}
        ext = {"result": {"fund_terms": {}, "economics": {}, "portfolio_construction": {},
                          "track_record": {}, "service_providers": []}, "unresolved": []}
        sco = {"result": {"recommendation": "hold", "recommendation_basis": "b",
                          "vetoed": False, "veto_fired": [], "veto_unevaluated": [],
                          "red_flags_fired": [], "green_flags_fired": [], "contested": [],
                          "unevaluated": [], "red_flag_weight": 0.0, "green_flag_weight": 0.0,
                          "analysis_date": "2026-07-21", "findings": [],
                          "criteria_set": {"set_code": "CS-TEST", "version": version}},
               "unresolved": []}
        dil = {"result": {"checks": []}, "unresolved": []}
        narr = {k: "x" for k in ("rationale", "risk_factors", "supporting_factors",
                                 "team", "track_record", "contested_findings", "asks")}
        arts = {"classification": cls, "extraction": ext, "diligence": dil, "scoring": sco}
        ubs = {k: [] for k in arts}
        files = build_sections(cls, ext, dil, sco, narr, ubs, arts)
        files["00-index.md"] = build_index(cls, ext, dil, sco, ubs, arts, None)
        return files

    def test_a_null_version_raises_a_draft_banner_on_the_index(self):
        files = self._files(None)
        index = files["00-index.md"]
        assert "DRAFT criteria set" in index
        assert "have not been signed off" in index
        assert "vNone" not in index, "a null version must never render as 'vNone'"

    def test_the_draft_banner_reaches_the_findings_sections_too(self):
        """Splitting the memo created a way for this banner to be missed that did
        not exist before: a reader who opens `04-risk-factors.md` directly never
        sees the index. Every section whose CONTENT is shaped by the rule set must
        carry the banner itself, or the split has quietly weakened the warning."""
        files = self._files(None)
        for name in ("01-recommendation.md", "04-risk-factors.md",
                     "05-supporting-factors.md", "09-contested-findings.md"):
            assert "DRAFT criteria set" in files[name], f"{name} lost the draft banner"

    def test_every_section_file_states_the_criteria_set_it_came_from(self):
        """A section file lifted out of the directory — which is the point of
        splitting — must not be an unattributed opinion."""
        files = self._files(None)
        for name, body in files.items():
            assert "CS-TEST" in body, f"{name} does not name its criteria set"

    def test_an_approved_set_raises_no_draft_banner(self):
        files = self._files(3)
        for name, body in files.items():
            assert "DRAFT criteria set" not in body, f"{name} shows a draft banner"
        assert "v3" in files["00-index.md"]


class TestAllSectionFilesAreMandatory:
    """PRD §3: a missing section file is itself a failure.

    This invariant exists BECAUSE of the split. In a single memo a dropped
    section was a visibly missing heading in a document someone was already
    reading. As separate files an absent section is invisible — the directory
    looks plausible and every file present is well-formed. An absent file must
    never read as a section that had nothing to say.
    """

    def _complete(self):
        from l1.stages.memo import ALL_MEMO_FILENAMES
        return {
            name: f"# {name}\n\nSubstantive body content for this section, long "
                  f"enough to be real prose rather than scaffolding.\n"
            for name in ALL_MEMO_FILENAMES
        }

    def test_the_complete_set_passes(self):
        assert_sections_complete(self._complete(), "<t>")

    def test_a_missing_section_file_fails(self):
        files = self._complete()
        del files["07-team.md"]
        with pytest.raises(InvariantViolation) as exc:
            assert_sections_complete(files, "<t>")
        assert "07-team.md" in str(exc.value)

    def test_a_missing_index_fails(self):
        files = self._complete()
        del files["00-index.md"]
        with pytest.raises(InvariantViolation) as exc:
            assert_sections_complete(files, "<t>")
        assert "00-index.md" in str(exc.value)

    @pytest.mark.parametrize("missing", [
        "01-recommendation.md", "04-risk-factors.md", "08-track-record.md",
        "11-open-questions.md", "12-sources.md",
    ])
    def test_any_one_of_the_twelve_missing_fails(self, missing):
        files = self._complete()
        del files[missing]
        with pytest.raises(InvariantViolation):
            assert_sections_complete(files, "<t>")

    def test_a_present_but_empty_section_fails(self):
        """A file containing only its header and nav footer is a section whose
        CONTENT is missing. Passing it would let the invariant be satisfied by
        writing thirteen stubs."""
        files = self._complete()
        files["09-contested-findings.md"] = (
            "# 9. Contested Findings\n\n---\n\n"
            "[Index](./00-index.md)\n"
        )
        with pytest.raises(InvariantViolation) as exc:
            assert_sections_complete(files, "<t>")
        assert "09-contested-findings.md" in str(exc.value)

    @pytest.mark.parametrize("body", [
        "No green-flag criterion fired.",
        "The lenient and strict passes agreed on every criterion this run.",
        "_The document names no investment committee members._",
    ])
    def test_a_terse_but_real_section_is_not_mistaken_for_empty(self, body):
        """MEASURED false positive: at a 40-character floor, a real
        'No green-flag criterion fired.' section was rejected as empty.

        Reporting an absence IS content — it is the engine doing what §5
        requires. A threshold tuned to catch thin prose fails correct runs, and
        a check that cries wolf gets switched off. The bar sits just above
        scaffolding and no higher. The italic case matters separately: a
        section's whole body can be one italic sentence, so the stripper must
        remove only the engine's own scaffolding, never all italics.
        """
        files = self._complete()
        files["05-supporting-factors.md"] = (
            f"# 5. Supporting Factors\n\n---\n\n{body}\n"
        )
        assert_sections_complete(files, "<t>")

    def test_a_section_that_says_it_has_nothing_to_report_passes(self):
        """'No green flags fired' is content. The check must distinguish a
        section that reports an absence from one that is absent."""
        files = self._complete()
        files["05-supporting-factors.md"] = (
            "# 5. Supporting Factors\n\n---\n\n"
            "No green-flag criterion fired on this document. That is a finding, "
            "not an omission: the criteria set was evaluated in full and none of "
            "its positive rules matched.\n"
        )
        assert_sections_complete(files, "<t>")


class TestNumericSweepCoversEverySectionFile:
    """§6.4 must not narrow when the memo splits.

    A fabricated number in `08-track-record.md` is exactly as much a fabrication
    as one in `02-rationale.md`. The failure mode this guards is a sweep that
    silently checks only the first file, or only the one the code happens to
    hold.
    """

    CORPUS = {"5000", "18", "20", "37"}

    def _files(self):
        from l1.stages.memo import ALL_MEMO_FILENAMES
        return {name: "The fund targets INR 5,000 crores.\n" for name in ALL_MEMO_FILENAMES}

    def _sweep(self, files):
        for name in sorted(files):
            assert_numerics_traceable(files[name], self.CORPUS, f"<{name}>")

    def test_a_clean_set_passes(self):
        self._sweep(self._files())

    @pytest.mark.parametrize("target", [
        "00-index.md", "01-recommendation.md", "02-rationale.md",
        "07-team.md", "08-track-record.md", "11-open-questions.md",
        "12-sources.md",
    ])
    def test_a_fabricated_number_in_ANY_file_fails(self, target):
        """Parameterised over files deliberately: the point is that no position
        in the set is exempt, especially not the last."""
        files = self._files()
        files[target] += "\nThe predecessor returned INR 9,876,543 crores.\n"
        with pytest.raises(InvariantViolation) as exc:
            self._sweep(files)
        assert "9,876,543" in str(exc.value)
        assert target in str(exc.value), "the failure must name the offending file"


class TestRecommendationFileRendersTheVerdict:
    """§6.2, now that the verdict lives in `01-recommendation.md`."""

    SCORING = {"recommendation": "hold"}

    def test_the_rendered_label_satisfies_the_check(self):
        assert_recommendation_rendered(
            "# 1. Recommendation\n\n**HOLD — defer pending answers**\n",
            self.SCORING, "<t>",
        )

    def test_a_file_missing_the_verdict_fails(self):
        with pytest.raises(InvariantViolation) as exc:
            assert_recommendation_rendered(
                "# 1. Recommendation\n\nSome prose that never states the verdict.\n",
                self.SCORING, "<t>",
            )
        assert "6.2" in str(exc.value)

    def test_a_file_stating_the_WRONG_verdict_fails(self):
        with pytest.raises(InvariantViolation):
            assert_recommendation_rendered(
                "# 1. Recommendation\n\n**PURSUE — proceed**\n", self.SCORING, "<t>",
            )

    def test_a_file_stating_TWO_verdicts_fails(self):
        """A recommendation file that states two verdicts states none."""
        with pytest.raises(InvariantViolation) as exc:
            assert_recommendation_rendered(
                "# 1. Recommendation\n\n**HOLD — defer pending answers**\n\n"
                "On another reading, **PASS — do not proceed**.\n",
                self.SCORING, "<t>",
            )
        assert "two verdicts" in str(exc.value)


class TestSeedCriteriaStillLoad:
    def test_the_real_criteria_set_loads_and_has_all_three_tiers(self):
        cs = load_criteria(CRITERIA_DIR)
        tiers = {c.tier for c in cs.active_criteria}
        assert tiers == {"VETO", "RED_FLAG", "GREEN_FLAG"}
        assert len(cs.active_criteria) == 17


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
