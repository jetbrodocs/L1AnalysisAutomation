"""Stage 3 — Diligence (PRD §5 stage 3).

Verifies document claims against external sources. For India there is no single
equivalent of EDGAR, so this stage is a multi-source router rather than one
lookup.

**This stage is deterministic and makes no model calls.** Every check here is a
register lookup or a string/numeric comparison. PRD §5 stage 3 specifies
"deterministic comparisons — not model judgements", and a model asked to decide
whether an address matches would produce an unreproducible verdict where a token
overlap ratio produces a reproducible one. That also makes this the cheapest
stage in the pipeline: it costs nothing and cannot hallucinate.

**Expect this stage to be mostly `unavailable`, and read that as a correct
result rather than a broken one.** Established empirically in
`30-analysis/india-regulatory-data-sources.md`:

  - SEBI is geo-fenced from this egress at the TLS layer. The regulatory core of
    diligence — registration validity, intermediary status, enforcement history —
    is therefore unobtainable here. That is the honest state of the world, and
    the artifact says so with the evidence for it.
  - MCA is behind a login and a CAPTCHA, both deliberate access controls, which
    the engine does not attempt to circumvent.
  - ZaubaCorp works from a browser and 403s a plain HTTP client.
  - IFSCA works from a browser and silently returns an empty table over plain
    HTTP, which is the most dangerous failure in the set because it mimics a
    clean negative.

**The unreachable-source policy, decided in the PRD and implemented here: an
unreachable source NEVER fails the run — not even for a veto-tier criterion.**
Failing the whole run because one lookup timed out discards sixteen other
evaluated criteria, and an analyst is better served by a partial memo with a
clearly-marked hole than by no memo at all. The safety property that makes this
acceptable is that `unavailable` is never rendered as `passed` anywhere: scoring
converts an unavailable veto check into `veto_unevaluated`, and the memo carries
it into section 11.
"""

from __future__ import annotations

from ..unresolved import make_entry
from ..artifacts import (
    assert_inputs_present,
    build_envelope,
    inputs_hash_of,
    write_artifact,
)
from ..diligence_sources import (
    FAILED,
    PASSED,
    UNAVAILABLE,
    CheckResult,
    address_match_check,
    ifsca_directory_lookup,
    key_person_match_check,
    mca_master_data_lookup,
    sebi_enforcement_lookup,
    sebi_registration_lookup,
    zaubacorp_company_lookup,
)

# Which criteria each check informs. Used by scoring to decide that a criterion's
# underlying check could not be performed — the link between an `unavailable`
# source and a `veto_unevaluated` criterion.
# Why each source cannot be reached, and who can fix it. Declared per check
# rather than inferred from the reason prose: the engine ESTABLISHED these causes
# empirically (see the README's diligence table), so stating them is recording a
# measured fact, not classifying a string.
#
# Every one of these is `infrastructure` except the ones a person could do by
# hand. That distinction is the point of the field — "re-run from an Indian IP"
# and "someone opens a browser and looks" go to different owners, and an analyst
# should never be handed the first.
CHECK_TO_BLOCKER = {
    # VERIFIED: DNS resolves and TCP/443 connects, but the connection is dropped
    # after the TLS Client Hello. A real browser fails identically to curl, so the
    # block is below the HTTP layer. No amount of analyst effort resolves this.
    "sebi_registration_active": ("geo_fence", "infrastructure"),
    "sebi_enforcement_actions": ("geo_fence", "infrastructure"),
    # VERIFIED: master data redirects to a login; DIN enquiry is CAPTCHA-gated.
    # These are deliberate access controls on a government system — the route is
    # a licensed data provider, which is a purchasing decision.
    "mca_master_data": ("login_required", "procurement"),
    # VERIFIED: 403/timeout to plain HTTP; works in a real browser. A person can
    # do this by hand today, so it is the analyst's to unblock, not infra's.
    "corporate_identity": ("paid_source", "manual_analyst_check"),
    # VERIFIED: HTTP 200 with the table shell and zero populated rows, because the
    # directory renders client-side. Also browser-only.
    "ifsca_gift_city_registration": ("paid_source", "manual_analyst_check"),
    # These two are comparisons that depend on the corporate filing above, so they
    # inherit its blocker.
    "registered_address_matches_hq": ("paid_source", "manual_analyst_check"),
    "key_persons_appear_in_filings": ("paid_source", "manual_analyst_check"),
}

CHECK_TO_CRITERIA = {
    "sebi_registration_active": ["CR-0001"],
    "sebi_enforcement_actions": ["CR-0002"],
    "corporate_identity": [],
    "mca_master_data": [],
    "registered_address_matches_hq": [],
    "key_persons_appear_in_filings": [],
    "ifsca_gift_city_registration": [],
}


def _collect_key_person_names(ext_result: dict) -> list[str]:
    team = ext_result.get("team") or {}
    return [
        p.get("name")
        for p in (team.get("key_persons") or [])
        if isinstance(p, dict) and p.get("name")
    ]


