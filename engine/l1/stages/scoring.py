"""Stage 4 — Scoring (PRD §5 stage 4).

Evaluates every active criterion against the classification, extraction, and
diligence artifacts. This is where the criteria set stops being data and starts
being a judgement.

Three design decisions dominate this module.

**Dual-pass evaluation.** Each criterion is evaluated twice, independently: a
LENIENT pass ("does the document plausibly satisfy this?") and a STRICT pass
("does it demonstrably satisfy this, with evidence?"). The two passes are
separate model invocations that never see each other's output — a single call
asked to produce both readings will anchor the second on the first and the
disagreement rate collapses to near zero, which looks like agreement but is
just contamination.

Where the passes disagree the criterion is marked `contested` and BOTH readings
are recorded. It is deliberately not resolved. A tiebreak pass would produce a
cleaner artifact and a less honest one: when the evidence genuinely supports two
readings, saying so is the correct output, and the memo surfaces it in section 9
for human judgement.

**Absence evidence.** A criterion that fires because something is *missing*
makes an unfalsifiable claim unless it states what was searched. `absence_evidence`
is required whenever a finding has no positive evidence, and is enforced by
`validate_finding_evidence` before the artifact is written.

**Veto asymmetry.** A veto criterion that fires with high confidence halts the
run (exit 11). A veto criterion whose underlying check could not be performed is
`veto_unevaluated` — a third state, distinct from both fired and not_fired, so
no downstream consumer can read an unperformed check as a clean result. This is
the scoring-side counterpart of diligence's `unavailable` ≠ `passed` rule.
"""

from __future__ import annotations

import json
from datetime import date, datetime

from ..artifacts import (
    assert_inputs_present,
    build_envelope,
    inputs_hash_of,
    write_artifact,
)
from ..claude_runner import run_claude
from ..criteria import CriteriaSet
from ..quoteverify import UNVERIFIED, verify_against_pages
from ..errors import StageFailureError
from ..unresolved import UNRESOLVED_ITEM_SCHEMA, coerce_entry, enforce_kind_safety, make_entry
from .common import GROUNDING_RULES, UNRESOLVED_RULE, page_budget_note

CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}

# A veto fires the run-halting path only at this confidence or above. A
# medium-confidence veto is recorded as fired but does not halt: halting a run
# on a judgement the engine itself is unsure of inverts the asymmetry that makes
# vetoes safe (they may prevent an investment, never mandate one).
VETO_HALT_CONFIDENCE = "high"


def _finding_schema(pass_name: str) -> dict:
    """Schema for one evaluation pass over the whole criteria set.

    `fired`, `confidence`, `evidence`, `absence_evidence`, `reasoning`, and
    `remediation` are all required — the model cannot emit a finding that omits
    the fields the invariants check.
    """
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["findings", "unresolved"],
        "properties": {
            "findings": {
                "type": "array",
                "description": (
                    f"One entry for EVERY criterion supplied, evaluated under the "
                    f"{pass_name} standard. Do not omit criteria that did not fire — "
                    "a criterion missing from this array is indistinguishable from "
                    "one you forgot to evaluate."
                ),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "criterion_code",
                        "fired",
                        "confidence",
                        "evidence",
                        "absence_evidence",
                        "reasoning",
                        "remediation",
                        "evaluable",
                    ],
                    "properties": {
                        "criterion_code": {
                            "type": "string",
                            "description": "Exactly as supplied, e.g. CR-0010.",
                        },
                        "fired": {
                            "type": "boolean",
                            "description": (
                                "True if the criterion's condition is met by this "
                                "document. For a GREEN_FLAG this means the positive "
                                "signal is present; for a RED_FLAG or VETO it means "
                                "the concern is present."
                            ),
                        },
                        "evaluable": {
                            "type": "boolean",
                            "description": (
                                "False ONLY when the check could not be performed at "
                                "all — e.g. it depends on an external register that "
                                "the diligence stage recorded as `unavailable`. A "
                                "criterion you evaluated and found not to apply is "
                                "evaluable:true with fired:false. Do not use "
                                "evaluable:false to express uncertainty."
                            ),
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                        "evidence": {
                            "type": "array",
                            "description": (
                                "Page-level evidence supporting the verdict. Required "
                                "whenever the criterion fires on the PRESENCE of "
                                "something. Each quote must be an exact substring of "
                                "the cited page."
                            ),
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["page", "quote"],
                                "properties": {
                                    "page": {"type": "integer", "minimum": 1},
                                    "quote": {"type": "string"},
                                },
                            },
                        },
                        "absence_evidence": {
                            "type": ["string", "null"],
                            "description": (
                                "REQUIRED when the criterion fires on the ABSENCE of "
                                "something. Must state what was searched: which terms, "
                                "across how many pages, and what those searches "
                                "returned. 'No net IRR figure was found' is not "
                                "acceptable; 'searched all 52 pages for net, "
                                "net-to-investor, net IRR, post-fee, after fees — only "
                                "gross figures on pp.4, 20, 52' is. Null when the "
                                "finding rests on positive evidence alone."
                            ),
                        },
                        "reasoning": {
                            "type": "string",
                            "description": (
                                "Why the verdict follows from the evidence, under this "
                                "pass's standard specifically."
                            ),
                        },
                        "remediation": {
                            "type": ["string", "null"],
                            "description": (
                                "What to ask the manager. Null when the criterion did "
                                "not fire."
                            ),
                        },
                    },
                },
            },
            "unresolved": {
                "type": "array",
                "items": UNRESOLVED_ITEM_SCHEMA,
                "description": (
                    "Mandatory. One structured entry per criterion you could not "
                    "evaluate, and why."
                ),
            },
        },
    }


LENIENT_STANDARD = """
EVALUATION STANDARD FOR THIS PASS: LENIENT.

You are asking: **does the document plausibly satisfy this criterion?**

Under the lenient standard you may rely on reasonable reading. If the document
substantially conveys what the criterion asks about, even without stating it in
the criterion's own words, treat the criterion as met. Indirect support,
implication from adjacent statements, and ordinary industry reading are all
admissible here.

You may NOT invent facts. Lenient means a generous reading of what is present,
never a supply of what is absent. Every finding still cites the page it read.
""".strip()


