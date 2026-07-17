---
title: "Observation: People Deep Research"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [pipeline, research, jina, exa, dossier]
---

# Observation: People Deep Research

Source: `00-inbox/pipeline-architecture.md` §7, audited against codebase.

## Activity

Per-person, per-role-tier research execution (`personResearchWorkflow`) that runs the 10-category research taxonomy (see personnel-intelligence observation) against internal documents and the open web, then consolidates into a merged dossier.

## Inputs

- Person's role tier (§6) — determines task count (3, 8, or 10).
- Fund's shared Gemini File Search store.

## Outputs

- 10 research-category outputs (all Jina-driven by default, 1M token budget, high reasoning): preliminary-search, generic, employment-history, regulatory-compliance, reputation, credentials, governance, performance, forensic-regulatory, oba-conflicts.
- Consolidated dossier: `masterProfile`, `individualReports`, run/citation metadata, files persisted to Tigris plus an FTS parquet index.

## Systems

- Phases (`workflow-phases.ts`):
  1. Context agents query fund's Gemini File Search store for relevant upstream outputs (cached via `computeLlmCacheKey`).
  2. "Master Biographical Profile" agent grounds against internally uploaded documents.
  3. Research dispatch: `preliminarySearchAgentTask` (first pass), `deepResearchTask` (rest), batch-triggered across the person's tier.
- `dispatcher.ts` routes to Jina (default) or Exa (`exa-research/-research-fast/-research-pro` tiers by effort).
- Internal knowledge base queried first (`queryTaskResponse`) to prepend verified facts before external search.
- `compile-person-dossier`: merges Dossier 1 (Gemini context-cache synthesis of structured JSON reports → markdown via `jsonToCustomMarkdown`) and Dossier 2 (Gemini File Search "Interactions API" over raw source docs with citation extraction). Merge template rules: comprehensiveness over summarization, preserve all quotes/citations, dedupe *only* on direct factual duplicates, mandatory "Source Audit & Report Map" section.
- `templates.toml` — Mustache snippets injecting upstream outputs into downstream prompts. Shared "extract, don't score" directive across all prompts — judgment deferred to §6 classification and consolidation.

## People / Actors

- Fully automated. No numeric confidence score — verification is qualitative (reasoning strings + source audit); forensic red flags surface as dedicated sections.

## Timing

- `[UNKNOWN: per-person total research duration]`

## Problems / Gaps / Workarounds

- Each of the 10 research categories has its own exclusion rules specifically to avoid overlap between categories (e.g., `employment-history` excludes board/advisory roles which are covered by `governance`) — implies overlap was a known failure mode designed around.
- `regulatory-compliance` explicitly distinguished from `forensic-regulatory` (routine compliance footprint vs. actual enforcement/allegations) — a deliberate severity split, not redundant categories.
- Report tone "normalized post-hoc" — Jina and Exa outputs read differently at the source and are reconciled after the fact, not at generation time.

## Open Questions

- What is the actual dossier generation time per person, end to end (across all applicable research tasks)?
