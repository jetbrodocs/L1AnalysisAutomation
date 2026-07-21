---
title: "Screen Spec — Deal List and Pipeline Board"
status: draft
created: 2026-07-21
updated: 2026-07-21
tags: [screen-spec, triage, pipeline, odd, allocator-stages, l1-analysis-platform]
---

# Screen Spec — Deal List and Pipeline Board

**Parent PRD:** `04-triage.md` (Screen 1 "Pipeline Board", Screen 2 "Deals", Screen 7 "My Deals" — one surface with three views, see §1.1).

> **Two design decisions from PRD 04 are load-bearing and non-negotiable in the UI.** (1) The stages use the allocator's own vocabulary — sourcing, initial screening, IDD, IC, commitment — because staff already hold that mental model and software that renames them is quietly rejected (§1.1). (2) **ODD is not a stage.** It is a parallel track with an asymmetric veto and its own reporting line. The moment ODD becomes a column on the investment team's board, it has been modelled as a stage and §1.2 is lost in the UI regardless of what the data model says (§8).

> **Standalone principle (PRD 06 §0).** Triage is pure workflow — the engine has no concept of a deal, a stage, or a pipeline, and must not acquire one. Nothing here supplies meaning that the memo files lack.

---

## 1. Purpose

Triage. Answer "what needs my attention, and what is stuck" across the book, and get from a deal to its memo in one click.

**Reference data:** `DL-2026-0007` — *Neo Infra Income Opportunities Fund II*, Neo Asset Management Private Limited, ~INR 5,000 crore, target 18–20% gross IRR, `INITIAL_SCREENING`, recommendation **HOLD**, red 11.0 / green 1.0, 49 open questions, criteria set `CS-2026-0001` (DRAFT).

### 1.1 Why three PRD screens are one spec

Pipeline Board (kanban), Deals (table), and My Deals (filtered table) are the same data in three shapes. They share entry points, filters, row data, and actions; only the layout differs. Speccing them separately would triplicate the ODD-treatment rules that are the hard part. **The board/table/mine toggle is a view control, not a navigation.**

---

## 2. Entry Points

| # | From | Trigger | Context passed in | Conditions |
|---|---|---|---|---|
| 1 | Primary navigation | "Deals" nav item | Last-used view and filters, per user | Any authenticated role |
| 2 | Primary navigation | "My Deals" | `assigned_analyst = current user` pre-filtered | Analyst |
| 3 | Login / home | Default landing for Analyst | Their book, sorted by what needs action | Analyst |
| 4 | Deal Detail | Breadcrumb "← Deals" | Restores prior filters and scroll position | — |
| 5 | Triage Decision (PRD 04 Screen 4) | On submit | Returns to the list with the triaged deal highlighted | — |
| 6 | Intake Dashboard (PRD 01 Screen 8) | "Open queue" / promotion counts | Filtered to recently promoted | Analyst |
| 7 | Promotion (PRD 01 Screen 3) | After "Submit for Analysis" | List filtered to the new deal, analysis running | — |
| 8 | Funnel Report (PRD 04 Screen 6) | Drill into a stage bar | `stage` filter applied | Super Admin, IC Member |
| 9 | Stalled Deals (PRD 04 Screen 13) | "Open deal" or the stalled count | `stalled = true` filter | Super Admin |
| 10 | Manager Detail (PRD 04 Screen 9) | "Every fund they brought us" | `manager_id` filter | — |
| 11 | Passed Deals (PRD 04 Screen 5) | Toggle back to active | `decision != PASS` | — |
| 12 | ODD Queue (PRD 04 Screen 10) | **Not an entry point** — see §7 state J | — | ODD Reviewers do not enter the investment pipeline board |
| 13 | Command palette `⌘K` | Deal search by `deal_code`, `fund_name`, `manager_name` | Direct to Deal Detail, or "See all matches" here | Per PRD 04 §8 |
| 14 | Notification — analysis complete | "3 analyses finished" | Filtered to those deals | Analyst |
| 15 | Notification — ODD blocking | "ODD returned Unsatisfactory on DL-2026-0004" | Filtered to that deal | Analyst, Super Admin |
| 16 | Deep link | `/deals`, `/deals?stage=INITIAL_SCREENING`, `/deals?view=board`, `/deals?odd=blocking` | — | — |
| 17 | Saved view | User-saved filter combination | Stored filters | — |
| 18 | Email digest | "5 deals need triage" | `needs_triage` filter | — |

---

