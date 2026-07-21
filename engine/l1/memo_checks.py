"""Invariants §6.2 and §6.4 — the two checks that only exist once a memo does.

Both are deterministic. Neither asks a model to evaluate its own output, which
is the explicit design constraint in PRD §1 point 4 and §6.4: "Models are not
asked to check their own arithmetic."

§6.2 — the memo cannot contradict its own scorecard. Scoring computes the
       recommendation deterministically; the memo must state that same
       recommendation. Disagreement is a hard failure, not a warning, because
       the documented failure mode in comparable systems is precisely a memo
       whose verdict contradicts the scorecard printed inside it.

§6.4 — every number in the memo must be traceable to an extraction field. A
       regex sweep pulls numerics out of the memo and matches them against the
       extracted values; unmatched numbers fail the run.
"""

from __future__ import annotations

import re

from .errors import InvariantViolation

# ---------------------------------------------------------------------------
# §6.2 — recommendation agreement
# ---------------------------------------------------------------------------

# NOTE: there is deliberately no prose-synonym table here. An earlier sketch
# mapped phrasings ("decline", "defer", "advance") back onto the four verdicts so
# the check could read the memo's prose. That is the wrong design: a check that
# parses prose to find a verdict is exactly as unreliable as the generation it is
# meant to guard, and it would fail open on any phrasing the table missed.
#
# Instead the memo emits its recommendation as a structured field, the engine
# renders the prose FROM that field, and this compares the two verdict strings
# exactly. The prose cannot drift from the field because it is derived from it.


def assert_recommendation_agrees(
    memo_recommendation: str | None, scoring_result: dict, source: str = "<memo>"
) -> None:
    """PRD §6.2. Raises InvariantViolation (exit 20) on disagreement.

    The comparison is on the structured `recommendation` field the memo stage
    emits alongside its prose, not on parsing the prose itself — parsing prose
    for a verdict would make the check as unreliable as the thing it guards.
    The prose is separately constrained to contain the recommendation verbatim.
    """
    expected = scoring_result.get("recommendation")
    if not expected:
        raise InvariantViolation(
            "6.2-memo-contradicts-scorecard",
            f"{source}: scoring result carries no recommendation to compare against",
        )
    if not memo_recommendation:
        raise InvariantViolation(
            "6.2-memo-contradicts-scorecard",
            f"{source}: memo states no recommendation; it cannot be checked against "
            f"the scorecard's {expected!r}",
        )

    if memo_recommendation.strip().lower() != expected.strip().lower():
        raise InvariantViolation(
            "6.2-memo-contradicts-scorecard",
            f"{source}: the memo recommends {memo_recommendation!r} but the scorecard "
            f"computed {expected!r}. A memo whose verdict contradicts the scorecard "
            "printed inside it is the documented failure this invariant exists to "
            "prevent, so this is a hard failure rather than a warning.",
            {"memo": memo_recommendation, "scoring": expected},
        )


def assert_veto_consistency(memo_json: dict, scoring_result: dict, source: str = "<memo>") -> None:
    """A vetoed scorecard must produce a memo in veto form, and vice versa."""
    scored_veto = bool(scoring_result.get("vetoed"))
    memo_veto = bool(memo_json.get("vetoed"))
    if scored_veto != memo_veto:
        raise InvariantViolation(
            "6.2-memo-contradicts-scorecard",
            f"{source}: scorecard veto status is {scored_veto} but the memo declares "
            f"{memo_veto}. A veto is terminal and cannot be dropped or invented "
            "between stages.",
            {"scoring_vetoed": scored_veto, "memo_vetoed": memo_veto},
        )


# ---------------------------------------------------------------------------
# §6.4 — numeric traceability
# ---------------------------------------------------------------------------

# Matches numbers with optional thousands separators and decimals, including
# percentages and ranges. Deliberately greedy about what counts as a number:
# a check that misses numerics is worse than one that over-collects, because
# over-collection surfaces as a traceability failure a human can inspect.
_NUMERIC_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")

