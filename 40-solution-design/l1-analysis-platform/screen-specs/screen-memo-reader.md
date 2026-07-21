---
title: "Screen Spec — Memo Reader"
status: draft
created: 2026-07-21
updated: 2026-07-21
tags: [screen-spec, memo, evidence, co-pilot, open-questions, l1-analysis-platform]
---

# Screen Spec — Memo Reader

**Parent PRD:** `05-memo.md` (Screen 2, "Memo Reader"), with the inline question-answering behaviour deriving from `00-overview.md` §1 "The co-pilot loop" and PRD `07-evidence-loop.md`.

> **Reconciliation note.** `07-evidence-loop.md` and `08-version-history.md` did not exist when this spec was written (verified 2026-07-21). The question-kind routing, attestation model, and version-chain behaviour specified here derive from `00-overview.md` §1, which already fixes the three-kind taxonomy and the analyst-attested/document-grounded distinction. **When PRD 07 lands, reconcile §"Open Questions" and §"CTAs" against it and record any conflict here rather than silently diverging.**

> **Screen 2 is the product.** Everything else in the platform exists to fill this screen (PRD 05 §8, screen notes). Two design claims are load-bearing and are treated as requirements, not preferences: (1) §11 is never collapsed by default, and (2) an assertion is never more than two clicks from the words in the document that support it.

---

> ## ⚠️ Navigation model decided 2026-07-21 — supersedes single-scroll assumptions below
>
> **Per-section routing, with `00-index.md` as the landing page.** Sections 3.3 and entry 11 below were written assuming one continuous scrolling document; the engine now emits 13 files (PRD 06 §3) and this screen routes to them individually.
>
> | Route | Renders |
> |---|---|
> | `/deals/{id}/memo` | `00-index.md` — the landing page. Recommendation, scorecard, open-question counts by kind, links out |
> | `/deals/{id}/memo/{section}` | One section file, e.g. `/memo/11-open-questions` |
>
> **Why routing beats one scroll:**
> - **Deep links work.** "See §4 risk factors" in an email opens that section, not a scroll position that drifts as content changes.
> - **The diff is per-section** (PRD 08). Routes and diff units align; one continuous scroll makes "what changed in §4" awkward to express.
> - **§11 is 45KB on the reference deck** — nearly half the memo. In one scroll it either dominates or gets collapsed, and collapsing is exactly what the design forbids. As its own route it is never collapsed *and* never in anyone's way.
> - **Audiences differ**: IC reads §1/§2/§4, analysts work §9/§10/§11, ODD reads §7. Routing lets each land where they belong.
>
> **The "§11 never collapsed" rule is preserved and strengthened**: within its own route it renders fully expanded. The index links to it with its count and kind breakdown visible, so it can never be silently skipped.
>
> **Section nav persists** across all routes — a rail listing all 12 sections with the current one marked, plus per-section state badges (finding counts, unanswered counts). The reader always knows where they are and what else exists.

## 1. Purpose

Read one Investment Committee memo — 12 sections, findings inline with their evidence — and **close the gaps in it without leaving the screen**. The memo is not a report to be consumed; it is a worksheet. The 49 open questions on the reference run are the main surface, not an apology.

**Reference data used throughout this spec** is the real run `fd33c73e-2db5-4389-855a-e597a476889c` on *Neo Infra Income Opportunities Fund II* (Neo Asset Management Private Limited), 52-page February 2026 deck, criteria set `CS-2026-0001` (DRAFT, unversioned), recommendation **HOLD**, red weight **11.0** vs green weight **1.0**, 4 red flags fired, 1 green, 1 contested, 2 vetoes unevaluated, **49 open questions**.

---

## 2. Entry Points

| # | From | Trigger | Context passed in | Conditions |
|---|---|---|---|---|
| 1 | Memos list (PRD 05 Screen 1) | Click a memo row | `memo_id` | Memo status any of `UNREVIEWED` / `IN_REVIEW` / `REVIEWED` |
| 2 | Deal Detail — Analysis tab (`screen-deal-detail.md`) | Click "Open Memo" on the latest run | `memo_id`, `deal_id` | A completed run with a memo exists |
| 3 | Deal Detail — version list | Click any version row (v1, v2, v3) | `memo_id` for that version, `version_no` | Opens that version **frozen**; non-latest versions are read-only (see §8 state R) |
| 4 | Run Detail (PRD 02 Screen 3) | "Open Memo" action | `run_id` → resolves `memo_id` | Run `status = completed` and `memo` stage completed |
| 5 | Run Progress live view (PRD 02 Screen 4) | Auto-redirect on run completion | `run_id` | Only when the analyst is still on the progress screen when the run finishes |
| 6 | Pipeline Board card (PRD 04 Screen 1) | Click the recommendation badge (`HOLD`) on a card | `deal_id` → latest `memo_id` | Card has a scored run |
| 7 | Triage Decision form (PRD 04 Screen 4) | "Read the memo" link | `memo_id`, returns to triage on back | See PRD 04 §8 note on anchoring bias — this link may be gated |
| 8 | Version History (`screen-version-history.md`) | Click a version in the chain, or "View this version" from a diff | `memo_id`, `version_no` | — |
| 9 | Version comparison diff | Click a causal diff row, e.g. "CR-0030 flipped not-fired → fired" | `memo_id` (v3), `scroll_to_finding = CR-0030` | Deep-links to the finding, section auto-expanded |
| 10 | Command palette `⌘K` | Search by `memo_code`, fund name, or manager name | `memo_id` | Per PRD 05 §8 palette entities |
| 11 | Deep link / shared URL | `/memos/{id}`, `/memos/{id}#section-11`, `/memos/{id}#finding-CR-0010`, `/memos/{id}?question=gp_commitment` | `memo_id` plus anchor | Anchored entries force the target section expanded regardless of collapse state |
| 12 | Notification — "Your re-run finished" | Click notification | `memo_id` of the **new** version | Fired on `MEMO_GENERATED` for a re-run the analyst triggered |
| 13 | Notification — "Question answered by another analyst" | Click notification | `memo_id`, `question_id` | Multi-analyst deals only |
| 14 | Export History (PRD 05 Screen 7) | "Open Memo" from an export row | `memo_id`, `version_no` as exported | — |
| 15 | ODD Review Detail (PRD 04 Screen 12) | "Open investment memo" cross-reference | `memo_id` | ODD Reviewer sees the memo **read-only**, no answer affordances (§8 state Q) |

