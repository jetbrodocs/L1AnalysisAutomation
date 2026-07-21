"""Structured `unresolved` entries (PRD §3, changed 2026-07-21).

Entries were originally free-text strings. That was insufficient: the evidence
loop (PRD 07) and the memo-reader screen route each open question by **kind**,
and each kind maps to a completely different UI affordance. Deriving that kind by
pattern-matching English prose is not a contract — it is a heuristic that breaks
silently the moment a stage rewords its output, and it breaks in the direction of
showing an analyst the wrong affordance.

So kind is now a declared field. `account` carries the prose that previously WAS
the entry, and that prose is still the most valuable part of the record: it is
the account of what was searched for, where, and what was found instead.
`field_path` is the stable identifier that survives rewording of the account.

THE CLASSIFICATION RULE IS SAFETY-FIRST AND ITS ORDERING IS DELIBERATE. A check
that could not be *performed* is EXTERNALLY_BLOCKED regardless of whether some
document might also contain the answer. When uncertain, choose blocked.

The asymmetry is the reason: inviting an analyst to answer an unanswerable
question wastes their time and erodes trust in every other prompt the system
makes. Under-prompting merely leaves a question unasked. Those costs are not
symmetric, so the tie-break is not neutral. This is the same principle as
`_enforce_blocked_criteria` in scoring — where a safety property must hold, the
code decides it, not a prompt and not a heuristic over prose.
"""

from __future__ import annotations

from .errors import InvariantViolation

KINDS = ("DOCUMENT_ANSWERABLE", "ANALYST_ANSWERABLE", "EXTERNALLY_BLOCKED")
TYPICAL_SOURCES = ("ppm", "audited_accounts", "ddq", "side_letter")
# Why a check could not be performed. The class names the REMEDY, which is the
# point: `paid_source` routes to procurement, `needs_browser` routes to an
# engineering capability, `login_required` and `captcha` route to a deliberate
# access control we will not defeat. Mislabelling a solvable engineering gap as
# a purchasing one is how it stays unsolved.
#
# `geo_fence` was removed 2026-07-21. It existed for exactly one case — SEBI —
# and that diagnosis was wrong: SEBI's Cloudflare rejects a default user-agent
# and returns HTTP 200 to a browser one. Keeping a class with no true instance
# invites its reuse for the next thing that merely looks like it.
BLOCKER_CLASSES = ("needs_browser", "login_required", "captcha", "paid_source")
UNBLOCK_OWNERS = ("infrastructure", "procurement", "manual_analyst_check")

# Human-readable labels, used by the memo and by `l1 inspect`. Defined once so
# the CLI and the memo cannot describe the same kind differently.
KIND_LABEL = {
    "DOCUMENT_ANSWERABLE": "Answerable from a document we do not have",
    "ANALYST_ANSWERABLE": "Answerable by an analyst",
    "EXTERNALLY_BLOCKED": "Blocked — the check could not be performed",
}

KIND_GUIDANCE = {
    "DOCUMENT_ANSWERABLE": (
        "Request the document named as the typical source. These are the questions "
        "a manager can close by sending a file."
    ),
    "ANALYST_ANSWERABLE": (
        "An analyst can resolve these with judgement or a manual check — no new "
        "document and no infrastructure change is required."
    ),
    "EXTERNALLY_BLOCKED": (
        "**Do not send these to the manager.** The check could not be performed at "
        "all, so no answer from the manager would resolve them. Each names the "
        "owner who can unblock it."
    ),
}

SOURCE_LABEL = {
    "ppm": "Private Placement Memorandum",
    "audited_accounts": "audited accounts",
    "ddq": "DDQ response",
    "side_letter": "side letter",
}

BLOCKER_LABEL = {
    "geo_fence": "geo-fence / source-IP block",
    "login_required": "authentication required",
    "captcha": "CAPTCHA",
    "paid_source": "paid source",
}

OWNER_LABEL = {
    "infrastructure": "Infrastructure",
    "procurement": "Procurement",
    "manual_analyst_check": "Analyst (manual check)",
}


