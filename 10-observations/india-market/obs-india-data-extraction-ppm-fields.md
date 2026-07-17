---
title: "Observation: India Variant — Data Extraction (PPM Field Additions)"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [india, ppm, data-extraction, schema]
---

# Observation: India Variant — Data Extraction (PPM Field Additions)

Source: `00-inbox/pipeline-architecture-india.md` §4, corresponds to US doc §4 ([obs-data-extraction](../obs-data-extraction.md)).

## Activity

Extend the existing pitch-deck extraction schema set to capture SEBI-mandated fields commonly present in an India PPM (Private Placement Memorandum) that the US-oriented schema doesn't currently ask for.

## Inputs

- Same two-step "text-first, structure-second" extraction pattern as US §4. **Unchanged.**
- Same core schemas: `fund_overview_and_terms`, `strategy_and_portfolio`, `team_and_track_record`, `warehoused_deals`. **Unchanged.**
- Same extract-then-normalize numeric handling (verbatim `source_number_text` first, separate LLM call to parse into structured amount/magnitude). **Unchanged.**
- Indian PPMs specifically, which commonly disclose fields not in the current schema.

## Outputs

Proposed new fields to add to `fund_overview_and_terms` (extend, not a separate schema):
- Distribution waterfall in the SEBI Part-A mandatory template format.
- Sponsor/manager commitment percentage — a **regulatory minimum**, not just a deal term (distinguishing it from a US GP-commitment figure, which is a negotiated deal term).
- Merchant-banker due-diligence certificate reference.

## Systems

- Same extraction pipeline/schema-mapper as US §4 — proposed as a field-set extension, not a new pipeline stage.

## People / Actors

- Fully automated, same as US pipeline.

## Timing

- `[UNKNOWN]` — no timing stated; presumably unchanged since this is additive fields on an existing schema, not a new extraction pass.

## Problems / Gaps / Workarounds

- **Not yet built.** This is a proposed schema extension, not confirmed code. No field names, Zod schema, or extraction prompt changes exist yet per this doc — just three named fields worth adding.
- Sponsor/manager commitment percentage carries different semantic weight in India (a regulatory minimum) vs. the US (a negotiated term) — if the extraction schema and downstream scoring rubric (see [obs-india-scoring-rubric](obs-india-scoring-rubric.md)) don't distinguish "meets regulatory minimum" from "GP put in extra skin in the game," this nuance could get lost in schema reuse.

## Open Questions

- Should the merchant-banker due-diligence certificate reference be its own boolean/structured field, or captured as free text within `fund_overview_and_terms`?
- Is there a canonical SEBI Part-A waterfall template to model the schema against, or does this need first-hand PPM samples to design against?
