---
title: "Screen Spec — Version History and Causal Diff"
status: draft
created: 2026-07-21
updated: 2026-07-21
tags: [screen-spec, version-history, causal-diff, evidence-loop, audit, l1-analysis-platform]
---

# Screen Spec — Version History and Causal Diff

**Parent PRD:** `08-version-history.md` — **not yet written** (verified absent 2026-07-21). This spec derives from `00-overview.md` §1 ("Answering questions and re-running produces a new version of the same analysis (v1 → v2 → v3). Evidence accumulates; prior versions stay frozen and downloadable. The version chain is the audit story"), `05-memo.md` Screen 8 (Memo Comparison), and `06-analysis-engine.md` §3 (the twelve-section file layout and its diff consequence).

> **Reconcile when PRD 08 lands.** Where this spec asserts a field or event that PRD 08 later defines differently, PRD 08 wins — record the conflict here rather than silently diverging. The specific assumptions at risk are listed in §8.

> **Standalone principle (PRD 06 §0).** Versioning is workflow, and workflow belongs to Phlo. Each version's underlying artifact directory is already a complete, readable answer on its own — an analyst who opens `05-memo/00-index.md` from v2 on a laptop needs nothing from this screen. **This screen adds the relationship between versions, never the meaning of any one of them.** If a diff row is only intelligible here, the section file it came from is under-written and that is an engine bug.

---

## 1. Purpose

Show how the understanding of one deal evolved, and **why each change happened**. The version chain is the audit story: *here is what we knew, here is what we learned, here is what it changed.*

The comparison is **causal, not textual**. A textual diff of two markdown files tells an analyst that words moved. A causal diff tells them:

> **CR-0030 flipped `not fired` → `fired`** because the PPM (uploaded 24 Jul, p.14) disclosed a 2.5% GP commitment.

That sentence is the product. Everything else on this screen supports it.

**Reference data:** deal `DL-2026-0007`, *Neo Infra Income Opportunities Fund II*. v1 is the real run `fd33c73e-2db5-4389-855a-e597a476889c` — 2026-07-20, HOLD, red 11.0 / green 1.0, 4 red flags, 1 green, 1 contested, 2 vetoes unevaluated, **49 open questions**, 104 citations across 22 pages, criteria set `CS-2026-0001` (DRAFT). v2 and v3 in this spec are illustrative continuations of that real run and are marked as such wherever they appear.

---

## 2. Entry Points

| # | From | Trigger | Context passed in | Conditions |
|---|---|---|---|---|
| 1 | Memo Reader header | "Compare versions" | `deal_id`, current `version_no` pre-selected as the right side | ≥2 versions exist |
| 2 | Memo Reader | Superseded-version banner → "Compare v1 → v3" | `deal_id`, both version numbers | Viewing a non-latest version |
| 3 | Deal Detail — Analysis tab | Click "Version history" or any version row | `deal_id` | ≥1 version |
| 4 | Deal Detail | "What changed?" on a version row | `deal_id`, that version vs its predecessor | ≥2 versions |
| 5 | Run Detail (PRD 02 Screen 3) | "Compare with previous run" | `run_id` → resolves version pair | A prior run exists on the same deal |
| 6 | Notification — re-run finished | "See what changed" | `deal_id`, new version vs previous | Fired on `MEMO_GENERATED` for a re-run |
| 7 | Evidence loop — after answering | "3 answers applied. See what changed." | `deal_id`, new vs previous | Post-re-run |
| 8 | Deal list (`screen-deal-list.md`) | Click a version-count badge `v3` on a row | `deal_id` | ≥2 versions |
| 9 | Export History (PRD 05 Screen 7) | "Compare with current" on an exported version | `deal_id`, exported version vs latest | The export is not the latest |
| 10 | Triage Decision (PRD 04 Screen 4) | "What changed since the last decision?" | `deal_id`, version at last decision vs latest | A prior `DEAL_TRIAGED` exists |
| 11 | Deep link | `/deals/{id}/versions`, `/deals/{id}/compare?from=v1&to=v3`, `…&section=04-risk-factors` | — | Section anchor opens that section's diff expanded |
| 12 | Command palette `⌘K` | Deal search → "Version history" action | `deal_id` | — |
| 13 | Manager Detail (PRD 04 Screen 9) | Cross-fund history → a deal's version chain | `deal_id` | — |

