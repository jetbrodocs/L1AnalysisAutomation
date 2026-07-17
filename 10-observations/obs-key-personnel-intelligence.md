---
title: "Observation: Key Personnel Intelligence & Classification"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [pipeline, personnel, classification, taxonomy]
---

# Observation: Key Personnel Intelligence & Classification

Source: `00-inbox/pipeline-architecture.md` §6, audited against codebase.

## Activity

Every named team member (sourced from pitch-deck extraction, website scraping, and filings) is classified into one of 7 role tiers. This classification mechanically determines how much research depth (3-10 tasks) that person receives downstream.

## Inputs

- Team roster: pitch-deck extraction + website scraping + filings.

## Outputs

- Per-person classification into one of 7 buckets, each entry carrying `classificationReasoning` and a possibly `corrected_title`:
  1. `key_principal` — 1-2 top-level, day-to-day heads of *this specific fund* (excludes parent-company CEOs/Chairmen)
  2. `fund_principal` — senior investment pros dedicated to the fund, not lead decision-makers
  3. `firm_leadership` — parent-firm executives/partners from unrelated strategies
  4. `advisor` — formal advisors without daily deployment authority
  5. `former_member` — departed people
  6. `extended_team` — VPs/Associates/Analysts
  7. `misc` — admin/operational staff

## Systems

- `verify-key-principals.ts` — Gemini Flash-Lite, strict JSON schema, per person.
- Tiered execution (`workflow.json`) drives research depth: `firm_leader` (10 tasks, includes forensic + OBA), `key_person` (8 tasks, no forensic/OBA), `extended_team` (3 tasks: preliminary-search, generic, employment-history only).
- Dependency graph is codegen'd, not hand-maintained: `mix research.generate_dag` (`lib/mix/tasks/research/generate_dag.ex`) writes the same graph to both `config/research_dag.json` (Elixir) and `src/config/research-dag.ts` (Trigger.dev), keeping both runtimes in sync.

## People / Actors

- Fully automated classification, no human review observed.

## Timing

- `[UNKNOWN: per-person classification call duration]`

## Problems / Gaps / Workarounds

- **Fail-open design, deliberately asymmetric**:
  - No research context available → defaults to `extended_team` (least scrutiny).
  - Parse failure/exception → defaults to `key_principal` (most scrutiny, 10 research tasks). This is a deliberate bias toward *not* under-scrutinizing someone important when the classifier errors out, rather than silently dropping them into a low-depth bucket.
- `former_member` bucket is explicitly guarded against false positives from bios that merely list prior employers (not actual departure) — implies this was a known misclassification failure mode worth designing around.

## Open Questions

- How often does the parse-failure fallback (→ `key_principal`) actually trigger in production, and does anyone monitor that rate?
