---
title: "Observation: India Variant — Fund Classification (AIF Taxonomy)"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [india, aif, sebi, fund-classification, taxonomy]
---

# Observation: India Variant — Fund Classification (AIF Taxonomy)

Source: `00-inbox/pipeline-architecture-india.md` §3, corresponds to US doc §3 ([obs-fund-classification](../obs-fund-classification.md)).

## Activity

Classify a fund into SEBI's Alternative Investment Fund (AIF) category system, in place of (or alongside) the US pipeline's `primaryAssetClass` enum, so the same downstream gating (extraction schema, scoring rubric, research mission pack) can operate on Indian funds.

## Inputs

- Same mandatory Pass-1 extraction pattern as the US pipeline: dedicated schema, high-thinking model, run before other extraction, forced chain-of-thought reasoning field. **Mechanically unchanged.**
- SEBI (AIF) Regulations, 2012, as amended — including a referenced 2026 AIF Amendment Regulations update (reduced "large value fund" accredited-investor threshold, new Accredited Investors Only Fund (AIOF) scheme).

## Outputs

Three-way category classification, each gating the same downstream stages the US `primaryAssetClass` enum gates (extraction schema choice, scoring rubric variant, research mission pack):

- **Category I AIF** — early-stage/infra/social-venture/angel funds. No leverage. Roughly maps to US VC/infra/social-impact/angel.
- **Category II AIF** — "everything else, no leverage beyond limited borrowing": PE, private credit/debt, real estate, funds-of-funds. Roughly maps to US PE/private-credit/real-estate/FoF.
- **Category III AIF** — hedge-fund-like, listed/derivative strategies, leverage permitted. Roughly maps to US Hedge Fund.

**Registration/corpus parameters** (regulatory facts, not pipeline logic, but gate whether a fund is even a valid AIF):
- Minimum fund corpus: ₹20 crore (all categories), ₹10 crore for angel funds specifically.
- Minimum per-investor commitment: ₹1 crore.
- SEBI registration fee: ₹5 lakh (Cat I) to ₹15 lakh (Cat III), filed via the SI Portal.
- Registration timeline: 4-8 months.

## Systems

- Same extraction mechanism as US §3 (one dedicated LLM pass, forced chain-of-thought).
- Proposed: extend the classification schema to capture the AIF category field alongside or instead of `primaryAssetClass`.

## People / Actors

- Fully automated — no human classification step, same as US pipeline.

## Timing

- `[UNKNOWN]` — no per-call timing stated; presumably same cost/latency profile as the equivalent US Pass-1 call since the mechanism is unchanged.
- SEBI's own registration timeline (4-8 months) is a regulatory fact about the fund's real-world registration process, not a pipeline processing time.

## Problems / Gaps / Workarounds

- **No existing mapping layer.** The three-way US↔India category mapping (Cat I ≈ VC/infra/social-impact/angel; Cat II ≈ PE/credit/RE/FoF; Cat III ≈ hedge-fund-like) is proposed in the source doc, not built. Building it is real, non-trivial work — the categories don't cleanly 1:1 map (e.g., Cat II bundles four distinct US asset classes into one bucket).
- The US taxonomy itself already has three unreconciled overlapping enums (flagged in [obs-fund-classification](../obs-fund-classification.md)) — adding a fourth (India AIF) taxonomy on top compounds that fragmentation unless explicitly reconciled.

## Open Questions

- Should India AIF category *replace* `primaryAssetClass` for India-market funds, or run as a parallel field? The source doc says "in addition to (or instead of)" without deciding.
- How should Category II's internal sub-types (PE vs. private credit vs. real estate vs. FoF) be captured, given the US pipeline already sub-tags Real Estate into 22 sub-classes for its own taxonomy?
- Has the 2026 AIF Amendment Regulations' AIOF scheme been scoped into this taxonomy, or just noted as a fact?
