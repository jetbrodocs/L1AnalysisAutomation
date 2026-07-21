---
title: India Regulatory & Corporate Data Sources — Programmatic Access Assessment
status: draft
created: 2026-07-20
updated: 2026-07-21
tags:
  - analysis
  - diligence
  - aif
  - regulatory-data
  - sebi
  - mca
  - ifsca
  - data-sources
---

# India Regulatory & Corporate Data Sources — Programmatic Access Assessment

## Purpose

Establish empirically which Indian regulatory and corporate data sources can be programmatically accessed to verify claims in an AIF marketing document. Every verdict below is based on an actual fetch attempt, not on what a site claims to offer.

**Test case used throughout:** manager "Neo Asset Management Private Limited" (Mumbai), fund "Neo Infra Income Opportunities Fund II", SEBI Category II AIF.

## Evidence standard

Every claim is marked:

- **VERIFIED** — a request was actually issued and the response observed (status code, content, block page).
- **UNVERIFIED** — inferred, remembered, or read from a site's own description without confirming it end to end.

**A second verdict changed.** ZaubaCorp was recorded ACCESSIBLE-BROWSER on the assumption that plain HTTP always drew a 403. With the browser header set applied it now returns the correct CIN over plain HTTP on 3/3 attempts — no browser needed. IFSCA and MCA were re-tested at the same time and are **unchanged**: IFSCA still renders its directory client-side (0 populated rows over HTTP) and MCA still requires login + CAPTCHA.

**Environment note — and a correction.** The original assessment ran from a US egress and concluded `www.sebi.gov.in` was geo-fenced. **That conclusion was wrong and has been retracted.** SEBI's Cloudflare edge rejects a default `curl` user-agent (HTTP 530) and serves a browser one normally (HTTP 200); the original TLS-stall signature was misread as a network-layer block. Re-verified 2026-07-21 from an Indian egress with browser headers: **SEBI is fully accessible over plain HTTP, server-side rendered, and searchable — no JS, no CAPTCHA, no login.** All SEBI verdicts below are re-derived from live fetches on that date.

---

## Headline result — the end-to-end proof

**The approach works.** For the real test case, a complete, verified corporate record was retrieved with no login and no payment:

| Field | Value | Evidence |
|---|---|---|
| Company | NEO ASSET MANAGEMENT PRIVATE LIMITED | VERIFIED |
| CIN | `U66300MH2021PTC371799` (Tofler, updated 15 Jul 2026) | VERIFIED |
| CIN (older NIC code) | `U67100MH2021PTC371799` (ZaubaCorp) | VERIFIED |
| Status | Active | VERIFIED |
| Incorporated | 18 November 2021 | VERIFIED |
| RoC | Registrar of Companies, Mumbai | VERIFIED |
| Registered address | 903, B-Wing, 9th Floor, Marathon Futurex, Mafatlal Mills Compound, N.M. Joshi Marg, Lower Parel, Mumbai 400013 | VERIFIED |
| Authorised capital | ₹20.00 lakh | VERIFIED |
| Paid-up capital | ₹4.35 lakh | VERIFIED |
| Last AGM | 24 September 2024 | VERIFIED |
| Balance sheet last filed | 31 March 2024 | VERIFIED |
| Revenue range FY2024 | ₹1 cr – ₹100 cr (banded, not exact) | VERIFIED |

**Directors with DINs** (VERIFIED, from two independent sources):

| Name | DIN | Source |
|---|---|---|
| Varun Bajpai | 00058339 | Both |
| Nitin Jain | 01995230 | Both |
| Hemant Daga | 07783248 | Tofler |
| Puneet Jain | 09716672 | Tofler |
| Suresh Chand Goyal | 00220575 | Tofler |
| Rashmi Jain | 03580510 | ZaubaCorp (historical) |
| Ruchika Daga | 09404739 | ZaubaCorp (historical) |

