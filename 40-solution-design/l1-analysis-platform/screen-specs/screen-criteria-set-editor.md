---
title: "Screen Spec — Criteria Set Editor"
status: draft
created: 2026-07-21
updated: 2026-07-21
tags: [screen-spec, criteria, personalisation, immutability, detection-guidance, l1-analysis-platform]
---

# Screen Spec — Criteria Set Editor

**Parent PRD:** `03-criteria.md` (Screen 2 "Criteria Set Detail", Screen 3 "Criterion Form", Screen 5 "Criterion Performance" — combined into one working surface, see §1.1).

> **Screen 2 is the demo centrepiece** (PRD 03 §8). Three requirements are load-bearing: the three tiers are visually distinct with vetoes unmistakable; an ACTIVE set replaces every edit affordance with "Clone to Draft" so immutability is legible rather than a surprise error; and `detection_guidance` shows worked examples inline, because the quality of that field determines the quality of every analysis the set produces.

> **Standalone principle (PRD 06 §0).** This screen is pure workflow — the engine reads a criteria directory and never needs Phlo to author it. A criteria set exported from here must be a plain directory the CLI can consume on a laptop with no server. Nothing on this screen may become necessary to *understand* a rule; the rule's own `detection_guidance`, `evidence_requirement`, and `rationale` carry that, and they travel with the export.

---

## 1. Purpose

Author, review, and version the rules that encode house policy. This is where an institution's judgement becomes machine-readable — and where a mis-authored veto silently kills deal flow, which is why authoring is restricted to Super Admin and every change is an auditable event (PRD 03 §6).

**Reference data:** criteria set `CS-2026-0001` — the set that produced the *Neo Infra Income Opportunities Fund II* run. **17 criteria evaluated**, status DRAFT, `version: null`, content hash `sha256:94ec11dfc26257c989e35e108f83158e194e4f9074b1b0f8e391478b96cae6d3`. On the reference run it fired 4 red flags (CR-0010, CR-0011, CR-0014, CR-0016), 1 green (CR-0033), produced 1 contested (CR-0034), and left 2 vetoes unevaluated (CR-0001, CR-0002).

### 1.1 Why three PRD screens are one spec

PRD 03 lists Set Detail, Criterion Form, and Criterion Performance separately. In use they are one loop: read the set → see a rule's fire rate → decide it is badly worded → rewrite its `detection_guidance` → see the worked examples while doing it. Splitting them across three screens puts a navigation between the diagnosis and the fix. This spec treats the set as the screen, the criterion form as an inline expansion, and fire-rate stats as a column and a panel rather than a separate dashboard. **Criterion Performance as a standalone dashboard (PRD 03 Screen 5) is still worth having for cross-set analysis** and is specced as a variant in §9 state N.

---

## 2. Entry Points

| # | From | Trigger | Context passed in | Conditions |
|---|---|---|---|---|
| 1 | Criteria Sets list (PRD 03 Screen 1) | Click a set row | `set_id` | — |
| 2 | Criteria Sets list | "New Set" | none — creates DRAFT | Super Admin only |
| 3 | Criteria Sets list | "Clone Set" on a row | `clone_from_set_id` | Any status; produces a new DRAFT |
| 4 | Memo Reader finding card | "Open criterion" on CR-0010 | `set_id`, `criterion_id`, scroll target | Opens **read-only** when the set is ACTIVE (§9 state B) |
| 5 | Memo Reader header | Click `CS-2026-0001 (draft)` in the run metadata line | `set_id` | Deep-links to the set that produced the memo, at its exact content hash |
| 6 | Run Detail (PRD 02 Screen 3) | Click the criteria set code or `criteria_content_hash` | `set_id`, `content_hash` | If the set has changed since the run, opens the **historical** version (§9 state M) |
| 7 | Criterion Performance dashboard (PRD 03 Screen 5) | "Open Criterion" | `set_id`, `criterion_id` | — |
| 8 | Criteria Set Comparison (PRD 03 Screen 4) | Click a changed criterion in a diff | `set_id`, `criterion_id` | — |
| 9 | Command palette `⌘K` | Search by `set_code` or name; or by `criterion_code` / criterion name | `set_id` (+ `criterion_id`) | Per PRD 03 §8 palette entities |
| 10 | Deep link | `/criteria-sets/{id}`, `/criteria-sets/{id}/criteria/{criterion_id}` | — | — |
| 11 | Draft-criteria banner in Memo Reader | "Open CS-2026-0001" | `set_id` | The path from "these findings are provisional" to "here is why" |
| 12 | Onboarding / empty platform | "Set up your criteria" | none | First-run only, when no set exists |
| 13 | Activation blocked notification | Click "Fix and retry" | `set_id`, failing validation | — |

