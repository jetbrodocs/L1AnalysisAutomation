---
title: "Observation: Infrastructure — Provisioned/Dormant & Explicitly Out of Scope"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [pipeline, infrastructure, dormant, out-of-scope]
---

# Observation: Infrastructure — Provisioned/Dormant & Explicitly Out of Scope

Source: `00-inbox/pipeline-architecture.md`, "Infrastructure Notes" and "Explicitly Out of Scope" sections, audited against codebase. Captured here so these aren't mistaken for active behavior or re-flagged as gaps in a future documentation pass.

## Provisioned, Not Yet Load-Bearing

- **FLAME / Hetzner elastic compute** (`lib/flame/hetzner_backend.ex`) — custom `FLAME.Backend` for provisioning ephemeral Hetzner Cloud VMs on demand (boots, `git pull && mix compile && mix phx.server`, self-destructs via Hetzner API on idle). A pool (`DealsAnalysis.HetznerRunner`, min:0/max:5) starts in `application.ex` when `HCLOUD_TOKEN` is set — but **zero call sites** (`FLAME.call`/`FLAME.place_child`) anywhere in the app. Wired up and ready, nothing dispatches work to it yet. The actual "needs a big dedicated machine" workload in this codebase is the standalone `mix extract.irs_990` batch job (see SEC diligence observation), not FLAME.
- **Bulk research admin tool** (`lib/deals_analysis_web/live/bulk_action_live/`, `lib/deals_analysis/research/bulk_action.ea`) — admin UI for firing a batch of ad hoc research prompts (Jina/Exa, configurable reasoning effort/token budget) with poll/cancel-all/start-all-pending controls. A research-prompt experimentation surface — distinct from a "re-run all funds through the pipeline" capability, **which does not exist**. Reprocessing is always scoped to one fund/document at a time via Workflow Status's "Dry Run Full" or per-step "rerun_task" (see dashboard UI observation).

## Explicitly Out of Scope — Confirmed No Live Product Logic

- **`stitch_investor_dashboard/`** — four static, AI-design-tool-generated (Stitch) HTML mockups (Tailwind-via-CDN, hardcoded placeholder data, no Phoenix/LiveView markup, no router references). Sketches a possible future LP/investor-facing dashboard; not wired into the app.
- **`conductor/`** — internal engineering planning/tracking scaffolding (plan docs, initiative archive). Documents how the team built the pipeline over time, not how the pipeline itself works.
- **`experiments/hei_structured_research/`** — unmerged prototype research schema/prompt for Home Equity Investment (HEI) firms, a real-estate-finance asset class the platform doesn't currently support. Never referenced from `src/` or `lib/`.
- **`priv/native/redb.so`** — compiled NIF for the `redb` embedded key-value store crate; no Elixir code references it. Orphaned build artifact.
- **`priv/resource_snapshots/`** — periodic JSON exports of DB tables, not read by any live code path; appears to be a manual/external backup process.

## Problems / Gaps / Workarounds

- These items were investigated and confirmed inert as of the source audit date — worth periodic re-confirmation if the codebase changes significantly, since "provisioned but dormant" can silently become "active" (or vice versa, orphaned) without documentation catching up.

## Open Questions

- Is there a plan to activate FLAME/Hetzner for any workload, or should the pool be torn down if genuinely unused?
- Should `priv/native/redb.so` and other orphaned artifacts be removed from the repo?
