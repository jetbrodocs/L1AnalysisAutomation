---
title: "Screen Spec — Upload and Promotion"
status: draft
created: 2026-07-21
updated: 2026-07-21
tags: [screen-spec, intake, upload, deduplication, sha256, promotion, l1-analysis-platform]
---

# Screen Spec — Upload and Promotion

**Parent PRD:** `01-intake.md` (Screen 1 "Upload Document", Screen 3 "Promote Document" — one flow, see §1.1).

> **PRD 01 §8, the sentence this screen exists to honour:** the promotion screen must lead with the match proposal — *"This appears to be Neo Infra Income Opportunities Fund II. We already track that fund as DL-2026-0007, last document 2026-02-14. Attach this as document 2 of that Deal?"* — with "create a new Deal instead" as the secondary action. **If "new Deal" is the default, every updated deck silently becomes a duplicate Deal and the timeline feature dies quietly.**

> **Standalone principle (PRD 06 §0).** Intake is workflow. The engine takes a PDF path and an output directory; it has no concept of a deal, a duplicate, or a promotion. Nothing on this screen may become necessary to read the resulting memo.

---

## 1. Purpose

Get a file in, recognise whether it has been seen before, and attach it to the right Deal. **The identity model is the content hash, not the filename** — the supplied filename is metadata, never an identifier (PRD 01 §1).

**Reference data:** `Neo Infra Income Opportunities Fund-II Feb'26.pdf`, 5,639,481 bytes, 52 pages, sha256 `2b176083b2938978a9ab84ba1cc2fc72cad052ded1bcf4893293abd1a4613562`, classified `PITCH_DECK`, promoted to `DL-2026-0007`, producing run `fd33c73e`.

### 1.1 Why upload and promotion are one spec

They are one task in the analyst's head: "get this deck into the system." The gap between them is where the Deal/Document distinction becomes visible or invisible to the user, and it is the screen most likely to be got wrong (PRD 01 §8). Speccing them apart would put the design seam exactly where the risk is.

---

## 2. Entry Points

| # | From | Trigger | Context passed in | Conditions |
|---|---|---|---|---|
| 1 | Primary navigation | "Upload" | none — unscoped | Analyst |
| 2 | Deal list / board | `[+ Upload]` | none | Analyst |
| 3 | Deal Detail — Documents tab | "Upload document" | `deal_id` **pre-scoped — attach is certain, no matching needed** | Analyst |
| 4 | Deal Detail / Memo Reader | "Upload a PPM" from the bulk-resolve affordance | `deal_id`, `document_type = PPM`, the 12 target question keys | Deal has document-answerable open questions |
| 5 | Memo Reader §11 | "Upload a document" on a single `document_answerable` question | `deal_id`, `question_id` | — |
| 6 | Promotion Queue (PRD 01 Screen 2) | "Promote" on a queued document | `document_id`, skips upload, opens at promotion | Document `CLASSIFIED` |
| 7 | Document Detail (PRD 01 Screen 5) | "Promote" | `document_id` | Not yet promoted |
| 8 | Intake Dashboard (PRD 01 Screen 8) | Queue depth → promotion queue → promote | `document_id` | — |
| 9 | Drag-and-drop onto any page | File dropped anywhere in the app | File; deal scope if dropped onto a deal surface | Analyst |
| 10 | Command palette `⌘K` | "Upload document" action | none | Analyst |
| 11 | Deep link | `/upload`, `/upload?deal={id}`, `/documents/{id}/promote` | — | — |
| 12 | API upload (no UI) | External system posts a document | `upload_source_id` | Documents land in the promotion queue; **promotion is always human** |
| 13 | Empty-state prompts | "Upload a deck to start" from an empty deal list | none | — |
| 14 | Manager Detail | "Add a fund from this manager" | `manager_id` pre-filled | — |

---

## 3. UX Layout

Three steps, one screen. The analyst sees where they are and what remains.

