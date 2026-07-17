---
title: "Process: Fund Deep Research"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [pipeline, research, fund]
---

# Process: Fund Deep Research

Built from: [obs-fund-deep-research](../10-observations/obs-fund-deep-research.md). Sub-process of step 6.3 (`fundDeepDiligenceWorkflow`) in [proc-deal-analysis-pipeline](proc-deal-analysis-pipeline.md), runs after [proc-people-deep-research](proc-people-deep-research.md) (sequentially, not in parallel — see main flow known issue).

## Process Overview

- **Purpose**: Research the fund itself (baseline + asset-class-specific), then run an automated "skeptic" gap-analysis pass that can trigger a second round of targeted research.
- **Trigger**: `fundDeepDiligenceWorkflow` starts; explicitly skips re-running SEC diligence (already done in step 6.1c).
- **End condition**: "FORENSIC MASTER DOSSIER" markdown synced to Tigris + Gemini File Search.

## Roles Involved

- Fully automated.

## Inputs and Outputs

- **Input**: fund/GP/management-company entities, key principals, `primaryAssetClass`, `isEmerging` flag.
- **Output**: forensic master dossier; `redFlagsDetected[]`, `caseNumbers[]`, `tier2ServiceProviders[]`, `missingDataForWebSearch[]`.

## Process Steps

1. **Baseline task set** (6 core + 2 extended) dispatched via `fund-deep-diligence.ts`:
   - `strategy-thesis` → `performance-returns` → `regulatory-disclosures` → `infrastructure-service-providers` (depends on regulatory-disclosures) → `competitive-benchmarking` (depends on strategy + performance) → `governance-adverse-media`.
   - Extended: `market-research`, `competitor-analysis`.
2. **Asset-class mission pack selected** by `primaryAssetClass` (decision point):
   - Private Credit (4 missions): `fund-mechanics-baseline`, `legal-odd`, `market-and-sector-dd`, `team-pedigree-dd`.
   - Real Estate (4 missions, tuned for REPE).
   - Private Equity (7 missions): deal-attribution/scalability, macro capital-overhang, human-capital-continuity, institutional litigation, skeptical strategy verification (2M token budget), regulatory/SEC-action audit, employment/HR-risk, reputational-risk/background.
3. Batch dispatch: `fund-deep-diligence.ts` builds a flat batch across entities (fund + GP/mgmt company, up to 10 parallel) and principals (up to 10 parallel × 20 prompts parallel), fired in one `batchTriggerAndWait` call. `single-fund-research-mission.ts` runs mission packs one at a time, keyed by `assetClass/missionId`.
4. Each task routed via `dispatcher.ts` (`executeDeepResearch`) — internal KB grounding first, then external provider (see [proc-web-research-providers](proc-web-research-providers.md)), then Gemini sanitization to JSON + Markdown.
5. **Critical Audit Gap Analysis** (`critical-audit-gap-analysis.ts`), run once per entity after baseline research consolidates:
   - 5a. Full dossier fed into LLM against `diligence_analysis.schema.json`.
   - 5b. Inspects 5 focus areas: Performance Blind Spots, Structural Omissions, Operational Risk, Regulatory/Compliance Nuance, Data Staleness (>2 quarters old).
   - 5c. **Decision point — `isEmerging` flag**: if true, "Emerging Manager Protocol" variant activates (stricter criteria).
6. Gap-analysis output (`redFlagsDetected`, `caseNumbers`, `tier2ServiceProviders`, `missingDataForWebSearch`) **mechanically triggers Phase-3 follow-up tasks**: regulatory-deep-dive, per-case-number forensic docket search, per-provider reputation check, recursive-deep-search — these re-enter the batch pipeline (loop back to step 3-4 scoped to the new tasks).

### Flow Diagram

```mermaid
flowchart TD
    A[Fund entity] --> B[Baseline: 6 core + 2 extended tasks]
    A --> C{Asset class?}
    C -->|Private Credit| D[4 missions:\nfund-mechanics, legal-odd,\nmarket-sector-dd, team-pedigree-dd]
    C -->|Real Estate| E[4 missions, REPE-tuned]
    C -->|Private Equity| F[7 missions:\ntrack record, macro, human-capital,\nlitigation, strategy-skeptic, reg/SEC, HR risk]
    B --> G[dispatcher.ts: executeDeepResearch]
    D --> G
    E --> G
    F --> G
    G --> H{Internal KB has answer?\nqueryTaskResponse}
    H -->|yes| I[Use internal fact, no external call]
    H -->|no| J[Jina default / Exa if requested]
    I --> K[consolidateFundTask\nFORENSIC MASTER DOSSIER]
    J --> K
    K --> L[critical-audit-gap-analysis.ts\n"skeptic" pass]
    L --> M{Gaps found?}
    M -->|yes| N[Phase-3 follow-up tasks\nre-enter batch pipeline]
    M -->|no /  after follow-up| O[sync-research-responses.ts\n-> Gemini File Search + Tigris + Parquet]
```

7. **Consolidation.** `consolidateFundTask` merges all task outputs into the FORENSIC MASTER DOSSIER (fixed structure: Executive Summary, Key Personnel/Alignment/LP Base, Strategy & Thesis, Historical Performance, Regulatory Filings, Operational Infrastructure, Competitive Landscape, Governance & Adverse Media, "Blind Spots" using `<critical_failure>`/`<unverified>` markup, Source Audit/Report Map).
8. **Sync-back.** `sync-research-responses.ts` uploads every raw report + citations to Gemini File Search stores and Tigris, tagged with metadata, exports run metadata to Parquet — this file-based sync is how the Elixir side reads results back.
9. Process rejoins main flow at step 6.4 (scoring) — see [proc-deal-analysis-pipeline](proc-deal-analysis-pipeline.md) for the wiring gap where scoring does not actually receive this stage's `ddResult`.

## Systems and Tools

- `fund-deep-diligence.ts`, `single-fund-research-mission.ts`, `dispatcher.ts`.
- `critical-audit-gap-analysis.ts`, `diligence_analysis.schema.json`.
- `consolidateFundTask`, `sync-research-responses.ts`.

## Known Issues

- Gap analysis is not advisory-only — it mechanically triggers a real second research round (step 6), a functioning feedback loop.
- Batching is aggressive (10 × 10 × 20 parallel) specifically to keep a full diligence pass to hours rather than days.

## Open Questions

- Observed hit rate of Phase-3 follow-up triggers — how often does gap analysis actually surface something requiring a second round?
- Specific criteria delta between standard and Emerging Manager Protocol gap analysis? `[UNKNOWN]`