---

## 3. UX Layout

Three regions: a **persistent header** that carries the things a reader must not be able to scroll past, a **left section rail**, and the **memo body**. An **evidence drawer** slides in from the right over the body; it never navigates away.

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ ⚠ DRAFT CRITERIA SET — CS-2026-0001 carries no version number.                        │  ← banner A
│   These findings have not been assessed against an agreed house view.  [What this means]│
├──────────────────────────────────────────────────────────────────────────────────────┤
│ Neo Infra Income Opportunities Fund II                        MEMO-2026-0007 · v1     │
│ Neo Asset Management Private Limited · DL-2026-0007                                   │
│                                                                                       │
│  ┌──────────┐  ┌───────────────────┐  ┌──────────────────┐  ┌─────────────────────┐  │
│  │  HOLD    │  │ red 11.0 ▓▓▓▓▓▓▓▓ │  │ 2 VETOES         │  │ 49 OPEN QUESTIONS   │  │
│  │ defer    │  │ green 1.0 ▓       │  │ NOT EVALUATED    │  │ 12 resolve from a   │  │
│  │ pending  │  │                   │  │ CR-0001, CR-0002 │  │ PPM → Upload  ▸     │  │
│  │ answers  │  │ 17 criteria       │  │  Why? ▸          │  │ Jump to §11   ▸     │  │
│  └──────────┘  └───────────────────┘  └──────────────────┘  └─────────────────────┘  │
│                                                                                       │
│  Analysed 2026-07-21 · 52pp · Feb 2026 deck · CS-2026-0001 (draft) · run fd33c73e     │
│  [Answer questions] [Export ▾] [Compare versions] [Re-run ▾]        Review: 0/12 ✓     │
└──────────────────────────────────────────────────────────────────────────────────────┘
┌────────────────────┬─────────────────────────────────────────────────────────────────┐
│ SECTIONS           │  ## 4. Risk Factors                            ○ Unreviewed  ▾   │
│                    │                                                                  │
│  1 Recommendation ✓│  ┌────────────────────────────────────────────────────────────┐ │
│  2 Rationale       │  │ ● RED FLAG · HIGH · fired · confidence high                 │ │
│  3 Fund Facts   ⚙  │  │ CR-0010 — Gross-only return disclosure           weight 3.0 │ │
│  4 Risk Factors  4●│  │                                                             │ │
│  5 Supporting   1● │  │ Every return figure in the document is expressly gross.     │ │
│  6 Fees & Terms ⚙  │  │ Page 52 makes this a document-wide convention.              │ │
│  7 Team            │  │                                                             │ │
│  8 Track Record    │  │ EVIDENCE (4 quotes)                                         │ │
│  9 Contested    ⚠1 │  │  ✓ p.52 "all returns are presented on a 'gross' basis"  ▸  │ │
│ 10 Asks            │  │  ✓ p.4  "Gross Returns ~ 18-20% p.a."                   ▸  │ │
│ 11 Not Determined  │  │  ▨ p.20 "Strategy aligned to NIIOF-I and targeting…"    ▸  │ │
│    ▸ 49 items   ⚙  │  │  ⚠ p.37 (layout-normalised — see drawer)                ▸  │ │
│ 12 Sources      ⚙  │  │                                                             │ │
│                    │  │ ABSENCE EVIDENCE ▾  All 52 pages searched for "net IRR"…    │ │
│ ─────────────────  │  │ ASK ▾  Request the net-of-fee IRR for NIIOF-I…              │ │
│ ⚙ = assembled      │  │                                                             │ │
│   mechanically     │  │ [Open source page] [Override finding] [Answer this] [Flag]  │ │
│   (no model call)  │  └────────────────────────────────────────────────────────────┘ │
│                    │                                                                  │
│ FILTER             │  ┌── CR-0011 — Predecessor track record unrealised ────────┐    │
│ ☐ Fired only       │  ...                                                            │
│ ☐ Unanswered only  │                                                                  │
│ ☐ Contested        │                                                                  │
└────────────────────┴─────────────────────────────────────────────────────────────────┘
```

### 3.1 Header (persistent, does not scroll away)

Four tiles, deliberately equal in visual weight. The **open-questions tile has the same prominence as the recommendation tile** — this is the co-pilot claim rendered as layout. PRD 05 §8 requires a persistent §11 summary in the header; the tile is that requirement, upgraded from a text line to a tile because 49 is not a footnote.

Tile 4 leads with the **bulk insight**, not a count alone: *"12 of these 49 typically resolve from a PPM — upload one?"*. The count without the affordance is a complaint; the count with the affordance is a co-pilot.

### 3.2 Left rail — section navigation

- All 12 sections listed, always visible, with a badge per section: finding count (`4●`), contested marker (`⚠1`), or the mechanical-assembly cog (`⚙` for sections 3, 6, 11, 12 where `is_generated = false`).
- Review state per section: `○ unreviewed` / `✓ reviewed` / `⚑ flagged`.
- **§11 is rendered as an expanded parent** in the rail with its 49 items grouped by stage beneath it (classification 1, extraction 11, diligence 6, scoring 31). It is never a single collapsed line.
- Filters at the foot of the rail re-scope the body: fired only, unanswered questions only, contested only.

### 3.3 Body — section rendering

Sections render in order 1→12 in a single scroll. **§11 is expanded on load; every other section's collapse state is remembered per user, except that §1, §2 and §11 are never collapsed by default.** A reader who forms a view from §1 and §2 and never scrolls has been misled by the layout, and layout is our responsibility (PRD 05 §8).

Each section header carries: number, title, review control, and — for sections 3, 6, 11, 12 — the marker **"assembled from extracted data · no model call"**. This is the strongest reliability signal available and costs one line (PRD 05 §5).

Findings render **inline within their section**, never in an appendix. Each finding card shows tier, severity, fired state, confidence, criterion code and name, weight, the narrative, its evidence list, collapsible absence evidence, collapsible ask, and its action row.

### 3.4 Evidence drawer (right, overlay)

Opens on any citation click. Two panes: the **rendered page image** on the left (not extracted text — PRD 05 §8 requires the image because PowerPoint-derived PDFs lose layout and the reader needs to see what the analyst would have seen), and the **quote, verdict, and provenance** on the right. `Esc` or click-away closes and returns scroll position to the originating finding. **The drawer never navigates away from the memo** — that is what keeps evidence two clicks deep.

### 3.5 Answer panel (inline, expands in place)

Opens beneath a question in §11 or beneath a finding's "Answer this" action. Its content depends entirely on question kind (§6). It **never opens as a modal and never routes to another screen** — inline answering is the core interaction, and a modal would make it a separate task.

---

## 4. Data Points Displayed

### 4.1 Header

| Label | Value / format | Source |
|---|---|---|
| Fund name | `Neo Infra Income Opportunities Fund II` | `Deal.fund_name` |
| Manager | `Neo Asset Management Private Limited` | `Deal.manager_name` |
| Deal code | `DL-2026-0007` | `Deal.deal_code` |
| Memo code | `MEMO-2026-0007` | `Memo.memo_code` |
| Version | `v1` of `v1→v3` chain | `Memo.version_no` (PRD 08) |
| Recommendation | `HOLD — defer pending answers` | `Memo.recommendation` / `04-scoring.json → result.recommendation` |
| Recommendation basis | `red-flag weight 11.0 materially exceeds green-flag weight 1.0; the open questions should be answered before proceeding. NOTE: 2 veto criterion/criteria could not be evaluated…` | `result.recommendation_basis` |
| Red-flag weight | `11.0` with proportional bar | `result.red_flag_weight` |
| Green-flag weight | `1.0` with proportional bar | `result.green_flag_weight` |
| Criteria evaluated | `17` | `result.criteria_evaluated` |
| Fired counts | `4 red · 1 green · 1 contested · 2 unevaluated` | `result.red_flags_fired[]`, `green_flags_fired[]`, `contested[]`, `unevaluated[]` |
| Veto banner | `2 VETOES NOT EVALUATED — CR-0001, CR-0002` | `result.veto_unevaluated[]` |
| Open question count | `49` | `05-memo.json → result.unresolved_total` |
| PPM-resolvable count | `12 of 49 typically resolve from a PPM` | Count of §11 items with `kind = document_answerable` and `suggested_document_type = PPM` |
| Criteria set | `CS-2026-0001 (DRAFT — unversioned)` | `run.json → criteria.set_code`, `criteria.version` (null) |
| Criteria content hash | `sha256:94ec11df…` (truncated, copy-on-click) | `run.json → criteria.content_hash` |
| Run code / id | `fd33c73e` | `run.json → run_id` |
| Source document | `Neo Infra Income Opportunities Fund-II Feb'26.pdf` · 52 pp · 5.4 MB · Feb 2026 | `run.json → source.*` |
| Source sha256 | `2b176083b293…` | `run.json → source.sha256` |
| Analysis date | `2026-07-21` | `Memo.generated_at` |
| Review progress | `0/12 sections reviewed` | Count over `MemoSection.review_status` |

