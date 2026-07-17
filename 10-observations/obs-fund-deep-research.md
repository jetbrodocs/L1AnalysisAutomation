---
title: "Observation: Fund Deep Research"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [pipeline, research, jina, exa, gap-analysis]
---

# Observation: Fund Deep Research

Source: `00-inbox/pipeline-architecture.md` §8, audited against codebase.

## Activity

Fund-level research combining a generic baseline task set (every fund, every asset class) with asset-class-specific "mission" packs, followed by an automated "skeptic" gap-analysis pass that can trigger a second round of targeted research.

## Inputs

- Fund/GP/management-company entities, key principals.
- `primaryAssetClass` (gates which mission pack fires).
- `isEmerging` flag (from §3 manager classification) — activates "Emerging Manager Protocol" variant of gap analysis.

## Outputs

- Baseline (6 core + 2 extended tasks): `strategy-thesis`, `performance-returns`, `regulatory-disclosures`, `infrastructure-service-providers`, `competitive-benchmarking`, `governance-adverse-media`; extended: `market-research`, `competitor-analysis`.
- Asset-class mission packs: Private Credit (4 missions), Real Estate (4 missions), Private Equity (7 missions, richest metadata).
- Critical Audit Gap Analysis output: `redFlagsDetected[]`, `caseNumbers[]`, `tier2ServiceProviders[]`, `missingDataForWebSearch[]`.
- "FORENSIC MASTER DOSSIER" markdown (fixed structure: Executive Summary, Key Personnel/Alignment/LP Base, Strategy & Thesis, Historical Performance, Regulatory Filings, Operational Infrastructure, Competitive Landscape, Governance & Adverse Media, "Blind Spots" using `<critical_failure>`/`<unverified>` markup, Source Audit/Report Map).

## Systems

- `fund-deep-diligence.ts` — baseline task set; `infrastructure-service-providers` depends on `regulatory-disclosures`; `competitive-benchmarking` depends on `strategy-thesis` + `performance-returns`.
- Mission packs (mirrored at runtime to `data/research/prompts/external_prompts/fund/`):
  - Private Credit (4, all Jina, 1M budget, high reasoning): `fund-mechanics-baseline`, `legal-odd`, `market-and-sector-dd`, `team-pedigree-dd`.
  - Real Estate (4, same shape, tuned for REPE).
  - Private Equity (7, richer metadata, organized under category taxonomy: Track Record & Performance / Strategy & Market Verification / Team & Human Capital / Legal & Regulatory Compliance / Reputational & ESG Risks).
- `dispatcher.ts` (`executeDeepResearch`) — picks provider, optionally grounds via internal KB, runs research, LLM-sanitizes into JSON + Markdown.
- `fund-deep-diligence.ts` batches: up to 10 entities (fund + GP/mgmt co) in parallel × up to 10 principals in parallel × 20 prompts in parallel, one `batchTriggerAndWait` call.
- `single-fund-research-mission.ts` — mission packs run one at a time, keyed by `assetClass/missionId`.
- **Critical Audit Gap Analysis** (`critical-audit-gap-analysis.ts`) — run once per entity after baseline research consolidated, feeds full dossier into LLM against `diligence_analysis.schema.json`, inspects 5 focus areas: Performance Blind Spots, Structural Omissions, Operational Risk, Regulatory/Compliance Nuance, Data Staleness (>2 quarters old). Output drives conditional Phase-3 follow-up tasks (regulatory-deep-dive, per-case-number forensic docket search, per-provider reputation check, recursive-deep-search) that re-enter the batch pipeline.
- `consolidateFundTask` — merges all task outputs into the forensic dossier; `sync-research-responses.ts` uploads individual raw reports + citations to Gemini File Search + Tigris, tagged with metadata, exports run metadata to Parquet. **This file-based sync (not a relational DB write) is how the Elixir side reads results back.**

## People / Actors

- Fully automated, including the gap-analysis "skeptic" pass and its follow-up task triggering.

## Timing

- Idempotency keys hashed from `date + task identifier + entity-name hash + token budget` — prevents duplicate spend on reruns within the same day.

## Problems / Gaps / Workarounds

- Gap analysis is **not just advisory** — its output fields mechanically trigger a second round of targeted research, a real feedback loop, not a note in a report.
- Emerging Manager Protocol is a stricter variant that activates automatically based on an upstream classification flag — worth confirming its exact criteria differ meaningfully from the standard protocol. `[UNKNOWN: specific delta between standard and Emerging Manager Protocol gap-analysis criteria]`
- Fund-level batching is aggressive (10 × 10 × 20 parallel) — source doc notes this is "what keeps a full diligence pass to hours rather than days," implying there was a slower prior approach or this was a deliberate scale decision.

## Open Questions

- What is the actual observed hit rate of the Phase-3 follow-up triggers (how often does gap analysis actually surface something requiring a second research round)?
