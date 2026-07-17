---
title: "Observation: Data Extraction from Pitch Decks"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [pipeline, extraction, gemini, schemas]
---

# Observation: Data Extraction from Pitch Decks

Source: `00-inbox/pipeline-architecture.md` §4, audited against codebase.

## Activity

Full-document extraction of fund terms, strategy, team/track-record, and warehoused deals, plus asset-class-specific metrics, run per-schema in parallel, then consolidated and mapped into the fund's master data record and a graph DB.

## Inputs

- Raw pitch-deck PDF (via Gemini Files API).
- `primaryAssetClass` from Fund Classification (gates which asset-class-specific schemas run).

## Outputs

- Core schemas (every asset class): `fund_overview_and_terms`, `strategy_and_portfolio`, `team_and_track_record`, `warehoused_deals`.
- Asset-class-specific schemas (gated by classification): `hedge_fund_metrics`, `venture_capital_metrics`, `real_estate_metrics`, `private_credit_metrics`, `private_equity_metrics`.
- `consolidatedKnowledge` — topic-level merge of all schema outputs.
- `master_data` object on the Elixir `Fund` resource (via `master-schema-mapper.ts`).
- Cypher `MERGE` statements populating a graph DB (Fund/Manager/Person/Company/Strategy/Location nodes).

## Systems

- Two-step extraction pattern per schema:
  1. `generateContent` with raw PDF → comprehensive markdown report, forced verbatim quoting with page citations (`[Page X]`).
  2. Second `generateContent` call over that markdown, `responseSchema` set (Zod → JSON Schema) → structured JSON.
- Numeric normalization: every monetary/%/duration/multiplier field captures `source_number_text` verbatim first, then a separate smaller LLM call parses into `{amount, magnitude: ONES|HUNDREDS|THOUSANDS|MILLIONS|BILLIONS|TRILLIONS}` or a range.
- Consolidation: schema groups extracted independently in parallel (one Gemini call per schema over full doc, concurrency 10), merged by schema name — topic-level, not page-by-page.
- Legacy path: `consolidate-entities-partitioned.ts` does true per-slide fan-out across 6 fixed partitions (summary/company/financials/market/people/investment) — appears to predate the schema-per-domain approach.
- `master-schema-mapper.ts` — coerces consolidated knowledge into `master_data`.

## People / Actors

- Fully automated, no human review step observed in this stage.

## Timing

- `[UNKNOWN: per-schema call duration not stated]`
- Schema extraction runs at concurrency 10 (parallel, not sequential).

## Problems / Gaps / Workarounds

- **Legacy/current path ambiguity**: `consolidate-entities-partitioned.ts` (per-slide fan-out) coexists with the current schema-per-domain consolidation approach. Source doc flags it as "appears to be a legacy strategy predating the schema-per-domain approach" — not confirmed dead, not confirmed actively used alongside the new path. `[UNKNOWN: whether legacy path still executes in production or is orphaned code]`
- Two-tier extract-then-normalize exists specifically to prevent hallucinated arithmetic — implies a known failure mode (LLM inventing/miscalculating numbers) that was designed around, not merely a stylistic choice.

## Open Questions

- Is `consolidate-entities-partitioned.ts` still invoked anywhere, or should it be marked dead code (like `score-agent.ts`, see scoring observation)?
- What is the actual per-schema/per-fund cost and latency of this extraction stage?
