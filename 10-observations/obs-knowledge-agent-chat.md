---
title: "Observation: Knowledge Agent — Chat With Your Data"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [pipeline, knowledge-agent, chat, correctness-gap]
---

# Observation: Knowledge Agent — Chat With Your Data

Source: `00-inbox/pipeline-architecture.md` §15, audited against codebase. Separate from the automatic Trigger.dev research pipeline (§7-8) — this is a live, interactive feature.

## Activity

A user opens a fund's Graph Explorer page and types natural-language questions against that fund's extracted knowledge base and schema. The agent maintains per-document chat history, routes each query through a selectable retrieval strategy, streams "thought" messages, then returns an answer with estimated token cost.

## Inputs

- User's natural-language question.
- Selected retrieval strategy.
- Fund's extracted knowledge base + schema.

## Outputs

- Streamed "thought" messages (e.g., "Initiating Hybrid SIRA Search...").
- Final answer with estimated token cost.

## Systems

- `DealsAnalysis.Research.KnowledgeAgent` (`lib/deals_analysis/research/knowledge_agent/`), exposed at `/funds/:id/graph_explorer` (`GraphExplorerLive`).
- Retrieval strategies, user-selectable:
  - **SIRA** — hybrid search with LLM query expansion, document-frequency-validated synonym candidates, reciprocal rank fusion; searchable against "knowledge" DB (document chunks) or "metadata" DB (schema topics).
  - **GraphRAG** — traverses a schema subgraph to answer conceptual questions.
  - **Vector (HNSW)** — search with LLM query reformulation.
  - **Lexical (BM25)** — DuckDB full-text search with keyword extraction.
  - **Gemini File Search** — calls Google's Generative Language API directly against a named Gemini file-search store, returns grounded citations (same mechanism as §11 Pattern 4, exposed here as a user-selectable mode).

## People / Actors

- Interactive feature used by a human operator/analyst posing questions per fund.

## Timing

- `[UNKNOWN: response latency per query/strategy]`

## Problems / Gaps / Workarounds

- **Confirmed live correctness gap**: Vector/HNSW mode is backed by `native/ruvector_nif` (Rust NIF via Rustler, wrapping `ruvector-core`/`ruvector-graph`), exposed as `DealsAnalysis.VectorDB.Ruvector`, reading a compiled index built from schema metadata (not deal content), synced from Tigris by `SchemaDbSync`. **`DealsAnalysis.VectorDB.RuvectorServer` is never started** — absent from `application.ex`'s supervision tree. Every caller (`KnowledgeSearcher.search_metadata`, `IdentifyKeysAction`) guards with `GenServer.whereis/1` and silently falls back to BM25/lexical search whenever the process isn't running — which, as deployed, is always. **The Vector/HNSW option in the UI is fully implemented but functionally dead: selecting it produces a lexical-search result, not a semantic one.** Fix: add the GenServer to the supervision tree.
- **Naming artifact**: the "RuVector" persona name used elsewhere in `GraphExplorerLive`/`RuvectorAgent` is misleading — that code path prompts an LLM over a raw Cypher-text graph string and does not call the Ruvector NIF at all, despite the shared name.

## Open Questions

- Is starting `RuvectorServer` in the supervision tree a trivial fix, or does it carry a known reason for being disabled (e.g., resource cost, instability)? Worth checking before flipping it on.
- How many users have selected "Vector (HNSW)" expecting semantic search and unknowingly gotten lexical results — any way to audit usage logs for this?