# Numbers that carry no factual claim about the fund and would otherwise
# generate noise. Each exclusion is a deliberate hole in the check, so each is
# justified rather than convenient.
_STRUCTURAL_CONTEXT_RE = re.compile(
    r"""
    (?:^\#{1,6}\s*\d+\.?\s)      # markdown section headings: "## 3. Fund Facts"
  | (?:^\s*\d+\.\s)              # ordered list markers
  | (?:\bp\.\s*\d+)              # page citations — provenance, not claims
  | (?:\bpage\s+\d+)
  | (?:\bpp\.\s*\d+)
  | (?:\bCR-\d+)                 # criterion codes
  | (?:\bsection\s+\d+)          # cross-references
  | (?:\[\d+\])                  # footnote markers
    """,
    re.VERBOSE | re.IGNORECASE | re.MULTILINE,
)


def _strip_structural(text: str) -> str:
    """Blank out numerics that are structure or provenance rather than claims."""
    return _STRUCTURAL_CONTEXT_RE.sub(" ", text)


def _canonical_numbers(raw: str) -> set[str]:
    """All plausible canonical forms of a numeric string.

    '5,000' and '5000' are the same number; '2.00' and '2' are the same rate.
    Matching on a canonical set rather than the literal string avoids failing a
    memo for reformatting a figure it took verbatim from extraction.
    """
    cleaned = raw.replace(",", "")
    forms = {cleaned}
    try:
        val = float(cleaned)
    except ValueError:
        return forms
    if val.is_integer():
        forms.add(str(int(val)))
    # Trailing-zero variants: 2.00 -> 2.0 -> 2
    forms.add(("%f" % val).rstrip("0").rstrip("."))
    forms.add(str(val))
    return {f for f in forms if f}


def collect_extraction_numbers(extraction_result: dict) -> set[str]:
    """Every number appearing anywhere in the extraction artifact.

    Collects from BOTH `as_written` and `normalised`, and from `value` and
    `quote`. Matching only against `normalised` fails on the tiered-fee case
    flagged in the README: page 38 gives four management-fee tiers, so
    `normalised` is legitimately null and a memo quoting "2.00%" would have
    nothing to match. `as_written` and the source quote carry it.
    """
    numbers: set[str] = set()

    def walk(node):
        # `numbers.update(...)` mutates in place; `numbers |= ...` would rebind
        # the name and make it a local of `walk`, raising UnboundLocalError.
        if isinstance(node, dict):
            for val in node.values():
                walk(val)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, str):
            for match in _NUMERIC_RE.findall(node):
                numbers.update(_canonical_numbers(match))
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            numbers.update(_canonical_numbers(str(node)))

    walk(extraction_result)
    return numbers


def collect_supporting_numbers(*artifacts: dict) -> set[str]:
    """Numbers from non-extraction artifacts that a memo may legitimately cite.

    Scoring counts ("4 red flags"), page counts, dates, and diligence data are
    all legitimate memo content that does not originate in an extraction field.
    §6.4's purpose is to stop the memo INVENTING figures about the fund, not to
    forbid it from counting its own findings.

    IMPORTANT — pass WHOLE artifact envelopes here, not just their `result`.
    `collect_extraction_numbers` walks every string in whatever it is given, so
    passing the envelope sweeps `unresolved` entries, `absence_evidence`, and
    evidence quotes as well as structured field values.

    MEASURED, and the reason this docstring exists: a full-pipeline run failed
    §6.4 on `2,222` and `1,860`, both of which were genuinely traceable — they
    appeared in `unresolved` prose on the extraction and scoring artifacts
    ("Rs 2,222 Cr of Rs 2,985 Cr is still merely 'Committed'"; "the page 25 table
    Grand Total states 1,860"). The memo was correctly propagating real findings,
    including a document inconsistency the engine had itself caught, and was
    being failed for it. Sweeping only `result` misses exactly the prose in which
    the most valuable findings live.
    """
    numbers: set[str] = set()
    for art in artifacts:
        if not art:
            continue
        numbers |= collect_extraction_numbers(art)
    return numbers