# The JSON-schema fragment every stage embeds for its `unresolved` array. Defined
# once here so four stages cannot drift into four dialects of the same object.
#
# `additionalProperties: false` plus an explicit `required` list is load-bearing
# with this runtime: a nullable field that is merely *permitted* gets omitted,
# and a consumer then cannot distinguish "not applicable" from "the model forgot".
# Requiring all eight keys and allowing null forces the distinction to be stated.
UNRESOLVED_ITEM_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "field_path",
        "kind",
        "stage_origin",
        "account",
        "typical_source",
        "blocker_class",
        "unblock_owner",
        "criterion_codes",
    ],
    "properties": {
        "field_path": {
            "type": "string",
            "description": (
                "Stable dotted identifier of what could not be established, e.g. "
                "'team.key_person_clause' or 'economics.gp_commitment'. Use the "
                "path of the field in this stage's own result object where one "
                "exists. This must survive rewording of `account`."
            ),
        },
        "kind": {
            "type": "string",
            "enum": list(KINDS),
            "description": (
                "DOCUMENT_ANSWERABLE — a document we do not have (usually the PPM) "
                "would answer it. "
                "ANALYST_ANSWERABLE — an analyst can settle it with judgement or a "
                "manual check, needing no new document. "
                "EXTERNALLY_BLOCKED — a check could not be PERFORMED at all. "
                "SAFETY RULE: if a check could not be performed, the entry is "
                "EXTERNALLY_BLOCKED even if some document might also contain the "
                "answer. When uncertain between blocked and answerable, choose "
                "EXTERNALLY_BLOCKED — prompting an analyst to answer an "
                "unanswerable question wastes their time and erodes trust in every "
                "other prompt."
            ),
        },
        "stage_origin": {
            "type": "string",
            "description": "The stage that could not resolve this.",
        },
        "account": {
            "type": "string",
            "description": (
                "What you searched for, WHERE you looked, and what you found "
                "instead. This is the most valuable part of the entry — it records "
                "what has already been ruled out so the same search is not repeated "
                "by hand. Name the specific terms searched and the specific pages "
                "consulted. Do not compress this."
            ),
        },
        "typical_source": {
            "type": ["string", "null"],
            "enum": [*TYPICAL_SOURCES, None],
            "description": (
                "For DOCUMENT_ANSWERABLE only: which document class usually answers "
                "this. Null for every other kind."
            ),
        },
        "blocker_class": {
            "type": ["string", "null"],
            "enum": [*BLOCKER_CLASSES, None],
            "description": (
                "For EXTERNALLY_BLOCKED only: why the check could not be performed. "
                "Null for every other kind."
            ),
        },
        "unblock_owner": {
            "type": ["string", "null"],
            "enum": [*UNBLOCK_OWNERS, None],
            "description": (
                "For EXTERNALLY_BLOCKED only: who can resolve the blocker. Null for "
                "every other kind."
            ),
        },
        "criterion_codes": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Criterion codes this gap affected, e.g. ['CR-0012']. Empty array "
                "if none or not yet known."
            ),
        },
    },
}


UNRESOLVED_RULE = """
The `unresolved` array is MANDATORY and must be present even when empty. Populate
it with one OBJECT per thing you could not determine — not a string.

Every object needs all eight keys. Use null for the ones that do not apply to its
kind, never omit them.

  field_path      the dotted path of what could not be established
  kind            DOCUMENT_ANSWERABLE | ANALYST_ANSWERABLE | EXTERNALLY_BLOCKED
  stage_origin    this stage's name
  account         what you searched for, where you looked, what you found instead
  typical_source  DOCUMENT_ANSWERABLE only, else null
  blocker_class   EXTERNALLY_BLOCKED only, else null
  unblock_owner   EXTERNALLY_BLOCKED only, else null
  criterion_codes affected criterion codes, or []

`account` is the part that matters most. Name the exact terms you searched for
and the exact pages you consulted, and say what you found in their place. "Not
stated" is not an account; "searched pages 37 and 38 and the whole deck for
'sponsor commitment', 'GP commitment' and 'continuing interest'; page 38 gives
the fee schedule but no sponsor figure appears anywhere" is.

SAFETY RULE ON `kind`: if the reason you could not determine something is that a
CHECK COULD NOT BE PERFORMED, the kind is EXTERNALLY_BLOCKED — even if a document
might also contain the answer. When you are unsure between blocked and
answerable, choose EXTERNALLY_BLOCKED.

A stage that silently drops what it could not find is the exact failure this
field exists to prevent.
""".strip()