### 4.2 Finding card (worked example — CR-0010)

| Label | Value | Source |
|---|---|---|
| Criterion code | `CR-0010` | `findings[].criterion_code` |
| Criterion name | `Gross-only return disclosure` | `findings[].criterion_name` |
| Tier | `RED_FLAG` | `findings[].tier` |
| Category | `disclosure` | `findings[].category` |
| Severity | `HIGH` | `findings[].severity` |
| Severity multiplier | `3.0` (HIGH) | `findings[].severity_multiplier` |
| Author weight | `1.0` | `findings[].author_weight` |
| Effective weight | `3.0` — `severity_multiplier × author_weight` | `findings[].effective_weight` |
| **Score contribution** | **`3.0`** — the effective weight if fired, else `0.0`. **This is the number to render on the card**, because it is what the scorecard sums | `findings[].score_contribution` |
| Fired | `true` | `findings[].fired` |
| Status | `fired` | `findings[].status` |
| Confidence | `high` | `findings[].confidence` |
| Contested | `false` | `findings[].contested` |
| Narrative | Section 4 body text for this finding | `05-memo.json → sections.4_risk_factors` |
| Evidence quotes | List of `{page, quote, verification}` | `findings[].evidence[]` |
| Absence evidence | `All 52 pages were searched for "net", "net IRR", "net-to-investor"… No fund-level net-to-investor return stated` | `findings[].absence_evidence` |
| Reasoning | Full engine reasoning | `findings[].reasoning` |
| Remediation / ask | `Request the net-of-fee IRR for NIIOF-I…` | `findings[].remediation` |

