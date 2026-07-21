"""Stage 5 — Memo (PRD §5 stage 5).

Twelve sections, following the Addepar/Stanford survey of 54 institutions:
summary (98%), risk factors (95%), fees (90%), team (88%), portfolio role (85%),
with the recommendation stated first.

**The memo is written as one file per section into `05-memo/`, plus an index**
(PRD §3, "Why the memo is split", decided 2026-07-21). The single `05-memo.md`
reached 58KB on the reference deck, which forced one reading order on every
audience and made depth expensive: an exhaustive section 11 penalised a reader
who only wanted section 1.

Split, depth is free. Each section is written to stand alone for the audience
that opens it — IC members read 01/02/04, analysts work 09/10/11, ODD reviewers
read 07 and the service-provider rows of 03 — so each carries the context it
needs without restating whole neighbouring sections. `00-index.md` carries the
recommendation, headline counts and links, so the one-page answer never requires
opening a section file.

`05-memo.json` remains the structured form of the whole memo. Its section bodies
are unchanged by the split; it gains `memo_dir`, `memo_files` and
`unresolved_by_kind` so a consumer does not have to hardcode the layout or
re-derive the routing counts.

**Four sections involve no model generation at all.** Sections 3 (Fund Facts),
6 (Fees and Terms), 11 (Open Questions), and 12 (Sources) are
rendered directly from prior artifacts by the functions in this module. This is
the central design decision of the stage: the more of the memo that is
mechanical, the less surface there is for fabrication. A rendered table of
extracted values cannot hallucinate a fee it was not given.

The model writes only sections 1, 2, 4, 5, 7, 8, 9, 10 — and even those are
constrained, because every finding they discuss already carries its own evidence
from scoring. The model is arranging evidence into prose, not sourcing it.

**The recommendation is NOT generated.** It is computed deterministically in
scoring and rendered here. Invariant §6.2 then checks the memo's stated
recommendation against the scorecard, which is only a meaningful check because
the two are produced independently — a model asked to both state and verify its
own verdict verifies nothing.

After generation, four deterministic gates run before anything is written:
  §6.2  recommendation and veto status must agree with the scorecard  — hard fail
        (read from `01-recommendation.md`, which is where it now lives)
  §6.4  every numeric must be traceable, swept over EVERY section file — hard fail
        A fabricated number in `08-track-record.md` is exactly as dangerous as
        one in `02-rationale.md`; the split must not narrow this check.
  §5    every unresolved entry from every stage must reach
        `11-open-questions.md`, with its full search account intact    — hard fail
  §3    all 12 sections plus the index must be present and non-empty  — hard fail
        A missing file must never read as an empty section.
"""

from __future__ import annotations

import json

from ..artifacts import (
    assert_inputs_present,
    build_envelope,
    inputs_hash_of,
    write_artifact,
)
from ..claude_runner import run_claude
from ..criteria import CriteriaSet
from ..unresolved import (
    UNRESOLVED_ITEM_SCHEMA,
    coerce_entry,
    enforce_kind_safety,
)
from ..unresolved import group_by_kind as _group_by_kind
from ..errors import StageFailureError
from ..fsutil import atomic_write_text
from ..memo_checks import (
    assert_numerics_traceable,
    assert_recommendation_agrees,
    assert_recommendation_rendered,
    assert_sections_complete,
    assert_unresolved_carried,
    assert_veto_consistency,
    build_traceable_corpus,
)
from .common import GROUNDING_RULES, UNRESOLVED_RULE

RECOMMENDATION_LABEL = {
    "pass": "PASS — do not proceed",
    "hold": "HOLD — defer pending answers",
    "pursue_with_questions": "PURSUE WITH QUESTIONS — proceed to manager interview",
    "pursue": "PURSUE — proceed",
}


# ---------------------------------------------------------------------------
# Mechanical renders — sections 3, 6, 11, 12. No model involvement.
# ---------------------------------------------------------------------------


def _val(node) -> str:
    """Render one extracted field with its provenance, or an explicit not-found."""
    if node is None:
        return "_not stated in the document_"
    if not isinstance(node, dict):
        return str(node)
    raw = node.get("as_written") if node.get("as_written") is not None else node.get("value")
    if raw is None:
        return "_not stated in the document_"
    page = node.get("page")
    suffix = f" (p.{page})" if page else ""
    if node.get("quote_verified") is False:
        suffix += " ⚠︎ quote unverified"
    return f"{raw}{suffix}"


# A few extraction values are stored in machine form (`without_catch_up`) or
# carry the surrounding parenthesis of the phrase they were quoted from
# ("(Hurdle Rate 10%)"). Both are correct in the artifact and wrong in a table a
# human reads. Presentation is fixed here; the artifact is not rewritten.
_ENUM_LABEL = {
    "without_catch_up": "without catch-up",
    "with_catch_up": "with catch-up",
    "yes": "yes",
    "no": "no",
    "gross": "gross",
    "net": "net",
}


def _tidy_value(raw: str) -> str:
    text = str(raw).strip()
    if text in _ENUM_LABEL:
        return _ENUM_LABEL[text]
    # Strip a parenthesis that wraps the entire value, never one inside it.
    if text.startswith("(") and text.endswith(")") and "(" not in text[1:-1]:
        text = text[1:-1].strip()
    return text


def _confidence_note(node) -> str:
    """The inference/confidence qualifier for a field, or empty.

    Rendered as plain words, not a symbol: a reader in a text editor must be able
    to tell a stated fact from a deduced one without a legend. `medium`/`low`
    confidence on an extraction is the engine saying it read between the lines,
    and a value presented without that qualifier is a stronger claim than the
    document supports.
    """
    if not isinstance(node, dict):
        return ""
    conf = node.get("confidence")
    if conf in ("medium", "low"):
        return f" [inferred — {conf} confidence]"
    return ""


# The index's fund-facts block. Kept to the figures an IC asks for first, each
# one carrying the page it was read from. Ordered as a reader asks them, not as
# the extraction schema happens to nest them.
INDEX_FACT_SPEC: list[tuple[str, tuple[str, ...]]] = [
    ("Target size", ("fund_terms", "fund_size")),
    ("Target return", ("fund_terms", "target_return")),
    ("Return basis", ("fund_terms", "target_return_basis")),
    ("Fund term", ("fund_terms", "fund_term")),
    ("Investment period", ("fund_terms", "investment_period")),
    ("Exit period", ("fund_terms", "exit_period")),
    ("Drawdowns", ("fund_terms", "drawdowns")),
    ("Minimum commitment", ("fund_terms", "minimum_commitment")),
    ("Hurdle rate", ("economics", "hurdle_rate")),
    ("Carried interest", ("economics", "carry")),
    ("Catch-up", ("economics", "catch_up")),
    ("Management fee", ("economics", "management_fee")),
    ("Target investments", ("portfolio_construction", "target_investment_count")),
    ("Geography", ("portfolio_construction", "geography")),
]

# Fields whose ABSENCE is itself a finding. These are not "missing data" — a fund
# that does not disclose its sponsor commitment has told you something, and the
# index must say so in the same breath as the facts that were found. Rendering
# them only when present would hide the strongest signal in the extraction.
INDEX_ABSENCE_SPEC: list[tuple[str, tuple[str, ...], str]] = [
    (
        "Net return disclosed",
        ("economics", "net_return_disclosed"),
        "returns are presented gross; no net-of-fee figure is given",
    ),
    (
        "GP / sponsor commitment",
        ("economics", "gp_commitment"),
        "no sponsor commitment is stated anywhere in the document",
    ),
    (
        "Key-person clause",
        ("team", "key_person_clause"),
        "no key-person provision is stated",
    ),
    (
        "Valuation policy",
        ("portfolio_construction", "valuation_policy"),
        "no valuation policy is stated",
    ),
    (
        "Realised DPI",
        ("track_record", "realised_dpi"),
        "no realised distribution figure is given for the predecessor fund",
    ),
]


