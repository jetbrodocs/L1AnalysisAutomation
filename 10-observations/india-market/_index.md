---
title: "India Market Variant — Observations Index"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [india, aif, sebi, market-variant]
---

# India Market Variant — Observations

Source for all entries below: `00-inbox/pipeline-architecture-india.md` (Deal Analysis Pipeline — India Market Variant), a companion doc to `00-inbox/pipeline-architecture.md` (US pipeline, see [../_index.md](../_index.md)). Not yet audited against a live India-specific codebase — this doc describes an unbuilt/planned variant, not an observed running system. Treat every entry here as **design intent**, not confirmed behavior.

- [Overview & Core Decision Logic Delta](obs-india-overview-and-decision-logic.md) — what changes for India, what doesn't, at a glance
- [Fund Classification — AIF Taxonomy](obs-india-fund-classification-taxonomy.md) — §3
- [Data Extraction — India PPM Fields](obs-india-data-extraction-ppm-fields.md) — §4
- [Regulatory Diligence — Multi-Regulator Router](obs-india-regulatory-diligence.md) — §5 (the section that changes most)
- [Key Personnel Intelligence — Source Substitutions](obs-india-key-personnel-intelligence.md) — §6
- [Fund Deep Research — AIF Category Mission Packs](obs-india-fund-deep-research-mission-packs.md) — §8
- [Scoring & Rubric — New Criteria](obs-india-scoring-rubric.md) — §9
- [Unchanged Components](obs-india-unchanged-components.md) — §1-2, 7, 10-15, confirmed reused as-is
- [Gaps & Build Delta vs. US Pipeline](obs-india-gaps-and-build-delta.md) — LP-discovery gap, out-of-scope, cross-cutting pattern, summary delta

## Key facts across these observations

- No single India equivalent of SEC EDGAR — regulatory truth fragmented across SEBI, MCA21, RBI/FEMA, and IFSCA (GIFT City only). This is the architectural core of the India variant.
- AIF taxonomy (SEBI Category I/II/III) replaces the US `primaryAssetClass` enum as the classification/gating dimension.
- A genuine capability gap exists with no proposed workaround: no public LP-discovery equivalent to US Form 5500/990 — AIF investor lists are confidential under SEBI regulations.
- Everything downstream of classification+diligence (scoring mechanics, L1 memo structure, Gemini usage patterns, research dispatch, dashboard, Elixir↔Trigger.dev bridge, Knowledge Agent) is asserted **unchanged** — reused as-is from the US pipeline.