def collect_source_numbers(pages: list[str]) -> set[str]:
    """Every number appearing verbatim in the source document text.

    A figure printed in the deck is traceable by definition — the memo quoting it
    is the memo doing its job. This is the fallback corpus, consulted after the
    artifacts.

    It is deliberately NOT the primary corpus. Matching against the whole deck
    first would let a memo assert any number that happens to appear anywhere in
    52 pages, in any context, which is close to no check at all on a
    number-dense document. Artifacts first, deck as backstop.
    """
    numbers: set[str] = set()
    for page in pages or []:
        for match in _NUMERIC_RE.findall(page):
            numbers.update(_canonical_numbers(match))
    return numbers


def build_traceable_corpus(
    *, artifacts: dict, pages: list[str] | None = None, extra: set[str] | None = None
) -> set[str]:
    """The full set of numbers a memo may legitimately contain.

    One place that decides what "traceable" means, so the memo stage and the
    acceptance tests cannot drift apart on it.

    Corpus, in order of authority:
      1. Every number in every prior artifact ENVELOPE — structured values,
         `unresolved` prose, `absence_evidence`, and evidence quotes.
      2. Every number appearing verbatim in the source page text.
      3. Explicit extras (page count, and similar engine-known quantities).
    """
    numbers: set[str] = set()
    for art in (artifacts or {}).values():
        if art:
            numbers |= collect_extraction_numbers(art)
    numbers |= collect_source_numbers(pages or [])
    numbers |= set(extra or set())
    return numbers


def assert_numerics_traceable(
    memo_markdown: str,
    allowed_numbers: set[str],
    source: str = "<memo>",
    max_report: int = 20,
) -> list[str]:
    """PRD §6.4. Raises InvariantViolation on any untraceable number.

    Returns the list of numbers checked, for reporting. The failure message names
    the offending numbers, because "a number is untraceable" without saying which
    one is not actionable.
    """
    body = _strip_structural(memo_markdown)

    untraceable: list[str] = []
    for match in _NUMERIC_RE.findall(body):
        forms = _canonical_numbers(match)
        if forms & allowed_numbers:
            continue
        # Small integers are overwhelmingly counts the memo computed about its
        # own findings ("3 red flags", "2 of 5 providers"). Requiring those to
        # appear in extraction would fail memos for correct arithmetic over
        # their own content.
        #
        # The ceiling is 100 and is the widest deliberate hole in this check: a
        # fabricated small integer passes. Larger self-computed counts (e.g. the
        # citation total in section 12, measured at 114 on one run) are NOT
        # covered by this and must be supplied explicitly by the caller via the
        # corpus — that keeps them traceable to a real computation rather than
        # widening the hole for every large number.
        cleaned = match.replace(",", "")
        try:
            if float(cleaned).is_integer() and abs(float(cleaned)) <= 100:
                continue
        except ValueError:
            pass
        untraceable.append(match)

    if untraceable:
        shown = untraceable[:max_report]
        raise InvariantViolation(
            "6.4-numeric-not-traceable",
            f"{source}: {len(untraceable)} number(s) in the memo do not appear in any "
            f"extraction field or prior artifact: {shown}"
            + (f" (and {len(untraceable) - len(shown)} more)" if len(untraceable) > len(shown) else "")
            + ". Every number in the memo must be traceable to an extracted value; "
            "an untraceable figure is either fabricated or arithmetic the engine "
            "cannot verify.",
            {"untraceable": untraceable},
        )

    return untraceable


