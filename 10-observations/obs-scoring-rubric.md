---
title: "Observation: Scoring & Rubric Analysis"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [pipeline, scoring, rubric, gemini, veto, dead-code]
---

# Observation: Scoring & Rubric Analysis

Source: `00-inbox/pipeline-architecture.md` §9, audited against codebase. This is described as the core of the platform.

## Activity

Every fund is scored on ~20 criteria across 4 categories, criteria set varying by asset class, using a dual-analyst-then-synthesize pattern. Each criterion lands on a fixed 5-tier ordinal scale; some criteria double as automatic veto triggers.

## Inputs

- Fund's normalized asset class (from §3).
- Fund's document store (Gemini File Search grounding).
- ~57 TOML files (`score-<Letter><Number>-<slug>.toml`) — rubric stored as data, not code.

## Outputs

- Per-dimension categorical score: `Exemplary → Strong → Adequate → Weak → Unacceptable`.
- Per-dimension structured JSON: `score_category`, `confidence_score` (0-100), `evidence[]`, `qualitative_explanation`, `data_gaps[]`, `red_flags[]`, `one_line_verdict`, `citations[]`, `synthesis_notes` (internal-only).
- No numeric roll-up — `report.scores[]`, markdown report per category, uploaded, POSTed to `/api/webhooks/score_sync`.

## Systems

- Rubric matrix: (dimension slot) × (asset class). 4 categories:
  - **A — Operational Quality & Viability** (ranking 1)
  - **B — Investment Sourcing & Value Creation** (ranking 2)
  - **C — Capital & Risk Mechanics** (ranking 3)
  - **D — Fund Operations & Compliance** (ranking 4)
  - Up to 5 numbered slots per letter (A1-A5, B1-B4, C1-C4, D1-D4), each with multiple asset-class-specific variants (e.g., B1 has separate files for RE/HF/PE-VC-Credit-Infra).
- `full-scoring-workflow.ts` (`workflow-full-scoring`) — sole live orchestrator: reads all 57 files, matches `constraints.asset_class` array against fund's normalized asset class, groups matched configs by letter, dispatches at most 4 category-level tasks via `scoreCategoryAgent.batchTriggerAndWait`.
- `cleanString()` (`full-scoring-workflow.ts` lines 64-70) — lowercases + strips non-alphanumerics from both TOML asset-class values and fund's classified asset class, special-cases two aliases: `hedgefund → hedgefunds`, `privatedebt → privatecredit`. Confirmed necessary against actual TOML data (constraint values stored plural/capitalized, e.g. `"Hedgefunds"`).
- Execution per category task, **3 Gemini calls**:
  1. Pass 1a + 1b in parallel — both call `gemini-3.1-flash-lite`, one lenient/deep-context, one "strict, ruthless compliance analyst" applying thresholds mechanically. Both output markdown, capped at 10 (single) or 20 (category-batch) search queries, `[NO_RELEVANT_DATA_FOUND]` escape hatch.
  2. Pass 2 — synthesis call ("Senior Investment Analyst") reconciles both, emits final structured JSON.
- **Total per fund: up to 4 category tasks × 3 calls = up to 12 Gemini calls per scoring run.**
- `repe-breaking-points.json` (Real Estate PE only) — quantitative table keyed by risk profile × property type: expected cash-on-cash yield, DSCR multiple, net IRR, LTV ranges, economic-outlook block, `breaking_point_thresholds` (hard min/max, e.g., DSCR min 1.2x, LTV max 65%, min net IRR 5%, min CoC 3.5%). Generated via `mix decode_repe_matrix` (`lib/mix/tasks/decode_repe_matrix.ex`) from an external, dated CSV source — meant to be periodically refreshed, not static.

## People / Actors

- Fully automated. Elixir side maps dimension codes (A1, B2, etc.) to human labels via a hardcoded 20-item `flat_dims` list.

## Timing

- `[UNKNOWN: per-category-task duration]`

## Problems / Gaps / Workarounds

- **`Unacceptable` frequently doubles as an automatic VETO** — hard-fail conditions (e.g., no key-person clause, no management-fee offset, fraudulent service providers) written directly into rubric text, not a separate rule engine.
- **Stale prompt copy, confirmed harmless**: the prompt text itself labels the two analyst passes "3.1-Pro" and "2.5-Pro" (lines 289-293) — leftover from an earlier version that used two different models. Both passes actually call the same `gemini-3.1-flash-lite` model today. The dual-*pass* structure is real and functioning; only the model-name framing in the prompt is stale.
- **Dead code, confirmed zero call sites**: `src/trigger/agents/score-agent.ts` (`scoreDimensionAgent`) is a near-duplicate of the asset-class matcher, but has **drifted** — missing the `privatedebt→privatecredit` alias. Doesn't matter in practice: zero call sites anywhere in the codebase. Abandoned single-dimension (non-batched) fork of logic `score-category-agent.ts` alone now implements live.
- **Wiring gap, confirmed in code**: `master-workflow.ts` calls `fullScoringWorkflow.triggerAndWait` with only `fundName`, `fundId`, `workflowRunId`, `masterData`, `teamData`, `isDryRun` — does NOT pass `fileSha256`, `kbStoreName`, or `cacheControl`, all of which the payload type accepts.
  - Omitting `fileSha256` → idempotency key's file-hash segment always resolves to literal string `"no-sha"` (`src/lib/idempotency.ts`), collapsing that part of the dedup mechanism to a constant.
  - Omitting `kbStoreName` → forces a fresh file-search store lookup instead of reusing one resolved earlier in the pipeline.
  - **More significant: the SEC/deep-diligence output (`ddResult`, computed one step earlier in `master-workflow.ts` Step 3) is never included in the scoring payload at all.** Scoring receives only `masterData`/`teamData` from deck extraction — not the diligence findings sitting right next to it in the same workflow run.
- Elixir `flat_dims` list hardcodes exactly A1-A5/B1-B5/C1-C5/D1-D5 (20 items) — "slightly diverges from the actual variable-per-asset-class file set" per source doc, since not every asset class has all 5 slots per letter.
- `category_rankings.json` governs display order only — no weighted composite score exists anywhere in the system.

## Open Questions

- Should `score-agent.ts` be deleted given zero call sites, or is it kept intentionally as a reference/fallback implementation?
- Is the missing `ddResult` (SEC/diligence output) in the scoring payload a known gap the team intends to fix, or an accepted design limitation?
- What breaks, if anything, from `flat_dims` diverging from the actual variable dimension-set-per-asset-class?
