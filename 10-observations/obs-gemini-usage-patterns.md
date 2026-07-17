---
title: "Observation: Gemini — Cross-Cutting Usage Patterns"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [pipeline, gemini, patterns, cross-cutting]
---

# Observation: Gemini — Cross-Cutting Usage Patterns

Source: `00-inbox/pipeline-architecture.md` §11, audited against codebase. Cross-cutting reference, not a single pipeline stage — describes how Gemini (`@google/genai`) is used across every stage above.

## Activity

Five distinct Gemini usage patterns recur throughout the pipeline, each suited to a different kind of task, rather than one uniform "call the LLM" approach.

## Patterns Observed

1. **Native structured output** — every extraction/classification call sets strict `responseSchema` (`responseMimeType: application/json`), built via `zodToJsonSchema`. Model cannot return free text. Used for: document classification (§2), fund classification (§3), every extraction schema (§4), key-principal verification (§6), final structured output of every scoring/L1 call (§9-10).
2. **Two-step "text first, structure second"** — for every extraction schema: (1) raw PDF → markdown report with forced verbatim quoting + page citations; (2) second call over that markdown with `responseSchema` set → structured JSON. Exists specifically to stop the model from inventing/miscalculating numbers while simultaneously reading and formatting.
3. **Extract-then-normalize for every number** — layered on Pattern 2. Every monetary/%/duration/multiplier field captures `source_number_text` verbatim first; a separate smaller call (`gemini-3.1-flash-lite`, `parseMeasurementsInPayload` in `schema-extraction.ts`) parses into `{amount, magnitude}` or a range. No arithmetic happens inside the same call that's reading prose.
4. **Per-fund File Search grounding (RAG)** — a Gemini File Search Store opens the moment a document is classified (§2); every subsequent document uploads into it. Every later stage (scoring analysts, L1 sections, research context agents) queries this store first via file-search-grounded calls before falling back to open-web research. `internal-research-context-agent.ts` and `queryTaskResponse` are the query mechanisms.
5. **Dual-analyst-then-synthesize** — used for every scored criterion (§9) and every L1 memo section (§10): two parallel analyst calls (one lenient/deep-context, one strict/mechanical, both capped at 10-20 search queries, `[NO_RELEVANT_DATA_FOUND]` escape hatch), then a third synthesis call reconciles into final structured JSON with evidence, confidence, data gaps, red flags.

## Model Tiering Observed

- `gemini-3.1-flash-lite` — high-volume/cheap calls: document classification, numeric normalization, key-principal verification, both scoring-analyst passes.
- `gemini-3.5-flash` (thinking: high) — heavier per-schema extraction, fund classification.
- `gemini-3.1-pro-preview` + `gemini-2.5-pro` (dual pass) — L1 memo's analyst stage; `gemini-3.1-pro-preview` alone does the synthesis. Most expensive, highest-stakes calls, reserved for the final client-facing output.

## Problems / Gaps / Workarounds

- Pattern 2/3 exist explicitly because raw-PDF-to-JSON-in-one-shot was a known failure mode (model inventing/miscalculating numbers) — this is a designed-around limitation, not a stylistic preference.
- Model tiering is a deliberate cost/quality tradeoff — cheapest model reserved for high-volume mechanical tasks, most expensive reserved for the final IC-facing synthesis.

## Open Questions

- None outstanding beyond what's captured in the per-stage observations (scoring, L1) where specific wiring/staleness issues live.