---

## 3. UX Layout

Two modes on one screen: **Chain** (default) and **Compare**. Chain answers "what happened to this deal"; Compare answers "what changed between these two points".

### 3.1 Chain mode

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ Neo Infra Income Opportunities Fund II · DL-2026-0007                                 │
│ Neo Asset Management Private Limited                    [Chain] [Compare]  [Export ▾] │
└──────────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                       │
│  ● v3 ── 2026-07-26 ─────────────────────────────────────────── CURRENT ────────────  │
│  │      PURSUE                        Open questions  31  ▼18                         │
│  │      red 5.0 / green 3.0  ▼6.0     Evidence  +2 documents, +38 citations           │
│  │      Criteria CS-2026-0002 v1 ⚠ changed                                            │
│  │      Triggered by: PPM upload (24 Jul) + 6 attestations                            │
│  │      [Open memo]  [Download ↓]  [Compare with v2]                                  │
│  │                                                                                     │
│  ●  ── What changed v2 → v3 ─────────────────────────────────────────────────────────  │
│  │     • CR-0030 not fired → fired   PPM p.14 disclosed 2.5% GP commitment            │
│  │     • CR-0016 fired → not fired   PPM p.31 gave the valuation policy               │
│  │     • Recommendation HOLD → PURSUE                                                  │
│  │     • 18 open questions closed (12 by the PPM, 6 by attestation)                   │
│  │     [See full comparison ▸]                                                        │
│  │                                                                                     │
│  ● v2 ── 2026-07-24 ────────────────────────────────────────────────────────────────  │
│  │      HOLD                          Open questions  49 → 37  ▼12                    │
│  │      red 9.0 / green 2.0  ▼2.0     Evidence  +1 document (PPM, 88pp), +31 citations│
│  │      Criteria CS-2026-0001 (draft) — unchanged                                     │
│  │      Triggered by: PPM upload 2026-07-24 09:14 by Sharva Jethwa                    │
│  │      [Open memo]  [Download ↓]  [Compare with v1]                                  │
│  │                                                                                     │
│  ● v1 ── 2026-07-20 ──────────────────────────────────── FIRST ANALYSIS ────────────  │
│         HOLD                          Open questions  49                               │
│         red 11.0 / green 1.0          Evidence  1 document (52pp), 104 citations      │
│         Criteria CS-2026-0001 (DRAFT — unversioned) ⚠                                 │
│         2 vetoes UNEVALUATED (CR-0001, CR-0002 — SEBI checks not yet run)             │
│         Triggered by: document promotion, run fd33c73e                                 │
│         [Open memo]  [Download ↓]                                                      │
│                                                                                       │
└──────────────────────────────────────────────────────────────────────────────────────┘

  ✓ CR-0001 and CR-0002 became EVALUABLE in v4 (2026-07-21).
    The SEBI register was reachable all along — the earlier "unreachable"
    reading was a misdiagnosis, corrected in the engine. Both checks now run.
    This is a BECAME_EVALUABLE delta and outranks every other row.   [Why] [Compare v3 → v4]
