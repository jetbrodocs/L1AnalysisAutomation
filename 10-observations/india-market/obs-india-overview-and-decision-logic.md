---
title: "Observation: India Variant — Overview & Core Decision Logic Delta"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [india, aif, sebi, overview]
---

# Observation: India Variant — Overview & Core Decision Logic Delta

Source: `00-inbox/pipeline-architecture-india.md` intro + "Core Decision Logic" section, describing intended delta vs. `00-inbox/pipeline-architecture.md` (US pipeline).

## Activity

Define which parts of the existing US-built pipeline carry over unchanged for an India-market build, and which parts need new engineering, for each of the 10 core decision points the US doc calls out as load-bearing.

## Inputs

- Existing US pipeline design/code (Elixir/Phoenix, Trigger.dev, Gemini, Jina/Exa, Tigris — same stack, asserted unchanged).
- SEBI (AIF) Regulations, 2012, as amended (2026 amendment referenced).
- Proposed `market: "IN" | "US"` flag concept to gate which regulatory-source adapter and scoring/mission packs load per fund.

## Outputs

A section-by-section delta assessment (§1-15 of the US doc, mapped 1:1):

| US doc § | What it covers | India-variant status |
|---|---|---|
| §1-2 | Document classification & promotion gate | Unchanged — same 12 `document_type` values, same 8-type allowlist |
| §3 | Fund classification | Mechanically unchanged; taxonomy overlay needed (AIF Cat I/II/III replaces US asset-class enum) — see [obs-india-fund-classification-taxonomy](obs-india-fund-classification-taxonomy.md) |
| §4 | Data extraction | Unchanged pattern; PPM field additions needed — see [obs-india-data-extraction-ppm-fields](obs-india-data-extraction-ppm-fields.md) |
| §5 | Regulatory diligence (deck-vs-official-record match) | **Changes most** — multi-regulator router replaces single `SECProvider` — see [obs-india-regulatory-diligence](obs-india-regulatory-diligence.md) |
| §6 | Key personnel classification | Mechanically unchanged; research *sources* differ — see [obs-india-key-personnel-intelligence](obs-india-key-personnel-intelligence.md) |
| §8 | Fund deep research / gap analysis | Design unchanged; mission packs reframed by AIF category — see [obs-india-fund-deep-research-mission-packs](obs-india-fund-deep-research-mission-packs.md) |
| §9-10 | Scoring & L1 memo | Unchanged mechanics; rubric matrix needs Cat I/II/III variants — see [obs-india-scoring-rubric](obs-india-scoring-rubric.md) |
| §7, 11-15 | People research, Gemini patterns, web research dispatch, dashboard, Elixir↔Trigger.dev bridge, Knowledge Agent | Asserted entirely unchanged — see [obs-india-unchanged-components](obs-india-unchanged-components.md) |

## Systems

- Proposed gating mechanism: a `market: "IN" | "US"` flag selects which regulatory-source adapter and which scoring/mission packs load per fund. Everything else (rasterization, extraction schemas, dual-analyst scoring, L1 memo generation) is asserted market-agnostic and reused as-is. **This flag does not exist yet** — it's a proposed design, not confirmed in code.

## People / Actors

- Fully automated pipeline, same as US variant — no new human role introduced by the India build.

## Timing

- `[UNKNOWN]` — this is a planning document for unbuilt work; no timeline or build sequence stated.

## Problems / Gaps / Workarounds

- This entire doc is **design intent for a not-yet-built variant**, not an audit of running code (unlike the US `pipeline-architecture.md`, which was explicitly audited against the codebase). Every claim here should be read as "this is how it should work," not "this is confirmed behavior."
- Four-way regulatory disciplinary-history mapping (US Form ADV Item 11 → SEBI Enforcement/Adjudication Orders + NCLT/IBC insolvency records) preserves the *same design intent* (boolean + categorized breakdown) but via a genuinely different acquisition path — flagged as the single most consequential red-flag-detection change in the whole variant.

## Open Questions

- Is there an actual product decision to build this India variant, or is this exploratory/speculative documentation?
- Who owns the `market: "IN" | "US"` flag design — has it been scoped as an engineering ticket?
- Does any part of this variant have a target ship date, or is it purely reference material at this stage?