def _dig(result: dict, path: tuple[str, ...]):
    node = result
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def render_fund_facts(cls: dict, ext: dict) -> str:
    """Section 3 — direct render of classification + extraction. Zero model calls."""
    c, e = cls["result"], ext["result"]
    terms = e.get("fund_terms") or {}
    pc = e.get("portfolio_construction") or {}
    tr = e.get("track_record") or {}

    rows = [
        ("Fund", c.get("fund_name") or "_not stated_"),
        ("Manager", c.get("manager_name") or "_not stated_"),
        (
            "AIF category",
            f"{c.get('aif_category') or '_not determined_'}"
            + (
                f" ({c['aif_category_confidence']})"
                if c.get("aif_category_confidence")
                else ""
            ),
        ),
        ("Structure", c.get("structure") or "_not stated_"),
        ("Strategy", c.get("strategy") or "_not stated_"),
        (
            "SEBI registration",
            c.get("sebi_registration")
            or "**no registration number appears in the document**",
        ),
        ("Document date", c.get("document_date") or "_not stated_"),
        ("Fund size", _val(terms.get("fund_size"))),
        ("Fund term", _val(terms.get("fund_term"))),
        ("Investment period", _val(terms.get("investment_period"))),
        ("Exit period", _val(terms.get("exit_period"))),
        ("Drawdowns", _val(terms.get("drawdowns"))),
        ("Minimum commitment", _val(terms.get("minimum_commitment"))),
        ("Target return", _val(terms.get("target_return"))),
        ("Return basis", _val(terms.get("target_return_basis"))),
        ("Target investments", _val(pc.get("target_investment_count"))),
        ("Geography", _val(pc.get("geography"))),
        ("Instruments", _val(pc.get("instrument_types"))),
        ("Concentration limits", _val(pc.get("concentration_limits"))),
        ("Predecessor fund", _val(tr.get("predecessor_fund_name"))),
        ("Predecessor status", _val(tr.get("predecessor_status"))),
        ("Manager AUM", _val(tr.get("manager_aum"))),
    ]

    out = [
        "| Field | Value |",
        "|---|---|",
    ]
    out += [f"| {k} | {v} |" for k, v in rows]

    sectors = pc.get("sectors") or []
    if sectors:
        listed = ", ".join(
            f"{s.get('value')} (p.{s.get('page')})" for s in sectors if isinstance(s, dict)
        )
        out.append(f"| Sectors | {listed} |")

    providers = e.get("service_providers") or []
    if providers:
        listed = ", ".join(
            f"{p.get('firm_name')} — {p.get('role')} (p.{p.get('page')})" for p in providers
        )
        out.append(f"| Service providers | {listed} |")

    out.append("")
    out.append(
        "_Rendered directly from the extraction artifact. No model generated this "
        "section; every value carries the page it was read from._"
    )
    return "\n".join(out)


