---
title: "Observation: India Variant — Fund Deep Research (AIF Category Mission Packs)"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [india, aif, fund-deep-research, mission-packs]
---

# Observation: India Variant — Fund Deep Research (AIF Category Mission Packs)

Source: `00-inbox/pipeline-architecture-india.md` §8, corresponds to US doc §8 ([obs-fund-deep-research](../obs-fund-deep-research.md)).

## Activity

Run the same baseline + asset-class-specific fund research design as the US pipeline, but reframe the asset-class mission packs by AIF category (I/II/III) instead of US PE/Credit/RE splits, and re-point the `regulatory-disclosures` baseline task at India's regulatory sources.

## Inputs

- Same baseline task set as US: `strategy-thesis`, `performance-returns`, `regulatory-disclosures`, `infrastructure-service-providers`, `competitive-benchmarking`, `governance-adverse-media`, + 2 extended (`market-research`, `competitor-analysis`). **Unchanged**, except `regulatory-disclosures` needs its prompt/grounding re-pointed at §5's India sources (SEBI/MCA21/RBI/IFSCA) instead of SEC EDGAR/IAPD.
- Fund's AIF category (I/II/III) from classification (§3) — see [obs-india-fund-classification-taxonomy](obs-india-fund-classification-taxonomy.md).

## Outputs

Same "FORENSIC MASTER DOSSIER" consolidation format as US, produced via reframed mission packs:

- **Category I** (VC/infra/angel-tuned): sourcing/pipeline-quality verification, follow-on-reserve discipline, exit-environment analysis (IPO/M&A liquidity for India-domiciled startups), founder-network/reputation checks.
- **Category II** (PE/credit/RE-tuned, same shape as US PE/Credit/RE packs): deal-attribution audit, capital-structure/leverage-limit compliance (Cat II AIFs face SEBI-enforced borrowing restrictions — a **stricter constraint** than typical US PE leverage covenants), litigation/NCLT audit, regulatory/SEC-style audit repointed at SEBI+MCA21.
- **Category III** (hedge-fund-like): leverage/margin compliance against SEBI's Cat III leverage caps, market-manipulation/SAST-compliance screening, derivative-strategy verification.

## Systems

- Same `dispatcher.ts` (`executeDeepResearch`), same Jina/Exa provider routing, same batching limits, same idempotency design. **All unchanged.**
- Same `critical-audit-gap-analysis.ts` skeptic pass, same 5 failure-mode categories (Performance Blind Spots, Structural Omissions, Operational Risk, Regulatory/Compliance Nuance, Data Staleness), same Emerging Manager Protocol trigger. **Unchanged design** — only the freshness check underneath "Data Staleness" and "Regulatory/Compliance Nuance" changes: checks against MCA21 filing due dates (AOC-4/MGT-7 annual cycle) instead of SEC quarterly cadences.
- Same "FORENSIC MASTER DOSSIER" consolidation format, same `sync-research-responses.ts` sync-back mechanics. **Unchanged.**

## People / Actors

- Fully automated, same as US pipeline.

## Timing

- `[UNKNOWN]` — no India-specific timing changes noted; presumed same batching/latency profile as US since dispatch mechanics are unchanged.

## Problems / Gaps / Workarounds

- Category II's leverage-limit compliance check is described as a **hard regulatory ceiling enforced directly by SEBI**, not a negotiated covenant like typical US PE leverage terms — this is a meaningfully different kind of check (binary compliance vs. benchmarked range) that the mission-pack prompt needs to reflect, not just relabel.
- No mission-pack detail is given for how Cat II's "sub-tags" (PE vs. private credit vs. real estate vs. FoF, all bundled under one AIF category) should differentiate their research focus — the source doc says Cat II mission packs are "same shape as the US PE/Credit/RE mission packs" but doesn't specify whether that means 3 separate sub-packs (mirroring US) or one merged Cat II pack.

## Open Questions

- Should Category II mission packs be split by sub-strategy (mirroring the US PE/Credit/RE 3-way split), or run as a single unified Cat II pack?
- Is there a defined SEBI Cat III leverage cap figure to check against programmatically, or is this presently a qualitative/rubric-text check only (same pattern as US VETO conditions)?
