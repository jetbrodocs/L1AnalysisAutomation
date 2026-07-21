"""Stage 2 — Extraction (PRD §5).

Two patterns from the PRD, both driven by observed failure modes:

- Extract-then-normalise for numbers. Capture the number AS WRITTEN
  ("~ INR 5,000 crores") and normalise separately (5e10, INR, approximate=true).
  Normalising during extraction loses the qualifier, and the qualifier is often
  the finding — "~" and "target" and "up to" are the difference between a fact
  and a marketing aspiration.

- Every extracted field carries {value, page, quote, confidence}. A field with
  no page reference is invalid output, enforced in artifacts.validate_extraction_fields.

The PRD also specifies "text-first-then-structure" (extract passages verbatim,
then structure in a second pass). This implementation uses a single structured
pass whose schema forces a verbatim `quote` alongside every `value`, which
achieves the same anti-hallucination goal — the model cannot fill a value
without also producing the source text for it. See README for why.
"""

from __future__ import annotations

from ..artifacts import assert_inputs_present, build_envelope, inputs_hash_of, write_artifact
from ..claude_runner import run_claude
from ..errors import StageFailureError
from ..pdf import render_pages_for_prompt
from ..quoteverify import UNVERIFIED, verify_against_pages
from ..unresolved import UNRESOLVED_ITEM_SCHEMA, coerce_entry, enforce_kind_safety
from .common import GROUNDING_RULES, UNRESOLVED_RULE, page_budget_note

# A field that carries a value plus its provenance. `page` and `quote` are
# required by the schema so the model cannot emit a bare value.
def _field(desc: str, value_type="string") -> dict:
    return {
        "type": ["object", "null"],
        "additionalProperties": False,
        "required": ["value", "page", "quote", "confidence"],
        "properties": {
            "value": {"type": [value_type, "null"], "description": desc},
            "page": {"type": ["integer", "null"], "minimum": 1},
            "quote": {
                "type": ["string", "null"],
                "description": "Verbatim substring of the cited page supporting this value.",
            },
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        },
        "description": desc,
    }


def _numeric_field(desc: str) -> dict:
    """Extract-then-normalise. `as_written` is the primary record; the normalised
    form is derived and explicitly allowed to be null when normalisation is not
    safe."""
    return {
        "type": ["object", "null"],
        "additionalProperties": False,
        "required": ["as_written", "normalised", "page", "quote", "confidence"],
        "properties": {
            "as_written": {
                "type": ["string", "null"],
                "description": "The figure EXACTLY as printed, including qualifiers like '~', 'up to', 'target'.",
            },
            "normalised": {
                "type": ["object", "null"],
                "additionalProperties": False,
                "required": ["amount", "unit", "currency", "approximate"],
                "properties": {
                    "amount": {
                        "type": ["number", "null"],
                        "description": "Numeric magnitude in the base unit (e.g. 50000000000 for INR 5,000 crore).",
                    },
                    "unit": {
                        "type": ["string", "null"],
                        "description": "e.g. 'absolute', 'percent', 'years', 'count', 'multiple'.",
                    },
                    "currency": {"type": ["string", "null"], "description": "ISO code, e.g. INR. Null if not monetary."},
                    "approximate": {
                        "type": "boolean",
                        "description": "True if the source used ~, circa, up to, target, or a range.",
                    },
                },
            },
            "page": {"type": ["integer", "null"], "minimum": 1},
            "quote": {"type": ["string", "null"]},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        },
        "description": desc,
    }


def _provider_array(desc: str) -> dict:
    return {
        "type": "array",
        "description": desc,
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["role", "firm_name", "page", "quote", "confidence"],
            "properties": {
                "role": {
                    "type": "string",
                    "description": "e.g. auditor, legal_counsel, tax_advisor, custodian, registrar (RTA), banker.",
                },
                "firm_name": {"type": "string"},
                "page": {"type": "integer", "minimum": 1},
                "quote": {"type": "string"},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
            },
        },
    }


SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["result", "unresolved"],
    "properties": {
        "result": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "fund_terms",
                "economics",
                "portfolio_construction",
                "track_record",
                "team",
                "service_providers",
            ],
            "properties": {
                "fund_terms": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "fund_size",
                        "fund_term",
                        "investment_period",
                        "exit_period",
                        "drawdowns",
                        "minimum_commitment",
                        "target_return",
                        "target_return_basis",
                        "first_close_status",
                    ],
                    "properties": {
                        "fund_size": _numeric_field("Target or hard-cap fund size."),
                        "fund_term": _numeric_field("Total fund life in years."),
                        "investment_period": _numeric_field("Investment/reinvestment period in years."),
                        "exit_period": _numeric_field("Balance exit/harvest period in years."),
                        "drawdowns": _numeric_field("Number of capital drawdowns/tranches."),
                        "minimum_commitment": _numeric_field("Minimum LP commitment."),
                        "target_return": _numeric_field("Target or expected return (IRR)."),
                        "target_return_basis": _field(
                            "Whether the stated return is GROSS, NET, or unspecified. "
                            "Use exactly 'gross', 'net', or 'unspecified'. This is a "
                            "critical field: report what the document says, and if it "
                            "does not qualify the figure at all, say 'unspecified'."
                        ),
                        "first_close_status": _field("Status of first close / fundraise timeline."),
                    },
                },
                "economics": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "management_fee",
                        "hurdle_rate",
                        "carry",
                        "catch_up",
                        "gp_commitment",
                        "net_return_disclosed",
                        "waterfall_example_present",
                    ],
                    "properties": {
                        "management_fee": _numeric_field("Management fee rate and basis."),
                        "hurdle_rate": _numeric_field("Preferred return / hurdle rate."),
                        "carry": _numeric_field("Carried interest percentage."),
                        "catch_up": _field(
                            "Catch-up treatment. Use 'with_catch_up', 'without_catch_up', or 'not_stated'."
                        ),
                        "gp_commitment": _numeric_field("Sponsor/GP commitment."),
                        "net_return_disclosed": _field(
                            "Whether ANY net-to-investor return figure appears anywhere. "
                            "Use exactly 'yes' or 'no'. If 'yes', quote it."
                        ),
                        "waterfall_example_present": _field(
                            "Whether a worked distribution example or illustrative waterfall appears. 'yes' or 'no'."
                        ),
                    },
                },
                "portfolio_construction": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "target_investment_count",
                        "sectors",
                        "concentration_limits",
                        "geography",
                        "instrument_types",
                    ],
                    "properties": {
                        "target_investment_count": _numeric_field("Target number of portfolio investments."),
                        "sectors": {
                            "type": "array",
                            "description": "Target sectors, each with its page and quote.",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["value", "page", "quote", "confidence"],
                                "properties": {
                                    "value": {"type": "string"},
                                    "page": {"type": "integer", "minimum": 1},
                                    "quote": {"type": "string"},
                                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                                },
                            },
                        },
                        "concentration_limits": _field("Stated single-investment or single-sector cap, if any."),
                        "geography": _field("Target geography."),
                        "instrument_types": _field("Instruments used, e.g. NCDs, mezzanine, structured credit."),
                    },
                },
                "track_record": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "predecessor_fund_name",
                        "predecessor_status",
                        "predecessor_returns",
                        "realised_dpi",
                        "manager_aum",
                    ],
                    "properties": {
                        "predecessor_fund_name": _field("Name of the predecessor fund, if any."),
                        "predecessor_status": _field(
                            "Whether the predecessor is fully realised, partially realised, or still "
                            "investing/holding. Quote the language used."
                        ),
                        "predecessor_returns": _numeric_field("Predecessor fund returns as stated."),
                        "realised_dpi": _numeric_field("Realised DPI / distributions, if stated."),
                        "manager_aum": _numeric_field("Manager's total AUM."),
                    },
                },
                "team": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["key_persons", "key_person_clause", "investment_committee"],
                    "properties": {
                        "key_persons": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["name", "role", "page", "quote", "confidence"],
                                "properties": {
                                    "name": {"type": "string"},
                                    "role": {"type": "string"},
                                    "page": {"type": "integer", "minimum": 1},
                                    "quote": {"type": "string"},
                                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                                },
                            },
                        },
                        "key_person_clause": _field("Any described key-person clause. Null if absent."),
                        "investment_committee": _field(
                            "Investment committee description, including whether any member is independent."
                        ),
                    },
                },
                "service_providers": _provider_array(
                    "Every named service provider: auditor, legal counsel, tax advisor, custodian, registrar/RTA."
                ),
            },
        },
        "unresolved": {"type": "array", "items": UNRESOLVED_ITEM_SCHEMA},
    },
}

SYSTEM_PROMPT = f"""{GROUNDING_RULES}

STAGE: extraction. You extract the factual substrate of a fund offering.

EXTRACT-THEN-NORMALISE. For every numeric field the schema gives you both
`as_written` and `normalised`. `as_written` is the primary record and must be
the figure EXACTLY as printed, retaining every qualifier: "~ INR 5,000 crores"
is recorded with the tilde and the word crores. Do not tidy it to "5000".
`normalised` is your arithmetic conversion of that same figure into a base unit,
and `approximate` must be true whenever the source hedged (~, circa, up to,
target, or a range). If you cannot normalise safely, set `normalised` to null
and keep `as_written` — a preserved qualifier is worth more than a confident
number.

For a range like "18-20%", record `as_written` as "~ 18-20% p.a." and set
`normalised.amount` to the midpoint with `approximate: true`.

Every field object requires `page` and `quote`. If a field is not in the
document, set the WHOLE field object to null and add an `unresolved` entry.
Never emit a field with a value but no page — automated validation rejects it
and the run fails.

`target_return_basis` and `net_return_disclosed` deserve particular care. An
allocator's central question is what the investor actually receives. Report
exactly what the document qualifies the return figure as, and whether a
net-of-fees figure appears ANYWHERE. Do not treat a gross figure as net because
the deck reads as though it were.

{UNRESOLVED_RULE}"""


