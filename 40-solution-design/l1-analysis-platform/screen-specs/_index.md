---
title: "Screen Specs — Index"
status: draft
created: 2026-07-21
updated: 2026-07-21
tags: [screen-spec, index, l1-analysis-platform]
---

# Screen Specs — L1 Analysis Platform

Per-screen UX detail for the L1 Analysis Platform, positioned as an **analyst co-pilot for L1 research**. Each spec covers entry points, UX layout, data displayed, CTAs, validations, and conditional states.

**Folder structure note.** The `screen-specs` skill describes a `prd-NN-<name>/prd.md` + `screen-specs/` pairing. This platform is one system with eight module PRDs as flat files in the parent folder, so a **single shared `screen-specs/` folder serves all modules**. Every spec names its parent PRD in the header.

**Grounding.** Every spec uses real data from the reference run `fd33c73e-2db5-4389-855a-e597a476889c` (`/tmp/l1-v3/`): *Neo Infra Income Opportunities Fund II*, Neo Asset Management Private Limited, 52-page February 2026 deck, ~INR 5,000 crore, 18–20% gross IRR, criteria set `CS-2026-0001` (DRAFT, unversioned), **HOLD**, red weight 11.0 vs green 1.0, 4 red flags fired, 1 green, 1 contested, 2 vetoes unevaluated, **49 open questions**, 104 citations of which 101 verified. Illustrative data (v2/v3 continuations, PPM quotes) is marked as such wherever it appears.

---

## Written specs

| # | Spec | Purpose | Parent PRD | Primary role |
|---|---|---|---|---|
| 1 | [`screen-memo-reader.md`](screen-memo-reader.md) | **The centrepiece.** The 12-section memo with findings and evidence inline, and open questions answered in place — routed by question kind | `05-memo.md` (Screen 2) + `07-evidence-loop.md` | Analyst |
| 2 | [`screen-criteria-set-editor.md`](screen-criteria-set-editor.md) | Author and version the rules that encode house policy; tier distinction, immutability, `detection_guidance` quality, fire-rate diagnostics | `03-criteria.md` (Screens 2, 3, 5) | Super Admin |
| 3 | [`screen-version-history.md`](screen-version-history.md) | The v1→v2→v3 chain and the **causal** section-level diff — what changed and why | `08-version-history.md` *(not yet written)* | Analyst |
| 4 | [`screen-deal-list.md`](screen-deal-list.md) | Triage across the book — allocator stages, ODD as a parallel track with an asymmetric veto | `04-triage.md` (Screens 1, 2, 7) | Analyst |
| 5 | [`screen-deal-detail.md`](screen-deal-detail.md) | The deal hub — documents, analysis versions, triage state, ODD, notes, re-up history | `04-triage.md` (Screen 3) | All roles |
| 6 | [`screen-upload.md`](screen-upload.md) | Intake — sha256 dedup, and the match proposal that keeps the cross-vintage timeline alive | `01-intake.md` (Screens 1, 3) | Analyst |

---

## Screens not yet specced

Named in the PRDs, not yet written. Roughly in build-value order.

