---
title: "Process: Data Extraction from Pitch Decks"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [pipeline, extraction]
---

# Process: Data Extraction from Pitch Decks

Built from: [obs-data-extraction](../10-observations/obs-data-extraction.md). Sub-process of step 6.1b in [proc-deal-analysis-pipeline](proc-deal-analysis-pipeline.md), runs after [proc-fund-classification](proc-fund-classification.md).

## Process Overview

- **Purpose**: Extract every structured fact from the pitch deck — terms, strategy, team/track record, warehoused deals, plus asset-class-specific metrics — into a single consolidated, mapped record.
- **Trigger**: Fund classification (Pass 1) completes.
- **End condition**: `master_data` written to the Elixir `Fund` resource; Cypher `MERGE` statements generated for the graph DB.

## Roles Involved

- Fully automated.

## Inputs and Outputs

- **Input**: raw pitch-deck PDF, `primaryAssetClass` (gates which asset-class schema runs).
- **Output**: `consolidatedKnowledge`, `master_data`, graph DB nodes (Fund/Manager/Person/Company/Strategy/Location).

## Process Steps

1. Schema list assembled: 4 core schemas (every asset class) — `fund_overview_and_terms`, `strategy_and_portfolio`, `team_and_track_record`, `warehoused_deals` — plus 1 asset-class-specific schema selected by `primaryAssetClass` (`hedge_fund_metrics` / `venture_capital_metrics` / `real_estate_metrics` / `private_credit_metrics` / `private_equity_metrics`).
2. Each schema extracted **independently in parallel**, concurrency 10. For each schema:
   - 2a. `generateContent` call with raw PDF (`fileData` part) → comprehensive markdown report, forced verbatim quoting + page citations (`[Page X]`).
   - 2b. Second `generateContent` call over that markdown, `responseSchema` set (Zod → JSON Schema) → structured JSON. (This two-step split exists specifically so the model doesn't invent/miscalculate numbers while simultaneously reading and formatting.)
3. **Numeric normalization**, per field, for every monetary/%/duration/multiplier value:
   - 3a. `source_number_text` captured verbatim in step 2b (e.g. "$500K", "2.5x", "18 months").
   - 3b. Separate smaller LLM call (`gemini-3.1-flash-lite`, `parseMeasurementsInPayload` in `schema-extraction.ts`) parses the string into `{amount, magnitude: ONES|HUNDREDS|THOUSANDS|MILLIONS|BILLIONS|TRILLIONS}` or a range. No arithmetic happens inside the prose-reading call.
4. All schema outputs merged by schema name into `consolidatedKnowledge` — topic-level merge, not page-by-page reconciliation.
5. `master-schema-mapper.ts` (`mapPrivateMarketSchema()`) coerces `consolidatedKnowledge` into `master_data`, stored on the Elixir `Fund` resource. (This is also, separately, the deterministic source for the L1 memo's Fund Factsheet section — no additional LLM call there.)
6. A separate LLM call converts `master_data` into Cypher `MERGE` statements for the graph DB (Fund/Manager/Person/Company/Strategy/Location nodes).
7. Process continues to person research (proc-key-personnel-intelligence) and SEC diligence (proc-sec-filing-diligence), both gated on this step's output.

### Legacy Path (parallel, status unclear)

- `consolidate-entities-partitioned.ts` performs true per-slide fan-out across 6 fixed partitions (summary/company/financials/market/people/investment) — appears to predate the schema-per-domain approach above. `[UNKNOWN: whether still invoked in production]`

## Systems and Tools

- Gemini (native structured output, Zod → JSON Schema via `zodToJsonSchema`).
- `gemini-3.1-flash-lite` for numeric normalization.
- `master-schema-mapper.ts`, graph-DB Cypher generator.

## Known Issues

- Legacy per-slide consolidation path (`consolidate-entities-partitioned.ts`) coexists with current approach, unconfirmed whether dead or live. See [obs-data-extraction](../10-observations/obs-data-extraction.md).

## Open Questions

- Should the legacy path be marked dead code (like `score-agent.ts` in scoring) or is it still in use?
- Actual per-schema/per-fund cost and latency of this stage? `[UNKNOWN]`