def render_fees_and_terms(ext: dict) -> str:
    """Section 6 — direct render. Zero model calls."""
    econ = (ext["result"].get("economics")) or {}
    rows = [
        ("Management fee", _val(econ.get("management_fee"))),
        ("Hurdle rate", _val(econ.get("hurdle_rate"))),
        ("Carried interest", _val(econ.get("carry"))),
        ("Catch-up", _val(econ.get("catch_up"))),
        ("GP / sponsor commitment", _val(econ.get("gp_commitment"))),
        ("Net return disclosed", _val(econ.get("net_return_disclosed"))),
        ("Worked waterfall example", _val(econ.get("waterfall_example_present"))),
    ]
    out = ["| Term | Value |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in rows]

    # A tiered fee whose `normalised` is null is a real case (Neo's page 38 gives
    # four tiers). Saying so is more useful than printing one tier as though it
    # were the headline rate.
    notes = []
    for label, key in (("Management fee", "management_fee"), ("Carried interest", "carry")):
        node = econ.get(key)
        if isinstance(node, dict) and node.get("as_written") and node.get("normalised") is None:
            notes.append(
                f"- **{label}** is stated as a tiered schedule; no single headline rate "
                "is correct, so none is asserted here. See the quoted figure above."
            )
    if notes:
        out.append("")
        out += notes

    out.append("")
    out.append("_Rendered directly from the extraction artifact. No model generated this section._")
    return "\n".join(out)


def _entry_line(entry: dict) -> str:
    """One entry rendered with its subject, routing and full search account."""
    from ..unresolved import BLOCKER_LABEL, OWNER_LABEL, SOURCE_LABEL

    bits = []
    if entry.get("typical_source"):
        bits.append(
            f"usually answered by the {SOURCE_LABEL.get(entry['typical_source'], entry['typical_source'])}"
        )
    if entry.get("blocker_class"):
        bits.append(BLOCKER_LABEL.get(entry["blocker_class"], entry["blocker_class"]))
    if entry.get("unblock_owner"):
        bits.append(
            f"unblocked by: **{OWNER_LABEL.get(entry['unblock_owner'], entry['unblock_owner'])}**"
        )
    if entry.get("criterion_codes"):
        bits.append("affects " + ", ".join(entry["criterion_codes"]))

    out = [f"**{entry.get('field_path', 'unspecified')}**"]
    if bits:
        out.append(" · ".join(bits))
    out.append("")
    out.append(entry.get("account") or "_no account recorded_")
    return "\n".join(out)


def render_open_questions(unresolved_by_stage: dict[str, list[dict]]) -> str:
    """Section 11 — every `unresolved` entry from every stage, GROUPED BY KIND.

    PRD §5: "Section 11 is non-negotiable. A memo that omits what it could not
    establish presents partial analysis as complete." So this is built by
    concatenation, not by asking a model to summarise — a summary would drop
    entries, and dropping entries is the failure the section exists to prevent.

    **Grouped by `kind`, blocked items separated and their owner named** (PRD §3
    + §0). The kinds route to genuinely different actions, and the split matters
    most for the blocked group: those questions must NOT be sent to the manager,
    because the check could not be performed at all and no answer they give would
    resolve it. Sending them would waste an analyst's time and erode trust in
    every other prompt the system makes.

    This is the Standalone Principle in practice. A Phlo user gets this routing
    as interactive affordances; a CLI-only user must get exactly the same
    information as a readable document. Someone reading only this file should
    know which questions they can act on, which need a document, and which need
    infrastructure.

    Now that the section is its own file, each entry carries its FULL search
    account rather than a compressed bullet. The engine already knows, for every
    open question, what was searched for, where it looked, and what it found
    instead; in a 58KB single-file memo that detail was squeezed. Here it is the
    point of the file — "we looked on pages 37 and 38 for sponsor commitment
    language and found none" is what stops the same search being repeated by hand.
    """
    from ..unresolved import KIND_GUIDANCE, KIND_LABEL, OWNER_LABEL, group_by_kind

    all_entries = [e for entries in unresolved_by_stage.values() for e in entries]
    total = len(all_entries)
    if total == 0:
        return (
            "No stage recorded an unresolved item. This is unusual and worth "
            "scepticism rather than comfort: on a marketing document, some things "
            "are normally undeterminable, and a run that found none is more likely "
            "to have failed to look than to have found everything."
        )

    grouped = group_by_kind(all_entries)

    out = [
        f"**{total} open question(s)** could not be determined across the run. They "
        "are stated rather than omitted, and several are more informative than the "
        "facts that were established — a fund that does not disclose its sponsor "
        "commitment has told you something.",
        "",
        "Each entry carries the full account of what was searched for, where the "
        "engine looked, and what it found instead. That account is the reason this "
        "is a worklist and not a disclaimer: it records what has already been ruled "
        "out, so the same search is not repeated by hand.",
        "",
        "**Routing summary**",
        "",
        "| Kind | Count | What to do |",
        "|---|---|---|",
    ]
    action = {
        "DOCUMENT_ANSWERABLE": "Request the document",
        "ANALYST_ANSWERABLE": "An analyst can settle it",
        "EXTERNALLY_BLOCKED": "**Do not ask the manager** — see owner",
    }
    for kind, entries in grouped.items():
        out.append(f"| {KIND_LABEL.get(kind, kind)} | {len(entries)} | {action.get(kind, '')} |")
    out.append("")

    blocked = grouped.get("EXTERNALLY_BLOCKED") or []
    if blocked:
        owners: dict[str, int] = {}
        for e in blocked:
            o = e.get("unblock_owner") or "manual_analyst_check"
            owners[o] = owners.get(o, 0) + 1
        out.append(
            "> **"
            + str(len(blocked))
            + " question(s) are blocked, not open.** The checks behind them could "
            "not be performed, so no answer from the manager would resolve them — "
            "they are listed last and must not be sent as manager questions. "
            "Owners: "
            + ", ".join(
                f"{OWNER_LABEL.get(o, o)} ({n})"
                for o, n in sorted(owners.items(), key=lambda kv: -kv[1])
            )
            + "."
        )
        out.append("")

    for kind, entries in grouped.items():
        out.append(f"## {KIND_LABEL.get(kind, kind)} — {len(entries)}")
        out.append("")
        out.append(KIND_GUIDANCE.get(kind, ""))
        out.append("")
        by_stage: dict[str, list[dict]] = {}
        for e in entries:
            by_stage.setdefault(e.get("stage_origin") or "unknown", []).append(e)
        for stage, stage_entries in by_stage.items():
            out.append(f"### From {stage} — {len(stage_entries)}")
            out.append("")
            for e in stage_entries:
                out.append(_entry_line(e))
                out.append("")
    return "\n".join(out).rstrip()


def _section_12_counts(artifacts: dict) -> set[str]:
    """The tallies section 12 prints, as strings, for the §6.4 corpus.

    Derived by the SAME traversal `render_sources` uses, so the two cannot
    disagree. If the rendering changes, this changes with it — the alternative
    (exempting large integers wholesale) would blind the check to genuinely
    fabricated figures of the same magnitude.
    """
    total = unverified = 0
    pages_seen: set[int] = set()
    for stage in ("classification", "extraction", "scoring"):
        art = artifacts.get(stage)
        if not art:
            continue
        for c in art.get("citations") or []:
            if not isinstance(c.get("page"), int):
                continue
            total += 1
            pages_seen.add(c["page"])
            if c.get("quote_verified") is False:
                unverified += 1
    return {
        str(total),
        str(len(pages_seen)),
        str(unverified),
        str(total - unverified),
    }


def render_sources(artifacts: dict) -> str:
    """Section 12 — derived from citations, not generated. Zero model calls."""
    by_page: dict[int, list[str]] = {}
    unverified = 0
    total = 0

    for stage in ("classification", "extraction", "scoring"):
        art = artifacts.get(stage)
        if not art:
            continue
        for c in art.get("citations") or []:
            page = c.get("page")
            if not isinstance(page, int):
                continue
            total += 1
            if c.get("quote_verified") is False:
                unverified += 1
            by_page.setdefault(page, []).append(
                f"{c.get('claim', '')} — \"{(c.get('quote') or '')[:160]}\""
                + ("" if c.get("quote_verified") is not False else " ⚠︎ quote not verified on this page")
            )

    out = [
        f"{total} citation(s) across {len(by_page)} page(s) of the source document. "
        f"Every quote was checked against the text of the page it cites; "
        f"{total - unverified} of {total} matched."
        + (
            f" {unverified} did not and are marked — these cluster on multi-line "
            "table layouts where whitespace is not reproducible, and are flagged "
            "rather than presented as verified."
            if unverified
            else ""
        ),
        "",
    ]

    dil = artifacts.get("diligence")
    if dil:
        out.append("**External sources consulted**")
        out.append("")
        for c in (dil.get("result") or {}).get("checks") or []:
            mark = {"passed": "✓", "failed": "✗", "unavailable": "—"}.get(c.get("outcome"), "?")
            out.append(
                f"- {mark} `{c.get('check')}` via {c.get('source')} "
                f"[{c.get('outcome')}]"
                + (f" — {c.get('url')}" if c.get("url") else "")
            )
        out.append("")

    out.append("**Document citations by page**")
    out.append("")
    for page in sorted(by_page):
        out.append(f"- **p.{page}** — {len(by_page[page])} citation(s)")
        for line in by_page[page][:6]:
            out.append(f"    - {line}")
    out.append("")
    out.append("_Derived from the citation records of prior artifacts. Not generated._")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Model-generated sections
# ---------------------------------------------------------------------------

NARRATIVE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "rationale",
        "risk_factors",
        "supporting_factors",
        "team",
        "track_record",
        "contested_findings",
        "asks",
        "unresolved",
    ],
    "properties": {
        "rationale": {
            "type": "string",
            "description": (
                "Section 2. Why the given recommendation follows from the findings, "
                "in markdown. You are EXPLAINING a recommendation that has already "
                "been computed — you are not making one, and you must not argue "
                "against it. "
                "EXPLAIN HOW THE FINDINGS COMPOUND. This section must not be a list "
                "of the findings restated; section 4 already lists them. Its job is "
                "to say why these particular findings TOGETHER produce this verdict "
                "— which ones reinforce each other, which one would change the "
                "answer if it were resolved, and what the combination means that no "
                "single finding means alone. A rationale that reads as an inventory "
                "has failed. "
                "This section has its own file, so it is not competing for space "
                "with any other section: develop the reasoning properly rather than "
                "compressing it."
            ),
        },
        "risk_factors": {
            "type": "string",
            "description": (
                "Section 4. Each fired RED_FLAG and VETO finding, with its evidence "
                "and page citations. Markdown. One subsection per finding, most "
                "severe first. Use ONLY the findings supplied — do not add concerns "
                "of your own."
            ),
        },
        "supporting_factors": {
            "type": "string",
            "description": (
                "Section 5. Each fired GREEN_FLAG finding with its evidence. Markdown. "
                "If none fired, say so plainly in one line."
            ),
        },
        "team": {
            "type": "string",
            "description": (
                "Section 7. Team and governance, from the extracted key persons, "
                "investment committee, and key-person clause, plus any diligence "
                "check on named persons. State absences explicitly."
            ),
        },
        "track_record": {
            "type": "string",
            "description": (
                "Section 8. The predecessor fund's record. Be precise about what is "
                "REALISED versus what is a mark or a tracking estimate — that "
                "distinction is the whole content of this section."
            ),
        },
        "contested_findings": {
            "type": "string",
            "description": (
                "Section 9. Every criterion where the lenient and strict passes "
                "disagreed. For each, state BOTH readings and what evidence would "
                "settle it. Do NOT resolve the disagreement. If none, say so."
            ),
        },
        "asks": {
            "type": "string",
            "description": (
                "Section 10. A numbered list of what to ask the manager, drawn from "
                "the remediation text of every fired criterion. Concrete and "
                "answerable — each item should be a question a manager could reply to "
                "with a document."
            ),
        },
        "unresolved": {
            "type": "array",
            "items": UNRESOLVED_ITEM_SCHEMA,
            "description": (
                "Mandatory. Anything you could not write with confidence, as "
                "structured entries. Usually empty — every fact you need was "
                "supplied to you, so an entry here means the supplied artifacts "
                "were insufficient to write a section honestly."
            ),
        },
    },
}


SYSTEM_PROMPT = f"""{GROUNDING_RULES}

STAGE: memo. You write the narrative sections of an Investment Committee memo
from artifacts that have already been produced and validated.

WHAT YOU ARE AND ARE NOT DOING. Every fact, finding, and figure you need has
already been extracted, scored, and evidenced. You are arranging that evidence
into prose an investment committee can read. You are NOT analysing the document,
NOT sourcing new facts, and NOT forming a view.

THE RECOMMENDATION IS ALREADY DECIDED. It was computed deterministically from
the scorecard and is supplied to you. Your `rationale` section explains why that
recommendation follows from the findings. You must not contradict it, hedge it
into a different verdict, or argue for another. An automated check compares the
memo's recommendation against the scorecard and FAILS THE RUN on disagreement.

NUMBERS. Every number you write must come from the supplied artifacts. Do not
compute new figures, do not annualise, do not convert currencies, do not
estimate. An automated regex sweep matches every numeric in your output against
the extracted values and FAILS THE RUN on any number it cannot trace. If you
want to express a magnitude you were not given, describe it in words instead.

FINDINGS ARE THE SUPPLIED FINDINGS. The criteria set is the entire question. A
concern that is real but is not among the fired criteria does not belong in the
memo. Adding one would be exactly the unrestricted recommendation-generation
this engine is designed not to do.

CONTESTED FINDINGS ARE NOT PROBLEMS TO SOLVE. Where the lenient and strict
evaluation passes disagreed, both readings are recorded. Present both. Do not
pick a winner — the disagreement is the honest output, and a human resolves it.

ABSENCES ARE CONTENT. Where a field is null or a check was unavailable, say so
plainly. "The document states no sponsor commitment" is a finding. Omitting the
subject because there was nothing to report is not.

UNAVAILABLE IS NOT CLEAN. Where a diligence check is marked unavailable, the
check was not performed. Never write that something was verified, confirmed, or
found clear on the strength of a check that did not run.

{UNRESOLVED_RULE}

Your own `unresolved` array is normally EMPTY: every fact you need has already
been supplied. An entry here means the supplied artifacts were not sufficient to
write some section honestly, which is worth stating plainly rather than papering
over."""