```

Each node carries the five things the brief requires — **date, recommendation, open-question count, evidence added** — plus the criteria set, because a recommendation that moved because the *rules* changed is a categorically different event from one that moved because the *evidence* changed, and conflating them is the failure mode this screen exists to prevent.

**Deltas are always shown against the previous version** (`▼18`, `▼6.0`), because the absolute number answers "where are we" and the delta answers "what did that re-run buy us".

The **persistent unevaluable footer** is deliberate. An analyst watching open questions fall 49 → 37 → 31 could reasonably conclude the picture is clearing. Two vetoes never evaluated on any version is the one fact that trend hides, and it belongs where the trend is displayed.

### 3.2 Compare mode — section-level causal diff

The memo is **twelve section files** (PRD 06 §3), so the diff unit is a section, not a 58KB blob. Sections are listed in numeric order with a change summary each; only changed sections expand by default.

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│  Compare   [ v2 · 24 Jul · HOLD ▾ ]  →  [ v3 · 26 Jul · PURSUE ▾ ]                    │
│                                                                                       │
│  ┌─ WHY IT CHANGED ─────────────────────────────────────────────────────────────────┐ │
│  │ Recommendation  HOLD → PURSUE                                                     │ │
│  │                                                                                   │ │
│  │ Because red-flag weight fell 9.0 → 5.0 and green rose 2.0 → 3.0:                  │ │
│  │                                                                                   │ │
│  │  ▲ CR-0030  GP commitment disclosed          not fired → FIRED   green +1.0      │ │
│  │    Cause: PPM (uploaded 24 Jul) p.14 — "the Sponsor shall contribute 2.5%        │ │
│  │           of aggregate capital commitments"                          ✓ exact ▸   │ │
│  │                                                                                   │ │
│  │  ▼ CR-0016  Valuation policy undisclosed        FIRED → not fired  red −2.0      │ │
│  │    Cause: PPM p.31 — "Portfolio valuations shall be performed semi-annually      │ │
│  │           by an independent registered valuer"                       ✓ exact ▸   │ │
│  │    In v2 this fired on absence across 52 pages. The PPM supplied the policy.     │ │
│  │                                                                                   │ │
│  │  ▼ CR-0014  Sector/counterparty concentration   FIRED → not fired  red −2.0      │ │
│  │    Cause: PPM p.52 — single-issuer cap of 15% of commitments        ✓ exact ▸    │ │
│  │    In v2 the deck stated only "Atleast 80%" floors (p.23), which are minimums.   │ │
│  │                                                                                   │ │
│  │  = CR-0010  Gross-only return disclosure        FIRED → FIRED      unchanged     │ │
│  │    The PPM did not supply a net-to-investor figure. Still fires on p.52          │ │
│  │    "all returns are presented on a 'gross' basis".                               │ │
│  │                                                                                   │ │
│  │  ⚠ CR-0001, CR-0002                       UNEVALUATED → UNEVALUATED              │ │
│  │    Cause: unchanged — the SEBI checks did not run on either version.             │ │
│  │    Not a change, and not a clearance.                                            │ │
│  └───────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                       │
│  ┌─ WHAT CAUSED IT ────────────────────────────────────────────────────────────────┐  │
│  │ 📄 PPM uploaded 2026-07-24 09:14 by Sharva Jethwa · 88pp · sha256 7f3a91c4…      │  │
│  │    Resolved 12 open questions · added 31 citations · caused 3 finding flips      │  │
│  │ ✍ 6 analyst attestations by Sharva Jethwa, 25 Jul                                │  │
│  │    investment_committee_members · geography · minimum_commitment · +3            │  │
│  │    Recorded as ANALYST-ATTESTED, not document-grounded                            │  │
│  │ ⚙ Criteria set CS-2026-0001 (draft) → CS-2026-0002 v1                            │  │
│  │    ⚠ The rules changed between these versions. 1 of the 3 flips is attributable  │  │
│  │      to a rule change, not to new evidence. [Isolate rule-driven changes]        │  │
│  └───────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                       │
│  SECTIONS                                                     [Show unchanged ☐]      │
│  ┌───────────────────────────────────────────────────────────────────────────────────┐│
│  │ 01-recommendation.md      ● changed    HOLD → PURSUE                          ▾  ││
│  │ 02-rationale.md           ● rewritten  3 flips restructured the argument       ▸  ││
│  │ 03-fund-facts.md          ● changed    4 fields: GP commitment, valuation…    ▸  ││
│  │ 04-risk-factors.md        ● changed    −2 findings (CR-0016, CR-0014)          ▸  ││
│  │ 05-supporting-factors.md  ● changed    +1 finding (CR-0030)                    ▸  ││
│  │ 06-fees-and-terms.md      ● changed    fee basis now stated (PPM p.28)         ▸  ││
│  │ 07-team.md                ○ unchanged                                             ││
│  │ 08-track-record.md        ● changed    realised DPI now stated (PPM p.19)     ▸  ││
│  │ 09-contested-findings.md  ● changed    CR-0034 resolved by PPM fee basis      ▸  ││
│  │ 10-asks.md                ● changed    −9 asks answered, +2 new                ▸  ││
│  │ 11-open-questions.md      ● changed    37 → 31  (−12 closed, +6 new)          ▾  ││
│  │ 12-sources.md             ● changed    +31 citations, +1 source document       ▸  ││
│  └───────────────────────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Section diff, expanded

Expanding a section gives the causal view first and the textual view second. **Text diff is available but never the default** — it is the fallback when the causal attribution is incomplete, not the primary reading.

```
  ▾ 04-risk-factors.md                                    [Causal] [Text] [Side-by-side]

     REMOVED — CR-0016 Valuation policy undisclosed (RED FLAG / HIGH, weight 2.0)
       v2: fired on absence. "Searches across all 52 pages returned zero hits for
           'valuer', 'independent valuation', 'fair value'…"
       v3: not fired.
       Cause  PPM p.31 supplied the policy — semi-annual, independent registered
              valuer, named methodology.                            [See evidence ▸]
       Effect red-flag weight −2.0

     REMOVED — CR-0014 Sector and counterparty concentration (RED FLAG / HIGH, w 2.0)
       …

     UNCHANGED — CR-0010, CR-0011  (2 findings)                         [Expand]

     ⓘ §11 carries 6 NEW open questions raised by the PPM itself.
       A longer document answers questions and asks them.            [See them ▸]
