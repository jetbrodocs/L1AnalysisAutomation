---
title: "Screen Spec — Deal Detail"
status: draft
created: 2026-07-21
updated: 2026-07-21
tags: [screen-spec, triage, deal-hub, odd, re-up, documents, l1-analysis-platform]
---

# Screen Spec — Deal Detail

**Parent PRD:** `04-triage.md` (Screen 3 "Deal Detail"), with the Documents tab deriving from `01-intake.md` (Screen 7) and the analysis-version list from `08-version-history.md` *(not yet written — see §9)*.

> **PRD 04 §8:** a Deal Detail for a `RE_UP` must open with the prior fund's decision above the fold. A re-up screen that looks identical to a new-manager screen has thrown away the institution's information advantage.

> **Standalone principle (PRD 06 §0).** This is the hub Phlo adds around a memo that already stands alone. Everything here is workflow — triage state, assignment, ODD, notes, the version chain. **No comprehension of the analysis lives on this screen**; the summary strip restates the memo's own headline and links to it. If a reader needed this screen to understand a finding, the section files are under-written.

---

## 1. Purpose

One deal, everything about it: documents in date order, analysis versions, triage state and history, ODD status, notes. The hub an analyst returns to, and the first screen an IC member opens when asked about a fund.

**Reference data:** `DL-2026-0007` — *Neo Infra Income Opportunities Fund II*, Neo Asset Management Private Limited, `INITIAL_SCREENING`, NEW track, HOLD, 49 open questions, one document (`Neo Infra Income Opportunities Fund-II Feb'26.pdf`, 52pp, sha256 `2b176083…`), one run (`fd33c73e`, 8m 45s, $2.30).

---

## 2. Entry Points

| # | From | Trigger | Context passed in | Conditions |
|---|---|---|---|---|
| 1 | Deal list / board (`screen-deal-list.md`) | Click a card or row | `deal_id` | Any role with read access |
| 2 | Command palette `⌘K` | Deal search by `deal_code`, `fund_name`, `manager_name` | `deal_id` | Per PRD 04 §8 |
| 3 | Memo Reader | Breadcrumb "← DL-2026-0007" | `deal_id` | — |
| 4 | Version History | Breadcrumb / "Back to deal" | `deal_id` | — |
| 5 | Promotion (PRD 01 Screen 3) | After promoting a document to an existing deal | `deal_id`, Documents tab active | — |
| 6 | Promotion | After creating a new deal | `deal_id`, analysis-running state | — |
| 7 | Document Detail (PRD 01 Screen 5) | "Open Deal" | `deal_id`, Documents tab | Document is promoted |
| 8 | Run Detail (PRD 02 Screen 3) | "Open deal" | `deal_id`, Analysis tab | — |
| 9 | Manager Detail (PRD 04 Screen 9) | Click a fund in the manager's history | `deal_id` | — |
| 10 | Manager Detail — re-up chain | "The prior fund" from a re-up | `deal_id` of the prior deal | — |
| 11 | ODD Review Detail (PRD 04 Screen 12) | "Open deal" | `deal_id`, ODD tab. **Read-only for ODD Reviewers** (§8 state L) | — |
| 12 | Passed Deals (PRD 04 Screen 5) | Open a declined deal | `deal_id` | — |
| 13 | Stalled Deals (PRD 04 Screen 13) | Open a stalled deal | `deal_id` | Super Admin |
| 14 | Triage Decision (PRD 04 Screen 4) | Cancel, or after submit | `deal_id` | — |
| 15 | Notification — analysis complete / failed / ODD returned | Click notification | `deal_id`, relevant tab | — |
| 16 | Deep link | `/deals/{id}`, `/deals/{id}/documents`, `/deals/{id}/analysis`, `/deals/{id}/odd`, `/deals/{id}/notes` | — | — |
| 17 | Upload (`screen-upload.md`) | "Attach to existing deal" completed | `deal_id`, Documents tab | — |
| 18 | Funnel Report drill-through | A stage bar → a specific deal | `deal_id` | — |
| 19 | Email digest | Deal link | `deal_id` | — |

---

## 3. UX Layout