def _render_findings_for_prompt(findings: list[dict]) -> str:
    """Give the model the findings with their evidence already attached."""
    out = []
    for f in findings:
        status = f.get("status", "?")
        header = (
            f"### {f['criterion_code']} — {f['criterion_name']} "
            f"[{f['tier']}/{f['severity']}] status={status} "
            f"confidence={f.get('confidence')}"
        )
        out.append(header)
        if f.get("fired") is None:
            out.append(f"  NOT EVALUATED: {f.get('unevaluated_reason') or f.get('reasoning')}")
            out.append("")
            continue
        out.append(f"  fired: {f.get('fired')}")
        out.append(f"  reasoning: {f.get('reasoning')}")
        if f.get("absence_evidence"):
            out.append(f"  absence_evidence: {f['absence_evidence']}")
        for e in f.get("evidence") or []:
            mark = "" if e.get("quote_verified") is not False else " [QUOTE UNVERIFIED]"
            out.append(f"  evidence: p.{e.get('page')} \"{e.get('quote')}\"{mark}")
        if f.get("contested"):
            out.append(f"  CONTESTED: {f.get('contested_reason')}")
            for name in ("lenient", "strict"):
                r = f.get(name)
                if r:
                    out.append(
                        f"    {name} reading: fired={r.get('fired')} "
                        f"({r.get('confidence')}) — {r.get('reasoning')}"
                    )
        if f.get("remediation"):
            out.append(f"  remediation: {f['remediation']}")
        out.append("")
    return "\n".join(out)


def _build_prompt(cls, ext, dil, sco, criteria_set: CriteriaSet) -> str:
    s = sco["result"]
    findings = s.get("findings") or []
    fired = [f for f in findings if f.get("fired")]
    contested = [f for f in findings if f.get("contested")]
    unevaluated = [f for f in findings if f.get("fired") is None]

    e = ext["result"]
    team = e.get("team") or {}
    tr = e.get("track_record") or {}

    return f"""Write the narrative sections of the IC memo for this fund.

RECOMMENDATION (already computed — explain it, do not revise it):
  {s.get('recommendation')} — {RECOMMENDATION_LABEL.get(s.get('recommendation'), '')}
  basis: {s.get('recommendation_basis')}
  vetoed: {s.get('vetoed')}

SCORECARD:
  red flags fired    : {s.get('red_flags_fired')}
  green flags fired  : {s.get('green_flags_fired')}
  contested          : {s.get('contested')}
  unevaluated        : {s.get('unevaluated')}
  veto fired         : {s.get('veto_fired')}
  veto unevaluated   : {s.get('veto_unevaluated')}
  red weight {s.get('red_flag_weight')} vs green weight {s.get('green_flag_weight')}

ALL FINDINGS, with evidence already attached ({len(findings)} criteria,
{len(fired)} fired, {len(contested)} contested, {len(unevaluated)} unevaluated):

{_render_findings_for_prompt(findings)}

TEAM FACTS (from extraction):
  key_persons: {json.dumps(team.get('key_persons') or [], ensure_ascii=False)}
  key_person_clause: {_val(team.get('key_person_clause'))}
  investment_committee: {_val(team.get('investment_committee'))}

TRACK RECORD FACTS (from extraction):
  predecessor_fund_name: {_val(tr.get('predecessor_fund_name'))}
  predecessor_status: {_val(tr.get('predecessor_status'))}
  predecessor_returns: {_val(tr.get('predecessor_returns'))}
  realised_dpi: {_val(tr.get('realised_dpi'))}
  manager_aum: {_val(tr.get('manager_aum'))}

EXTERNAL DILIGENCE:
{json.dumps((dil or {}).get('result', {}).get('by_outcome', {}), indent=2)}
  Checks marked `unavailable` were NOT PERFORMED. Do not describe anything as
  verified on their strength.

Sections 3 (Fund Facts), 6 (Fees and Terms), 11 (Open Questions) and 12
(Sources) are rendered mechanically by the engine and are NOT your
responsibility. Do not write them and do not duplicate their content.

EACH SECTION BECOMES ITS OWN FILE. The memo is written as one markdown file per
section, and different readers open different files: an IC member reads the
recommendation, rationale and risk factors; an analyst works the contested
findings, asks and open questions; an operational-diligence reviewer reads team.
Write every section so it makes sense to someone who opened ONLY that file.

Concretely, that means: name the subject rather than relying on a previous
section having named it ("the predecessor fund, NIIOF-I" not "the fund above"),
and do not use cross-section deixis like "as noted above" or "as discussed
earlier". The engine adds the heading, the fund name and the navigation links to
every file, so you do not need to repeat those.

DEPTH IS NOW FREE, AND THAT IS THE POINT OF THE SPLIT. A long section no longer
penalises a reader who did not want it, so do not compress to save the reader's
time. Where the supplied evidence supports more detail — more of the reasoning,
more of the specific quotes, the precise distinction between two similar
findings — give it. Be exhaustive within the evidence you were handed. This is
NOT licence to speculate, pad, or introduce material you were not given: the
constraints above still hold in full, and more words about evidence you do not
have is the one thing worse than brevity."""


# ---------------------------------------------------------------------------
# Section assembly — one file per section, plus an index (PRD §3)
# ---------------------------------------------------------------------------

MEMO_DIR = "05-memo"
INDEX_FILENAME = "00-index.md"

# The 12 sections in reading order. Filename, heading, and the audience the
# section is written FOR — the audience note is not decoration: each body is
# written to stand alone for that reader, because with one file per section
# nobody is guaranteed to have read the one before.
SECTION_SPEC: list[tuple[str, str, str]] = [
    ("01-recommendation.md", "Recommendation", "IC"),
    ("02-rationale.md", "Rationale", "IC"),
    ("03-fund-facts.md", "Fund Facts", "IC, ODD"),
    ("04-risk-factors.md", "Risk Factors", "IC"),
    ("05-supporting-factors.md", "Supporting Factors", "IC"),
    ("06-fees-and-terms.md", "Fees and Terms", "IC, ODD"),
    ("07-team.md", "Team", "ODD"),
    ("08-track-record.md", "Track Record", "IC, ODD"),
    ("09-contested-findings.md", "Contested Findings", "Analyst"),
    ("10-asks.md", "Asks", "Analyst"),
    ("11-open-questions.md", "Open Questions", "Analyst"),
    ("12-sources.md", "Sources", "Analyst, ODD"),
]

SECTION_FILENAMES = [f for f, _, _ in SECTION_SPEC]
ALL_MEMO_FILENAMES = [INDEX_FILENAME] + SECTION_FILENAMES

# Named because invariants point at them: §6.2 reads the recommendation file and
# §11 completeness reads the open-questions file. Naming them here means a rename
# cannot leave a check silently pointing at a file that no longer exists.
RECOMMENDATION_FILENAME = "01-recommendation.md"
OPEN_QUESTIONS_FILENAME = "11-open-questions.md"