```

That last note matters. Open questions falling monotonically would be the intuitive expectation, and it is wrong: on the illustrative v2→v3 the PPM closes 12 and opens 6. A UI that only ever shows a decreasing count would misrepresent what a re-run does.

---

## 4. Data Points Displayed

### 4.1 Version node

| Label | Value (v1 = real) | Source |
|---|---|---|
| Version number | `v1` | `MemoVersion.version_no` |
| Generated at | `2026-07-20 20:02:02 UTC` | `run.json → completed_at` |
| Recommendation | `HOLD` | `04-scoring.json → result.recommendation` |
| Recommendation basis | `red-flag weight 11.0 materially exceeds green-flag weight 1.0…` | `result.recommendation_basis` |
| Red / green weight | `11.0` / `1.0` | `result.red_flag_weight`, `green_flag_weight` |
| Criteria evaluated | `17` | `result.criteria_evaluated` |
| Fired summary | `4 red · 1 green · 1 contested · 2 unevaluated` | `result.*_fired[]`, `contested[]`, `unevaluated[]` |
| Open questions | `49` | `05-memo.json → result.unresolved_total` |
| Open-question delta | `▼18` vs previous | Computed |
| Documents in evidence | `1 document, 52pp` | Documents attached to the run |
| Citation count | `104 across 22 pages` | `12-sources.md` / `05-memo.json` |
| Citation verification | `101 of 104 matched` | Sources section |
| Criteria set | `CS-2026-0001 (DRAFT — unversioned)` + hash `94ec11df…` | `run.json → criteria.*` |
| Trigger | `document promotion` / `PPM upload` / `6 attestations` | `[TODO: PRD 08 must define the field carrying re-run cause. Assumed `MemoVersion.triggered_by`.]` |
| Triggered by (user) | `Sharva Jethwa` | Event actor |
| Run id | `fd33c73e` | `run.json → run_id` |
| Cost | `$2.30` | `run.json → cost_usd` |
| Duration | `8m 45s` | `started_at` → `completed_at` |
| Engine version | `0.1.0` | `run.json → engine_version` |
| Status | `CURRENT` / frozen | Derived |

### 4.2 Causal diff row

| Label | Value (illustrative v2→v3) | Source |
|---|---|---|
| Criterion | `CR-0030 — GP commitment disclosed` | `findings[].criterion_code`, `.criterion_name` |
| Transition | `not fired → FIRED` | Both versions' `findings[].fired` |
| Tier / weight effect | `GREEN_FLAG · green +1.0` | `.tier`, `.weight` |
| **Cause** | `PPM (uploaded 24 Jul) p.14 — "the Sponsor shall contribute 2.5% of aggregate capital commitments"` | Evidence present in vN, absent in vN−1 |
| Cause type | `new document` / `attestation` / `criteria change` / `engine version` / `unexplained` | Derived — see §5 |
| Verification verdict | `✓ exact` / `▨ layout` / `⚠ unverified` | `findings[].evidence[].verification` |
| Confidence change | `medium → high` | `.confidence` both sides |

### 4.3 Change summary (chain node)

Documents added (name, pages, sha256, upload date, uploader), attestations added (question key, attester, date, source given), criteria set change (from → to, with hash), engine version change, citations added/removed, open questions closed/opened.

---

## 5. Causal Attribution — how the "because" is derived

The causal claim is the product, so how it is computed must be legible and its limits admitted.

For each finding whose state changed between vN−1 and vN, the diff classifies the cause:

| Cause type | Test | Rendering |
|---|---|---|
| **New document evidence** | The finding's evidence in vN cites a document not present in vN−1 | "Cause: PPM (uploaded 24 Jul) p.14 — [quote]" with a link to the evidence drawer |
| **Attestation** | An analyst attestation exists against a question linked to this criterion, dated between the runs | "Cause: analyst attestation by Sharva Jethwa, 25 Jul — source: 'Call with Rahul Sharma (IR)'. Recorded as attested, not document-grounded" |
| **Criteria change** | The criterion's `content_hash` differs between the sets used | "Cause: the rule itself changed. CR-0014's threshold moved from 'no cap stated' to 'no cap below 20%'. This flip is a rule change, not new evidence." |
| **Engine version** | `engine_version` differs and no evidence or rule change explains it | "Cause: unexplained. The engine version changed 0.1.0 → 0.2.0 between these runs; a flip with no evidence or rule change behind it may be a model-behaviour change. Worth checking." |
| **Unexplained** | None of the above | **"Cause: not established."** Shown plainly, never hidden and never guessed at |

**An unexplained flip is displayed as unexplained.** A diff that invents a plausible cause is worse than one that admits it cannot attribute the change — the whole value of this screen is that its causal claims can be trusted. Unexplained flips are counted in a header strip: *"2 of 5 changes could not be attributed to a cause. [Show them]"*

**Rule-driven changes are separable.** When the criteria set changed between versions, `[Isolate rule-driven changes]` re-renders the diff showing only changes attributable to evidence, with rule-driven flips greyed. This answers the question an IC will ask the first time a recommendation moves: *"did the fund get better, or did we change the test?"*

---

## 6. CTAs

| CTA | Behaviour |
|---|---|
| **Open memo** (per version) | Opens the Memo Reader at that version. Non-latest opens frozen (Memo Reader state N/R) |
| **Download ↓** (per version) | Submenu: `Branded PDF` (sections concatenated in numeric order, **§11 non-excludable**), `Markdown (all 12 section files, .zip)`, `Full artifact directory (.zip — run.json, artifacts, page text, source PDF)`. Every version stays downloadable forever, including superseded ones. The artifact download is the standalone-principle escape hatch: it is exactly what the CLI would have produced |
| **Compare with v2** | Switches to Compare mode with that pair loaded |
| **See full comparison** | Same, from an inline chain summary |
| **Version selectors** (Compare) | Two dropdowns; any pair, in any order. Reversing shows the inverse diff, labelled "Comparing backwards (v3 → v1)" so a reader is never confused about direction |
| **Show unchanged ☐** | Reveals unchanged sections and unchanged findings |
| **Causal / Text / Side-by-side** | Per-section view toggle. Causal is default; Text is a true line diff of the section file; Side-by-side shows both renderings |
| **See evidence ▸** | Opens the evidence drawer on the causing quote, with its verification verdict. Same drawer as the Memo Reader — evidence is never more than two clicks from an assertion, including here |
| **Isolate rule-driven changes** | Filters to evidence-driven changes only |
| **Show them** (unattributed) | Filters to unexplained flips |
| **Export ▾** | `Comparison as PDF`, `Comparison as markdown`, `Version chain summary (one page)`. The chain summary is the artefact an IC paper wants: how the view evolved, on one page |
| **Why** (unevaluable footer) | Opens the blocking-reason detail for CR-0001 / CR-0002 |
| **Compare v3 → v4** | Opens the diff scoped to the `BECAME_EVALUABLE` rows. **Replaced "Request Indian-egress run" on 2026-07-21** — that CTA served a geo-fence that did not exist (overview §8a). What an analyst wants at this point is not a re-run request but to see what the newly-evaluated vetoes said |
| **Re-run now** | Available when answers are pending; produces the next version |
| **Restore this version** | **Deliberately absent.** Versions are a chain, not a branch — there is nothing to restore to. If an analyst wants v1's answer they read v1, which stays frozen and downloadable |

---

## 7. Validations

| # | Rule | Message |
|---|---|---|
| V1 | Compare requires two distinct versions | "Pick two different versions." |
| V2 | Compare requires ≥2 versions to exist | Compare tab disabled: "Only one analysis so far. Comparison appears after a re-run." |
| V3 | Non-adjacent comparison permitted, but flagged | "v1 → v3 skips v2. Changes are cumulative across both re-runs." |
| V4 | Backwards comparison permitted, labelled | "Comparing backwards (v3 → v1)." |
| V5 | Comparison across different criteria sets warns | "These versions used different criteria sets (CS-2026-0001 draft → CS-2026-0002 v1). Some changes are rule changes, not evidence changes. [Isolate rule-driven changes]" |
| V6 | Comparison across engine versions warns | "Engine version changed 0.1.0 → 0.2.0 between these runs. Unattributed changes may be model-behaviour changes." |
| V7 | Download blocked when the artifact directory is missing | "The artifact directory for v1 is not on disk. The database copy of the memo is intact and still readable. [Open memo]" |
| V8 | PDF export cannot exclude §11 | Checkbox disabled: "Every exported memo carries its open questions." |
| V9 | Section diff unavailable when a section file is absent in either version | "`07-team.md` is missing from v2's output. A missing section file is a run failure, not an empty section (PRD 06 §3). [Open run]" |
| V10 | Comparison while a run is in flight | Info: "v4 is running (scoring, 6m elapsed). This comparison covers v2 → v3." |

---

## 8. Conditional States

| State | Trigger | What the user sees |
|---|---|---|
| **A — Single version** | Only v1 exists | Chain shows one node, no deltas. Compare disabled per V2. Prompt: "One analysis so far, with 49 open questions. Answering them and re-running creates v2 — and this screen becomes the record of what changed. [Answer questions]" |
| **B — Loading** | Fetch in flight | Chain skeleton with the correct number of nodes (known from the count) so the chain's shape appears before content |
| **C — Diff computing** | Comparison requested, attribution running | "Working out what changed and why…" with the section list appearing progressively. Causal attribution is more than a text diff and may take a few seconds; the honest message beats a spinner |
| **D — Empty** | Deal has no completed run | "No analysis yet for DL-2026-0007. [Run analysis]" |
| **E — Error** | API failure | "Couldn't load the version history." Error code, `[Retry]` |
| **F — Restricted access** | No read permission on the deal | "You don't have access to DL-2026-0007." Deal code and assigned analyst shown so the user can ask |
| **G — Read-only role** | IC Member / ODD Reviewer | Full chain, full comparison, full downloads. No re-run, no answer affordances |
| **H — Analysis running** | A run is in flight | A **pending node** at the top of the chain with live per-stage progress, never a spinner: `⟳ v4 — running · Scoring (strict pass) · 6m 12s elapsed · $1.86` over the five stages with their durations. Reference timings: classification 12.0s, extraction 89.4s, diligence 1.0s, scoring 332.7s, memo 89.6s. Total 8–16 min. `[Cancel run]`. Existing versions stay fully readable |
| **I — Analysis failed** | Latest run failed | Failed node in the chain, greyed, with the failure code, stage, attempt count, next retry, and the stderr excerpt **visible without a click** (PRD 02 §8). **The failed run does not become a version** — a failed run has no memo. `[Requeue] [Raise budget] [Open run]` |
| **J — Unattributed changes present** | ≥1 flip with no derivable cause | Header strip: "2 of 5 changes could not be attributed to a cause. [Show them]" Each renders "Cause: not established" |
| **K — Criteria changed between versions** | Sets differ | Amber strip per V5, `[Isolate rule-driven changes]` offered inline |
| **L — Engine version changed** | `engine_version` differs | Per V6 |
| **M — No changes** | Two versions with identical findings and sections | "Nothing changed between v2 and v3. Same findings, same recommendation, same open questions. The criteria hash and the evidence are both unchanged — this re-run reproduced its predecessor exactly." Framed as **reproducibility confirmed**, not as a wasted run |
| **N — Only §11 changed** | Answers recorded, no finding flipped | "6 questions were answered and none of them changed a finding. The answers are recorded in §11 and travel with the memo, but nothing in the assessment moved." Prevents the reading that answering was pointless — it narrowed the unknown without moving the score |
| **O — Persistent unevaluable** | Same criteria `unevaluated` across all versions | The footer described in §3.1, always visible in chain mode |
| **P — Long chain** | >8 versions | Collapses the middle: v1, v2, … `[12 versions hidden]` … v14, v15. Endpoints always shown. First and current are the two an analyst reaches for |
| **Q — Version exported / circulated** | An export exists for a version | Node badge: `Exported to IC 2026-07-25 by Sharva Jethwa`. **Critical when that version has since been superseded** — the IC is holding a document the platform no longer agrees with, and that should be visible here: "⚠ v2 was circulated to the IC on 25 Jul. v3 changed the recommendation to PURSUE." |
| **R — Artifact directory missing** | Files gone from disk | Per V7. The database copy renders; the download is disabled with the reason. Filesystems are hostile (overview §6.6) and this is that risk surfacing |
| **S — Memo hash mismatch** | `memo_sha256` ≠ file on disk for a version | Node flagged red: "v2's file on disk does not match the hash recorded when it was generated. Do not circulate. [Report]" Download of that version disabled |
| **T — Section file missing** | A version's output lacks a section file | Per V9. The section row reads "missing from v2 — this is a run failure, not an empty section" |

---

## 9. Open Questions

1. **PRD 08 does not exist.** Every field marked `[TODO]` here — `MemoVersion.version_no`, `triggered_by`, the causal-attribution store — is assumed. The highest-risk assumption is that **causal attribution is computed and persisted at re-run time, not recomputed on demand**. Recomputing at read time means the "because" can change retroactively as evidence is re-indexed, which would undermine the audit claim this screen makes.
2. **Where does attribution live — engine or Phlo?** The standalone principle (PRD 06 §0) says Phlo adds workflow, never comprehension. A causal diff is arguably comprehension. But it is comprehension *about the relationship between two runs*, and the engine only ever sees one run. **Current reading: attribution belongs to Phlo because it is inherently cross-run.** If the engine should emit a machine-readable "what my evidence rests on" per finding to make attribution derivable rather than inferred, that is an engine change worth making, and it would make this screen's claims much stronger. Flagging rather than designing around it.
3. **Is a version a run, or can one run produce several?** This spec assumes 1:1. A re-run with a different criteria set on the same evidence is arguably a *branch*, not a new version, and the chain metaphor breaks if branching is allowed.
4. **Illustrative v2/v3 data.** v2 and v3 throughout are constructed continuations of the real v1. The PPM quotes (p.14 GP commitment, p.31 valuation policy, p.52 concentration cap) are **invented for illustration and marked as such**. Before this spec informs build, run a real PPM through the engine and replace them with real output — the "12 of 49 resolve from a PPM" claim in the Memo Reader depends on the same unverified assumption.
5. **Open questions can go up.** §3.3 notes the PPM opens 6 new questions while closing 12. Confirm this against a real second run — if a larger document reliably raises more than it answers, the "upload a PPM to resolve 12 questions" affordance in the Memo Reader needs different framing.
6. **Cross-vintage vs re-run versions.** The version chain here is re-runs on *one* document set. PRD 01 §8 describes a different timeline: NIIOF-I's deck vs NIIOF-II's deck, years apart. Both are "versions" in casual speech and they are not the same thing. Does this screen handle both, or does cross-vintage comparison belong on Deal Detail / Manager Detail? **Current reading: this screen is re-runs only; cross-vintage is Manager Detail.** Needs confirming — getting it wrong merges two unrelated timelines.
7. **Retention.** Every version keeps a full artifact directory including a copy of the source PDF (5.4 MB for the reference run). Fifteen versions of a deal with a PPM attached is not trivial. Is there a retention policy, and does it conflict with "prior versions stay frozen and downloadable"?
8. **Diff granularity below the section.** Section-level is right for navigation. Within `04-risk-factors.md` the diff is finding-level. But §2 Rationale is a single prose block that gets rewritten wholesale when findings flip — "rewritten" is all this screen can honestly say about it. Is that enough, or does §2 need sentence-level attribution?