```
  ①  Upload  ──────  ②  Recognised  ──────  ③  Attach
```

### 3.1 Step 1 — Upload

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│  Upload a document                                                                    │
│  ┌────────────────────────────────────────────────────────────────────────────────┐  │
│  │                                                                                 │  │
│  │                        Drop PDFs here, or browse                                │  │
│  │                                                                                 │  │
│  │             PDFs only · up to 50 MB each · multiple files fine                  │  │
│  └────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                       │
│  ⓘ The file is stored by its content hash, not its name. Two people forwarding the    │
│    same deck from the same email thread produce one stored document, whatever their   │
│    mail clients called it.                                                            │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

Per-file progress on upload: bytes transferred, then **hashing**, then classification. Hashing is named explicitly because it is what the system does next and it explains the recognition that follows.

### 3.2 Step 2 — Recognised (the critical screen)

Four outcomes. The order below is the order of the decision tree, and each has a different default.

#### Outcome A — Exact duplicate: this file has been seen before

`content_sha256` already exists. **This is not an error and is never presented as one.**

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│  ✓ We've seen this exact file before.                                                 │
│                                                                                       │
│  Neo Infra Income Opportunities Fund-II Feb'26.pdf                                    │
│  sha256 2b176083b2938978a9ab84ba1cc2fc72cad052ded1bcf4893293abd1a4613562              │
│                                                                                       │
│  Identical bytes to DOC-2026-000412, uploaded 2026-07-20 19:51 by Sharva Jethwa,      │
│  attached to DL-2026-0007 (Neo Infra Income Opportunities Fund II).                   │
│  That document has been analysed — v1, HOLD, 49 open questions.                       │
│                                                                                       │
│  Nothing new was stored. The file you uploaded and the one we hold are the same       │
│  bytes, so there is nothing to add.                                                   │
│                                                                                       │
│  [Open DL-2026-0007]      [Open the existing document]      [Upload something else]   │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

No "create anyway" affordance. Identical bytes cannot be a second document — the hash *is* the identity (PRD 01 §1), and offering to duplicate it would contradict the storage model.

#### Outcome B — New file, known fund: **attach is the default**

This is the path that matters. The deck is new bytes, but the fund is already tracked.

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│  This appears to be Neo Infra Income Opportunities Fund II.                           │
│                                                                                       │
│  We already track that fund as DL-2026-0007.                                          │
│  Last document: Neo Infra Income Opportunities Fund-II Feb'26.pdf, 2026-02-14.        │
│  Current stage: Initial Screening · latest analysis: HOLD, 49 open questions.         │
│                                                                                       │
│  ┌────────────────────────────────────────────────────────────────────────────────┐  │
│  │  ▶  Attach this as document 2 of DL-2026-0007                                   │  │
│  │                                                                                 │  │
│  │     The two documents sit on one timeline, and the analyses can be compared.    │  │
│  └────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                       │
│  Matched on: fund name (exact, p.1) · manager name (exact, p.37)     confidence: high │
│                                                                                       │
│  Not the same fund?   [Create a new Deal instead]                                     │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

The attach action is the large primary control with the consequence spelled out beneath it. "Create a new Deal instead" is a **text link, below, phrased as a correction to a proposal** — not a button of equal weight offering a symmetric choice. The match basis and confidence are always shown, so the analyst can judge the proposal rather than trust it.

**A near-duplicate is called out specifically**, because it is the case where creating a new Deal is most tempting and most wrong:

```
  ⓘ This looks like an updated version of the February deck — same fund, same manager,
    54 pages against 52, document date June 2026. Attaching keeps both on one timeline
    so the analyses can be compared. [What changed?]
```

#### Outcome C — Multiple candidate deals

Ranked list with match basis and confidence per candidate, most likely pre-selected but nothing auto-committed. "Create a new Deal instead" remains the last option, below all candidates.

#### Outcome D — No match: create a new Deal

