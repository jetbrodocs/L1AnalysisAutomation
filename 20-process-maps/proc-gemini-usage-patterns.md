---
title: "Process: Gemini Call-Pattern Selection"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [pipeline, gemini, cross-cutting]
---

# Process: Gemini Call-Pattern Selection

Built from: [obs-gemini-usage-patterns](../10-observations/obs-gemini-usage-patterns.md). Not a stage-specific flow — this is the decision logic that determines *which* of 5 recurring Gemini call patterns a given pipeline stage uses. Referenced from nearly every other sub-process (extraction, scoring, L1, research).

## Process Overview

- **Purpose**: Describe how a task's shape (extraction vs. judgment vs. numeric parsing) determines which Gemini calling pattern and model tier it uses.
- **Trigger**: Any point in the pipeline where a Gemini call is needed.
- **End condition**: N/A — this is a reusable selection pattern invoked throughout the pipeline, not a single terminating flow.

## Roles Involved

- Fully automated; this is architecture/dispatch logic, not a human-facing process.

## Decision Flow — Which Pattern Applies

1. **Is the task "read a document and produce structured fields"?**
   - **Yes, and it's a first-time schema extraction from raw PDF** → **Pattern 2 (text-first-then-structure)**: (a) raw PDF → markdown report with forced verbatim quoting + page citations; (b) second call over that markdown with `responseSchema` set → structured JSON. Used by: document classification (step 3, proc-document-ingestion-classification), fund classification (proc-fund-classification), every extraction schema (proc-data-extraction).
   - **Yes, and it's parsing an already-extracted numeric string** → **Pattern 3 (extract-then-normalize)**: `source_number_text` captured verbatim first (inside Pattern 2's structure step), then a separate smaller call (`gemini-3.1-flash-lite`) parses into `{amount, magnitude}` or a range. Layered on top of Pattern 2, not standalone.
2. **Does the task need to cite specific evidence from the fund's own uploaded documents?**
   - **Yes** → **Pattern 4 (File Search grounding / RAG)**: query the fund's Gemini File Search store first via `queryTaskResponse`/`internal-research-context-agent.ts`, before falling back to open-web research (proc-web-research-providers).
3. **Is the task a scored judgment or a memo section that needs both leniency-checking and strictness-checking?**
   - **Yes** → **Pattern 5 (dual-analyst-then-synthesize)**: two parallel analyst calls (lenient/deep-context + strict/mechanical, both capped 10-20 search queries, `[NO_RELEVANT_DATA_FOUND]` escape hatch), then a third synthesis call reconciles into final structured JSON. Used by: every scoring criterion (proc-scoring-rubric), every L1 memo section (proc-l1-analysis).
4. **Regardless of pattern**: every call setting `responseSchema` uses **Pattern 1 (native structured output)** — `zodToJsonSchema` converts the app's Zod schema, model cannot return free text outside the defined fields.
5. **Model tier selected** based on task's cost/stakes profile:
   - `gemini-3.1-flash-lite` — high-volume/cheap: document classification, numeric normalization, key-principal verification, both scoring-analyst passes.
   - `gemini-3.5-flash` (thinking: high) — heavier per-schema extraction, fund classification.
   - `gemini-3.1-pro-preview` + `gemini-2.5-pro` (dual pass), synthesis by `gemini-3.1-pro-preview` alone — L1 memo analyst stage. Most expensive, reserved for the final client-facing output.

## Systems and Tools

- `zodToJsonSchema`, `@google/genai`.
- `schema-extraction.ts` (`parseMeasurementsInPayload`).
- `internal-research-context-agent.ts`, `queryTaskResponse`.

## Known Issues

- Pattern 2/3's split exists specifically because raw-PDF-to-JSON-in-one-shot was a known failure mode (model inventing/miscalculating numbers) — a designed-around limitation, not stylistic preference.
- Model tiering is a deliberate cost/quality tradeoff, not uniform model use across the pipeline.

## Open Questions

- None beyond what's captured in the per-stage wiring gaps (proc-scoring-rubric, proc-l1-analysis) where Pattern 5's `consolidatedInfo` input is sometimes empty due to upstream wiring gaps.
