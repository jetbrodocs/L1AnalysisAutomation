---
title: "Process: Operator Navigation — Fund Dashboard"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [pipeline, ui, ops-tooling]
---

# Process: Operator Navigation — Fund Dashboard

Built from: [obs-fund-dashboard-ui](../10-observations/obs-fund-dashboard-ui.md). Not a pipeline stage — this maps how a human operator moves through the fund-detail screen to review, debug, or extend an analysis. Sits alongside [proc-deal-analysis-pipeline](proc-deal-analysis-pipeline.md), reading its outputs.

## Process Overview

- **Purpose**: Give an operator a path to review a fund's analysis, diagnose a failure, or ask an ad hoc question the standard pipeline didn't answer.
- **Trigger**: Operator opens a fund's detail screen (`PitchDeckWorkflowProgressLive`), typically after `workflow-master-fund` completes or fails.
- **End condition**: Varies by branch — issue resolved, fund reviewed, or ad hoc question answered.

## Roles Involved

- **Operator** — reviews pipeline output, debugs failures, or extends research.

## Process Steps (Typical Triage Path)

1. Operator opens fund detail screen. Most panels are tabs (`?tab=` query param, socket stays alive on switch); Gemini Store and Agent Inspection are standalone routes.
2. **Check Workflow Status tab first** (`WorkflowStepperComponent` + `TriggerLogsComponent`) — vertical stepper (upload → page conversion → parsing → asset-class classification → extraction → SEC diligence → team research → …), live per-step status (pending/current/completed/failed), live execution log console.
3. **Decision point — did every step complete?**
   - **Yes, all completed** → go to step 4 (review results).
   - **No, a step failed** → go to Exception A (targeted rerun) or Exception B (full rerun).
4. **Review results** across relevant tabs, typically in this order:
   - **Fund Intelligence** — polished read-only "final answer" view of extraction output (numbered magazine-style sections: Overview & Model, Leadership/Team, Strategy & Focus, Track Record, Pipeline, Analyst Disclosures).
   - **Slide Analysis** — QA check of what was actually extracted per slide ("Extracted Data" vs. "OCR Slide Data"), export buttons for Consolidated MD/JSON.
   - **SEC Data / People / Fund Deep Research / Scoring / L1 Analysis** tabs — display outputs of the respective pipeline stages (see proc-sec-filing-diligence, proc-key-personnel-intelligence, proc-fund-deep-research, proc-scoring-rubric, proc-l1-analysis).
5. **If something looks wrong or incomplete** → go to Exception C (deep debug) or Exception D (ask a custom question).

### Exception A: Single Step Failed

A1. Operator identifies the failed step in the Workflow Status stepper.
A2. Operator clicks "rerun_task" for that step — mapped to a specific Trigger.dev task identifier (`workflow-process-pitch-deck`, `acquire-sec-diligence`, `find-fund-website`, `compile-target-research-team`, etc.).
A3. Only that stage re-runs — the rest of the ~4-hour pipeline is not re-triggered.
A4. Return to step 3.

### Exception B: Systemic Failure / Full Rerun Needed

B1. Operator clicks "Dry Run Full" on the Workflow Status tab.
B2. Entire pipeline re-triggers from scratch.
B3. Return to step 2.

### Exception C: Deep Debug ("why did the model conclude X?")

C1. Operator opens **Agent Inspection** (standalone `DocumentAgentsLive`, `/funds/:id/agents`) — read-only trace over every autonomous agent call for the fund, filterable by pipeline run/search/status.
C2. Operator clicks into a specific agent call — sees full conversation turns, tool calls, async LLM-generated summary.
C3. If the issue is a raw-output question rather than an agent-reasoning question, operator instead opens **Debug Payload** (`system_debug_view`) — syntax-highlighted raw JSON dump (`document.parsed_data`, falling back to `trigger_full_run["output"]`), "Copy Raw JSON" button.
C4. If the issue is about Gemini file/store staleness, operator opens **Gemini Store** (standalone `DocumentGeminiStoreLive`) — lists every uploaded Gemini file reference, filterable by search/task/status. Operator can click **"sync_metadata"** per file to refresh expiration state from the live Gemini API or mark `EXPIRED`.
C5. If the issue is about website-sourced data specifically, operator opens **Website Extraction** (`website_research_dashboard`) — visited URLs, search queries, SEC- vs. deck-sourced candidates, own "Trigger Execution Logs" sub-tab and scoped "rerun_task" button.
C6. For raw run-log detail beyond the stepper, operator opens **Task Logs** (`TriggerLogsComponent`, standalone) — terminal-styled console, links to full-log view (`/funds/:id/workflow/log/:run_id`).

### Exception D: Ask a Custom Question (Escape Hatch)

D1. Operator opens **Custom Research** tab (`CustomResearchComponent`).
D2. Operator defines a named research topic (extraction prompt, system prompt, research prompt), saves as a `custom_research` Ash record.
D3. **Decision point — which action?**
   - `run_custom_agent` — grounds against the fund's Gemini File Search store (ad hoc version of Pattern 4 in proc-gemini-usage-patterns).
   - `run_custom_research` — full open-web deep-research call (ad hoc version of proc-web-research-providers).
D4. Either action supports a `force`/no-cache override.
D5. Result returned inline in the Custom Research tab — no further pipeline steps triggered.

## Systems and Tools

- `PitchDeckWorkflowProgressLive`, `WorkflowStepperComponent`, `TriggerLogsComponent`, `WorkflowProgressHelper.workflow_steps/3`.
- `DocumentGeminiStoreLive`, `DocumentAgentsLive`.
- `CustomResearchComponent`, `custom_research` Ash record.

## Known Issues

- None flagged as bugs — this section of source material is primarily descriptive of operator tooling.

## Open Questions

- Who are the actual day-to-day operators, and what's their typical triage order in practice (does it match the sequence above)?
- How often is "Dry Run Full" used vs. targeted "rerun_task"?
