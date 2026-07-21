"""Stage 1 — Classification (PRD §5).

Determines the two things that gate everything downstream: whether the document
is analysable at all, and which AIF category applies. A non-analysable type
exits 10 and no further stage runs.
"""

from __future__ import annotations

from ..artifacts import assert_inputs_present, build_envelope, write_artifact
from ..claude_runner import run_claude
from ..errors import DocumentRejectedError, StageFailureError
from ..pdf import render_pages_for_prompt
from ..quoteverify import UNVERIFIED, verify_against_pages
from ..unresolved import UNRESOLVED_ITEM_SCHEMA, coerce_entry, enforce_kind_safety, make_entry
from .common import GROUNDING_RULES, UNRESOLVED_RULE, page_budget_note

ANALYSABLE_TYPES = {
    "pitch_deck",
    "ppm",
    "tear_sheet",
    "fact_sheet",
    "fund_overview",
    "investor_presentation",
    "quarterly_report",
}
NON_ANALYSABLE_TYPES = {
    "data_room_document",
    "financial_statement",
    "legal_document",
    "unknown",
}

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["result", "unresolved", "citations"],
    "properties": {
        "result": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "document_type",
                "is_analysable",
                "fund_name",
                "manager_name",
                "aif_category",
                "aif_category_confidence",
                "structure",
                "strategy",
                "sebi_registration",
                "document_date",
            ],
            "properties": {
                "document_type": {
                    "type": "string",
                    "enum": sorted(ANALYSABLE_TYPES | NON_ANALYSABLE_TYPES),
                    "description": (
                        "The kind of document this is. These types overlap in ordinary "
                        "usage, so apply them in this priority order and pick the FIRST "
                        "that fits: "
                        "'pitch_deck' — a slide-based fundraising document marketing a "
                        "specific fund to prospective investors (use this for any "
                        "slide deck raising a named fund, even if it is titled a "
                        "presentation); "
                        "'ppm' — a private placement memorandum, a long prose offering "
                        "document with formal risk factors and legal terms; "
                        "'investor_presentation' — a slide deck for EXISTING investors "
                        "that is not raising a new fund, e.g. an AGM or annual update; "
                        "'quarterly_report' — periodic performance reporting on a live "
                        "fund; "
                        "'fact_sheet' / 'tear_sheet' — a one-to-two page summary; "
                        "'fund_overview' — a short prose fund description that is none "
                        "of the above."
                    ),
                },
                "is_analysable": {
                    "type": "boolean",
                    "description": "True only for marketing/reporting documents describing a fund offering.",
                },
                "fund_name": {
                    "type": ["string", "null"],
                    "description": "Full legal or marketing name of the fund. Null if not stated.",
                },
                "manager_name": {
                    "type": ["string", "null"],
                    "description": "Full legal name of the investment manager. Null if not stated.",
                },
                "aif_category": {
                    "type": ["string", "null"],
                    "enum": ["CAT_I", "CAT_II", "CAT_III", None],
                    "description": "SEBI AIF category. Null if neither stated nor confidently inferable.",
                },
                "aif_category_confidence": {
                    "type": ["string", "null"],
                    "enum": ["stated", "inferred", None],
                    "description": "'stated' only if the document says the category in words.",
                },
                "structure": {
                    "type": ["string", "null"],
                    "enum": ["close_ended", "open_ended", None],
                },
                "strategy": {
                    "type": ["string", "null"],
                    "description": "Short snake_case strategy label, e.g. infrastructure_credit.",
                },
                "sebi_registration": {
                    "type": ["string", "null"],
                    "description": (
                        "SEBI AIF registration number, typically IN/AIF2/YY-YY/NNNN. "
                        "Null if no NUMBER appears. A statement that the fund is "
                        "'SEBI registered' without a number is NOT a registration number."
                    ),
                },
                "document_date": {
                    "type": ["string", "null"],
                    "description": "Date on the document as written, e.g. 'February 2026'.",
                },
            },
        },
        "unresolved": {
            "type": "array",
            "items": UNRESOLVED_ITEM_SCHEMA,
            "description": "Mandatory. One structured entry per field that could not be determined.",
        },
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["claim", "page", "quote"],
                "properties": {
                    "claim": {"type": "string"},
                    "page": {"type": "integer", "minimum": 1},
                    "quote": {"type": "string"},
                },
            },
            "description": "One citation per non-null field in result, quoting the page it came from.",
        },
    },
}

SYSTEM_PROMPT = f"""{GROUNDING_RULES}

STAGE: classification. You classify the document and identify the fund at a high
level. You do not extract detailed terms — a later stage does that.

On `sebi_registration` specifically: many Indian AIF decks state "SEBI
registered Category II AIF" as a descriptive phrase without ever printing the
registration number. That phrase establishes the CATEGORY, not the REGISTRATION
NUMBER. If no number in the form IN/AIF*/YY-YY/NNNN (or similar) appears
anywhere, `sebi_registration` MUST be null and the absence MUST be listed in
`unresolved`. Do not synthesise a number that looks right.

On `aif_category_confidence`: use `stated` only when the document uses the
category in words ("Category II AIF"). If you deduced the category from the
strategy or structure, that is `inferred`, and a downstream memo will caveat it.

{UNRESOLVED_RULE}"""



