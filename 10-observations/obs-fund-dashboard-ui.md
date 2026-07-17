---
title: "Observation: Fund Dashboard — Operator-Facing UI"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [pipeline, ui, liveview, ops-tooling]
---

# Observation: Fund Dashboard — Operator-Facing UI

Source: `00-inbox/pipeline-architecture.md` §13, audited against codebase. This is the operator-facing UI sitting on top of the pipeline (§1-10), not the pipeline itself.

## Activity

Fund-detail workflow screen, `DealsAnalysisWeb.PitchDeckWorkflowProgressLive`. Most panels are tabs on one LiveView (`?tab=` query param, socket stays alive on switch); Gemini Store and Agent Inspection are standalone LiveViews at their own routes.

## Location / Station

- Elixir/Phoenix LiveView, `lib/deals_analysis_web/live/pitch_deck_workflow_progress/`.

## Panels Observed

- **Fund Intelligence** (`pitch_deck_summary/1`) — read-only "final answer" view of extraction output (`document.parsed_data`, `document.master_data`, `sec_data`) as numbered magazine-style sections (Overview & Model, Leadership/Team, Strategy & Focus, Track Record, Pipeline, Analyst Disclosures). Distinct from the L1 memo — raw structured facts, not IC synthesis.
- **Slide Analysis** (`SlidesTabComponent`) — QA tool for verifying per-slide extraction, toggled between "Extracted Data" (structured, tied to rasterized page images) and "OCR Slide Data" (raw per-slide markdown/OCR + annotations). Has "Consolidated MD" / "Consolidated JSON" export buttons.
- **Workflow Status** (`WorkflowStepperComponent` + `TriggerLogsComponent`) — ops/monitoring view of `workflow-master-fund` orchestration: vertical stepper (upload → page conversion → parsing → asset-class classification → extraction → SEC diligence → team research → …), live per-step status computed from `WorkflowProgressHelper.workflow_steps/3`, plus live execution log console. Operator actions: **"Dry Run Full"** (re-triggers entire pipeline from scratch) and per-step **"rerun_task"** (mapped to specific Trigger.dev task identifiers: `workflow-process-pitch-deck`, `acquire-sec-diligence`, `find-fund-website`, `compile-target-research-team`, etc.) — a single failed stage can be re-run without re-running the whole ~4-hour pipeline.
- **Custom Research** (`CustomResearchComponent`) — the one panel that's a trigger UI, not a viewer. Operator defines a named research topic (extraction prompt, system prompt, research prompt), saves as a `custom_research` Ash record, fires via `run_custom_agent` (grounds against fund's Gemini File Search store, ad hoc version of Pattern 4) or `run_custom_research` (full open-web deep-research call, ad hoc version of §12), each with a `force`/no-cache override. Escape hatch for "the standard pipeline didn't ask this specific question — ask it now."
- **Gemini Store** (standalone `DocumentGeminiStoreLive`, `/funds/:id/gemini_store`) — ops/debug window into raw Gemini Files API usage. Lists every uploaded file reference (display name, `gemini_file_id`, size, uploading task, expiration state), filterable by search/task/status, plus grounding queries run against those files. Action: **"sync_metadata"** per file — calls live Gemini API to refresh expiration state or mark `EXPIRED`, catching staleness since Gemini Files auto-expire after a fixed window.
- **Agent Inspection** (standalone `DocumentAgentsLive`, `/funds/:id/agents`) — read-only trace/observability view over every autonomous agent call for a fund (the `Agent` Ash resource), filterable by pipeline run/search/status. Clicking an agent shows full conversation turns + tool calls, each with an async LLM-generated summary — debugging tool for "why did the scoring/research agent conclude X." Second tab lists Gemini file-search vector stores and indexed documents.
- **Website Extraction** (`website_research_dashboard`) — output of `find-fund-website` task: visited URLs, search queries, SEC-sourced vs. deck-sourced website candidates, extracted `fundData`, team members sourced from the website (tagged "(Website)" in unified team list). Own "Trigger Execution Logs" sub-tab and scoped "rerun_task" button.
- **Task Logs** (`TriggerLogsComponent`, standalone from stepper) — raw terminal-styled console of Trigger.dev run log: task identifier, version, per-attempt start/success/error events with durations. Links to full-log view (`/funds/:id/workflow/log/:run_id`). Pure ops console, no interactive actions beyond that link.
- **Debug Payload** (`system_debug_view` + `l1_debug_layout`) — syntax-highlighted, pretty-printed dump of raw JSON a workflow run produced (`document.parsed_data`, falling back to raw `trigger_full_run["output"]`), "Copy Raw JSON" button, plus L1 debug layout sub-tab. Tool of last resort for diagnosing extraction bugs.
- L1 Analysis, SEC Data, People, Fund Deep Research, and Scoring are also tabs on this screen — see their respective §5-10 observations for detail; they display the outputs of those pipeline stages.

## People / Actors

- Operators (internal team members reviewing/debugging fund analyses) — the primary users of this dashboard. `[UNKNOWN: specific roles/headcount using this UI day to day]`

## Timing

- Workflow Status "Dry Run Full" re-runs the entire ~4-hour pipeline. Per-step "rerun_task" scopes re-runs to a single stage.
- Realtime status polling every ~1.5-3s (see Elixir↔Trigger.dev bridge observation).

## Problems / Gaps / Workarounds

- None flagged as bugs in this section of the source doc — this section is primarily descriptive of operator tooling, not a defect audit.

## Open Questions

- Who are the actual day-to-day operators using this dashboard, and what's their typical workflow (triage order across panels)?
- How often is "Dry Run Full" actually used vs. targeted per-step reruns?