STRICT_STANDARD = """
EVALUATION STANDARD FOR THIS PASS: STRICT.

You are asking: **does the document DEMONSTRABLY satisfy this criterion, with
evidence a sceptical reader would accept?**

Under the strict standard, only explicit statements count. An implication is not
a statement. Something that "must be true given the strategy" is not evidence.
If the criterion requires five service providers named, four named and one
implied does not satisfy it. If it requires a percentage, a commitment described
without a percentage does not satisfy it.

Where the lenient reading would accept an inference, the strict reading rejects
it and says what would have been needed instead.
""".strip()


SYSTEM_PROMPT_TEMPLATE = """{grounding}

STAGE: scoring. You evaluate a fixed set of admin-authored criteria against a
fund document and the structured facts already extracted from it.

You do NOT invent concerns. You are not asked whether this is a good fund. You
are asked, for each supplied criterion and only those criteria, whether its
stated condition is met by this document. A concern that is real but is not one
of the supplied criteria is out of scope — the criteria set is the entire
question.

{standard}

TIER SEMANTICS. `fired: true` means the criterion's CONDITION IS MET, whatever
its tier:
  - VETO / RED_FLAG — the concern described is present. Firing is adverse.
  - GREEN_FLAG — the positive signal described is present. Firing is favourable.
Do not invert green flags. CR-0033 "tier-one service provider set" fires when
the providers ARE all named and institutional.

ABSENCE EVIDENCE IS MANDATORY WHEN YOU FIRE ON ABSENCE. Several criteria fire
precisely because something is missing. Asserting a thing is absent is a claim
about all {page_count} pages, and it is unfalsifiable unless you state what you
searched for. When `evidence` is empty and `fired` is true, `absence_evidence`
must name the search terms used and report what each returned. A finding that
fires with neither positive evidence nor a stated search is rejected by
automated validation and fails the run.

AN UNREACHABLE SOURCE IS NEVER AN ADVERSE FINDING. This is the rule most easily
reasoned past, so read it carefully. Some criteria depend on an external register
— SEBI registration validity, enforcement history. Where the diligence section
above marks a check UNAVAILABLE, that check WAS NOT PERFORMED. You may draw no
conclusion from it in either direction.

In particular, do NOT reason "the document does not state it AND the register
could not be reached, therefore it is unverified, therefore the criterion fires."
That chain is invalid. The correct verdict is `evaluable: false` — the check
could not be performed, so the criterion cannot be evaluated. An unreachable
regulator means we do not know; it does not mean the fund has a problem. Firing
a veto on a check nobody performed would halt an analysis over a network
timeout.

`evaluable: false` is exactly what that state is for. Use it whenever your
verdict would otherwise rest on the absence of an external check rather than on
the content of the document.

MUTUALLY EXCLUSIVE PAIRS. Some criteria are inverses of one another and must not
both fire on the same facts: CR-0015 (providers unnamed) vs CR-0033 (tier-one
provider set); CR-0011 (predecessor unrealised) vs CR-0031 (predecessor
realised). If you find yourself firing both, you have made an error — re-read.

EVERY criterion supplied must appear exactly once in `findings`. A criterion you
believe irrelevant is `fired: false` with reasoning, not an omission.

{unresolved}"""


def _fmt_field(node) -> str:
    """Render one extracted field compactly for the prompt, preserving provenance."""
    if node is None:
        return "null (not found in document)"
    if not isinstance(node, dict):
        return json.dumps(node, ensure_ascii=False)
    val = node.get("value", node.get("as_written"))
    if val is None and node.get("normalised"):
        val = node["normalised"].get("amount")
    page = node.get("page")
    conf = node.get("confidence")
    if val is None:
        return "null (not found in document)"
    bits = [json.dumps(val, ensure_ascii=False)]
    if page:
        bits.append(f"p.{page}")
    if conf:
        bits.append(f"conf={conf}")
    if node.get("quote_verified") is False:
        bits.append("QUOTE UNVERIFIED")
    return " ".join(bits)


def _render_extraction(result: dict) -> str:
    """Flatten the extraction result into a readable fact sheet.

    Passing raw extraction JSON works but buries the values under schema
    scaffolding. This keeps the value, its page, and its confidence adjacent,
    which is what the criteria are actually evaluated against.
    """
    lines: list[str] = []

    def walk(node, prefix=""):
        if not isinstance(node, dict):
            return
        for key, val in node.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(val, dict) and ("value" in val or "as_written" in val):
                lines.append(f"  {path}: {_fmt_field(val)}")
            elif isinstance(val, dict):
                walk(val, path)
            elif isinstance(val, list):
                if not val:
                    lines.append(f"  {path}: [] (none found)")
                for i, item in enumerate(val):
                    if isinstance(item, dict):
                        label = item.get("firm_name") or item.get("name") or item.get("value")
                        role = item.get("role")
                        page = item.get("page")
                        quote = (item.get("quote") or "")[:120]
                        desc = f"{label}" + (f" ({role})" if role else "")
                        lines.append(f"  {path}[{i}]: {desc} p.{page} — \"{quote}\"")
            elif val is None:
                lines.append(f"  {path}: null (not found in document)")
            else:
                lines.append(f"  {path}: {json.dumps(val, ensure_ascii=False)}")

    walk(result)
    return "\n".join(lines)


def _render_diligence(dil: dict | None) -> str:
    """Render the diligence artifact, making `unavailable` impossible to misread.

    The rendering is deliberately verbose about unavailability. A check that
    could not be performed must never read to the model as a check that passed —
    that conflation is exactly what PRD §5 stage 3 forbids, and it would silently
    convert an unreachable regulator into a clean bill of health.
    """
    if not dil:
        return (
            "DILIGENCE: not run. No external verification was performed. Treat every "
            "external claim as UNVERIFIED — not as verified, and not as contradicted."
        )
    checks = dil.get("checks") or []
    if not checks:
        return "DILIGENCE: ran but produced no checks. Treat external claims as UNVERIFIED."

    lines = ["DILIGENCE CHECKS (external verification):"]
    for c in checks:
        outcome = c.get("outcome", "unknown")
        name = c.get("check")
        source = c.get("source")
        detail = c.get("detail") or ""
        if outcome == "unavailable":
            lines.append(
                f"  - {name} [{source}]: UNAVAILABLE — the source could not be "
                f"reached, so this check WAS NOT PERFORMED. Reason: "
                f"{c.get('reason') or 'not stated'}. This is NOT a pass. You may "
                f"draw no conclusion, favourable or adverse, from this line."
            )
        elif outcome == "passed":
            lines.append(f"  - {name} [{source}]: PASSED — claim verified. {detail}")
        elif outcome == "failed":
            lines.append(f"  - {name} [{source}]: FAILED — claim contradicted. {detail}")
        else:
            lines.append(f"  - {name} [{source}]: {outcome}. {detail}")
    return "\n".join(lines)


