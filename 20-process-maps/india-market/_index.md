---
title: "India Market Variant — Process Maps Index"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [india, aif, market-variant, process-maps]
---

# India Market Variant — Process Maps

Built from: all `10-observations/india-market/obs-india-*.md` files, themselves sourced from `00-inbox/pipeline-architecture-india.md`. Companion to the US pipeline process maps in [../_index.md](../_index.md) — same `workflow-master-fund` shape, different regulatory-diligence and taxonomy sub-processes.

**Status note:** every process below describes a **planned/unbuilt variant**, not an observed running system — the source material is design intent, not an audited codebase (unlike the US process maps). Steps marked from a diagram in the source doc are traceable; anything else is a direct narrative claim with no independent confirmation.

## Main Flow

- [Deal Analysis Pipeline — India Variant](proc-india-deal-analysis-pipeline.md) — full `workflow-master-fund` sequence with India-specific deltas called out step-by-step against the US main flow.

## Sub-processes

- [Fund Classification — AIF Taxonomy](proc-india-fund-classification.md) — §3
- [Data Extraction — PPM Field Additions](proc-india-data-extraction.md) — §4
- [Regulatory Diligence — Multi-Regulator Router](proc-india-regulatory-diligence.md) — §5, the process that changes most
- [Key Personnel Intelligence — Source Substitutions](proc-india-key-personnel-intelligence.md) — §6
- [Fund Deep Research — AIF Category Mission Packs](proc-india-fund-deep-research.md) — §8
- [Scoring & Rubric — New Criteria Flow](proc-india-scoring-rubric.md) — §9
- [L1 Analysis — India-Sourced Verification](proc-india-l1-analysis.md) — §10
- [Build Delta vs. US Pipeline](proc-india-build-delta-and-unchanged.md) — not a true process, kept for parity with the US "Infrastructure Status Reference" entry; summarizes what's reused as-is vs. genuinely new
