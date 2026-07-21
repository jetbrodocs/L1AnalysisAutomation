---
title: "PRD 06 — Analysis Engine (Standalone CLI)"
status: draft
created: 2026-07-20
updated: 2026-07-21
tags: [prd, cli, engine, product-a, pipeline]
---

# PRD 06 — Analysis Engine (Product A)

> **This is Product A.** A standalone command-line tool with no dependency on Phlo, no database, and no network service. See `00-overview.md` §3 for the two-product boundary.
>
> **This PRD does not follow the ten-section Phlo format** — it describes a CLI, not an event-sourced module. It defines the artifact contract that `02-analysis-pipeline.md` consumes.

---

## 0. Standalone Principle (binding constraint)

> **The engine must remain a complete, useful product with no management system present.** Phlo is one consumer of its output, not a required part of it.

This is a design constraint, not an aspiration. Concretely:

- **The output is a finished deliverable on its own.** An analyst runs the CLI on a laptop, opens `05-memo/00-index.md`, and has the entire answer — recommendation, findings, evidence, open questions — without any server, database, or login.
- **The engine generates everything the memo needs to be read**, including the index. Nothing essential is left for a downstream system to fill in. If a section only makes sense once Phlo renders it, that is a bug in the engine.
- **Phlo adds workflow, never comprehension.** Triage state, version chains, assignment, PDF branding, and the evidence loop are all things Phlo layers *around* a memo that already stands alone.
- **No Phlo identifiers leak into engine artifacts.** No deal IDs, user IDs, or event references. The engine knows about a PDF, a criteria directory, and an output directory. Nothing else.
- **Confidentiality is a feature of this.** An analyst can run a confidential PPM through the engine with no document leaving the machine — which matters directly for Indian AIF material carrying SEBI confidentiality obligations.

**Test for any proposed change**: if it makes the CLI's output incomplete, ambiguous, or unreadable without Phlo, it belongs in Phlo instead.

---

## 1. Purpose and Scope

The Analysis Engine turns a fund marketing document into a scored, evidence-grounded Investment Committee memo. It is the analytical core of the platform; everything else is orchestration around it.

**In scope**: PDF ingestion, document classification, structured extraction, regulatory diligence, criteria evaluation, scoring, memo generation, artifact output, progress reporting.

**Out of scope**: authentication to Phlo, job queueing, user management, storage beyond the output directory, any UI.

### Design posture: the industry's stated objection

The most credible operator in document AI for alternatives — Canoe Intelligence — publicly argues that AI should be confined to *"classification and information extraction — not for making value judgments, investment advice, or strategic recommendations,"* naming unrestricted recommendation-generation as the highest-risk quadrant. Separately, FinanceBench found GPT-4-Turbo with retrieval incorrectly answered or refused **81%** of questions over public filings.

This engine generates something closer to a judgement than an extraction, so that objection lands on it directly. The design answer is not to dismiss it but to constrain the output:

1. **Every finding must cite page-level evidence.** A finding without a source page is a bug, not a low-confidence result.
2. **Findings are criteria hits, not free-form opinions.** The engine reports *"criterion CR-0010 fired, here is the evidence"* — it does not invent concerns outside the admin-authored rule set.
3. **The memo recommends a decision gate, not an investment.** Output is "pursue / hold / pass, and here is what to ask" — mirroring how a real IC memo requests an interview rather than a commitment.
4. **Numeric claims are verified in code**, not by asking a model to check itself.
5. **The engine states what it could not determine.** Absence of evidence is reported as absence, never silently omitted.

The acceptance standard is **correctness, not time saved**. Vendors in this category publish hours-saved and never accuracy; that is the gap this engine is measured against.

---

## 2. Command Interface

```bash
l1 analyze <pdf-path> \
    --criteria <criteria-dir> \
    --out <output-dir> \
    [--stage <stage>] \
    [--resume] \
    [--model <model>] \
    [--max-budget-usd <amount>] \
    [--json]
```

| Flag | Required | Description |
|---|---|---|
| `<pdf-path>` | Yes | Source document. Must be a readable PDF. |
| `--criteria` | Yes | Directory containing the exported criteria set (see §4). |
| `--evidence` | No | Directory of analyst-supplied evidence: additional documents plus `attested-facts.yaml`. Omitted entirely on a first run — an empty directory means "evidence supplied and empty", which is a different statement. See §7. |
| `--out` | Yes | Output directory for artifacts. Created if absent. |
| `--stage` | No | Run a single stage only. For debugging and re-running one step. |
| `--resume` | No | Skip stages whose artifacts already exist and validate. |
| `--model` | No | Model override. Defaults to the configured default. |
| `--max-budget-usd` | No | Hard spend ceiling; aborts cleanly if exceeded. |
| `--json` | No | Emit machine-readable progress on stdout instead of human-readable. |

### Supporting commands

```bash
l1 validate <criteria-dir>      # lint a criteria set without running analysis
l1 inspect <output-dir>         # summarise a completed run
l1 version                      # engine version + model + criteria schema version
```

### Exit codes

| Code | Meaning | Phlo worker action |
|---|---|---|
| 0 | Success — all stages completed, memo written | Emit stage events through `L1_MEMO_GENERATED` |
| 10 | Document rejected — not an analysable type | Emit `DOCUMENT_REJECTED`; do not retry |
| 11 | Vetoed — a veto criterion fired; analysis halted early | Emit `DEAL_SCORED` with veto; memo contains veto reason |
| 20 | Stage failure — recoverable | Emit `ANALYSIS_RUN_FAILED`; retry permitted |
| 21 | Budget exceeded | Emit `ANALYSIS_RUN_FAILED`; do not retry without a higher budget |
| 30 | Invalid input — bad PDF, malformed criteria | Emit `ANALYSIS_RUN_FAILED`; do not retry |
| 31 | Evidence directory malformed — bad manifest, or attested-facts referencing a document not present | Emit `ANALYSIS_RUN_FAILED`; do not retry. Distinct from 30 so the worker can name the cause |
| 143 | Terminated (SIGTERM) | Requeue; run is resumable via `--resume` |

