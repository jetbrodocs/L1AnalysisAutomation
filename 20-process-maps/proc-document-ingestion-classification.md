---
title: "Process: Document Upload, Ingestion & Classification"
status: draft
created: 2026-07-17
updated: 2026-07-17
tags: [pipeline, ingestion, classification]
---

# Process: Document Upload, Ingestion & Classification

Built from: [obs-document-ingestion-classification](../10-observations/obs-document-ingestion-classification.md). Sub-process of steps 1-5 in [proc-deal-analysis-pipeline](proc-deal-analysis-pipeline.md).

## Process Overview

- **Purpose**: Turn an uploaded file into a stored, classified, promoted-or-rejected document, and (if promoted) trigger the full analysis pipeline.
- **Trigger**: File arrives via webhook POST or browser upload.
- **End condition**: Document is either promoted (Fund/Document records created, `workflow-master-fund` fired) or stored-only (no further action).

## Roles Involved

- **Uploader** — external system (webhook) or human (browser). No role past step 1.
- **Pipeline** — fully automated for the rest of the flow.

## Inputs and Outputs

- **Input**: `{file_urls, file_names, callback_url, workspace_id, deal_id}` (webhook) or direct file (browser).
- **Output**: stored file + page images in Tigris; classification result; promoted `Fund`/`Document` records (conditional).

## Process Steps

1. File arrives via `FundUploadController.upload/2` (webhook, server pulls each URL) or LiveView browser upload.
2. SHA-256 computed over raw bytes.
   - **If hash matches an existing upload:** dedup — file already stored, DB lookup via `get_client_upload_by_sha/1`, no new storage or re-processing. Process ends here.
   - **If new hash:** continue to step 3.
3. File written to Tigris at `decks/<sha256>.<ext>`. MIME type inferred from extension (else `application/octet-stream`, not rejected).
4. `ClientUpload` state machine advances: `uploading → pending_initialization → processing → downloading → generating_thumbnails → uploading_to_gemini → processing_gemini → classifying`.
5. **Page rasterization fires** (parallel to classification, not blocking it):
   - 5a. `regenerate_pdf_preview/1` fires two Trigger.dev requests: page-1 thumbnail at priority 10, full deck at priority 0.
   - 5b. `pdfinfo` gets page count, `pdftoppm` rasterizes each page into `preview` (144 PPI) and `thumbnail` (36 PPI); `workflow-generate-thumbnails` also adds `large` (300 PPI) tier, parallelized across CPU-core-derived chunks.
     - **Exception — `pdftoppm` fails on a page** (corrupt fonts, unusual color profile): fall back to ImageMagick (`magick`) for that page rather than failing the whole document.
   - 5c. Every image written to Tigris at `<sha>/<paddedPage>/<sizeLabel>.jpg`.
6. **Classification.** One Gemini Flash-Lite call over the PDF (via Gemini Files API) returns `document_type`, `fund_name`, `company_name`, `key_principals[]`, `summary`, `fund_classification`, `asset_class`, `sector`. This call also opens a per-fund Gemini File Search store.
7. **Promotion gate (decision point).**
   - **If `document_type` in {`pitch_deck, tear_sheet, fact_sheet, fund_overview, investor_presentation, ppm, marketing_flyer, quarterly_report`}:** promote — go to step 8.
   - **If `document_type` in {`data_room_document, financial_statement, legal_document, unknown`}:** stored only. State machine ends at `classifying`/`completed`, never reaches `analyzing`. Process ends here.
8. `Fund` record created/matched by `fund_name`; `Document` record created; state advances to `analyzing`.
9. `workflow-master-fund` auto-triggers, unconditionally, for this document. → continues in [proc-deal-analysis-pipeline](proc-deal-analysis-pipeline.md) step 6.

### Exception: Stuck Upload

- **Detection**: `sweep_processing_uploads/0` polling sweep reconciles stuck uploads against Trigger.dev run status.
- **Resolution**: uploads/batches are cancellable, which also cancels downstream Trigger.dev runs.

### Re-upload Path

- Same fund, new document bytes (e.g. updated quarterly deck): SHA-256 differs → treated as new upload, runs full flow above, creates a new `Document` linked to the *existing* `Fund` (matched by `fund_name` in step 8), triggers a fresh `workflow-master-fund` run scoped to the new document.

## Systems and Tools

| Step | System |
|---|---|
| 1 | `FundUploadController.upload/2`, LiveView |
| 2-4 | Tigris, `Uploads.ClientUpload` (Ash state machine) |
| 5 | `pdf_to_images`, `workflow-generate-thumbnails`, `pdftoppm`, ImageMagick |
| 6 | `workflow-document-classify-and-summary`, Gemini Flash-Lite |
| 8-9 | `workflow-master-fund` (`master-workflow.ts`) |

**Queues** (env-tunable concurrency, prevents an upload burst from starving any one stage): `diligence-workflows`, `llm-generation` (default 20), `sec-scraping` (default 10), `jina-deep-research`, `jina-api`, `deep-research-bulk` (default 10), `test-generation` (fixed 1).

## Known Issues

- Two rasterization implementations (`pdf_to_images`, `workflow-generate-thumbnails`) run with overlapping responsibility — not reconciled. See [obs-document-ingestion-classification](../10-observations/obs-document-ingestion-classification.md).
- 4 of 12 document types are stored but never analyzed (step 7) — hardcoded allowlist, single gate for whether a fund gets evaluated at all.

## Open Questions

- Is the data_room/financial_statement/legal_document exclusion from analysis intentional or a gap?
- Why two rasterization implementations in parallel?
