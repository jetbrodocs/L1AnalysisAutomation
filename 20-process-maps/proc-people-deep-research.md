---
title: "Process: People Deep Research"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [pipeline, research, people]
---

# Process: People Deep Research

Built from: [obs-people-deep-research](../10-observations/obs-people-deep-research.md). Sub-process of step 6.2b in [proc-deal-analysis-pipeline](proc-deal-analysis-pipeline.md), runs after [proc-key-personnel-intelligence](proc-key-personnel-intelligence.md).

## Process Overview

- **Purpose**: Research each team member to the depth their role tier warrants, then merge into a single dossier per person.
- **Trigger**: Personnel classification (previous sub-process) complete for a person.
- **End condition**: Consolidated dossier (`masterProfile`, `individualReports`, run/citation metadata) persisted to Tigris + FTS parquet index.

## Roles Involved

- Fully automated (`personResearchWorkflow`).

## Inputs and Outputs

- **Input**: person's role tier (task count), fund's shared Gemini File Search store.
- **Output**: merged per-person dossier.

## Process Steps

1. **Context phase.** Context agents query the fund's shared Gemini File Search store for relevant upstream outputs, cached via `computeLlmCacheKey`.
2. **Biographical grounding.** "Master Biographical Profile" agent grounds against internally uploaded documents.
3. **Research dispatch**, batch-triggered across the person's tier task count (3/8/10 per proc-key-personnel-intelligence):
   - 3a. `preliminarySearchAgentTask` — first pass.
   - 3b. `deepResearchTask` — remaining tasks, across up to 10 categories: preliminary-search, generic, employment-history, regulatory-compliance, reputation, credentials, governance, performance, forensic-regulatory, oba-conflicts. Each category has its own exclusion rules to avoid overlapping with adjacent categories.
4. Per task, internal knowledge base queried first (`queryTaskResponse`) to prepend verified facts before dispatching to external search (see [proc-web-research-providers](proc-web-research-providers.md) for the dispatch mechanics: Jina default, Exa alternate).
5. Downstream tasks (regulatory-compliance/reputation/governance/forensic/OBA) receive prior outputs as `prompt_append` context via `templates.toml` Mustache injection.
6. **Consolidation** (`compile-person-dossier`):
   - 6a. Dossier 1 — Gemini context-cache synthesis of all structured JSON reports, converted to markdown via `jsonToCustomMarkdown`.
   - 6b. Dossier 2 — Gemini File Search "Interactions API" over raw source documents with citation extraction.
   - 6c. Final merge, template-driven rules: comprehensiveness over summarization, preserve all quotes/citations, dedupe only on direct factual duplicates, mandatory "Source Audit & Report Map" section.
7. Output persisted: `masterProfile`, `individualReports`, run/citation metadata → Tigris + FTS parquet index.
8. Process rejoins main flow at step 6.3 (fund deep diligence) — see [proc-deal-analysis-pipeline](proc-deal-analysis-pipeline.md) known sequencing issue (6.2/6.3 run sequentially, not in parallel).

## Systems and Tools

- `personResearchWorkflow`, `workflow-phases.ts`.
- `dispatcher.ts` (Jina default, Exa alternate) — see [proc-web-research-providers](proc-web-research-providers.md).
- `compile-person-dossier`, `templates.toml`.

## Known Issues

- No numeric confidence score anywhere in this process — verification is entirely qualitative (reasoning strings + source audit).
- Report tone normalized post-hoc across providers, since Jina and Exa outputs read differently at the source.

## Open Questions

- Total dossier generation time per person, end to end? `[UNKNOWN]`