def _parse_document_date(raw: str | None) -> date | None:
    """Best-effort parse of a document date like 'February 2026'.

    Deliberately conservative: returns None rather than guessing. CR-0017 is an
    arithmetic comparison, and an arithmetic comparison against a date we had to
    guess is worse than no comparison. A None here means the model does the
    staleness reasoning from the stated date instead, and says so.
    """
    if not raw or not isinstance(raw, str):
        return None
    cleaned = raw.strip().replace(",", "")
    formats = (
        "%B %Y", "%b %Y", "%B %d %Y", "%b %d %Y", "%d %B %Y", "%d %b %Y",
        "%Y-%m-%d", "%d/%m/%Y", "%m/%Y", "%Y",
    )
    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def _analysis_date_note(cls_result: dict, today: date) -> str:
    """Supply CR-0017's arithmetic rather than asking the model to do it.

    PRD §6.4's principle — models are not asked to check their own arithmetic —
    applies here too. The elapsed-months computation is deterministic, so the
    engine performs it and hands the model the result to reason about.
    """
    raw = cls_result.get("document_date")
    doc_date = _parse_document_date(raw)
    lines = [
        "DATE ARITHMETIC (computed by the engine, not by you — use these numbers):",
        f"  analysis date  : {today.isoformat()}",
        f"  document date  : {raw or 'not stated in the document'}",
    ]
    if doc_date is not None:
        months = (today.year - doc_date.year) * 12 + (today.month - doc_date.month)
        lines.append(f"  parsed as      : {doc_date.isoformat()}")
        lines.append(f"  elapsed        : {months} months")
        lines.append(
            f"  → The document is {months} months old as of the analysis date. "
            f"Criteria with a staleness threshold should be evaluated against this "
            f"number, which is arithmetic, not judgement."
        )
    else:
        lines.append(
            "  parsed as      : COULD NOT PARSE — the engine could not convert the "
            "stated document date into a comparable date. Do the comparison from the "
            "date as written if you can do so unambiguously; if you cannot, mark the "
            "staleness criterion evaluable:false and say why."
        )
    return "\n".join(lines)


def _build_prompt(
    criteria_set: CriteriaSet,
    cls: dict,
    ext: dict,
    dil: dict | None,
    pages: list[str],
    today: date,
) -> str:
    from ..pdf import render_pages_for_prompt

    cls_r = cls["result"]
    ext_r = ext["result"]

    upstream_unresolved = list(cls.get("unresolved", [])) + list(ext.get("unresolved", []))
    if dil:
        upstream_unresolved += list(dil.get("unresolved", []))

    unresolved_block = (
        "\n".join(
            f"  - [{u.get('kind')}] {u.get('field_path')}: {u.get('account')}"
            if isinstance(u, dict)
            else f"  - {u}"
            for u in upstream_unresolved
        )
        or "  (none)"
    )

    return f"""{page_budget_note(len(pages))}

{_analysis_date_note(cls_r, today)}

CLASSIFICATION (stage 1):
  fund_name       : {cls_r.get('fund_name')}
  manager_name    : {cls_r.get('manager_name')}
  aif_category    : {cls_r.get('aif_category')} ({cls_r.get('aif_category_confidence')})
  structure       : {cls_r.get('structure')}
  strategy        : {cls_r.get('strategy')}
  sebi_registration: {cls_r.get('sebi_registration') or 'null — no registration NUMBER found in the document'}
  document_date   : {cls_r.get('document_date')}

EXTRACTED FACTS (stage 2). Each line is value, page, and confidence. `null (not
found in document)` means the extraction stage searched and did not find it —
that is a positive finding of absence, not a gap in the extraction:

{_render_extraction(ext_r)}

{_render_diligence(dil)}

WHAT UPSTREAM STAGES COULD NOT DETERMINE:
{unresolved_block}

CRITERIA TO EVALUATE ({len(criteria_set.active_criteria)} of them, every one
requiring an entry in `findings`):

{json.dumps(criteria_set.as_prompt_payload(), indent=2, ensure_ascii=False)}

FULL DOCUMENT TEXT follows. The extracted facts above are a summary; where a
criterion asks about something the extraction did not cover, or where you need
to confirm an absence, read the pages directly. Quote from this text.

{render_pages_for_prompt(pages)}"""


def _run_pass(
    ctx,
    pass_name: str,
    standard: str,
    prompt: str,
    pages: list[str],
    budget,
    model: str | None,
) -> tuple[dict[str, dict], list[str]]:
    """One independent evaluation pass over the full criteria set.

    Returns findings keyed by criterion code, plus the pass's unresolved list.
    """
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        grounding=GROUNDING_RULES,
        standard=standard,
        page_count=len(pages),
        unresolved=UNRESOLVED_RULE,
    )

    ctx.stage_progress("scoring", f"{pass_name} pass …")
    result = run_claude(
        prompt,
        stage="scoring",
        system_prompt=system_prompt,
        json_schema=_finding_schema(pass_name),
        model=model,
        budget=budget,
        ctx=ctx,
    )
    # PRD §3 telemetry. Scoring makes TWO logical model calls — lenient and
    # strict — and each is recorded separately, so `model_calls` reads 2 for a
    # clean scoring stage. That is the point of the field: it distinguishes one
    # expensive call from several, which are different problems.
    ctx.stage_telemetry("scoring").record_call(result)
    if result.used_fallback:
        ctx.warn(
            f"scoring {pass_name} pass used the text-mode fallback; schema "
            "conformance was not enforced by the runtime",
            {"stage": "scoring", "pass": pass_name},
        )

    payload = result.structured
    if not isinstance(payload, dict) or "findings" not in payload:
        raise StageFailureError(
            f"stage 'scoring' ({pass_name} pass): model returned no usable findings array"
        )
    unresolved = payload.get("unresolved")
    if unresolved is None:
        raise StageFailureError(
            f"stage 'scoring' ({pass_name} pass): model omitted the mandatory "
            "'unresolved' array"
        )

    by_code: dict[str, dict] = {}
    for finding in payload["findings"]:
        if not isinstance(finding, dict):
            continue
        code = finding.get("criterion_code")
        if not code:
            continue
        if code in by_code:
            ctx.warn(
                f"scoring {pass_name} pass returned criterion {code} more than once; "
                "keeping the first verdict",
                {"criterion_code": code, "pass": pass_name},
            )
            continue
        by_code[code] = finding

    ctx.stage_progress(
        "scoring",
        f"{pass_name} pass: {len(by_code)} criteria evaluated, "
        f"{sum(1 for f in by_code.values() if f.get('fired'))} fired "
        f"(${result.cost_usd:.3f})",
    )
    return by_code, list(unresolved), result.cost_usd


