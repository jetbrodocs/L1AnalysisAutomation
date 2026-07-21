"""External source adapters for stage 3 diligence.

Every adapter here returns one of exactly three outcomes — `passed`, `failed`,
`unavailable` — and NOTHING may collapse the third into the first. That rule is
the entire safety property of this module: a diligence tool that reports "no
adverse findings" when it actually failed to reach the regulator is worse than
one that reports nothing at all.

The reachability facts below were established empirically in
`30-analysis/india-regulatory-data-sources.md`, against the real test case
(Neo Asset Management Private Limited). They are not assumptions:

  SEBI (www.sebi.gov.in)  UNREACHABLE from this egress. TCP connects on :443,
                          then the connection dies after the TLS Client Hello.
                          A real Chrome browser fails identically to curl, which
                          places the block BELOW the HTTP layer — a geo-fence or
                          source-IP WAF. No amount of headless-browser work
                          fixes it. Every SEBI check therefore records
                          `unavailable` with the geo-fence as the stated reason.

  MCA (mca.gov.in)        Company master data now sits behind a login, and DIN
                          status behind a canvas CAPTCHA. Both are deliberate
                          access controls on a government system. Not automated.

  ZaubaCorp               WORKS. robots.txt is permissive (`Disallow: /*.pdf$`,
                          else `Allow: *`). Returns CIN, status, incorporation
                          date, RoC, and the director/DIN table. This is the
                          backbone of what diligence can actually verify.

  Tofler                  NOT USED. Its robots.txt explicitly disallows
                          `/companyinfo/*`, `/basicsearch`, `/findcompany*` and
                          `/cnamesearch*` — precisely the paths a scraper needs.
                          Automated harvesting would contravene its stated crawl
                          policy. There is no code path here that fetches it.

  IFSCA                   WORKS, BROWSER-ONLY. A plain HTTP GET returns the
                          table shell with zero populated rows, which is
                          indistinguishable from a legitimate "no match". That
                          failure mode is guarded explicitly in
                          `ifsca_directory_lookup` — an empty table over plain
                          HTTP is reported `unavailable`, never "not found".
"""

from __future__ import annotations

import re
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

DEFAULT_TIMEOUT_S = 20

PASSED = "passed"
FAILED = "failed"
UNAVAILABLE = "unavailable"

OUTCOMES = (PASSED, FAILED, UNAVAILABLE)


@dataclass
class CheckResult:
    """One diligence check. `outcome` is the load-bearing field.

    `unavailable` carries a mandatory `reason`. A check that could not be
    performed without a stated reason is indistinguishable from laziness, and the
    memo's section 11 has nothing to print.
    """

    check: str
    source: str
    outcome: str
    detail: str = ""
    reason: str | None = None
    url: str | None = None
    retrieved_at: str | None = None
    data: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.outcome not in OUTCOMES:
            raise ValueError(
                f"outcome {self.outcome!r} is not one of {OUTCOMES}; there is no "
                "fourth state, and 'unavailable' must never be rendered as 'passed'"
            )
        if self.outcome == UNAVAILABLE and not self.reason:
            raise ValueError(
                f"check {self.check!r} is unavailable but states no reason. An "
                "unperformed check without a reason cannot be reported honestly."
            )
        if self.retrieved_at is None:
            self.retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def as_dict(self) -> dict:
        return {
            "check": self.check,
            "source": self.source,
            "outcome": self.outcome,
            "detail": self.detail,
            "reason": self.reason,
            "url": self.url,
            "retrieved_at": self.retrieved_at,
            "data": self.data,
        }


# ---------------------------------------------------------------------------
# HTTP primitive
# ---------------------------------------------------------------------------


