---
title: "Process: Elixir → Trigger.dev Call Flow"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [pipeline, elixir, trigger-dev, infrastructure]
---

# Process: Elixir → Trigger.dev Call Flow

Built from: [obs-elixir-trigger-bridge](../10-observations/obs-elixir-trigger-bridge.md). Underlying request/response mechanics used by every Elixir→Trigger.dev call across the pipeline (e.g., firing `workflow-master-fund`, polling its status).

## Process Overview

- **Purpose**: Describe what actually happens when Elixir triggers or polls a Trigger.dev run, including large-output handling and realtime status.
- **Trigger**: Elixir code calls `lib/trigger_dev/client.ex`.
- **End condition**: Run result available to Elixir (inline or via redirect), or run status reflected in UI.

## Process Steps

1. Elixir calls one of: `trigger_task/3`, `batch_trigger_task/2`, `get_run/1`, `cancel_run/1`, `trigger_and_wait/4`.
2. Every outbound payload has `bucketName` (from `TIGRIS_BUCKET`) auto-injected — Tigris is the shared object-storage bus both runtimes read/write against, avoiding a direct RPC for large files (decks, page images, research reports).
3. **Environment routing (decision point).**
   - **`preview` environment**: uses `TRIGGER_SECRET_KEY_PREVIEW` (falls back to prod key if unset), adds `x-trigger-branch` header — hits isolated Trigger.dev environments without a separate secret per branch.
   - **Other environments**: standard secret key, no branch header.
4. **If `trigger_and_wait/4`**: polls with exponential backoff (1s → 5s), not a fixed interval — short-running tasks resolve quickly without hammering the API on long ones.
5. **Result retrieval via `get_run/1`.**
   - **If output is small**: returned inline.
   - **If output is large**: Trigger.dev offloads it to S3 (`outputPresignedUrl`/`outputUrl`); `get_run/1` transparently follows the redirect and decodes via `TriggerDev.SuperJSON`. Callers never need to know which path was taken.
6. **If the caller needs the full run tree** (e.g., Workflow Status or Agent Inspection panels): `get_deep_run/1` recursively expands child runs for known task-identifier prefixes (`workflow-`, `fund-deep-diligence-`, `person-research-`, plus `deep-research`, `compile-person-dossier`, `gather-sources`, `build-knowledge-parquet`) — reconstructs the tree of a top-level run fanning into dozens of child runs.
7. **Realtime status (for live UI updates, not one-shot calls):**
   - `lib/trigger_dev/realtime.ex` reimplements Trigger.dev's `useRealtimeRun` React hook for LiveView, polling every ~1.5-3s with terminal-state detection.
   - `sse_client.ex` provides an SSE alternative against `/realtime/v1/runs/:id`.
   - Either powers live-updating progress in the Workflow Status tab (proc-fund-dashboard-ui) without a page refresh.

## Deploy Model (Context, Not a Runtime Step)

- Trigger.dev workflows deploy independently of the Phoenix app (`npx trigger.dev deploy --env {preview,staging,prod}`), secrets managed in the Trigger.dev dashboard, not app `.env` files.
- The two runtimes are versioned and released separately — this is part of why the preview-branch header logic (step 3) exists: a Phoenix preview deploy and a Trigger.dev preview deploy aren't guaranteed to land at the same moment.

## Systems and Tools

- `lib/trigger_dev/client.ex`, `lib/trigger_dev/realtime.ex`, `sse_client.ex`.
- `TriggerDev.SuperJSON`.

## Known Issues

- Independent deploy cadence is a deliberate choice, but creates a theoretical window where a payload/schema mismatch is possible if one side deploys ahead of the other without coordination. `[UNKNOWN: whether any contract-versioning/compatibility check exists]`

## Open Questions

- Is there any automated check that Elixir's expected Trigger.dev payload shapes stay in sync with what's actually deployed?