def _normalise_ws(s: str) -> str:
    return " ".join(s.split()).lower()


def _verify_evidence_quotes(ctx, findings: list[dict], pages: list[str]) -> tuple[int, int]:
    """Check every evidence quote against the page it cites.

    Same mechanism as classification and extraction: whitespace-normalised
    comparison, a recorded verdict on every citation, and a warning rather than a
    hard failure on mismatch. Evidence that fails verification is downgraded and
    marked, never silently presented as verified.

    An evidence item that cites a page outside the document is treated more
    severely — that is fabricated provenance rather than a layout artifact, so it
    is dropped from the evidence array entirely.
    """
    checked = verified = 0

    for finding in findings:
        code = finding.get("criterion_code", "?")
        kept: list[dict] = []
        for item in finding.get("evidence") or []:
            if not isinstance(item, dict):
                continue
            page, quote = item.get("page"), (item.get("quote") or "")
            tier, in_range = verify_against_pages(quote, page, pages)
            if not in_range:
                ctx.warn(
                    f"scoring: {code} cites page {page}, outside 1..{len(pages)}; "
                    "dropping the evidence item as fabricated provenance",
                    {"criterion_code": code, "page": page},
                )
                continue
            checked += 1
            item["quote_verified"] = tier != UNVERIFIED
            item["verification"] = tier
            if tier == UNVERIFIED:
                ctx.warn(
                    f"scoring: {code} evidence quote not found on cited page {page} "
                    "(neither contiguously nor as an in-order column splice)",
                    {"criterion_code": code, "page": page, "quote": quote[:200]},
                )
            else:
                verified += 1
            kept.append(item)
        finding["evidence"] = kept

    return checked, verified


def _reconcile(
    ctx,
    criteria_set: CriteriaSet,
    lenient: dict[str, dict],
    strict: dict[str, dict],
) -> list[dict]:
    """Merge the two passes into one finding per criterion.

    The reconciliation rule, in order:

    1. If either pass says the check could not be performed (`evaluable: false`),
       the criterion is `unevaluated`. For a VETO criterion this becomes
       `veto_unevaluated` — the third state that stops an unperformed check being
       read as a clean result.
    2. If the two passes agree on `fired`, that is the verdict. Confidence is the
       lower of the two: agreement under both standards is strong, but the engine
       should not claim more confidence than its least confident reading.
    3. If they disagree, the criterion is `contested`. BOTH readings are recorded
       in full and the headline `fired` takes the STRICT verdict, because the
       strict pass is the one whose standard of proof an IC would apply. The
       contested flag is what carries the disagreement forward; the memo surfaces
       it in section 9 rather than presenting the strict verdict as settled.
    """
    findings: list[dict] = []

    for crit in criteria_set.active_criteria:
        code = crit.criterion_code
        l = lenient.get(code)
        s = strict.get(code)

        if l is None and s is None:
            ctx.warn(
                f"scoring: criterion {code} was returned by neither pass; recorded "
                "as unevaluated rather than assumed clean",
                {"criterion_code": code},
            )
            findings.append(_unevaluated_finding(crit, "neither evaluation pass returned a verdict"))
            continue

        # A criterion returned by only one pass cannot be reconciled. Treating the
        # single verdict as settled would present a one-pass result as though it
        # had survived both standards.
        if l is None or s is None:
            missing = "lenient" if l is None else "strict"
            present = s if l is None else l
            ctx.warn(
                f"scoring: criterion {code} was returned only by the "
                f"{'strict' if l is None else 'lenient'} pass; recording as contested "
                f"because the {missing} reading is unknown",
                {"criterion_code": code},
            )
            merged = _base_finding(crit, present)
            merged.update(
                {
                    "contested": True,
                    "contested_reason": f"the {missing} pass returned no verdict for this criterion",
                    "lenient": _reading(l),
                    "strict": _reading(s),
                    "confidence": "low",
                }
            )
            findings.append(merged)
            continue

        l_evaluable = l.get("evaluable", True)
        s_evaluable = s.get("evaluable", True)

        if not l_evaluable or not s_evaluable:
            reason = (
                (s.get("reasoning") if not s_evaluable else l.get("reasoning"))
                or "the check could not be performed"
            )
            merged = _unevaluated_finding(crit, reason)
            merged["lenient"] = _reading(l)
            merged["strict"] = _reading(s)
            findings.append(merged)
            continue

        l_fired = bool(l.get("fired"))
        s_fired = bool(s.get("fired"))
        agree = l_fired == s_fired

        # Prefer whichever pass actually fired as the source of evidence text: a
        # not-fired finding rarely carries useful evidence, and on agreement-on-
        # false either is equally empty.
        primary = s if s_fired else (l if l_fired else s)
        merged = _base_finding(crit, primary)

        if agree:
            merged["fired"] = s_fired
            merged["contested"] = False
            merged["status"] = "fired" if s_fired else "not_fired"
            merged["confidence"] = _lower_confidence(
                l.get("confidence"), s.get("confidence")
            )
        else:
            merged["fired"] = s_fired
            merged["contested"] = True
            merged["status"] = "contested"
            merged["contested_reason"] = (
                f"the lenient reading {'fires' if l_fired else 'does not fire'} this "
                f"criterion while the strict reading {'fires' if s_fired else 'does not fire'} "
                "it. Both readings are recorded below; the disagreement is not resolved "
                "by the engine."
            )
            # A contested finding is by construction not high-confidence. The two
            # standards disagreeing IS the uncertainty, whatever either pass
            # claimed about its own certainty.
            merged["confidence"] = "low"
            # Evidence for a contested finding must carry both sides, otherwise
            # the memo can only show the strict reading's support.
            merged["evidence"] = _merge_evidence(l, s)

        merged["lenient"] = _reading(l)
        merged["strict"] = _reading(s)
        findings.append(merged)

    return findings