def assert_unresolved_carried(
    memo_markdown: str, all_unresolved: list[dict], source: str = "<memo>"
) -> None:
    """PRD §5 stage 5: section 11 must carry EVERY unresolved entry from EVERY
    stage. Checked by `field_path` presence rather than by exact string, since
    the memo groups and reformats entries.

    This is the check behind "Section 11 is non-negotiable". A memo that omits
    what it could not establish presents partial analysis as complete.

    Since entries became structured (PRD §3), `field_path` is the stable
    identifier to match on — it exists precisely so this check does not depend on
    the wording of `account`. The account is separately checked for presence,
    because carrying the identifier while dropping the search account would
    satisfy the letter of this invariant and defeat its purpose: the account is
    the part that tells an analyst what has already been ruled out.
    """
    if not all_unresolved:
        return

    section = _extract_section(memo_markdown, "Open Questions")
    if section is None:
        section = _extract_section(memo_markdown, "What We Could Not Determine")
    if section is None:
        section = memo_markdown

    if not section.strip():
        raise InvariantViolation(
            "6.5-section-11-missing",
            f"{source}: the open-questions section is empty, but "
            f"{len(all_unresolved)} unresolved item(s) were recorded across the run. "
            "A memo that omits what it could not establish presents partial analysis "
            "as complete.",
        )

    normalised_section = " ".join(section.split()).lower()

    missing: list[str] = []
    accounts_missing: list[str] = []
    for entry in all_unresolved:
        if isinstance(entry, str):
            head = re.split(r"[—\-–:(]", entry, maxsplit=1)[0].strip().lower()
            head = " ".join(head.split())
            if head and head not in normalised_section:
                missing.append(entry)
            continue

        field_path = (entry.get("field_path") or "").strip().lower()
        if field_path and field_path not in normalised_section:
            missing.append(entry.get("field_path") or str(entry)[:120])
            continue

        # The account must survive too. Matching its tail rather than the whole
        # string tolerates the memo prefixing or wrapping it, while still failing
        # if the account was truncated or summarised away.
        account = " ".join((entry.get("account") or "").split()).lower()
        if len(account) > 80:
            tail = account[-80:]
            if tail not in normalised_section:
                accounts_missing.append(entry.get("field_path") or "<unnamed>")

    if missing:
        raise InvariantViolation(
            "6.5-section-11-incomplete",
            f"{source}: section 11 omits {len(missing)} of {len(all_unresolved)} "
            f"unresolved item(s). First omitted: {missing[0][:200]!r}. Every "
            "unresolved entry from every stage must be carried into the memo.",
            {"missing_count": len(missing), "missing": missing[:10]},
        )

    if accounts_missing:
        raise InvariantViolation(
            "6.5-section-11-incomplete",
            f"{source}: section 11 names {len(accounts_missing)} entry/entries but "
            f"does not carry their full search account: {accounts_missing[:10]}. The "
            "account is the part that records what was already ruled out; carrying "
            "the identifier without it satisfies the letter of this invariant and "
            "defeats its purpose.",
            {"accounts_missing": accounts_missing[:10]},
        )


# ---------------------------------------------------------------------------
# PRD §3 — the memo is a set of files, and the set must be complete
# ---------------------------------------------------------------------------

# The minimum body length, in characters, below which a section file is treated
# as empty. A section file always carries a standing header and a nav footer, so
# a file containing only those is a section whose CONTENT is missing even though
# the file exists.
#
# The threshold is deliberately LOW, and that is the whole calibration. Several
# legitimate sections are genuinely short: "No green-flag criterion fired." is a
# complete and correct section 5, and "the lenient and strict passes agreed on
# every criterion" is a complete section 9. Reporting an absence IS content — it
# is the engine doing exactly what §5 requires — so a threshold tuned to catch
# thin prose would fail runs for being honest.
#
# MEASURED: at 40 characters, a real "No green-flag criterion fired." section
# was rejected as empty. This check is only trying to catch a file that carries
# nothing but scaffolding, so the bar is set just above scaffolding and no
# higher. A too-strict version of this check would be worse than none: it would
# fail correct runs, and a check that cries wolf gets switched off.
_MIN_SECTION_BODY = 20


