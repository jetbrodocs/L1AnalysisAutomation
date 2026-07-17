---
title: "Process: Web Research Dispatch (Jina / Exa)"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [pipeline, jina, exa, cross-cutting]
---

# Process: Web Research Dispatch (Jina / Exa)

Built from: [obs-web-research-providers](../10-observations/obs-web-research-providers.md). Shared dispatch flow invoked by every person-research task (proc-people-deep-research) and fund-research task (proc-fund-deep-research) whenever a claim can't be resolved from the fund's own uploaded documents.

## Process Overview

- **Purpose**: Route a research question to internal knowledge first, then the correct external web-research provider, then normalize the output.
- **Trigger**: A research task (person or fund) needs to answer a question.
- **End condition**: Normalized JSON + Markdown report returned to the calling task.

## Roles Involved

- Fully automated (`src/trigger/research/provider.ts` → `dispatcher.ts`).

## Process Steps

1. **Internal-first check.** Query the fund's internal Gemini File Search store (`queryTaskResponse`).
   - **If the fact is already verified from an uploaded document:** use it, no external call happens. Process ends here.
   - **If not found:** continue to step 2.
2. **Provider routing (decision point).** Dispatcher checks the task's `provider` field.
   - **Default (unset) or `jina`** → step 3.
   - **`exa`** → step 4.
3. **Jina path** (`jina/deepsearch.ts`, `performJinaResearch`):
   - Autonomous multi-page web crawl per question, tuned by `reasoning_effort`/`token_budget` (person research: 1M budget, high reasoning; some PE fund missions: 2M).
   - Two calls fire per task: one schema-constrained (forces response into task's output schema), one parallel markdown-only (so info that doesn't cleanly fit the schema isn't silently dropped).
   - Lighter sibling `quick-search.ts` (Jina Search API) backs `preliminarySearchAgentTask` for fast snippet-level disambiguation sweeps.
   - Citations for this path come from step 5's cleanup/re-citation pass, not natively from Jina.
4. **Exa path** (`exa/deepsearch.ts`, `performExaDeepResearch`):
   - Effort maps to 3 tiers: `exa-research-fast`, `exa-research`, `exa-research-pro`.
   - Returns actual source list natively (`references`, `visitedURLs`, `readURLs`) — feeds the citation trail directly.
5. **Cleanup pass** (both paths converge here). Raw provider output passed through a Gemini cleanup call that strips citation-ID artifacts, normalizes tone, and re-cites — so every downstream report reads uniformly regardless of which provider produced it.
6. Normalized JSON + Markdown returned to the calling task (person research or fund research).

### Fallback Path

- `acquireL1SecDocumentsTask` (SEC diligence, proc-sec-filing-diligence step 1) also falls back to Jina web search when entity categorization can't be resolved from the internal knowledge base — same steps 3/5 apply.

## Systems and Tools

- `src/trigger/research/provider.ts`, `dispatcher.ts` (`executeDeepResearch`/`deepResearchTask`).
- `jina/deepsearch.ts`, `quick-search.ts`, `exa/deepsearch.ts`.

## Timing / Scale

- Idempotency key hashed from `date + taskIdentifier + entity-name hash + token budget` — re-running within the same day doesn't re-spend on identical research.
- Fund research batches aggressively (10 entities × 10 principals × 20 prompts, all parallel) — see proc-fund-deep-research.

## Known Issues

- Citation provenance differs structurally: Exa citations are native source URLs; Jina citations are synthesized post-hoc in the cleanup pass — a Jina-sourced citation is one step further removed from the original crawl.

## Open Questions

- Documented cost/quality rationale for provider choice per task, or historical accretion? `[UNKNOWN]`
