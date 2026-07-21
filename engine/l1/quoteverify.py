"""Quote-vs-page verification. One implementation, used by every stage.

This is the mechanical half of the engine's grounding claim: a model asserts
"page 37 says X", and this module checks whether page 37 actually says X. It is
the reason a citation here is evidence rather than a decoration.

THE PROBLEM IT SOLVES, established by inspecting every failure on a real run
(17 of 73 evidence quotes unverified, none of them fabricated):

`pdftotext -layout` renders a multi-column slide by splicing the columns
together line by line. On page 27 of the reference deck, the left column reads
"Total team size / 33 members", but the extracted text is:

    India's largest roads
    Total team size        investing experience of
                           19+ Years                 platforms have joined
    33 members                                       the team

A model reading that slide correctly quotes "Total team size 33 members". Those
words are genuinely on the page, in that order — but they are NOT CONTIGUOUS,
because the middle column's text sits between them. Exact substring matching
fails, and whitespace normalisation does not help: the intervening characters
are other columns' words, not whitespace.

THE FIX, AND ITS DELIBERATE LIMIT. Verification proceeds in three tiers, each
weaker than the last, and the tier that succeeded is recorded on the citation so
a consumer can tell an exact match from a reconstructed one:

  `exact`      — the normalised quote is a contiguous substring of the page.
  `layout`     — the quote's tokens appear on the page IN ORDER, with a bounded
                 amount of intervening text (the column-splice case above).
  `unverified` — neither. Treated as before: flagged, confidence downgraded,
                 warned to errors.jsonl, never silently presented as verified.

**This is explicitly NOT a fuzzy or similarity match, and must not become one.**
Three properties keep it strict:

  1. EVERY token of the quote must be present. No token may be missing, so a
     quote cannot be "close enough" to a page that lacks its key words.
  2. Tokens must appear IN THE QUOTE'S OWN ORDER. Reordered words fail.
  3. The gap between consecutive tokens is BOUNDED (`MAX_GAP_CHARS`). Without a
     bound, any set of common words scattered across a dense page would match,
     which would make the check meaningless — the failure mode this bound exists
     to prevent.

A quote whose text lives on a DIFFERENT page still fails, which is the entire
point: that is fabricated provenance. `tests/test_quote_verification.py` pins
this with real text from the reference deck.
"""

from __future__ import annotations

import re
import unicodedata

# Both bounds below were CALIBRATED, not guessed: every evidence quote from a
# real scoring run was tested against its cited page and against all 51 other
# pages, and the thresholds chosen to rescue genuine column splices while
# admitting ZERO cross-page matches.
#
# The measurement that determined the design (see README VERIFIED item 10):
#
#   Genuine splices need gaps up to ~1,137 chars (a 3-column slide on p.27,
#   and p.52's dense disclaimer). But cross-page FALSE matches occur at gaps
#   as low as 1. So GAP SIZE ALONE CANNOT SEPARATE the two — a bound tight
#   enough to exclude the false matches would also reject most real splices.
#
#   What separates them is TOKEN COUNT. Every cross-page false match was a
#   short generic phrase that legitimately recurs in a fund deck:
#   "senior advisor" (2 tokens), "tracking gross irr" (3),
#   "managing director and partner" (4). Genuine wide splices are long,
#   distinctive passages.
#
# Measured on the reference run (rescued / cross-page false matches):
#     min_tokens=5, gap=1200  ->  11 rescued, 1 FALSE
#     min_tokens=6, gap=1200  ->   8 rescued, 0 false   <- chosen
#     min_tokens=8, gap=1200  ->   4 rescued, 0 false
#
# 6/1200 is chosen over 5/1200 deliberately: three fewer quotes verify, but a
# single cross-page match would be a fabricated citation reported as verified,
# which is exactly the failure this module exists to prevent. Recall is the
# cheaper thing to give up.
MAX_GAP_CHARS = 1200

# A quote shorter than this must match EXACTLY or not at all. Short quotes carry
# too little signal to reconstruct safely across a splice.
MIN_TOKENS_FOR_LAYOUT = 6

EXACT = "exact"
LAYOUT = "layout"
UNVERIFIED = "unverified"

# Decorative glyphs that appear in slide bullets and are frequently dropped or
# substituted when a model transcribes them. Removing them from both sides
# cannot manufacture a match on its own, because every remaining word token must
# still be present and in order.
_BULLETS = "❖✦✧◆◇▪▫●○•·‣⁃⁌⁍☞➤➜→"

_PUNCT_MAP = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "–": "-", "—": "-", "―": "-", "−": "-",
    " ": " ", " ": " ", " ": " ", " ": " ",
    "​": "", "﻿": "",
}


def normalise(text: str) -> str:
    """Canonical form for comparison. Applied to BOTH sides, never one.

    NFKC folds ligatures and full-width forms; curly punctuation is straightened
    because `pdftotext` and the model disagree about apostrophes; decorative
    bullets are dropped; all whitespace runs (including newlines) collapse to a
    single space. Case is folded last.
    """
    text = unicodedata.normalize("NFKC", text)
    for src, dst in _PUNCT_MAP.items():
        text = text.replace(src, dst)
    text = "".join(" " if ch in _BULLETS else ch for ch in text)
    return " ".join(text.split()).strip().lower()


_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[.,%/'-][a-z0-9]+)*|[%₹$]")


def _tokens(normalised: str) -> list[str]:
    """Word-ish tokens. Keeps figures such as `18-20`, `2.00%`, `~21%` intact."""
    return _TOKEN_RE.findall(normalised)


def _layout_match(quote_norm: str, page_norm: str) -> bool:
    """True when the quote's tokens occur on the page in order, closely spaced.

    Greedy leftmost scan: for each token take its earliest occurrence at or
    after the previous token's end, and reject if the gap exceeds
    MAX_GAP_CHARS. Greedy is sufficient here and keeps the check linear — the
    bounded gap is what does the real work of preventing a page-wide scatter
    from matching.
    """
    toks = _tokens(quote_norm)
    if len(toks) < MIN_TOKENS_FOR_LAYOUT:
        return False

    pos = 0
    first = True
    for tok in toks:
        idx = page_norm.find(tok, pos)
        if idx < 0:
            return False  # a token is simply absent — never a match
        if not first and (idx - pos) > MAX_GAP_CHARS:
            return False  # tokens too far apart to be one spliced passage
        pos = idx + len(tok)
        first = False
    return True


def verify_quote(quote: str, page_text: str) -> str:
    """Return EXACT, LAYOUT, or UNVERIFIED for one quote against one page."""
    if not quote or not quote.strip():
        return UNVERIFIED
    q, p = normalise(quote), normalise(page_text)
    if not q:
        return UNVERIFIED
    if q in p:
        return EXACT
    return LAYOUT if _layout_match(q, p) else UNVERIFIED


def verify_against_pages(quote: str, page: object, pages: list[str]) -> tuple[str, bool]:
    """Verify a quote against its cited page.

    Returns `(tier, in_range)`. `in_range` is False when the cited page number
    does not exist in the document — fabricated provenance, which callers treat
    more severely than a failed text match.
    """
    if not isinstance(page, int) or not (1 <= page <= len(pages)):
        return UNVERIFIED, False
    return verify_quote(quote, pages[page - 1]), True
