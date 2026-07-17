---
title: "Observation: Jina + Exa — Web Research Provider Usage"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [pipeline, jina, exa, web-research, cross-cutting]
---

# Observation: Jina + Exa — Web Research Provider Usage

Source: `00-inbox/pipeline-architecture.md` §12, audited against codebase. Cross-cutting reference shared by people research (§7) and fund research (§8).

## Activity

When a claim can't be resolved from the fund's own uploaded documents, the pipeline leaves the private knowledge base and searches the open web through a single shared dispatcher.

## Dispatch Order

1. Query fund's internal Gemini File Search store first (`queryTaskResponse`) — if already verified from an uploaded document, used with no external call.
2. If not found, dispatcher routes to a provider based on the task's `provider` field (defaults to Jina).
3. Raw provider output passed through a Gemini cleanup call that strips citation-ID artifacts, normalizes tone, and re-cites — so every downstream report reads uniformly regardless of source provider.

## Systems

- `src/trigger/research/provider.ts` → `dispatcher.ts` (`executeDeepResearch`/`deepResearchTask`) — shared by every person-research and fund-research task.
- **Jina** (default): `jina/deepsearch.ts` (`performJinaResearch`) — autonomous multi-page web crawl per question, tuned by `reasoning_effort`/`token_budget` (person research: 1M budget, high reasoning; some PE fund missions go to 2M). Two calls fire per task: one schema-constrained, one parallel markdown-only — so info that doesn't fit the schema isn't silently dropped. Lighter sibling `quick-search.ts` (Jina Search API) backs `preliminarySearchAgentTask`.
- **Exa** (alternate): `exa/deepsearch.ts` (`performExaDeepResearch`) — used where a task explicitly requests it. Effort maps to `exa-research-fast`, `exa-research`, `exa-research-pro`. Returns actual source list (`references`, `visitedURLs`, `readURLs`) feeding the citation trail directly — Jina's citations instead come from the cleanup pass's re-citation step.
- Provider choice is a per-task configuration, not a stage-level architectural split.
- `acquireL1SecDocumentsTask` (§5) also falls back to Jina web search when entity categorization can't resolve from internal KB.

## Timing / Scale

- Idempotency key hashed from `date + taskIdentifier + entity-name hash + token budget` — re-running an analysis within the same day doesn't re-spend on identical research.
- `fund-deep-diligence.ts` batches aggressively: up to 10 entities in parallel × up to 10 principals in parallel × 20 prompts in parallel, all fired in a single `batchTriggerAndWait` call rather than sequential loops — cited as what keeps a full diligence pass to hours rather than days.

## Problems / Gaps / Workarounds

- Citation provenance differs structurally between providers: Exa gives real source URLs natively; Jina's citations are synthesized post-hoc by the cleanup pass's re-citation step. Not flagged as a bug, but worth knowing when auditing citation trustworthiness — a Jina-sourced citation is one step further removed from the original crawl than an Exa one.

## Open Questions

- Is there a cost comparison between Jina and Exa in production, and does provider choice per task follow a documented cost/quality rationale, or historical accretion?
