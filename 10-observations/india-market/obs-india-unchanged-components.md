---
title: "Observation: India Variant — Unchanged Components"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [india, unchanged, gemini, l1, dashboard, knowledge-agent]
---

# Observation: India Variant — Unchanged Components

Source: `00-inbox/pipeline-architecture-india.md` §1-2, 7, 10-15, all asserted as reused as-is from the US pipeline (`00-inbox/pipeline-architecture.md`). Grouped into one observation since the source doc's claim for each is identical: no jurisdiction dependency.

## Activity

Confirm which pipeline components carry over from the US build with zero design change, so India-variant engineering effort concentrates only on the components flagged elsewhere as changed (§3-6, 8-9).

## Inputs

- Full US pipeline design as documented in `00-inbox/pipeline-architecture.md` §1-2, 7, 10-15 and their corresponding `10-observations/obs-*.md` files.

## Outputs

Per-section unchanged assertions, each with its corresponding US observation for full detail:

| §  | Component | India-variant claim | US reference |
|---|---|---|---|
| 1-2 | Document upload, ingestion, classification, rasterization | Entirely unchanged — same 12 `document_type` values, same promotion gate, same `pdftoppm`→ImageMagick fallback, same two-phase priority rendering. Indian PPMs/IMs/fact sheets classify identically to US decks. | [obs-document-ingestion-classification](../obs-document-ingestion-classification.md) |
| 7 | People deep research | Entirely unchanged execution — same phase structure, same Jina/Exa provider routing, same two-dossier consolidation. Only *what* research tasks search for (§6 sources) changes, not *how* research runs. | [obs-people-deep-research](../obs-people-deep-research.md) |
| 10 | L1 Analysis (final IC memo) | Entirely unchanged — same `L1AnalysisSchema`, same 10-section format, same orchestrator, same 14-agent-invocation fan-out, same dual-analyst-then-synthesize mechanics, same deterministic Fund Factsheet. Only the underlying Claims Ledger/Flags content reflects India-sourced (not SEC-sourced) verification. | [obs-l1-analysis](../obs-l1-analysis.md) |
| 11 | Gemini usage patterns | Entirely unchanged — all 5 usage patterns (native structured output, two-step text-then-structure, extract-then-normalize, per-fund File Search grounding, dual-analyst-then-synthesize) and model tiering are jurisdiction-agnostic. | [obs-gemini-usage-patterns](../obs-gemini-usage-patterns.md) |
| 12 | Jina + Exa web research dispatch | Dispatch mechanics unchanged (internal-KB-first ordering, provider routing, cleanup/re-citation pass). Only change: research-task prompts should bias search toward `sebi.gov.in`, `mca.gov.in`, `rbi.org.in`, `nclt.gov.in`, and Indian business press (Economic Times, Mint, Moneycontrol, VCCircle) instead of SEC/EDGAR-adjacent sources — a prompt/config change, not architectural. | [obs-web-research-providers](../obs-web-research-providers.md) |
| 13 | Fund Dashboard UI | Unchanged — every panel (Fund Intelligence, Slide Analysis, Workflow Status, Custom Research, Gemini Store, Agent Inspection, Website Extraction, Task Logs, Debug Payload) is jurisdiction-agnostic ops tooling. One proposed UI change: the "SEC Data" tab would need renaming/restructuring into a multi-source India regulatory panel (SEBI registration status, MCA21 filing history, RBI/FEMA filings if applicable, IFSCA record if applicable, SEBI enforcement search results) — a direct UI consequence of §5's multi-regulator fragmentation. | [obs-fund-dashboard-ui](../obs-fund-dashboard-ui.md) |
| 14 | Elixir ↔ Trigger.dev bridge | Entirely unchanged — same `client.ex` seam, S3-redirect handling, environment-routing/preview-branch logic, Tigris shared-file-bus design, realtime polling/SSE mechanics. No jurisdiction-specific logic exists at this layer at all. | [obs-elixir-trigger-bridge](../obs-elixir-trigger-bridge.md) |
| 15 | Knowledge Agent (chat) | Entirely unchanged — same SIRA/GraphRAG/Vector/Lexical/Gemini-File-Search retrieval strategies, same live correctness gap re: the un-started `RuvectorServer` GenServer (see US observation). Retrieval has no jurisdiction dependency; it queries whatever KB was built, regardless of which regulators fed it. | [obs-knowledge-agent-chat](../obs-knowledge-agent-chat.md) |

Also asserted unchanged, not tied to a specific numbered section:
- **Infrastructure notes** (FLAME/Hetzner elastic compute — zero call sites; bulk research admin tool) — same dormant/provisioned status as US, jurisdiction-agnostic.
- **Explicitly out-of-scope directories** — same five directories as the US doc (`stitch_investor_dashboard/`, `conductor/`, `experiments/hei_structured_research/`, `priv/native/redb.so`, `priv/resource_snapshots/`) — none jurisdiction-specific, same determination holds.

## Systems

- No new systems introduced by this observation — it's a confirmation list pointing back at existing US-documented systems.

## People / Actors

- Fully automated, same as US pipeline, across every component listed above.

## Timing

- No timing changes asserted for any component in this list.

## Problems / Gaps / Workarounds

- These are **assertions in a planning document**, not confirmed by running India-market code (no India-specific codebase exists yet per this doc's own framing). "Unchanged" here means "the source doc's author expects no change needed," not "verified identical in production."
- The Fund Dashboard's proposed SEC-Data-tab → multi-regulator-panel change is the one UI consequence flagged from an otherwise "unchanged" list — worth tracking separately as real (if small) frontend work, not assuming it falls out of the "unchanged" bucket for free.

## Open Questions

- Given the India variant hasn't been built, has any of this "unchanged" list actually been tested against a real Indian pitch deck to confirm the same document_type/extraction schemas apply cleanly?
- Is the proposed India regulatory panel (§13) in scope for an initial India-variant MVP, or deferred until after the core §5 multi-regulator router ships?