## 3. UX Layout

### 3.1 Board view (default for Analyst)

Six columns, the allocator's own stages, left to right. **ODD is not among them.**

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ Deals            [▦ Board] [☰ Table] [My deals]        [+ Upload]  [Export]  [⌘K]    │
│ Stage: all ▾  Track: all ▾  ODD: all ▾  Manager: all ▾  Age: all ▾   ☐ Needs triage  │
└──────────────────────────────────────────────────────────────────────────────────────┘

  SOURCING (4)    INITIAL SCREENING (7)   IDD (3)      IC (2)       COMMITMENT (1)
  ┌───────────┐   ┌────────────────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
  │ Sierra    │   │┌──────────────────┐│  │ Ashoka  │  │ Vantage │  │ Meridian│
  │ Roads III │   ││ Neo Infra Income ││  │ Capital │  │ Credit  │  │ Infra   │
  │ Sierra AM │   ││ Opportunities II ││  │ Fund IV │  │ Fund II │  │ Fund I  │
  │           │   ││ Neo Asset Mgmt   ││  │         │  │         │  │         │
  │ ○ no      │   ││ DL-2026-0007     ││  │ PURSUE  │  │ PURSUE  │  │ PURSUE  │
  │   analysis│   ││ ~₹5,000 cr       ││  │ 8 open  │  │ 2 open  │  │ 0 open  │
  │           │   ││                  ││  │         │  │         │  │         │
  │ 2d        │   ││ ⏸ HOLD           ││  │ ODD:    │  │ ODD:    │  │ ODD:    │
  │ [Upload]  │   ││ red 11.0 ▓▓▓▓▓▓▓ ││  │ ▶ in    │  │ ✓ sat.  │  │ ⛔ BLOCK │
  └───────────┘   ││ green 1.0 ▓      ││  │   prog. │  │   w/obs │  │  ING    │
                  ││                  ││  │ NEW     │  │ RE-UP   │  │ RE-UP   │
  ┌───────────┐   ││ ⚠ 49 open Qs     ││  │ 14d     │  │ 9d      │  │ 31d ⚠   │
  │ Kalpataru │   ││ ⚠ 2 vetoes not   ││  └─────────┘  └─────────┘  └─────────┘
  │ Yield Fund│   ││   evaluated      ││
  │ …         │   ││ ⚠ draft criteria ││   ⛔ DL-2026-0002 cannot enter COMMITMENT
  └───────────┘   ││                  ││      ODD rated Unsatisfactory 2026-07-18.
                  ││ ODD: ○ not       ││      Not overridable by the investment team.
                  ││      started     ││      [Open ODD review]
                  ││ NEW · 1d         ││
                  ││ [Triage] [Memo]  ││
                  │└──────────────────┘│
                  │ ┌────────────────┐ │
                  │ │ Highway Trust  │ │
                  │ …                  │
                  └────────────────────┘
```

**MONITORING** is reachable but not a board column by default — it holds committed funds and is a different job. Available via the stage filter and the table view.

### 3.2 ODD treatment — badge, never a column

Three rules, all from PRD 04 §1.2 and §8:

1. **ODD is a badge on the card, never a column.** A column is a position in a sequence, and ODD has no position in the investment team's sequence.
2. **The badge's form cannot be mistaken for a stage position.** It renders as `ODD: <state>` on its own line with its own glyph set, visually distinct from stage chrome.
3. **The asymmetry is visible in the badge itself.** A passing ODD review is recessive; a blocking one is loud. Because passing ODD *does not advance anything* — it merely removes an obstacle — a satisfactory badge must never look like an achievement or a green gate.

| ODD state | Badge | Weight |
|---|---|---|
| Not started | `ODD: ○ not started` | Neutral, quiet |
| Requested | `ODD: ◷ requested 3d ago` | Neutral |
| In progress | `ODD: ▶ in progress` | Neutral |
| Satisfactory | `ODD: ✓ satisfactory` | **Recessive** — grey, small. Not green, not a tick-in-a-circle, nothing that reads as "cleared to proceed" |
| Satisfactory with observations | `ODD: ✓ sat. w/ observations` | Recessive |
| Significant findings | `ODD: ⚠ significant findings` | Amber, prominent |
| Unsatisfactory | `ODD: ⛔ BLOCKING` | **Red, loud, unmissable** |
| Expired | `ODD: ⧗ expired 2026-06-30` | Amber |

**The rating scale is never rendered numerically and never beside the investment score as if comparable.** An ODD rating and an L1 recommendation are not commensurable, and a UI that displays them as a pair invites exactly the trade-off ODD exists to prevent (PRD 04 §2). The card therefore places them on separate lines with different visual languages — never in a shared "scores" row.

**The blocking case gets a column-level annotation**, not just a card badge: when a deal in `IC` has a blocking ODD review, a note sits at the foot of the `COMMITMENT` column stating the deal cannot enter and that the block is not overridable by the investment team. The veto is one-directional, so its UI presence is one-directional too — it appears as an obstacle in front of `COMMITMENT`, never as a gate that ODD opens.

### 3.3 Table view

```
☐  Deal          Fund / Manager              Stage        Track  Rec     Open  ODD          Age  Analyst
☐  DL-2026-0007  Neo Infra Income Opps II    INITIAL      NEW    ⏸ HOLD   49   ○ not started  1d  S. Jethwa
                 Neo Asset Management        SCREENING           11.0/1.0                          
   ⚠ 2 vetoes unevaluated · draft criteria set CS-2026-0001
