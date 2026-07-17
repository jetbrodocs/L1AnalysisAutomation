---
title: "Observation: India Variant — Scoring & Rubric (New Criteria)"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [india, aif, scoring, rubric]
---

# Observation: India Variant — Scoring & Rubric (New Criteria)

Source: `00-inbox/pipeline-architecture-india.md` §9, corresponds to US doc §9 ([obs-scoring-rubric](../obs-scoring-rubric.md)).

## Activity

Score India funds using the same architecture, scale, and execution pattern as the US pipeline, matched against AIF category (I/II/III) instead of the US asset-class enum, with new criteria added for India-specific structural checks that have no US analogue.

## Inputs

- Same TOML-as-data rubric matrix, same 4 categories (A/B/C/D), same fixed 5-tier scale (Exemplary → Strong → Adequate → Weak → Unacceptable) with VETO conditions, same dual-analyst-then-synthesize 3-call pattern, same up-to-12-Gemini-calls-per-fund cost structure. **All unchanged.**
- Fund's AIF category (I/II/III) instead of US `constraints.asset_class` matching key — with sub-tags for VC/infra/angel within Cat I and PE/credit/RE within Cat II, mirroring how the US ruleset already sub-tags Real Estate into 22 sub-classes.

## Outputs

Same per-dimension categorical scoring output as US, plus two proposed new TOML criteria with no clean US equivalent:

- **New D-category (Operations & Compliance) criterion — SEBI AIF leverage-limit compliance.** Cat II AIFs are restricted from borrowing except for temporary funding needs — a hard regulatory ceiling, not a covenant. Functions like the US `repe-breaking-points.json` quantitative gate, but as a **binary compliance check** rather than a market-benchmarked range.
- **New structural-red-flag criterion — merchant-banker due-diligence certificate presence** on the PPM. Its absence (for schemes required to have one) is a procedural red flag with no US equivalent.

## Systems

- Same `full-scoring-workflow.ts`/`score-category-agent.ts` execution mechanism as US, same dual-analyst (lenient + strict-compliance) → synthesis 3-call pattern per category. **Unchanged.**
- Proposed: `india-repe-breaking-points.json`, a parallel quantitative table to the US `repe-breaking-points.json` (DSCR/LTV/IRR cutoffs by RE risk profile × property type), refreshed from Indian market data (e.g., Knight Frank/JLL India cap-rate reports, RBI repo-rate-linked financing benchmarks) — India RE PE cutoffs differ meaningfully from US benchmarks (cap rates, rental yields, RBI-driven financing costs). Would need its own periodic-refresh mix task analogous to `mix decode_repe_matrix`. **Not yet built** — proposed only.

## People / Actors

- Fully automated, same as US pipeline.

## Timing

- `[UNKNOWN]` — no India-specific timing changes noted; cost structure (up to 12 Gemini calls/fund) explicitly asserted unchanged.

## Problems / Gaps / Workarounds

- The `constraints.asset_class` matching key needs to support the new Cat I/II/III values (with sub-tags) — this is a TOML-data change across ~57 rubric files, not a code change, consistent with the existing "rubric/task-as-data" pattern, but still a real content-authoring effort not yet done.
- No India market-data source has been identified/contracted for the proposed `india-repe-breaking-points.json` — the source doc names candidate sources (Knight Frank/JLL India, RBI repo-rate benchmarks) but this is a suggestion, not a confirmed data pipeline.
- The SEBI leverage-limit compliance check is described as binary (compliant/non-compliant against a hard ceiling), which is a structurally different kind of rubric criterion than the US pipeline's benchmarked-range checks — worth confirming the `ModuleResponseSchema`/scoring-schema actually supports a binary compliance criterion type, or whether it needs to be shoehorned into the existing 5-tier scale.

## Open Questions

- Does the existing scoring schema (`ModuleResponseSchema` / category scoring schema) natively support a binary compliance criterion, or does the SEBI leverage-limit check need schema changes beyond adding a new TOML file?
- Who would own building and refreshing `india-repe-breaking-points.json`, and is India RE PE even an initial-scope asset class for this variant?
- Should the merchant-banker certificate check apply to all AIF categories or only specific schemes (the source doc notes it applies "for schemes required to have one" without listing which)?
