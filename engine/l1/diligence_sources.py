"""External source adapters for stage 3 diligence.

Every adapter here returns one of exactly three outcomes — `passed`, `failed`,
`unavailable` — and NOTHING may collapse the third into the first. That rule is
the entire safety property of this module: a diligence tool that reports "no
adverse findings" when it actually failed to reach the regulator is worse than
one that reports nothing at all.

The reachability facts below were established empirically in
`30-analysis/india-regulatory-data-sources.md`, against the real test case
(Neo Asset Management Private Limited). They are not assumptions:

  SEBI (www.sebi.gov.in)  WORKS over plain HTTP. It is NOT geo-fenced — an
                          earlier verdict in this module said so and was WRONG.
                          The actual behaviour: SEBI sits behind Cloudflare,
                          which returns HTTP 530 to a default `curl` user-agent
                          and HTTP 200 to a browser one. Ordinary bot filtering
                          at the HTTP layer, not a network block below it. The
                          old diagnosis ("TCP connects then dies after the TLS
                          Client Hello, therefore below HTTP, therefore a
                          browser cannot help") mistook that rejection for a
                          layer-4 block and hard-coded `unavailable` into two
                          VETO criteria that then never ran.

                          Both registers are server-side rendered Struts pages —
                          no JS, no CAPTCHA, no login. They need a session
                          cookie and a form token from a seed GET, then a POST.
                          robots.txt disallows only /js, /css and their Hindi
                          equivalents; both paths used here are permitted.

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

import html
import http.cookiejar
import re
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# The single place outbound request headers are defined. Centralised because
# getting this wrong is not a cosmetic failure: SEBI's Cloudflare edge returns
# HTTP 530 to a default `curl`/urllib user-agent and HTTP 200 to a browser one,
# and an earlier revision of this module read that 530 as proof of a geo-fence
# and disabled two VETO criteria on the strength of it. A UA alone is sometimes
# not enough — some edges also want a real Accept and Accept-Language — so all
# three travel together and every adapter uses them.
BROWSER_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}

DEFAULT_TIMEOUT_S = 20

# Politeness delay between successive requests to the same government host. A
# register is not a load test; the AIF search is two requests per lookup.
POLITE_DELAY_S = 1.0

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
    req = urllib.request.Request(url, headers=dict(BROWSER_HEADERS))
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
# SEBI — reachable, server-side rendered, and actually checked
# ---------------------------------------------------------------------------
#
# Both SEBI registers are Struts applications behind Cloudflare. The access
# pattern is the same for each and is the reason these adapters are more than a
# `http_get`:
#
#   1. GET the seed page with browser headers. This sets a JSESSIONID cookie and
#      returns an `org.apache.struts.taglib.html.TOKEN` hidden field.
#   2. POST the search with that cookie AND that token.
#
# Omitting either yields a ~21KB page with no results and no error — which looks
# exactly like a legitimate empty result. That is the same class of trap as the
# IFSCA empty table, so `_sebi_parse_state` below distinguishes the three cases
# explicitly (`results` / `empty` / `unparseable`) and only `empty` is ever
# allowed to become a negative finding.

SEBI_BASE = "https://www.sebi.gov.in"
SEBI_INTERMEDIARY_ACTION = f"{SEBI_BASE}/sebiweb/other/OtherAction.do"
SEBI_HOME_ACTION = f"{SEBI_BASE}/sebiweb/home/HomeAction.do"

# VERIFIED from the live "Recognised Intermediaries" dropdown: intmId 16 is
# "Registered Alternative Investment Funds" (1,991 entries as at Jul 20, 2026).
SEBI_AIF_INTM_ID = "16"
SEBI_AIF_URL = f"{SEBI_INTERMEDIARY_ACTION}?doRecognisedFpi=yes&intmId={SEBI_AIF_INTM_ID}"

# VERIFIED from the Enforcement section's sub-section dropdown: sid=2 is
# Enforcement and ssid=9 is "Orders" (adjudication, settlement, WTM orders).
SEBI_ORDERS_SID = "2"
SEBI_ORDERS_SSID = "9"
SEBI_ORDERS_URL = (
    f"{SEBI_HOME_ACTION}?doListing=yes&sid={SEBI_ORDERS_SID}&ssid={SEBI_ORDERS_SSID}&smid=0"
)

_STRUTS_TOKEN_RE = re.compile(
    r'name="org\.apache\.struts\.taglib\.html\.TOKEN"\s+value="([^"]+)"'
)
_PAGINATION_RE = re.compile(r"(\d+)\s+to\s+(\d+)\s+of\s+(\d+)\s+records", re.I)
_NO_RECORDS_RE = re.compile(r"No\s+record\(s\)\s+available", re.I)


def _sebi_session_post(
    seed_url: str, action_url: str, fields: dict, timeout: int = DEFAULT_TIMEOUT_S
) -> tuple[int | None, str, str | None]:
    """Seed a SEBI session, then POST a search. Returns (status, body, error).

    The seed GET is not optional politeness — it is where both the session cookie
    and the CSRF-ish Struts token come from, and a POST without them silently
    returns an empty result page rather than an error.
    """
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

    try:
        seed_req = urllib.request.Request(seed_url, headers=dict(BROWSER_HEADERS))
        with opener.open(seed_req, timeout=timeout) as resp:
            seed_body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, "", f"HTTP {exc.code} on seed request"
    except (urllib.error.URLError, socket.timeout, ssl.SSLError, OSError) as exc:
        return None, "", f"{type(exc).__name__}: {getattr(exc, 'reason', exc)}"

    token_match = _STRUTS_TOKEN_RE.search(seed_body)
    if not token_match:
        # Not fatal — recorded so the caller can explain a subsequent empty page
        # as a probable session failure rather than a real negative.
        token = ""
    else:
        token = token_match.group(1)

    payload = dict(fields)
    payload["org.apache.struts.taglib.html.TOKEN"] = token

    time.sleep(POLITE_DELAY_S)

    headers = dict(BROWSER_HEADERS)
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    headers["Referer"] = seed_url
    data = urllib.parse.urlencode(payload).encode()

    try:
        post_req = urllib.request.Request(action_url, data=data, headers=headers)
        with opener.open(post_req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace"), None
    except urllib.error.HTTPError as exc:
        return exc.code, "", f"HTTP {exc.code} on search POST"
    except (urllib.error.URLError, socket.timeout, ssl.SSLError, OSError) as exc:
        return None, "", f"{type(exc).__name__}: {getattr(exc, 'reason', exc)}"


def _sebi_parse_state(body: str) -> tuple[str, int]:
    """Classify a SEBI result page: ('results', n) | ('empty', 0) | ('unparseable', 0).

    The three-way split is the safety property. A page that is merely missing its
    pagination marker is NOT the same as a page that says "No record(s)
    available", and only the latter licenses a negative finding. A session or
    token failure produces the former, and calling it "not registered" would be a
    confident false negative about a VETO criterion.
    """
    pagination = _PAGINATION_RE.search(body)
    if pagination:
        return "results", int(pagination.group(3))
    if _NO_RECORDS_RE.search(body):
        return "empty", 0
    return "unparseable", 0


def _sebi_parse_intermediary_cards(body: str) -> list[dict]:
    """Parse the AIF register's card layout into dicts.

    The register renders each entity as a stack of title/value divs rather than a
    table, so a <tr>-based parser reads zero rows off a page that is full of data.
    """
    records: list[dict] = []
    for block in re.findall(
        r'(?is)<div class="card-table-left[^"]*">(.*?)</div>\s*</div>\s*</div>', body
    ):
        record: dict = {}
        for title, value in re.findall(
            r'(?is)<div class="title"><span>(.*?)</span></div>'
            r'<div class="value[^"]*"><span>(.*?)</span>',
            block,
        ):
            key = html.unescape(re.sub(r"<[^>]*>", "", title)).strip()
            val = html.unescape(re.sub(r"<[^>]*>", "", value)).strip()
            if key:
                record[key] = val
        if record.get("Name"):
            records.append(record)
    return records


def sebi_registration_lookup(
    manager_name: str, registration: str | None, timeout: int = DEFAULT_TIMEOUT_S
) -> CheckResult:
    """SEBI AIF register lookup — a real query against the live register.

    WHAT THIS CHECK CAN AND CANNOT ESTABLISH, because CR-0001 is a VETO and the
    distinction decides whether a veto is honest:

    SEBI registers the ALTERNATIVE INVESTMENT FUND — which in the Indian
    structure is a TRUST — and not the manager company, and not the individual
    scheme. VERIFIED on the reference case: searching the register for "Neo"
    returns seven trusts including `Neo Alternatives Investment Trust`
    (IN/AIF3/21-22/1001) and `Neo Credit Alternatives Investment Trust`
    (IN/AIF2/22-23/1042), all carrying @neoassetmanagement.com contacts. But
    searching "Neo Infra" or "Infra Income" returns a genuine "No record(s)
    available", because `Neo Infra Income Opportunities Fund II` is a SCHEME of a
    registered trust, not itself a registered entity.

    So an absent scheme name is NOT evidence of an unregistered fund, and this
    adapter must never report it as one. The search is therefore run on the
    manager's distinctive leading token, matches are returned as supporting
    evidence, and the outcome is `passed` when a plausibly-related registered
    trust is found — never `failed` merely because an exact string was absent.
    A true `failed` here would require a positive finding of non-registration,
    which this register cannot express.
    """
    needle = _sebi_search_term(manager_name)
    fields = {
        "doRecognisedFpi": "yes",
        "intmId": SEBI_AIF_INTM_ID,
        "name": needle,
        "regNo": "",
        "contPer": "",
        "email": "",
        "location": "",
        "curr_alp": "",
        "nextValue": "1",
    }
    status, body, err = _sebi_session_post(
        SEBI_AIF_URL, SEBI_INTERMEDIARY_ACTION, fields, timeout=timeout
    )

    base_data = {
        "manager_name": manager_name,
        "stated_registration": registration,
        "search_term": needle,
        "register": "SEBI Registered Alternative Investment Funds (intmId=16)",
    }

    if status is None or status >= 400:
        return CheckResult(
            check="sebi_registration_active",
            source="SEBI AIF register",
            outcome=UNAVAILABLE,
            reason=(
                f"The SEBI AIF register did not return a usable response "
                f"({err or f'HTTP {status}'}). SEBI is normally reachable with browser "
                "headers, so this is a transient failure or an edge rejection rather "
                "than a structural block — retry before treating it as meaningful."
            ),
            url=SEBI_AIF_URL,
            detail=f"No registration lookup completed for {manager_name!r}.",
            data={**base_data, "http_status": status},
        )

    state, total = _sebi_parse_state(body)

    if state == "unparseable":
        return CheckResult(
            check="sebi_registration_active",
            source="SEBI AIF register",
            outcome=UNAVAILABLE,
            reason=(
                "The SEBI AIF register returned HTTP 200 but the response carried "
                "neither a pagination marker nor a 'No record(s) available' notice. "
                "VERIFIED failure mode: a POST made without a valid JSESSIONID and "
                "Struts token returns exactly this page. It is INDISTINGUISHABLE from "
                "an empty result and is therefore explicitly NOT reported as one — "
                "reporting it as 'not registered' would veto a fund on a search that "
                "never ran."
            ),
            url=SEBI_AIF_URL,
            detail=f"Registration status of {manager_name!r} not determined.",
            data={**base_data, "http_status": status, "response_bytes": len(body)},
        )

    records = _sebi_parse_intermediary_cards(body)

    if state == "empty" or not records:
        return CheckResult(
            check="sebi_registration_active",
            source="SEBI AIF register",
            outcome=UNAVAILABLE,
            reason=(
                f"The SEBI AIF register was searched successfully for {needle!r} and "
                "returned no matching registered fund. This is NOT recorded as a "
                "failed check, because SEBI registers the AIF trust rather than the "
                "manager company or the individual scheme: a manager whose trusts are "
                "named differently from the manager will legitimately return nothing. "
                "Confirming registration requires the trust name or the registration "
                "number from the fund documents, which was not available here."
            ),
            url=SEBI_AIF_URL,
            detail=(
                f"No SEBI-registered AIF matched {needle!r}. Absence of a match is not "
                "evidence of non-registration — resolve by searching the register for "
                "the trust name stated in the PPM."
            ),
            data={**base_data, "matches": 0, "register_total_reported": total},
        )

    matches = [
        {
            "name": r.get("Name"),
            "registration_no": r.get("Registration No."),
            "validity": r.get("Validity"),
            "email": r.get("E-mail"),
            "address": r.get("Address"),
            "contact_person": r.get("Contact Person"),
        }
        for r in records
    ]
    stated_seen = bool(
        registration and any((m["registration_no"] or "") == registration.strip() for m in matches)
    )

    return CheckResult(
        check="sebi_registration_active",
        source="SEBI AIF register",
        outcome=PASSED,
        url=SEBI_AIF_URL,
        detail=(
            f"SEBI AIF register searched for {needle!r}: {len(matches)} registered "
            f"AIF(s) found — "
            + "; ".join(
                f"{m['name']} ({m['registration_no']}, valid {m['validity']})"
                for m in matches[:6]
            )
            + ". NOTE: SEBI registers the AIF trust, not the manager company and not "
            "the individual scheme, so these are the manager's registered vehicles "
            "rather than a registration of the manager itself."
            + (
                f" The registration number {registration!r} stated in the document WAS "
                "matched in the register."
                if stated_seen
                else (
                    f" The registration number {registration!r} stated in the document "
                    "was NOT among these entries — verify which trust the scheme sits under."
                    if registration
                    else " The document itself states no registration number."
                )
            )
        ),
        data={
            **base_data,
            "matches": len(matches),
            "records": matches,
            "stated_registration_matched": stated_seen,
        },
    )


def sebi_enforcement_lookup(manager_name: str, timeout: int = DEFAULT_TIMEOUT_S) -> CheckResult:
    """SEBI enforcement / adjudication order search — full-text, and real.

    VERIFIED that this search actually discriminates, which matters more than
    that it returns 200: the same query path returns 56 orders for "Reliance" and
    a genuine "No record(s) available" for "Neo Asset Management". Without that
    positive control, a clean result would be indistinguishable from a search
    field that silently ignores its input.

    A clean result is reported as `passed` and is a real finding. An unparseable
    page is `unavailable`, never clean — a false "no enforcement action found" is
    materially worse than an honest "not checked".
    """
    needle = manager_name.strip()
    fields = {
        "doListing": "yes",
        "sid": SEBI_ORDERS_SID,
        "ssid": SEBI_ORDERS_SSID,
        "smid": "0",
        "ssidhidden": SEBI_ORDERS_SSID,
        "smidhidden": "0",
        "sectName": "Enforcement",
        "search": needle,
        "fromDate": "",
        "toDate": "",
        "deptId": "",
        "nextValue": "1",
    }
    status, body, err = _sebi_session_post(
        SEBI_ORDERS_URL, SEBI_HOME_ACTION, fields, timeout=timeout
    )

    base_data = {
        "manager_name": manager_name,
        "search_term": needle,
        "register": "SEBI Enforcement > Orders (sid=2, ssid=9)",
    }

    if status is None or status >= 400:
        return CheckResult(
            check="sebi_enforcement_actions",
            source="SEBI enforcement / adjudication orders",
            outcome=UNAVAILABLE,
            reason=(
                f"The SEBI enforcement order search did not return a usable response "
                f"({err or f'HTTP {status}'}). Retry before drawing any conclusion; this "
                "is NOT a finding of no adverse history."
            ),
            url=SEBI_ORDERS_URL,
            detail=f"No enforcement search completed for {manager_name!r}.",
            data={**base_data, "http_status": status},
        )

    state, total = _sebi_parse_state(body)

    if state == "unparseable":
        return CheckResult(
            check="sebi_enforcement_actions",
            source="SEBI enforcement / adjudication orders",
            outcome=UNAVAILABLE,
            reason=(
                "The SEBI enforcement order search returned HTTP 200 but carried "
                "neither a pagination marker nor a 'No record(s) available' notice — "
                "the signature of a POST that lost its session or Struts token. "
                "Reported as unavailable rather than clean: an unrun search must never "
                "be rendered as an absence of enforcement history."
            ),
            url=SEBI_ORDERS_URL,
            detail=f"Enforcement history of {manager_name!r} not determined.",
            data={**base_data, "http_status": status, "response_bytes": len(body)},
        )

    if state == "empty":
        return CheckResult(
            check="sebi_enforcement_actions",
            source="SEBI enforcement / adjudication orders",
            outcome=PASSED,
            url=SEBI_ORDERS_URL,
            detail=(
                f"SEBI enforcement orders searched for {needle!r}: no matching order "
                "found. The search was verified to discriminate (the same query path "
                "returns 56 orders for a known-litigated name), so this is a genuine "
                "clean result rather than an unrun search. Scope caveat: this covers "
                "the Enforcement > Orders section only — it does not cover recovery "
                "proceedings, unserved summons, or actions by other regulators."
            ),
            data={**base_data, "orders_found": 0},
        )

    titles = []
    for row in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", body):
        cells = [
            re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", c)).strip()
            for c in re.findall(r"(?is)<td[^>]*>(.*?)</td>", row)
        ]
        if len(cells) >= 2 and cells[1]:
            titles.append({"date": cells[0], "title": cells[1][:200]})

    return CheckResult(
        check="sebi_enforcement_actions",
        source="SEBI enforcement / adjudication orders",
        outcome=FAILED,
        url=SEBI_ORDERS_URL,
        detail=(
            f"SEBI enforcement order search for {needle!r} returned {total} matching "
            f"order(s). These are keyword matches on the order listing and REQUIRE "
            "manual review — a match may name an unrelated party, a different entity "
            "with a similar name, or a complainant rather than a respondent. "
            + "; ".join(f"[{t['date']}] {t['title']}" for t in titles[:5])
        ),
        data={**base_data, "orders_found": total, "sample_orders": titles[:25]},
    )


def _sebi_search_term(manager_name: str) -> str:
    """Reduce a manager name to the distinctive token(s) SEBI's register indexes.

    The register does substring matching (VERIFIED: 'Alternatives Investment
    Trust' returns four trusts across three managers), but it matches literally —
    so a full legal name like 'Neo Asset Management Private Limited' matches
    nothing, while 'Neo' returns the manager's seven registered trusts. Legal-form
    and generic asset-management words are therefore dropped, and the leading
    distinctive token is what gets searched.
    """
    cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", manager_name).strip()
    drop = {
        "private", "limited", "pvt", "ltd", "llp", "inc", "corp",
        "asset", "management", "managers", "advisors", "advisers",
        "capital", "investment", "investments", "partners", "fund", "funds",
        "trustee", "trustees", "company", "co",
    }
    tokens = [t for t in cleaned.split() if t]
    core = [t for t in tokens if t.lower() not in drop]
    return (core[0] if core else (tokens[0] if tokens else manager_name)).strip()


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

    UPDATED 2026-07-21: this adapter now WORKS over plain HTTP. Re-tested after
    the browser headers were centralised, it returned the correct CIN
    (U67100MH2021PTC371799) on 3 of 3 consecutive attempts. Note that raw `curl`
    with the same UA still gets HTTP 403, so the UA alone is not what satisfies
    ZaubaCorp's edge — the full urllib header set does. That is precisely why the
    headers live in one constant rather than being spelled out per adapter.

    The `unavailable` branch below is retained and still correct: this is an
    anti-bot edge that can start returning 403 again at any time, and a 403 is a
    source we did not reach, not a company that does not exist.
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