def make_entry(
    field_path: str,
    kind: str,
    stage_origin: str,
    account: str,
    *,
    typical_source: str | None = None,
    blocker_class: str | None = None,
    unblock_owner: str | None = None,
    criterion_codes: list[str] | None = None,
) -> dict:
    """Build one entry from code (the deterministic stages and backstops)."""
    return {
        "field_path": field_path,
        "kind": kind,
        "stage_origin": stage_origin,
        "account": account,
        "typical_source": typical_source,
        "blocker_class": blocker_class,
        "unblock_owner": unblock_owner,
        "criterion_codes": list(criterion_codes or []),
    }


def coerce_entry(raw, stage_origin: str) -> dict:
    """Normalise one model-returned entry into the contract shape.

    Tolerant of a model omitting a nullable key or returning a bare string,
    because the alternative is failing a whole run over a shape detail while
    holding a perfectly good search account. What it will NOT do is invent a
    `kind`: an unclassifiable entry is forced to EXTERNALLY_BLOCKED by
    `_enforce_kind_safety`, which is the safe direction, not the convenient one.
    """
    if isinstance(raw, str):
        # A bare string still carries the account, which is the valuable part.
        # Keep it rather than discard it; the safety default handles the kind.
        return make_entry(
            field_path=_leading_identifier(raw) or "unspecified",
            kind="EXTERNALLY_BLOCKED",
            stage_origin=stage_origin,
            account=raw,
        )
    if not isinstance(raw, dict):
        return make_entry(
            field_path="unspecified",
            kind="EXTERNALLY_BLOCKED",
            stage_origin=stage_origin,
            account=str(raw),
        )

    account = raw.get("account") or ""
    return make_entry(
        field_path=raw.get("field_path") or _leading_identifier(account) or "unspecified",
        kind=raw.get("kind") or "EXTERNALLY_BLOCKED",
        stage_origin=raw.get("stage_origin") or stage_origin,
        account=account,
        typical_source=raw.get("typical_source"),
        blocker_class=raw.get("blocker_class"),
        unblock_owner=raw.get("unblock_owner"),
        criterion_codes=raw.get("criterion_codes") or [],
    )


def _leading_identifier(text: str) -> str | None:
    """The `field_path`-ish head of a legacy string entry, before the em-dash."""
    if not text:
        return None
    for sep in (" — ", " – ", " - "):
        if sep in text:
            head = text.split(sep, 1)[0].strip()
            if head and len(head) <= 80:
                return head.split()[0].strip("[]()")
    return None


def enforce_kind_safety(entries: list[dict], stage_origin: str) -> list[dict]:
    """Force the safety-first classification rule in CODE, not in the prompt.

    Two corrections, both in the blocked direction only:

    1. An unknown or missing `kind` becomes EXTERNALLY_BLOCKED. A kind the code
       does not recognise cannot be routed, and the safe place to put an
       unroutable question is the list that says "do not ask the manager this".

    2. An entry whose account says a check could not be PERFORMED is forced to
       EXTERNALLY_BLOCKED whatever kind was declared. This is the same lesson as
       `_enforce_blocked_criteria` in scoring, where an explicit prompt rule
       measurably reduced but did NOT eliminate a model turning an unreachable
       source into an adverse finding. **Where a safety property must hold, a
       prompt is not a mechanism.** The prompt lowers the rate; only the code
       makes it invariant.

    Nothing is ever forced the other way — the function cannot make a blocked
    entry answerable, so it can only ever move entries toward the safe side.

    Fields that do not apply to the final kind are nulled, so a consumer reading
    `blocker_class` on a DOCUMENT_ANSWERABLE entry cannot find stale data.
    """
    out: list[dict] = []
    for entry in entries:
        e = dict(entry)
        account = (e.get("account") or "").lower()

        if e.get("kind") not in KINDS:
            e["kind"] = "EXTERNALLY_BLOCKED"
            e["_forced"] = "unrecognised kind"

        if e["kind"] != "EXTERNALLY_BLOCKED" and _reads_as_unperformed(account):
            e["kind"] = "EXTERNALLY_BLOCKED"
            e["_forced"] = "account describes a check that could not be performed"

        if e["kind"] == "EXTERNALLY_BLOCKED":
            e["typical_source"] = None
            if e.get("blocker_class") not in BLOCKER_CLASSES:
                e["blocker_class"] = None
            if e.get("unblock_owner") not in UNBLOCK_OWNERS:
                # An unattributed blocker is worse than useless — it reads as
                # nobody's problem. Default to the analyst, who at least sees it.
                e["unblock_owner"] = "manual_analyst_check"
        else:
            e["blocker_class"] = None
            e["unblock_owner"] = None
            if e["kind"] != "DOCUMENT_ANSWERABLE":
                e["typical_source"] = None
            elif e.get("typical_source") not in TYPICAL_SOURCES:
                e["typical_source"] = None

        e.setdefault("stage_origin", stage_origin)
        if not e.get("stage_origin"):
            e["stage_origin"] = stage_origin
        e["criterion_codes"] = list(e.get("criterion_codes") or [])
        out.append(e)
    return out