def http_get(url: str, timeout: int = DEFAULT_TIMEOUT_S) -> tuple[int | None, str, str | None]:
    """Plain HTTP GET. Returns (status, body, error).

    Deliberately minimal and dependency-free. Anything needing a real browser is
    marked browser-only rather than being attempted here with a heavier client —
    see `ifsca_directory_lookup` for why a partial success is more dangerous than
    a failure.
    """
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body, None
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return exc.code, body, f"HTTP {exc.code}"
    except (urllib.error.URLError, socket.timeout, ssl.SSLError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        return None, "", f"{type(exc).__name__}: {reason}"


# ---------------------------------------------------------------------------
# SEBI — structurally unavailable from this egress
# ---------------------------------------------------------------------------

SEBI_GEOFENCE_REASON = (
    "www.sebi.gov.in is unreachable from this network egress. VERIFIED "
    "empirically: DNS resolves (202.191.143.30 / .158) and TCP connect to :443 "
    "succeeds, but the connection is dropped after the TLS Client Hello. A real "
    "Chrome browser fails identically to curl, which places the block below the "
    "HTTP layer — a geo-fence or source-IP WAF rather than an outage or bot "
    "detection. A headless browser does not help. Re-run this check from an "
    "Indian IP to obtain a real result."
)


def sebi_registration_lookup(manager_name: str, registration: str | None) -> CheckResult:
    """SEBI AIF register lookup. Always `unavailable` from this egress.

    This function deliberately does NOT attempt the request. The block is at the
    TLS layer and takes 25s to time out; attempting it per-run would add a minute
    of latency to produce a result already known with certainty. The empirical
    evidence for that certainty is in the reason string, so the artifact carries
    its own justification rather than an unexplained "unavailable".

    If SEBI later becomes reachable (different egress, or a mirror), this is the
    one function to change — the check name and shape stay the same, so nothing
    downstream needs to know.
    """
    return CheckResult(
        check="sebi_registration_active",
        source="SEBI intermediary register",
        outcome=UNAVAILABLE,
        reason=SEBI_GEOFENCE_REASON,
        url="https://www.sebi.gov.in/",
        detail=(
            f"Could not verify whether {manager_name!r} holds an active SEBI AIF "
            f"registration"
            + (
                f", nor whether the number {registration!r} stated in the document is valid."
                if registration
                else ". The document itself states no registration number."
            )
        ),
        data={"manager_name": manager_name, "stated_registration": registration},
    )


def sebi_enforcement_lookup(manager_name: str) -> CheckResult:
    """SEBI enforcement/adjudication order search. Unavailable, same cause.

    Worth stating plainly in the artifact: a false "no enforcement action found"
    is materially worse than an honest "not checked". This check exists so that
    the absence of an enforcement search is visible in the memo rather than
    inferred from silence.
    """
    return CheckResult(
        check="sebi_enforcement_actions",
        source="SEBI enforcement / adjudication orders",
        outcome=UNAVAILABLE,
        reason=SEBI_GEOFENCE_REASON,
        url="https://www.sebi.gov.in/enforcement.html",
        detail=(
            f"No search for enforcement, adjudication, or debarment proceedings "
            f"against {manager_name!r} was performed. This is NOT a finding of no "
            "adverse history — it is the absence of a search. Treat as an open item "
            "requiring manual check."
        ),
        data={"manager_name": manager_name},
    )


# ---------------------------------------------------------------------------
# MCA — access-controlled, routed to a licensed provider rather than defeated
# ---------------------------------------------------------------------------


def mca_master_data_lookup(manager_name: str) -> CheckResult:
    """MCA21 company master data. Unavailable by policy, not by failure.

    VERIFIED: the no-login "View Company Master Data" service is retired; the V3
    replacement redirects to a login, and DIN status is behind a self-hosted
    canvas CAPTCHA. Both are intentional access controls on a government system.

    The engine does not attempt either. That is a decision, not a limitation:
    reverse-engineering a government portal's CAPTCHA is legal and reputational
    exposure disproportionate to a DIN status check, and it would be fragile.
    The correct resolution is a licensed provider (Probe42 or MCA's own bulk
    data product), which is a procurement task rather than a code one.
    """
    return CheckResult(
        check="mca_master_data",
        source="MCA21 V3 master data",
        outcome=UNAVAILABLE,
        reason=(
            "MCA company master data requires an authenticated MCA account "
            "(VERIFIED: /content/mca/global/en/mca/master-data/MDS.html redirects "
            "to fologin.html), and DIN status enquiry is gated by a self-hosted "
            "canvas CAPTCHA that appears on submit. Both are deliberate access "
            "controls on a government system; the engine does not attempt to "
            "circumvent them. Route through a licensed provider for authoritative "
            "MCA data."
        ),
        url="https://www.mca.gov.in/content/mca/global/en/mca/master-data/MDS.html",
        detail=(
            f"Authoritative MCA record for {manager_name!r} not retrieved. See the "
            "ZaubaCorp check for an aggregator-sourced record, which is indicative "
            "and dated but not authoritative."
        ),
        data={"manager_name": manager_name},
    )


# ---------------------------------------------------------------------------
# ZaubaCorp — the one source that actually works
# ---------------------------------------------------------------------------

_CIN_RE = re.compile(r"\b([UL]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6})\b")
_DIN_RE = re.compile(r"\b(\d{8})\b")


def _strip_tags(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    html = html.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", html).strip()


def _slugify_company(name: str) -> str:
    """ZaubaCorp's search path uses a hyphenated upper-case company name."""
    cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", name).strip()
    # Trailing legal-form words are frequently absent from the aggregator's
    # index entry, so the search is done on the distinctive leading tokens.
    tokens = [t for t in cleaned.split() if t]
    drop = {"private", "limited", "pvt", "ltd", "llp"}
    core = [t for t in tokens if t.lower() not in drop]
    return "-".join((core or tokens)).upper()


def zaubacorp_company_lookup(manager_name: str, timeout: int = DEFAULT_TIMEOUT_S) -> CheckResult:
    """Corporate identity via ZaubaCorp.

    robots.txt VERIFIED permissive for HTML paths. Even so, this is an
    aggregator: its data was VERIFIED stale on the test case (an older NIC
    segment in the CIN, and departed directors still listed as current). So the
    result is recorded as indicative, stamped with a retrieval time, and
    explicitly not treated as authoritative — that framing is carried into the
    artifact so the memo cannot present it as a registry confirmation.

    ALSO VERIFIED: plain curl gets HTTP 403 from ZaubaCorp; a real browser loads
    fine. So this adapter will usually return `unavailable` when run from a plain
    HTTP client, and that is the honest outcome — an anti-bot 403 is a source we
    did not reach, not a company that does not exist.
    """
    slug = _slugify_company(manager_name)
    url = f"https://www.zaubacorp.com/companysearchresults/{urllib.parse.quote(slug)}"
    status, body, err = http_get(url, timeout=timeout)

    if status is None or status >= 400:
        return CheckResult(
            check="corporate_identity",
            source="ZaubaCorp",
            outcome=UNAVAILABLE,
            reason=(
                f"ZaubaCorp did not return a usable response ({err or f'HTTP {status}'}). "
                "VERIFIED behaviour: ZaubaCorp returns HTTP 403 to plain HTTP clients "
                "and loads correctly only in a real browser, so this is anti-bot "
                "edge filtering rather than an absent record. A browser-driven "
                "fetch is required to complete this check."
            ),
            url=url,
            detail=f"No corporate record retrieved for {manager_name!r}.",
            data={"manager_name": manager_name, "http_status": status},
        )

    text = _strip_tags(body)
    if "0 records found" in text.lower() or "no records found" in text.lower():
        return CheckResult(
            check="corporate_identity",
            source="ZaubaCorp",
            outcome=FAILED,
            url=url,
            detail=(
                f"ZaubaCorp search for {manager_name!r} returned no matching company. "
                "The source was reached and the search executed, so this is a genuine "
                "negative rather than an unreachable source — but aggregator indexes "
                "are incomplete and this alone does not establish the entity does not exist."
            ),
            data={"manager_name": manager_name, "search_slug": slug},
        )

    cins = _CIN_RE.findall(body)
    if not cins:
        return CheckResult(
            check="corporate_identity",
            source="ZaubaCorp",
            outcome=UNAVAILABLE,
            reason=(
                "ZaubaCorp responded but the page contained no CIN in the expected "
                "format. The page structure may have changed, or the response may be "
                "an interstitial. Not treated as 'company not found', because a "
                "parse failure and an absent record are different things."
            ),
            url=url,
            detail=f"Response received ({len(body)} bytes) but no CIN parsed.",
            data={"manager_name": manager_name, "http_status": status},
        )

    return CheckResult(
        check="corporate_identity",
        source="ZaubaCorp",
        outcome=PASSED,
        url=url,
        detail=(
            f"Corporate record located for {manager_name!r}: CIN {cins[0]}. "
            "AGGREGATOR DATA — indicative, not authoritative. VERIFIED on the "
            "reference case that ZaubaCorp carries a stale snapshot (older NIC "
            "segment in the CIN, departed directors listed as current). Confirm "
            "against MCA before relying on it."
        ),
        data={
            "manager_name": manager_name,
            "cin": cins[0],
            "all_cins": sorted(set(cins)),
            "authoritative": False,
        },
    )


# ---------------------------------------------------------------------------
# IFSCA — works, but browser-only. The empty-table trap is guarded explicitly.
# ---------------------------------------------------------------------------

IFSCA_URL = "https://ifsca.gov.in/DirectoryList"


def ifsca_directory_lookup(manager_name: str, timeout: int = DEFAULT_TIMEOUT_S) -> CheckResult:
    """IFSCA GIFT City entity directory.

    THE TRAP THIS FUNCTION EXISTS TO AVOID: a plain HTTP GET to /DirectoryList
    returns HTTP 200 with the full table shell — headers, 12 `<tr>` elements —
    and ZERO populated data rows. In a real browser the rows populate. So the
    HTTP response looks like a successful query that found no match, and a naive
    adapter would report "entity not registered with IFSCA" on the strength of a
    page it never actually loaded.

    That is the single most dangerous failure mode in this module, because it
    produces a confident false negative rather than an obvious error. The guard
    is a row-count assertion: if the table is present but unpopulated, the result
    is `unavailable` with the reason stated, NEVER `passed` and never a negative
    finding.
    """
    status, body, err = http_get(IFSCA_URL, timeout=timeout)

    if status is None or status >= 400:
        return CheckResult(
            check="ifsca_gift_city_registration",
            source="IFSCA directory",
            outcome=UNAVAILABLE,
            reason=f"IFSCA directory unreachable ({err or f'HTTP {status}'}).",
            url=IFSCA_URL,
            detail=f"Could not determine whether {manager_name!r} is an IFSCA-registered entity.",
            data={"manager_name": manager_name},
        )

    # Count populated ENTITY rows. Counting any <tr> with non-empty <td> is not
    # sufficient, and getting this wrong is how the trap bites:
    #
    # VERIFIED against the live page — a plain GET returns 12 <tr>, of which two
    # are the entity table's <th> header row and TEN are a hidden per-entity
    # detail template whose left cell holds a static LABEL ("Registered Address",
    # "Validity From", "Email ID", …) and whose right cell is empty. A naive
    # "any non-empty <td>" test scores those ten as data and concludes the
    # directory was searched and the entity is absent. That is a confident false
    # negative produced from a page that was never actually loaded.
    #
    # So a row counts as an entity row only if it has >= 2 cells with non-empty
    # text AND its first cell is not one of the known template labels.
    rows = re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", body)
    template_labels = {
        "registered address",
        "date of registration / authorization / license",
        "registration / authorization no.",
        "validity from",
        "validity to",
        "name of contact person",
        "contact number",
        "email id",
        "website",
        "remarks",
    }
    populated = 0
    for row in rows:
        cells = [_strip_tags(c).strip() for c in re.findall(r"(?is)<td[^>]*>(.*?)</td>", row)]
        filled = [c for c in cells if c]
        if len(filled) < 2:
            continue
        if cells and cells[0].strip().lower().rstrip(":") in template_labels:
            continue
        populated += 1

    if populated == 0:
        return CheckResult(
            check="ifsca_gift_city_registration",
            source="IFSCA directory",
            outcome=UNAVAILABLE,
            reason=(
                "The IFSCA directory returned HTTP 200 with the table shell but ZERO "
                "populated data rows. VERIFIED: the directory renders its rows "
                "client-side, so a plain HTTP fetch always yields an empty table. "
                "This is INDISTINGUISHABLE from a legitimate 'no match' and is "
                "therefore explicitly NOT reported as one. A browser-driven fetch "
                "is required to perform this check."
            ),
            url=IFSCA_URL,
            detail=(
                f"Could not determine whether {manager_name!r} appears in the IFSCA "
                "directory. Reported as unavailable rather than 'not registered' — "
                "an empty scrape is not a negative result."
            ),
            data={"manager_name": manager_name, "rows_seen": len(rows), "rows_populated": 0},
        )

    text = _strip_tags(body).lower()
    needle = _slugify_company(manager_name).replace("-", " ").lower()
    found = needle in text

    return CheckResult(
        check="ifsca_gift_city_registration",
        source="IFSCA directory",
        outcome=PASSED if found else FAILED,
        url=IFSCA_URL,
        detail=(
            f"{manager_name!r} {'appears' if found else 'does not appear'} in the "
            f"IFSCA directory ({populated} populated rows read). "
            + (
                ""
                if found
                else "Note: most SEBI-registered AIF managers are NOT GIFT City "
                "entities, so absence here is expected and is not adverse."
            )
        ),
        data={
            "manager_name": manager_name,
            "rows_populated": populated,
            "matched": found,
        },
    )


# ---------------------------------------------------------------------------
# Deterministic comparisons over already-retrieved data
# ---------------------------------------------------------------------------


def _normalise_address(addr: str) -> str:
    addr = addr.lower()
    addr = re.sub(r"[^a-z0-9 ]+", " ", addr)
    expansions = {
        r"\brd\b": "road", r"\bst\b": "street", r"\bmarg\b": "road",
        r"\bfl\b": "floor", r"\bflr\b": "floor", r"\bblg\b": "building",
        r"\bbldg\b": "building", r"\bopp\b": "opposite", r"\bnr\b": "near",
    }
    for pat, rep in expansions.items():
        addr = re.sub(pat, rep, addr)
    return " ".join(addr.split())


def address_match_check(stated: str | None, filed: str | None) -> CheckResult:
    """Registered address vs stated HQ. A deterministic string comparison.

    Not a model judgement (PRD §5 stage 3): the comparison is token overlap on
    normalised text, and the threshold is stated in the artifact so the verdict
    is reproducible.
    """
    if not stated or not filed:
        return CheckResult(
            check="registered_address_matches_hq",
            source="ZaubaCorp / document",
            outcome=UNAVAILABLE,
            reason=(
                "Comparison requires both a stated HQ address from the document and a "
                "filed registered address from a corporate register; "
                f"{'the document address' if not stated else 'the filed address'} was not obtained."
            ),
            detail="Address comparison not performed.",
            data={"stated": stated, "filed": filed},
        )

    a, b = set(_normalise_address(stated).split()), set(_normalise_address(filed).split())
    overlap = len(a & b) / max(1, min(len(a), len(b)))
    matched = overlap >= 0.6
    return CheckResult(
        check="registered_address_matches_hq",
        source="ZaubaCorp / document",
        outcome=PASSED if matched else FAILED,
        detail=(
            f"Normalised token overlap {overlap:.0%} against a 60% threshold. "
            f"Document HQ: {stated!r}. Filed registered address: {filed!r}."
        ),
        data={"stated": stated, "filed": filed, "overlap": round(overlap, 3), "threshold": 0.6},
    )


def key_person_match_check(
    document_names: list[str], filed_directors: list[str]
) -> CheckResult:
    """Named key persons vs director records. Deterministic name matching.

    A key person who is not a director is entirely normal — investment staff are
    rarely all on the board — so a non-match is NOT adverse on its own and the
    detail says so. What matters is that the comparison was performed and its
    basis is stated.
    """
    if not document_names:
        return CheckResult(
            check="key_persons_appear_in_filings",
            source="ZaubaCorp directors",
            outcome=UNAVAILABLE,
            reason="The document named no key persons to compare against filed records.",
            detail="Key-person comparison not performed.",
            data={},
        )
    if not filed_directors:
        return CheckResult(
            check="key_persons_appear_in_filings",
            source="ZaubaCorp directors",
            outcome=UNAVAILABLE,
            reason=(
                "No filed director list was retrieved, so no comparison could be made. "
                "This is not a finding that the named persons are absent from filings."
            ),
            detail="Key-person comparison not performed.",
            data={"document_names": document_names},
        )

    def norm(n: str) -> str:
        return " ".join(re.sub(r"[^a-z ]+", " ", n.lower()).split())

    filed = {norm(d) for d in filed_directors}
    matched = [n for n in document_names if norm(n) in filed]
    return CheckResult(
        check="key_persons_appear_in_filings",
        source="ZaubaCorp directors",
        outcome=PASSED if matched else FAILED,
        detail=(
            f"{len(matched)} of {len(document_names)} named key persons appear in the "
            f"filed director list. Matched: {matched or 'none'}. "
            "A key person who is not a director is ordinary — investment staff are "
            "seldom all board members — so a low match rate is not adverse in itself."
        ),
        data={
            "document_names": document_names,
            "filed_directors": filed_directors,
            "matched": matched,
        },
    )
