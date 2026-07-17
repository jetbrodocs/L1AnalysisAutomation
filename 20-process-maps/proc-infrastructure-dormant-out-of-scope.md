---
title: "Process: N/A — Infrastructure Status Reference"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [pipeline, infrastructure, reference]
---

# Process: N/A — Infrastructure Status Reference

Built from: [obs-infrastructure-dormant-out-of-scope](../10-observations/obs-infrastructure-dormant-out-of-scope.md).

## Note on Fit

This item is a **status reference**, not a sequential process — nothing here executes as a flow with a trigger and steps. Per the process-mapping skill's own entry rule, this content technically doesn't belong in `20-process-maps/`; it's kept here only for parity with the other 14 observation-derived docs. Treat this file as an index, not a process map.

## Provisioned, Not Yet Load-Bearing

| Item | Status | What would activate it |
|---|---|---|
| FLAME / Hetzner elastic compute (`lib/flame/hetzner_backend.ex`) | Pool started (min:0/max:5) when `HCLOUD_TOKEN` set, but **zero call sites** anywhere in the app | A future workload calling `FLAME.call`/`FLAME.place_child` |
| Bulk research admin tool (`bulk_action_live/`, `research/bulk_action.ex`) | Live, but scoped to ad hoc research-prompt experimentation — not a "re-run all funds" tool (that doesn't exist) | Already active for its intended narrow use; not dormant, just narrower than it might appear |

## Explicitly Out of Scope — Confirmed No Live Product Logic

| Item | Why it's out of scope |
|---|---|
| `stitch_investor_dashboard/` | Static AI-generated HTML mockups, not wired into the app |
| `conductor/` | Internal engineering planning scaffolding, not product logic |
| `experiments/hei_structured_research/` | Unmerged prototype for an unsupported asset class, never referenced from `src/`/`lib/` |
| `priv/native/redb.so` | Orphaned compiled NIF, no Elixir references |
| `priv/resource_snapshots/` | Manual/external backup exports, not read by live code |

## If You're Deciding Whether to Activate Something Here

1. Confirm the item is still dormant (re-check call sites — this table can go stale).
2. If activating FLAME: identify the actual workload that needs elastic compute (the current heavy-compute story, `mix extract.irs_990`, doesn't use it — see [proc-sec-filing-diligence](proc-sec-filing-diligence.md)).
3. If touching an out-of-scope item: confirm with the team it's genuinely meant to be resurrected before wiring it in — several of these (mockups, experiments) look like intentional parking, not oversights.

## Open Questions

- Plan to activate FLAME/Hetzner, or should the pool be torn down?
- Should orphaned artifacts (`priv/native/redb.so`) be removed from the repo?