def _base_finding(crit, source: dict) -> dict:
    return {
        "criterion_code": crit.criterion_code,
        "criterion_name": crit.name,
        "tier": crit.tier,
        "category": crit.category,
        "severity": crit.severity,
        "weight": crit.weight,
        "fired": bool(source.get("fired")),
        "status": "fired" if source.get("fired") else "not_fired",
        "contested": False,
        "confidence": source.get("confidence") or "low",
        "evidence": list(source.get("evidence") or []),
        "absence_evidence": source.get("absence_evidence"),
        "reasoning": source.get("reasoning") or "",
        # Fall back to the criterion's authored remediation_prompt. The rule
        # author wrote what to ask; a model-generated ask is a paraphrase of it
        # at best.
        "remediation": source.get("remediation") or crit.remediation_prompt or None,
    }


def _unevaluated_finding(crit, reason: str) -> dict:
    """The third state. `fired` is null, not false.

    Using false here would be the exact conflation the PRD forbids: a consumer
    filtering on `fired == false` would sweep up checks that were never
    performed and present them alongside genuinely clean results.
    """
    return {
        "criterion_code": crit.criterion_code,
        "criterion_name": crit.name,
        "tier": crit.tier,
        "category": crit.category,
        "severity": crit.severity,
        "weight": crit.weight,
        "fired": None,
        "status": "veto_unevaluated" if crit.is_veto else "unevaluated",
        "contested": False,
        "confidence": "low",
        "evidence": [],
        "absence_evidence": None,
        "reasoning": reason,
        "remediation": crit.remediation_prompt or None,
        "unevaluated_reason": reason,
    }


def _reading(pass_result: dict | None) -> dict | None:
    """Preserve one pass's verdict verbatim inside the merged finding."""
    if pass_result is None:
        return None
    return {
        "fired": pass_result.get("fired"),
        "evaluable": pass_result.get("evaluable", True),
        "confidence": pass_result.get("confidence"),
        "reasoning": pass_result.get("reasoning"),
        "evidence": list(pass_result.get("evidence") or []),
        "absence_evidence": pass_result.get("absence_evidence"),
    }