**Note the discrepancy — it is a finding, not noise.** The two aggregators disagree on both the NIC segment of the CIN (`U67100` vs `U66300`) and on the director list. ZaubaCorp appears to carry a stale snapshot including departed directors; Tofler is dated 15 Jul 2026. **Any v1 build must treat aggregator data as needing a freshness check and ideally cross-source confirmation, not as ground truth.**

**UPDATED 2026-07-21.** The SEBI half is now proven too. The register yields the manager's registered AIF trusts and their registration numbers — e.g. `Neo Credit Alternatives Investment Trust` / `IN/AIF2/22-23/1042`, valid Apr 05, 2022 – Perpetual (§1). What is still **NOT** obtainable from the register is a registration for the *scheme* `Neo Infra Income Opportunities Fund II`, because SEBI registers trusts rather than schemes — an absence that is structural and must not be read as non-registration. **Both halves of diligence are now proven; the residual gap is scheme-to-trust resolution, which needs the PPM.**

---

## Per-source verdicts

Verdict vocabulary as requested: ACCESSIBLE-HTTP / ACCESSIBLE-BROWSER / CAPTCHA-BLOCKED / LOGIN-REQUIRED / PAID / UNAVAILABLE.

| # | Source | URL | Verdict | Evidence |
|---|---|---|---|---|
| 1 | SEBI main site & AIF register | `www.sebi.gov.in` …`intmId=16` | **ACCESSIBLE-HTTP** ⟵ *corrected 2026-07-21* | VERIFIED 200 + 1,991 entries; browser UA required |
| 2 | SEBI intermediary sub-portal | `siportal.sebi.gov.in` | **UNAVAILABLE (stub)** | VERIFIED — superseded by #1 |
| 3 | SEBI enforcement / orders | `…sid=2&ssid=9` | **ACCESSIBLE-HTTP** ⟵ *corrected 2026-07-21* | VERIFIED full-text; positive control passed |
| 4 | SEBI SCORES | `scores.sebi.gov.in` | **PARTIAL / LOGIN-REQUIRED** | VERIFIED reachable |
| 5 | MCA V3 — Master Data Services | `mca.gov.in/.../MDS.html` | **LOGIN-REQUIRED** | VERIFIED |
| 6 | MCA V3 — legacy V2 URLs | `/mcafoportal/*.do` | **UNAVAILABLE (retired)** | VERIFIED |
| 7 | MCA V3 — Enquire DIN Status | `.../enquire-din-status.html` | **CAPTCHA-BLOCKED** | VERIFIED |
| 8 | IFSCA Directory (GIFT City) | `ifsca.gov.in/DirectoryList` | **ACCESSIBLE-BROWSER** | VERIFIED, data retrieved |
| 9 | ZaubaCorp | `zaubacorp.com` | **ACCESSIBLE-HTTP** ⟵ *upgraded 2026-07-21* | VERIFIED: correct CIN on 3/3 plain-HTTP attempts with full browser headers. Raw `curl` still 403s — the complete header set, not the UA alone, is what works. Anti-bot edge, so may regress. |
| 10 | Tofler | `tofler.in` | **ACCESSIBLE-BROWSER (partial) / PAID** | VERIFIED, data retrieved |
| 11 | NSE | `nseindia.com` | **ACCESSIBLE-BROWSER** (curl 403) | VERIFIED blocked on HTTP |
| 12 | BSE | `bseindia.com` | **ACCESSIBLE-HTTP** | VERIFIED 200 |
| 13 | data.gov.in API | `api.data.gov.in` | **ACCESSIBLE-HTTP** but wrong granularity | VERIFIED |
| 14 | Probe42 / Signzy / Karza / Perfios | various | **PAID** | VERIFIED reachable only |

---

### 1. SEBI — `www.sebi.gov.in` — ACCESSIBLE-HTTP

> **CORRECTION (2026-07-21).** This section previously read "UNAVAILABLE — geo-fenced" and was **wrong**. The error was consequential: it propagated into the engine, the PRDs, and a client deck, and it left CR-0001 and CR-0002 — both VETO criteria — permanently unevaluated. The corrected finding is below; the original reasoning is dissected under "why the first diagnosis was wrong" so the failure mode is not repeated.