**Exit 11 is deliberately distinct from 0.** A veto is a successful analysis with a terminal finding, not a failure — but the worker must treat it differently from a normal completion.

---

## 3. Output Artifact Contract

This is the interface between Product A and Product B. It must remain stable independently of either side's internals.

```
<output-dir>/
  run.json                  # run metadata, written first, updated last
  status.jsonl              # append-only progress stream
  00-source.pdf             # copy of input, content-addressed
  00-pages/                 # extracted page text, one file per page
      page-001.txt
      ...
  01-classification.json
  02-extraction.json
  03-diligence.json
  04-scoring.json
  05-memo/                  # one file per section — see below
      00-index.md
      01-recommendation.md
      02-rationale.md
      03-fund-facts.md
      04-risk-factors.md
      05-supporting-factors.md
      06-fees-and-terms.md
      07-team.md
      08-track-record.md
      09-contested-findings.md
      10-asks.md
      11-open-questions.md
      12-sources.md
  05-memo.json              # structured form of the whole memo
  errors.jsonl              # any non-fatal warnings
```

### Why the memo is split (decided 2026-07-21)

The memo was originally a single `05-memo.md`. On the reference deck that file reached **58KB**, which forces one reading order on every audience and caps how deep any section can go without bloating the rest.

Splitting to one file per section means:

- **Each audience reads its own part.** An IC member wants §1, §2, §4. An analyst works §9, §10, §11. An ODD reviewer wants §7 and the service-provider content in §3. Nobody scrolls past the others.
- **Depth stops being expensive.** A section can be exhaustive without penalising readers who do not need it. This is the point — the goal is the highest level of detail, not the shortest memo.
- **Diffs get sharp.** Version comparison (PRD 08) diffs `04-risk-factors.md` between v2 and v3, not a 58KB blob. Causal attribution — *which finding flipped and why* — becomes tractable.
- **§11 becomes a working document.** The 49 open questions are the analyst's worklist, not a wall at the bottom of a long file. As its own file it can carry per-question state, evidence links, and resolution history.

`00-index.md` carries the recommendation, the headline counts, and links to every section — so a reader who wants the one-page answer gets it without opening anything else.

**Invariants are unaffected in intent but change in scope**: §6.2 (recommendation agreement) reads `01-recommendation.md`; §6.4 (numeric traceability) sweeps **every** section file, not one; §11 completeness is checked against `11-open-questions.md`. A section file missing from the set is itself a failure — the 12 sections are mandatory, and an absent file must not read as an empty section.

**PDF export** (PRD 08, rendered in Phlo not the CLI) concatenates the sections in numeric order. Section 11 remains non-excludable.

### `run.json`

```json
{
  "run_id": "uuid",
  "engine_version": "0.1.0",
  "schema_version": 2,
  "source": {
    "filename": "Neo Infra Income Opportunities Fund-II Feb'26.pdf",
    "sha256": "2b176083b2938978a9ab84ba1cc2fc72cad052ded1bcf4893293abd1a4613562",
    "page_count": 52,
    "bytes": 5639481
  },
  "criteria": {
    "set_id": "uuid",
    "set_code": "CS-2026-0001",
    "version": 3,
    "content_hash": "sha256:..."
  },
  "model": "claude-...",
  "started_at": "2026-07-20T22:15:00Z",
  "completed_at": "2026-07-20T22:41:00Z",
  "status": "completed",
  "stages_completed": ["classification", "extraction", "diligence", "scoring", "memo"],
  "cost_usd": 1.42
}
```

`criteria.content_hash` is what makes a score reproducible: it proves which exact rule text the engine saw, independent of what the database says today.

### Run telemetry (added 2026-07-21)

> `run.json` originally recorded only total cost and per-stage duration. That is not enough to diagnose a system whose cost varies **7× on identical input** (§7). Token counts, model identity, and retry accounting are all available from the CLI's result envelope and were being discarded.

Every run records, per stage and in total:

```json
{
  "totals": {
    "wall_clock_s": 525.4,
    "billable_s": 498.1,
    "cost_usd": 2.30,
    "tokens": {
      "input": 22,
      "output": 131715,
      "cache_creation": 254614,
      "cache_read": 447418,
      "total": 833769
    },
    "model_calls": 41,
    "retries": 3,
    "fallbacks_used": 0
  },
  "stages": [
    {
      "stage": "extraction",
      "started_at": "...", "completed_at": "...",
      "wall_clock_s": 123.3,
      "cost_usd": 0.418,
      "tokens": {"input": 180400, "output": 14200, "cache_creation": 41000, "cache_read": 139400, "total": 194600},
      "model": "claude-...",
      "model_calls": 9,
      "attempts": 2,
      "retry_reasons": ["error_max_structured_output_retries"],
      "fallback_used": false,
      "quotes_verified": 45, "quotes_total": 45
    }
  ]
}
```

| Field | Why it earns its place |
|---|---|
| `tokens.{input,output}` | The actual cost driver. Cost alone cannot tell you whether an expensive run was a big document or a retry storm |
| `tokens.{cache_creation,cache_read}` | Cache hits are the largest controllable cost lever. A run with poor cache reuse is a tuning opportunity, invisible in a cost figure |

> **⚠️ `total` sums all four counters, not input+output.** An earlier draft of this section implied `total = input + output`. That is wrong against the live API: **`input_tokens` excludes the cached prefix.** Measured on a real classification call, the envelope read `input_tokens: 4` against `cache_creation_input_tokens: 59615` — so input+output would have reported 1,927 tokens for a call that actually moved 102,092, a ~53× understatement. Every cache-efficiency figure derived from it would have been wrong in the same direction. The example block above is real output from the reference run, not a constructed illustration.
>
> Related implementation note: **the resolved model id is not a top-level field** in the CLI's result envelope — it is a *key* of `modelUsage`. Verified against a live envelope and pinned by a test, because it is the kind of thing that silently reverts to `"default"` on a refactor.
| `model` **per stage** | Currently `"default"`, which is unreproducible. A run cannot be reproduced or compared without knowing which model served each stage |
| `model_calls` | Distinguishes one expensive call from many cheap ones — different problems, different fixes |
| `attempts` / `retry_reasons` | §7 documents ~2-in-8 structured-output failures. Without per-stage retry counts, that rate cannot be tracked as it changes |
| `fallback_used` | Text-mode fallback produces lower-confidence output. It must be visible in the run record, not just in logs |
| `wall_clock_s` vs `billable_s` | Separates model time from local work (PDF extraction, verification, I/O). Tells you whether a slow run was the model or the machine |
| `quotes_verified` / `quotes_total` | The grounding metric. Tracked per run so degradation is detectable across a corpus, not just noticed once |