☐  DL-2026-0004  Ashoka Capital Fund IV      IDD          NEW    ▶ PURSUE  8   ▶ in progress 14d  P. Nair
☐  DL-2026-0002  Meridian Infra Fund I       IC           RE-UP  ▶ PURSUE  0   ⛔ BLOCKING    31d  S. Jethwa
   ⛔ ODD rated Unsatisfactory 2026-07-18 — cannot enter COMMITMENT
```

Sortable on every column. Multi-select for bulk assign and export. The warning strip under a row carries the things that must not be a hover tooltip: unevaluated vetoes, draft criteria, ODD blocks.

---

## 4. Data Points Displayed

### 4.1 Deal card / row

| Label | Value | Source |
|---|---|---|
| Deal code | `DL-2026-0007` | `Deal.deal_code` |
| Fund name | `Neo Infra Income Opportunities Fund II` | `Deal.fund_name` |
| Manager | `Neo Asset Management Private Limited` | `Deal.manager_name` |
| Fund size | `~₹5,000 cr` | `02-extraction.json` fund size (p.37) |
| Target return | `18–20% gross` — **"gross" always shown** | Extraction (p.37, p.20) |
| AIF category | `CAT_II` | `Deal.aif_category` |
| Stage | `INITIAL_SCREENING` | `Deal.stage` |
| Days in stage | `1d`, amber past threshold | `Deal.stage_entered_at` |
| Track | `NEW` / `RE_UP` | `Deal.deal_track` |
| Recommendation | `HOLD` | Latest run `result.recommendation` |
| Weights | `red 11.0 / green 1.0` with proportional bars | `result.red_flag_weight`, `green_flag_weight` |
| Open questions | `49` | `result.unresolved_total` |
| Unevaluated vetoes | `⚠ 2 vetoes not evaluated` | `result.veto_unevaluated[]` |
| Contested count | `1 contested` | `result.contested[]` |
| Draft criteria warning | `⚠ draft criteria set` | `run.json → criteria.version is null` |
| Version count | `v1` / `v3` badge | Version chain |
| ODD state | Per §3.2 | `ODDReview.status`, `.rating` |
| ODD blocking | `Deal.odd_blocking` | `Deal.odd_blocking` |
| ODD expiry | `expires 2026-12-01` | `ODDReview.expires_at` |
| Assigned analyst | `S. Jethwa` | `Deal.assigned_analyst_id` |
| Last activity | `analysis completed 4h ago` | Latest event |
| Latest decision | `HOLD by S. Jethwa, 2026-07-21` | Latest `DEAL_TRIAGED` |
| Prior fund (re-up) | `NIIOF-I — committed ₹200 cr, 2023` | Prior Deal |
| Document count | `2 documents` | Count |
| Analysis state | `running` / `failed` / `none` | Latest run status |

### 4.2 Header counts

Per-stage counts; needs-triage count; stalled count; ODD-blocking count (its own counter, never folded into a stage count); analyses running; analyses failed.

---

## 5. CTAs

### 5.1 Header

| CTA | Behaviour |
|---|---|
| **Board / Table / My deals** | View toggle, persisted per user |
| **+ Upload** | Opens `screen-upload.md` |
| **Export** | CSV/XLSX of the current filtered set with filters recorded in the file |
| **Save this view** | Names the current filter combination |
| **Filters** | Stage, track, ODD state, manager, analyst, recommendation, age, criteria set, has-open-questions, needs-triage, stalled. **ODD is a filter dimension, never a stage value** — `stage=ODD` must not be expressible |

### 5.2 Card / row

| CTA | Behaviour |
|---|---|
| **Open deal** | `screen-deal-detail.md` |
| **Triage** | Triage Decision form (PRD 04 Screen 4). Blocked before `DEAL_SCORED` — "Nothing to decide against yet" |
| **Memo** | Straight to the Memo Reader at the latest version. **One click from the board to the memo** |
| **Advance** | Stage advance with gate checks (§6). On the board, drag-to-advance |
| **Assign** | Assigns an analyst |
| **Add note** | Inline note, emits `DEAL_NOTE_ADDED` |
| **Request ODD** | Emits `ODD_REVIEW_REQUESTED`, routes to the ODD queue. **This is the only ODD action available to the investment team** — they can ask for a review, never conduct or resolve one |
| **Open ODD review** | Read-only view of the ODD review (PRD 04 Screen 12) |
| **Upload document** | Upload scoped to this deal |
| **Re-run analysis** | Queues a run; card shows live per-stage progress |

### 5.3 Bulk

Assign, export, add to a saved view. **No bulk advance and no bulk triage** — both are judgements with a required rationale, and a bulk affordance would make the rationale pro forma, which is how an audit trail becomes worthless.

---

## 6. Validations

| # | Rule | Message |
|---|---|---|
| V1 | Advance only along the state machine (PRD 04 §4) | "A deal can't go from Sourcing straight to IC." |
| V2 | `INITIAL_SCREENING` requires a promoted document and a run | "No analysis yet." |
| V3 | `IDD` requires `DEAL_SCORED`, a `PURSUE` decision against the latest run, and an assigned analyst | "Ashoka Capital Fund IV needs an assigned analyst before it can enter IDD." |
| V4 | `IC` requires an ODD review not in `NOT_STARTED`, a latest `PURSUE`, and a target commitment amount | "No ODD review has been requested. [Request ODD]" |
| V5 | **`COMMITMENT` blocked by `odd_blocking`** | "DL-2026-0002 cannot enter Commitment. ODD rated it Unsatisfactory on 2026-07-18. **This gate is not overridable by the investment team.** It clears only on a new ODD review with a non-blocking rating, or by a Super Admin acting with an ODD Reviewer's recorded concurrence." |
| V6 | Super Admin gate override requires a rationale, recorded in `gate_checks_passed` | "Which gate are you waiving, and why?" |
| V7 | Backward moves require a rationale | "Why is this going back to Initial Screening?" |
| V8 | Triage before `DEAL_SCORED` blocked | "There's nothing to decide against yet." |
| V9 | Triage requires a rationale; `PASS` requires a reason code | "Record why." |
| V10 | Advancing on a draft-criteria analysis warns | "This deal was scored with CS-2026-0001, a draft criteria set that has not been signed off. Advance anyway?" |
| V11 | Advancing with unevaluated vetoes warns | "CR-0001 and CR-0002 were never evaluated — the SEBI register was unreachable. This is not a finding that registration and enforcement are clean. Advance anyway?" |
| V12 | Expired ODD on a deal in `IC` | "ODD review ODD-2026-0014 expired 2026-06-30. [Request refresh]" |
| V13 | Assign requires an active user with the Analyst role | — |
| V14 | Re-run blocked while one is in flight | "An analysis is already running for this deal." |

**V11 is the most important validation on this screen.** A HOLD with two unevaluated vetoes reads, at a glance, like a mild negative. It is actually a partial assessment with the two most serious checks never performed. The confirmation is where that gets said before a deal advances on a misreading.

---

## 7. Conditional States

| State | Trigger | What the user sees |
|---|---|---|
| **A — Empty (no deals)** | Nothing in the system | "No deals yet. Upload a deck to start." `[+ Upload]`, with a note that intake accepts browser upload and API |
| **B — Empty (filtered)** | Filters match nothing | "No deals match these filters." `[Clear filters]`, showing which filters are active |
| **C — Empty column** | A stage has no deals | Column keeps its header and count `(0)` with a quiet dropzone. Columns never disappear — a board that reflows as counts change is unreadable |
| **D — Loading** | Fetch in flight | Card skeletons in the correct columns |
| **E — Error** | API failure | "Couldn't load deals." Error code, `[Retry]` |
| **F — Analysis running** | ≥1 run in flight | The card shows **per-stage progress, not a spinner**: `⟳ Scoring (strict pass) · 6m 12s`, with the five stages and their reference durations (classification 12s, extraction 89s, diligence 1s, scoring 333s, memo 90s; 8–16 min total). Triage and Advance disabled with "Analysis in progress". Card updates live |
| **G — Analysis failed** | Latest run failed | Card badge `⚠ analysis failed`, failure code and stage visible without a click. `[Requeue] [Open run]`. The deal stays in its stage — a failed run is not a triage outcome |
| **H — ODD blocking** | `odd_blocking = true` | Red badge on the card; annotation at the foot of `COMMITMENT`; deal counted in a header ODD-blocking counter. Advance to `COMMITMENT` blocked per V5 |
| **I — ODD expired** | Past `expires_at` | Amber badge, `[Request refresh]` |
| **J — Restricted (ODD Reviewer)** | Role = ODD Reviewer | **This screen is not in their navigation at all.** If reached by deep link: "This is the investment team's pipeline. Your work is in the ODD queue. [Go to ODD queue]" No board, no cards, no advancement affordances anywhere — an ODD Reviewer shown an "Advance to IC" button they cannot press has been shown a power they do not have (PRD 04 §8) |
| **K — Restricted (IC Member)** | Role = IC Member | Full read, memos openable. No triage, no advance, no assign |
| **L — Restricted (Analyst, unassigned deals)** | `[TODO: PRD 04 does not state whether analysts see the whole book or only their own. "My Deals" existing as a separate view implies they see everything by default. Confirm.]` | — |
| **M — Stalled deals** | Past the stage age threshold | Amber age chip and `⚠`. Board offers "Sort by age" — a board sorted by recency hides exactly the deals that need attention |
| **N — Re-up track** | `deal_track = RE_UP` | Card carries `RE-UP` and the prior fund's outcome: "NIIOF-I — committed ₹200 cr, 2023. ODD: satisfactory with observations." The institution's information advantage is visible at list level, not only on the detail screen (PRD 04 §1.3) |
| **O — Needs triage** | Scored, not yet triaged | `[Triage]` becomes the card's primary action; counted in the header |
| **P — Draft criteria** | Latest run used an unversioned set | `⚠ draft criteria` chip; V10 on advance. A whole board scored on a draft set shows a board-level strip: "7 deals were scored with draft criteria set CS-2026-0001." |
| **Q — Unevaluated vetoes** | `veto_unevaluated` non-empty | `⚠ 2 vetoes not evaluated` chip. **Never rendered as a pass.** V11 on advance |
| **R — Multiple versions** | ≥2 versions | `v3` badge linking to `screen-version-history.md` |
| **S — Offline** | Connection lost | "Not connected — showing a cached copy from 14:32." Read continues, writes disabled |
| **T — Board over capacity** | A column exceeds ~50 cards | Virtualised scroll within the column, count in the header, "Sorted by age" default. Never silently truncated |

---

## 8. Open Questions

1. **Analyst visibility scope** (state L) — whole book or own deals only?
2. **Drag-to-advance and gates.** Dragging a card to `COMMITMENT` when ODD is blocking: does it snap back with an explanation, or refuse the drop? Snapping back after the fact teaches the rule; refusing prevents the error. **Current reading: allow the drop and snap back with V5's message**, because the message is the point and a refused drop teaches nothing. Needs a decision.
3. **Monitoring as a column.** Excluded by default here. Confirm — allocators do track committed funds, but on this board it would be the widest column and the least actionable.
4. **The anchoring-bias question stays open.** PRD 04 §8 flags whether the memo recommendation should be hidden until the analyst writes a rationale. This screen shows `HOLD` on every card, which **settles that question by default in the negative** — by the time an analyst opens the triage form they have seen the recommendation ten times. If the anchoring mitigation is wanted, it has to start here, not on the triage form. Flagging because it is a genuine conflict between two PRD requirements, not a UI detail.
5. **ODD counter placement.** The header ODD-blocking counter is arguably a stage-like treatment of ODD by another route. **Current reading: acceptable, because it is a count of obstacles, not a position in a sequence.** Worth a second opinion.
6. **Re-up prior-outcome data.** State N assumes the prior deal's decision and ODD rating are cheaply available at list level. For a manager with five prior funds, which one shows?
7. **Fund size and target return on the card.** Both come from extraction with page citations. On the card they appear without citations, which is the only place in the platform a number appears uncited. Acceptable at list density, or does it breach the evidence discipline?