Header spanning the width, then five tabs. The header carries the things that must be true regardless of which tab is open.

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ ← Deals                                                                               │
│ Neo Infra Income Opportunities Fund II                          DL-2026-0007  [NEW]   │
│ Neo Asset Management Private Limited · CAT_II · ~₹5,000 cr · 18–20% gross             │
│                                                                                       │
│  SOURCING ──▶ ● INITIAL SCREENING ──▶ IDD ──▶ IC ──▶ COMMITMENT     1 day in stage    │
│                                                                                       │
│  ┌──────────────┐ ┌────────────────────┐ ┌──────────────────┐ ┌───────────────────┐  │
│  │ ⏸ HOLD       │ │ red 11.0 ▓▓▓▓▓▓▓▓  │ │ ⚠ 2 VETOES       │ │ ⚠ 49 OPEN         │  │
│  │ v1 · 20 Jul  │ │ green 1.0 ▓        │ │   NOT EVALUATED  │ │   QUESTIONS       │  │
│  │ [Read memo ▸]│ │ 17 criteria        │ │   CR-0001/0002   │ │   [Answer them ▸] │  │
│  └──────────────┘ └────────────────────┘ └──────────────────┘ └───────────────────┘  │
│                                                                                       │
│  ODD: ○ not started                              Analyst: Sharva Jethwa               │
│                                                                                       │
│  [Triage ▸]  [Advance ▸]  [Request ODD]  [Upload document]  [Re-run ▾]  [Assign]      │
└──────────────────────────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ [Overview] [Documents 1] [Analysis 1] [ODD] [Notes 0] [History]                       │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

**The ODD line sits below the stage rail and outside it, on its own row.** It is never rendered as a step in the rail, never between IDD and IC, and never as a chip inline with the stage chips. Its visual separation is the model made visible.

### 3.1 Overview tab

Left column: the memo summary strip — recommendation, basis in the engine's own words (*"red-flag weight 11.0 materially exceeds green-flag weight 1.0; the open questions should be answered before proceeding. NOTE: 2 veto criterion/criteria could not be evaluated, so this recommendation is made without them."*), fired findings as a compact list with tier glyphs, and a link into each. Right column: fund facts from extraction, each with its page citation (`Fund size ~₹5,000 cr (p.37)`), the source document, and the criteria set with its hash.

**The fund-facts panel carries page citations even here.** It costs a few characters and preserves the evidence discipline outside the memo.

### 3.2 Documents tab — the cross-vintage timeline

```
  Documents for DL-2026-0007                                      [+ Upload document]

  ┌────────────────────────────────────────────────────────────────────────────────┐
  │ 📄 Neo Infra Income Opportunities Fund-II Feb'26.pdf              DOC-2026-000412│
  │    PITCH_DECK · 52 pages · 5.4 MB · uploaded 2026-07-20 19:51 by Sharva Jethwa  │
  │    sha256 2b176083b2938978a9ab84ba1cc2fc72cad052ded1bcf4893293abd1a4613562  ⧉   │
  │    Document date: February 2026 · classification: STATED                        │
  │    → Analysis v1 (run fd33c73e, completed 20 Jul, HOLD)                         │
  │    [Open document] [Download] [Open run]                                        │
  └────────────────────────────────────────────────────────────────────────────────┘

  ⓘ 49 open questions. 12 of them typically resolve from a PPM.   [Upload a PPM ▸]
```

The sha256 is shown in full, not in a metadata drawer (PRD 01 §8) — when an analyst asks "is this the same deck they sent in February?", the hash is the answer, and displaying it teaches the identity model the system actually uses.

Multiple documents render as a **dated timeline**, oldest first, each with its analysis run, so "what did they send us, when, and what did we make of it" reads top to bottom. This is the payoff for the Deal/Document model (PRD 01 §1) and the reason the promotion screen must default to attaching rather than creating (`screen-upload.md` §3.2).

### 3.3 Analysis tab

The version chain in compact form — v1, v2, v3 with date, recommendation, open-question count, and evidence added — with `[Full version history ▸]` to `screen-version-history.md`. Below it, the latest run's stage timeline with real durations (classification 12.0s, extraction 89.4s, diligence 1.0s, scoring 332.7s, memo 89.6s), cost ($2.30), engine version (0.1.0), criteria set and content hash, and the artifact download.

### 3.4 ODD tab

