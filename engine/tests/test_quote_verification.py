"""Tests for the three-tier quote verifier.

Fast: no API calls, no network. Uses real text from the reference deck.

The purpose of these tests is NOT that genuine quotes verify. It is that the
`layout` tier — which was added to rescue multi-column splices — did not turn
the verifier into a fuzzy matcher that would accept a fabricated citation.
Every relaxation gets a test proving what it still rejects.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from l1.quoteverify import (
    EXACT,
    LAYOUT,
    MAX_GAP_CHARS,
    MIN_TOKENS_FOR_LAYOUT,
    UNVERIFIED,
    normalise,
    verify_against_pages,
    verify_quote,
)

# VERBATIM from page 27 of the reference deck, as `pdftotext -layout` renders it.
# Three columns spliced line by line: the left column reads "Total team size /
# 33 members" but the middle column's text sits between those two fragments.
PAGE_27_REAL = (
    "                                   India's largest roads\n"
    "   Total team size        investing experience of\n"
    "                          19+ Years                 platforms have joined\n"
    "   33 members                                       the team\n"
)

PAGE_13_REAL = (
    "   Deals worth Rs 2,985 crore completed or committed\n"
    "   accruing cashflows from deals that are yet\n"
    "                                                               to close\n"
)


class TestExactTier:
    def test_contiguous_text_is_exact(self):
        assert verify_quote("33 members", PAGE_27_REAL) == EXACT

    def test_whitespace_and_newlines_are_normalised(self):
        """A quote reflowed across lines is still the same text."""
        assert verify_quote("Deals worth Rs 2,985 crore\ncompleted or committed", PAGE_13_REAL) == EXACT

    def test_case_is_ignored(self):
        assert verify_quote("TOTAL TEAM SIZE", PAGE_27_REAL) == EXACT

    def test_curly_apostrophe_matches_straight(self):
        """`pdftotext` and the model disagree about apostrophes."""
        assert verify_quote("India's largest roads", PAGE_27_REAL) == EXACT
        assert verify_quote("India’s largest roads", PAGE_27_REAL) == EXACT


class TestLayoutTier:
    """The column-splice case this tier exists for."""

    def test_the_real_page_27_column_splice_verifies_as_layout(self):
        """MEASURED failure from a live run: the model correctly quoted the left
        column of a three-column slide, and exact matching rejected it because
        the middle column's words sit between the fragments."""
        # NOTE the token order: in the SPLICED text the middle column's words
        # ("investing experience of 19+ Years") fall between "Total team size"
        # and "33 members". A quote following the page's reading order verifies;
        # one that reorders them does not (see test_reordered_tokens_fail).
        quote = "Total team size investing experience of 19+ Years 33 members"
        assert verify_quote(quote, PAGE_27_REAL) == LAYOUT

    def test_layout_is_reported_distinctly_from_exact(self):
        """A consumer must be able to tell a reconstructed match from a
        contiguous one — they are not equally strong evidence."""
        assert verify_quote("33 members", PAGE_27_REAL) == EXACT
        assert (
            verify_quote(
                "Total team size investing experience of 19+ Years 33 members",
                PAGE_27_REAL,
            )
            == LAYOUT
        )


class TestLayoutTierDoesNotBecomeFuzzyMatching:
    """The relaxation must not admit a citation the engine cannot stand behind.

    Each test here corresponds to a specific way a fuzzy matcher would fail.
    """

    def test_a_missing_token_fails(self):
        """Every token must be present. 'Close enough' is not a match."""
        quote = "Total team size 33 members with quantum blockchain synergy"
        assert verify_quote(quote, PAGE_27_REAL) == UNVERIFIED

    def test_reordered_tokens_fail(self):
        """Order carries meaning; a bag of words does not."""
        quote = "members 33 size team Total experience investing"
        assert verify_quote(quote, PAGE_27_REAL) == UNVERIFIED

    def test_text_from_a_different_page_fails(self):
        """THE CORE GUARANTEE the coordinator asked to be pinned: real text, but
        not on the page it is cited to, is fabricated provenance."""
        pages = [PAGE_27_REAL, PAGE_13_REAL]
        # Real text from page 13 (index 2), cited to page 1.
        quote = "Deals worth Rs 2,985 crore completed or committed"
        tier, in_range = verify_against_pages(quote, 1, pages)
        assert tier == UNVERIFIED, "text from another page was accepted as verified"
        assert in_range is True
        # Cited correctly, it verifies — proving the test is not passing by accident.
        assert verify_against_pages(quote, 2, pages)[0] == EXACT

    def test_a_short_generic_phrase_cannot_use_the_layout_tier(self):
        """MEASURED: every cross-page false match on the reference run was a
        short generic phrase — 'senior advisor' (2 tokens), 'tracking gross irr'
        (3), 'managing director and partner' (4). These recur legitimately
        across a fund deck, so below MIN_TOKENS_FOR_LAYOUT a quote must match
        exactly or not at all."""
        page = "senior advisor to the board\n" + ("filler text here. " * 40) + "\nsenior advisor"
        # Present contiguously, so exact — fine.
        assert verify_quote("senior advisor", page) == EXACT
        # But a short phrase whose tokens are merely scattered must NOT verify.
        scattered = "alpha beta\n" + ("noise " * 60) + "\ngamma"
        assert verify_quote("alpha gamma", scattered) == UNVERIFIED

    def test_tokens_scattered_beyond_the_gap_bound_fail(self):
        """Without a bound, common words scattered across a dense page would
        match, which would make the check meaningless."""
        far = "alpha beta gamma delta epsilon zeta" + (" filler" * (MAX_GAP_CHARS)) + " omega"
        quote = "alpha beta gamma delta epsilon zeta omega"
        assert verify_quote(quote, far) == UNVERIFIED

    def test_an_entirely_invented_quote_fails(self):
        assert (
            verify_quote(
                "The fund guarantees a 40% net internal rate of return to all investors",
                PAGE_27_REAL,
            )
            == UNVERIFIED
        )

    def test_a_page_outside_the_document_is_flagged_separately(self):
        """Citing page 99 of a 2-page document is fabricated provenance of a
        different kind, and callers drop it rather than merely flagging it."""
        tier, in_range = verify_against_pages("33 members", 99, [PAGE_27_REAL, PAGE_13_REAL])
        assert tier == UNVERIFIED
        assert in_range is False


class TestCalibrationIsDocumented:
    def test_thresholds_match_the_measured_calibration(self):
        """These constants were calibrated against a real run (see the module
        docstring). Changing them is a decision, not a tweak — this test exists
        so a change is deliberate."""
        assert MIN_TOKENS_FOR_LAYOUT == 6
        assert MAX_GAP_CHARS == 1200


class TestNormalisation:
    def test_bullets_are_stripped_from_both_sides(self):
        page = "❖ Detailed review with IC sub-committee on performance"
        assert verify_quote("Detailed review with IC sub-committee", page) == EXACT

    def test_normalise_is_idempotent(self):
        once = normalise(PAGE_27_REAL)
        assert normalise(once) == once

    def test_empty_quote_never_verifies(self):
        assert verify_quote("", PAGE_27_REAL) == UNVERIFIED
        assert verify_quote("   \n  ", PAGE_27_REAL) == UNVERIFIED


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
