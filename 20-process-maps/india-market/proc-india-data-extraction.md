---
title: "Process: Data Extraction — India PPM Field Additions"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [india, ppm, data-extraction]
---

# Process: Data Extraction — India PPM Field Additions

Built from: [obs-india-data-extraction-ppm-fields](../../10-observations/india-market/obs-india-data-extraction-ppm-fields.md). Sub-process of step 5.1b in [proc-india-deal-analysis-pipeline](proc-india-deal-analysis-pipeline.md). Companion to [../proc-data-extraction.md](../proc-data-extraction.md) (US extraction pipeline).

## Process Overview

- **Purpose**: Extend the existing extraction schema to capture SEBI-mandated PPM fields Indian pitch decks commonly disclose that the US-oriented schema doesn't ask for.
- **Trigger**: Same as US — runs as part of the per-schema extraction pass in `processPitchDeckWorkflow`.
- **End condition**: `fund_overview_and_terms` schema (extended) populated with the added India fields, merged into `consolidatedKnowledge` same as US.

## Roles Involved

- Fully automated, same as US.

## Inputs and Outputs

- **Input**: Same two-step "text-first, structure-second" pattern as US, same core schemas, same extract-then-normalize numeric handling — all unchanged.
- **Output**: Same `consolidatedKnowledge`/`master_data` output as US, plus three proposed new fields on `fund_overview_and_terms`.

## Process Steps

1. Same as US step 6.1b — text-first markdown generation, then structured-schema extraction over that markdown.
2. **Extend `fund_overview_and_terms`** (proposed, not built) with three India-specific fields:
   - Distribution waterfall in the SEBI Part-A mandatory template format.
   - Sponsor/manager commitment percentage — flagged as a **regulatory minimum**, not a negotiated deal term (semantic difference from the US GP-commitment figure).
   - Merchant-banker due-diligence certificate reference.
3. Consolidation proceeds identically to US — merged into `consolidatedKnowledge` by schema name, no new consolidation logic needed.

## Systems and Tools

- Same extraction pipeline/schema-mapper as US — this is a field-set extension on an existing schema, not a new pipeline stage.

## Known Issues

- **Not yet built.** No Zod schema fields, extraction prompt, or field names beyond the three named above exist in code per source material.
- Sponsor/manager commitment percentage carries different semantic weight in India (regulatory minimum) vs. US (negotiated term) — if the schema and downstream scoring rubric don't distinguish "meets regulatory minimum" from "GP put in extra skin in the game," this nuance is lost. See [proc-india-scoring-rubric](proc-india-scoring-rubric.md).

## Open Questions

- Should the merchant-banker certificate reference be a structured boolean field or free text?
- Is a canonical SEBI Part-A waterfall template available to design the schema against, or does this need first-hand India PPM samples first?
