---
title: "Observation: Fund Classification (Pass 1)"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [pipeline, classification, gemini, taxonomy]
---

# Observation: Fund Classification (Pass 1)

Source: `00-inbox/pipeline-architecture.md` §3, audited against codebase.

## Activity

A dedicated LLM pass classifies the fund's asset class, structure, and manager maturity, before any other extraction runs. This single decision gates which extraction schemas, scoring rubric, and research mission pack fire downstream.

## Inputs

- Full pitch-deck PDF, over Gemini file API (not the RAG store).
- Schema: `fund_overview_and_terms` only.

## Outputs

- `primaryAssetClass`: enum `Private Equity, Hedge Fund, Venture Capital, Real Estate, Private Credit, Fund of Funds, Infrastructure, Unknown`
- `hedgeFundStrategy` (conditional)
- `isOpenEnded` — open-ended/evergreen vs. closed-end draw-down
- `classificationReasoning` — forced free-text justification (chain-of-thought)
- `managerClassification`: enum `Emerging, Transitioning, Established` + own reasoning field

## Systems

- Model: Gemini 3.5 Flash, high thinking level.
- Downstream gates set by this pass: asset-class-specific extraction schemas (`hedge_fund_metrics`, `venture_capital_metrics`, `real_estate_metrics`, `private_credit_metrics`, `private_equity_metrics`), scoring rubric (§9 in analysis doc), fund-research mission pack (§8).

## People / Actors

- Fully automated, no human in the loop.

## Timing

- `[UNKNOWN: exact duration — not stated in source; runs as "Pass 1" before other extraction within `processPitchDeckWorkflow`]`

## Problems / Gaps / Workarounds

- **Three overlapping, unreconciled taxonomies exist in the codebase:**
  1. The extraction-schema enum above (`primaryAssetClass`).
  2. A richer `capital_structure × asset_class × sub_asset_class` taxonomy in `schemas/common/taxonomy.ts` (e.g., Real Estate has 22 sub-classes).
  3. A separate `asset_class.schema.json` with snake_case values and a `primary_strategy` enum (`pe_leveraged_buyout`, `vc_early_stage`, `credit_direct_lending`, etc.), plus `fund_structure` (direct/fund-of-funds/secondary/co-investment) and `is_esg_impact`.
  - These represent different eras of the same concept — not reconciled into one source of truth. Downstream code that fuzzy-matches asset class (see scoring observation) has to normalize across this fragmentation.
- Getting this classification wrong scores every downstream judgment against the wrong yardstick — no correction mechanism observed downstream if Pass 1 is wrong.

## Open Questions

- Is there a plan/timeline to consolidate the three asset-class taxonomies into one?
- What happens if `primaryAssetClass` returns `Unknown` — which schemas/rubric apply then? `[UNKNOWN]`