**Also added to the run header** — reproducibility fields that were missing:

| Field | Purpose |
|---|---|
| `engine_git_sha` | Which build produced this. `engine_version` alone is too coarse |
| `criteria.version` resolution | Already present; when null, `run.json` states **`"criteria_status": "DRAFT"`** explicitly rather than leaving null to be interpreted |
| `evidence` block | For re-runs: attestation count, verification outcomes (`confirmed` / `contradicted` / `unreachable`), evidence document hashes |
| `environment.egress_country` | Best-effort. Recorded because "where did this run from" is a cheap thing to capture and an expensive thing to reconstruct later. **Not** because any source is known to be geo-fenced — the SEBI geo-fence that originally justified this field did not exist (overview §8a, corrected 2026-07-21). Had this field been populated and read at the time, it would have shown `IN` and killed the misdiagnosis on the spot |
| `page_extraction_method` | `text_layer` / `ocr` / `mixed`. Governs how much extraction output can be trusted |

**Standalone consequence** (§0): all of this lands in `run.json` on disk, so a CLI-only user gets the same telemetry. `l1 inspect <output-dir>` renders it as a human-readable summary. Phlo reads the same file into projections for cross-run reporting; it does not compute anything the CLI cannot.

**What Phlo gets for free from this**: cost-per-deal reporting, cache-efficiency trends, retry-rate monitoring as an early warning of model or API degradation, and the ability to answer "why did this deal cost $4 when the median is $2." None of that is possible today.

`[NEEDS REVIEW — should token counts be recorded per model call rather than per stage? Per-call is strictly more informative for tuning prompts, at the cost of a much larger run.json. Per-stage is the right default; a --verbose-telemetry flag could emit per-call detail when someone is actively optimising.]`

### `status.jsonl`

One JSON object per line, appended as the run progresses. This is what the Phlo worker tails to emit stage events in near-real-time rather than only at completion.

```jsonl
{"ts":"...","stage":"classification","event":"started"}
{"ts":"...","stage":"classification","event":"completed","artifact":"01-classification.json","duration_s":12}
{"ts":"...","stage":"extraction","event":"started"}
{"ts":"...","stage":"extraction","event":"progress","detail":"core schema 3/7"}
```

### Stage artifact schemas

Every stage artifact carries a common envelope:

```json
{
  "stage": "classification",
  "schema_version": 2,
  "generated_at": "2026-07-20T22:15:12Z",
  "inputs_hash": "sha256:...",
  "result": { ... },
  "unresolved": [ ... ],
  "citations": [ {"claim": "...", "page": 37, "quote": "..."} ]
}
```

**`unresolved` is mandatory and must not be omitted when empty.** It is the list of things the stage could not determine. A stage that silently drops what it could not find is the failure mode this field exists to prevent.

### `unresolved` entries are structured, not strings (changed 2026-07-21)

Entries were originally free-text strings. That is insufficient: the evidence loop (PRD 07) routes each open question by **kind**, and a downstream consumer cannot reliably derive kind by pattern-matching prose. Deriving UI behaviour from heuristics over English is exactly the kind of implicit contract that breaks silently.

Each entry is therefore an object:

```json
{
  "field_path": "team.key_person_clause",
  "kind": "DOCUMENT_ANSWERABLE",
  "stage_origin": "extraction",
  "account": "Searched all 52 pages for 'key person', 'key man', 'key-man', 'departure', 'suspension of investment period'. No key-person provision is described; the Key Fund Terms table on page 37 does not include one.",
  "typical_source": "ppm",
  "blocker_class": null,
  "unblock_owner": null,
  "criterion_codes": ["CR-0012"]
}
```

| Field | Purpose |
|---|---|
| `field_path` | Stable identifier — what could not be established. Survives rewording of `account`. |
| `kind` | `DOCUMENT_ANSWERABLE` / `ANALYST_ANSWERABLE` / `EXTERNALLY_BLOCKED` — drives routing in PRD 07 |
| `stage_origin` | Which stage could not resolve it |
| `account` | The search account — what was looked for, where, and what was found instead. This is the prose that previously *was* the entry. |
| `typical_source` | For `DOCUMENT_ANSWERABLE`: which document class usually answers it (`ppm`, `audited_accounts`, `ddq`, `side_letter`) |
| `blocker_class` | For `EXTERNALLY_BLOCKED`: `login_required`, `captcha`, `paid_source`. (`geo_fence` was listed here until 2026-07-21 on the strength of the SEBI misdiagnosis; no source in the register set is geo-fenced, and the value is not emitted — see overview §8a) |
| `unblock_owner` | For `EXTERNALLY_BLOCKED`: who can resolve it — `infrastructure`, `procurement`, `manual_analyst_check` |
| `criterion_codes` | Which criteria this gap affected, if any |

**Classification rule, safety-first ordering**: a check that could not be *performed* is `EXTERNALLY_BLOCKED`, regardless of whether a document might also contain the answer. When uncertain between blocked and answerable, **choose blocked** — inviting an analyst to answer an unanswerable question wastes their time and erodes trust in every other prompt; the reverse merely under-prompts.

**Standalone consequence** (§0): `11-open-questions.md` groups by `kind` with the blocked items clearly separated and their `unblock_owner` named. A CLI-only user gets the same routing information a Phlo user does — as a readable document rather than an interactive one.