> **Render the contribution, not the author weight.** `author_weight` is `1.0` on every criterion in `CS-2026-0001`. Showing it on a card inside a memo whose scorecard reads `11.0` is a contradiction the reader cannot resolve, and was the reason the first prototype omitted weight entirely. Show `score_contribution`, with the derivation (`HIGH 3.0 × 1.0`) beside it so the total is reproducible by eye. Verified: 3.0 + 3.0 + 2.0 + 3.0 = 11.0 red; 1.0 green.
>
> **Never render `0.0` on an unevaluated veto.** CR-0001 and CR-0002 carry `CRITICAL` severity (×5.0, the heaviest multiplier) and contribute `0.0` — *because they did not fire, not because they are harmless*. A `0.0` beside a CRITICAL veto reads as "no problem here", which is the precise misreading state B exists to prevent. Render an em dash with `not scored · CRITICAL 5.0 unapplied`, and state in the body that their absence from the score is a gap in the arithmetic, not a point in the fund's favour.
>
> **A contested finding still contributes.** CR-0014 contributes `2.0` — 18% of the red weight — carried on the strict reading. Surface this: an IC should know how much of the score rests on a disagreement the engine refused to resolve. On this run, accepting the lenient reading gives `9.0`, which lands *exactly on* the `hold` threshold (`red ≥ 9.0 and red > 2 × green`), so the recommendation holds either way but has no margin above it.

### 4.3 Evidence quote row — the three verdicts

Every quote carries a `verification` value. **The UI must distinguish all three honestly.** On the reference run, **101 of 105** citations matched their cited page; the **4** that did not are shown, not hidden.

> **Two denominators — do not blur them.** §12 reports **105 citations across 22 pages, 101 matched, 4 marked**, covering every stage of the run. The *scoring stage's finding evidence alone* is **70 citations — 61 `exact`, 5 `layout`, 4 `unverified`**. Both are true of different populations. A surface that shows a ratio must say which population it is over; "101 of 105" and "61 of 70" describe different things, and a memo that conflates them undercuts its own verification claim. (Corrected 2026-07-21 against `04-scoring.json` and `12-sources.md`; the earlier 104/101/3 figures were stale.)

| Verdict | Icon + label | Meaning shown to the reader | Treatment |
|---|---|---|---|
| `exact` | `✓ Verified exact` (green) | The quoted string was found character-for-character on the cited page | Default. Quote shown normally. |
| `layout` | `▨ Verified — layout-normalised` (amber) | Matched after whitespace/line-break normalisation. Typical of multi-line table cells in PowerPoint-derived PDFs | Quote shown with a note: *"Matched after normalising whitespace. The words are on the page; the line breaks are not reproducible."* |
| `unverified` | `⚠ Not mechanically confirmed` (grey outline, not red) | The string could not be matched against the extracted page text | **Quote is retained and displayed in full**, with: *"This quote could not be matched to the extracted text of p.37. The engine's extraction loses spatial layout on slide-derived pages. Open the page image and read it yourself."* Primary action: **Open source page**. |

**An `unverified` quote is never hidden and never silently dropped.** Hiding it would make the citation-verification discipline invisible at the exact moment it matters. It is also not styled as an error — it is a statement about the extractor, not about the manager. The §12 Sources summary states the ratio plainly: *"105 citation(s) across 22 page(s) of the source document. Every quote was checked against the text of the page it cites; 101 of 105 matched. 4 did not and are marked — these cluster on multi-line table layouts where whitespace is not reproducible."*

### 4.4 §11 open-question item

| Label | Value (worked example) | Source |
|---|---|---|
| Question key | `gp_commitment` | `unresolved_by_stage.*[].key` |
| Stage group | `Scoring (criteria evaluation) — 31 items` | `unresolved_by_stage` key |
| Body | `searched all 52 pages for 'sponsor commitment', 'GP commitment', 'manager commitment', 'co-investment', 'skin in the game'… No sponsor or manager commitment figure appears anywhere. CR-0030 could not fire.` | item text |
| Kind | `document_answerable` | `[TODO: PRD 07 must define the field that carries question kind. This spec assumes `unresolved[].kind ∈ {document_answerable, analyst_answerable, externally_blocked}`. Reconcile when 07 lands.]` |
| Linked criterion | `CR-0030` | Parsed / carried on the item |
| Suggested source | `PPM` — *"page 37 refers readers to the PPM"* | Item text carries the pointer |
| Answer state | `unanswered` / `answered — document` / `answered — analyst-attested` / `blocked` | PRD 07 |

### 4.5 Contested finding (CR-0034)

| Label | Value | Source |
|---|---|---|
| Criterion | `CR-0034 — Transparent fee and waterfall disclosure` | `findings[]` |
| Tier / severity | `GREEN_FLAG` / `MEDIUM` | — |
| Contested reason | `the lenient reading fires this criterion while the strict reading does not fire it. Both readings are recorded below; the disagreement is not resolved by the engine.` | `findings[].contested_reason` |
| Lenient verdict | `fired: true`, confidence `medium`, reasoning, own evidence list | `findings[].lenient` |
| Strict verdict | `fired: false`, confidence, reasoning, own evidence list | `findings[].strict` |

