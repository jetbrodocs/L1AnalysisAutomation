---
title: "Observation: India Variant — Regulatory Diligence (Multi-Regulator Router)"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [india, sebi, mca21, rbi, fema, ifsca, regulatory-diligence]
---

# Observation: India Variant — Regulatory Diligence (Multi-Regulator Router)

Source: `00-inbox/pipeline-architecture-india.md` §5, "the section that changes most" vs. the US doc §5 ([obs-sec-filing-diligence](../obs-sec-filing-diligence.md)). Described in the source doc as the architectural core of the India variant.

## Activity

Acquire a fund/manager's official regulatory record and deterministically cross-check it against pitch-deck claims — same design intent as the US SEC-diligence flow, but routed across **four independent regulators** instead of one federal API, because no India equivalent of SEC EDGAR exists.

## Inputs

- Fund/manager identity and structure signals from deck extraction (which regulator(s) apply depends on fund structure — AIF category, foreign-LP presence, GIFT City domicile, listed-company holdings).
- **SEBI** — intermediary/AIF registration lookup (searchable list, no bulk-download API), SI Portal registration records, public Adjudication/Enforcement Orders pages, SAST (Substantial Acquisition of Shares and Takeovers) disclosures.
- **MCA21** — company master data (CIN, registered office, director/DIN roster, incorporation date), AOC-4 (audited financials), MGT-7/MGT-7A (annual return), DIR-3 KYC (director-record freshness signal).
- **RBI/FEMA** — Form FC-GPR (foreign equity allotment), Form FC-TRS (resident↔non-resident transfers), annual FLA (Foreign Liabilities and Assets) returns, all via the RBI FIRMS portal. Applies only when the fund has foreign LPs or makes ODI investments.
- **IFSCA** — Fund Management Entity (FME) registration record, tiered Authorised FME / Registered FME (Non-Retail) / Registered FME (Retail) by investor net-worth threshold (USD 75K / 500K / 1M). Applies only to GIFT City-domiciled funds.
- **NCLT/IBC** — insolvency-proceeding records for the manager entity and its promoters/directors.

## Outputs

- Entity/fund routed to whichever of the five source categories applies to its structure (a fund can hit multiple sources at once, e.g. an AIF with foreign LPs hits both SEBI and RBI/FEMA).
- Same `MatchChecks`-shaped output as the US pipeline (domain/location/AUM/registration-status categorical checks), re-pointed at whichever India source applies — **no single numeric confidence score**, same design as US.
- Enforcement check output: `has_any_flags` boolean + categorized breakdown — same shape as US ADV Item 11 output, sourced from SEBI Adjudication/Enforcement Orders + NCLT/IBC instead.
- **Confirmed capability gap, no output produced**: no LP-roster equivalent to the US Form 5500/990 chain — see Problems below.

## Systems

**Proposed pipeline** (acquire → identify → extract → verify, same shape as US `SECProvider` flow, but multi-source):
1. Entity categorization (LLM-classified + web-search fallback) routes to one or more of 5 source categories based on fund/entity type.
2. Acquisition — **per-source adapter, no unified API** (unlike US EDGAR's single submissions JSON). SEBI and enforcement-order acquisition specifically require Jina web-search-and-match against `sebi.gov.in` rather than a clean REST call, since no bulk-download API equivalent to EDGAR exists publicly.
3. Identification — doc-type pattern match, per source format.
4. Extraction — regex + LLM hybrid, same two-tier design as US ADV parsing.
5. Verify — deterministic cross-check vs. deck claims, same `match-verification.ts` design, re-pointed per source.
6. Enforcement check — separate branch, same output shape as US ADV Item 11.

**Per-source acquisition mechanics:**
- **SEBI intermediary/AIF registration**: scrape/search-based (no bulk API). Confirms registration category (I/II/III), registration number, sponsor/manager names, and — for schemes beyond Angel/LVF — whether the PPM was filed through a SEBI-registered Merchant Banker with a due-diligence certificate.
- **MCA21**: free real-time lookup by CIN or company name (MCA21 V3 portal). AOC-4/MGT-7 report **corporate structure and statutory financials**, not regulatory AUM in the SEC sense — this is a semantic gap versus US ADV AUM figures, not a like-for-like substitute.
- **RBI/FEMA**: FC-GPR (30-day filing window), FC-TRS (60-day filing window), annual FLA returns, via FIRMS portal.
- **IFSCA**: FME tier lookup, GIFT City only.
- **SEBI SAST**: sourced from BSE/NSE corporate-announcement feeds, not SEBI directly — closest analogue to US Schedule 13D/13G.
- **Enforcement**: SEBI Adjudication/Enforcement Orders pages searchable by entity name but **not bulk-indexed** the way SEC Item 11 data is — same search-and-match acquisition pattern as SEBI intermediary lookup.

## People / Actors

- Fully automated, same as US pipeline — no new human role proposed.

## Timing

- `[UNKNOWN]` — no cache duration, acquisition latency, or refresh cadence stated for any of the four India sources (US EDGAR has an explicit 24h cache; no equivalent stated here).
- Filing due-date windows (regulatory facts, not pipeline timing): FC-GPR 30 days, FC-TRS 60 days, AOC-4 30 days post-AGM, MGT-7 60 days post-AGM, DIR-3 KYC annual (due Sept 30).

## Problems / Gaps / Workarounds

- **No unified API across any of the four regulators** — every acquisition path is a per-source adapter, several of them scrape/search-based rather than clean REST calls. This is the single largest new-build item in the entire India variant.
- **AUM figure does not reconcile across sources by design.** SEBI AIF corpus commitments, MCA21 balance-sheet figures, and RBI FDI-inflow totals are three different numbers. The verification logic must compare deck claims against whichever figure the *relevant* source reports — it should not try to force these into one number.
- **Confirmed capability gap: no LP-discovery equivalent to US Form 5500/990.** AIF investor lists are confidential under SEBI regulations — there is no public LP-disclosure regime in India analogous to the US pension (Form 5500) / nonprofit (Form 990) chain. The only indirect signal: EPFO/pension-fund and IRDAI-regulated insurers participation is visible only when *those* institutional LPs disclose an AIF investment in their own public filings — not from a fund-side registry. Source doc explicitly flags this as a **genuine gap to communicate to stakeholders**, not something to paper over with a weaker substitute.
- **Enforcement/adjudication data is not bulk-indexed** — same search-and-match acquisition burden as the SEBI registration lookup, meaning entity-name-matching quality directly determines whether disciplinary history is actually found.
- **MatchChecks needs a new field for India that the US struct never needed**: a `source` field per check (which regulator/registry produced this match result), since India routes across five possible sources — the US struct only ever has one source (SEC), so this need doesn't currently exist in the US design.

## Open Questions

- Which of the five source adapters (SEBI, MCA21, RBI/FEMA, IFSCA, SAST) would be built first if this variant were greenlit — is there a proposed build order given AIF Cat II funds (PE/credit/RE) are likely the most common target segment?
- Is there any existing third-party data vendor/API that already aggregates SEBI+MCA21+RBI+IFSCA data, avoiding the need to build five separate scrapers in-house?
- How should the pipeline communicate the LP-discovery gap to an Investment Committee reading the memo — a dedicated "Data Not Available in India" note in the Claims Ledger, or silent omission of the section?