---

## 3. UX Layout

Two columns: a **tier-grouped criteria list** on the left, a **detail/edit pane** on the right. The set header spans both and carries the status, which governs every affordance on the screen.

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ ⚠ DRAFT — unversioned. Analyses run against this set are marked provisional.          │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ CS-2026-0001   India Cat-II AIF — House Screen              [DRAFT]                   │
│ Scope: CAT_II · 17 criteria · 3 vetoes · hash 94ec11df… ⧉                             │
│ Created 2026-07-12 by Sharva Jethwa · Last edited 2026-07-20 14:02 · 6 runs used it   │
│                                                                                       │
│ [+ Add criterion]  [Activate set ▸]  [Clone to draft]  [Export for CLI ↓]  [Archive]  │
└──────────────────────────────────────────────────────────────────────────────────────┘
┌───────────────────────────────────────┬──────────────────────────────────────────────┐
│ ⛔ VETO — 3                            │  CR-0010 · Gross-only return disclosure       │
│ ┌───────────────────────────────────┐ │  ● RED FLAG · HIGH · weight 3.0 · disclosure  │
│ │⛔CR-0001 No verifiable SEBI reg.   │ │                                               │
│ │  CRITICAL · w1.0                  │ │  ┌─ FIRE RATE ──────────────────────────────┐ │
│ │  ⚠ 2 runs UNEVALUATED (external)  │ │  │ Fired on 5 of 6 deals evaluated   83%    │ │
│ ├───────────────────────────────────┤ │  │ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░                │ │
│ │⛔CR-0002 Undisclosed reg. action   │ │  │ ✓ Discriminating — no action needed      │ │
│ │  CRITICAL · w1.0                  │ │  └──────────────────────────────────────────┘ │
│ │  ⚠ 2 runs UNEVALUATED (external)  │ │                                               │
│ ├───────────────────────────────────┤ │  DETECTION GUIDANCE            [Edit]         │
│ │⛔CR-0003 No prior track record     │ │  ┌──────────────────────────────────────────┐ │
│ │  CRITICAL · w1.0 · ⚑ NEEDS REVIEW │ │  │ Returns are quoted gross with no          │ │
│ └───────────────────────────────────┘ │  │ corresponding net-to-investor figure      │ │
│                                       │  │ anywhere in the document. Check for       │ │
│ ● RED FLAG — 11                       │  │ "net IRR", "net-to-investor", "post-fee", │ │
│ ┌───────────────────────────────────┐ │  │ "after fees". A document-wide gross       │ │
│ │● CR-0010 Gross-only returns    ◀  │ │  │ convention in the disclaimer counts.      │ │
│ │  HIGH · w3.0 · fired 83%          │ │  └──────────────────────────────────────────┘ │
│ ├───────────────────────────────────┤ │  ✓ 247 chars · specific · names search terms  │
│ │● CR-0011 Track record unrealised  │ │                                               │
│ │  HIGH · w3.0 · fired 67%          │ │  ▸ See 3 worked examples for this field       │
│ ├───────────────────────────────────┤ │                                               │
│ │● CR-0014 Concentration risk       │ │  EVIDENCE REQUIREMENT          [Edit]         │
│ │  HIGH · w3.0 · fired 50%          │ │  A quoted return figure labelled gross, plus  │
│ ├───────────────────────────────────┤ │  a negative search across all pages for net…  │
│ │● CR-0016 Valuation policy undisc. │ │                                               │
│ │  HIGH · w2.0 · fired 67%          │ │  RATIONALE (shown in the memo) [Edit]         │
│ ├───────────────────────────────────┤ │  Gross returns overstate what an investor…    │
│ │● CR-0017 Stale marketing doc      │ │                                               │
│ │  MEDIUM · w1.0 · ⚠ never fired    │ │  REMEDIATION PROMPT (feeds §10 Asks) [Edit]   │
│ └───────────────────────────────────┘ │  Request the net-of-fee IRR for NIIOF-I and…  │
│                                       │                                               │
│ ○ GREEN FLAG — 3                      │  ┌─ WHERE THIS FIRED ───────────────────────┐ │
│ ┌───────────────────────────────────┐ │  │ DL-2026-0007 Neo Infra II  v1  fired  ▸  │ │
│ │○ CR-0033 Tier-one providers       │ │  │ DL-2026-0004 Ashoka Cap    v2  fired  ▸  │ │
│ │  LOW · w1.0 · fired 100% ⚠        │ │  │ DL-2026-0002 Sierra Roads  v1  not     ▸ │ │
│ ├───────────────────────────────────┤ │  └──────────────────────────────────────────┘ │
│ │○ CR-0034 Transparent fees         │ │                                               │
│ │  MEDIUM · w1.0 · ⚠ 3 contested    │ │  [Disable]  [Delete]  [Duplicate]             │
│ └───────────────────────────────────┘ │                                               │
└───────────────────────────────────────┴──────────────────────────────────────────────┘
```

### 3.1 Tier distinction — the vetoes must be unmistakable

Three tiers, three visual languages. Not three colours of the same chip — three shapes:

| Tier | Treatment |
|---|---|
| **VETO** | Own group, always **first**, always expanded, never collapsible. Heavy left border, `⛔` glyph, inverted header band. Each card carries the consequence in words: *"If this fires, the fund is marked VETOED and the memo leads with the reason. Evaluation of other criteria continues but cannot offset it."* The group header states the count against the total: `⛔ VETO — 3 of 17`. |
| **RED FLAG** | Filled dot `●`, standard card, weight shown prominently because weight is what drives the arithmetic (11.0 vs 1.0 on the reference run). |
| **GREEN FLAG** | Hollow dot `○`, lighter card, visually recessive. Green flags are low-weight by design and the UI should not imply parity. |

A **tier-change is treated as a structural edit**, not a field edit: changing a criterion to or from VETO shows a confirmation naming the consequence, and recalculates the parent's `veto_count` (PRD 03 §3).

### 3.2 The `detection_guidance` editor — worked examples inline

This is the field that makes the system customisable without code, and the field most likely to be authored badly. **Worked examples sit beside the input, not behind a help icon.**

```
┌─ DETECTION GUIDANCE ─────────────────────────────────────────────────────────────┐
│ Plain-English instruction to the analysis engine: what to look for.               │
│ ┌──────────────────────────────────────────────────────────────────────────────┐ │
│ │ Returns are quoted gross with no corresponding net-to-investor figure         │ │
│ │ anywhere in the document. Check for "net IRR", "net-to-investor",             │ │
│ │ "post-fee", "after fees". A document-wide gross convention stated in the      │ │
│ │ disclaimer counts as firing this criterion.                                   │ │
│ └──────────────────────────────────────────────────────────────────────────────┘ │
│ 247 characters · minimum 80                                                       │
│                                                                                   │
│ ✓ Names specific search terms      ✓ States what counts as firing                │
│ ✓ Testable against a document      ○ Consider: what does NOT count?              │
│                                                                                   │
│ WORKED EXAMPLES ─────────────────────────────────────────────────────────────────│
│                                                                                   │
│ ✓ USABLE — CR-0010, fired correctly on 5 of 6 deals                              │
│   "Returns are quoted gross with no corresponding net-to-investor figure          │
│    anywhere in the document."                                                     │
│   Why it works: names the exact absence, and the absence is searchable.           │
│   → On the Neo deck this produced: p.52 "all returns are presented on a           │
│     'gross' basis" with a 52-page negative search for "net IRR".                  │
│                                                                                   │
│ ✓ USABLE — CR-0016                                                                │
│   "No description of how unlisted or illiquid assets are valued: no named         │
│    valuer, no methodology, no frequency. Acquisition-price discussion does        │
│    not count."                                                                    │
│   Why it works: the last sentence excludes the near-miss. On the Neo deck the     │
│   engine correctly ignored p.25 "Valuation agreed with Seller".                   │
│                                                                                   │
│ ✗ NOT USABLE                                                                      │
│   "Bad disclosure."                                                               │
│   Why it fails: nothing to search for, no threshold, no way to evidence it.       │
│   A rule like this either never fires or fires on everything.                     │
│                                                                                   │
│ ✗ NOT USABLE                                                                      │
│   "The fund seems risky."                                                         │
│   Why it fails: asks for a judgement, not an observation. The engine's job is     │
│   to find and evidence; the judging is the analyst's.                             │
└──────────────────────────────────────────────────────────────────────────────────┘
```

The checklist beneath the input is **advisory, not blocking** beyond the minimum length (V3). A rule author who knows what they are doing should not be argued with; one who does not should see the shape of a good rule while typing.

### 3.3 Fire-rate panel — both extremes are signals

`criterion_hit_stats` is the feedback loop that makes the set improvable rather than static (PRD 03 §5). **Never-fired and always-fired are both signals a rule needs rewriting**, and the UI says so in those terms:

| Fire rate | Badge | Text shown |
|---|---|---|
| 0% | `⚠ Never fired` (amber) | "This rule has never fired across 6 deals. Either it is worded too narrowly to match anything, or it describes something our deal flow does not contain. Both are worth knowing. Check the guidance names terms that actually appear in documents." |
| 1–20% | `Rare` (neutral) | "Fires rarely. Normal for a rule targeting an uncommon defect." |
| 21–79% | `✓ Discriminating` (green) | "Separates deals — no action needed." |
| 80–99% | `⚠ Fires on almost everything` (amber) | "Fires on 5 of 6 deals. A rule that almost always fires is not discriminating — it is describing the market rather than separating within it. Consider tightening the threshold, or accept that this is a market-wide condition and lower the weight." |
| 100% | `⚠ Always fires` (amber) | "Fired on every deal evaluated. This contributes the same weight to every score and therefore separates nothing. CR-0033 is the live example: every Indian Cat-II deck names EY, Trilegal and a bank custodian." |
| n/a — unevaluable | `⚠ Unevaluable` (grey) | "Could not be evaluated on 2 of 6 runs because an external check was unavailable. This is a rule that depends on a source we cannot reach — see CR-0001 and CR-0002 (SEBI register, geo-fenced). The rule may be correct and still be useless from this network." |
| Contested | `⚠ n contested` (amber) | "Lenient and strict readings disagreed on 3 runs. The guidance is ambiguous enough that two readings of the same words diverge. That ambiguity is fixable here. CR-0034 is the live example." |

**The unevaluable and contested badges are the two most valuable and are specific to this platform.** A criterion that is never evaluable is a rule the institution cannot actually run, and no fire-rate percentage would reveal it.

Sample-size honesty: below 10 evaluations the panel shows the raw fraction, not a percentage, with *"6 deals is not enough to judge a rule. Treat this as directional."*

---

## 4. Data Points Displayed

### 4.1 Set header

| Label | Value / format | Source |
|---|---|---|
| Set code | `CS-2026-0001` | `CriteriaSet.set_code` |
| Name | `India Cat-II AIF — House Screen` | `CriteriaSet.name` |
| Description | Free text | `CriteriaSet.description` |
| Status | `DRAFT` / `ACTIVE` / `ARCHIVED` | `CriteriaSet.status` |
| Version | `—` for the reference set (`version: null`) else `v2` | `CriteriaSet.version` / `run.json → criteria.version` |
| Asset class scope | `CAT_II`; "All categories" when empty | `CriteriaSet.asset_class_scope[]` |
| Criterion count | `17` | `CriteriaSet.criterion_count` |
| Veto count | `3` | `CriteriaSet.veto_count` |
| Content hash | `sha256:94ec11df…` truncated, full on hover, copy-on-click | `run.json → criteria.content_hash` |
| Created by / at | `Sharva Jethwa · 2026-07-12` | `CRITERIA_SET_CREATED` event |
| Last edited | `2026-07-20 14:02` | Latest `CRITERION_UPDATED` |
| Runs using this set | `6 runs` → links to filtered run list | Count over `deal_scores.criteria_set_id` |
| Supersedes | `CS-2025-0004` when set | `CriteriaSet.supersedes_set_id` |
| Activation history | Who activated, when, what it superseded | `CRITERIA_SET_ACTIVATED` events |

### 4.2 Criterion list row

| Label | Value | Source |
|---|---|---|
| Code | `CR-0010` | `Criterion.criterion_code` |
| Name | `Gross-only return disclosure` | `Criterion.name` |
| Tier | `RED_FLAG` — drives the glyph and grouping | `Criterion.tier` |
| Severity | `HIGH` | `Criterion.severity` |
| Weight | `3.0` | `Criterion.weight` |
| Category | `disclosure` | `Criterion.category` |
| Active | Struck through + `disabled` chip when `is_active = false` | `Criterion.is_active` |
| Fire rate | `fired 83%` or `⚠ never fired` | `criterion_hit_stats.fire_rate_pct` |
| Times fired / evaluated | `5 of 6` | `criterion_hit_stats.times_fired`, `deals_evaluated` |
| Unevaluable count | `⚠ 2 runs UNEVALUATED (external)` | Count of `veto_unevaluated` / `unevaluated` occurrences |
| Contested count | `⚠ 3 contested` | Count of runs where this code appears in `result.contested` |
| Review flag | `⚑ NEEDS REVIEW` on CR-0003 | `[TODO: PRD 03 carries NEEDS REVIEW as prose annotations, not a field. Confirm whether this becomes a real `needs_review` boolean or stays in the description.]` |

### 4.3 Criterion detail pane

All list fields, plus the four text fields — `detection_guidance`, `evidence_requirement`, `rationale`, `remediation_prompt` — each with its character count and last-edited attribution, plus the "Where this fired" table (deal code, fund name, run version, fired/not-fired/unevaluated/contested, link to the finding in the Memo Reader).

**"Where this fired" is the highest-value panel on the screen.** A rule author judging a rule needs to see it against real documents, not in the abstract. Clicking a row opens that finding in the Memo Reader with its evidence — the loop from "is this rule any good?" to "here is what it actually did to the Neo deck" is two clicks.

---

## 5. CTAs

### 5.1 Set-level

| CTA | Behaviour | Availability |
|---|---|---|
| **+ Add criterion** | Expands a blank criterion form in the right pane | DRAFT only |
| **Activate set** | Opens the activation dialog (§5.3). Emits `CRITERIA_SET_ACTIVATED`, assigns the version number, makes the set immutable | DRAFT only, validations V6–V9 |
| **Clone to draft** | Creates a new DRAFT copying every criterion; navigates to it. **On an ACTIVE set this is the only mutating action on the screen** | Always |
| **Export for CLI** | Downloads the criteria directory the engine consumes — plain files, no Phlo identifiers (PRD 06 §0). This is the standalone principle made concrete: an analyst takes this to a laptop and runs a confidential PPM with nothing leaving the machine | Any status |
| **Archive** | Emits `CRITERIA_SET_ARCHIVED`. Blocked while the set is the only ACTIVE set in its scope | ACTIVE / DRAFT |
| **Compare with…** | Opens Criteria Set Comparison (PRD 03 Screen 4) against a chosen set | Always |
| **Copy hash** | Copies the full `content_hash` — the artifact that makes the reproducibility claim checkable | Always |
| **View activation history** | Panel of `CRITERIA_SET_*` events with actor and timestamp | Always |

### 5.2 Criterion-level

| CTA | Behaviour | Availability |
|---|---|---|
| **Edit** (per field) | Inline edit; saves on blur or `⌘↵`. Emits `CRITERION_UPDATED` | DRAFT only |
| **Save & add another** | Saves and opens a blank form, retaining tier and category | DRAFT only |
| **Disable** | Sets `is_active = false`. Rule stays in the set and in history but is not evaluated. Preferred over Delete for anything that has ever fired | DRAFT only |
| **Delete** | Hard delete. Blocked with an explanation when the criterion has findings against it (V10) | DRAFT only, no findings |
| **Duplicate** | Copies into a new criterion in the same set, name suffixed `(copy)` | DRAFT only |
| **Change tier** | Confirmation naming the consequence; recalculates `veto_count` | DRAFT only |
| **See worked examples** | Expands the examples panel (§3.2) | Always, including read-only |
| **Open finding** (from "Where this fired") | Opens the Memo Reader at that finding | Always |
| **Test against a document** | `[TODO: PRD 03 does not specify a single-criterion dry-run. This is the most requested affordance for rule authoring — "does this rule fire on the Neo deck?" — but it implies the engine can evaluate one criterion in isolation, which PRD 06 does not currently expose. Flag to engine owner rather than design around it.]` | — |

### 5.3 Activation dialog

Activation is the moment a set stops being provisional. The dialog states what changes:

```
Activate CS-2026-0001 as v1?

  • The set becomes IMMUTABLE. No criterion can be added, edited, or removed.
    To change it later, clone to a new draft and activate that.
  • Analyses run against it stop carrying the "draft criteria set" banner.
  • Content hash 94ec11df… is frozen and recorded on every run that uses it.

  ⚠ CS-2025-0004 is currently ACTIVE for CAT_II scope.
    Activating this set will supersede it.        [supersedes_set_id set]

  ⚠ 2 criteria have never been evaluable on this network:
    CR-0001, CR-0002 depend on the SEBI register, which is geo-fenced from
    this egress. They will be reported UNEVALUATED on every run until that
    changes. Activate anyway?

  ⚠ CR-0003 is flagged NEEDS REVIEW (veto for no prior track record —
    institutions that back emerging managers would find this wrong).

  [Activate as v1]   [Cancel]