**Backwards compatibility**: none. This is a breaking change to the artifact contract, made before any consumer exists. `schema_version` increments.

---

## 4. Criteria Input Format

The criteria directory is produced by Phlo (`CRITERIA_SET_EXPORTED`) or hand-authored by a standalone user. Both must work.

```
<criteria-dir>/
  set.yaml           # set metadata
  criteria.yaml      # the rules
```

```yaml
# set.yaml
set_id: "uuid"
set_code: "CS-2026-0001"
name: "AIF Cat II Credit — House View 2026"
version: 3
asset_class_scope: ["CAT_II"]
schema_version: 1
```

```yaml
# criteria.yaml
criteria:
  - criterion_code: "CR-0010"
    name: "Gross-only return disclosure"
    tier: "RED_FLAG"
    category: "disclosure"
    severity: "HIGH"
    weight: 1.0
    detection_guidance: >
      Target or historical returns are stated on a gross basis with no
      corresponding net-to-investor figure anywhere in the document.
      Check whether fee load, hurdle, and carry are separately disclosed
      such that net could be derived.
    evidence_requirement: >
      Quote the page and text stating gross returns, and confirm no net
      figure appears elsewhere.
    rationale: >
      Gross returns overstate what an investor receives.
    remediation_prompt: >
      Request net-to-investor IRR for the predecessor fund and target
      net IRR for this fund, after all fees and carry.
```

`l1 validate` checks: schema conformance, unique codes, `detection_guidance` length ≥ 40 chars, valid tier/severity enums, weight > 0, and warns on criteria whose guidance contains no concrete noun (a heuristic for unusable rules).

---

## 5. Pipeline Stages

Each stage is a separate invocation with an explicit input contract. Stages never share memory; they communicate only through artifacts on disk. This is what makes `--resume` and `--stage` work, and what prevents the context-loss failure described in §6.

### Stage 1 — Classification

**Input**: page text
**Output**: `01-classification.json`

Determines two things that gate everything downstream:

1. **Document type** — is this an analysable marketing document (pitch deck, PPM, tear sheet, fact sheet, fund overview, investor presentation, quarterly report) or not (data room document, financial statement, legal document, unknown)? Non-analysable types exit 10.
2. **AIF category** — SEBI Category I / II / III, open vs close-ended, and manager classification (emerging / established). This selects which criteria set scope applies and which extraction schemas run.

```json
{
  "result": {
    "document_type": "pitch_deck",
    "is_analysable": true,
    "fund_name": "Neo Infra Income Opportunities Fund II",
    "manager_name": "Neo Asset Management Private Limited",
    "aif_category": "CAT_II",
    "aif_category_confidence": "stated",
    "structure": "close_ended",
    "strategy": "infrastructure_credit",
    "sebi_registration": null
  },
  "unresolved": ["sebi_registration — no registration number found in document"]
}
```

`aif_category_confidence` distinguishes `stated` (the document says so explicitly) from `inferred` (deduced from strategy and structure). An inferred category on a gating decision must surface in the memo as a caveat.

### Stage 2 — Extraction

**Input**: page text + classification
**Output**: `02-extraction.json`

Extracts the factual substrate: fund terms, economics, team, track record, portfolio construction, service providers.

Two patterns apply, both driven by observed failure modes:

- **Text-first-then-structure.** Extract relevant passages verbatim, then structure them in a second pass. One-shot structured extraction over slide layouts tends to hallucinate plausible values for fields it cannot find.
- **Extract-then-normalise for numbers.** Capture the number *as written* (`"~ INR 5,000 crores"`), then normalise separately (`5_000_000_0000`, `INR`, `approximate: true`). Normalising during extraction loses the qualifier, and the qualifier is often the finding.

Every extracted field carries `{value, page, quote, confidence}`. A field with no page reference is invalid output.

### Stage 3 — Diligence

**Input**: classification + extraction
**Output**: `03-diligence.json`

Verifies document claims against external sources. For India: SEBI intermediary registers, MCA21 company filings, IFSCA (GIFT City entities only). There is **no single Indian equivalent of EDGAR**, so this stage is a multi-source router, not one lookup.

Deterministic comparisons — not model judgements:

| Check | Method |
|---|---|
| SEBI registration exists and is active | Register lookup by **trust** name — not the manager and not the scheme, which are not registrants. A miss is `unavailable`, never `failed` |
| Registered address matches stated HQ | String comparison, normalised |
| AUM within tolerance of filed figure | Numeric band comparison |
| Named key persons appear in filings | Name matching against director records |
| Regulatory action against manager or sponsor | Enforcement register search |

**This stage degrades gracefully.** If a source is unreachable, the check is recorded as `unavailable` with a reason — never as `passed`. `unavailable` and `passed` must never be conflated.

#### Source reachability, as verified (2026-07-21)

| Source | Status | Note |
|---|---|---|
| **SEBI** AIF register, enforcement orders | ✅ **Queried live** | Server-side-rendered Struts pages. No JS, no CAPTCHA, no headless browser. Requires a **browser `User-Agent`** — the default `curl`/`urllib` UA gets HTTP 530 from Cloudflare, a browser UA gets HTTP 200 |
| **ZaubaCorp** corporate identity | ✅ Working | Needs the full browser header set, not the user-agent alone |
| **MCA** master data | ❌ `login_required` | Login wall plus a canvas CAPTCHA on submit. **Deliberately out of scope** — the engine does not defeat access controls on government systems. Route to a licensed provider (`unblock_owner: procurement`) |
| **IFSCA** directory | ❌ `needs_browser` | Client-rendered; plain HTTP returns an empty table indistinguishable from a legitimate "no match", so it is never reported as one |

Result on the reference case: **3 passed, 4 unavailable** — up from 7/7 unavailable. `CR-0001` and `CR-0002` are genuinely evaluated, and `criteria_blocked_by_unavailable_source` is empty.