def _verify_citations(ctx, citations: list[dict], pages: list[str]) -> list[dict]:
    """Mark each citation with whether its quote occurs on the page it cites.

    MEASURED on the Neo deck: ~1 citation in 21 fails exact verification, and the
    failures cluster on multi-line layout blocks where `pdftotext -layout` pads
    with runs of spaces and newlines that the model reconstructs slightly
    differently. The text is genuinely on the page; the whitespace is not
    reproducible. So this is recorded as `quote_verified: false` rather than
    treated as fabrication.

    The engine deliberately does NOT hard-fail here. Comparing on
    whitespace-normalised text already absorbs the common case, and a residual
    mismatch is far more likely to be a layout artifact than an invented quote.
    What matters is that the discrepancy is visible in the artifact and in
    errors.jsonl rather than being silently presented as verified.
    """
    verified = 0
    for c in citations:
        page, quote = c.get("page"), c.get("quote") or ""
        tier, _ = verify_against_pages(quote, page, pages)
        ok = tier != UNVERIFIED
        c["quote_verified"] = ok
        c["verification"] = tier
        if ok:
            verified += 1
        else:
            ctx.warn(
                f"classification citation quote not found verbatim on cited page {page}",
                {"page": page, "quote": quote[:200], "claim": c.get("claim", "")[:120]},
            )
    # The grounding metric (PRD §3), recorded per stage so degradation is
    # detectable across a corpus rather than noticed once.
    ctx.stage_telemetry("classification").record_quotes(verified, len(citations))
    if citations:
        ctx.stage_progress(
            "classification",
            f"citation verification: {verified}/{len(citations)} quotes matched their cited page",
        )
    return citations


def run_classification(ctx, pages: list[str], budget, model: str | None) -> dict:
    stage = "classification"
    assert_inputs_present(ctx.out_dir, stage)  # no inputs; asserts the contract exists
    ctx.stage_started(stage)

    prompt = (
        f"{page_budget_note(len(pages))}\n\n"
        "Classify the following document and identify the fund. Return only the "
        "structured object required by the schema.\n\n"
        f"{render_pages_for_prompt(pages)}"
    )

    result = run_claude(
        prompt,
        stage=stage,
        system_prompt=SYSTEM_PROMPT,
        json_schema=SCHEMA,
        model=model,
        budget=budget,
        ctx=ctx,
    )
    # PRD §3 telemetry — tokens, resolved model, attempts and fallback for this
    # stage. Folded in immediately after the call so a later raise cannot lose
    # the accounting for work that was actually paid for.
    ctx.stage_telemetry(stage).record_call(result)
    if result.used_fallback:
        ctx.warn(
            f"stage '{stage}' used the text-mode fallback; schema conformance was "
            "not enforced by the runtime and this artifact is more likely to contain "
            "structural errors",
            {"stage": stage},
        )

    payload = result.structured
    if not isinstance(payload, dict) or "result" not in payload:
        raise StageFailureError(
            f"stage '{stage}': model returned no usable result object"
        )

    body = payload["result"]
    unresolved = payload.get("unresolved")
    if unresolved is None:
        raise StageFailureError(
            f"stage '{stage}': model omitted the mandatory 'unresolved' array"
        )
    # Structured entries (PRD §3). `enforce_kind_safety` applies the safety-first
    # classification rule in CODE — a prompt lowers the misclassification rate but
    # only the code makes it invariant, the same lesson as
    # `_enforce_blocked_criteria` in scoring.
    unresolved = enforce_kind_safety(
        [coerce_entry(u, stage) for u in unresolved], stage
    )

    # Deterministic backstop for the single most consequential hallucination in
    # this stage. If the model returned a registration number, it must actually
    # occur in the page text. This is checked in code because asking the model
    # to check itself is precisely what PRD §6.4 forbids.
    reg = body.get("sebi_registration")
    if reg:
        haystack = "\n".join(pages).replace(" ", "").upper()
        if reg.replace(" ", "").upper() not in haystack:
            ctx.warn(
                f"classification returned sebi_registration={reg!r} which does not "
                "occur in the extracted page text; discarding as unverifiable",
                {"value": reg},
            )
            body["sebi_registration"] = None
            unresolved.append(
                make_entry(
                    field_path="sebi_registration",
                    kind="DOCUMENT_ANSWERABLE",
                    stage_origin=stage,
                    account=(
                        f"The model proposed the registration number {reg!r}, but that "
                        "string does not appear anywhere in the extracted page text, so "
                        "it was discarded as unverifiable rather than carried forward. "
                        "The document states the registration in words only."
                    ),
                    typical_source="ppm",
                    criterion_codes=["CR-0001"],
                )
            )

    citations = _verify_citations(ctx, payload.get("citations", []), pages)

    envelope = build_envelope(
        stage,
        body,
        unresolved,
        citations=citations,
        inputs_hash=None,
    )
    if result.used_fallback:
        envelope["degraded"] = {"reason": "text_mode_fallback", "schema_enforced": False}
    path = write_artifact(ctx.out_dir, stage, envelope)
    ctx.stage_completed(stage, path.name, result.cost_usd)

    doc_type = body.get("document_type")
    if not body.get("is_analysable") or doc_type in NON_ANALYSABLE_TYPES:
        raise DocumentRejectedError(
            f"document classified as '{doc_type}' which is not an analysable type; "
            "no further stages will run",
            {"document_type": doc_type},
        )

    return envelope
