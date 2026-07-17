---
title: "Observations Index"
status: active
updated: 2026-07-17
---

# Observations

Source for all entries below: `00-inbox/pipeline-architecture.md` (Deal Analysis Pipeline — Business Logic Reference), audited against the codebase 2026-07-17.

- [Document Upload, Ingestion & Classification](obs-document-ingestion-classification.md) — §1-2
- [Fund Classification (Pass 1)](obs-fund-classification.md) — §3
- [Data Extraction from Pitch Decks](obs-data-extraction.md) — §4
- [SEC Filing Diligence](obs-sec-filing-diligence.md) — §5
- [Key Personnel Intelligence & Classification](obs-key-personnel-intelligence.md) — §6
- [People Deep Research](obs-people-deep-research.md) — §7
- [Fund Deep Research](obs-fund-deep-research.md) — §8
- [Scoring & Rubric Analysis](obs-scoring-rubric.md) — §9 (core of the platform)
- [L1 Analysis (Final IC Output)](obs-l1-analysis.md) — §10
- [Gemini — Cross-Cutting Usage Patterns](obs-gemini-usage-patterns.md) — §11
- [Jina + Exa — Web Research Provider Usage](obs-web-research-providers.md) — §12
- [Fund Dashboard — Operator-Facing UI](obs-fund-dashboard-ui.md) — §13
- [Elixir ↔ Trigger.dev Bridge](obs-elixir-trigger-bridge.md) — §14
- [Knowledge Agent — Chat With Your Data](obs-knowledge-agent-chat.md) — §15
- [Infrastructure — Provisioned/Dormant & Explicitly Out of Scope](obs-infrastructure-dormant-out-of-scope.md)

## Confirmed gaps/dead code flagged across these observations

- Scoring: `master-workflow.ts` doesn't pass `fileSha256`/`kbStoreName`/`ddResult` into `fullScoringWorkflow` — see [scoring observation](obs-scoring-rubric.md).
- L1: `master-workflow.ts` doesn't pass `consolidatedKnowledge`/`scoreResult` into `l1AnalysisWorkflow` — see [L1 observation](obs-l1-analysis.md).
- `score-agent.ts` — dead code, zero call sites, drifted alias logic — see [scoring observation](obs-scoring-rubric.md).
- `RuvectorServer` never started — Vector/HNSW mode in Knowledge Agent silently falls back to lexical search — see [knowledge agent observation](obs-knowledge-agent-chat.md).
- Three unreconciled asset-class taxonomies — see [fund classification observation](obs-fund-classification.md).