---

## 5. Evidence Interaction — the two-click rule

PRD 05 §8 sets the standard: **two clicks from an assertion to the words in the document that support it.**

1. **Click 1** — the citation chip `✓ p.52 "all returns are presented on a 'gross' basis"` inside the CR-0010 card. The evidence drawer opens showing p.52's rendered image with the quote highlighted, the verdict, and the full quote text.
2. **Click 2** — "Open full page" in the drawer, for the full-screen source viewer with next/previous citation navigation.

Anything slower than this makes the engine's evidence discipline invisible to the person who needs it. Specifically prohibited: a full page navigation between the finding and its evidence, and a modal that loses the reader's scroll position in the memo.

Drawer contents:

- Rendered page image from `00-pages/`, quote region highlighted where the match is positional; **no highlight drawn when `verification = unverified`** — drawing a highlight the engine could not locate would be a fabrication.
- Quote text, verdict badge, verdict explanation.
- Every other citation on the same page, so a reader on p.37 sees all 9 findings that cite it.
- "Used by" — the list of findings citing this quote.
- Actions: `Open full page`, `Next citation`, `Copy quote with citation`, `Flag this citation`.

---

## 6. Open Questions — inline answering

This is the core interaction and the most important design decision in the spec: **three question kinds route differently.** A co-pilot that treats all three identically is annoying (overview §1).

Questions appear in two places, backed by the same component: grouped in §11, and inline under any finding whose evaluation was limited by them ("Answer this" on CR-0010 opens the `net_return_figure` question in place).

### 6.1 `document_answerable` — offer upload

**Example items:** `gp_commitment`, `key_person_clause`, `valuation_policy`, `realised_dpi`, `named_fund_investors`, `first_close_status`, `economics.management_fee basis`, `Distribution waterfall`. Several literally point at the PPM — `valuation_policy` ends *"Page 37 refers readers to the PPM."*

```
┌─ gp_commitment ────────────────────────────── document-answerable ─┐
│ Searched all 52 pages for 'sponsor commitment', 'GP commitment',    │
│ 'manager commitment', 'co-investment', 'skin in the game'. No       │
│ sponsor or manager commitment figure appears anywhere. CR-0030      │
│ could not fire.                                                     │
│                                                                     │
│ 📄 A PPM would normally answer this.                                │
│    Related: CR-0030 (GP commitment disclosed) could not fire.       │
│                                                                     │
│ [Upload a document ▸]  [I can answer this myself]  [Not applicable] │
└─────────────────────────────────────────────────────────────────────┘
```

**The bulk affordance is the point.** The header tile and a banner at the top of §11 both surface it:

> **12 of these 49 questions typically resolve from a PPM.** Upload one and re-run, and the analysis answers them together rather than one at a time. → **[Upload a PPM]**

Clicking it opens the upload flow (`screen-upload.md`) **pre-scoped to this deal** with `document_type = PPM` pre-selected and the 12 target questions listed, so the analyst sees what the upload is expected to resolve. On successful promotion the analyst is offered a re-run, producing v2.

"I can answer this myself" downgrades the item to the attestation form (§6.2) — an analyst who knows the GP commitment is 2.5% should not be forced to find a document first, but the answer is then recorded as attested, not document-grounded.

### 6.2 `analyst_answerable` — attestation with a REQUIRED source

**Example items:** `investment_committee_members` (no IC member named anywhere in 52 pages), `portfolio_construction.geography` (India, deduced from Indian counterparties and "Indian infrastructure" on p.44, never stated), `fund_terms.minimum_commitment` (deduced from the lowest Class A1 band "1-2.99 Crs" on p.38), `due_diligence_partner_firms` (p.29 shows logos; no names in extracted text).

```
┌─ investment_committee_members ──────────────── analyst-answerable ─┐
│ Page 28 asserts 'Independent industry experts on IC' and page 27    │
│ describes the IC's collective history, but no individual member is  │
│ named and the IC size is not stated. CR-0035 could not fire on the  │
│ naming limb.                                                        │
│                                                                     │
│ Your answer                                                         │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │                                                                 │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│ Source *  (required — where did this come from?)                    │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ e.g. "Call with Rahul Sharma (IR), 18 Jul 2026" or "PPM p.14"   │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│ ⓘ This will be recorded as ANALYST-ATTESTED, not document-grounded. │
│   It appears in the memo attributed to you, with your source and    │
│   today's date. It is not treated as evidence from the deck.        │
│                                                                     │
│ [Save attestation]  [Cancel]                                        │
└─────────────────────────────────────────────────────────────────────┘
```

The source field is **required and cannot be satisfied by whitespace**. An attestation without a source is an unsourced assertion entering an evidence-graded system, which is the one thing the platform exists to prevent. The attested/grounded distinction is carried through every downstream surface: memo body, §11, PDF export, and the version diff.

### 6.3 `externally_blocked` — do NOT invite an answer

**The six diligence checks:** `sebi_registration_active`, `sebi_enforcement_actions`, `mca_master_data`, `ifsca_gift_city_registration`, `registered_address_matches_hq`, `key_persons_appear_in_filings`.

These carry **no answer field, no upload button, no text input.** Inviting an analyst to "answer" a geo-fenced register check is a broken affordance, not a minor UI flaw (overview §1).