def run_diligence(ctx, pages: list[str], budget, model: str | None, live: bool = True) -> dict:
    """Stage 3. `live=False` skips network calls and records every remote check
    as unavailable — used by fast tests so the suite neither hits the network nor
    depends on a registry being up.
    """
    stage = "diligence"
    inputs = assert_inputs_present(ctx.out_dir, stage)  # PRD §6.1
    ctx.stage_started(stage)

    cls = inputs["classification"]["result"]
    ext = inputs["extraction"]["result"]

    manager = cls.get("manager_name")
    stated_registration = cls.get("sebi_registration")

    checks: list[CheckResult] = []
    unresolved: list[dict] = []

    if not manager:
        unresolved.append(
            make_entry(
                field_path="manager_name",
                kind="EXTERNALLY_BLOCKED",
                stage_origin=stage,
                account=(
                    "Classification did not identify a manager name, so no external "
                    "register could be queried at all. Every external check is "
                    "unavailable for want of a search term — this is not a finding "
                    "about the manager, it is the absence of one."
                ),
                blocker_class="login_required",
                unblock_owner="manual_analyst_check",
            )
        )
        for name, source in (
            ("sebi_registration_active", "SEBI intermediary register"),
            ("sebi_enforcement_actions", "SEBI enforcement / adjudication orders"),
            ("corporate_identity", "ZaubaCorp"),
            ("ifsca_gift_city_registration", "IFSCA directory"),
        ):
            checks.append(
                CheckResult(
                    check=name,
                    source=source,
                    outcome=UNAVAILABLE,
                    reason="No manager name was identified, so no lookup key existed.",
                    detail="Check not performed.",
                )
            )
    else:
        # SEBI — known unavailable, recorded with the empirical evidence for why.
        checks.append(sebi_registration_lookup(manager, stated_registration))
        checks.append(sebi_enforcement_lookup(manager))

        # MCA — unavailable by policy (login + CAPTCHA are access controls).
        checks.append(mca_master_data_lookup(manager))

        if live:
            ctx.stage_progress(stage, f"querying corporate registers for {manager!r} …")
            checks.append(zaubacorp_company_lookup(manager))
            checks.append(ifsca_directory_lookup(manager))
        else:
            for name, source in (
                ("corporate_identity", "ZaubaCorp"),
                ("ifsca_gift_city_registration", "IFSCA directory"),
            ):
                checks.append(
                    CheckResult(
                        check=name,
                        source=source,
                        outcome=UNAVAILABLE,
                        reason="Live external lookups were disabled for this run.",
                        detail="Check not performed.",
                    )
                )

        # Deterministic comparisons over whatever the register lookups returned.
        corporate = next(
            (c for c in checks if c.check == "corporate_identity" and c.outcome == PASSED),
            None,
        )
        filed_address = (corporate.data.get("registered_address") if corporate else None)
        filed_directors = (corporate.data.get("directors") if corporate else None) or []

        checks.append(address_match_check(None, filed_address))
        checks.append(key_person_match_check(_collect_key_person_names(ext), filed_directors))

    # Every unavailable check becomes an unresolved entry. This is the mechanism
    # by which a source we could not reach reaches memo section 11 rather than
    # vanishing between stages.
    for c in checks:
        if c.outcome == UNAVAILABLE:
            blocker_class, unblock_owner = CHECK_TO_BLOCKER.get(
                c.check, (None, "manual_analyst_check")
            )
            unresolved.append(
                make_entry(
                    field_path=c.check,
                    # Every entry here is EXTERNALLY_BLOCKED by construction: this
                    # loop runs only over checks whose outcome is `unavailable`,
                    # which means the check was NOT PERFORMED. No document the
                    # manager could send would change that, so none of these may
                    # ever be routed as answerable.
                    kind="EXTERNALLY_BLOCKED",
                    stage_origin=stage,
                    account=f"[{c.source}] could not be checked: {c.reason}",
                    blocker_class=blocker_class,
                    unblock_owner=unblock_owner,
                    criterion_codes=CHECK_TO_CRITERIA.get(c.check, []),
                )
            )

    by_outcome = {o: [c.check for c in checks if c.outcome == o] for o in (PASSED, FAILED, UNAVAILABLE)}

    # Criteria whose underlying external check could not be performed. Scoring
    # reads this to mark them unevaluated rather than clean.
    blocked: list[str] = []
    for c in checks:
        if c.outcome == UNAVAILABLE:
            blocked.extend(CHECK_TO_CRITERIA.get(c.check, []))

    result = {
        "manager_name": manager,
        "checks": [c.as_dict() for c in checks],
        "summary": {
            "total": len(checks),
            "passed": len(by_outcome[PASSED]),
            "failed": len(by_outcome[FAILED]),
            "unavailable": len(by_outcome[UNAVAILABLE]),
        },
        "by_outcome": by_outcome,
        "criteria_blocked_by_unavailable_source": sorted(set(blocked)),
        "policy": (
            "An unreachable source never fails the run, including for veto-tier "
            "criteria (PRD §5 stage 3). `unavailable` is never rendered as `passed`: "
            "a criterion whose check is unavailable is reported as unevaluated in "
            "scoring, not as clean."
        ),
    }

    envelope = build_envelope(
        stage,
        result,
        unresolved,
        citations=[],  # external sources, not document pages — see `url` on each check
        inputs_hash=inputs_hash_of(inputs),
    )
    path = write_artifact(ctx.out_dir, stage, envelope)
    ctx.stage_completed(stage, path.name, 0.0)
    ctx.stage_progress(
        stage,
        f"{by_outcome[PASSED] and len(by_outcome[PASSED]) or 0} passed, "
        f"{len(by_outcome[FAILED])} failed, {len(by_outcome[UNAVAILABLE])} unavailable "
        f"(no model calls, $0.00)",
    )
    return envelope
