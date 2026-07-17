---
title: "Observation: SEC Filing Diligence"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [pipeline, sec, diligence, edgar, deterministic]
---

# Observation: SEC Filing Diligence

Source: `00-inbox/pipeline-architecture.md` §5, audited against codebase.

## Activity

Acquire → identify → extract → verify workflow that pulls a fund/manager's official regulatory record (SEC EDGAR and other public-data sources) and deterministically cross-checks it against pitch-deck claims.

## Inputs

- Fund/manager name and identifying details from deck extraction (§3-4).
- SEC EDGAR public submissions API (`data.sec.gov/submissions/CIK{cik}.json`, 24h cache).
- Form D/13F/990/5500/ACFR bulk data sources.

## Outputs

- Entity categorization: `registered` / `private` / `public_manager`.
- Extracted ADV fields: identity, AUM/scale, conflicts/custody, ownership (Schedule A), Schedule R relying advisers, per-fund reporting (Section 7.B.1), disciplinary history (Item 11), ADV Part 2A Brochure narrative summary.
- `MatchChecks` struct — four categorical match results (domain, location, AUM, fund-flag) handed to a judge/LLM upstream. No single numeric confidence score.
- LP-discovery data: Form 5500 (pension), Form 990 (foundation/endowment), ACFR (public pension) — normalized fund-name/investor-name pairs in DuckDB/Parquet indexes.

## Systems

1. **Entity categorization** — LLM-classified, Jina web-search fallback. Category determines target document set (private funds → ADV Part 1/2, Form D/13F/13D/13G; registered funds → Prospectus/SAI/N-CSR/N-PORT; public managers → private-fund docs + 10-K/10-Q).
2. **Acquisition** — `SECProvider`, EDGAR submissions API, unwraps SGML/XML/PDF envelopes.
3. **Identification** — deterministic pattern matching (not LLM): XML tag inspection for Form D/13F/3-4-5/13D-13G; `pdftotext -layout` + regex/keyword rules for PDFs (e.g., "uniform application for investment adviser registration" ⇒ ADV Part 1). Returns `confidence: high|medium|low` + `isMerged` flag.
4. **Extraction** — type-specific extractors, concurrency 5: Form D/13F/ownership XML; ADV Part 1 (hybrid regex + LLM — regex for Item 1 identity/Item 5 AUM, Gemini for multi-page tabular sections like Schedule A/R and Item 11); ADV Part 2 brochures (LLM narrative per item).
5. **Match-verification** (`match-verification.ts`) — deterministic:
   - Domain: exact / mismatch / missing (URL normalized — strip protocol/www/trailing slash, lowercase).
   - Location: exact_city_state / state_only / mismatch.
   - AUM: parses free-text into numeric magnitude, asymmetric tolerance band `lowerBound = dbVal * 0.4`, `upperBound = dbVal * 2.5` (decks round up, filings under-report) → magnitude_match/mismatch/unparseable/missing.
   - Fund-flag: deck claims private funds exist but SEC `has_private_funds = false` → flagged `inconsistent`.
- Other sources: Form D (DuckDB/Parquet), Form 13F, Schedule 13D/13G, Forms 3/4/5, DOL Form 5500, IRS Form 990/TEOS (parsing happens Elixir-side: `DealsAnalysis.Teos.Extractor.extract_xml/1`, regex-based, entity-dedup, invoked via `mix extract.irs_990` — manual, OTP-concurrent, ~2M files, `2× CPU core count` workers), ACFR.
- `analyze-firm-investors.ts` chains Form D → Form 990 search to build LP roster for a manager.

## People / Actors

- Fully automated except `mix extract.irs_990`, which is a manually-run bulk job (not scheduled), sized for a dedicated high-core machine.

## Timing

- EDGAR submissions cached 24h.
- Extraction runs concurrency 5.
- `mix extract.irs_990` processes ~2M IRS XML files — no duration stated. `[UNKNOWN: actual run time]`

## Problems / Gaps / Workarounds

- **Filed disciplinary history (Item 11)** is called out in code comments as the single highest-signal red flag in the entire pipeline.
- **Fund-flag mismatch** (deck claims private funds, SEC record shows none) is called out in code comments as a "major red flag."
- No single numeric confidence score for match-verification — deliberately left as four categorical results for a judge/LLM to weigh, not resolved to one number.
- `mix extract.irs_990` is a manual, unscheduled batch job — not part of the automated per-fund pipeline; its output (`extracted_funds` fund-name-normalization view) is a dependency other entity-matching code relies on. If it's not re-run periodically, downstream matching may work against stale IRS data. `[UNKNOWN: last run date / refresh cadence]`

## Open Questions

- How often is `mix extract.irs_990` actually re-run in production, and who owns that cadence?
- Is there a plan to fold the manual IRS-990 batch job into the automated per-fund pipeline, or is it intentionally a separate offline refresh?