Only here is a new Deal the default. The form is pre-filled from classification, with every field editable and each showing its source page:

| Field | Pre-filled | Source |
|---|---|---|
| Fund name | `Neo Infra Income Opportunities Fund II` | `01-classification.json`, p.1 |
| Manager | `Neo Asset Management Private Limited` | p.37 |
| AIF category | `CAT_II` | p.37, `STATED` |
| Document type | `PITCH_DECK` | Classifier |
| Document date | `February 2026` | p.1 |
| Deal track | `NEW` — auto-set to `RE_UP` if the manager is known | Manager lookup |
| Priority | Normal | Analyst |

**When the manager is known but the fund is not**, the screen says so, because it changes the track:

```
  ⓘ We don't track this fund, but we know Neo Asset Management — 1 prior commitment
    (NIIOF-I, ₹200 cr, 2023) and 1 deal in the pipeline.
    This will be created as a RE-UP.   [See the manager]
```

### 3.3 Step 3 — Submit for analysis

Confirms the deal, the criteria set that will be used (with a **draft warning when unversioned**), and the expected duration and cost.

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│  Ready to analyse                                                                     │
│                                                                                       │
│  Document   Neo Infra Income Opportunities Fund-II Feb'26.pdf · 52 pages              │
│  Deal       DL-2026-0007 · Neo Infra Income Opportunities Fund II                     │
│  Criteria   CS-2026-0001 · 17 criteria · ⚠ DRAFT — unversioned                        │
│                                                                                       │
│  ⚠ CS-2026-0001 has not been through an approval workflow. Findings will be marked    │
│    provisional, and the memo will carry a draft banner.        [Use a different set]  │
│                                                                                       │
│  Typically 8–16 minutes · about $2.30. You'll be notified; you don't need to wait.    │
│                                                                                       │
│  [Submit for analysis]                                    [Save without analysing]    │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

Stating the duration and cost up front is what makes the wait acceptable rather than a defect.

---

## 4. Data Points Displayed

### 4.1 Uploaded file

| Label | Value | Source |
|---|---|---|
| Filename | `Neo Infra Income Opportunities Fund-II Feb'26.pdf` — **display only** | `Document.original_filename` |
| sha256 | `2b176083b2938978a9ab84ba1cc2fc72cad052ded1bcf4893293abd1a4613562` full, copyable | `Document.content_sha256` |
| Size | `5.4 MB (5,639,481 bytes)` | `Document.byte_size` |
| Pages | `52` | `Document.page_count` |
| MIME | `application/pdf` — **detected from content, not extension** | `Document.mime_type` |
| Document code | `DOC-2026-000412` | `Document.document_code` |
| Uploaded at / by | `2026-07-20 19:51 · Sharva Jethwa` | `DOCUMENT_UPLOADED` |
| Source | `browser` / `API — {source_code}` | `Document.upload_source_id` |
| Status | `UPLOADED` → `CLASSIFIED` → `PROMOTED` / `REJECTED` / `DUPLICATE` | `Document.status` |

### 4.2 Classification

Document type (`PITCH_DECK`), analysable (`true`), confidence (`STATED` / `INFERRED` / `LOW`), fund name, manager name, AIF category, document date — each with its source page. On the reference run, classification took 12.0s and verified 7 of 7 quotes against their cited pages; that ratio is shown when confidence is below `STATED`.

### 4.3 Match proposal

Candidate deal code, fund name, manager, stage, last document date, latest recommendation, open-question count, document count, match basis (which fields matched, exact or fuzzy, with pages), match confidence.

### 4.4 Duplicate record

Existing `document_code`, upload date and uploader, attached deal, analysis outcome, and `duplicate_of_document_id`.

---

## 5. CTAs