_UNPERFORMED_MARKERS = (
    "could not be checked",
    "not performed",
    "could not be performed",
    "unreachable",
    "geo-fence",
    "geofence",
    "captcha",
    "requires an authenticated",
    "requires a login",
    "login required",
    "could not be evaluated",
)


def _reads_as_unperformed(account_lower: str) -> bool:
    return any(marker in account_lower for marker in _UNPERFORMED_MARKERS)


def assert_entries_valid(entries, source: str = "<artifact>") -> None:
    """Validate the contract shape. Raises InvariantViolation (exit 20).

    Called from `write_artifact`, so a malformed entry never reaches disk where
    the next stage would consume it as valid — the same placement as §6.3.
    """
    if not isinstance(entries, list):
        raise InvariantViolation(
            "3-unresolved-malformed",
            f"{source}: 'unresolved' must be a list, got {type(entries).__name__}",
        )
    for i, e in enumerate(entries):
        where = f"{source}: unresolved[{i}]"
        if not isinstance(e, dict):
            raise InvariantViolation(
                "3-unresolved-malformed",
                f"{where} is a {type(e).__name__}, not an object. Entries are "
                "structured objects since PRD §3 changed on 2026-07-21; a bare "
                "string cannot be routed by kind.",
            )
        for key in ("field_path", "kind", "stage_origin", "account"):
            if not e.get(key):
                raise InvariantViolation(
                    "3-unresolved-malformed",
                    f"{where} has no {key!r}. All four of field_path, kind, "
                    "stage_origin and account are required on every entry.",
                    {"entry": e},
                )
        if e["kind"] not in KINDS:
            raise InvariantViolation(
                "3-unresolved-malformed",
                f"{where} has kind {e['kind']!r}, which is not one of {KINDS}.",
                {"entry": e},
            )
        if e["kind"] == "EXTERNALLY_BLOCKED":
            if e.get("typical_source") is not None:
                raise InvariantViolation(
                    "3-unresolved-malformed",
                    f"{where} is EXTERNALLY_BLOCKED but names a typical_source. A "
                    "blocked check is not answerable from a document; saying it is "
                    "would route it to the manager, which is the routing error this "
                    "contract exists to prevent.",
                    {"entry": e},
                )
            if not e.get("unblock_owner"):
                raise InvariantViolation(
                    "3-unresolved-malformed",
                    f"{where} is EXTERNALLY_BLOCKED with no unblock_owner. An "
                    "unattributed blocker reads as nobody's problem.",
                    {"entry": e},
                )
        else:
            for key in ("blocker_class", "unblock_owner"):
                if e.get(key) is not None:
                    raise InvariantViolation(
                        "3-unresolved-malformed",
                        f"{where} is {e['kind']} but sets {key}. That field applies "
                        "only to EXTERNALLY_BLOCKED entries.",
                        {"entry": e},
                    )


def group_by_kind(entries: list[dict]) -> dict[str, list[dict]]:
    """Entries grouped by kind, in the fixed order blocked-last.

    Blocked last is deliberate: the first two groups are actionable, and a reader
    working top-down hits the things they can do something about before the
    things they cannot.
    """
    order = ("DOCUMENT_ANSWERABLE", "ANALYST_ANSWERABLE", "EXTERNALLY_BLOCKED")
    grouped: dict[str, list[dict]] = {k: [] for k in order}
    for e in entries:
        grouped.setdefault(e.get("kind", "EXTERNALLY_BLOCKED"), []).append(e)
    return {k: v for k, v in grouped.items() if v}


def entry_text(entry: dict) -> str:
    """The searchable text of an entry — used by §11 completeness checks."""
    return f"{entry.get('field_path', '')} — {entry.get('account', '')}"