```
┌─ sebi_registration_active ──────────────────── externally blocked ─┐
│ 🚫 This check could not be performed. Nothing you can type or      │
│    upload will resolve it.                                          │
│                                                                     │
│ Source     SEBI intermediary register — www.sebi.gov.in            │
│ Attempted  2026-07-20 19:54:59 UTC                                  │
│ Outcome    unavailable                                              │
│                                                                     │
│ Why  DNS resolves (202.191.143.30 / .158) and TCP connect to :443  │
│      succeeds, but the connection is dropped after the TLS Client   │
│      Hello. A real Chrome browser fails identically to curl, which  │
│      places the block below the HTTP layer — a geo-fence or         │
│      source-IP WAF, not an outage or bot detection. A headless      │
│      browser does not help.                                         │
│                                                                     │
│ Blocks  CR-0001 (VETO — No verifiable SEBI registration)            │
│         Reported as UNEVALUATED — neither fired nor clean.          │
│                                                                     │
│ To unblock                                                          │
│   → Re-run this check from an Indian IP  [Request Indian-egress run]│
│   → Or ask the manager for the registration number and certificate  │
│     [Add to Asks list]                                              │
│                                                                     │
│ [Assign to…]   [Mark as handled outside the system ▾]               │
└─────────────────────────────────────────────────────────────────────┘
```

Per-check routing differs because the blocking reasons differ:

| Check | Blocking reason | Route offered |
|---|---|---|
| `sebi_registration_active`, `sebi_enforcement_actions` | Geo-fence / source-IP WAF below the HTTP layer | Re-run from Indian egress; or ask the manager |
| `mca_master_data` | Requires an authenticated MCA account; DIN enquiry is CAPTCHA-gated. **Deliberate access controls on a government system — the engine does not attempt to circumvent them** | Route through a licensed data provider; assign to whoever holds the account |
| `ifsca_gift_city_registration` | Directory renders rows client-side; a plain HTTP fetch yields an empty table, indistinguishable from a genuine "no match" | Request a browser-driven fetch |
| `registered_address_matches_hq` | Requires both a document HQ address (not obtained) and a filed register address | Partially unblockable — supply the HQ address, then re-run |
| `key_persons_appear_in_filings` | No filed director list retrieved | Depends on MCA/ZaubaCorp unblocking first |

Each blocked item states, in the item itself, that **absence of a check is not a finding**: *"This is NOT a finding of no adverse history — it is the absence of a search."* The `ifsca` item says the same in its own terms: an empty scrape is explicitly not reported as a negative result.

### 6.4 Answered-question rendering

Once answered, the item stays in §11 — the count moves from `49 open` to `48 open · 1 answered`, and the item shows its answer, its kind, its attribution, and an `[Undo]`. **Items never disappear on being answered**; the record of what was once unknown is part of the audit story. Answers apply to the *next* run: the item shows `Answered — will apply on re-run` until v2 is generated, and the header shows `3 answers pending — [Re-run analysis]`.

---

## 7. CTAs

### 7.1 Header

| CTA | Behaviour |
|---|---|
| **Answer questions** | Scrolls to §11 and applies the "unanswered only" filter |
| **Upload a PPM** (in tile 4) | Opens `screen-upload.md` scoped to `DL-2026-0007`, `document_type = PPM`, carrying the 12 target question keys |
| **Jump to §11** | Anchors to §11, expanded |
| **Why?** (on the veto tile) | Opens the evidence drawer on the diligence-check detail for CR-0001 / CR-0002 |
| **Export ▾** | Opens Export Memo (PRD 05 Screen 6). **§11 is non-excludable from any export** (overview) — its checkbox is present, checked, and disabled with the tooltip *"Every exported memo carries its open questions."* |
| **Compare versions** | Opens `screen-version-history.md` comparison, this version pre-selected as the right-hand side |
| **Re-run ▾** | `Re-run with pending answers (3)` · `Re-run with the current criteria set` · `Re-run with a different criteria set…`. Emits a new run; navigates to Run Progress (PRD 02 Screen 4). Disabled with a reason when a run is already in flight for this deal |
| **What this means** (draft banner) | Opens an explainer on draft vs versioned criteria sets |
| **Review: n/12** | Opens the review checklist; jumps to the next unreviewed section |

### 7.2 Section header

| CTA | Behaviour |
|---|---|
| **Mark reviewed** | Emits `MEMO_SECTION_REVIEWED` with `review_status = REVIEWED`. Memo status → `IN_REVIEW` on first, → `REVIEWED` on twelfth |
| **Flag section** | Emits `MEMO_SECTION_REVIEWED` with `FLAGGED`. **Requires `review_note`** — a flag without a reason is noise (PRD 05 §3) |
| **Collapse / expand** | Persists per user. **Not available as a default-collapsed state for §1, §2, §11** |
| **Copy section** | Copies markdown with citations intact |

### 7.3 Finding card

| CTA | Behaviour |
|---|---|
| **Citation chip** | Opens the evidence drawer at that quote |
| **Open source page** | Opens the full source viewer at the cited page |
| **Override finding** | Opens Override Finding (PRD 05 Screen 5). Records analyst disagreement; does **not** recompute the score — an override is a recorded human judgement, not a re-scoring |
| **Answer this** | Expands the linked open question inline, routed by kind |
| **Flag** | Flags the individual finding with a required note |
| **Open criterion** | Opens the criterion in `screen-criteria-set-editor.md`, read-only when the set is ACTIVE |
| **Show reasoning ▾** | Expands the engine's full reasoning text |
| **Show absence evidence ▾** | Expands the negative-search record |

### 7.4 Contested finding (§9)

| CTA | Behaviour |
|---|---|
| **Accept lenient reading** / **Accept strict reading** | Records the analyst's judgement as an override with the chosen reading and a required rationale. **Neither resolves the contest in the engine** — both readings remain in the artifact and in every export |
| **Leave contested** | Explicit no-op, recorded, so "we saw it and left it" is distinguishable from "nobody looked" |
| **Compare readings side by side** | Two-column view: lenient vs strict reasoning, confidence, and evidence lists |