> **Corrected 2026-07-21.** This stage was previously documented as unable to reach SEBI at all, on the diagnosis that SEBI was **geo-fenced** and needed an India-hosted runner or VPN egress. **That was wrong.** The reasoning — "TCP connects then dies after the TLS Client Hello, therefore the block is below the HTTP layer, therefore a headless browser cannot help" — was internally coherent and false, and its control was run from the same egress it was trying to test, so it confirmed the egress rather than the hypothesis. The cheap test, changing one header, was never run. Full account in overview §8a.
>
> **The residual SEBI limit is real but different.** SEBI registers the AIF **trust**, not the manager and not the scheme, so searching a fund name returns "no records" for a legitimately registered fund. **Absence can therefore never be an adverse finding** — the strongest outcome from a scheme-name miss is `unavailable`. Verifying registration needs the trust name, which lives in the PPM rather than a marketing deck. That makes it `unblock_owner: manual_analyst_check`. See `03-criteria.md`, the structural-limit block under CR-0001.
>
> **A trap this stage must guard**, found during the fix: a SEBI POST that loses its session token returns **HTTP 200 with a page carrying neither results nor an error** — indistinguishable from an empty result set. The adapter splits parse state into `results` / `empty` / `unparseable`, and **only `empty` may become a negative finding**. A 200 is not evidence that a query ran.

#### Unreachable-source policy (decided)

An unreachable source **never fails the run**. The check is recorded as `unavailable`, the run continues, and the gap surfaces in memo section 11 ("What We Could Not Determine").

This holds **even for veto-tier criteria**. If MCA's master data is behind its login wall and a dependent criterion therefore cannot be evaluated, the engine does not fire the veto and does not fail — it records that the check could not be performed and continues. Rationale: failing the whole run discards sixteen other evaluated criteria because one lookup was blocked, and an analyst is better served by a partial memo with a clearly-marked hole than by no memo at all.

The safety property that makes this acceptable is §6.3 and the `unavailable` ≠ `passed` rule: an unverified registration is never rendered as confirmed anywhere in the output.

Each check therefore has three outcomes, and the artifact must distinguish all three:

| Outcome | Meaning | Memo treatment |
|---|---|---|
| `passed` | Source reached, claim verified | Stated as verified, with source |
| `failed` | Source reached, claim contradicted | Finding fires with evidence |
| `unavailable` | Source not reached | Section 11 open item, with reason |

A veto criterion whose check is `unavailable` is reported as `veto_unevaluated` in `04-scoring.json` — distinct from both `fired` and `not_fired`, so downstream consumers cannot mistake an unperformed check for a clean result.

### Stage 4 — Scoring

**Input**: classification + extraction + diligence + criteria
**Output**: `04-scoring.json`

Evaluates every criterion in the active set. For each:

```json
{
  "criterion_code": "CR-0010",
  "fired": true,
  "confidence": "high",
  "evidence": [
    {"page": 5, "quote": "Gross Returns ~ 18-20% p.a."},
    {"page": 37, "quote": "Expected IRR ~ 18-20% p.a."}
  ],
  "absence_evidence": "No net-to-investor IRR figure located in any of 52 pages.",
  "reasoning": "Returns stated gross in both summary and terms sections...",
  "remediation": "Request net-to-investor IRR for NIIOF-I and target net IRR for NIIOF-II."
}
```

**`absence_evidence`** is required when a criterion fires on the *absence* of something. Asserting "no net figure exists" requires stating what was searched — otherwise the claim is unfalsifiable.

**Dual-pass evaluation.** Each criterion is evaluated twice, independently: a **lenient** pass (does the document plausibly satisfy this?) and a **strict** pass (does it demonstrably satisfy this, with evidence?). Where the two disagree, the disagreement is recorded and the criterion is marked `contested` rather than silently resolved. Contested findings surface in the memo as items needing human judgement — which is the honest output when the evidence genuinely supports both readings.

**Veto handling.** If any veto-tier criterion fires with high confidence, scoring halts, the memo is generated in veto form, and the engine exits 11. Vetoes are asymmetric: they can prevent an investment, never mandate one.

### Stage 5 — Memo

**Input**: **all prior artifacts** + criteria
**Output**: `05-memo/` (one file per section plus `00-index.md` — see §3), `05-memo.json`

The final IC memo. Section structure follows verified allocator practice — the Addepar/Stanford study of 54 institutions found summary (98%), risk factors (95%), fees (90%), team (88%), and portfolio role (85%) as the most common sections, with recommendation stated first.

| # | Section | Source |
|---|---|---|
| 1 | Recommendation | Scoring result + veto status |
| 2 | Rationale | Top findings by severity |
| 3 | Fund Facts | Extraction (zero model calls — direct render) |
| 4 | Risk Factors | Red flags and vetoes, with evidence |
| 5 | Supporting Factors | Green flags, with evidence |
| 6 | Fees and Terms | Extraction |
| 7 | Team | Extraction + diligence |
| 8 | Track Record | Extraction + diligence |
| 9 | Contested Findings | Where lenient and strict passes disagreed |
| 10 | Asks | `remediation_prompt` from every fired criterion |
| 11 | Open Questions (`11-open-questions.md`) | Every `unresolved` entry from every stage, grouped by `kind`, each with its full search account |
| 12 | Sources | Derived from citations — not generated |

**Sections 3, 6, 11, and 12 involve no model generation.** They are direct renders of prior artifacts. This is deliberate: the more of the memo that is mechanical, the less surface there is for fabrication.

**Section 11 is non-negotiable.** A memo that omits what it could not establish presents partial analysis as complete. This section is what makes the output honest enough to put in front of an IC.

As its own file it carries, per question, the full account the engine already produces — what was searched for, where it looked, and what it found instead. That detail exists in the `unresolved` entries of every stage and was compressed when the memo was one file. It is the analyst's worklist: it records what has already been ruled out, so the same search is not repeated by hand.

**Entries are grouped by `kind`**, with `EXTERNALLY_BLOCKED` items separated last and each naming its `unblock_owner`. Blocked questions must not be sent to the manager: the check could not be performed at all, so no answer would resolve them. This is §0 in practice — a CLI-only reader gets the same routing a Phlo user gets, as a readable document rather than an interactive one.

