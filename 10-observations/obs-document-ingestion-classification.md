---
title: "Observation: Document Upload, Ingestion & Classification"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [pipeline, ingestion, classification, elixir, trigger-dev]
---

# Observation: Document Upload, Ingestion & Classification

Source: `00-inbox/pipeline-architecture.md` §1-2, audited against codebase.

## Activity

Deal-analysis pipeline entry: a file (pitch deck, tear sheet, etc.) is uploaded, stored, deduped, classified by document type, rasterized into page images, and — if it clears a document-type allowlist — promoted into a `Fund`/`Document` record that auto-triggers the full downstream analysis pipeline (`workflow-master-fund`).

## Inputs

- Webhook upload: external system POSTs `{file_urls, file_names, callback_url, workspace_id, deal_id}` to `FundUploadController.upload/2`; server pulls each URL.
- Direct browser upload via LiveView.

## Outputs

- File stored in Tigris (S3-compatible) at `decks/<sha256>.<ext>`.
- SHA-256 hash used as both storage key and DB lookup key (`get_client_upload_by_sha/1`).
- Page images at `<sha>/<paddedPage>/<sizeLabel>.jpg` (three size tiers: thumbnail 36 PPI, preview 144 PPI, large 300 PPI).
- One structured LLM classification result: `document_type`, `fund_name`, `company_name`, `key_principals[]`, `summary`, `fund_classification`, `asset_class`, `sector`.
- If promoted: new/matched `Fund` record, new `Document` record, triggered `workflow-master-fund` run.
- A per-fund Gemini File Search store (RAG index), opened at classification time.

## Systems

- `FundUploadController.upload/2` (Elixir webhook entry)
- `Uploads.ClientUpload` — Ash state-machine resource: `uploading → pending_initialization → processing → downloading → generating_thumbnails → uploading_to_gemini → processing_gemini → classifying → analyzing → promoted/completed/failed`
- `workflow-document-classify-and-summary` (Trigger.dev, Gemini Flash-Lite, structured output)
- `pdf_to_images` (`src/trigger/pitch-deck/pdf-to-images.ts`) — concurrency 1, `large-2x` machine, 10-min max
- `workflow-generate-thumbnails` (`src/trigger/pitch-deck/generate-thumbnails.ts`) — parallelizes across CPU-core chunks
- `regenerate_pdf_preview/1` (`lib/deals_analysis/documents/workflows.ex`) — two-phase priority rendering
- `sweep_processing_uploads/0` — polling reconciliation sweep against Trigger.dev run status. Uploads/batches are cancellable, which also cancels downstream Trigger.dev runs.
- Named Trigger.dev queues, env-tunable concurrency, so a burst of uploads doesn't starve any one stage: `diligence-workflows`, `llm-generation` (default 20), `sec-scraping` (default 10), `jina-deep-research`, `jina-api`, `deep-research-bulk` (default 10), `test-generation` (fixed 1).

## Orchestration — What Fires on Promotion

The moment a document is promoted (see promotion gate below), one task kicks off the entire rest of the pipeline: `workflow-master-fund` (`master-workflow.ts`, up to 4h max duration, retry 1-2x on failure). This is the one workflow that runs, unconditionally, every time a new marketing document clears the promotion gate — nothing downstream (extraction, diligence, research, scoring, memo) is triggered any other way.

Five internal steps, each wrapped in its own try/catch **except step 1**, which is not — a failure there aborts the entire run, unlike steps 2-5 which fail gracefully (null result, run continues):

1. `processPitchDeckWorkflow` — schema/entity extraction, SEC-entity resolution (run once here so later diligence steps can skip it), fund-maturity classification. **Not wrapped in try/catch — failure aborts the whole run.**
2. Person research per key principal, batch-triggered via `personResearchWorkflow` — skipped entirely if no principals were found in step 1.
3. `fundDeepDiligenceWorkflow` — explicitly skips re-running SEC diligence, since step 1 already produced it.
4. `fullScoringWorkflow`.
5. `l1AnalysisWorkflow` — final IC memo.

Steps 2 and 3 both only depend on step 1's output, but as currently written they run **sequentially, not concurrently** — `master-workflow.ts` awaits step 2 (person research) fully before starting step 3 (fund deep diligence). Flagged as a real optimization opportunity, not yet taken: person research and fund research have no dependency on each other and could run in parallel.

**Completion sync.** When all five steps resolve (or fail gracefully), `workflow-master-fund` posts a webhook back to the Elixir app at `{APP_URL}/api/webhooks/trigger_sync` with `_sync: {state: "analysis completed", l1_analysis_cache, parsed_data_merge}`, which flips the `Document` state machine to `scoring completed` and makes the finished analysis visible in the UI. If the original upload came in via the webhook path, the stored `callback_url` also receives a completion notification at this point.

## People / Actors

- No human review in the ingestion/classification path — fully automated.
- One LLM call (Gemini Flash-Lite) performs classification.
- MIME type inferred mechanically from file extension (pdf/pptx/ppt/xlsx/docx recognized; else `application/octet-stream`, not rejected).

## Timing

- Two-phase rendering: page-1 thumbnail fires at priority 10 (visible within seconds of upload); full deck fires at priority 0 (completes before extraction needs it, doesn't block fast path).
- `pdf_to_images` / `workflow-generate-thumbnails`: 10-min max duration each.
- Re-upload of identical bytes: no new processing at all (SHA-256 dedup catches it before classification).

## Problems / Gaps / Workarounds

- **Rasterization fallback**: if `pdftoppm` fails on a page (corrupt embedded fonts, unusual color profiles), code falls back to ImageMagick (`magick`) rather than failing the whole document.
- **12 document types classified, only 8 promoted.** `document_type` enum has 12 values; only `pitch_deck, tear_sheet, fact_sheet, fund_overview, investor_presentation, ppm, marketing_flyer, quarterly_report` pass the promotion gate. `data_room_document, financial_statement, legal_document, unknown` are stored but never analyzed — this is a hardcoded allowlist, the single gate deciding whether a fund gets evaluated at all.
- **Duplicate rendering paths**: two separate implementations (`pdf_to_images` and `workflow-generate-thumbnails`) run largely in parallel with overlapping responsibility — not reconciled into one path.
- Two rasterization implementations exist with overlapping purpose (`pdf_to_images` vs `workflow-generate-thumbnails`) — not flagged as a bug in source doc, but worth confirming intentional with the team. `[UNKNOWN: whether this duplication is deliberate (redundancy) or historical drift]`

## Open Questions

- Is the `data_room_document`/`financial_statement`/`legal_document` exclusion from analysis an intentional product decision, or a gap (e.g., financial statements plausibly contain analyzable data)?
- Why do two separate page-rasterization implementations exist in parallel?