| CTA | Behaviour |
|---|---|
| **Drop / Browse** | Selects files; upload begins immediately |
| **Attach as document N of DL-2026-0007** | **Primary in outcome B.** Sets `deal_id`, emits `DEAL_SUBMITTED`, proceeds to step 3 |
| **Create a new Deal instead** | **Secondary text link, never a primary button when a match exists.** Opens the new-deal form pre-filled, with a confirmation naming the consequence: "DL-2026-0007 already tracks this fund. A second Deal means two separate timelines and no comparison between them. Create anyway?" |
| **Select a different deal** | Search across deals by code, fund, or manager |
| **Open DL-2026-0007** / **Open the existing document** | Duplicate outcome navigation |
| **Submit for analysis** | Emits `DEAL_SUBMITTED` → PRD 02 queue; navigates to Run Progress |
| **Save without analysing** | Promotes without queueing a run |
| **Use a different criteria set** | Set picker, defaulting to the active set for the deal's category |
| **Reject** | `DOCUMENT_REJECTED` with a required reason |
| **Cancel upload** | Aborts in-flight transfer; nothing stored |
| **Remove file** | Removes from the batch before promotion |
| **What changed?** | On a near-duplicate — page-count and document-date comparison against the existing document |
| **See the manager** | Manager Detail |
| **Bulk reject** | Promotion queue only, with a shared reason |

---

## 6. Validations

| # | Rule | Message |
|---|---|---|
| V1 | MIME must be `application/pdf`, **detected from content** (PRD 01 §3) | "Only PDFs can be analysed. This file is a Word document, whatever its extension says. It's been stored but not queued." |
| V2 | Size ≤ 50 MB | `[TODO: PRD 01 does not state a limit. 50 MB is assumed — the reference file is 5.4 MB and a PPM runs larger. Confirm.]` |
| V3 | Non-empty file | "This file is empty." |
| V4 | PDF must be readable — not encrypted or corrupt | "This PDF is password-protected. Remove the password and re-upload." |
| V5 | Page count > 0 | "No pages could be read from this PDF." |
| V6 | **Duplicate sha256 → recognition, not an error** | Outcome A. Never a red error state |
| V7 | Fund name required to create a deal | "What fund is this? The classifier couldn't read a name." |
| V8 | Manager name required | — |
| V9 | AIF category ∈ enum | — |
| V10 | Creating a new deal when a match exists requires confirmation | Per §5 |
| V11 | Deal must exist and be non-archived to attach | "DL-2026-0004 is archived." |
| V12 | Criteria set must be `ACTIVE` or explicitly-chosen `DRAFT` | Draft warning per §3.3 |
| V13 | No criteria set for the category | "No active criteria set covers CAT_II. [Choose a set] [Create one]" — blocks analysis, not upload |
| V14 | Classified non-analysable → auto-reject | "This looks like a quarterly report, not a marketing document. Stored, not queued. [Promote anyway]" |
| V15 | `LOW` classification confidence requires field confirmation | "The classifier wasn't confident about the fund name. Check it." |
| V16 | Upload permission required | — |
| V17 | Batch: each file validated independently | One failure never blocks the rest |

---

## 7. Conditional States