def _banners(sco: dict) -> tuple[str, str, str, str]:
    """The four standing banners, so every section renders them identically.

    Returns (draft_banner, veto_banner, veto_gap_banner, version_label).

    These are repeated on the index and on the sections where they change how
    the content should be read. That is deliberate duplication: with one file per
    section, a reader who opens `04-risk-factors.md` directly has not seen the
    index, and "these findings come from an unapproved draft rule set" is not
    something to learn later.
    """
    s = sco["result"]

    veto_banner = ""
    if s.get("vetoed"):
        veto_banner = (
            "\n> **VETO — analysis halted.** One or more veto-tier criteria fired at "
            "high confidence: "
            + ", ".join(s.get("veto_fired") or [])
            + ". A veto may prevent an investment; it can never mandate one.\n"
        )

    unevaluated_veto = s.get("veto_unevaluated") or []
    veto_gap = ""
    if unevaluated_veto:
        veto_gap = (
            "\n> **Veto criteria that could not be evaluated:** "
            + ", ".join(unevaluated_veto)
            + ". The check these depend on could not be performed, so they are "
            "reported as unevaluated — neither fired nor clean. No veto fired, but "
            "no veto was cleared either. This recommendation is made without them.\n"
        )

    # A null criteria-set version is legitimate — it means an unversioned DRAFT
    # set, which `set.yaml` documents. Rendering it as "vNone" would read as a
    # bug, and rendering it as a quiet parenthetical invites a reader to skim
    # past it. A memo produced from draft rules that nobody has signed off is a
    # materially different artifact from one produced from an approved set, so
    # the distinction gets its own banner rather than a suffix.
    cs_meta = s.get("criteria_set", {})
    cs_version = cs_meta.get("version")
    is_draft = cs_version is None
    version_label = f"v{cs_version}" if not is_draft else "DRAFT — unversioned"

    draft_banner = ""
    if is_draft:
        draft_banner = (
            "\n> **These findings were produced from a DRAFT criteria set.** "
            f"`{cs_meta.get('set_code')}` carries no version number, meaning it has "
            "not been through an approval workflow. The rules themselves — what "
            "counts as a red flag, and at what threshold — are provisional and have "
            "not been signed off. Treat the findings as indicative of what this rule "
            "set would flag, not as an assessment against an agreed house view.\n"
        )

    return draft_banner, veto_banner, veto_gap, version_label


def _agreement_label(scoring_result: dict) -> str:
    """Lenient/strict agreement as a percentage string, or an honest absence.

    The rate lives on `evaluation.agreement_rate` as a fraction. Rendering it as
    a percentage creates a number (88.2) that appears in no artifact, so
    `_index_numbers` hands it to the §6.4 corpus explicitly — the check is not
    weakened for it, the figure is declared as engine arithmetic.
    """
    ev = scoring_result.get("evaluation") or {}
    rate = ev.get("agreement_rate")
    if rate is None:
        return "not recorded"
    return f"{round(float(rate) * 100, 1)}%"


def _index_counts(unresolved_by_stage: dict, extraction_result: dict) -> set[str]:
    """Counts the index computes about itself, for the §6.4 corpus.

    The open-questions total, its per-kind counts, the blocked owner tallies and
    the number of undisclosed fields are all engine arithmetic over the
    artifacts — real quantities that appear in no artifact field. Same principle
    as `_section_12_counts`: declared by the code that prints them, never
    exempted by a magnitude rule.
    """
    from ..memo_checks import _canonical_numbers
    from ..unresolved import group_by_kind

    out: set[str] = set()
    all_open = [e for entries in (unresolved_by_stage or {}).values() for e in entries]
    out |= _canonical_numbers(str(len(all_open)))

    grouped = group_by_kind(all_open)
    for kind, entries in grouped.items():
        out |= _canonical_numbers(str(len(entries)))

    owners: dict[str, int] = {}
    for entry in grouped.get("EXTERNALLY_BLOCKED") or []:
        owner = entry.get("unblock_owner") or "manual_analyst_check"
        owners[owner] = owners.get(owner, 0) + 1
    for count in owners.values():
        out |= _canonical_numbers(str(count))

    absences = 0
    for _label, path, _meaning in INDEX_ABSENCE_SPEC:
        node = _dig(extraction_result or {}, path)
        if node is None or (isinstance(node, dict) and node.get("value") == "no"):
            absences += 1
    out |= _canonical_numbers(str(absences))
    return out


def _index_numbers(scoring_result: dict, cost_usd: float | None = None) -> set[str]:
    """Numbers the index computes about the run, for the §6.4 corpus.

    Same principle as `_section_12_counts`: an engine-computed figure is supplied
    explicitly by the code that prints it, never exempted by a magnitude rule.
    The run cost is included here for the same reason — it is a real quantity the
    engine measured, and the honest way to let it through the sweep is to declare
    it, not to widen the check for every decimal.
    """
    from ..memo_checks import _canonical_numbers

    out: set[str] = set()
    label = _agreement_label(scoring_result)
    if label != "not recorded":
        out |= _canonical_numbers(label.rstrip("%"))
    for key in ("red_flag_weight", "green_flag_weight"):
        val = scoring_result.get(key)
        if val is not None:
            out |= _canonical_numbers(str(val))
    if cost_usd:
        out |= _canonical_numbers(f"{cost_usd:.2f}")
    return out


def _section_header(cls: dict, sco: dict, number: int, title: str, audience: str) -> str:
    """A short standing header on every section file.

    Each file names the fund, the analysis date and the criteria set it was
    produced under. Without this a section file lifted out of the directory — and
    they will be, that is the point of splitting — is an unattributed opinion.
    """
    c, s = cls["result"], sco["result"]
    _, _, _, version_label = _banners(sco)
    cs_meta = s.get("criteria_set", {})
    return (
        f"# {number}. {title}\n\n"
        f"**{c.get('fund_name') or 'Unnamed Fund'}** · "
        f"{c.get('manager_name') or '_manager not stated_'} · "
        f"analysed {s.get('analysis_date')} · "
        f"criteria {cs_meta.get('set_code')} ({version_label})\n\n"
        f"_Written for: {audience}. "
        f"[Index](./{INDEX_FILENAME}) · all 12 sections are listed there._\n"
    )


def _nav_footer(number: int) -> str:
    """Relative previous/next/index links.

    Relative paths on purpose (PRD §0): these must resolve in a plain editor or
    markdown viewer on a laptop with no server, no base URL and no rendering
    layer present.
    """
    parts = []
    if number > 1:
        prev_file, prev_title, _ = SECTION_SPEC[number - 2]
        parts.append(f"← [{number - 1}. {prev_title}](./{prev_file})")
    parts.append(f"[Index](./{INDEX_FILENAME})")
    if number < len(SECTION_SPEC):
        next_file, next_title, _ = SECTION_SPEC[number]
        parts.append(f"[{number + 1}. {next_title}](./{next_file}) →")
    return "\n---\n\n" + " · ".join(parts) + "\n"


