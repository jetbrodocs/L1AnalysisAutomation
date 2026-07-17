---
title: "Process: Fund Classification (Pass 1)"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [pipeline, classification]
---

# Process: Fund Classification (Pass 1)

Built from: [obs-fund-classification](../10-observations/obs-fund-classification.md). Sub-process of step 6.1a in [proc-deal-analysis-pipeline](proc-deal-analysis-pipeline.md).

## Process Overview

- **Purpose**: Determine asset class, structure, and manager maturity before any other extraction runs — gates every downstream schema/rubric/mission-pack choice.
- **Trigger**: `processPitchDeckWorkflow` begins (first sub-step, runs before extraction).
- **End condition**: `primaryAssetClass`, `isOpenEnded`, `managerClassification` written to the fund record.

## Roles Involved

- Fully automated. No human review.

## Inputs and Outputs

- **Input**: full pitch-deck PDF, via Gemini file API (not the RAG store).
- **Output**: `primaryAssetClass`, `hedgeFundStrategy` (conditional), `isOpenEnded`, `classificationReasoning`, `managerClassification` + reasoning.

## Process Steps

1. `processPitchDeckWorkflow` loads full pitch-deck PDF via Gemini file API.
2. One LLM call (Gemini 3.5 Flash, high thinking level) runs the `fund_overview_and_terms` schema, forced chain-of-thought.
3. Model returns `primaryAssetClass` (enum: Private Equity, Hedge Fund, Venture Capital, Real Estate, Private Credit, Fund of Funds, Infrastructure, Unknown), plus conditional `hedgeFundStrategy`, `isOpenEnded`, `classificationReasoning`, `managerClassification` (Emerging/Transitioning/Established) + reasoning.
4. **Downstream gate (decision point)** — `primaryAssetClass` determines:
   - Which asset-class-specific extraction schema fires in step 6.1b (`hedge_fund_metrics` / `venture_capital_metrics` / `real_estate_metrics` / `private_credit_metrics` / `private_equity_metrics`).
   - Which scoring rubric variant applies in step 6.4.
   - Which fund-research mission pack fires in step 6.3.
5. Result persists on the fund record; process continues into data extraction (proc-data-extraction).

## Systems and Tools

- Gemini 3.5 Flash (thinking: high), `fund_overview_and_terms` schema.
- Downstream consumers: extraction schema selector, scoring rubric matcher (`cleanString()` in `full-scoring-workflow.ts`), fund-research mission-pack selector.

## Known Issues

- Three overlapping, unreconciled asset-class taxonomies exist in the codebase (this enum, `schemas/common/taxonomy.ts`, `asset_class.schema.json`) — see [obs-fund-classification](../10-observations/obs-fund-classification.md).
- No observed correction mechanism downstream if this classification is wrong — every later stage scores against whatever yardstick this step picked.

## Open Questions

- What happens when `primaryAssetClass` returns `Unknown` — which schema/rubric applies? `[UNKNOWN]`
- Plan to consolidate the three taxonomies?