Contested findings get a **distinct visual treatment** — split-card, both verdicts labelled, no single fired/not-fired badge, and no "resolve" action anywhere. They are for human judgement, not resolution by the system (PRD 02 §8, PRD 05 §8).

### 7.5 §11 items

| CTA | Kind | Behaviour |
|---|---|---|
| **Upload a document** | document_answerable | Scoped upload flow |
| **I can answer this myself** | document_answerable | Converts to attestation form |
| **Save attestation** | analyst_answerable | Validates answer + source, records analyst-attested answer |
| **Request Indian-egress run** | externally_blocked | Queues a re-run tagged for an Indian egress worker. `[TODO: PRD 02 does not currently model egress-tagged workers. Confirm whether this is a worker capability tag or a manual ops request.]` |
| **Add to Asks list** | externally_blocked | Appends to §10 Asks for the manager |
| **Assign to…** | externally_blocked | Assigns to a user who can unblock; emits a task/notification |
| **Mark as handled outside the system ▾** | externally_blocked | Records that the check was done elsewhere, with a required note and the outcome. Does **not** mark the criterion evaluated |
| **Not applicable** | any | Dismisses with a required reason; item remains visible, struck through |
| **Undo** | any answered | Reverts to unanswered; recorded as an event |

---

## 8. Validations

| # | Rule | Message |
|---|---|---|
| V1 | `review_note` required when `review_status = FLAGGED` | "Say why you're flagging this section. A flag without a reason is noise." |
| V2 | Attestation `answer` required, non-whitespace, min 3 chars | "Enter your answer." |
| V3 | **Attestation `source` required, non-whitespace, min 3 chars** | "Where did this come from? A call, an email, a document and page — anything, but something. Attested answers without a source are not accepted." |
| V4 | Attestation source cannot be `"n/a"`, `"none"`, `"-"`, `"unknown"` (case-insensitive) | "That isn't a source. If you don't have one, this stays an open question — which is a valid outcome." |
| V5 | Override requires a rationale, min 20 chars | "Explain your disagreement. This is read by the IC." |
| V6 | Contested-reading acceptance requires a rationale | "Record why you prefer this reading." |
| V7 | "Not applicable" requires a reason | "Why does this not apply?" |
| V8 | Re-run blocked while a run is in flight for this deal | "An analysis is already running for DL-2026-0007 (started 4m ago). Wait for it to finish or cancel it." |
| V9 | Re-run with zero pending answers and unchanged criteria warns | "Nothing has changed since v1 — no new answers, same criteria set (hash `94ec11df…`). A re-run will produce the same result. Re-run anyway?" |
| V10 | Export cannot exclude §11 | Checkbox disabled: "Every exported memo carries its open questions." |
| V11 | Answering is disabled on non-latest versions | "v1 is frozen. Answers apply to v3, the current version. [Open v3]" |
| V12 | Uploaded document must be a PDF (PRD 01 §3) | "Only PDFs can be analysed. This file is `application/msword`." |
| V13 | Attestation on a question already answered by another analyst | "Priya answered this 20 minutes ago: '…'. Replace her answer, or leave it?" |
| V14 | Section review requires the section to have been scrolled into view | `[TODO: is scroll-tracked review a requirement or paternalism? PRD 05 does not specify. Flagged rather than decided.]` |

---

## 9. Conditional States