def build_sections(
    cls, ext, dil, sco, narrative: dict, unresolved_by_stage: dict, artifacts: dict
) -> dict[str, str]:
    """Build the 12 section files. Returns {filename: full markdown}.

    Every section is self-contained: standing header, banners where they matter,
    body, navigation footer. A reader who opens exactly one of these files gets
    enough context to read it correctly, without any section restating another
    in full.
    """
    s = sco["result"]
    draft_banner, veto_banner, veto_gap, _ = _banners(sco)
    rec = s.get("recommendation")
    label = RECOMMENDATION_LABEL.get(rec, rec)

    red = s.get("red_flags_fired") or []
    green = s.get("green_flags_fired") or []
    contested = s.get("contested") or []

    bodies: dict[str, str] = {}

    # --- 1. Recommendation -------------------------------------------------
    # §6.2 reads this file. The verdict is rendered from the scorecard's
    # structured field, never written by a model, which is what makes the
    # comparison in `assert_recommendation_agrees` a real check.
    bodies["01-recommendation.md"] = f"""{draft_banner}{veto_banner}{veto_gap}
**{label}**

{s.get('recommendation_basis')}

This is a decision gate, not investment advice: it recommends what to do next,
not whether to invest.

**Scorecard at a glance**

| | |
|---|---|
| Red flags fired | {len(red)}{(' — ' + ', '.join(red)) if red else ''} |
| Green flags fired | {len(green)}{(' — ' + ', '.join(green)) if green else ''} |
| Red weight vs green weight | {s.get('red_flag_weight')} vs {s.get('green_flag_weight')} |
| Contested between passes | {len(contested)}{(' — ' + ', '.join(contested)) if contested else ''} |
| Veto fired | {', '.join(s.get('veto_fired') or []) or 'none'} |
| Veto unevaluated | {', '.join(s.get('veto_unevaluated') or []) or 'none'} |

The recommendation is computed deterministically from this scorecard, not
written by a model. Why these findings compound into this verdict is
[section 2](./02-rationale.md); the findings themselves are
[section 4](./04-risk-factors.md) and [section 5](./05-supporting-factors.md).
"""

    # --- 2. Rationale ------------------------------------------------------
    bodies["02-rationale.md"] = f"""{draft_banner}{veto_gap}
_Why the recommendation in [section 1](./01-recommendation.md) follows from the findings. The findings themselves, with their evidence, are in [section 4](./04-risk-factors.md) and [section 5](./05-supporting-factors.md)._

{narrative.get('rationale', '').strip()}
"""

    # --- 3. Fund Facts -----------------------------------------------------
    bodies["03-fund-facts.md"] = f"""_Every value below is rendered directly from the extraction artifact with the page it was read from. No model generated this section. Service-provider rows are the ODD-relevant content here; economics are [section 6](./06-fees-and-terms.md)._

{render_fund_facts(cls, ext)}
"""

    # --- 4. Risk Factors ---------------------------------------------------
    bodies["04-risk-factors.md"] = f"""{draft_banner}{veto_banner}
_Each fired red-flag and veto criterion, with its evidence and page citations. Only criteria in the set can appear here — the engine does not raise concerns of its own. Where the two scoring passes disagreed about a criterion, it is in [section 9](./09-contested-findings.md) rather than presented as settled._

{narrative.get('risk_factors', '').strip()}
"""

    # --- 5. Supporting Factors ---------------------------------------------
    bodies["05-supporting-factors.md"] = f"""{draft_banner}
_Each fired green-flag criterion with its evidence. A green flag is a positive finding against a rule, not an endorsement, and it does not offset a red flag — [section 2](./02-rationale.md) explains how they were weighed._

{narrative.get('supporting_factors', '').strip()}
"""

    # --- 6. Fees and Terms -------------------------------------------------
    bodies["06-fees-and-terms.md"] = f"""_Rendered directly from the extraction artifact. No model generated this section. Fund-level terms — size, term, drawdowns — are [section 3](./03-fund-facts.md)._

{render_fees_and_terms(ext)}
"""

    # --- 7. Team -----------------------------------------------------------
    bodies["07-team.md"] = f"""{draft_banner}
_Team and governance. Where an external check on a named person could not be performed, that is stated as unperformed — never as clean. The full list of external checks and their outcomes is [section 12](./12-sources.md)._

{narrative.get('team', '').strip()}
"""

    # --- 8. Track Record ---------------------------------------------------
    bodies["08-track-record.md"] = f"""{draft_banner}
_The predecessor fund's record. The distinction between what is REALISED and what is a mark or a tracking estimate is the whole content of this section. Every number here was checked against an extracted value before this file was written, exactly as in every other section — see [section 12](./12-sources.md) for provenance._

{narrative.get('track_record', '').strip()}
"""

    # --- 9. Contested Findings ---------------------------------------------
    bodies["09-contested-findings.md"] = f"""{draft_banner}
_Criteria where the lenient and strict scoring passes disagreed. Both readings are stated and neither is resolved — the disagreement is the honest output, and a human resolves it. An empty contested set is not evidence that the document is unambiguous; it means the two passes happened to agree on this run._

{narrative.get('contested_findings', '').strip()}
"""

    # --- 10. Asks ----------------------------------------------------------
    bodies["10-asks.md"] = f"""_What to ask the manager, drawn from the remediation text of every fired criterion. These address the findings in [section 4](./04-risk-factors.md). Questions arising from what the engine could not determine at all are [section 11](./11-open-questions.md) — that list is longer and is the analyst's worklist._

{narrative.get('asks', '').strip()}
"""

    # --- 11. Open Questions ------------------------------------------------
    bodies["11-open-questions.md"] = f"""_Every `unresolved` entry from every stage of the run, with the full account of what was searched for and where. This section is non-negotiable: a memo that omits what it could not establish presents partial analysis as complete. Things to ask the manager about findings that DID fire are [section 10](./10-asks.md)._

{render_open_questions(unresolved_by_stage)}
"""

    # --- 12. Sources -------------------------------------------------------
    bodies["12-sources.md"] = f"""_Derived from the citation records of prior artifacts, not generated. Every quote was checked against the text of the page it cites; quotes that did not verify are marked rather than dropped or presented as verified._

{render_sources(artifacts)}
"""

    out: dict[str, str] = {}
    for number, (filename, title, audience) in enumerate(SECTION_SPEC, start=1):
        body = bodies[filename].strip()
        out[filename] = (
            _section_header(cls, sco, number, title, audience)
            + "\n---\n\n"
            + body
            + "\n"
            + _nav_footer(number)
        )
    return out


