"""End-to-end regression against the real Neo deck (PRD §8 acceptance criteria).

This is the test that proves the stage works. It makes real `claude` calls, costs
real money (~$0.55 for classification, ~$1-2 with extraction), and takes minutes.

    python3 -m pytest tests/test_neo_deck.py -v -m slow        # run it
    python3 -m pytest tests/ -m "not slow"                     # skip it

The run directory is shared across tests in this module and built once, so the
acceptance assertions do not each pay for their own analysis.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from l1.artifacts import load_stage_artifact
from l1.cli import main

# PORTABILITY: resolved by conftest, which supports L1_REFERENCE_DECK, a local
# tests/fixtures/ copy, or the sibling-repo path. Never reach outside the engine
# directory from here — see conftest for the rationale.
from conftest import CRITERIA, DECK  # noqa: E402

# Ground truth, independently verified against the PDF text layer with pdftotext
# before this test was written — not copied from engine output.
EXPECTED_SHA256 = "2b176083b2938978a9ab84ba1cc2fc72cad052ded1bcf4893293abd1a4613562"
EXPECTED_PAGES = 52

pytestmark = pytest.mark.slow


class TestClassificationAcceptance:
    """PRD §8 acceptance criteria 1 and 7."""

    def test_source_is_content_addressed_correctly(self, classified):
        import json
        run = json.loads((classified / "run.json").read_text())
        assert run["source"]["sha256"] == EXPECTED_SHA256
        assert run["source"]["page_count"] == EXPECTED_PAGES

    def test_artifact_validates_as_its_own_input(self, classified):
        load_stage_artifact(classified, "classification")

    # --- the five items the diagnosis asked to pin ---

    def test_document_type_is_pitch_deck(self, classified):
        art = load_stage_artifact(classified, "classification")
        assert art["result"]["document_type"] == "pitch_deck"
        assert art["result"]["is_analysable"] is True

    def test_aif_category_is_cat_ii_and_stated_not_inferred(self, classified):
        """'stated' matters: an inferred category on a gating decision has to
        surface in the memo as a caveat. Page 37 says it in words."""
        art = load_stage_artifact(classified, "classification")
        assert art["result"]["aif_category"] == "CAT_II"
        assert art["result"]["aif_category_confidence"] == "stated"

    def test_structure_is_close_ended(self, classified):
        assert load_stage_artifact(classified, "classification")["result"]["structure"] == "close_ended"

    def test_manager_name_identified(self, classified):
        manager = load_stage_artifact(classified, "classification")["result"]["manager_name"]
        assert manager and "Neo Asset Management" in manager

    def test_sebi_registration_is_null_and_unresolved(self, classified):
        """PRD §8 criterion 7, and the sharpest anti-hallucination test available.

        The deck says "SEBI registered Category II AIF" on page 37 but prints no
        registration number anywhere. A model that pattern-matches Indian AIF
        decks will want to emit IN/AIF2/YY-YY/NNNN. It must not.
        """
        art = load_stage_artifact(classified, "classification")
        assert art["result"]["sebi_registration"] is None, (
            "engine invented a SEBI registration number that is not in the document"
        )
        # Entries are structured objects (PRD §3), so this matches on the
        # declared `field_path` rather than searching prose — which is the whole
        # point of that field existing.
        assert any(
            "sebi_registration" in (u.get("field_path") or "").lower()
            for u in art["unresolved"]
        ), "absence of the registration number was not recorded in unresolved"

    def test_every_citation_points_at_a_real_page(self, classified):
        """A citation to page 60 of a 52-page deck is fabricated provenance."""
        art = load_stage_artifact(classified, "classification")
        assert art["citations"], "classification produced no citations at all"
        for c in art["citations"]:
            assert 1 <= c["page"] <= EXPECTED_PAGES, f"citation to page {c['page']}"
            assert c["quote"].strip()

    def test_engine_records_a_verification_verdict_for_every_citation(self, classified):
        """Every citation must carry an explicit verified/not-verified verdict.

        The engine checks each quote against its cited page and records the
        result. What is non-negotiable is that the verdict EXISTS — an
        unverified quote must never be presented as though it were verified.
        """
        art = load_stage_artifact(classified, "classification")
        assert art["citations"], "classification produced no citations at all"
        for c in art["citations"]:
            assert "quote_verified" in c, f"no verification verdict for page {c['page']}"

    def test_the_large_majority_of_citation_quotes_verify(self, classified):
        """MEASURED over repeated runs: ~20/21 quotes verify exactly. Residual
        failures cluster on multi-line layout blocks where `pdftotext -layout`
        padding is not reproducible — a formatting artifact, not fabrication.

        The threshold is deliberately a floor, not equality: demanding 100% makes
        the suite flaky for a known-benign cause, while a collapse below this
        floor would indicate the model has genuinely started inventing quotes.
        """
        art = load_stage_artifact(classified, "classification")
        cites = art["citations"]
        verified = sum(1 for c in cites if c.get("quote_verified"))
        assert verified >= len(cites) * 0.75, (
            f"only {verified}/{len(cites)} citation quotes verified against their "
            "cited pages — below the floor for benign layout artifacts"
        )

    def test_verification_failures_are_reported_not_hidden(self, classified):
        """An unverified quote must reach errors.jsonl. Silent degradation is the
        failure mode the whole evidence design exists to prevent."""
        import json
        art = load_stage_artifact(classified, "classification")
        unverified = [c for c in art["citations"] if not c.get("quote_verified")]
        if not unverified:
            pytest.skip("all quotes verified this run; nothing to report")
        errors = (classified / "errors.jsonl")
        assert errors.exists(), "citation failed verification but errors.jsonl absent"
        logged = errors.read_text(encoding="utf-8")
        assert "not found verbatim" in logged


class TestExtractionAcceptance:
    """PRD §8 acceptance criterion 2. Extraction is slower and pricier than
    classification, so it runs as its own module-scoped fixture."""

    def test_artifact_validates(self, extracted):
        load_stage_artifact(extracted, "extraction")

    def test_fund_size_captured_as_written_with_qualifier(self, extracted):
        """Extract-then-normalise: '~ INR 5,000 crores' must keep its tilde. The
        qualifier is often the finding."""
        r = load_stage_artifact(extracted, "extraction")["result"]
        fs = r["fund_terms"]["fund_size"]
        assert fs and fs["as_written"], "fund size not extracted"
        assert "5,000" in fs["as_written"] or "5000" in fs["as_written"]
        assert fs["page"], "fund size has no page reference"

    def test_return_basis_identified_as_gross(self, extracted):
        """The central allocator question. The deck states ~18-20% p.a. gross."""
        r = load_stage_artifact(extracted, "extraction")["result"]
        basis = r["fund_terms"]["target_return_basis"]
        assert basis and basis["value"], "return basis not extracted"
        assert "gross" in str(basis["value"]).lower()

    def test_service_providers_extracted_with_pages(self, extracted):
        """PRD §8 criterion 2: all five, each with a page reference."""
        providers = load_stage_artifact(extracted, "extraction")["result"]["service_providers"]
        names = " ".join(p["firm_name"].lower() for p in providers)
        for firm in ("ey", "trilegal", "pwc", "icici", "kfintech"):
            assert firm in names, f"service provider {firm!r} not extracted"
        for p in providers:
            assert p["page"] >= 1, f"{p['firm_name']} has no page reference"

    def test_no_extracted_value_lacks_a_page(self, extracted):
        """Invariant 6.3 on real output, not a synthetic fixture."""
        from l1.artifacts import validate_extraction_fields
        validate_extraction_fields(
            load_stage_artifact(extracted, "extraction")["result"], "<neo deck>"
        )


class TestDiligenceAcceptance:
    """Stage 3. Costs nothing (no model calls) but does hit the network."""

    def test_artifact_validates(self, diligenced):
        load_stage_artifact(diligenced, "diligence")

    def test_every_check_carries_one_of_exactly_three_outcomes(self, diligenced):
        checks = load_stage_artifact(diligenced, "diligence")["result"]["checks"]
        assert checks
        for c in checks:
            assert c["outcome"] in ("passed", "failed", "unavailable"), c

    def test_no_unavailable_check_is_rendered_as_passed(self, diligenced):
        """The safety property of the whole stage."""
        for c in load_stage_artifact(diligenced, "diligence")["result"]["checks"]:
            if c["outcome"] == "unavailable":
                assert c["reason"], f"{c['check']} unavailable with no reason"
                assert c["outcome"] != "passed"

    def test_sebi_is_unavailable_with_the_geofence_stated(self, diligenced):
        """VERIFIED empirically: SEBI is unreachable from this egress at the TLS
        layer. The check must say so rather than failing the run or passing."""
        checks = {c["check"]: c for c in load_stage_artifact(diligenced, "diligence")["result"]["checks"]}
        sebi = checks["sebi_registration_active"]
        assert sebi["outcome"] == "unavailable"
        assert "sebi.gov.in" in sebi["reason"]

    def test_an_unreachable_source_never_fails_the_run(self, diligenced):
        """PRD §5 stage 3 policy: exit 0 even with every external source down."""
        art = load_stage_artifact(diligenced, "diligence")
        assert art["result"]["summary"]["unavailable"] > 0, "expected some unavailable"
        # The fixture already asserted exit 0 — this pins WHY that is correct.
        assert art["result"]["policy"]

    def test_unavailable_checks_reach_unresolved(self, diligenced):
        art = load_stage_artifact(diligenced, "diligence")
        n_unavailable = art["result"]["summary"]["unavailable"]
        assert len(art["unresolved"]) >= n_unavailable


class TestScoringAcceptance:
    """PRD §8 acceptance criteria 3-6. Two model passes; the priciest stage."""

    def _finding(self, scored, code):
        for f in load_stage_artifact(scored, "scoring")["result"]["findings"]:
            if f["criterion_code"] == code:
                return f
        raise AssertionError(f"{code} absent from findings")

    def test_artifact_validates(self, scored):
        load_stage_artifact(scored, "scoring")

    def test_every_active_criterion_is_evaluated_exactly_once(self, scored):
        from l1.criteria import load_criteria
        findings = load_stage_artifact(scored, "scoring")["result"]["findings"]
        codes = [f["criterion_code"] for f in findings]
        assert len(codes) == len(set(codes)), "a criterion was evaluated twice"
        assert set(codes) == {c.criterion_code for c in load_criteria(CRITERIA).active_criteria}

    def test_cr0010_gross_only_returns_fires_with_absence_evidence(self, scored):
        """PRD §8 criterion 3. Firing is not enough — asserting no net figure
        exists requires stating what was searched."""
        f = self._finding(scored, "CR-0010")
        assert f["fired"] is True, "CR-0010 did not fire on a gross-only deck"
        assert (f["absence_evidence"] or "").strip(), "no absence_evidence naming the search"
        assert f["evidence"], "no page-level evidence"

    def test_cr0011_unrealised_predecessor_fires(self, scored):
        """PRD §8 criterion 4. NIIOF-I is committed but not realised."""
        assert self._finding(scored, "CR-0011")["fired"] is True

    def test_cr0033_tier_one_providers_fires_as_a_green_flag(self, scored):
        """PRD §8 criterion 5. Green flags fire on the POSITIVE signal — this
        also pins that green-flag polarity is not inverted."""
        f = self._finding(scored, "CR-0033")
        assert f["tier"] == "GREEN_FLAG"
        assert f["fired"] is True, "all five providers are named; CR-0033 should fire"

    def test_cr0030_gp_commitment_does_not_fire(self, scored):
        """The deck states no sponsor commitment, so the green flag must NOT
        fire. A green flag firing on absent evidence is the more dangerous
        direction of error."""
        assert self._finding(scored, "CR-0030")["fired"] is not True

    def test_cr0017_staleness_is_arithmetic_not_judgement(self, scored):
        """PRD §8 criterion 6 EXPECTS this to fire. It must not, and the reason
        is arithmetic the engine computes itself: the deck is dated February
        2026, the analysis date is July 2026, and the criterion's threshold is
        'more than six months'. Five months does not exceed six.

        This test pins the ARITHMETIC, not a fixed verdict, so it stays correct
        when the analysis date moves past the threshold."""
        from datetime import date
        from l1.stages.scoring import _parse_document_date

        art = load_stage_artifact(scored, "scoring")
        f = self._finding(scored, "CR-0017")
        doc_date = _parse_document_date(
            load_stage_artifact(scored, "classification")["result"].get("document_date")
        )
        assert doc_date is not None, "document date did not parse"
        today = date.fromisoformat(art["result"]["analysis_date"])
        months = (today.year - doc_date.year) * 12 + (today.month - doc_date.month)
        expected = months > 6
        assert bool(f["fired"]) is expected, (
            f"document is {months} months old; CR-0017 fired={f['fired']} "
            f"but the >6-month threshold implies {expected}"
        )

    def test_veto_blocked_by_an_unavailable_source_is_unevaluated_not_fired(self, scored):
        """THE REGRESSION THIS EXISTS FOR. Measured: the strict pass fired
        CR-0001 (VETO) at high confidence because SEBI was unreachable, exiting
        11 on a fund whose registration status is merely unknown. An unreachable
        regulator must never become a terminal adverse finding."""
        art = load_stage_artifact(scored, "scoring")
        blocked = set(
            load_stage_artifact(scored, "diligence")["result"][
                "criteria_blocked_by_unavailable_source"
            ]
        )
        if not blocked:
            pytest.skip("no criteria were blocked by an unavailable source this run")
        for code in blocked:
            f = self._finding(scored, code)
            assert f["fired"] is None, (
                f"{code} depends on an unavailable source but has fired={f['fired']}"
            )
            assert code not in art["result"]["veto_fired"]
            if f["tier"] == "VETO":
                assert f["status"] == "veto_unevaluated"

    def test_unevaluated_is_distinguishable_from_not_fired(self, scored):
        """Three states must be distinct in the artifact so no consumer can read
        an unperformed check as a clean result."""
        findings = load_stage_artifact(scored, "scoring")["result"]["findings"]
        states = {f["status"] for f in findings}
        for f in findings:
            if f["status"] in ("unevaluated", "veto_unevaluated"):
                assert f["fired"] is None
            elif f["status"] == "not_fired":
                assert f["fired"] is False
        assert states, "no statuses recorded"

    def test_contested_findings_record_both_readings(self, scored):
        art = load_stage_artifact(scored, "scoring")
        contested = [f for f in art["result"]["findings"] if f.get("contested")]
        if not contested:
            pytest.skip("the two passes agreed on every criterion this run")
        for f in contested:
            assert f.get("lenient") is not None and f.get("strict") is not None, (
                f"{f['criterion_code']} is contested but does not carry both readings"
            )
            assert f["confidence"] == "low", "a contested finding cannot be high-confidence"

    def test_every_fired_finding_cites_evidence_or_states_its_search(self, scored):
        """Invariant 6.3 on real output."""
        from l1.artifacts import validate_finding_evidence
        validate_finding_evidence(
            load_stage_artifact(scored, "scoring")["result"]["findings"], "<neo deck>"
        )

    def test_evidence_pages_are_within_the_document(self, scored):
        for f in load_stage_artifact(scored, "scoring")["result"]["findings"]:
            for e in f.get("evidence") or []:
                assert 1 <= e["page"] <= EXPECTED_PAGES, f"citation to page {e['page']}"


class TestUnresolvedContractAcceptance:
    """PRD §3: `unresolved` entries are structured objects, live on the real deck.

    The point of the contract is routing: the evidence loop sends each open
    question to a different affordance by `kind`. These assertions check the
    contract holds on real model output, not just on synthetic fixtures — the
    fast suite already proves the validator rejects malformed entries, and what
    is unproven without a live run is whether real stages actually emit them.
    """

    STAGES = ("classification", "extraction", "diligence", "scoring")

    def test_every_entry_from_every_stage_is_a_valid_structured_object(self, scored):
        from l1.unresolved import assert_entries_valid
        total = 0
        for stage in self.STAGES:
            entries = load_stage_artifact(scored, stage)["unresolved"]
            assert_entries_valid(entries, f"<disk:{stage}>")
            total += len(entries)
        assert total >= 16, f"expected a substantive open-question set, got {total}"

    def test_no_entry_is_a_bare_string(self, scored):
        for stage in self.STAGES:
            for e in load_stage_artifact(scored, stage)["unresolved"]:
                assert isinstance(e, dict), f"{stage} emitted a string entry: {e!r}"

    def test_every_entry_carries_a_substantive_search_account(self, scored):
        """`account` is the part that records what was already ruled out. A
        one-word account would satisfy the schema and defeat the purpose."""
        thin = []
        for stage in self.STAGES:
            for e in load_stage_artifact(scored, stage)["unresolved"]:
                if len(e.get("account") or "") < 60:
                    thin.append((stage, e.get("field_path"), e.get("account")))
        assert not thin, f"entries with no real search account: {thin[:5]}"

    def test_the_artifact_schema_version_incremented(self, scored):
        for stage in self.STAGES:
            assert load_stage_artifact(scored, stage)["schema_version"] == 2

    def test_every_diligence_entry_is_externally_blocked(self, diligenced):
        """A diligence `unresolved` entry exists only because a check could not
        be PERFORMED. None may ever be routed as answerable — no document from
        the manager resolves an unreachable regulator."""
        entries = load_stage_artifact(diligenced, "diligence")["unresolved"]
        assert entries, "expected unavailable checks on this network"
        for e in entries:
            assert e["kind"] == "EXTERNALLY_BLOCKED", e
            assert e["typical_source"] is None
            assert e["unblock_owner"], f"{e['field_path']} names no owner"

    def test_the_sebi_block_is_attributed_to_infrastructure(self, diligenced):
        """VERIFIED empirically as a geo-fence below the HTTP layer. No analyst
        effort and no manager document resolves it, so it must not be routed to
        either."""
        entries = load_stage_artifact(diligenced, "diligence")["unresolved"]
        sebi = [e for e in entries if e["field_path"].startswith("sebi_")]
        if not sebi:
            pytest.skip("SEBI checks were not unavailable on this run")
        for e in sebi:
            assert e["blocker_class"] == "geo_fence"
            assert e["unblock_owner"] == "infrastructure"

    def test_a_blocked_entry_never_names_a_document_source(self, scored):
        """The routing error the contract exists to prevent."""
        for stage in self.STAGES:
            for e in load_stage_artifact(scored, stage)["unresolved"]:
                if e["kind"] == "EXTERNALLY_BLOCKED":
                    assert e["typical_source"] is None, e

    def test_more_than_one_kind_is_represented(self, scored):
        """If every entry landed in one bucket the routing would be decorative.
        The deck genuinely produces document questions AND blocked checks."""
        kinds = set()
        for stage in self.STAGES:
            for e in load_stage_artifact(scored, stage)["unresolved"]:
                kinds.add(e["kind"])
        assert len(kinds) >= 2, f"only one kind present: {kinds}"

    def test_the_unevaluated_vetoes_are_blocked_not_answerable(self, scored):
        """CR-0001 / CR-0002 are unevaluated because SEBI is unreachable. Routing
        them as answerable would invite an analyst to resolve a veto they cannot."""
        scoring = load_stage_artifact(scored, "scoring")
        blocked_codes = {
            code
            for e in scoring["unresolved"]
            if e["kind"] == "EXTERNALLY_BLOCKED"
            for code in e.get("criterion_codes") or []
        }
        for code in scoring["result"].get("veto_unevaluated") or []:
            assert code in blocked_codes, f"{code} is unevaluated but not routed as blocked"


class TestMemoAcceptance:
    """PRD §8 acceptance criteria 8-10, invariants 6.2 / 6.4, and PRD §3's
    split-memo layout.

    The memo is now a directory of 13 files, not one markdown blob. The
    assertions below are deliberately written so that the split cannot quietly
    weaken any of them — in particular §6.4 is swept over EVERY section file, and
    the fabrication test injects its number into a file that is NOT the first
    one, because a sweep that only ever checks `01-recommendation.md` would pass
    a naive version of this test.
    """

    # ---- layout -------------------------------------------------------

    def test_the_memo_directory_and_all_thirteen_files_exist(self, memoed):
        from l1.stages.memo import ALL_MEMO_FILENAMES, MEMO_DIR
        memo_dir = memoed / MEMO_DIR
        assert memo_dir.is_dir(), f"{MEMO_DIR}/ was not created"
        assert len(ALL_MEMO_FILENAMES) == 13
        for name in ALL_MEMO_FILENAMES:
            assert (memo_dir / name).exists(), f"{name} missing"
        load_stage_artifact(memoed, "memo")

    def test_no_memo_file_is_empty(self, memoed):
        """An absent or blank file must never read as a section with nothing to
        say. Checked on disk, not on the in-memory dict the stage validated."""
        from l1.stages.memo import ALL_MEMO_FILENAMES, MEMO_DIR
        for name in ALL_MEMO_FILENAMES:
            body = (memoed / MEMO_DIR / name).read_text(encoding="utf-8")
            assert body.strip(), f"{name} is empty"
            assert len(body) > 200, f"{name} is {len(body)} bytes — too short to be real"

    def test_the_written_files_pass_the_completeness_invariant(self, memoed):
        from l1.memo_checks import assert_sections_complete
        from l1.stages.memo import ALL_MEMO_FILENAMES, MEMO_DIR
        files = {
            name: (memoed / MEMO_DIR / name).read_text(encoding="utf-8")
            for name in ALL_MEMO_FILENAMES
        }
        assert_sections_complete(files, "<disk>")

    def test_the_old_monolithic_memo_is_no_longer_written(self, memoed):
        """The contract changed; leaving the 58KB file behind would mean two
        sources of truth diverging on the next run."""
        assert not (memoed / "05-memo.md").exists()

    def test_the_memo_json_is_unchanged_in_shape(self, memoed):
        """`05-memo.json` stays as-is — the structured form of the whole memo."""
        memo = load_stage_artifact(memoed, "memo")["result"]
        for key in ("recommendation", "recommendation_basis", "vetoed",
                    "sections", "mechanical_sections", "unresolved_by_stage",
                    "unresolved_total"):
            assert key in memo, f"05-memo.json lost {key}"
        assert set(memo["sections"]) == {
            "1_recommendation", "2_rationale", "3_fund_facts", "4_risk_factors",
            "5_supporting_factors", "6_fees_and_terms", "7_team", "8_track_record",
            "9_contested_findings", "10_asks", "11_could_not_determine", "12_sources",
        }

    def test_memo_json_carries_the_routing_breakdown(self, memoed):
        """A consumer gets the kind counts without re-deriving them — and so
        cannot derive them differently from what the index prints."""
        memo = load_stage_artifact(memoed, "memo")["result"]
        by_kind = memo["unresolved_by_kind"]
        assert by_kind, "no routing breakdown emitted"
        assert sum(by_kind.values()) == memo["unresolved_total"]
        from l1.unresolved import KINDS
        for kind in by_kind:
            assert kind in KINDS, f"unknown kind {kind!r}"

    def test_memo_json_declares_where_the_files_are(self, memoed):
        from l1.stages.memo import MEMO_DIR
        memo = load_stage_artifact(memoed, "memo")["result"]
        assert memo["memo_dir"] == MEMO_DIR
        assert len(memo["memo_files"]) == 13
        for rel in memo["memo_files"]:
            assert (memoed / rel).exists(), f"{rel} declared but absent"

    # ---- PRD §0: the output stands alone ------------------------------

    def test_cross_section_links_resolve_on_a_plain_filesystem(self, memoed):
        """PRD §0. No server, no base URL, no rendering layer — every relative
        link between section files must point at a file that exists."""
        import re
        from l1.stages.memo import ALL_MEMO_FILENAMES, MEMO_DIR
        memo_dir = memoed / MEMO_DIR
        broken = []
        for name in ALL_MEMO_FILENAMES:
            body = (memo_dir / name).read_text(encoding="utf-8")
            for target in re.findall(r"\]\(\./([^)#]+)", body):
                if not (memo_dir / target).exists():
                    broken.append(f"{name} -> {target}")
        assert not broken, f"broken relative links: {broken}"

    def test_no_management_system_identifiers_leak_into_the_memo(self, memoed):
        """PRD §0. The engine knows about a PDF, a criteria directory and an
        output directory. Nothing else."""
        from l1.stages.memo import ALL_MEMO_FILENAMES, MEMO_DIR
        forbidden = ("deal_id", "user_id", "phlo", "http://", "https://localhost")
        for name in ALL_MEMO_FILENAMES:
            body = (memoed / MEMO_DIR / name).read_text(encoding="utf-8").lower()
            for token in forbidden:
                assert token not in body, f"{name} contains {token!r}"

    def test_the_index_answers_the_question_without_opening_anything_else(self, memoed):
        """The index must carry the recommendation, the weights, the fired
        counts, the open-question count and the criteria set."""
        from l1.stages.memo import INDEX_FILENAME, MEMO_DIR, RECOMMENDATION_LABEL
        index = (memoed / MEMO_DIR / INDEX_FILENAME).read_text(encoding="utf-8")
        scoring = load_stage_artifact(memoed, "scoring")["result"]
        memo = load_stage_artifact(memoed, "memo")["result"]

        assert RECOMMENDATION_LABEL[scoring["recommendation"]] in index
        assert str(scoring["red_flag_weight"]) in index
        assert str(scoring["green_flag_weight"]) in index
        assert str(len(scoring["red_flags_fired"])) in index
        assert str(memo["unresolved_total"]) in index
        assert scoring["criteria_set"]["set_code"] in index
        for name in ("01-recommendation.md", "11-open-questions.md", "12-sources.md"):
            assert name in index, f"index does not link {name}"

    def test_the_index_breaks_open_questions_down_by_kind(self, memoed):
        """Kind is a DECLARED field now, not something re-derived from prose —
        so this reads it off the entries rather than re-classifying them."""
        from l1.stages.memo import INDEX_FILENAME, MEMO_DIR
        from l1.unresolved import KIND_LABEL
        index = (memoed / MEMO_DIR / INDEX_FILENAME).read_text(encoding="utf-8")
        memo = load_stage_artifact(memoed, "memo")["result"]
        kinds = {
            e["kind"]
            for entries in memo["unresolved_by_stage"].values()
            for e in entries
        }
        assert kinds, "no unresolved entries to classify"
        for kind in kinds:
            assert KIND_LABEL[kind] in index, f"index omits open-question kind {kind!r}"
        # And the counts must agree with the artifact's own breakdown.
        for kind, count in memo["unresolved_by_kind"].items():
            assert str(count) in index, f"index omits the count for {kind}"

    # ---- invariants ----------------------------------------------------

    def test_recommendation_does_not_contradict_the_scorecard(self, memoed):
        """PRD §8 criterion 8 / invariant 6.2. The memo stage already asserts
        this before writing; this re-checks the artifact on disk — including
        that `01-recommendation.md` itself renders the verdict."""
        from l1.memo_checks import (
            assert_recommendation_agrees,
            assert_recommendation_rendered,
            assert_veto_consistency,
        )
        from l1.stages.memo import MEMO_DIR, RECOMMENDATION_FILENAME
        memo = load_stage_artifact(memoed, "memo")["result"]
        scoring = load_stage_artifact(memoed, "scoring")["result"]
        assert_recommendation_agrees(memo["recommendation"], scoring, "<disk>")
        assert_veto_consistency(memo, scoring, "<disk>")
        assert_recommendation_rendered(
            (memoed / MEMO_DIR / RECOMMENDATION_FILENAME).read_text(encoding="utf-8"),
            scoring,
            "<disk>",
        )

    def _corpus(self, memoed):
        from l1.memo_checks import build_traceable_corpus
        from l1.pdf import load_pages
        from l1.stages.memo import _index_numbers, _section_12_counts
        artifacts = {
            s: load_stage_artifact(memoed, s)
            for s in ("classification", "extraction", "diligence", "scoring")
        }
        scoring = artifacts["scoring"]["result"]
        # The cost figure the index PRINTED, read off the memo artifact. Not
        # `run.json`'s `cost_usd`: that is the final run total, recorded after the
        # memo call was billed, so it is a different number. Re-deriving it here
        # would fail §6.4 on a figure the engine itself wrote.
        memo = load_stage_artifact(memoed, "memo")["result"]
        return build_traceable_corpus(
            artifacts=artifacts,
            pages=load_pages(memoed / "00-pages"),
            extra={
                str(EXPECTED_PAGES),
                *_section_12_counts(artifacts),
                *_index_numbers(scoring, memo.get("index_cost_usd")),
            },
        )

    def test_every_number_in_every_section_file_is_traceable(self, memoed):
        """PRD §8 criterion 10 / invariant 6.4, swept over the WHOLE set.

        Uses `build_traceable_corpus` — the same single definition of
        "traceable" the memo stage uses — so the test and the gate cannot drift.
        """
        from l1.memo_checks import assert_numerics_traceable
        from l1.stages.memo import ALL_MEMO_FILENAMES, MEMO_DIR
        corpus = self._corpus(memoed)
        for name in ALL_MEMO_FILENAMES:
            body = (memoed / MEMO_DIR / name).read_text(encoding="utf-8")
            assert_numerics_traceable(body, corpus, f"<disk:{name}>")

    @pytest.mark.parametrize("target", [
        "08-track-record.md",
        "04-risk-factors.md",
        "12-sources.md",
    ])
    def test_a_fabricated_number_in_a_NON_FIRST_section_still_fails(self, memoed, target):
        """§6.4 was widened to fix false positives; this pins that it did not go
        slack, AND that the split did not narrow it to one file.

        The injection target is deliberately never `01-recommendation.md`: a
        sweep that checked only the first file would pass that version of this
        test while leaving eleven sections unguarded.
        """
        from l1.errors import InvariantViolation
        from l1.memo_checks import assert_numerics_traceable
        from l1.stages.memo import ALL_MEMO_FILENAMES, MEMO_DIR

        corpus = self._corpus(memoed)
        files = {
            name: (memoed / MEMO_DIR / name).read_text(encoding="utf-8")
            for name in ALL_MEMO_FILENAMES
        }
        files[target] += "\n\nThe predecessor returned INR 9,876,543 crores.\n"

        caught = None
        for name in sorted(files):
            try:
                assert_numerics_traceable(files[name], corpus, f"<tampered:{name}>")
            except InvariantViolation as exc:
                caught = (name, str(exc))
                break
        assert caught is not None, f"a fabricated number in {target} was NOT caught"
        assert caught[0] == target, f"caught in {caught[0]}, expected {target}"
        assert "9,876,543" in caught[1]

    def test_section_11_carries_every_unresolved_item_from_every_stage(self, memoed):
        """PRD §8 criterion 9, now checked against `11-open-questions.md`."""
        from l1.memo_checks import assert_unresolved_carried
        from l1.stages.memo import MEMO_DIR, OPEN_QUESTIONS_FILENAME
        body = (memoed / MEMO_DIR / OPEN_QUESTIONS_FILENAME).read_text(encoding="utf-8")
        all_unresolved = []
        for stage in ("classification", "extraction", "diligence", "scoring"):
            all_unresolved += load_stage_artifact(memoed, stage)["unresolved"]
        assert len(all_unresolved) >= 16, "expected at least the 16 extraction unresolved items"
        assert_unresolved_carried(body, all_unresolved, "<disk>")

    def test_section_11_carries_the_full_search_account_not_a_summary(self, memoed):
        """The reason for the split: depth stops being expensive. Each open
        question must carry what was searched for and where — that detail exists
        in the `unresolved` entries and was previously compressed."""
        from l1.stages.memo import MEMO_DIR, OPEN_QUESTIONS_FILENAME
        body = (memoed / MEMO_DIR / OPEN_QUESTIONS_FILENAME).read_text(encoding="utf-8")
        entries = []
        for stage in ("classification", "extraction", "diligence", "scoring"):
            entries += load_stage_artifact(memoed, stage)["unresolved"]

        # The `account` is the search account. Its tail must survive into the
        # file — carrying the field_path while summarising the account away
        # would satisfy §11 completeness by the letter and defeat its purpose.
        long_entries = [e for e in entries if len(e.get("account") or "") > 200]
        assert long_entries, "expected detailed unresolved entries on this deck"
        normalised = " ".join(body.split())
        for entry in long_entries:
            tail = " ".join(entry["account"][-120:].split())
            assert tail in normalised, (
                f"search account truncated for: {entry['field_path']!r}"
            )

    def test_section_11_is_substantially_longer_than_it_was_compressed(self, memoed):
        """A weak but useful floor: the worklist is the point of the file."""
        from l1.stages.memo import MEMO_DIR, OPEN_QUESTIONS_FILENAME
        body = (memoed / MEMO_DIR / OPEN_QUESTIONS_FILENAME).read_text(encoding="utf-8")
        assert len(body) > 10_000, f"section 11 is only {len(body)} bytes"

    def test_unavailable_checks_are_never_described_as_verified(self, memoed):
        """The end-to-end safety property: an unreachable regulator must not be
        rendered anywhere as a clean result — in ANY section file."""
        from l1.stages.memo import ALL_MEMO_FILENAMES, MEMO_DIR
        dil = load_stage_artifact(memoed, "diligence")["result"]
        blocked = [
            c for c in dil["checks"]
            if c["outcome"] == "unavailable" and c["check"] == "sebi_registration_active"
        ]
        if not blocked:
            pytest.skip("SEBI check was not unavailable on this run")
        for name in ALL_MEMO_FILENAMES:
            body = (memoed / MEMO_DIR / name).read_text(encoding="utf-8").lower()
            assert "sebi registration verified" not in body, name
            assert "registration confirmed" not in body, name

    def test_the_unevaluated_veto_framing_survives(self, memoed):
        """'No veto fired — but no veto was cleared either.' This framing is the
        difference between an unperformed check and a clean one."""
        from l1.stages.memo import INDEX_FILENAME, MEMO_DIR
        scoring = load_stage_artifact(memoed, "scoring")["result"]
        if not scoring.get("veto_unevaluated"):
            pytest.skip("no unevaluated veto on this run")
        index = (memoed / MEMO_DIR / INDEX_FILENAME).read_text(encoding="utf-8")
        rec = (memoed / MEMO_DIR / "01-recommendation.md").read_text(encoding="utf-8")
        assert "neither fired nor clean" in index
        assert "no veto was cleared either" in index.lower()
        assert "neither fired nor clean" in rec

    def test_mechanical_sections_are_declared_as_such(self, memoed):
        memo = load_stage_artifact(memoed, "memo")["result"]
        assert memo["mechanical_sections"] == [3, 6, 11, 12]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short", "-m", "slow"]))