def assert_sections_complete(
    files: dict[str, str],
    source: str = "<memo>",
    *,
    expected: list[str] | None = None,
    min_body: int = _MIN_SECTION_BODY,
) -> None:
    """PRD §3: all 12 section files plus the index are mandatory.

    This check exists because splitting the memo created a failure mode the
    single-file memo did not have. In one file, a dropped section was a visibly
    missing heading in the middle of a document someone was already reading. As
    separate files, an absent section is invisible: the directory listing looks
    plausible, every file that IS there is well-formed, and the reader has no
    way to know that `07-team.md` was never written. **An absent file must never
    read as an empty section** — so presence and non-emptiness are asserted here
    rather than left to a reader to notice.

    `expected` defaults to the memo stage's own filename list, imported lazily so
    this module does not depend on the stage that uses it.
    """
    if expected is None:
        from .stages.memo import ALL_MEMO_FILENAMES

        expected = ALL_MEMO_FILENAMES

    missing = [name for name in expected if name not in files]
    if missing:
        raise InvariantViolation(
            "3-memo-section-missing",
            f"{source}: {len(missing)} of {len(expected)} memo file(s) were not "
            f"produced: {missing}. All twelve sections and the index are mandatory. "
            "A missing section file is a failure in its own right — it must never "
            "be readable as a section that had nothing to say.",
            {"missing": missing},
        )

    empty = []
    for name in expected:
        body = files[name]
        # Strip the standing header, the horizontal rules and the nav footer, so
        # a file carrying only its scaffolding counts as empty rather than as
        # content. Otherwise the check passes on a section whose body is blank.
        # Strip only the scaffolding the engine itself adds: headings, rules and
        # relative links. NOT all italics — a section's entire body can
        # legitimately be one italic sentence, and stripping italics wholesale
        # would make such a section indistinguishable from an empty one.
        stripped = re.sub(r"^#.*$", "", body, flags=re.MULTILINE)
        stripped = re.sub(r"^---+$", "", stripped, flags=re.MULTILINE)
        stripped = re.sub(r"\[[^\]]*\]\(\./[^)]*\)", "", stripped)
        stripped = re.sub(r"^_Written for:.*$", "", stripped, flags=re.MULTILINE)
        if len(stripped.strip()) < min_body:
            empty.append(name)

    if empty:
        raise InvariantViolation(
            "3-memo-section-empty",
            f"{source}: {len(empty)} memo file(s) were produced but carry no content "
            f"beyond their heading and navigation: {empty}. A section that could not "
            "be written must say so in words; a blank one is indistinguishable from "
            "a section the engine forgot.",
            {"empty": empty},
        )


def assert_recommendation_rendered(
    recommendation_markdown: str, scoring_result: dict, source: str = "<memo>"
) -> None:
    """§6.2, applied to `01-recommendation.md`.

    `assert_recommendation_agrees` compares structured field to structured field.
    This is the narrower companion check that the FILE a human opens actually
    renders that verdict — because after the split, the recommendation lives in
    one specific file, and a memo whose `01-recommendation.md` does not state the
    computed recommendation is exactly the contradiction §6.2 exists to prevent,
    even if the JSON is correct.

    It matches the rendered label, which the engine derives from the scorecard
    field. It is NOT prose parsing: it asserts that a string the engine itself
    generated from the field is present, not that some phrasing implies a verdict.
    """
    from .stages.memo import RECOMMENDATION_LABEL

    expected = scoring_result.get("recommendation")
    if not expected:
        raise InvariantViolation(
            "6.2-memo-contradicts-scorecard",
            f"{source}: scoring result carries no recommendation to render",
        )
    label = RECOMMENDATION_LABEL.get(expected, expected)
    if label not in recommendation_markdown:
        raise InvariantViolation(
            "6.2-memo-contradicts-scorecard",
            f"{source}: the recommendation file does not render the computed verdict "
            f"{expected!r} (expected the label {label!r} to appear). The file a reader "
            "opens must state the recommendation the scorecard computed.",
            {"expected": expected, "label": label},
        )

    # And no OTHER verdict's label may appear, which would make the file
    # ambiguous about its own conclusion.
    others = [
        lbl
        for verdict, lbl in RECOMMENDATION_LABEL.items()
        if verdict != expected and lbl in recommendation_markdown
    ]
    if others:
        raise InvariantViolation(
            "6.2-memo-contradicts-scorecard",
            f"{source}: the recommendation file renders {expected!r} but also contains "
            f"the label of a different verdict: {others}. A recommendation file that "
            "states two verdicts states none.",
            {"expected": expected, "also_present": others},
        )


def _extract_section(markdown: str, title_fragment: str) -> str | None:
    """Return the body of the section whose heading contains `title_fragment`."""
    lines = markdown.splitlines()
    start = None
    level = None
    for i, line in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m and title_fragment.lower() in m.group(2).lower():
            start = i + 1
            level = len(m.group(1))
            break
    if start is None:
        return None
    body: list[str] = []
    for line in lines[start:]:
        m = re.match(r"^(#{1,6})\s+", line)
        if m and len(m.group(1)) <= level:
            break
        body.append(line)
    return "\n".join(body)