| State | Trigger | What the user sees |
|---|---|---|
| **A — Idle** | No file | Dropzone with the content-addressing note |
| **B — Uploading** | Transfer in flight | Per-file progress bar, bytes and percent, `[Cancel]`. Multiple files upload in parallel with individual states |
| **C — Hashing** | Bytes received | "Checking whether we've seen this before…" — names the operation, because the recognition that follows only makes sense if the hashing is visible |
| **D — Classifying** | Post-dedup | "Reading the document…" Reference: 12.0s |
| **E — Duplicate found** | Hash matches | Outcome A. Informational, positive framing, never an error |
| **F — Match found** | Fund matches an existing deal | Outcome B, attach as default |
| **G — Multiple matches** | >1 candidate | Outcome C, ranked, nothing auto-committed |
| **H — No match** | No candidate | Outcome D, new-deal form pre-filled |
| **I — Manager known, fund new** | Manager matches | Outcome D plus the re-up note; `deal_track = RE_UP` |
| **J — Classification failed** | Classifier error | "Couldn't read this PDF. It may be a scan with no text layer." Manual entry offered; document stored. `[TODO: is OCR in scope? PRD 06 does not say. A scanned deck is a realistic intake case.]` |
| **K — Not analysable** | `is_analysable = false` | Per V14 |
| **L — Low confidence** | `classification_confidence = LOW` | Fields flagged for confirmation with their source pages; submit blocked until confirmed |
| **M — Upload failed** | Network / server error | "Upload failed at 34%." `[Retry]` — resumes rather than restarting where supported |
| **N — Invalid file type** | Non-PDF | Per V1. Stored, not queued |
| **O — Analysis queued** | `DEAL_SUBMITTED` | "Queued. Position 3, starting in about 4 minutes." `[Watch progress] [Upload another]` |
| **P — Analysis running** | Run started | **Per-stage progress, not a spinner** — the five stages with elapsed times and the live detail line from `status.jsonl`, plus running cost. 8–16 min. Analyst can leave; notified on completion |
| **Q — Analysis failed** | Run failed | Failure code, stage, stderr excerpt visible without a click. `[Requeue] [Raise budget] [Reject document]` |
| **R — No criteria set** | Per V13 | Blocks analysis, not upload. Document is stored and promotable |
| **S — Restricted access** | No upload permission | "You don't have permission to upload." Names who does |
| **T — Batch mixed outcomes** | Several files, different results | Per-file result list: 1 duplicate, 2 attached, 1 rejected — each with its own actions. **No single batch-level success or failure message**, which would misrepresent every mixed outcome |
| **U — Deal-scoped upload** | Entered with `deal_id` (entry 3, 4, 5) | Matching skipped entirely. Header: "Uploading to DL-2026-0007." When entered from a PPM prompt, the target questions are listed: "This should help with 12 open questions including gp_commitment, valuation_policy, key_person_clause." |
| **V — Storage unavailable** | Backend storage error | "Can't store files right now." Upload blocked, nothing half-written |
| **W — Offline** | Connection lost | "Not connected. Uploads will resume when you're back." Queued locally where supported |

---

## 8. Open Questions

1. **Fund-name matching.** Outcome B rests entirely on match quality. PRD 04 §8 requires manager search to match aliases ("Neo Asset Management", "Neo AMC", "Neo Asset Management Private Limited"). Fund names have the same problem — "NIIOF-II", "Neo Infra Income Opportunities Fund II", "Neo Infra Fund 2". **A missed match produces the exact duplicate-Deal failure this screen exists to prevent, and it fails silently: the analyst sees a clean new-deal form and no reason to doubt it.** Matching strategy needs specifying, and near-misses should probably be surfaced as "no confident match, but these are close".
2. **Same fund, different vintage.** NIIOF-I and NIIOF-II are different funds and must be different Deals — but they are one manager relationship and the roman numeral is the only distinguisher. Matching that is too loose merges two vintages into one Deal, which is worse than splitting one vintage into two. Where is the line?
3. **File size limit** (V2) — unspecified.
4. **OCR** (state J) — scanned decks are realistic and the engine's position is unstated.
5. **Batch promotion.** Multi-file upload is supported but promotion is per-file, with a match decision each. Ten files means ten decisions. Is a bulk-promote flow needed, and can it preserve the attach-by-default discipline without making it pro forma?
6. **API uploads and the queue.** Entry 12 says API documents land in the queue and promotion is always human. At volume the queue becomes the bottleneck the platform was meant to remove. Is auto-promotion on a high-confidence match ever acceptable?
7. **Cost confirmation.** $2.30 is shown but not gated. Should a threshold require confirmation, and does a re-run on a large PPM change the estimate materially?
8. **"Save without analysing".** What is a promoted, unanalysed document for? It appears on the Deal's timeline with no run. Real case, or an affordance that just creates dead rows?