**SEBI is fully accessible over plain HTTP. It is not geo-fenced.**

VERIFIED 2026-07-21, from an Indian egress (AS55836 Reliance Jio, Ahmedabad):

| Request | Result |
|---|---|
| `curl https://www.sebi.gov.in/` with default curl UA | **HTTP 530** |
| Same URL with a browser `User-Agent` | **HTTP 200**, 57,274 bytes |
| `…/OtherAction.do?doRecognisedFpi=yes&intmId=16` (AIF register) | **HTTP 200**, 116,416 bytes |
| `…/HomeAction.do?doListing=yes&sid=2&ssid=9&smid=0` (enforcement orders) | **HTTP 200** |

The gate is **Cloudflare bot filtering at the HTTP layer**, which rejects a default `curl`/urllib user-agent with HTTP 530 and serves a browser user-agent normally. Ordinary bot filtering — not a network block, not a geo-fence.

Working header set (all three sent together; a UA alone is sometimes not enough):

```
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8
Accept-Language: en-GB,en;q=0.9
```

`robots.txt` VERIFIED permissive — it disallows only `/js`, `/css` and their Hindi equivalents. Both paths used below are permitted.

**Why the first diagnosis was wrong.** The original assessment observed a TCP connect followed by a stalled TLS handshake and inferred a block *below* the HTTP layer, concluding that "no amount of headless-browser work fixes this". That inference does not follow: an edge that drops or stalls disfavoured clients produces the same signature as a network filter, and the "a real browser fails identically" control was run from the same blocked egress, so it confirmed the egress rather than testing the hypothesis. **The lesson: a negative result from one egress is a fact about that egress, not about the source.** Reachability claims that gate a VETO criterion deserve a positive control before they are believed.

#### The AIF register — server-side rendered, searchable, no JS

`intmId=16` is "Registered Alternative Investment Funds" (**1,991 entries** as at Jul 20, 2026). VERIFIED characteristics:

- **Server-side rendered.** No JS execution required; content is in the HTML response. A headless browser is **not** needed.
- **Not a plain GET.** The search is a Struts POST needing a `JSESSIONID` cookie and an `org.apache.struts.taglib.html.TOKEN` hidden field, both from a seed GET of the register page.
- **Substring matching, but literal.** VERIFIED: `Alternatives Investment Trust` returns 4 trusts across 3 managers. But full legal names match nothing — `Neo Asset Management Private Limited` returns zero, while `Neo` returns 7.
- Results render as title/value **card divs**, not `<tr>` rows — a table parser reads zero rows off a page full of data.

**The trap.** A POST missing its cookie or token returns HTTP 200 with a ~21.7 KB page carrying neither results nor an error — indistinguishable from an empty result. A genuine empty result says **"No record(s) available"**. Any adapter must separate `results` / `empty` / `unparseable` and let only `empty` become a negative finding.

#### Registration found for the test case

Searching the register for `Neo` returns **7 registered AIFs**, of which these carry `@neoassetmanagement.com` contacts:

| Registered AIF (trust) | Registration No. | Validity |
|---|---|---|
| Neo Alternatives Investment Trust | `IN/AIF3/21-22/1001` | Feb 25, 2022 – Perpetual |
| Neo Credit Alternatives Investment Trust | `IN/AIF2/22-23/1042` | Apr 05, 2022 – Perpetual |
| NEO CREDIT INVESTMENT TRUST | `IN/AIF2/24-25/1656` | Dec 05, 2024 – Perpetual |
| Neo Private Equity Alternative Investment Trust | `IN/AIF2/24-25/1770` | Mar 27, 2025 – Perpetual |
| NEO WSI REAL ESTATE TRUST | `IN/AIF2/26-27/2251` | Jul 07, 2026 – Perpetual |

**A structural finding that governs how CR-0001 may ever fire:** SEBI registers the **AIF trust**, not the manager company and not the individual scheme. Searches for `Neo Infra` and `Infra Income` both return a genuine "No record(s) available", because **Neo Infra Income Opportunities Fund II is a scheme of a registered trust, not itself a registered entity**. Neither is `Neo Asset Management Private Limited` in the register — the manager is not the registrant.