ODD's own space, and it looks different — different accent, its own vocabulary, no investment-team affordances. States: not started (with `[Request ODD]` for the investment team, which is the only ODD action they hold), requested, in progress, completed with rating.

A completed review shows the rating on **ODD's own scale** (`SATISFACTORY` / `SATISFACTORY_WITH_OBSERVATIONS` / `SIGNIFICANT_FINDINGS` / `UNSATISFACTORY`), findings by category, remediation, reviewer, completion date, expiry. **Never a number, never beside the L1 recommendation as if comparable** (PRD 04 §2).

When blocking:

```
  ⛔ ODD-2026-0014 — UNSATISFACTORY, completed 2026-07-18 by A. Menon

     This deal cannot enter COMMITMENT.

     The block is not overridable by the investment team. It clears only on a
     new ODD review with a non-blocking rating, or by a Super Admin acting with
     an ODD Reviewer's concurrence recorded in the rationale.

     [Request a refresh review]   [Open full review]
```

### 3.5 Re-up banner (above the fold, `RE_UP` only)

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ RE-UP — we have history with this manager                                             │
│                                                                                       │
│ Neo Infra Income Opportunities Fund I · DL-2023-0031                                  │
│   We committed ₹200 crore in March 2023.                                              │
│   Triage: PURSUE — "strong operating-asset sourcing, accepted the gross-only          │
│   disclosure on the basis of the PPM's net table" — S. Jethwa, 2023-01-14             │
│   ODD: SATISFACTORY_WITH_OBSERVATIONS (ODD-2023-0009) — observations on valuation     │
│   frequency and BCP testing.                                                          │
│                                                                                       │
│   The question for a re-up is what changed, not evaluation from zero.                 │
│   [Open prior deal]  [Compare NIIOF-I and NIIOF-II analyses]                          │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

The 2023 ODD observation on **valuation frequency** is exactly the kind of institutional memory that makes CR-0016 firing on NIIOF-II a pattern rather than an isolated finding — and it is the reason this banner is above the fold.

---

## 4. Data Points Displayed

### 4.1 Header

| Label | Value | Source |
|---|---|---|
| Fund name | `Neo Infra Income Opportunities Fund II` | `Deal.fund_name` |
| Deal code | `DL-2026-0007` | `Deal.deal_code` |
| Manager | `Neo Asset Management Private Limited` | `Deal.manager_name` → Manager |
| AIF category | `CAT_II` | `Deal.aif_category` |
| Fund size | `~₹5,000 cr` (p.37) | Extraction |
| Target return | `18–20% gross` (p.37, p.20) — basis always shown | Extraction |
| Stage | `INITIAL_SCREENING` in the rail | `Deal.stage` |
| Days in stage | `1 day` | `Deal.stage_entered_at` |
| Track | `NEW` / `RE_UP` | `Deal.deal_track` |
| Recommendation + version | `HOLD · v1 · 20 Jul` | Latest run |
| Weights, criteria evaluated | `11.0 / 1.0`, `17` | `04-scoring.json → result` |
| Unevaluated vetoes | `CR-0001, CR-0002` | `result.veto_unevaluated[]` |
| Open questions | `49` | `05-memo.json → result.unresolved_total` |
| ODD state | `○ not started` | `ODDReview` |
| Assigned analyst | `Sharva Jethwa` | `Deal.assigned_analyst_id` |

### 4.2 Per tab

**Overview** — recommendation basis verbatim; fired findings (CR-0010, CR-0011, CR-0014, CR-0016 red; CR-0033 green; CR-0034 contested) with tier, severity, confidence; fund facts with page citations; criteria set `CS-2026-0001 (DRAFT)` + hash `94ec11df…`.

**Documents** — filename, `document_code`, type, pages, bytes, **full sha256**, uploader, upload time, source (browser/API), document date, classification confidence, linked run, duplicate relationships.

**Analysis** — per version: number, date, recommendation, open-question count, evidence added, criteria set, run id, duration, cost, engine version, artifact availability.

**ODD** — `review_code`, status, rating, reviewer, requested/completed dates, expiry, findings by category, remediation, blocking flag.

**Notes** — author, timestamp, body, edit history.