**All twelve sections plus the index are mandatory.** A missing section file is a failure in its own right, asserted before the run is declared successful. This check exists because the split created a failure mode the single file did not have: a dropped section used to be a visibly missing heading, whereas an absent *file* is invisible — the directory looks plausible and every file present is well-formed. An absent file must never read as a section that had nothing to say.

---

## 6. Invariants

Enforced in code, checked at stage boundaries, failing loudly rather than degrading silently.

### 6.1 No stage proceeds on missing input

A documented failure in comparable systems: the memo stage received neither the consolidated extraction nor the scoring result, so it generated from document grounding alone — producing memos whose verdict could contradict the scorecard printed inside them.

**Therefore**: each stage asserts the presence and schema-validity of every declared input before doing any work. A missing input is exit 20, never a null-tolerant continue.

### 6.2 The memo cannot contradict its own scorecard

After memo generation, a deterministic check compares the memo's stated recommendation against the scoring result. Disagreement is a hard failure, not a warning. Since the split, this reads `01-recommendation.md`: the structured verdicts are compared field-to-field, and a companion check asserts that the file a human actually opens renders that same verdict and no other.

### 6.3 Every finding cites evidence

A finding with an empty `evidence` array and no `absence_evidence` is invalid. Checked in code before the artifact is written.

### 6.4 Numeric claims are verified mechanically

Every number appearing in the memo must be traceable to an extraction field. A regex sweep extracts numerics from the memo and matches them against extracted values; unmatched numbers fail the run. Models are not asked to check their own arithmetic.

**The sweep covers every section file, not one.** A fabricated figure in `08-track-record.md` is exactly as dangerous as one in `02-rationale.md`, and the obvious way for this check to decay after the split is to silently narrow to whichever file the code happens to hold. Engine-computed figures that appear in no artifact — the section 12 citation tallies, the index's agreement percentage and run cost — are supplied explicitly to the corpus by the code that prints them, never exempted by a magnitude rule.

### 6.5 Critique is bounded

Self-correction loops have been measured *reducing* accuracy substantially when applied open-endedly. **Therefore the review pass checks only closed questions**: does every finding cite evidence, is every numeric traceable, does the recommendation match the score, is every `unresolved` item carried into section 11. It never asks "is this analysis good."

### 6.6 Content addressing, never filename trust

macOS APFS is case-insensitive and `os.rename` overwrites silently: `Report.pdf` and `report.pdf` are one file. **Therefore** the source PDF is addressed by sha256, stored as `00-source.pdf` inside a run directory named by run ID, and all writes are temp-then-rename within the same filesystem. The input path is never a destination path.

The output directory must not be inside a sync client's watched tree (Dropbox, iCloud, Drive). Sync clients write conflicted copies as new files and can leave dataless placeholders where `stat()` succeeds but reads block. `l1 analyze` warns if it detects a known sync path.

---

## 7. Implementation Approach

### Runtime

Stages are invoked as separate `claude -p` calls. Verified available in Claude Code 2.1.215:

| Flag | Use |
|---|---|
| `--print` | Non-interactive execution |
| `--json-schema <schema>` | Structured output for extraction stages |
| `--output-format json` | Machine-readable result envelope |
| `--append-system-prompt` | Stage-specific instruction |
| `--max-budget-usd` | Per-run spend ceiling |
| `--model` | Model selection |

### Grounding: how citations actually work here

> **CORRECTED 2026-07-20 — this section previously specified an approach that does not exist.**
>
> The original design said "citations vs. structured output are mutually exclusive, therefore the memo stage uses citations." **The Anthropic *citations* feature is an API-level capability and is not exposed by the Claude Code CLI** — verified: `claude --help` contains zero occurrences of "citation". The tradeoff the PRD was designed around never arises at this layer, because one side of it is unavailable.

Grounding is therefore achieved through **schema-enforced citation fields plus mechanical verification**, which is what the implementation does:

1. Every extracted field carries `{value, page, quote, confidence}` as explicit schema properties.
2. After each stage, **every quote is checked against the text of the page it cites.** A quote that does not appear on its cited page fails the run.
3. Structured output is used for **all** stages, including memo generation.

This is stronger than the API citations feature for this use case, because verification is performed by the engine rather than trusted from the model. Observed on the reference case: classification 7/7 quotes matched their cited page; extraction 49/49 matched.

| Stage | Mode | Grounding mechanism |
|---|---|---|
| Classification | Structured output | Schema citation fields + quote-vs-page verification |
| Extraction | Structured output | Schema citation fields + quote-vs-page verification |
| Diligence | Structured output | Source URLs + retrieval timestamps |
| Scoring | Structured output | Evidence array referencing extraction fields |
| Memo | Structured output | Every claim references a prior artifact field; numerics verified per §6.4 |

**Known column-format limitation**: text extracted from table cells laid out in columns may not appear as a contiguous string on the page, so exact quote matching can fail on legitimately-present values.

Verification is performed by `l1/quoteverify.py`, which normalises **both sides** before comparison: NFKC folding, curly→straight punctuation, decorative bullet removal, whitespace-run collapse, case folding. It then attempts a contiguous match, falling back to an in-order column splice.

**Measured on the reference deck** (52-page PowerPoint export):

| Stage | Before normalisation | After |
|---|---|---|
| Classification | 7/8 | **7/7** |
| Extraction | 47/47 | **45/45** |
| Scoring evidence | 56/73 | **68/71** |

The residual ~4% are genuine layout defeats, not fabrications — verified by hand. Example: `"Total team size\n   33 members"` cited to page 27, where every keyword *is* present but interleaved with other column content in the extracted text stream.

**This ceiling is deliberate.** Closing the last few percent would require fuzzy or similarity matching, which would also start accepting quotes that do not appear on the cited page. An unverified-but-real quote is flagged and visible; a silently-accepted fabricated quote is the failure mode the whole grounding design exists to prevent. The verifier is therefore tuned strict, and unverified quotes are **retained with `quote_verified: false`** rather than dropped — the reader sees both the claim and the fact that it could not be mechanically confirmed.

