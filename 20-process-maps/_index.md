---
title: "Process Maps Index"
status: active
updated: 2026-07-17
---

# Process Maps

## Main Flow

- [Deal Analysis Pipeline — Upload to IC Memo](proc-deal-analysis-pipeline.md) — full `workflow-master-fund` sequence, upload through completed L1 memo, with decision points, skip conditions, and known wiring/sequencing issues.

## Sub-processes

Per-stage detail, one file per `10-observations/` source. Each links back into the main flow above.

- [Document Upload, Ingestion & Classification](proc-document-ingestion-classification.md)
- [Fund Classification (Pass 1)](proc-fund-classification.md)
- [Data Extraction from Pitch Decks](proc-data-extraction.md)
- [SEC Filing Diligence](proc-sec-filing-diligence.md)
- [Key Personnel Intelligence & Classification](proc-key-personnel-intelligence.md)
- [People Deep Research](proc-people-deep-research.md)
- [Fund Deep Research](proc-fund-deep-research.md)
- [Scoring & Rubric Analysis](proc-scoring-rubric.md)
- [L1 Analysis (Final IC Memo)](proc-l1-analysis.md)
- [Gemini Call-Pattern Selection](proc-gemini-usage-patterns.md) — cross-cutting, not a stage
- [Web Research Dispatch (Jina/Exa)](proc-web-research-providers.md) — cross-cutting, not a stage
- [Operator Navigation — Fund Dashboard](proc-fund-dashboard-ui.md) — human/operator flow, not automated
- [Elixir → Trigger.dev Call Flow](proc-elixir-trigger-bridge.md) — infrastructure mechanics
- [Knowledge Agent — Chat Query Flow](proc-knowledge-agent-chat.md) — interactive, on-demand
- [Infrastructure Status Reference](proc-infrastructure-dormant-out-of-scope.md) — not a true process, kept for parity