**History** — every event on the deal: `DEAL_CREATED`, `DOCUMENT_UPLOADED`, `DEAL_SUBMITTED`, run stage events, `DEAL_SCORED`, `MEMO_GENERATED`, `DEAL_TRIAGED`, `DEAL_STAGE_ADVANCED`, `DEAL_ASSIGNED`, `DEAL_NOTE_ADDED`, `ODD_REVIEW_REQUESTED`, `ODD_REVIEW_COMPLETED` — with actor and timestamp.

---

## 5. CTAs

| CTA | Behaviour |
|---|---|
| **Read memo** | Memo Reader at the latest version |
| **Answer them** (open questions) | Memo Reader at §11, unanswered filter applied |
| **Triage** | Triage Decision form. Blocked before `DEAL_SCORED` |
| **Advance** | Stage advance with gate checks (§6). Shows which gates pass and which fail before submitting |
| **Request ODD** | `ODD_REVIEW_REQUESTED` → ODD queue. The investment team's only ODD action |
| **Upload document** | `screen-upload.md` pre-scoped to this deal |
| **Re-run ▾** | `With pending answers (n)` · `With current criteria set` · `With a different criteria set…` |
| **Assign** | `DEAL_ASSIGNED` |
| **Add note** | `DEAL_NOTE_ADDED` |
| **Open prior deal** / **Compare analyses** | Re-up banner → prior deal, or cross-vintage comparison |
| **Full version history** | `screen-version-history.md` |
| **Open run** / **Download artifacts** | Run Detail; artifact `.zip` — the standalone escape hatch |
| **Open document** / **Download** / **Copy sha256** | Document Detail; original bytes; hash to clipboard |
| **Request refresh review** | New ODD review scoped to what changed |
| **Export ▾** | IC packet (available on entering `IC`), memo PDF, deal summary |
| **Reopen** | On a passed deal — records why it is being reconsidered |

---

## 6. Validations

| # | Rule | Message |
|---|---|---|
| V1 | Stage transitions follow the state machine | "Not a valid move from Initial Screening." |
| V2 | `IDD` needs `DEAL_SCORED`, a `PURSUE` on the latest run, an assigned analyst | Lists which are missing, each actionable |
| V3 | `IC` needs an ODD review beyond `NOT_STARTED`, latest `PURSUE`, target commitment | "No ODD review requested. [Request ODD]" |
| V4 | **`COMMITMENT` blocked by `odd_blocking`, not overridable by the investment team** | As `screen-deal-list.md` V5 |
| V5 | Gate override (Super Admin) requires a rationale | "Which gate, and why?" |
| V6 | ODD gate override additionally requires recorded ODD concurrence | "Name the ODD Reviewer who concurs. This is recorded permanently." |
| V7 | Backward moves require a rationale | — |
| V8 | Triage requires rationale; `PASS` requires a reason code | — |
| V9 | Advancing on draft criteria warns | "Scored with CS-2026-0001, a draft set that has not been signed off." |
| V10 | **Advancing with unevaluated vetoes warns** | "CR-0001 and CR-0002 were never evaluated — the SEBI register was unreachable from this network. This is not a finding that registration and enforcement history are clean. Advance anyway?" |
| V11 | Re-run blocked while one is in flight | — |
| V12 | Upload must be a PDF | "Only PDFs can be analysed." |
| V13 | Note body required, min 3 chars | — |
| V14 | Assign requires an active Analyst | — |
| V15 | ODD refresh requires the prior review to be complete | — |

---

## 7. Conditional States

