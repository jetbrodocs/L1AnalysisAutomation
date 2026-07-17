---
title: "Process: Scoring & Rubric Analysis"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [pipeline, scoring, rubric]
---

# Process: Scoring & Rubric Analysis

Built from: [obs-scoring-rubric](../10-observations/obs-scoring-rubric.md). Sub-process of step 6.4 (`fullScoringWorkflow`) in [proc-deal-analysis-pipeline](proc-deal-analysis-pipeline.md), runs after [proc-fund-deep-research](proc-fund-deep-research.md). Described in source material as the core of the platform.

## Process Overview

- **Purpose**: Score the fund on ~20 criteria across 4 categories, criteria set varying by asset class, using a dual-analyst-then-synthesize pattern.
- **Trigger**: `master-workflow.ts` calls `fullScoringWorkflow.triggerAndWait` with `fundName`, `fundId`, `workflowRunId`, `masterData`, `teamData`, `isDryRun`.
- **End condition**: per-category markdown reports uploaded, POSTed to `/api/webhooks/score_sync`.

## Roles Involved

- Fully automated.

## Inputs and Outputs

- **Input**: fund's normalized asset class, fund's document store, ~57 rubric TOML files.
- **Output**: per-dimension categorical scores + structured JSON (`score_category`, `confidence_score`, `evidence[]`, etc.), no numeric roll-up.

## Process Steps

1. `full-scoring-workflow.ts` reads all 57 `score-<Letter><Number>-<slug>.toml` files.
2. **Asset-class matching (decision point).** `cleanString()` normalizes both the TOML's `constraints.asset_class` values and the fund's classified asset class (lowercase, strip non-alphanumerics), applies two aliases (`hedgefund → hedgefunds`, `privatedebt → privatecredit`). Only configs whose `constraints.asset_class` matches the fund's asset class are kept.
3. Matched configs grouped by letter (regex `/^score-([A-D])/i`) — 4 categories: A (Operational Quality & Viability), B (Investment Sourcing & Value Creation), C (Capital & Risk Mechanics), D (Fund Operations & Compliance).
4. Dispatch **at most 4 category-level tasks** via `scoreCategoryAgent.batchTriggerAndWait` — fewer if a category has zero matched dimensions for this asset class.
5. **Per category task, 3 Gemini calls:**
   - 5a. Pass 1a + 1b run in parallel (`Promise.all`), both call `gemini-3.1-flash-lite` over the fund's document store via file-search grounding:
     - Pass 1a — lenient/deep-context analyst.
     - Pass 1b — "strict, ruthless compliance analyst": must mechanically apply thresholds without benefit of the doubt (breached limit ⇒ must assign that tier even if fund beat benchmark elsewhere; missing clause ⇒ graded per rubric).
     - Both output markdown (Qualitative Explanation / Evidence / Data Gaps / Red Flags), capped at 10 (single) or 20 (category-batch) search queries, `[NO_RELEVANT_DATA_FOUND]` escape hatch.
   - 5b. Pass 2 — synthesis call ("Senior Investment Analyst") reconciles both analysts, emits final structured JSON: `score_category` (5-tier: Exemplary/Strong/Adequate/Weak/Unacceptable), `confidence_score` (0-100), `evidence[]`, `qualitative_explanation`, `data_gaps[]`, `red_flags[]`, `one_line_verdict`, `citations[]`, `synthesis_notes` (internal-only).
6. **VETO check (decision point, embedded in rubric text, not a separate rule engine).** If a criterion lands `Unacceptable` and the rubric text marks it as a hard-fail condition (e.g. no key-person clause, no management-fee offset, fraudulent service providers) → automatic VETO, regardless of other criteria's strength.
7. **Real Estate PE only — quantitative gate.** `repe-breaking-points.json` (keyed by risk profile × property type, refreshed via `mix decode_repe_matrix` from external CSV) provides hard min/max cutoffs (DSCR, LTV, net IRR, cash-on-cash) checked against the deal's underwriting numbers. Reference data consulted during prompting — not a hard programmatic gate — layered on top of the qualitative VETO triggers.
8. **Total cost per fund: up to 4 category tasks × 3 calls = up to 12 Gemini calls.**
9. `fullScoringWorkflow` collects per-dimension results into `report.scores[]`, generates markdown per category, uploads, POSTs to `/api/webhooks/score_sync`.
10. Elixir side maps dimension codes (A1, B2, etc.) to human labels via hardcoded 20-item `flat_dims` list, stores each as `create_score` row keyed by `document_id`/`dimension`/`run_id`.
11. Process rejoins main flow at step 6.5 (L1 memo) — see known wiring gap below.

## Systems and Tools

- `full-scoring-workflow.ts` (`workflow-full-scoring`), `score-category-agent.ts`, `cleanString()`.
- `gemini-3.1-flash-lite` (both analyst passes and synthesis).
- `repe-breaking-points.json`, `mix decode_repe_matrix`.
- `category_rankings.json` — governs display order only, not a scoring formula.

## Known Issues

- **Confirmed wiring gap.** `master-workflow.ts` does not pass `fileSha256`, `kbStoreName`, or `cacheControl` into this workflow, though the payload type accepts all three.
  - Missing `fileSha256` → idempotency key's file-hash segment always resolves to literal `"no-sha"` — collapses that part of dedup to a constant.
  - Missing `kbStoreName` → forces a fresh file-search store lookup instead of reusing one resolved earlier in the pipeline.
  - **The SEC/deep-diligence output (`ddResult`, from step 6.1c) is never included in this workflow's payload at all** — step 5 above scores the fund blind to the diligence findings computed one step earlier in the same run.
- **Confirmed dead code.** `src/trigger/agents/score-agent.ts` (`scoreDimensionAgent`) — near-duplicate matcher, missing the `privatedebt→privatecredit` alias, has drifted. Zero call sites anywhere. Abandoned single-dimension fork; `score-category-agent.ts` alone implements this live.
- **Stale prompt copy, confirmed harmless.** Prompt text in `score-category-agent.ts` lines 289-293 labels the two analyst passes "3.1-Pro" and "2.5-Pro" — leftover from an earlier version. Both passes actually call `gemini-3.1-flash-lite` today; only the naming in the prompt is stale.
- Elixir `flat_dims` (20 items, A1-A5/B1-B5/C1-C5/D1-D5) slightly diverges from the actual variable-per-asset-class dimension set.
- No weighted composite score exists anywhere in the system — `category_rankings.json` is display order only.

## Open Questions

- Delete `score-agent.ts` given zero call sites, or keep as reference?
- Is the missing `ddResult` a known/prioritized fix?
- What breaks (if anything) from `flat_dims` diverging from actual dimension count?