Therefore **an absent fund or manager name is not evidence of non-registration** and must never be reported as one. This register cannot express a positive finding of non-registration; confirming which trust a scheme sits under requires the trust name or registration number from the PPM.

#### Enforcement orders — full-text searchable

`sid=2` is Enforcement; `ssid=9` is **Orders** (adjudication, settlement, WTM). Same session+token POST pattern, with a `search` field.

**VERIFIED to discriminate, which matters more than that it returns 200:** `Reliance` → **56 orders**; `Neo Asset Management` → **"No record(s) available"**. Without that positive control a clean result would be indistinguishable from a search field silently ignoring its input. So the clean result for the test manager is a **genuine finding**, not an unrun search.

Scope caveat: `ssid=9` covers Orders only. Recovery Proceedings (`ssid=50`, 18,863 records), Orders That Could Not be Served (`ssid=12`), and Unserved Summons (`ssid=13`) are separate listings, reachable by the same pattern but not currently searched.

Sub-portal `siportal.sebi.gov.in/intermediary/AIFDetails.html` remains a "Site under construction" stub, © 2016 — VERIFIED, still no data. The main register above supersedes it.

### 4. SEBI SCORES — PARTIAL / LOGIN-REQUIRED

- `https://scores.sebi.gov.in/` → **HTTP 200**, 120,576 bytes. VERIFIED reachable (note: on a different host from the blocked `www`).
- `robots.txt` VERIFIED, and it is **restrictive in a way that matters**:
  ```
  User-Agent: *
  Disallow: https://scores.sebi.gov.in:443/c/*
  Disallow: https://scores.sebi.gov.in:443/login
  ```
- Complaint data behind login — UNVERIFIED (not tested).

**Assessment (UNVERIFIED):** SCORES is a complaint-*filing* system. Individual complaints against a named intermediary are very unlikely to be public. Do not plan on this as a diligence signal in v1.

### 5–7. MCA21 V3 — the headline change

**The old no-login "View Company Master Data" service is gone.** This is the finding most likely to break an assumption in the build plan.

VERIFIED:

- `curl https://www.mca.gov.in/` → **HTTP 403** (Akamai edge block, `errors.edgesuite.net` reference). Even `robots.txt` → 403, so **robots.txt could not be read at all** for MCA.
- A **real browser reaches the site fine** — the 403 is anti-bot fingerprinting at the edge, defeated by a genuine browser. Clear ACCESSIBLE-BROWSER signal at the transport level.
- Legacy V2 URL `/mcafoportal/viewCompanyMasterData.do` → redirects to an **error page**. MCA's own text VERIFIED: *"If you are using any direct or legacy V2 URLs, those links may no longer be valid"*. **The V2 endpoint is retired.**
- Current V3 service located: `https://www.mca.gov.in/content/mca/global/en/mca/master-data/MDS.html`.
- Navigating to it **auto-redirects to `/foportal/fologin.html`** — "MCA User Login / Registration", User ID + Password. VERIFIED. **Company master data now requires an account.**
- Registration is free but requires an MCA user account — UNVERIFIED whether it permits automated querying, and MCA terms likely restrict sharing/scraping.

**"Enquire DIN Status" — CAPTCHA-BLOCKED, but the tractable kind.** VERIFIED:

- `.../fo-llp-services/enquire-din-status.html` loads **without login** and shows **no CAPTCHA on page load** — only a `*DIN` field and Submit.
- Entering a DIN and clicking Submit causes a CAPTCHA panel to appear: "Enter Captcha / Refresh Captcha / Enter the Value". **The CAPTCHA is deferred until submit** — a load-time check would wrongly report this source as open. Worth flagging to whoever scopes this.
- CAPTCHA type VERIFIED by DOM inspection: a **`<canvas id="new-captcha-canvas">` 200×80**, plus a refresh icon and an **audio-playback icon** (accessibility fallback). Explicitly **NOT** reCAPTCHA, **NOT** hCaptcha, **NOT** Turnstile — `window.grecaptcha` absent, no third-party iframes.