```

Surfacing the unevaluable vetoes **at activation** is the point. An institution activating a set with two vetoes it can never evaluate should know before, not after six runs report HOLD with a caveat.

---

## 6. Validations

| # | Rule | Message |
|---|---|---|
| V1 | Criterion `name` required, 5–120 chars | "Name this rule." |
| V2 | `tier` ∈ `GREEN_FLAG` / `RED_FLAG` / `VETO` | — (select) |
| V3 | **`detection_guidance` required, minimum 80 characters** (PRD 03 §2 requires a minimum length) | "Too short to be actionable. The engine needs to know what to look for — name the terms, and say what counts as firing. See the worked examples." |
| V4 | `evidence_requirement` required, min 40 chars | "What must be found for this to fire? This is what forces grounding." |
| V5 | `severity` ∈ `LOW` / `MEDIUM` / `HIGH` / `CRITICAL`; `weight` numeric > 0, ≤ 10 | "Weight must be between 0 and 10." |
| V6 | Set must have ≥1 active criterion to activate | "A set with no active criteria would evaluate nothing." |
| V7 | Overlapping ACTIVE set in the same scope must be superseded | "CS-2025-0004 is active for CAT_II. Activating this set will supersede it. Confirm." |
| V8 | All criteria must pass V1–V5 to activate | "3 criteria are incomplete: CR-0041, CR-0042, CR-0043. Fix before activating." |
| V9 | Activation requires a version number, auto-assigned, not editable | — |
| V10 | Delete blocked when findings exist | "CR-0010 has fired on 5 deals. Deleting it would orphan those findings. Disable it instead — it stays in the set, stops being evaluated, and the history survives." |
| V11 | Any edit on an ACTIVE set | Not an error message — **the affordance does not exist** (§9 state B). Immutability is legible, never a surprise |
| V12 | Duplicate `criterion_code` within a set | — (codes are generated) |
| V13 | Two criteria with near-identical `detection_guidance` | Advisory: "This is close to CR-0016's guidance. Two rules matching the same thing double-count its weight. Review?" `[TODO: similarity threshold undefined.]` |
| V14 | VETO tier with `weight` < 1.0 | Advisory: "Weight has no effect on a veto — a veto terminates evaluation regardless of weight. Set it to 1.0 to avoid implying otherwise." |
| V15 | `remediation_prompt` empty on a rule that can fire | Advisory: "Without this, §10 Asks has nothing to say when this fires." |

---

## 7. Conditional States

| State | Trigger | What the user sees |
|---|---|---|
| **A — Draft set** | `status = DRAFT` | Amber header banner: "DRAFT — unversioned. Analyses run against this set are marked provisional." All edit affordances live. `[Activate set]` prominent. This is the state of the reference set `CS-2026-0001`, and the reason every memo it produced carries the draft banner |
| **B — Active set (immutable)** | `status = ACTIVE` | **Every edit affordance is replaced, not disabled.** No greyed buttons, no inputs that reject input. Fields render as text. A single primary action: `[Clone to draft]`. A one-line explanation sits under the header: *"CS-2026-0001 v1 is active and immutable. Analyses cite it by hash, so its rules cannot change under them. To revise, clone to a draft."* **Immutability is legible rather than a surprise error** (PRD 03 §8) |
| **C — Archived set** | `status = ARCHIVED` | Read-only, greyscale header, banner: "Archived 2026-06-01 by Sharva Jethwa. Superseded by CS-2026-0002 v2. Runs that used it remain valid and reproducible." `[Clone to draft]` remains available |
| **D — Empty set** | DRAFT, 0 criteria | Not a bare empty state. Three routes: `[Start from the India Cat-II starter set (17 rules)]`, `[Clone an existing set]`, `[Add a criterion from scratch]`. Copy: "A criteria set is your house policy in machine-readable form. Most institutions start from the starter set and edit down." |
| **E — Empty platform** | No sets exist at all | First-run guidance leading to the starter set |
| **F — Loading** | Fetch in flight | List skeletons grouped by tier so the tier structure is visible before content lands |
| **G — Error** | API failure | "Couldn't load CS-2026-0001." Error code, `[Retry]` |
| **H — Restricted (Analyst)** | Role = Analyst | Full read access — an analyst must be able to see the rules that produced a finding, which is the attribution claim (PRD 03 §6 grants Analyst read). **No authoring affordances at all**, including no `[Clone to draft]`. Banner: "Criteria are authored by the Head of Research. You're seeing the rules that scored your deals." |
| **I — Restricted (IC Member)** | Role = IC Member | Read-only, same as H |
| **J — Unsaved changes** | Dirty form, navigation attempted | "You have unsaved changes to CR-0010." `[Save] [Discard] [Cancel]` |
| **K — Concurrent edit** | Another Super Admin edited this criterion since load | "Priya changed this criterion 4 minutes ago. Your copy is stale." Shows both versions side by side. `[Take theirs] [Keep mine] [Merge manually]` |
| **L — Activation blocked** | V6/V7/V8 fails | `[Activate set]` opens a blocking panel listing exactly what fails, each item linking to the criterion. Never a toast |
| **M — Historical view** | Entered from a run whose `content_hash` ≠ the set's current hash | Blue banner: "You're seeing CS-2026-0001 as it was when run `fd33c73e` used it on 2026-07-20 (hash `94ec11df…`). The set has changed 3 times since. [View current] [Compare]" Fully read-only |
| **N — Performance view** | Toggle "Performance" or entered from PRD 03 Screen 5 | The list re-sorts by fire rate and shows the diagnostic columns for every criterion at once: fire rate, unevaluable count, contested count, average confidence. Never-fired and always-fired rules pinned to the top as the two actionable groups. Cross-set filter available |
| **O — No fire-rate data** | Set never used in a run | Fire-rate column reads "Not yet used". Panel: "No analysis has run against this set. Fire rates appear after the first run." Never renders 0% — 0% and "no data" are different claims and conflating them would libel a working rule |
| **P — Small sample** | `deals_evaluated` < 10 | Raw fractions instead of percentages, with the directional caveat (§3.3) |
| **Q — Set in use by a running analysis** | A run is in flight citing this set | Info strip: "An analysis is running against this set (DL-2026-0009, started 6m ago, scoring stage). Edits won't affect it — the run holds hash `94ec11df…`." Reassures rather than blocks; hash-pinning is exactly what makes editing safe |
| **R — Analysis running (from this screen)** | Activation triggers re-runs `[TODO: does activating a set offer to re-run affected deals? PRD 03 does not say. High-value if yes.]` | Per-stage progress per queued run, not a spinner. Runs take 8–16 min |
| **S — Contested-heavy rule** | A criterion has contested outcomes on ≥2 runs | Inline callout on the criterion: "Lenient and strict readings disagreed on 3 of 6 runs. That ambiguity lives in this guidance text and is fixable here. [See the disagreements]" linking to each contested finding |
| **T — Unevaluable rule** | A criterion was `unevaluated` on ≥1 run | Callout: "CR-0001 could not be evaluated on 2 runs — the SEBI intermediary register is unreachable from this network (geo-fence/WAF, verified). The rule is not wrong; the source is unavailable. [Why]" |

---

## 8. Open Questions

1. **Single-criterion dry-run.** The natural authoring loop is "write the rule, test it on the Neo deck, adjust". PRD 06 does not expose per-criterion evaluation. Without it, rule authoring is write-and-hope with a 8–16 minute feedback loop and a $2.30 cost per attempt. **This is the single biggest gap in the authoring experience** and it is an engine question, not a UI one.
2. **`NEEDS REVIEW` as a field.** PRD 03 carries several of these as prose (CR-0003's veto-vs-red-flag question). Prose annotations do not survive into the UI or the export. Should this be a real field?
3. **Starter-set provenance.** State D offers "the India Cat-II starter set (17 rules)". Is `CS-2026-0001` itself that starter set, or is it a deployment's edit of one? The distinction matters for what a new institution sees on day one.
4. **Re-running on activation.** When a set activates, do deals scored under the draft get re-run? Doing it silently is wrong; not offering it means memos cite a set that no longer represents house policy.
5. **Criterion-level scope.** PRD 03 §10 raises conditional applicability (a rule that applies only to Cat II, or only above a size threshold). Currently scope is set-level. If criterion-level scope arrives, this screen needs a scope editor per rule and the tier grouping may not be the right primary grouping.
6. **Weight and severity overlap.** Both `severity` and `weight` influence contribution. On the reference run CR-0010 is HIGH/3.0 and CR-0033 is LOW/1.0 — severity and weight move together in every example. If they always co-vary, one of them is redundant and the form is asking for the same thing twice.
7. **Fire-rate denominators across sets.** If a criterion is cloned into three sets, is its fire rate per-set or per-criterion-lineage? Per-set is correct but produces thin samples; lineage is richer but conflates rules that have since diverged.
8. **Export format.** "Export for CLI" must produce exactly what the engine consumes. `[TODO: PRD 06 §3 describes a criteria directory but this spec has not verified the file layout. Confirm before build.]`