def _merge_evidence(l: dict, s: dict) -> list[dict]:
    """Union of both passes' evidence, de-duplicated on (page, quote)."""
    seen: set[tuple] = set()
    out: list[dict] = []
    for item in list(l.get("evidence") or []) + list(s.get("evidence") or []):
        if not isinstance(item, dict):
            continue
        key = (item.get("page"), _normalise_ws(item.get("quote") or ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _lower_confidence(a: str | None, b: str | None) -> str:
    ranked = [c for c in (a, b) if c in CONFIDENCE_ORDER]
    if not ranked:
        return "low"
    return min(ranked, key=lambda c: CONFIDENCE_ORDER[c])


def _repair_absence_evidence(ctx, findings: list[dict]) -> None:
    """Invariant 6.3 pre-check with an honest failure mode.

    A fired finding with no evidence and no absence_evidence would be rejected by
    `validate_finding_evidence` and fail the run. That is the correct behaviour
    for a malformed artifact, but it is a poor outcome when the cause is a model
    that fired a legitimate absence-based criterion and simply did not fill the
    field.

    So rather than fail the whole run or silently synthesise a plausible-sounding
    search description, the finding is DOWNGRADED to unevaluated with an explicit
    reason. The engine never asserts a search it cannot show was performed.
    """
    for f in findings:
        if not f.get("fired"):
            continue
        has_evidence = bool(f.get("evidence"))
        has_absence = bool((f.get("absence_evidence") or "").strip())
        if has_evidence or has_absence:
            continue
        ctx.warn(
            f"scoring: {f['criterion_code']} fired with neither page evidence nor "
            "absence_evidence. Downgraded to unevaluated — the engine will not "
            "assert an absence it cannot show was searched for.",
            {"criterion_code": f["criterion_code"]},
        )
        f["fired"] = None
        f["status"] = "veto_unevaluated" if f.get("tier") == "VETO" else "unevaluated"
        f["unevaluated_reason"] = (
            "the criterion was reported as fired but carried neither page-level "
            "evidence nor a statement of what was searched; the engine will not "
            "assert an unfalsifiable absence"
        )
        f["reasoning"] = f.get("reasoning") or f["unevaluated_reason"]


def _blocker_for_causes(causes: list[dict]) -> str | None:
    """The blocker class of the check that blocked a criterion.

    Looked up from diligence's declared per-check table rather than inferred from
    the reason prose. Diligence established these causes empirically, so reading
    them back is recording a measured fact; pattern-matching the sentence would
    be re-deriving it badly.
    """
    from .diligence import CHECK_TO_BLOCKER

    for c in causes:
        entry = CHECK_TO_BLOCKER.get(c.get("check", ""))
        if entry:
            return entry[0]
    return None


def _owner_for_causes(causes: list[dict]) -> str:
    from .diligence import CHECK_TO_BLOCKER

    for c in causes:
        entry = CHECK_TO_BLOCKER.get(c.get("check", ""))
        if entry:
            return entry[1]
    return "manual_analyst_check"


def _causes_for_criterion(code: str, dil: dict | None) -> list[dict]:
    """The unavailable diligence checks that block a given criterion."""
    if not dil:
        return []
    from .diligence import CHECK_TO_CRITERIA

    return [
        c
        for c in ((dil.get("result") or {}).get("checks") or [])
        if c.get("outcome") == "unavailable"
        and code in CHECK_TO_CRITERIA.get(c.get("check", ""), [])
    ]


def _blocker_for_criterion(code: str, dil: dict | None) -> str | None:
    return _blocker_for_causes(_causes_for_criterion(code, dil))


def _owner_for_criterion(code: str, dil: dict | None) -> str:
    return _owner_for_causes(_causes_for_criterion(code, dil))


def _enforce_blocked_criteria(ctx, findings: list[dict], dil: dict | None) -> list[dict]:
    """Deterministically force criteria whose external check was `unavailable`
    into the unevaluated state, whatever the model concluded.

    THIS IS THE LOAD-BEARING IMPLEMENTATION OF THE UNREACHABLE-SOURCE POLICY, and
    it exists because leaving the judgement to the model demonstrably fails.

    MEASURED on the reference run: the diligence stage correctly recorded
    `sebi_registration_active` as `unavailable` (geo-fence, evidence in the
    artifact), and the strict pass then fired CR-0001 — a VETO — at high
    confidence, reasoning that the registration was "unverified from both
    directions". That reasoning is locally sensible and globally wrong: it
    converts an unreachable regulator into a terminal adverse finding, which is
    exactly what PRD §5 stage 3 forbids. The run exited 11 on a fund whose
    registration status is simply unknown.

    A prompt instruction alone cannot be relied on to prevent this — the model
    followed a plausible chain of reasoning to get there. So the rule is enforced
    in code, after the fact, where it is deterministic: if the check a criterion
    depends on could not be performed, the criterion is unevaluated. Full stop.
    The model's reading is preserved inside the finding for inspection, but it
    does not decide the outcome.
    """
    if not dil:
        return []
    blocked = set((dil.get("result") or {}).get("criteria_blocked_by_unavailable_source") or [])
    if not blocked:
        return []

    checks = (dil.get("result") or {}).get("checks") or []
    notes: list[dict] = []

    for f in findings:
        code = f["criterion_code"]
        if code not in blocked:
            continue

        # Which unavailable check blocked it, and why — carried into the finding
        # so section 11 can state the cause rather than just the effect.
        from .diligence import CHECK_TO_CRITERIA

        causes = [
            c
            for c in checks
            if c.get("outcome") == "unavailable"
            and code in CHECK_TO_CRITERIA.get(c.get("check", ""), [])
        ]
        cause_text = "; ".join(
            f"{c['check']} [{c['source']}]: {c.get('reason', 'no reason recorded')}"
            for c in causes
        ) or "the external check this criterion depends on was unavailable"

        was_fired = f.get("fired")
        reason = (
            f"The external check this criterion depends on could not be performed, "
            f"so the criterion cannot be evaluated either way. {cause_text}"
        )

        if was_fired:
            note = (
                f"{code} was reported as fired but depends on an external source that "
                "was unavailable; forced to unevaluated. An unreachable source is "
                "never an adverse finding."
            )
            # EXTERNALLY_BLOCKED, necessarily: the whole point of this branch is
            # that a check could not be performed. Routing it any other way would
            # invite an analyst to answer a question that has no answer available.
            notes.append(
                make_entry(
                    field_path=code,
                    kind="EXTERNALLY_BLOCKED",
                    stage_origin="scoring",
                    account=f"{note} {cause_text}",
                    blocker_class=_blocker_for_causes(causes),
                    unblock_owner=_owner_for_causes(causes),
                    criterion_codes=[code],
                )
            )
            ctx.warn(f"scoring: {note}", {"criterion_code": code})

        f["fired"] = None
        f["status"] = "veto_unevaluated" if f.get("tier") == "VETO" else "unevaluated"
        f["contested"] = False
        f["confidence"] = "low"
        f["unevaluated_reason"] = reason
        f["model_reading_before_policy"] = {
            "fired": was_fired,
            "reasoning": f.get("reasoning"),
        }
        f["reasoning"] = reason

    return notes


def _check_exclusive_pairs(ctx, findings: list[dict]) -> list[str]:
    """Flag inverse criteria that both fired.

    Recorded as an unresolved item rather than resolved, on the same principle as
    contested findings: the engine reports the contradiction and lets a human
    settle it. Silently dropping one would hide a real signal that the criteria
    set or the evidence is being read inconsistently.
    """
    pairs = (("CR-0015", "CR-0033"), ("CR-0011", "CR-0031"))
    by_code = {f["criterion_code"]: f for f in findings}
    notes: list[dict] = []
    for a, b in pairs:
        fa, fb = by_code.get(a), by_code.get(b)
        if fa and fb and fa.get("fired") and fb.get("fired"):
            note = (
                f"{a} and {b} both fired, but they are inverse criteria and cannot "
                "both hold on the same facts. Both findings are retained for human "
                "review rather than one being silently dropped."
            )
            # A human settles this, and no document or infrastructure change is
            # needed to do so — the contradiction is visible in findings already
            # in hand. That makes it ANALYST_ANSWERABLE.
            notes.append(
                make_entry(
                    field_path=f"{a}+{b}",
                    kind="ANALYST_ANSWERABLE",
                    stage_origin="scoring",
                    account=note,
                    criterion_codes=[a, b],
                )
            )
            ctx.warn(f"scoring: {note}", {"criteria": [a, b]})
            for f in (fa, fb):
                f["contested"] = True
                f["status"] = "contested"
                f["contested_reason"] = (
                    f.get("contested_reason") or ""
                ) + (" " if f.get("contested_reason") else "") + note
    return notes


def _summarise(findings: list[dict]) -> dict:
    """Weighted tally plus a recommendation gate.

    The recommendation is a DECISION GATE, not investment advice (PRD §1): pursue
    / hold / pass, mirroring how a real IC memo requests an interview rather than
    a commitment. It is computed deterministically here so that invariant §6.2
    has a fixed target to compare the memo against — a model-generated
    recommendation could not be checked for contradiction against itself.
    """
    fired = [f for f in findings if f.get("fired")]
    veto_fired = [f for f in fired if f["tier"] == "VETO"]
    veto_unevaluated = [f for f in findings if f.get("status") == "veto_unevaluated"]
    red_fired = [f for f in fired if f["tier"] == "RED_FLAG"]
    green_fired = [f for f in fired if f["tier"] == "GREEN_FLAG"]
    contested = [f for f in findings if f.get("contested")]
    unevaluated = [f for f in findings if f.get("fired") is None]

    sev_weight = {"LOW": 1.0, "MEDIUM": 2.0, "HIGH": 3.0, "CRITICAL": 5.0}

    # A finding's contribution is severity_multiplier * author_weight. Publish it
    # on the finding itself: without this, a card reads `weight: 1.0` while the
    # scorecard totals 11.0 from three of them, and the two numbers cannot be
    # reconciled by anyone reading the memo. The multiplier is a real part of the
    # scoring model, so it must be visible where the score is shown — an IC that
    # cannot reproduce the arithmetic is right to distrust it.
    for f in findings:
        mult = sev_weight.get(f.get("severity"), 1.0)
        f["severity_multiplier"] = mult
        f["author_weight"] = f.get("weight", 1.0)
        f["effective_weight"] = round(mult * f.get("weight", 1.0), 2)
        # Only a fired finding contributes to the score.
        f["score_contribution"] = f["effective_weight"] if f.get("fired") else 0.0

    red_score = sum(f["effective_weight"] for f in red_fired)
    green_score = sum(f["effective_weight"] for f in green_fired)

    if veto_fired:
        recommendation = "pass"
        basis = (
            f"{len(veto_fired)} veto criterion/criteria fired: "
            + ", ".join(f["criterion_code"] for f in veto_fired)
        )
    elif red_score >= HOLD_RED_THRESHOLD and red_score > green_score * HOLD_RATIO:
        recommendation = "hold"
        margin = red_score - HOLD_RED_THRESHOLD
        basis = (
            f"red-flag weight {red_score:.1f} materially exceeds green-flag weight "
            f"{green_score:.1f}; the open questions should be answered before proceeding"
        )
        if margin <= 2.0:
            basis += (
                f" — NOTE: this clears the hold threshold ({HOLD_RED_THRESHOLD}) by only "
                f"{margin:.1f}. A single contested finding resolving the other way would "
                f"change the recommendation"
            )
    elif red_fired:
        recommendation = "pursue_with_questions"
        basis = (
            f"{len(red_fired)} red flag(s) fired against {len(green_fired)} green "
            f"flag(s); proceed to manager interview with the listed asks"
        )
    else:
        recommendation = "pursue"
        basis = f"no red flags fired; {len(green_fired)} green flag(s) support proceeding"

    if veto_unevaluated and recommendation != "pass":
        basis += (
            f". NOTE: {len(veto_unevaluated)} veto criterion/criteria could not be "
            "evaluated, so this recommendation is made without them."
        )

    return {
        "recommendation": recommendation,
        "recommendation_basis": basis,
        "veto_fired": [f["criterion_code"] for f in veto_fired],
        "veto_unevaluated": [f["criterion_code"] for f in veto_unevaluated],
        "red_flags_fired": [f["criterion_code"] for f in red_fired],
        "green_flags_fired": [f["criterion_code"] for f in green_fired],
        "contested": [f["criterion_code"] for f in contested],
        "unevaluated": [f["criterion_code"] for f in unevaluated],
        "red_flag_weight": round(red_score, 2),
        "green_flag_weight": round(green_score, 2),
        "criteria_evaluated": len(findings),
        # How the two weights above were arrived at. Published so a reader can
        # reproduce the scorecard from the findings without knowing the internal
        # severity table — the arithmetic behind a recommendation should never be
        # something an IC has to take on trust.
        "scoring_model": {
            "formula": "score_contribution = severity_multiplier * author_weight, summed over fired findings",
            "severity_multipliers": sev_weight,
            "red_contributions": [
                {"criterion_code": f["criterion_code"], "severity": f["severity"],
                 "author_weight": f["author_weight"], "contribution": f["effective_weight"]}
                for f in red_fired
            ],
            "green_contributions": [
                {"criterion_code": f["criterion_code"], "severity": f["severity"],
                 "author_weight": f["author_weight"], "contribution": f["effective_weight"]}
                for f in green_fired
            ],
        },
    }


# --- Recommendation thresholds -------------------------------------------------
#
# [NEEDS REVIEW — PLACEHOLDER VALUES, never approved by a stakeholder]
#
# These decide what a memo recommends. They were chosen to produce sensible
# output on the reference deck and have no other justification. They are the
# most consequential unreviewed numbers in the engine: the severity table and
# per-criterion weights only feed a total, but these turn that total into the
# sentence an Investment Committee reads first.
#
# HOLD_RED_THRESHOLD = 9.0 is exactly three HIGH findings (3.0 each). That is a
# defensible story but it is a story told after the fact, not a derivation.
#
# Known fragility, measured on the reference run: red weight is 11.0, of which
# the CONTESTED CR-0014 contributes 2.0. If that contest resolves the other way
# the total is 9.0 — landing exactly ON the threshold. The recommendation is
# stable but with zero margin, which is why `_summarise` now states the margin
# in the basis whenever it is thin.
#
# An institution tuning these should treat them as house policy, the same as the
# criteria themselves. They belong in the criteria set, not hardcoded here.
# [NEEDS REVIEW — should thresholds move into set.yaml so they are versioned and
#  frozen alongside the rules they operate on? Today a threshold change silently
#  reinterprets every past score, which is exactly what criteria-set versioning
#  exists to prevent.]
HOLD_RED_THRESHOLD = 9.0
HOLD_RATIO = 2.0

VALID_RECOMMENDATIONS = ("pass", "hold", "pursue_with_questions", "pursue")


def run_scoring(ctx, pages: list[str], budget, model: str | None, today: date | None = None) -> dict:
    """Stage 4. Returns the written envelope.

    Raises VetoError (exit 11) after writing the scoring artifact when a veto
    criterion fires at high confidence — the artifact is written FIRST so that a
    vetoed run still has a scorecard on disk for the memo stage to render.
    """
    from ..errors import VetoError

    stage = "scoring"
    inputs = assert_inputs_present(ctx.out_dir, stage)  # PRD §6.1
    ctx.stage_started(stage)

    today = today or date.today()
    criteria_set: CriteriaSet = ctx.criteria_set
    cls, ext = inputs["classification"], inputs["extraction"]
    dil = inputs.get("diligence")

    prompt = _build_prompt(criteria_set, cls, ext, dil, pages, today)

    # The two passes are independent invocations over an identical prompt with
    # different standards. Neither sees the other's output — see module docstring
    # for why a combined call is not equivalent.
    lenient, l_unresolved, l_cost = _run_pass(
        ctx, "lenient", LENIENT_STANDARD, prompt, pages, budget, model
    )
    strict, s_unresolved, s_cost = _run_pass(
        ctx, "strict", STRICT_STANDARD, prompt, pages, budget, model
    )

    findings = _reconcile(ctx, criteria_set, lenient, strict)

    checked, verified = _verify_evidence_quotes(ctx, findings, pages)
    # The grounding metric (PRD §3), per stage.
    ctx.stage_telemetry(stage).record_quotes(verified, checked)
    if checked:
        ctx.stage_progress(
            stage,
            f"evidence verification: {verified}/{checked} quotes matched their cited page",
        )

    _repair_absence_evidence(ctx, findings)

    # Order matters: the unreachable-source policy is applied BEFORE the summary
    # and before the veto check, so a criterion blocked by an unavailable source
    # can never reach the veto-halt path. Applying it afterwards would let the
    # run exit 11 on a check that was never performed.
    blocked_notes = _enforce_blocked_criteria(ctx, findings, dil)
    pair_notes = _check_exclusive_pairs(ctx, findings)

    summary = _summarise(findings)

    # Model-supplied entries from both passes, deduplicated on field_path+account
    # rather than on object identity — two passes routinely report the same gap.
    model_entries = enforce_kind_safety(
        [coerce_entry(u, "scoring") for u in (l_unresolved + s_unresolved)], "scoring"
    )
    unresolved: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for e in model_entries + blocked_notes + pair_notes:
        key = (e.get("field_path", ""), (e.get("account") or "")[:160])
        if key in seen:
            continue
        seen.add(key)
        unresolved.append(e)

    for f in findings:
        if f.get("fired") is None:
            # An unevaluated criterion is unevaluated because its check could not
            # be performed — that is the only path to `fired is None` after
            # `_enforce_blocked_criteria`. EXTERNALLY_BLOCKED, and the blocker is
            # inherited from the diligence check that caused it.
            unresolved.append(
                make_entry(
                    field_path=f["criterion_code"],
                    kind="EXTERNALLY_BLOCKED",
                    stage_origin="scoring",
                    account=(
                        f"{f['criterion_name']} could not be evaluated: "
                        f"{f.get('unevaluated_reason') or f.get('reasoning')}"
                    ),
                    blocker_class=_blocker_for_criterion(f["criterion_code"], dil),
                    unblock_owner=_owner_for_criterion(f["criterion_code"], dil),
                    criterion_codes=[f["criterion_code"]],
                )
            )
    for f in findings:
        if f.get("contested"):
            # A human resolves a contested finding by reading both readings and
            # the evidence already attached to them. No new document is required
            # to make the call, though one may be required to make it confidently
            # — that is stated in the account rather than by routing it as a
            # document request.
            unresolved.append(
                make_entry(
                    field_path=f["criterion_code"],
                    kind="ANALYST_ANSWERABLE",
                    stage_origin="scoring",
                    account=(
                        f"{f['criterion_name']} is contested between the lenient and "
                        f"strict passes: {f.get('contested_reason')}"
                    ),
                    criterion_codes=[f["criterion_code"]],
                )
            )

    veto_halt = [
        f
        for f in findings
        if f["tier"] == "VETO"
        and f.get("fired")
        and CONFIDENCE_ORDER.get(f.get("confidence"), 0)
        >= CONFIDENCE_ORDER[VETO_HALT_CONFIDENCE]
    ]

    result = {
        **summary,
        "vetoed": bool(veto_halt),
        "findings": findings,
        "criteria_set": {
            "set_code": criteria_set.set_code,
            "version": criteria_set.version,
            "content_hash": criteria_set.content_hash,
        },
        "analysis_date": today.isoformat(),
        "evaluation": {
            "mode": "dual_pass",
            "passes": ["lenient", "strict"],
            "lenient_fired": sorted(c for c, f in lenient.items() if f.get("fired")),
            "strict_fired": sorted(c for c, f in strict.items() if f.get("fired")),
            "agreement_rate": round(
                sum(
                    1
                    for f in findings
                    if not f.get("contested") and f.get("fired") is not None
                )
                / max(1, len(findings)),
                3,
            ),
        },
    }

    envelope = build_envelope(
        stage,
        result,
        unresolved,
        citations=_citations_from(findings),
        inputs_hash=inputs_hash_of(inputs),
    )
    # write_artifact runs validate_finding_evidence — invariant 6.3 — before the
    # artifact reaches disk.
    path = write_artifact(ctx.out_dir, stage, envelope)
    ctx.stage_completed(stage, path.name, l_cost + s_cost)

    ctx.stage_progress(
        stage,
        f"recommendation: {summary['recommendation']} — "
        f"{len(summary['red_flags_fired'])} red, {len(summary['green_flags_fired'])} green, "
        f"{len(summary['contested'])} contested, {len(summary['unevaluated'])} unevaluated",
    )

    if veto_halt:
        # The artifact is already on disk. The memo stage can still render it in
        # veto form; the exception carries the halt to the CLI, which decides
        # whether to generate the memo before exiting 11.
        raise VetoError(
            "veto criterion fired at high confidence: "
            + ", ".join(f"{f['criterion_code']} ({f['criterion_name']})" for f in veto_halt),
            {"veto": [f["criterion_code"] for f in veto_halt], "scoring_written": True},
        )

    return envelope


def _citations_from(findings: list[dict]) -> list[dict]:
    """Envelope citations derived from finding evidence, not generated separately."""
    out: list[dict] = []
    for f in findings:
        for item in f.get("evidence") or []:
            if isinstance(item, dict) and item.get("page") and item.get("quote"):
                out.append(
                    {
                        "claim": f"{f['criterion_code']} — {f['criterion_name']}",
                        "page": item["page"],
                        "quote": item["quote"],
                        "quote_verified": item.get("quote_verified"),
                    }
                )
    return out