#### The three-tier verdict and its calibration

Whitespace normalisation alone is insufficient. On page 27 the extracted stream reads:

```
Total team size    investing experience of
                   19+ Years                 platforms have joined
33 members                                   the team
```

The characters between `Total team size` and `33 members` are **other columns' words**, not whitespace. So the verifier adds a middle tier — all tokens present, in order, within a bounded gap — and records which tier matched:

| Verdict | Meaning |
|---|---|
| `exact` | Contiguous match after normalisation |
| `layout` | Tokens present and in order, reconstructed across a column splice |
| `unverified` | Not found on the cited page |

A consumer can therefore distinguish a contiguous match from a reconstructed one, rather than being handed a single boolean.

**Calibration — the non-obvious part.** Measuring every quote against its cited page *and all 51 others*:

- genuine splices require gaps up to **~1,137 characters**
- cross-page **false** matches begin at gaps as low as **1**

Gap size alone therefore cannot separate true splices from false ones. What separates them is **token count**: every false match was a short generic phrase ("senior advisor", "tracking gross irr"). Constants are `MIN_TOKENS_FOR_LAYOUT = 6`, `MAX_GAP_CHARS = 1200` — chosen over a 5-token threshold that rescued 3 more quotes at the cost of 1 false match. **Recall is the cheaper thing to give up here.**

Independently re-verified: a 7-token and an 8-token splice both resolve to `layout`; a 5-token variant of the same text correctly stays `unverified`, falling below the threshold by design.

**Note on multi-page quotes**: a quote may legitimately verify against several pages — "Neo Infra Income Opportunities Fund I" appears on pages 1, 12, 13 and 18. The verifier's contract is *"does this quote appear on the page it cites"*, not *"is this quote unique to that page"*. Uniqueness is not a grounding property and must not be treated as one.

Adversarial behaviour confirmed by direct test — all of the following are correctly rejected after normalisation:

| Case | Result |
|---|---|
| Real quote, column-layout newlines | ✅ verifies |
| Fabricated text | ❌ rejected |
| Real text, but cited to the wrong page | ❌ rejected |
| Subtly altered figure (`~21%` → `~91%`) | ❌ rejected |

The last case is the important one: a plausible digit change is exactly how a fabricated figure would otherwise pass.

### Structured output reliability

**Structured output fails intermittently — measured at roughly 2 failures in 8 identical calls.** This is not schema-dependent, prompt-size-dependent, or system-prompt-dependent; all three were bisected and eliminated as causes. Any deployment must budget for it.

**Root cause identified** (from `errors.jsonl`, run `2cf5c874`): the failure surfaces as Claude Code's own result subtype **`error_max_structured_output_retries`**. The CLI has an internal retry loop for structured output which exhausts before returning to the caller. So this is not a random parse error — it is the CLI's structured-output mechanism giving up on these schemas under load. The engine's outer retry is what rescues the run, and it is load-bearing rather than defensive.

**Runtime variance is large and must be planned for.** Observed on identical input, same schema, same machine:

| Run | Classification | Extraction | Notes |
|---|---|---|---|
| A | 66.2s / $0.086 | 253.0s / $1.055 | 2 retries on classification |
| B | 11.5s / $0.047 | 123.3s / $0.418 | clean |
| C | 40.6s / $0.091 | **792.1s / $2.918** | 1 retry each stage |

Extraction varied **6×** in wall-clock and **7×** in cost across runs of the same document. A Phlo worker's per-run timeout and budget ceiling must be set against the worst observed case, not the median, or long runs will be killed mid-stage.

**Observed full-pipeline range, widened 2026-07-21**: ~8 to ~23 minutes at **$2.03 – $6.06**. An earlier draft of this section said "$2–$4", which the clean verification run exceeded at **$5.70 / 17 minutes** — the stated band was narrower than the measured reality, which is the more dangerous direction for a budget ceiling to be wrong in.

| Run | Wall clock | Cost | Note |
|---|---|---|---|
| Reference (early) | ~8 min | $2.03 | fastest observed |
| Post-split | ~16 min | $2.30 | |
| Telemetry verification | ~23 min | $6.06 | slowest observed |
| Clean pre-commit verification | ~17 min | $5.70 | 0 retries, 5 stages |

**Set `--max-budget-usd` and the worker timeout against the top of this range, not the median.** A ceiling at $4 would have killed two of the four runs above mid-stage, and a killed run costs everything spent before the kill.

Mitigation implemented:
- 4 attempts with exponential backoff
- Retries are **not byte-identical** — an identical request can fail identically
- Raw stdout/stderr of each failed attempt logged to `errors.jsonl`
- Text-mode fallback after exhausted retries, **flagged in the artifact** so its use is visible rather than silent

### Attested facts and source verification (added 2026-07-21)

The engine accepts analyst-supplied facts alongside the document, via `--evidence <dir>`:

```
<evidence-dir>/
  manifest.yaml           # what documents are here and what they are
  attested-facts.yaml     # facts the analyst supplied, with sources
  <uploaded documents>    # PPM, side letter, audited accounts, …
```

```yaml
# attested-facts.yaml
attestations:
  - field_path: "economics.gp_commitment"
    value: "2.5% of fund size, in cash"
    value_normalised: 2.5
    unit: "PERCENT"
    source_kind: "ATTACHED_DOCUMENT"     # ATTACHED_DOCUMENT | PUBLIC_SOURCE | UNVERIFIABLE
    source_document: "neo-ppm-feb26.pdf"
    source_locator: "page 14, Fund Terms table"
    attested_at: "2026-07-22"
```

**The engine verifies every sourced attestation. It does not take the locator on faith.**

| `source_kind` | Verification |
|---|---|
| `ATTACHED_DOCUMENT` | Read the cited page/section of the named document; check the value appears there using the **same quote-verification machinery as the primary document** (§7), including the three-tier `exact` / `layout` / `unverified` verdict |
| `PUBLIC_SOURCE` | Fetch the locator; check the value appears in the retrieved content. Subject to the same reachability limits as stage 3 — an MCA URL fails behind its login wall exactly as the master-data check does |
| `UNVERIFIABLE` | No verification attempted. Recorded and carried into the memo, but **cannot fire a criterion** |