| Screen | One-line purpose | Parent PRD | Primary role |
|---|---|---|---|
| Run Progress (live) | Per-stage progress for an 8–16 minute run — the async architecture's benefit made visible | `02-analysis-pipeline.md` (4) | Analyst |
| Evidence Drill-Down | A finding's full evidence with the source page alongside | `05-memo.md` (3) | Analyst, IC Member |
| Source Document Viewer | The deck opened to a cited page, quote highlighted, **page image not extracted text** | `05-memo.md` (4) | Analyst, IC Member |
| Triage Decision | Record pursue / hold / pass with rationale and cited findings | `04-triage.md` (4) | Analyst, IC Member |
| Promotion Queue | Classified documents awaiting a promote/reject decision | `01-intake.md` (2) | Analyst |
| ODD Queue | The ODD function's own workspace — no pipeline chrome | `04-triage.md` (10) | **ODD Reviewer** |
| ODD Review | Record rating, findings by category, remediation | `04-triage.md` (11) | **ODD Reviewer** |
| ODD Review Detail | One review: rating, findings, remediation, expiry | `04-triage.md` (12) | ODD Reviewer, Analyst |
| Memo Comparison | Two runs on one Deal side by side | `05-memo.md` (8) | Analyst, IC Member |
| Override Finding | Record a disagreement with a finding | `05-memo.md` (5) | Analyst |
| Export Memo | Type, format, template, inclusions — **§11 non-excludable** | `05-memo.md` (6) | Analyst, IC Member |
| Memos list | All memos with recommendation, review status, flagged count | `05-memo.md` (1) | All |
| Passed Deals | Everything declined, with reason — the counterfactual | `04-triage.md` (5) | Analyst, IC Member |
| Manager Detail | One manager: every fund, every decision, ODD history | `04-triage.md` (9) | Analyst |
| Managers list | Every manager with deal count, commitments, passes | `04-triage.md` (8) | Analyst |
| Criteria Sets list | Browse all sets with status/version/scope | `03-criteria.md` (1) | Super Admin |
| Criteria Set Comparison | Side-by-side diff of two sets | `03-criteria.md` (4) | Super Admin |
| Documents list | All documents with status/type/source filters | `01-intake.md` (4) | Analyst |
| Document Detail | One document: metadata, **prominent sha256**, classification, duplicates | `01-intake.md` (5) | Analyst |
| Analysis Runs list | All runs with status/stage/deal filters | `02-analysis-pipeline.md` (2) | Analyst |
| Run Detail | Stage timeline, criteria hash, findings, artifacts, cost | `02-analysis-pipeline.md` (3) | Analyst |
| Findings list | All findings across runs, filterable by criterion and state | `02-analysis-pipeline.md` (5) | Analyst, IC Member |
| Finding Detail | Evidence, absence evidence, lenient vs strict verdicts | `02-analysis-pipeline.md` (6) | Analyst |
| Failed Runs | Failures with code, stage, attempts, **stderr visible without a click** | `02-analysis-pipeline.md` (7) | Analyst |
| Funnel Report | Stage conversion, cycle time, pass-reason mix | `04-triage.md` (6) | Super Admin, IC Member |
| Stalled Deals | Deals over the age threshold in their stage | `04-triage.md` (13) | Super Admin |
| Export History | Every export: who, when, what was included | `05-memo.md` (7) | Analyst |
| Overrides list | All overrides grouped by criterion and reason | `05-memo.md` (9) | Super Admin |
| Intake Dashboard | Today's arrivals, queue depth, rejection reasons | `01-intake.md` (8) | Analyst |
| Pipeline Dashboard | Queue depth, running runs, throughput, worker health | `02-analysis-pipeline.md` (1) | Super Admin |
| Workers / Worker Detail | Worker status, current run, heartbeat, counters | `02-analysis-pipeline.md` (8, 9) | Super Admin |
| Upload Sources / Detail | Browser and API sources with volume and usable-rate | `01-intake.md` (9, 10) | Super Admin |
| Criterion Performance | Fire rates; never-fired and always-fired detection | `03-criteria.md` (5) | Super Admin |
| Memo Templates / Editor | House export templates — **v2, out of scope for v1** | `05-memo.md` (10, 11) | Super Admin |
| Pipeline / Triage Settings | Thresholds, budgets, gate override policy | `02` (10), `04` (14) | Super Admin |

---

## Conflicts and reconciliation notes

Recorded rather than silently resolved. Each needs a decision from the PRD owner.

### C1 — Memo reader assumes a single scrolling document (**needs reconciliation**)

`screen-memo-reader.md` was written before PRD 06 §3 split the memo into twelve section files (`05-memo/00-index.md` … `12-sources.md`). Two places assume one document:

- **§3.3** — "Sections render in order 1→12 in a **single scroll**."
- **§2 entry 11** — deep links as **anchors** within one document (`/memos/{id}#section-11`).

Neither is wrong as a *rendering* choice — Phlo can still present twelve files as one scroll, and the standalone principle is satisfied either way because the engine's output stands alone regardless of how Phlo renders it. But the section-file split makes per-section routes (`/memos/{id}/sections/11-open-questions`) the more natural model, and it is what the version-history spec assumes when it diffs a section. **Left unedited per the coordinator's instruction.** The substantive question for the PRD owner: does the reader stay one scroll with anchors, or become per-section routes? §11's "never collapsed" requirement is easier to honour in a single scroll; per-section routes make deep links and diffs cleaner.

### C2 — PRDs 07 and 08 do not exist

Verified absent 2026-07-21. `screen-memo-reader.md` (question-kind routing, attestation) and `screen-version-history.md` (the whole spec) derive from `00-overview.md` §1, which already fixes the three-kind taxonomy and the attested/grounded distinction. Highest-risk assumptions:

- **`unresolved[].kind`** — the reference artifact `04-scoring.json` carries `unresolved` as **flat strings with no kind field**. The three-kind routing that the memo reader's design rests on is currently derivable only by heuristics over item text, which is not good enough to route UI on. **The engine must emit the kind.**
- **`MemoVersion.triggered_by`** and the causal-attribution store — assumed, and assumed to be computed and persisted at re-run time rather than recomputed on read.
- Whether an analyst attestation is an **input the engine reasons over** or only an annotation displayed alongside. These are materially different products; the specs assume the former.

### C3 — Causal attribution may belong to the engine

`screen-version-history.md` computes "CR-0030 flipped because the PPM p.14 disclosed 2.5%" in Phlo, by comparing two runs. The standalone principle says Phlo adds workflow, never comprehension — and a causal claim is arguably comprehension. The counter-argument, and the spec's current position: attribution is inherently *cross-run*, and the engine only ever sees one run. **But** if the engine emitted a machine-readable "what my evidence rests on" per finding, attribution would become derivable rather than inferred, and the causal claims would be much stronger. Flagged as an engine question.

