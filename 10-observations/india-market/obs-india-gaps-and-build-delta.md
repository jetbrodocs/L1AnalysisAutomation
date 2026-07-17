---
title: "Observation: India Variant — Gaps & Build Delta vs. US Pipeline"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [india, build-delta, gaps, cross-cutting]
---

# Observation: India Variant — Gaps & Build Delta vs. US Pipeline

Source: `00-inbox/pipeline-architecture-india.md` — "Cross-Cutting Patterns Worth Noting" and "Summary: Build Delta vs. US Pipeline" sections, synthesizing across all other India-variant observations.

## Activity

Summarize what's genuinely new build work for an India-market variant vs. what's reused as-is, and name the one India-specific structural pattern (multi-source-of-truth) that doesn't exist in the US design at all.

## Inputs

- All other India-variant observations in this folder (see [_index.md](_index.md)).
- Same five cross-cutting patterns as the US doc, asserted to hold regardless of jurisdiction: extract-then-normalize, dual-analyst-then-synthesize, rubric/task-as-data, file-search-grounding-before-external-search, fail-open-on-ambiguity, idempotency-by-content-hash.

## Outputs

**New India-specific cross-cutting pattern (has no US equivalent):**
- **No single-source-of-truth regulator.** Unlike the US pipeline's single `SECProvider` abstraction, India genuinely needs a multi-source router (SEBI + MCA21 + RBI + IFSCA) because no one regulator covers what one fund needs verified, and there's no cross-index between them. Any India `MatchChecks`-style verification struct should carry a `source` field per check — the US struct never needed this because there's only ever one source.

**Summary build delta:**

| Bucket | Items |
|---|---|
| **Unchanged — reuse as-is** | §1-2 ingestion & classification; §3 mechanics (taxonomy overlay only); §4 extraction (minor schema additions); §6-8 mechanics (source substitutions only); §9-10 scoring + L1 (rubric-matrix additions only); §11-15 Gemini, research dispatch, dashboard, bridge, knowledge agent |
| **Genuinely new build work** | §5 multi-regulator router (SEBI + MCA21 + RBI + IFSCA); LP-discovery gap (no Form 5500/990 equivalent — see [obs-india-regulatory-diligence](obs-india-regulatory-diligence.md)); India RE breaking-point table (new market-data source, see [obs-india-scoring-rubric](obs-india-scoring-rubric.md)) |

## Systems

- No new systems beyond what's already itemized in the per-section observations — this document is a synthesis/index, not a new component.

## People / Actors

- Fully automated pipeline, same as US, across the entire variant.

## Timing

- `[UNKNOWN]` — no build sequencing or timeline given for the "genuinely new build work" bucket.

## Problems / Gaps / Workarounds

- **The LP-discovery gap is explicitly flagged in the source doc as a genuine capability gap, not a solvable different-data-source problem.** AIF investor lists are confidential under SEBI regulation — there's no legal path to a public LP-roster equivalent of US Form 5500/990 in India. This should be communicated to stakeholders as a permanent capability delta, not tracked as an open engineering task to eventually close.
- The "unchanged" bucket is large (12 of 15 sections), but several of those sections carry *small* proposed changes bundled inside an otherwise-unchanged label (e.g., §4's 3 new PPM fields, §13's SEC-Data-tab restructuring, §9's 2 new TOML criteria) — treating the whole bucket as zero-effort would understate real, if small, work items. See the per-section observations for each specific addition.
- This entire India variant is speculative/planning-stage documentation (see [obs-india-overview-and-decision-logic](obs-india-overview-and-decision-logic.md)) — the build-delta summary here reflects proposed scope, not a committed roadmap.

## Open Questions

- Is there a committed decision to build any part of this India variant, and if so, does the build order follow the "new build work" bucket above (§5 router first, since everything else depends on classification/diligence completing)?
- Should the LP-discovery gap be surfaced as a standing disclaimer in every India-market L1 memo's Claims Ledger, given it's a permanent (not temporary) capability delta?
- Does the `source`-field addition to `MatchChecks` (needed for India) get backported into the US struct too for schema consistency, or kept as an India-only schema variant?