def build_index(
    cls, ext, dil, sco, unresolved_by_stage: dict, artifacts: dict, cost_usd: float | None
) -> str:
    """`00-index.md` — the whole answer without opening anything else.

    PRD §0 (Standalone Principle): the engine generates this, not a downstream
    system. An analyst on a laptop with no server opens this file and has the
    recommendation, the counts, and working relative links to every section.
    """
    s, c = sco["result"], cls["result"]
    draft_banner, veto_banner, veto_gap, version_label = _banners(sco)
    cs_meta = s.get("criteria_set", {})
    rec = s.get("recommendation")
    label = RECOMMENDATION_LABEL.get(rec, rec)

    red = s.get("red_flags_fired") or []
    green = s.get("green_flags_fired") or []
    contested = s.get("contested") or []
    unevaluated = s.get("unevaluated") or []

    from ..unresolved import KIND_LABEL, OWNER_LABEL, group_by_kind

    all_open = [e for entries in unresolved_by_stage.values() for e in entries]
    grouped_open = group_by_kind(all_open)
    total_open = len(all_open)

    dil_counts: dict[str, int] = {}
    for chk in ((dil or {}).get("result") or {}).get("checks") or []:
        o = chk.get("outcome", "?")
        dil_counts[o] = dil_counts.get(o, 0) + 1

    out = [
        f"# Investment Committee Memo — {c.get('fund_name') or 'Unnamed Fund'}",
        "",
        f"**Manager:** {c.get('manager_name') or '_not stated_'}  ",
        f"**Analysis date:** {s.get('analysis_date')}  ",
        f"**Criteria set:** {cs_meta.get('set_code')} ({version_label})  ",
        f"**Source document:** {c.get('document_date') or 'undated'}",
        f"{draft_banner}{veto_banner}{veto_gap}",
        "---",
        "",
        "## Recommendation",
        "",
        f"**{label}**",
        "",
        f"{s.get('recommendation_basis')}",
        "",
        "This is a decision gate, not investment advice. The recommendation is "
        "computed deterministically from the scorecard below, not written by a "
        "model.",
        "",
        "## Scorecard",
        "",
        "| | |",
        "|---|---|",
        f"| Red flags fired | **{len(red)}**{(' — ' + ', '.join(red)) if red else ''} |",
        f"| Green flags fired | **{len(green)}**{(' — ' + ', '.join(green)) if green else ''} |",
        f"| Red weight vs green weight | **{s.get('red_flag_weight')}** vs **{s.get('green_flag_weight')}** |",
        f"| Contested between passes | {len(contested)}{(' — ' + ', '.join(contested)) if contested else ''} |",
        f"| Unevaluated | {len(unevaluated)}{(' — ' + ', '.join(unevaluated)) if unevaluated else ''} |",
        f"| Veto fired | {', '.join(s.get('veto_fired') or []) or 'none'} |",
        f"| Veto unevaluated | {', '.join(s.get('veto_unevaluated') or []) or 'none'} |",
        f"| Lenient/strict agreement | {_agreement_label(s)} |",
        "",
    ]

    # How the weights were arrived at. Published on the index because an IC that
    # cannot reproduce the arithmetic behind a recommendation is right to
    # distrust it, and the sum is four rows long.
    model = s.get("scoring_model") or {}
    red_contrib = model.get("red_contributions") or []
    green_contrib = model.get("green_contributions") or []
    if red_contrib or green_contrib:
        out += [
            "### How the weights are computed",
            "",
            f"`{model.get('formula', 'score_contribution = severity_multiplier * author_weight')}`",
            "",
            "| Criterion | Severity | Multiplier | Author weight | Contribution |",
            "|---|---|---|---|---|",
        ]
        for row in red_contrib:
            out.append(
                f"| {row.get('criterion_code')} | {row.get('severity')} | "
                f"{model.get('severity_multipliers', {}).get(row.get('severity'), '')} | "
                f"{row.get('author_weight')} | {row.get('contribution')} |"
            )
        if red_contrib:
            out.append(
                f"| **Red-flag weight** | | | | **{s.get('red_flag_weight')}** |"
            )
        for row in green_contrib:
            out.append(
                f"| {row.get('criterion_code')} | {row.get('severity')} | "
                f"{model.get('severity_multipliers', {}).get(row.get('severity'), '')} | "
                f"{row.get('author_weight')} | {row.get('contribution')} |"
            )
        if green_contrib:
            out.append(
                f"| **Green-flag weight** | | | | **{s.get('green_flag_weight')}** |"
            )
        out.append("")

    # Unevaluated vetoes carry the heaviest multiplier in the model and
    # contribute nothing — because they were never checked, not because they
    # passed. Printing "0.0" beside a CRITICAL veto reads as "no problem here",
    # which is the precise misreading this block exists to prevent.
    unevaluated_veto = s.get("veto_unevaluated") or []
    if unevaluated_veto:
        mult = (model.get("severity_multipliers") or {}).get("CRITICAL")
        by_code = {f.get("criterion_code"): f for f in (s.get("findings") or [])}
        out += [
            "### Weight that was never applied",
            "",
            "| Criterion | Severity | Multiplier | Contribution | Why |",
            "|---|---|---|---|---|",
        ]
        for code in unevaluated_veto:
            finding = by_code.get(code) or {}
            sev = finding.get("severity") or "CRITICAL"
            out.append(
                f"| {code} | {sev} | "
                f"{finding.get('severity_multiplier', mult)} | "
                "— not scored | the check could not be performed |"
            )
        out += [
            "",
            "**These are not zeroes.** Each carries the heaviest multiplier in the "
            "model and contributed nothing because it was never evaluated. Their "
            "absence from the score is a gap in the arithmetic, not a point in the "
            "fund's favour.",
            "",
        ]

    if s.get("veto_unevaluated"):
        out += [
            "> No veto fired — but no veto was cleared either. The checks the "
            "unevaluated veto criteria depend on could not be performed, so they "
            "are neither fired nor clean.",
            "",
        ]

    # --- Fund facts -------------------------------------------------------
    # On the index rather than only in section 3, because the standalone reader
    # (PRD §0) forms a view from this file alone, and a recommendation without
    # the terms it was formed against is an opinion. Every row carries its page.
    e = (ext or {}).get("result") or {}
    fact_rows: list[str] = []
    for label, path in INDEX_FACT_SPEC:
        node = _dig(e, path)
        if node is None:
            continue
        raw = node.get("as_written") if isinstance(node, dict) else None
        if raw is None and isinstance(node, dict):
            raw = node.get("value")
        if raw is None:
            continue
        page = node.get("page") if isinstance(node, dict) else None
        value = _tidy_value(raw) + (f" (p.{page})" if page else "")
        fact_rows.append(f"| {label} | {value}{_confidence_note(node)} |")

    if fact_rows:
        out += [
            "## Fund facts",
            "",
            "| Field | Value (page) |",
            "|---|---|",
            *fact_rows,
            "",
            "Every value above was read from the page named beside it. Values marked "
            "`[inferred]` were deduced by the engine rather than stated in those terms "
            "by the document — they carry less weight than a quoted figure. "
            "Full detail: [section 3](./03-fund-facts.md), "
            "[section 6](./06-fees-and-terms.md).",
            "",
        ]

    # --- Absences ---------------------------------------------------------
    # Reported as findings in their own right. A reader scanning for what the
    # document says must not have to notice what it fails to say.
    absence_rows: list[str] = []
    for label, path, meaning in INDEX_ABSENCE_SPEC:
        node = _dig(e, path)
        if node is None:
            absence_rows.append(f"| **{label}** | NOT DISCLOSED | {meaning} |")
            continue
        if isinstance(node, dict) and node.get("value") == "no":
            page = node.get("page")
            where = f" (p.{page})" if page else ""
            absence_rows.append(f"| **{label}** | NO{where} | {meaning} |")

    if absence_rows:
        out += [
            f"## Not disclosed — {len(absence_rows)}",
            "",
            "These are findings, not gaps in the analysis. The engine searched for "
            "each one and the document does not contain it.",
            "",
            "| Field | Status | What the absence means |",
            "|---|---|---|",
            *absence_rows,
            "",
            "**An absence is not a neutral result.** A fund that does not state its "
            "sponsor commitment, its key-person provision or its net-of-fee return "
            "has told you something about all three.",
            "",
        ]

    out += [
        f"## Open questions — {total_open}",
        "",
        "| Kind | Count | What to do |",
        "|---|---|---|",
    ]
    _action = {
        "DOCUMENT_ANSWERABLE": "Request the document",
        "ANALYST_ANSWERABLE": "An analyst can settle it",
        "EXTERNALLY_BLOCKED": "**Do not ask the manager** — see owner",
    }
    for _kind, _entries in grouped_open.items():
        out.append(
            f"| {KIND_LABEL.get(_kind, _kind)} | {len(_entries)} | "
            f"{_action.get(_kind, '')} |"
        )

    _blocked = grouped_open.get("EXTERNALLY_BLOCKED") or []
    if _blocked:
        _owners: dict[str, int] = {}
        for _e in _blocked:
            _o = _e.get("unblock_owner") or "manual_analyst_check"
            _owners[_o] = _owners.get(_o, 0) + 1
        out += [
            "",
            f"> **{len(_blocked)} of these are blocked, not open.** The checks behind "
            "them could not be performed, so no answer from the manager would "
            "resolve them. Owners: "
            + ", ".join(
                f"{OWNER_LABEL.get(_o, _o)} ({_n})"
                for _o, _n in sorted(_owners.items(), key=lambda kv: -kv[1])
            )
            + ".",
        ]

    out += [
        "",
        "Full account of each, with what was searched for and where: "
        "[section 11](./11-open-questions.md).",
        "",
    ]

    if dil_counts:
        out += [
            "## External diligence",
            "",
            " · ".join(f"**{v}** {k}" for k, v in sorted(dil_counts.items())),
            "",
            "An `unavailable` check was NOT PERFORMED. It is never a clean result. "
            "Each check and its cause: [section 12](./12-sources.md).",
            "",
        ]

    out += [
        "## Sections",
        "",
        "| # | Section | Written for |",
        "|---|---|---|",
    ]
    for number, (filename, title, audience) in enumerate(SECTION_SPEC, start=1):
        out.append(f"| {number} | [{title}](./{filename}) | {audience} |")

    out += [
        "",
        "---",
        "",
        "_Generated by the L1 Analysis Engine. Sections 3, 6, 11 and 12 are "
        "mechanical renders of prior artifacts with no model generation. The "
        "recommendation is computed from the scorecard, not written by a model. "
        "Every number in every section file was checked against an extracted "
        "value before any of them were written._",
    ]
    if cost_usd:
        out.append("")
        out.append(f"_Run cost: ${cost_usd:.2f}._")
    return "\n".join(out) + "\n"


