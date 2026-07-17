---
title: "Observation: Elixir ↔ Trigger.dev Bridge"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [pipeline, elixir, trigger-dev, infrastructure]
---

# Observation: Elixir ↔ Trigger.dev Bridge

Source: `00-inbox/pipeline-architecture.md` §14, audited against codebase.

## Activity

Every pipeline stage (§1-10) runs as TypeScript in Trigger.dev; state, storage orchestration, and UI live in Elixir. `lib/trigger_dev/client.ex` is the integration seam, carrying real operational logic beyond a plain HTTP call.

## Systems

- **`trigger_task/3`, `batch_trigger_task/2`, `get_run/1`, `cancel_run/1`, `trigger_and_wait/4`** — the last polls with exponential backoff (1s → 5s), not a fixed interval, so short tasks resolve quickly without hammering the API on long ones.
- **Large-output handling** — `get_run/1` transparently follows `outputPresignedUrl`/`outputUrl` when Trigger.dev offloads a large output to S3, decoding via `TriggerDev.SuperJSON`. Callers never need to know whether output arrived inline or via redirect.
- **`get_deep_run/1`** — recursively expands child runs for workflow/research/diligence task-identifier prefixes (`workflow-`, `fund-deep-diligence-`, `person-research-`, plus `deep-research`, `compile-person-dossier`, `gather-sources`, `build-knowledge-parquet`) — the actual run-tree model behind Workflow Status and Agent Inspection panels: one top-level run fans out into dozens of child runs, and this reconstructs that tree for display.
- **Environment routing** — `preview` environment uses `TRIGGER_SECRET_KEY_PREVIEW` (falls back to prod key if unset), adds `x-trigger-branch` header, so branch-based preview deployments hit isolated Trigger.dev environments without a separate secret per branch.
- **Shared file bus** — every outbound Elixir payload has `bucketName` (from `TIGRIS_BUCKET`) auto-injected. Tigris is the shared object-storage bus both runtimes read/write, avoiding a direct RPC to move large files (decks, page images, research reports) between them.
- **Realtime status** — `lib/trigger_dev/realtime.ex` reimplements Trigger.dev's `useRealtimeRun` React hook for LiveView, polling every ~1.5-3s with terminal-state detection; `sse_client.ex` provides an SSE alternative against `/realtime/v1/runs/:id`. Powers live-updating progress in Workflow Status without a page refresh.

## Deploy Model

- Trigger.dev workflows deploy independently of the Phoenix app (`npx trigger.dev deploy --env {preview,staging,prod}`), secrets managed in the Trigger.dev dashboard, not app `.env` files.
- The two runtimes are versioned and released separately — part of why the preview-branch header logic exists: a Phoenix preview deploy and a Trigger.dev preview deploy aren't guaranteed to land at the same moment.

## Problems / Gaps / Workarounds

- Independent deploy cadence between Phoenix and Trigger.dev is a deliberate architectural choice, not a bug — but it means a payload/schema mismatch between the two sides is possible if one deploys ahead of the other without coordination. `[UNKNOWN: whether any contract-versioning/compatibility check exists between the two deploy pipelines]`

## Open Questions

- Is there any automated check that the Elixir side's expected Trigger.dev payload shapes stay in sync with what's actually deployed, given independent release cadences?