### C4 — Anchoring bias is settled by default, in the negative

PRD 04 §8 flags as `[NEEDS REVIEW]` whether the memo recommendation should be hidden until an analyst writes their triage rationale. `screen-deal-list.md` shows `HOLD` on every card and `screen-deal-detail.md` shows it in the header — so by the time an analyst opens the triage form they have seen the recommendation many times. **If the anchoring mitigation is wanted, it must start at the list, not the triage form.** This is a genuine conflict between two PRD requirements, not a UI detail.

### C5 — No single-criterion dry-run

`screen-criteria-set-editor.md` §5.2 flags this as the biggest gap in rule authoring. Without it, writing a `detection_guidance` is write-and-hope with an 8–16 minute, ~$2.30 feedback loop. PRD 06 does not expose per-criterion evaluation. An engine question, not a UI one.

### C6 — Cross-vintage comparison is specced nowhere

Two different things are both called "comparison": **re-runs on one document set** (v1→v2→v3, `screen-version-history.md`) and **NIIOF-I's deck vs NIIOF-II's deck** years apart (`screen-deal-detail.md` §3.5 offers the action). The second belongs on Manager Detail or Deal Detail and has no spec. Merging the two timelines would be wrong — they answer different questions.

---

## Cross-cutting requirements

Every spec honours these; listed here so a new spec inherits them.

1. **Analysis runs take 8–16 minutes.** Every screen touching a run shows **per-stage progress, never a spinner** — the five stages with elapsed time and the live detail line from `status.jsonl`. Reference: classification 12.0s, extraction 89.4s, diligence 1.0s, scoring 332.7s, memo 89.6s; total 8m 45s, $2.30.
2. **Three evidence verdicts, shown honestly.** `exact`, `layout`, `unverified`. An `unverified` quote is **retained and displayed**, flagged as not mechanically confirmed, never hidden and never styled as the manager's fault.
3. **Unevaluated is never a pass.** `veto_unevaluated` (CR-0001, CR-0002 on the reference run) renders as neither fired nor clean, with the blocking reason. This is the state most likely to be mis-rendered as a green tick.
4. **Draft criteria sets are announced.** Any analysis produced by an unversioned set carries a prominent, non-dismissible banner, and it survives into every export.
5. **Contested findings are never resolved by the system.** Both lenient and strict readings shown and labelled; no "resolve" affordance anywhere.
6. **§11 is non-excludable** from any export, and never collapsed by default in any view.
7. **Two clicks from an assertion to the words that support it** — finding → evidence drawer → source page image.
8. **ODD is never a stage.** Badge, never a column; asymmetric veto rendered as a one-directional obstacle; ODD's own rating scale never displayed as comparable to an investment score.
9. **Attach beats create.** Any flow that could produce a duplicate Deal defaults to attaching to the existing one, with creation as an explicit correction.
10. **Standalone principle (PRD 06 §0).** Phlo adds workflow, never comprehension. No screen may supply meaning the memo's own section files should carry — if one seems to, that is an engine bug to flag, not a UI problem to design around.

---

## Open questions across the set

Each spec carries its own list. These are the ones that cut across several:

1. **The engine must emit question kind** (C2). The co-pilot's core interaction depends on it and it does not currently exist in the artifact.
2. **"12 of 49 resolve from a PPM"** appears in the memo reader as a headline promise. The count is derived by this spec, not by the engine, and has never been validated against a real PPM run. **Validate before it ships as a promise.**
3. **Attestations: input or annotation?** (C2)
4. **Single-criterion dry-run** (C5).
5. ~~**Indian-egress re-runs.**~~ **CLOSED 2026-07-21 — false premise.** Three specs offered "request a re-run from an Indian IP" for six blocked checks, on the basis that SEBI was geo-fenced. It never was (overview §8a); the CTA has been removed from all three specs and the prototype. No source in the register set needs a specific egress, so PRD 02 does not need egress-tagged workers. IFSCA's browser requirement is a genuine worker-capability question, but that is a headless browser, not a location.
6. **Analyst visibility scope** — whole book or own deals only? Affects the deal list's default and "My Deals" reason for existing.
7. **§11 at scale.** 49 items is readable; a PPM run could produce several hundred. Does §11 need pagination or its own workspace — and does that break the "never collapsed" rule that makes it valuable?
8. **Override vs answer.** Both record human judgement against a finding. Keeping them as separate concepts may be duplication.
9. **Retention.** Every version keeps a full artifact directory including the source PDF (5.4 MB reference). Fifteen versions with a PPM attached is not trivial, and it conflicts with "prior versions stay frozen and downloadable".
10. **Fund-name matching strategy** (`screen-upload.md` §8.1). A missed match produces the duplicate-Deal failure the promotion screen exists to prevent, and it **fails silently**.