| State | Trigger | What the user sees |
|---|---|---|
| **A — Draft criteria set** | `run.criteria.version` is null | **Full-width amber banner, top of screen, above the fund name, not dismissible.** "These findings were produced from a DRAFT criteria set. `CS-2026-0001` carries no version number, meaning it has not been through an approval workflow. The rules themselves — what counts as a red flag, and at what threshold — are provisional and have not been signed off. Treat the findings as indicative of what this rule set would flag, not as an assessment against an agreed house view." Actions: `What this means`, `Open CS-2026-0001`. Every export of this memo carries the same banner on page 1 |
| **B — Veto unevaluated** | `result.veto_unevaluated` non-empty | Header tile: `2 VETOES NOT EVALUATED`. Rendered as **neither passed nor fired** — grey, never a green tick, never a red cross. This is the state most likely to be mis-rendered as a pass (PRD 05 §8). §1 and §2 both carry: "This is not a finding that registration and enforcement history are clean, and nothing in this memo should be read as clearing either." |
| **C — Veto fired** | `result.veto_fired` non-empty | Red header band replaces the recommendation tile: `VETOED — CR-00NN`. §1 leads with the reason. All other sections still render, and evidence remains browsable — a veto is not a reason to stop showing work |
| **D — Loading** | Memo fetch in flight | Section skeletons in the rail and body, header tiles skeletonised. **The recommendation tile does not render a placeholder value** — a skeleton reading "HOLD" that later becomes "PASS" is worse than a blank |
| **E — Empty (no memo)** | Deal exists, no completed run | "No memo yet for DL-2026-0007." Shows the deal's documents and a `[Run analysis]` CTA, or the in-progress state if a run is live |
| **F — Analysis running** | A run for this deal is `RUNNING` | **Per-stage progress, never a spinner.** Runs take 8–16 minutes (reference run: 8m 45s). Live from `status.jsonl`: <br>`✓ Classification  12.0s  — 7/7 quotes matched their cited page`<br>`✓ Extraction      89.4s  — 45/45 quotes matched`<br>`✓ Diligence        1.0s  — 1 passed, 0 failed, 6 unavailable`<br>`⟳ Scoring       4m 32s  — strict pass … (lenient: 17 criteria, 6 fired)`<br>`○ Memo`<br>Plus elapsed total, running cost (`$1.86 of $2.30 typical`), and `[Cancel run]`. When a prior version exists: "You're seeing v1 while v2 runs. [Stay on v1]" |
| **G — Analysis failed** | Run `status = failed` | Prior version stays readable. Banner: failure code, stage, attempt count, next retry time, and the stderr excerpt **visible without a click** (PRD 02 §8). Actions: `Requeue`, `Raise budget`, `Open run`, `Reject document` |
| **H — Error loading memo** | API failure | "Couldn't load this memo." Shows the error code and `[Retry]`. Never a blank screen |
| **I — Memo hash mismatch** | `memo_sha256` ≠ hash of the file on disk | **Red banner, above everything:** "This memo does not match the file the engine wrote. The stored hash is `…` and the file on disk hashes to `…`. It may have been altered. Do not export or circulate this memo until it has been checked." Export disabled. `[Report this]` |
| **J — Restricted access** | User lacks memo read permission on this deal | "You don't have access to DL-2026-0007." Shows the deal code and the assigned analyst's name so the user can ask. No memo content, no counts, no recommendation |
| **K — Read-only role (IC Member)** | Role = IC Member | Full memo, full evidence, full §11. **No answer affordances, no override, no re-run.** Section review is available (IC Members review memos). Open questions render with kind badges and reasons but no inputs |
| **L — Read-only role (ODD Reviewer)** | Role = ODD Reviewer, entered from ODD Review Detail | Full memo read-only. **No investment-team affordances anywhere** — no triage, no advance, no re-run (PRD 04 §8: an ODD Reviewer shown a power they do not have has been mis-served). A note explains: "You're viewing the investment team's L1 memo for context. ODD findings are recorded on your own review." |
| **M — Answers pending re-run** | ≥1 answer saved, no re-run since | Header strip: "3 answers saved. They apply on the next run. [Re-run analysis]" Each answered §11 item shows `Answered — will apply on re-run` |
| **N — Superseded version** | This memo is not the latest | Blue banner: "You're reading v1. v3 is current (generated 2026-07-24, recommendation PURSUE). [Open v3] [Compare v1 → v3]" All write actions disabled per V11 |
| **O — Contested findings present** | `result.contested` non-empty | §9 badge in the rail (`⚠1`); §9 never collapsed by default; header shows `1 contested` |
| **P — Citation verification below threshold** | `unverified` count exceeds a threshold | §12 note is promoted to a header advisory: "4 of 105 citations could not be mechanically confirmed. They are marked in place." `[TODO: threshold not specified in PRD 05 — 4/105 (~96% verified) is normal for slide decks. Define with stakeholder.]` |
| **Q — All sections reviewed** | 12/12 reviewed or flagged | Header: `Reviewed ✓ 12/12 · 2 flagged`. Memo status `REVIEWED`. Enables the IC packet export path (PRD 04: entering `IC` makes the packet exportable) |
| **R — Frozen version** | Any non-latest version | Content immutable. Answer, override, review, and re-run disabled with reasons; export and download remain enabled — a frozen version must stay downloadable (overview §1) |
| **S — No open questions** | `unresolved_total = 0` | Tile 4 reads "No open questions" with a caveat: "Every criterion in CS-2026-0001 was evaluable against this document. That is a statement about the rule set as much as the document." |
| **T — Offline / stale** | Connection lost | Banner: "Not connected. You're reading a cached copy from 14:32." Read continues; all write actions disabled |

---

## 10. Open Questions

1. **PRD 07 field contract.** This spec assumes `unresolved[].kind ∈ {document_answerable, analyst_answerable, externally_blocked}` and `suggested_document_type`. The reference artifact `04-scoring.json` carries `unresolved` as **flat strings with no kind field** — the classification currently exists only in the overview's prose. PRD 07 must define the field, and the engine must emit it. Until then, kind is derivable only by heuristics over the item text, which is not good enough to route UI on.
2. **The 12-of-49 figure.** The overview says "many resolve from a PPM" and this spec renders "12 of 49". 12 is a derived count over items whose text points at a PPM or names a PPM-carried term (`gp_commitment`, `key_person_clause`, `valuation_policy`, `realised_dpi`, `named_fund_investors`, `first_close_status`, fee basis, waterfall, concentration caps, minimum commitment, IC membership, distribution mechanics). **Confirm the count and its derivation rule with the engine before it appears in the UI as a promise.**
3. **Indian-egress re-runs.** PRD 02 models workers but not egress capability tags. Is "re-run from an Indian IP" a worker tag, a separate deployment, or a manual ops request outside the system?
4. **Attestation and the engine.** Does an analyst attestation enter the next run as an input the engine reasons over, or only as an annotation displayed alongside? These are very different products. This spec assumes the former (it is what makes the loop a loop), but PRD 07 must state it.
5. **Override vs answer.** Both record human judgement against a finding. Is an override just an answer to a question the engine did not ask? Keeping them separate may be duplicating a concept.
6. **Section 11 in a 200-item memo.** 49 items is readable. A PPM run could produce several hundred. Does §11 need its own pagination or a separate workspace at some threshold — and does that break the "never collapsed" rule that makes it valuable?
7. **Scroll-tracked review** (V14) — requirement or paternalism?
8. **Concurrent answering.** V13 assumes last-write-wins with a prompt. Confirm against PRD 07's concurrency model.