So: a **self-hosted, canvas-rendered image CAPTCHA**, the category that is weakest in principle. I did not attempt to defeat it. I began inspecting the client-side validation routine and stopped: reverse-engineering a government portal's CAPTCHA to bypass it is not something to build into a product, independent of whether it is technically possible. **Recommend treating the CAPTCHA as a hard boundary and routing DIN checks through a licensed commercial provider instead.** A provider pays for compliant access; we would be circumventing an access control on a government system.

**Also found (UNVERIFIED, not opened):** `View Companies/Directors Under Prosecution` at `.../master-data/View-Companies-Directors-under-prosecution-V3.html`, and `Verify DIN PAN Details of Director`. The prosecution list is directly relevant to question 6 (disqualification) and is worth a look in a follow-up — it may be a static published list rather than a gated query.

### 8. IFSCA — ACCESSIBLE-BROWSER — the best government source found

The only **government** source from which entity-level data was actually retrieved. VERIFIED:

- `https://www.ifsca.gov.in/` → HTTP 200. `robots.txt` → **empty** (no crawl restrictions expressed).
- Directory at `https://ifsca.gov.in/DirectoryList` → HTTP 200. **No CAPTCHA** (`captcha`/`recaptcha` absent from source), **no login**.
- Plain HTTP GET returns the **table shell only — 12 `<tr>` but 0 populated data rows**. Header labels are present ("Registration / Authorization No.", "Validity From", "Validity To", …) but no entities. A naive HTTP scraper gets nothing and may look like a success.
- **In a real browser the rows populate.** VERIFIED sample:

  | # | Entity | Category | Sub-category |
  |---|---|---|---|
  | 1 | ASSETFRACTIO ADVISORY PRIVATE LIMITED | Fintech Sandbox Entities | Sandbox Entities |
  | 2 | Baroda BNP Paribas Gift Multicap Fund | Fund Management | Retail Scheme |
  | 3 | HDFC SECURITIES IFSC LIMITED | Capital Market Intermediaries | Clearing Members |
  | 4 | InBrok (IFSC) Private Limited | Capital Market Intermediaries | Global Access Providers |

- POST to `/DirectoryList` with `__RequestVerificationToken` + cookie → HTTP 200 (ASP.NET MVC anti-forgery flow works), but still without populated rows via HTTP.
- An internal endpoint `Directory/DirectoryChildDataByID` was identified in page source. GET → 404; POST without body → **411 Length Required**, which VERIFIES the route exists and is POST-only. Its exact payload was not determined — worth 30 minutes with devtools open, as finding it would downgrade this to cheap ACCESSIBLE-HTTP.

**Automation cost — low.** Load one page, wait for render, read the table, handle pagination. Filters exist (Global Search, Category, Sub Category) if per-entity lookup is preferred over a full harvest. **The directory is small enough to mirror wholesale on a schedule** rather than querying live — the better design.

### 9–10. Commercial aggregators — where the working data actually came from

**ZaubaCorp — ACCESSIBLE-BROWSER, free.** VERIFIED:

- `curl` → **HTTP 403**. Real browser → **loads fine**. Anti-bot at the edge; a headless browser is mandatory.
- Working search: `https://www.zaubacorp.com/companysearchresults/NEO-ASSET-MANAGEMENT` → "1 records found", link to the company page.
- Company page yielded the full record and the director/DIN table quoted above.
- `robots.txt` VERIFIED and **permissive**: only `Disallow: /*.pdf$`, then `Allow: *`. **Scraping HTML pages does not violate robots.txt.** Site ToS not reviewed — worth a legal read before production.
- Weakness VERIFIED: data is **stale** (older NIC code, departed directors listed as current).

**Tofler — ACCESSIBLE-BROWSER for identity, PAID for financials.** VERIFIED:

- Root → HTTP 200 on plain curl (friendlier than Zauba). Company page renders identity data free.
- Gave the **registered address and the current director list** — the highest-quality free record obtained anywhere, dated 15 Jul 2026.
- **Financials are paywalled**: Total Revenue, EBITDA, Net Profit, Networth, Borrowings, margins, ROE/ROCE all require "Tofler Pro". Only a **banded** revenue figure is free. Question 3 ("filed financials") is therefore **not** answerable free at useful precision.
- `robots.txt` VERIFIED and **materially restrictive** — this is a ToS/robots flag as requested:
  ```
  Disallow: /companyinfo/*
  Disallow: /basicsignatoryinfo/*
  Disallow: /basicsearch
  Disallow: /findcompany*
  Disallow: /cnamesearch*
  ```
  **Tofler's robots.txt disallows exactly the search and company-info paths a scraper would use.** Automated harvesting of Tofler would contravene its stated crawl policy. **Recommend not scraping Tofler.** If its data is wanted, license it.

**Probe42, Signzy, Karza, Perfios — PAID.** VERIFIED only that the marketing sites resolve (probe42.in 200, signzy.com 200, perfios.com 200, karza.in 200). `docs.probe42.in` → `000`. **No API contract, no rate limit, and no pricing was verified.** Anything about their coverage or cost is UNVERIFIED. Probe42 is understood (UNVERIFIED) to be the closest fit for MCA company/director data via authorised API — it should be the first commercial conversation, precisely because it resolves the MCA login/CAPTCHA problem legitimately.

### 11–12. Exchanges

- NSE `www.nseindia.com` → **HTTP 403** on curl (well-known aggressive bot blocking; browser-accessible — ACCESSIBLE-BROWSER, UNVERIFIED in browser here).
- BSE `www.bseindia.com` → **HTTP 200** on plain curl. ACCESSIBLE-HTTP. VERIFIED.
- **Low relevance:** AIF managers are typically unlisted private companies. Neo Asset Management is a private limited company — VERIFIED — so exchange data does not apply to the test case. Deprioritise.

### 13. Bulk data — the answer is no

The brief asks whether bulk datasets could avoid per-query scraping. **VERIFIED: not for this use case.**

- `api.data.gov.in/lists?format=json` → **HTTP 200**, `"total": 285829` resources. A genuinely working open API.
- Searched the catalogue: `title=company` → 306 results; `corporate affairs` → 2,201; `SEBI` → **4**.
- **Everything returned is aggregate statistics, not entity-level registers.** Actual titles VERIFIED: "Company-wise Corporate Social Responsibility (CSR) Spent…", "Year-wise Detail of Registration of New Foreign Portfolio Investors (FPIs)…", "Year-wise Number of Cases of Stock Trading Frauds…".
- **No AIF register, no company master-data dump, no director/DIN dataset.**

MCA does sell a bulk "Company Master Data" product commercially (UNVERIFIED — could not be checked, MCA returns 403 to non-browser clients). Worth investigating alongside Probe42, since a licensed bulk file would sidestep both the login and the CAPTCHA cleanly.

---

## ToS / robots.txt flags

Raised explicitly because the coordinator asked to know before building, not after.

| Source | robots.txt | Flag |
|---|---|---|
| Tofler | Disallows `/companyinfo/*`, `/basicsearch`, `/findcompany*`, `/cnamesearch*` | **Do not scrape.** Search & company paths explicitly disallowed. License instead. |
| ZaubaCorp | Only `Disallow: /*.pdf$`, else `Allow: *` | Scraping HTML appears permitted. Review ToS before production. |
| SCORES | Disallows `/c/*` and `/login` | Avoid those paths. |
| IFSCA | Empty robots.txt | No stated restriction. Still, prefer scheduled mirroring over hammering. |
| MCA | **Could not be read (403)** | Unknown. Assume restrictive. Login + CAPTCHA are deliberate access controls — **treat as off-limits to automation**; use a licensed provider. |
| SEBI | AIF register + enforcement orders, read live over HTTP | Manager's registered trusts and registration numbers found; no enforcement orders. Scheme itself is not separately registered (structural). |