def run_memo(ctx, pages: list[str], budget, model: str | None) -> dict:
    stage = "memo"
    inputs = assert_inputs_present(ctx.out_dir, stage)  # PRD §6.1 — all four priors
    ctx.stage_started(stage)

    cls, ext = inputs["classification"], inputs["extraction"]
    dil, sco = inputs["diligence"], inputs["scoring"]

    prompt = _build_prompt(cls, ext, dil, sco, ctx.criteria_set)

    result = run_claude(
        prompt,
        stage=stage,
        system_prompt=SYSTEM_PROMPT,
        json_schema=NARRATIVE_SCHEMA,
        model=model,
        budget=budget,
        ctx=ctx,
    )
    # PRD §3 telemetry — see classification for why this is recorded here.
    ctx.stage_telemetry(stage).record_call(result)
    if result.used_fallback:
        ctx.warn(
            "memo stage used the text-mode fallback; schema conformance was not "
            "enforced by the runtime",
            {"stage": stage},
        )

    narrative = result.structured
    if not isinstance(narrative, dict) or "rationale" not in narrative:
        raise StageFailureError(f"stage '{stage}': model returned no usable narrative object")

    unresolved_by_stage = {
        "classification": list(cls.get("unresolved") or []),
        "extraction": list(ext.get("unresolved") or []),
        "diligence": list(dil.get("unresolved") or []),
        "scoring": list(sco.get("unresolved") or []),
    }
    all_unresolved = [u for entries in unresolved_by_stage.values() for u in entries]

    artifacts = {"classification": cls, "extraction": ext, "diligence": dil, "scoring": sco}
    sections = build_sections(cls, ext, dil, sco, narrative, unresolved_by_stage, artifacts)
    # The exact figure the index prints. Captured once and reused for the §6.4
    # corpus and the artifact, because `budget.spent_usd` keeps rising after this
    # point and `run.json`'s final total is a DIFFERENT number — re-deriving it
    # downstream would fail §6.4 on a figure the engine itself wrote.
    index_cost = getattr(budget, "spent_usd", None)
    index_md = build_index(
        cls, ext, dil, sco, unresolved_by_stage, artifacts, index_cost
    )
    files: dict[str, str] = {INDEX_FILENAME: index_md, **sections}

    s = sco["result"]
    memo_json = {
        "recommendation": s.get("recommendation"),
        "recommendation_basis": s.get("recommendation_basis"),
        "vetoed": bool(s.get("vetoed")),
        "veto_fired": s.get("veto_fired") or [],
        "veto_unevaluated": s.get("veto_unevaluated") or [],
        "sections": {
            "1_recommendation": s.get("recommendation"),
            "2_rationale": narrative.get("rationale"),
            "3_fund_facts": "rendered",
            "4_risk_factors": narrative.get("risk_factors"),
            "5_supporting_factors": narrative.get("supporting_factors"),
            "6_fees_and_terms": "rendered",
            "7_team": narrative.get("team"),
            "8_track_record": narrative.get("track_record"),
            "9_contested_findings": narrative.get("contested_findings"),
            "10_asks": narrative.get("asks"),
            "11_could_not_determine": "rendered",
            "12_sources": "rendered",
        },
        "mechanical_sections": [3, 6, 11, 12],
        # The on-disk layout, so a consumer does not have to hardcode it. Paths
        # are relative to the run directory and resolve on a plain filesystem
        # (PRD §0) — no base URL, no server.
        # The cost figure printed on the index, recorded so a consumer (or an
        # acceptance test) checks numeric traceability against what was actually
        # written rather than against a later total.
        "index_cost_usd": index_cost,
        "memo_dir": MEMO_DIR,
        "memo_files": [f"{MEMO_DIR}/{name}" for name in ALL_MEMO_FILENAMES],
        "unresolved_by_stage": unresolved_by_stage,
        "unresolved_total": len(all_unresolved),
        # Counts by routing kind, so a consumer gets the same breakdown the index
        # prints without re-deriving it — and cannot derive it differently.
        "unresolved_by_kind": {
            kind: len(entries)
            for kind, entries in _group_by_kind(all_unresolved).items()
        },
    }

    # ---------------- deterministic gates, before anything is written ----------

    # PRD §3 — all 12 sections plus the index must exist and carry content.
    # A missing file must never read as an empty section, which is exactly what a
    # split memo makes possible for the first time: in a single file a dropped
    # section was a visibly absent heading, whereas an absent FILE is invisible
    # until someone goes looking for it. So presence is asserted, not assumed.
    ctx.stage_progress(stage, "checking all 12 sections and the index are present …")
    assert_sections_complete(files, "<memo>")

    # §6.2 — the memo cannot contradict its own scorecard. The verdict now lives
    # in `01-recommendation.md`; the structured field it is rendered from is what
    # is compared, as before.
    ctx.stage_progress(stage, "checking §6.2 recommendation agreement …")
    assert_recommendation_agrees(memo_json["recommendation"], s, "<memo>")
    assert_veto_consistency(memo_json, s, "<memo>")
    assert_recommendation_rendered(
        files[RECOMMENDATION_FILENAME], s, f"<memo:{RECOMMENDATION_FILENAME}>"
    )

    # §6.4 — every numeric traceable. The corpus is every number in every prior
    # artifact ENVELOPE (structured values, `unresolved` prose, absence_evidence
    # and evidence quotes), plus every number appearing verbatim in the source
    # deck, plus the counts the engine itself computed for section 12.
    #
    # Passing envelopes rather than `result` bodies is load-bearing: a run failed
    # this check on `2,222` and `1,860`, both of which appeared in `unresolved`
    # prose recording a real document inconsistency the engine had caught. See
    # `collect_supporting_numbers`.
    ctx.stage_progress(stage, "checking §6.4 numeric traceability …")
    allowed = build_traceable_corpus(
        artifacts=artifacts,
        pages=pages,
        extra={
            str(len(pages)),
            str(ctx.page_count),
            # Section 12 states its own citation and page tallies. These are
            # engine arithmetic over the artifacts, so they are supplied
            # explicitly rather than exempted by a magnitude rule.
            *_section_12_counts(artifacts),
            # The index computes an agreement percentage and restates the
            # scorecard weights. Same principle — declared, not exempted.
            *_index_numbers(s, index_cost),
            # The index's own tallies: the open-questions total and its per-kind
            # and per-owner splits, and the count of undisclosed fields.
            *_index_counts(unresolved_by_stage, (ext or {}).get("result") or {}),
        },
    )
    # EVERY file, not just the first. A fabricated figure in `08-track-record.md`
    # is exactly as dangerous as one in `02-rationale.md`, and the split is the
    # obvious way for this check to silently narrow to whichever file the code
    # happens to hold. Sweeping the dict means adding a section cannot bypass it.
    for filename in sorted(files):
        assert_numerics_traceable(files[filename], allowed, f"<memo:{filename}>")

    # Section 11 completeness — every unresolved entry from every stage, now
    # checked against the file that carries them.
    ctx.stage_progress(stage, "checking section 11 carries every unresolved item …")
    assert_unresolved_carried(
        files[OPEN_QUESTIONS_FILENAME], all_unresolved, f"<memo:{OPEN_QUESTIONS_FILENAME}>"
    )

    ctx.stage_progress(
        stage,
        f"invariants passed: all {len(files)} memo files present, §6.2 recommendation "
        f"agrees, §6.4 all numerics traceable across every section file, "
        f"section 11 carries {len(all_unresolved)} unresolved item(s)",
    )

    envelope = build_envelope(
        stage,
        memo_json,
        enforce_kind_safety(
            [coerce_entry(u, stage) for u in (narrative.get("unresolved") or [])],
            stage,
        ),
        citations=[],  # section 12 derives citations from prior artifacts
        inputs_hash=inputs_hash_of(inputs),
    )
    if result.used_fallback:
        envelope["degraded"] = {"reason": "text_mode_fallback", "schema_enforced": False}

    memo_dir = ctx.out_dir / MEMO_DIR
    memo_dir.mkdir(parents=True, exist_ok=True)
    for filename, body in files.items():
        atomic_write_text(memo_dir / filename, body)

    path = write_artifact(ctx.out_dir, stage, envelope)
    ctx.stage_completed(
        stage, f"{MEMO_DIR}/ ({len(files)} files) + " + path.name, result.cost_usd
    )
    return envelope