| State | Trigger | What the user sees |
|---|---|---|
| **A — No documents** | Deal created, nothing attached | Documents tab: "No documents yet." `[Upload]`. Header shows no recommendation tile |
| **B — No analysis** | Documents present, no run | "Document promoted, analysis not started." `[Run analysis]` |
| **C — Analysis running** | Run in flight | Header replaces the recommendation tile with **per-stage progress**: five stages, elapsed per stage, current detail line from `status.jsonl` (`scoring — strict pass …`), total elapsed, running cost. 8–16 min. `[Cancel run]`. Prior version stays readable when one exists |
| **D — Analysis failed** | Run failed | Header banner: code, stage, attempt count, next retry, **stderr excerpt visible without a click**. `[Requeue] [Raise budget] [Open run] [Reject document]`. Deal stays in stage |
| **E — Loading** | Fetch in flight | Header skeleton, tab bar rendered with counts, no placeholder recommendation value |
| **F — Error** | API failure | "Couldn't load DL-2026-0007." `[Retry]` |
| **G — Restricted access** | No read permission | "You don't have access to DL-2026-0007." Assigned analyst named so the user can ask |
| **H — Draft criteria** | Latest run unversioned set | Amber strip below the header, same wording as the Memo Reader's banner, linking to `CS-2026-0001` |
| **I — Unevaluated vetoes** | `veto_unevaluated` non-empty | Header tile, **never a green tick**. V10 on advance |
| **J — Veto fired** | `veto_fired` non-empty | Red header band replaces the recommendation tile: `VETOED — CR-00NN`. Advance beyond `INITIAL_SCREENING` blocked pending an explicit override |
| **K — ODD blocking** | `odd_blocking` | Red ODD row in the header, blocking panel in the ODD tab, `COMMITMENT` blocked |
| **L — Restricted (ODD Reviewer)** | Role = ODD Reviewer | Deal facts, documents, and the ODD tab. **No triage, no advance, no assign, no re-run anywhere on the screen** — not disabled, absent. Memo readable read-only for context, labelled as the investment team's assessment |
| **M — Restricted (IC Member)** | Role = IC Member | Full read, memo and evidence, export. No triage, advance, assign, or re-run |
| **N — Re-up** | `deal_track = RE_UP` | The §3.5 banner above the fold, prior decision and prior ODD rating visible without scrolling |
| **O — Passed deal** | Latest decision `PASS` | Greyscale header, banner: "Passed 2026-07-22 by S. Jethwa — reason: `DISCLOSURE_QUALITY`. 'Gross-only returns with no PPM forthcoming.'" `[Reopen]`. Everything stays readable — the counterfactual is the point (PRD 04 §1.4) |
| **P — Stalled** | Past the stage age threshold | Amber age chip: "31 days in IC — threshold is 21." `[Reassign] [Add note]` |
| **Q — Multiple versions** | ≥2 | Analysis tab leads with the chain; header shows `v3` and "recommendation changed at v3" when it did |
| **R — Duplicate document attempted** | Upload of an existing sha256 | Documents tab: "This file is already attached (DOC-2026-000412, uploaded 20 Jul). No new document created." |
| **S — Memo hash mismatch** | `memo_sha256` ≠ disk | Red strip: "v1's memo file does not match its recorded hash. Do not circulate." Export disabled for that version |
| **T — Manager under review** | Manager relationship flag | Strip: "Neo Asset Management has 1 other deal in the pipeline and 1 prior commitment. [Open manager]" |
| **U — Offline** | Connection lost | Cached copy with timestamp; writes disabled |

---

## 8. Open Questions

1. **Does the ODD tab exist for an investment-team user before a review is requested?** Shown here as present-but-empty with `[Request ODD]`. Hiding it until requested would make ODD invisible; showing it always risks reading as a checklist item the team owns. Current reading: always present, clearly labelled as another function's work.
2. **Prior-fund selection for a re-up** with several prior funds — most recent, largest commitment, or all?
3. **Cross-vintage comparison.** The re-up banner offers "Compare NIIOF-I and NIIOF-II analyses". That is a different comparison from the version chain (`screen-version-history.md` §9 Q6) — different documents, different criteria sets, years apart. **It is specced nowhere.** Either it belongs here as its own view or on Manager Detail. Flagging rather than inventing it.
4. **IC packet contents.** PRD 04 §4 says the packet becomes exportable on entering `IC`; PRD 05 §8 defers template authoring to v2. What is in the packet for v1?
5. **Notes and §11 answers.** Both are analyst-entered text against a deal. An analyst who types "spoke to IR, GP commitment is 2.5%" as a note has answered an open question in the wrong place, and nothing connects the two. Should notes offer "is this an answer to an open question?"
6. **Header tile count.** Four tiles plus stage rail plus ODD row plus six actions is a dense header. On a `RE_UP` with a blocking ODD it is denser still. Needs a real layout pass at narrow widths.
7. **Target return "gross".** Shown as `18–20% gross` because CR-0010 fired precisely on the absence of a net figure. Should the basis suffix be universal, or only when a gross-only finding fired? Universal is more honest and slightly noisier.