**Position on CAPTCHA:** MCA's CAPTCHA is technically the weak self-hosted kind, but it is an intentional access control on a government system. Defeating it is a legal and reputational exposure disproportionate to the value of a DIN status check, and it would be fragile. Route this through a licensed provider.

---

## Recommendation for v1

### Build now — proven to work

1. **Corporate identity via ZaubaCorp, headless browser.** VERIFIED end to end on the real test case: CIN, status, incorporation date, RoC, capital, AGM/balance-sheet dates, directors + DINs. Two steps: search URL → company page. Permissive robots.txt. **This is the backbone of v1.**
2. **IFSCA GIFT City check.** VERIFIED working; answers question 5 outright. Mirror the whole directory on a schedule and look up locally — the directory is small, and this avoids repeated live queries. **Must use a browser: plain HTTP silently returns an empty table** — build a row-count assertion so an empty scrape fails loudly rather than reporting "no match found".
3. **Cross-source freshness checks.** The Zauba/Tofler disagreement on CIN and directors is VERIFIED and material. Stamp every field with source + retrieval date, and surface disagreement to a human rather than silently picking one.

### Resolve before committing — highest priority

4. ~~**Re-run the entire SEBI assessment from an Indian IP.**~~ **DONE 2026-07-21 — and the premise was wrong.** SEBI needed browser headers, not a different egress. Questions 1, 2 and 4 are now **answered**: the AIF register (`intmId=16`) and enforcement orders (`sid=2&ssid=9`) are both server-side rendered, searchable over plain HTTP, and implemented in the engine. The remaining SEBI work is narrower: resolve a scheme to its parent trust (the register holds trusts, not schemes), and decide whether to extend enforcement coverage beyond `ssid=9` to recovery proceedings and unserved summons.
5. **Talk to Probe42** (and price MCA's bulk data product) for MCA company/director/financial data. This legitimately resolves the login wall, the CAPTCHA, and the Tofler robots.txt problem in one move.

### Defer / flag for manual check

6. **Filed financials** — free sources give only a banded revenue figure. Either license, or flag for manual review. Do not promise precise financials in v1.
7. **DIN status & disqualification** — CAPTCHA-gated; route via provider. Do check the **"Companies/Directors Under Prosecution"** page first (identified, not yet opened) — it may be a free static list.
8. ~~**SEBI enforcement actions** — cannot be scoped until (4) is done.~~ **Scoped and built.** Full-text search over Enforcement > Orders, VERIFIED to discriminate against a positive control. The "false no-actions-found is worse than an honest not-checked" principle still governs the implementation: an unparseable response is recorded `unavailable`, never clean.
9. **SCORES complaints** — assume not public. Drop from v1.
10. **NSE/BSE** — not applicable to unlisted private managers. Drop.
11. **Bulk/open data** — VERIFIED dead end. Do not spend further time here.

### Design principle

Every check should return one of **VERIFIED / NOT FOUND / COULD NOT CHECK** — never conflate the last two. Several sources here fail in ways that *look* like a clean negative result: IFSCA returns an empty table over HTTP, MCA returns a login page, SEBI times out. A diligence tool that reports "no adverse findings" when it actually failed to reach the regulator is worse than one that reports nothing at all.

---

## Open questions

1. ~~Is `www.sebi.gov.in` reachable, and what are the real AIF-register and enforcement-search URLs?~~ **ANSWERED 2026-07-21.** Reachable with browser headers from any egress tested; URLs documented in §1 and implemented. Superseded by: how should a scheme name be resolved to its parent registered trust, given the register indexes trusts only? Today the engine searches the manager's distinctive token and reports matches as supporting evidence, never as a negative.
2. What is the IFSCA `DirectoryChildDataByID` payload? Would downgrade IFSCA to cheap HTTP.
3. Is "Companies/Directors Under Prosecution" free and static?
4. Probe42 / MCA bulk pricing, coverage, rate limits — all UNVERIFIED.
5. Does an MCA account permit automated querying under its terms?
6. ZaubaCorp ToS (beyond robots.txt) — legal review before production.
