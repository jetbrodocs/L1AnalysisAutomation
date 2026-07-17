---
title: "Process: Knowledge Agent — Chat Query Flow"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [pipeline, knowledge-agent, chat]
---

# Process: Knowledge Agent — Chat Query Flow

Built from: [obs-knowledge-agent-chat](../10-observations/obs-knowledge-agent-chat.md). Interactive feature, separate from the automatic Trigger.dev pipeline — operator/analyst-driven, not fund-upload-triggered.

## Process Overview

- **Purpose**: Let a user ask natural-language questions against a fund's extracted knowledge base and schema, on demand.
- **Trigger**: User opens Graph Explorer page (`/funds/:id/graph_explorer`) and types a question.
- **End condition**: Answer returned with citations (where applicable) and estimated token cost.

## Roles Involved

- **User** — operator/analyst posing questions per fund.

## Process Steps

1. User opens `GraphExplorerLive` for a specific fund.
2. User selects a retrieval strategy (decision point):
   - **SIRA** — hybrid search with LLM query expansion, document-frequency-validated synonym candidates, reciprocal rank fusion. Further choice: search against "knowledge" DB (document chunks) or "metadata" DB (schema topics).
   - **GraphRAG** — traverses a schema subgraph to answer conceptual questions.
   - **Vector (HNSW)** — search with LLM query reformulation. **See Known Issues — this option does not behave as its name implies.**
   - **Lexical (BM25)** — DuckDB full-text search with keyword extraction.
   - **Gemini File Search** — calls Google's Generative Language API directly against the fund's named Gemini file-search store, returns grounded citations (same mechanism as proc-gemini-usage-patterns Pattern 4, exposed here as a user-selectable mode).
3. User types question, submits.
4. Agent maintains per-document chat history for context.
5. Agent streams "thought" messages during processing (e.g., "Initiating Hybrid SIRA Search...").
6. Agent returns final answer with estimated token cost.

### Exception: Vector (HNSW) Selected

E1. User selects "Vector (HNSW)" expecting semantic search over a compiled index built from schema metadata.
E2. Every caller (`KnowledgeSearcher.search_metadata`, `IdentifyKeysAction`) checks `GenServer.whereis/1` for `DealsAnalysis.VectorDB.RuvectorServer`.
E3. **`RuvectorServer` is never started** — absent from `application.ex`'s supervision tree, as deployed today.
E4. Caller silently falls back to BM25/lexical search.
E5. User receives a lexical-search result, not a semantic one — with no indication in the UI that the fallback occurred.

## Systems and Tools

- `DealsAnalysis.Research.KnowledgeAgent` (`lib/deals_analysis/research/knowledge_agent/`), `GraphExplorerLive`.
- `native/ruvector_nif` (Rust NIF via Rustler, `ruvector-core`/`ruvector-graph`), `DealsAnalysis.VectorDB.Ruvector`, `SchemaDbSync`.

## Known Issues

- **Confirmed live correctness gap.** Vector/HNSW mode is fully implemented but functionally dead — the backing GenServer is never started, so selecting it silently produces a lexical-search result instead of a semantic one. Fix: add `RuvectorServer` to the supervision tree.
- **Naming artifact.** The "RuVector" persona used elsewhere in `GraphExplorerLive`/`RuvectorAgent` is misleading — that code path prompts an LLM over a raw Cypher-text graph string and does not call the Ruvector NIF at all, despite the shared name.

## Open Questions

- Is disabling `RuvectorServer` intentional (resource cost, instability) or an oversight? Worth checking before flipping it on.
- Any way to audit how many users selected "Vector (HNSW)" expecting semantic search and unknowingly got lexical results?