def run_extraction(ctx, pages: list[str], budget, model: str | None) -> dict:
    stage = "extraction"
    inputs = assert_inputs_present(ctx.out_dir, stage)  # PRD §6.1
    ctx.stage_started(stage)

    cls = inputs["classification"]["result"]
    context_note = (
        f"Prior classification (stage 1) established:\n"
        f"  fund_name: {cls.get('fund_name')}\n"
        f"  manager_name: {cls.get('manager_name')}\n"
        f"  aif_category: {cls.get('aif_category')} ({cls.get('aif_category_confidence')})\n"
        f"  structure: {cls.get('structure')}\n"
        f"  strategy: {cls.get('strategy')}\n"
        "Treat these as context, not as facts to re-derive. If the document "
        "contradicts them, extract what the document says and note the conflict "
        "in `unresolved`."
    )

    prompt = (
        f"{page_budget_note(len(pages))}\n\n{context_note}\n\n"
        "Extract the factual substrate of this fund offering per the schema.\n\n"
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
    # PRD §3 telemetry — see classification for why this is recorded here.
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
        raise StageFailureError(f"stage '{stage}': model returned no usable result object")

    unresolved = payload.get("unresolved")
    if unresolved is None:
        raise StageFailureError(
            f"stage '{stage}': model omitted the mandatory 'unresolved' array"
        )
    unresolved = enforce_kind_safety(
        [coerce_entry(u, stage) for u in unresolved], stage
    )

    body = payload["result"]
    _verify_quotes(ctx, body, pages)

    envelope = build_envelope(
        stage,
        body,
        unresolved,
        citations=_citations_from(body),
        inputs_hash=inputs_hash_of(inputs),
    )
    if result.used_fallback:
        envelope["degraded"] = {"reason": "text_mode_fallback", "schema_enforced": False}
    path = write_artifact(ctx.out_dir, stage, envelope)
    ctx.stage_completed(stage, path.name, result.cost_usd)
    return envelope



def _verify_quotes(ctx, body, pages: list[str]) -> None:
    """Check every quote actually occurs on the page it cites.

    This is the mechanical counterpart to rule 2 in the grounding prompt. A quote
    that does not occur on its cited page is either a paraphrase or a
    fabrication; either way the citation is not usable as evidence, so we
    downgrade confidence and record a warning rather than letting it pass as
    verified. We do not hard-fail: pdftotext -layout inserts whitespace that a
    model reasonably normalises, so exact-substring failure is not proof of
    fabrication. Whitespace-insensitive comparison absorbs that.
    """
    checked = mismatched = 0

    def walk(node, path=""):
        nonlocal checked, mismatched
        if isinstance(node, dict):
            quote, page = node.get("quote"), node.get("page")
            if isinstance(quote, str) and quote.strip() and isinstance(page, int):
                checked += 1
                tier, in_range = verify_against_pages(quote, page, pages)
                if in_range:
                    node["verification"] = tier
                    if tier == UNVERIFIED:
                        mismatched += 1
                        ctx.warn(
                            f"quote for '{path}' not found on cited page {page} "
                            "(neither contiguously nor as an in-order column splice)",
                            {"field": path, "page": page, "quote": quote[:200]},
                        )
                        node["confidence"] = "low"
                        node["quote_verified"] = False
                    else:
                        node["quote_verified"] = True
                else:
                    mismatched += 1
                    ctx.warn(
                        f"quote for '{path}' cites page {page}, outside 1..{len(pages)}",
                        {"field": path, "page": page},
                    )
                    node["quote_verified"] = False
            for k, v in list(node.items()):
                walk(v, f"{path}.{k}" if path else k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")

    walk(body)
    # The grounding metric (PRD §3), per stage.
    ctx.stage_telemetry("extraction").record_quotes(checked - mismatched, checked)
    ctx.stage_progress(
        "extraction",
        f"quote verification: {checked - mismatched}/{checked} quotes matched their cited page",
    )


def _citations_from(body) -> list[dict]:
    """Derive the envelope's citation list from the extracted fields.

    Derived, not generated — the citations are a projection of what was actually
    extracted, so they cannot drift from it.
    """
    out: list[dict] = []

    def walk(node, path=""):
        if isinstance(node, dict):
            quote, page = node.get("quote"), node.get("page")
            has_value = node.get("value") is not None or node.get("as_written") is not None
            if has_value and isinstance(page, int) and isinstance(quote, str) and quote.strip():
                # Carry the verification verdict through to the citation. Without
                # it the envelope's citations lose the tier that `_verify_quotes`
                # already established on the field, and memo section 12 cannot
                # tell an exact match from a reconstructed one.
                out.append(
                    {
                        "claim": path,
                        "page": page,
                        "quote": quote,
                        "quote_verified": node.get("quote_verified"),
                        "verification": node.get("verification"),
                    }
                )
            for k, v in node.items():
                walk(v, f"{path}.{k}" if path else k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")

    walk(body)
    return out