Each attestation gets an outcome the analyst cannot set, written into `04-scoring.json`:

| Outcome | Effect |
|---|---|
| `CONFIRMED` | Value found at the locator. Criterion may fire, labelled *attested, source verified* |
| `CONTRADICTED` | Source reached but says something different. **Criterion does not fire**; surfaced prominently as a finding about the analysis |
| `UNREACHABLE` | Source could not be retrieved. Criterion does not fire; recorded as `unavailable` with a reason — **never conflated with `CONTRADICTED`** |

`CONTRADICTED` is the case that justifies the mechanism: a mistyped figure, a misread table, or a wrong page reference is caught by the engine rather than propagating into an IC memo under the analyst's name.

**Provenance is preserved end to end.** A criterion fired by an attestation is marked `attested` in `04-scoring.json`, never `document_grounded`, and carries the attestation's source and verification outcome. The three levels — document-grounded, attested-and-verified, attested-unverified — remain distinguishable in every downstream artifact.

**Standalone consequence** (§0): a CLI-only user gets verification too. They hand the engine an attested-facts file and the engine checks it. Phlo supplies the form; it does not supply the verification.

New exit code: **31** — evidence directory malformed (bad manifest, attested-facts referencing a document not present). Distinct from 30 so the worker can report it precisely.

### Auth

The engine is **auth-agnostic**. It invokes Claude Code and does not inspect how authentication resolves.

| Context | Auth | Permitted |
|---|---|---|
| Local development and testing | Developer's own subscription | Yes — a person using their own tool |
| Analyst running CLI on own machine | Their own subscription | Yes, same basis |
| Phlo worker, unattended | `ANTHROPIC_API_KEY` | Required |
| Commercial distribution | `ANTHROPIC_API_KEY` | Required |

No code path differs. Only the environment does. `claude --bare` requires an API key and is therefore used only in the worker context.

### Language

Python 3.11+. Rationale: `pdftotext`/`pypdf` for extraction, straightforward JSON/YAML handling, and it matches Phlo's FastAPI stack so the worker can import engine types directly if that later proves useful. No framework — this is a CLI, not a service.

---

## 8. Validation

### Reference case

`00-inbox/Neo Infra Income Opportunities Fund-II Feb'26.pdf` — SEBI Cat II AIF, 52 pages, clean text layer.

**Acceptance criteria** — the run must:

1. Classify as `pitch_deck`, `CAT_II`, `close_ended`, confidence `stated`
2. Extract fund size (~₹5,000 crore), term (7yr), hurdle (10%), carry (without catch-up), investment count (20–22), sectors (roads, renewables), and all five service providers — each with a page reference
3. Fire `CR-0010` (gross-only returns) with page-level evidence **and** `absence_evidence` naming what was searched
4. Fire `CR-0011` (unrealised predecessor) citing NIIOF-I's still-running status
5. Fire `CR-0033` (tier-one service providers, green flag) citing EY/Trilegal/PwC/ICICI/KFintech
6. ~~Fire `CR-0017` (stale document — Feb 2026 vs. July 2026 analysis)~~ — **CORRECTED 2026-07-21: `CR-0017` must NOT fire.** The criterion's threshold is "more than six months"; Feb 2026 → Jul 2026 is five months. This PRD originally asserted the wrong verdict because the arithmetic was never checked. The test pins the *arithmetic* (months elapsed, compared to threshold), not the verdict, so it will not rot when the date crosses the boundary.

   Similarly **`CR-0012` (key person risk) must NOT fire**: the criterion is conjunctive — concentration on one or two individuals *and* no succession evidence. The deck evidences a 33-member team (p.27), so the concentration limb fails even though the key-person-clause limb holds. `CR-0012`'s underlying gap still surfaces via extraction's `key_person_clause` unresolved entry and reaches memo §11.
7. Record `sebi_registration` as unresolved — the deck text contains no registration number
8. Produce a memo whose recommendation does not contradict the scorecard
9. Carry every unresolved item into section 11
10. Contain no numeric not traceable to an extraction field

**A memo that merely restates the deck fails.** The test is whether findings 3, 4, and 7 appear with defensible evidence — those are the things an analyst would have to read 52 pages to notice.

### Regression approach

Deterministic assertions first — schema conformance, citation presence, numeric traceability, recommendation/score agreement. These catch most regressions and cost nothing to run.

LLM-as-judge only for prose quality, and only cross-family: the judge must not be the same model that generated the memo. Published human-human agreement on this class of judgement is ~81%, so a judge scoring near 80% is at parity, not failing.

**No cross-section contradiction detection exists in any framework surveyed.** Given that this is the documented failure mode in comparable systems (§6.1), it is the one custom check worth building: extract every assertion from every memo section, and check for direct contradictions between them.

---

## 9. Open Questions

- ~~**Diligence sources.**~~ **ANSWERED 2026-07-21** — see the reachability table in §5 stage 3. SEBI and ZaubaCorp are machine-accessible over plain HTTP with browser headers; MCA needs a licensed provider; IFSCA needs a headless browser. Stage 3 is genuinely automatable for three of seven checks today.
- **Contested findings.** When lenient and strict passes disagree, the finding is surfaced for human judgement. Is that the right default, or should a tiebreak pass run? Surfacing is more honest; tiebreaking is less work for the analyst.
- **Page-level citation for slide decks.** Text extracted from PowerPoint-derived PDFs loses spatial layout, so a "page 37" citation may point at a slide whose meaning depends on a chart. Is page-level sufficient, or is a rendered slide image needed alongside?
- **Multi-document funds.** When a PPM and a pitch deck both exist for the same fund, does the engine analyse them together or separately? Together is more accurate and materially more complex.
- **Criteria that need external data.** Some plausible criteria ("fees above peer median") require peer data the engine does not have. Out of scope for v1, but the criteria format should not preclude it.
