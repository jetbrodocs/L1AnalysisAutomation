---
title: "Process: SEC Filing Diligence"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [pipeline, sec, diligence]
---

# Process: SEC Filing Diligence

Built from: [obs-sec-filing-diligence](../10-observations/obs-sec-filing-diligence.md). Sub-process of step 6.1c in [proc-deal-analysis-pipeline](proc-deal-analysis-pipeline.md), runs once per fund (later diligence steps skip re-running it — see step 6.3 note in main flow).

## Process Overview

- **Purpose**: Acquire the fund/manager's official regulatory record and deterministically cross-check it against pitch-deck claims.
- **Trigger**: Runs within `processPitchDeckWorkflow`, after fund/team identity is available from extraction.
- **End condition**: `MatchChecks` struct (domain/location/AUM/fund-flag) produced and handed upstream; extracted ADV/Form D/13F/etc. fields stored.

## Roles Involved

- Fully automated, except the standalone `mix extract.irs_990` batch job (manually run, not scheduled).

## Inputs and Outputs

- **Input**: fund/manager name and identifying details from deck extraction.
- **Output**: entity category, extracted ADV/Form D/13F/990/5500/ACFR fields, `MatchChecks` struct.

## Process Steps

1. **Entity categorization.** LLM classifies fund/manager as `registered` (mutual fund/ETF) / `private` (hedge fund/PE/VC/RIA) / `public_manager`. Jina web-search fallback if internal classification is inconclusive.
2. **Target document set selected** by category (decision point):
   - `private` → ADV Part 1, ADV Part 2 Brochure, Form D, Form 13F, Schedule 13D/13G.
   - `registered` → Prospectus/SAI/N-CSR/N-PORT.
   - `public_manager` → private-fund docs plus 10-K/10-Q.
3. **Acquisition.** `SECProvider` hits SEC EDGAR public submissions API (`data.sec.gov/submissions/CIK{cik}.json`, 24h cache), unwraps SGML/XML/PDF filing envelopes.
4. **Identification** (deterministic, not LLM):
   - XML tag inspection for Form D/13F/Forms 3-4-5/Schedule 13D-13G.
   - For PDFs: `pdftotext -layout` + regex/keyword rules (e.g. "uniform application for investment adviser registration" ⇒ ADV Part 1). Returns `confidence: high|medium|low` and `isMerged` flag for combined Part 1+2 PDFs.
5. **Extraction**, type-specific extractors run concurrently (concurrency 5):
   - Form D/13F/ownership XML — deterministic.
   - ADV Part 1 — hybrid: deterministic regex for Item 1 identity/Item 5 AUM (fast, hallucination-free); Gemini for multi-page tabular sections (Schedule A/R, Item 11 disciplinary tables) where layout drift breaks regex.
   - ADV Part 2 brochures — LLM narrative summarization per item.
6. **Match-verification** (`match-verification.ts`), all deterministic:
   - Domain: exact / mismatch / missing (URL normalized).
   - Location: exact_city_state / state_only / mismatch.
   - AUM: parsed to numeric magnitude, checked against asymmetric tolerance `lowerBound = dbVal * 0.4`, `upperBound = dbVal * 2.5` → magnitude_match/mismatch/unparseable/missing.
   - Fund-flag: deck claims private funds exist but SEC `has_private_funds = false` → `inconsistent` (flagged in code as "major red flag").
7. `MatchChecks` struct (four categorical results, no single numeric score) handed upstream for a judge/LLM to weigh in later stages (scoring, L1).
8. Result feeds into step 6.3 (`fundDeepDiligenceWorkflow` — skips re-running this) and eventually scoring (step 6.4, though see wiring gap below).

### Parallel/Supporting Data Sources (not gated by steps 1-7)

- Form D (DuckDB/Parquet over EDGAR bulk TSVs), Form 13F, Schedule 13D/13G, Forms 3/4/5.
- DOL Form 5500 — ERISA pension filings, extracts sponsor/plan/investment fields for LP-side pension discovery.
- IRS Form 990/TEOS — nonprofit/foundation returns. Trigger.dev tasks (`form990-ingestion.ts`, `sync-form990-teos.ts`, `teos-worker.ts`, `search-form990-db.ts`) are query/sync layer; heavy XML parsing happens Elixir-side (`DealsAnalysis.Teos.Extractor.extract_xml/1`), invoked via `mix extract.irs_990` — **manual, unscheduled, OTP-concurrent bulk job**, processes ~2M IRS XML files across `2× CPU core count` workers, produces `extracted_funds` fund-name-normalization view that entity-matching elsewhere relies on.
- ACFR — state/municipal pension audited financials.
- All three (5500/990/ACFR) normalize into DuckDB/Parquet indexes with corporate suffixes stripped for fuzzy ILIKE matching. `analyze-firm-investors.ts` chains Form D → Form 990 to build an LP roster for a manager.

## Systems and Tools

- SEC EDGAR submissions API, `SECProvider`, `pdftotext`, regex extractors, Gemini (tabular sections only).
- `match-verification.ts`.
- `mix extract.irs_990`, `DealsAnalysis.Teos.Extractor.extract_xml/1`.

## Known Issues

- Filed disciplinary history (Item 11) is called out in code comments as the single highest-signal red flag in the entire pipeline.
- Fund-flag mismatch is called out as a "major red flag."
- `mix extract.irs_990` is manual/unscheduled — downstream entity matching depends on its output freshness. See [obs-sec-filing-diligence](../10-observations/obs-sec-filing-diligence.md).
- Downstream: scoring (step 6.4) does not actually receive this stage's output (`ddResult`) — see [proc-scoring-rubric](proc-scoring-rubric.md) known issues.

## Open Questions

- Refresh cadence / last-run date of `mix extract.irs_990`? `[UNKNOWN]`
- Plan to automate the IRS-990 batch job into the per-fund pipeline?
