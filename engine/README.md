# L1 Analysis Engine (Product A)

Standalone Python CLI that turns a fund marketing PDF into evidence-grounded,
machine-readable artifacts. Implements PRD 06 (`06-analysis-engine.md` in the
solution-design repo).

---

## ⚠️ Implemented vs. specified — read before integrating

The PRDs describe more than this engine currently does. **A developer building
the Phlo integration against PRD 07 or 08 will hit flags that do not exist yet.**
This table is the boundary.

| Capability | PRD | Status |
|---|---|---|
| `analyze` — 5 stages, 13-file memo | 06 | ✅ **Built and verified** |
| `validate` — criteria set linting | 06 | ✅ Built |
| `inspect` — run summary with telemetry | 06 | ✅ Built |
| `test-criterion` — single-criterion dry run | 06 | ✅ Built (92s / ~$1 vs 23min / ~$6) |
| Structured `unresolved` entries with `kind` | 06 §3 | ✅ Built — safety-first classification enforced in code |
| Run telemetry: tokens, cache, model, retries | 06 §3 | ✅ Built |
| Quote verification, 3-tier exact/layout/unverified | 06 §7 | ✅ Built (~96% on the reference deck) |
| Invariants 6.1 – 6.4 | 06 §6 | ✅ Enforced in code, each with a test that violates it |
| Diligence: SEBI + MCA via ZaubaCorp | 06 §5 | ⚠️ **Partial** — SEBI AIF register + enforcement orders live over HTTP; ZaubaCorp/IFSCA still need a browser; MCA login-walled |
| `--evidence <dir>` flag | 06 §7, 07 §11 | ❌ **Specified, not built** |
| `attested-facts.yaml` ingestion | 07 §2b | ❌ **Specified, not built** |
| Source verification (`CONFIRMED`/`CONTRADICTED`/`UNREACHABLE`) | 07 §2c | ❌ **Specified, not built** |
| Exit code 31 (malformed evidence dir) | 06 §2 | ❌ **Specified, not built** |
| Re-run producing analysis versions | 07, 08 | ❌ Phlo-side concern; engine is stateless per run |

**For the Phlo integration**: everything in PRD 02's worker protocol works today
against the built surface. The evidence loop (PRD 07) needs the `--evidence`
flag before it can be wired end to end.

---

## Portability

**This engine is designed to be lifted into its own repository.** Nothing under
`l1/` reaches outside this directory, and the tests do not either.

To move it: copy `engine/` wherever it belongs and it works unchanged. Verified
by copying to an isolated location with no parent repo — 256 fast tests pass.

The one external dependency is the **reference deck** used by the slow
acceptance tests. It is a 5.4MB third-party document marked *Private &
Confidential* and deliberately does **not** live in git. Resolution order:

1. `L1_REFERENCE_DECK=/path/to/deck.pdf`
2. `tests/fixtures/<deck name>.pdf` (gitignored)
3. `../00-inbox/<deck name>.pdf` — the original monorepo layout

If none resolve, slow tests **skip with guidance** rather than failing with a
confusing `FileNotFoundError`. Fast tests never need it.

**Status: 5 of 5 stages built.** The full pipeline runs end-to-end against the
real Neo deck and produces a 13-file IC memo directory (`05-memo/`: an index plus
one file per section). All six PRD §6 invariants are enforced in code, including
6.2 and 6.4, which previously had nothing to check.

**The memo is split, one file per section (PRD §3, decided 2026-07-21).** The
single `05-memo.md` had reached 58KB, which forced one reading order on every
audience and made depth expensive — an exhaustive section 11 penalised anyone who
only wanted section 1. Split, depth is free, and section 11 now carries the full
search account per open question rather than a compressed bullet. `05-memo.json`
keeps its section bodies unchanged and gains `memo_dir`, `memo_files`,
`unresolved_by_kind` and `index_cost_usd`, so a consumer never has to hardcode
the layout or re-derive a figure the engine already wrote.

Two invariants changed scope but not intent, and one is new:

- **§6.4 sweeps EVERY section file.** A fabricated number in `08-track-record.md`
  is exactly as dangerous as one in `02-rationale.md`. This is the check most
  likely to decay after a split, so the acceptance test injects its fabricated
  number into non-first files (`08`, `04`, `12`) and asserts the failure names
  the file it was injected into — a sweep that only checked the first file would
  pass a naive version of that test.
- **§6.2 reads `01-recommendation.md`**, and a companion check asserts the file a
  human opens renders that verdict and no other.
- **NEW: a missing section file is itself a failure.** All 12 plus the index are
  mandatory, asserted before the run is declared successful. This exists because
  the split created a failure mode the single file did not have: a dropped
  section used to be a visibly missing heading, whereas an absent *file* is
  invisible — the directory looks plausible and every file present is well-formed.
  An absent file must never read as an empty section, so presence *and*
  non-emptiness are both asserted.

**`unresolved` entries are structured objects, not strings (PRD §3, changed
2026-07-21).** Each carries `field_path`, `kind`, `stage_origin`, `account`, and
the routing fields for its kind. `schema_version` is now **2**; there is no
backwards compatibility, and none is needed because no consumer exists yet.

The reason is routing. The evidence loop sends each open question to a different
affordance by kind — `DOCUMENT_ANSWERABLE` (request the document),
`ANALYST_ANSWERABLE` (an analyst settles it), `EXTERNALLY_BLOCKED` (nobody can
answer it until the source is reachable). Deriving that kind by pattern-matching
English prose is not a contract; it is a heuristic that breaks silently and
breaks in the direction of showing the wrong affordance.

**The classification rule is safety-first and enforced in code.**
`enforce_kind_safety` forces an unrecognised kind, and any entry whose account
describes a check that could not be *performed*, to `EXTERNALLY_BLOCKED` —
whatever the model said. It can only ever move an entry toward blocked, never
away. This is the same lesson as `_enforce_blocked_criteria`: **where a safety
property must hold, a prompt is not a mechanism.** The asymmetry that justifies
the tie-break is that inviting an analyst to answer an unanswerable question
wastes their time and erodes trust in every other prompt, whereas
under-prompting merely leaves a question unasked.

`assert_entries_valid` runs inside `write_artifact`, so a malformed entry never
reaches disk — the same placement as §6.3, for the same reason. It specifically
rejects a blocked entry that names a `typical_source`, because that combination
is the exact routing error the contract exists to prevent.

`11-open-questions.md` groups by kind with the blocked items separated last and
their `unblock_owner` named, and `l1 inspect` prints the same routing per entry.
That is the Standalone Principle (§0) in practice: a CLI-only reader gets the
same routing information a Phlo user gets, as a readable document rather than an
interactive one.

**Diligence is partial, and what remains unavailable is recorded with its
cause rather than hidden.** SEBI — previously believed geo-fenced, which was a
misdiagnosis — is now queried live: both the AIF register and the enforcement
order search work over plain HTTP with browser headers. ZaubaCorp and IFSCA
still need a real browser, and MCA is behind a login and a CAPTCHA. See
"Diligence: what can and cannot be checked" below.

### Known limitation: contested findings are not reproducible

**Measured across three full runs on byte-identical inputs: 3, 3, then 0
contested findings.** Everything else held steady — the `hold` recommendation,
the same four red flags, the same green flag, the same two `veto_unevaluated`.
Only the lenient/strict *disagreement* moved.

This matters because contested findings are a headline feature: they are the
engine's claim to honesty about ambiguous evidence. **Read a contested set as
"these were arguable on this run", never as a fixed property of the document.**
An empty contested set is not evidence that the document is unambiguous.

The cause is that each pass is an independent sampled generation, and criteria
near a judgement boundary (CR-0014 concentration, CR-0016 valuation, CR-0034 fee
transparency — all three of which have real evidence on both sides) land
differently run to run. **The fix is not to collapse the dual pass**, which would
trade a visible instability for an invisible one: a single pass would still land
arbitrarily on one side, it would simply stop telling you. Options worth testing
are running each pass n times and reporting a disagreement *rate*, or pinning
temperature — neither is implemented.

The live acceptance test skips rather than fails when a run yields no contested
findings, since a fixed expectation here would be flaky by construction.

---

## Quick start

```bash
cd engine
python3 -m pip install PyYAML pypdf pytest      # Python 3.11+

python3 -m l1.cli version
python3 -m l1.cli validate criteria/default

python3 -m l1.cli analyze "../00-inbox/Neo Infra Income Opportunities Fund-II Feb'26.pdf" \
    --criteria criteria/default \
    --out /tmp/l1-run          # NOT a synced folder — see §6.6

python3 -m l1.cli inspect /tmp/l1-run
```

Measured on the 52-page Neo deck, full pipeline ~$3.80 and ~16 minutes:

| Stage | Time | Cost | Model calls |
|---|---|---|---|
| classification | ~11s | ~$0.05 | 1 |
| extraction | ~122s | ~$0.73 | 1 |
| diligence | ~21s | **$0.00** | **0** — deterministic, network only |
| scoring | ~360-490s | ~$1.50-2.30 | 2 (lenient + strict) |
| memo | ~100-120s | ~$0.46-0.71 | 1 (narrative sections only) |

Scoring is the expensive stage because dual-pass means two full evaluations of
17 criteria over 52 pages. That cost buys the `contested` findings — see below.

### Tests

```bash
python3 -m pytest              # 256 fast tests, ~0.3s, no API calls, no cost
python3 -m pytest -m slow      # 65 live tests against the real deck (~21min, ~$5)
```

**The marker is `slow`, not `live`.** `-m "not live"` is an unknown-marker
filter: it deselects nothing and silently starts running the real pipeline.
Slow tests are excluded by default via `addopts` in `pytest.ini`.

The split is by file, and the fast suite is where the invariants are proven:

| File | Tests | Cost | Covers |
|---|---|---|---|
| `test_invariants.py` | 40 | free | 6.1, 6.3, 6.6, envelope contract, structured `unresolved` never reaching disk |
| `test_scoring_memo.py` | 127 | free | 6.2, 6.4 (+ its false positives), dual-pass reconciliation, unreachable-source policy, three-outcome diligence, **the split-memo invariants**: all-sections-mandatory, the §6.4 sweep across every file, the recommendation-file render, and **the structured `unresolved` contract** with its code-enforced kind-safety rule |
| `test_exit_codes.py` | 14 | free | exit-code contract |
| `test_retry.py` | 16 | free | structured-output retry and fallback |
| `test_quote_verification.py` | 17 | free | three-tier quote verifier, and what it still rejects |
| `test_telemetry.py` | 29 | free | run.json / status.jsonl / errors.jsonl emission |
| `test_test_criterion.py` | 13 | free | single-criterion dry-run path |
| `test_neo_deck.py` | 65 | ~$5 | live acceptance against the real deck, including the 13-file memo layout, link resolution, and §11's search-account depth |

Every invariant has fast coverage that fails when violated: 6.1 ×10, 6.2 ×9
(4 of them on the recommendation *file*), 6.3 ×10, 6.4 ×20 (6 guarding against
the §6.4 false positives, 8 parameterised over which section file the
fabrication lands in), all-sections-mandatory ×10, plus 17 pinning the quote
verifier against fuzzy matching. So "256 fast tests pass" is evidence about the
invariants, not only about plumbing — but the live suite is what proves the
stages actually work.

Live fixtures are session-scoped in `tests/conftest.py` and chained
(`classified` → `extracted` → `diligenced` → `scored` → `memoed`), so the whole
acceptance suite shares **one** pipeline run rather than re-running it per class.

---

## What works

| Capability | State |
|---|---|
| `l1 analyze` — all five stages | Works end-to-end on the reference deck |
| Memo written as `05-memo/` — index + 12 section files | Works; all 13 asserted present and non-empty before success |
| `l1 validate` / `l1 inspect` / `l1 version` | Work |
| Invariant 6.1 (no stage proceeds on missing input) | Enforced, 10 tests prove it fails when violated |
| Invariant 6.2 (memo cannot contradict its scorecard) | Enforced before the memo is written, 5 tests |
| Invariant 6.3 (every finding cites evidence) | Enforced at write time, 10 tests |
| Invariant 6.4 (numeric traceability) | Enforced by regex sweep, 6 tests |
| Invariant 6.5 (bounded critique — closed questions only) | The three gates are closed checks; no "is this good" pass exists |
| Invariant 6.6 (content addressing, atomic writes) | Enforced, 5 tests |
| Dual-pass lenient/strict scoring, `contested` findings | Works — 3, 3, 0 contested across three runs |
| Three-state diligence (`passed`/`failed`/`unavailable`) | Enforced in the type; a 4th value raises |
| `veto_unevaluated` distinct from fired and not_fired | Works, forced deterministically |
| Exit 11 (veto) | Reachable; memo is generated in veto form first |
| Section 11 carries every `unresolved` from every stage | 61-62 items per run, checked against `11-open-questions.md` before write |
| Every relative cross-section link resolves on a plain filesystem | Asserted in acceptance — PRD §0, no server or base URL |
| `--resume`, `--stage`, `--max-budget-usd`, `--json` | Work |
| Exit codes 0/10/11/20/30/143 | Work, pinned by tests |

### Not implemented

- **LLM-as-judge regression** and cross-section contradiction detection (PRD §8).
  The deterministic assertions are built; the judge is not.
- **Browser-driven diligence.** ZaubaCorp and IFSCA both need a real browser
  (see below). The adapters are written and correctly report `unavailable` from
  a plain HTTP client, so wiring a browser in is a localised change.

---

## Verified empirically vs. assumed

Everything below marked VERIFIED was run and observed, not inferred.

### VERIFIED — corrections to the PRD

**1. `--json-schema` takes a literal JSON string, not a file path.** The PRD does
not say which. Passing a path fails immediately:

```
Error: --json-schema is not valid JSON: JSON Parse error: Unrecognized token '/'
```

The schema goes on argv. The extraction schema is 25,502 bytes, well inside
macOS ARG_MAX (~1MB); `claude_runner` guards at 128KB.

**2. There is NO citations flag on the Claude Code CLI.** `claude --help` has no
`--citations` or equivalent. **PRD §7's central design decision — "citations vs.
structured output are mutually exclusive, so memo uses citations" — cannot be
implemented as written on the mandated runtime.** Citations are an Anthropic
*API* feature (a `citations` block on document content), not exposed by the CLI
the PRD requires stages to shell out to.

**RESOLVED — the PRD has since been corrected and re-read.** §7 now specifies
schema-enforced citation fields plus mechanical quote-vs-page verification, and
carries an explicit "CORRECTED 2026-07-20" note recording that the original
mutual-exclusivity design described something that does not exist at this layer.

That is what this build does at **every** stage including the memo: citations are
a projection of structured fields, so they cannot drift from them, and every
quote is checked against the text of the page it cites. The corrected §7 and the
implementation now agree; no deviation remains. The memo additionally derives
section 12 wholly from prior artifacts' citation records rather than generating
it, which is stronger than either original option.

**3. `--bare` cannot be used for local runs.** It requires `ANTHROPIC_API_KEY`
and fails "Not logged in · Please run /login" under subscription auth. This
matches PRD §7's auth table, so the engine does not use it — but it means the
worker and developer paths are not byte-identical, contrary to "no code path
differs".

**4. Structured output fails intermittently — the largest operational surprise.**
Measured **2 failures in 8 identical trivial calls**, surfacing as either:

```
The model's tool call could not be parsed (retry also failed).
subtype: error_max_structured_output_retries
```

Extraction additionally exits 1 with **completely empty stderr** on some runs,
while the byte-identical invocation succeeds on retry.

Two hypotheses were tested and **disproved**, recorded so nobody re-litigates
them:
- *Nullable encoding.* `{"type":["string","null"]}` vs an `anyOf` equivalent:
  an early n=5 sample suggested `anyOf` was more reliable (3/5 vs 5/5). At n=8
  both measured 6/8. **The n=5 result was noise** and nearly caused an
  unnecessary rewrite of both schemas.
- *Schema size / prompt length.* A 25KB schema over 83KB of deck text succeeds
  routinely. Not the variable.

The engine therefore retries 4× with exponential backoff and a non-identical
prompt on retry, then falls back to text-mode JSON parsing, flagging
`degraded.reason = "text_mode_fallback"` on the artifact. **Any production
deployment must budget for this**; a single-shot call to this runtime is not
reliable.

**5. Classification was unstable between two near-synonymous enum values.**
`pitch_deck` vs `investor_presentation` alternated across runs on the same
document. Fixed by giving `document_type` an explicit priority-ordered
disambiguation in the schema description; now 3/3 stable. **The PRD's enum list
needs these definitions** — the values overlap in ordinary usage.

**6. The single most important finding in this build: a prompt instruction did
NOT prevent an unreachable source from becoming a veto.**

The diligence stage recorded SEBI as `unavailable`, with what was then believed
to be geo-fence evidence attached. (That diagnosis was later found wrong — SEBI
is reachable; see the diligence table. The finding below is unaffected: it is
about what scoring does with an `unavailable` check, whatever its cause, and
that behaviour is unchanged for the sources that genuinely are unreachable.) The strict scoring pass then **fired CR-0001 — a VETO — at
high confidence**, reasoning:

> "The document asserts the status in words on page 37 but supplies no
> registration number anywhere in 52 pages, and the SEBI intermediary register
> could not be reached, so the assertion is unverified from both directions."

That chain is locally sensible and globally wrong. It converts "we could not
check" into a terminal adverse finding, and the run exited 11 on a fund whose
registration status is merely unknown — the exact conflation PRD §5 stage 3
forbids.

Adding an explicit prompt rule ("an unreachable source is never an adverse
finding") **reduced but did not eliminate it**: on the re-run the strict pass
still returned CR-0001 as fired. What actually fixes it is
`_enforce_blocked_criteria`, which deterministically forces any criterion whose
external check was `unavailable` into `unevaluated`, whatever the model
concluded, before the summary and before the veto check. The model's reading is
preserved in `model_reading_before_policy` for inspection but does not decide
the outcome.

**Generalise this: where a safety property must hold, a prompt is not a
mechanism.** The prompt lowers the rate; only the code makes it invariant. This
is the same principle as §6.4's "models are not asked to check their own
arithmetic", applied to policy rather than numbers.

**7. The IFSCA empty-table trap caught a real bug in this build's own guard.**
The adapter was written specifically to guard against IFSCA's plain-HTTP
response (HTTP 200, full table shell, zero entity rows — indistinguishable from
a legitimate "no match"). The first implementation counted any `<tr>` with a
non-empty `<td>` and scored **10 populated rows**, so it reported "does not
appear in the IFSCA directory" — a confident false negative from a page that
never loaded.

Those ten rows are a hidden per-entity detail template whose left cell holds a
static label ("Registered Address", "Validity From", …) and whose right cell is
empty. The guard now excludes known template labels and requires ≥2 non-empty
cells. **The trap is subtle enough to catch an implementation written expressly
to avoid it**, which is the strongest argument for the row-count assertion being
mandatory rather than advisory.

**8. §6.4 failed the run on numbers that were genuinely traceable — a false
positive is as damaging as a miss.**

A full-pipeline run died at exit 20 on `['2,222', '1,860', '114']`. All three
were real:

- `2,222` and `1,860` appear in **`unresolved` prose** on the extraction and
  scoring artifacts. `1,860` in particular records a document inconsistency the
  engine caught itself — page 25's headline reads "Pipeline of Rs ~1,900 crore"
  while its own table totals 1,860, and the engine explicitly refused to average
  or correct it. **The memo was propagating a high-value finding and being
  failed for it.**
- `114` is the **citation count section 12 computes about its own artifacts**.

The first cause was that the corpus was built from artifact `result` bodies
only, missing `unresolved`, `absence_evidence`, and evidence quotes — precisely
where the most valuable findings live. The second was that engine-computed
tallies above the ≤100 small-integer allowance had no home.

Fixed by `build_traceable_corpus()`, one definition of "traceable" shared by the
memo stage and the acceptance tests so they cannot drift: every number in every
prior artifact **envelope**, plus every number appearing verbatim in the source
deck, plus section 12's tallies derived by the same traversal that prints them.

**The invariant was widened, not weakened**, and that is pinned by tests:
`9,999`, `12,345` and `7,777,777` still fail from a corpus built over the real
run. The deck is the *fallback* corpus, never the primary one — matching against
52 pages first would let almost any number pass on a number-dense document.

**The general lesson: a check that cries wolf gets switched off.** Precision in
both directions is what keeps an invariant enforceable.

**9. Two memo acceptance tests ERRORED for a whole cycle without being noticed —
and the verification method is what hid it.**

The pipeline fixtures were `scope="class"`, each defined in the class that first
used it. `memoed` (in `TestMemoAcceptance`) requested `scored` (in
`TestScoringAcceptance`), and a class-scoped fixture is invisible outside its
own class:

```
E  fixture 'scored' not found
ERROR tests/test_neo_deck.py::TestMemoAcceptance::test_every_number_is_traceable
ERROR tests/test_neo_deck.py::TestMemoAcceptance::test_a_fabricated_number_would_still_fail
```

The second of those is the test whose entire job is proving §6.4 was widened
rather than weakened. **An ERROR is not a pass, and a test that errors proves
nothing.**

It went unnoticed because the results were verified by instantiating the test
classes and calling their methods directly in a hand-rolled harness. That
bypasses pytest's fixture resolution entirely, so every test "passed" while two
of them could not run under pytest at all. **Convenience harnesses that skip the
runner do not verify the suite; they verify a different thing that resembles
it.** Acceptance results are now only reported from real `pytest` output.

Fixed by hoisting all five fixtures to `scope="session"` in `tests/conftest.py`,
which also cuts the acceptance run from one pipeline per class to one per
session. `pytest --setup-plan` confirms the chain resolves.

**10. The quote verifier failed on multi-column slides — 17 of 73 on one run,
none of them fabrication. Fixed by a three-tier check, and the calibration is
the interesting part.**

`pdftotext -layout` renders a multi-column slide by splicing columns together
line by line. Page 27's left column reads "Total team size / 33 members", but
the extracted text is:

```
                        India's largest roads
Total team size    investing experience of
                   19+ Years                 platforms have joined
33 members                                   the team
```

A model reading the slide correctly quotes the left column. Those words are on
the page, in reading order, but **not contiguous** — the middle column sits
between them. **Whitespace normalisation does not fix this**, which was my first
assumption and it was wrong: the intervening characters are other columns'
words, not whitespace.

`l1/quoteverify.py` now returns one of three tiers, recorded on every citation:
`exact` (contiguous substring), `layout` (all tokens present, in order, within a
bounded gap), `unverified` (flagged and downgraded exactly as before).

**The calibration is empirical and the obvious approach fails.** I measured every
evidence quote against its cited page and against all 51 other pages:

- Genuine splices need gaps up to **~1,137 characters**.
- Cross-page FALSE matches occur at gaps as low as **1**.

So **gap size alone cannot separate them** — a bound tight enough to exclude
false matches also rejects most real splices. What separates them is **token
count**: every cross-page false match was a short generic phrase that recurs
legitimately in a fund deck — "senior advisor" (2 tokens), "tracking gross irr"
(3), "managing director and partner" (4).

| Setting | Rescued | Cross-page false |
|---|---|---|
| min_tokens=5, gap=1200 | 11 | **1** |
| **min_tokens=6, gap=1200** | **8** | **0** ← chosen |
| min_tokens=8, gap=1200 | 4 | 0 |

6/1200 is chosen over 5/1200 deliberately: three fewer quotes verify, but a
single cross-page match would be a fabricated citation reported as verified.
**Recall is the cheaper thing to give up.**

Measured effect on the reference run: **52/66 → 60/66** (52 exact, 8 layout,
6 still unverified and honestly flagged).

**This is not fuzzy matching and must not become it.** Every token must be
present, in the quote's own order, within the gap bound.
`tests/test_quote_verification.py` pins what it still rejects: missing tokens,
reordered tokens, scattered tokens, short generic phrases, invented quotes, and
— the one the coordinator specifically asked for — **real text from a different
page**, which must fail because that is fabricated provenance.

**11. Splitting the memo created a new failure mode, and the check for it had to
be calibrated down, not up.**

A missing section file is invisible in a way a missing section never was. In one
file, a dropped section was an absent heading in the middle of something someone
was already reading. As thirteen files, the directory listing looks plausible,
every file present is well-formed, and nothing signals that `07-team.md` was
never written. So `assert_sections_complete` asserts presence AND non-emptiness
before the run is declared successful.

**The calibration went the opposite way to the obvious instinct.** The first
threshold — 40 characters of body after scaffolding is stripped — rejected a
legitimate section: `"No green-flag criterion fired."` is a complete and correct
section 5. So is `"the lenient and strict passes agreed on every criterion"` for
section 9. **Reporting an absence IS content**; it is the engine doing exactly
what §5 requires. A threshold tuned to catch thin prose fails correct runs.

The stripper had the same bug in a second form: it removed all `_italic_` text as
scaffolding, which would make a section whose entire body is one italic sentence
indistinguishable from an empty one. It now strips only the engine's own
scaffolding — headings, rules, relative links, the "Written for:" line.

The bar sits just above scaffolding and no higher, and three terse-but-real
bodies are pinned as tests. **Same lesson as §6.4's false positives: a check that
cries wolf gets switched off**, and this one guards a property nothing else
covers.

**12. The prose-classification heuristic was built, measured, and then thrown
away in favour of a declared field — and that is the right outcome.**

The first version of section 11 grouped entries by pattern-matching their prose
for a cause. It worked on the reference run: after adding two rules, all 61
entries bucketed meaningfully and none fell through to "other". It was also the
wrong design, and the PRD change to structured entries superseded it.

The measurement that shows why is worth keeping. Rule ORDER turned out to be
load-bearing, because
`"CR-0001 ... forced to unevaluated. An unreachable source is never an adverse
finding."` mentions the unavailable source, so an order-insensitive classifier
filed it under a generic network failure and **hid the single most important
safety behaviour in the engine**. Getting that right required knowing, in
advance, which sentence fragments each stage happened to emit.

That is the definition of a heuristic that breaks silently: it was correct only
because it had been tuned against one run's actual wording, and any stage
rewording its output would have re-broken it with no test failing. `kind` is now
a declared field on the entry, and the safety rule is enforced in code by
`enforce_kind_safety` rather than inferred from prose. **A contract that a
downstream consumer routes on cannot be a regex over English.**

**13. The index's own run-cost figure is a §6.4 trap, caught before it fired.**

`00-index.md` prints the run cost. The index is built during the memo stage, so
the figure it prints is `budget.spent_usd` **at that moment** — before the memo's
own model call has been billed. `run.json`'s `cost_usd` is the FINAL total,
written after. At two decimal places these are different numbers.

Anything that re-derives the printed figure from `run.json` therefore fails §6.4
on a number the engine itself wrote — a false positive of exactly the kind that
gets a check switched off, and the acceptance test was originally written that
way. The fix is that the memo records `index_cost_usd` on its artifact, so no
consumer re-derives it. Three tests pin it, including one that asserts the two
numbers genuinely differ, so the test stops being vacuous if the trap ever goes
away.

**The general shape recurs**: every engine-computed figure that reaches the memo
must be supplied to the corpus by the code that prints it. Section 12's citation
tallies and the index's agreement percentage are handled the same way. The
alternative — exempting numbers by magnitude — would blind the check to genuine
fabrications of the same size.

**14. A run that fails at the last write can still be strong evidence — and
editing the tree mid-run will bite you.**

The first full run of the structured-`unresolved` build failed at the very last
step, writing the memo artifact:

```
invariants passed: all 13 memo files present, §6.2 recommendation agrees,
§6.4 all numerics traceable across every section file,
section 11 carries 59 unresolved item(s)
✗ run: [3-unresolved-malformed] <outgoing memo artifact>: unresolved[0] is a
  str, not an object.
```

**Every gate passed; the write is what failed.** The cause was not the code on
disk — it was that the process had imported `memo.py` at 06:30 and the coercion
that fixes exactly this was added at 07:12, while the run was still going. Python
caches modules at import, so the running pipeline held the old function for its
entire 17 minutes.

Two things worth keeping from it. First, **`write_artifact` did its job**: a
malformed entry did not reach disk, which is the whole point of validating there
rather than after. Second, editing a live tree during a long run produces
failures that look like code defects and are not — the fix was to re-run the
memo stage alone against the already-valid prior artifacts, which cost one model
call instead of seventeen minutes.

**15. Two acceptance tests failed on the first real pytest run — both were the
tests being stale, not the engine.**

```
FAILED test_the_index_breaks_open_questions_down_by_kind
  ImportError: cannot import name 'classify_unresolved'
FAILED test_section_11_carries_the_full_search_account_not_a_summary
  AssertionError: expected detailed unresolved entries on this deck
  assert []
```

The first imported a function the structured-`unresolved` change had deleted.
The second computed `len(entry) > 200` over entries that are now **objects**, so
every entry measured as short and the filter returned empty — the assertion that
caught it was the guard `assert long_entries`, which existed only because a
filter that silently returns nothing makes the loop below it vacuous.

**That guard is the reason this was a failure rather than a silent pass.** Without
it, the test would have iterated zero entries, asserted nothing, and reported
PASSED — a test that proves nothing while looking like evidence. Same family as
the fixture-scope bug in item 9: **the dangerous outcome is not a red test, it is
a green one that never ran its assertions.** Any test that filters a collection
before looping should assert the filter matched something.

Both fixes were test-side: read the declared `kind` instead of re-deriving it,
and measure `entry["account"]` instead of the object.

**16. A "bug" I diagnosed from a failing acceptance test did not exist — the
criteria set had changed under the run, and I nearly filed a fix for nothing.**

```
FAILED test_every_active_criterion_is_evaluated_exactly_once
  missing: {'CR-0018'}   extra: {'CR-0003'}
```

I read this as scoring hallucinating a criterion code and silently dropping a
red flag — a serious finding, and I wrote it up as the highest-priority open
item. It was wrong.

`criteria/default/criteria.yaml` had been edited mid-session: **CR-0003 (VETO)
was retired and replaced by CR-0018 at RED_FLAG tier** by stakeholder decision,
with the rationale recorded inline — a veto silently rejects every genuinely
first-time manager, and a veto is invisible in a way a red flag is not, because
the analysis stops rather than surfacing the concern for judgement. Scoring
evaluated exactly the 17 active criteria, correctly, on both runs. The two sets I
compared were simply drawn from different versions of the file.

**What actually failed was a stale assertion**, `tiers == {"VETO": 3,
"RED_FLAG": 8, "GREEN_FLAG": 6}`, pinning PRD §11's seed distribution against a
set that had deliberately moved to 2/9/6. It now pins the current set and names
the deviation, so a future reader sees a decision rather than a discrepancy.

**Two lessons, and the second is the uncomfortable one.** First, an acceptance
test that compares live output against a file on disk is comparing two moving
things; when it fails, check whether the *expectation* moved. Second: I had a
plausible mechanism, two "reproductions", and a written-up root cause — all of it
wrong, because I never checked the file's mtime. **Reproducing a symptom twice is
not confirmation when both runs read the same changed input.**

### VERIFIED — runtime variance and the retry's root cause

**Structured output failures are not random parse errors.** `errors.jsonl`
carries subtype `error_max_structured_output_retries`: Claude Code's OWN
internal structured-output retry exhausts before returning to the caller. The
engine's outer 4× retry is therefore **load-bearing, not defensive** — removing
it would surface those exhaustions as run failures.

**Runtime variance is severe and must be budgeted for.** Extraction measured
**123s/$0.42 → 792s/$2.92** across identical runs on the same document: 6×
wall-clock, 7× cost. Full pipeline ranges **8–16 minutes and $2–4**. Any worker
timeout or budget ceiling must target the worst case, not the median; a timeout
set from a fast run will kill a legitimate slow one.

### VERIFIED — corrections to the PRD's own acceptance criteria

**PRD §8 criteria 3, 4, 5 and 7 hold. Criterion 6 is wrong, and the brief's
expectation for CR-0012 is wrong.** Both non-fires were checked against the
source text rather than taken from the model.

- **CR-0017 (stale document) must NOT fire.** The criterion's threshold is
  "more than six months prior to the date of analysis". The deck is dated
  February 2026 (p.1, corroborated by an 18-02-2026 price reference on p.17) and
  the analysis date is 2026-07-20 — **5 months**. Five does not exceed six. Both
  passes agreed at high confidence, using date arithmetic the engine computes
  itself and hands to the model rather than asking it to calculate.
  The acceptance test therefore pins **the arithmetic, not the verdict**, so it
  stays correct once the analysis date crosses the threshold.

- **CR-0012 (key person risk) must NOT fire on this deck.** The rule is
  conjunctive: attribution concentrated on one or two individuals **AND** no
  key-person clause **AND** no bench depth. Only the middle limb holds — the
  key-person clause is genuinely absent. The deck evidences a 33-member team
  (p.27, verified: the string "33 members" is on that page), a separate
  investment team (p.33) and an operations bench (p.34), so the concentration
  limb fails. Firing it would require ignoring two of the rule's three limbs.

The brief predicted both would fire "because extraction already found the
underlying facts". Extraction did find them — `key_person_clause` is null — but
a criterion is its whole condition, not its most salient clause.

### VERIFIED — ground truth on the Neo deck

sha256 `2b17...3562` and 52 pages confirmed. `pdftotext -layout` gives a clean
text layer. Extraction recovered every ground-truth value in the brief, each
with a page citation:

| Field | Extracted | Page |
|---|---|---|
| Fund size | `~ INR 5,000 crores` | 37 |
| Target return | `~ 18-20% p.a.` | 37 |
| Return basis | `gross` | 20 |
| Term / investment / exit | `7 years` / `4.5 Years` / `2.5 Years` | 37 |
| Drawdowns | `6` | 37 |
| Investment count | `20 to 22` | 37 |
| Hurdle | `10%` | 38 |
| Catch-up | `without_catch_up` | 38 |
| Net return disclosed | `no` | 52 |
| Service providers | EY, Trilegal, PwC, ICICI Bank, KFintech | 37 |
| Predecessor | NIIOF-I, committed/unrealised, no exits | 13, 17 |
| SEBI registration | **null**, recorded unresolved | — |

**The SEBI registration case is the sharpest result.** Page 37 says "SEBI
registered Category II AIF" with no number anywhere in 52 pages. (The live
register now supplies the missing side of this: the manager's registered trusts
and their numbers, e.g. `IN/AIF2/22-23/1042`. The scheme itself is not
separately registered — SEBI registers trusts — so the document's silence still
cannot be resolved to a single number without the PPM's trust name.) Across 5+ runs
the engine never invented one. A deterministic backstop in
`classification.py` additionally discards any returned registration string that
does not occur in the page text.

Two `unresolved` entries are genuinely analytical, and are the kind of thing the
PRD's acceptance bar was aiming at:

- `target_return_basis` — flagged that pages 4/20/52 say "gross" but **the terms
  table on page 37 states the same figure without the qualifier**. That is the
  CR-0010 disclosure gap, found without CR-0010 having run.
- `waterfall_example_present` — distinguished page 42's asset-level IRR build-up
  from an actual LP/GP distribution waterfall (no hurdle, no carry, no fees).

Also correctly refused to normalise tiered fees (2.00/1.75/1.50/1.25%) and
tiered carry (20/15/12.5/10%) into a single headline rate, preserving
`as_written` and explaining why in `unresolved`.

### VERIFIED — the reference run's scorecard

`recommendation: hold`, exit 0, 59 unresolved items carried into memo section 11.

| | Criteria |
|---|---|
| Red flags fired | CR-0010, CR-0011, CR-0014, CR-0016 |
| Green flags fired | CR-0033 |
| Contested | CR-0014 (was CR-0014, CR-0016, CR-0034 on an earlier run — see below) |
| `veto_unevaluated` | CR-0001, CR-0002 |
| Lenient/strict agreement | 82.4% (70.6% on an earlier run) |

**The split-memo run reproduced all of the stable outputs.** Same `hold`, same
four red flags, same green flag, same two `veto_unevaluated`. Section 11 grew
from 25KB to **45KB** on the same findings — that is the split doing what it was
for: the search accounts are no longer competing for space with sections nobody
reading them wants.

Open questions by routing kind on that run: **36 DOCUMENT_ANSWERABLE, 18
EXTERNALLY_BLOCKED, 5 ANALYST_ANSWERABLE.** The 18 blocked split across
Infrastructure (10), Analyst manual check (5) and Procurement (3) — which is the
whole argument for the field existing. Under the old flat list those 18 were
indistinguishable from the 36 a manager could actually answer.

**The contested count varies run to run: 3, 3, then 0 across three full runs**,
on identical inputs. The `hold` recommendation, the 4 red flags, the 1 green
flag and the 2 `veto_unevaluated` were stable across all three; only the
lenient/strict *disagreement* moved. So the contested set is the least stable
output in the engine and should be read as "these are arguable this time", not
as a fixed property of the document. The acceptance test skips rather than fails
when a run produces none.

**The disagreement is the point, not noise.** On the runs that produced them,
the lenient pass fired 4 criteria and the strict pass 6, overlapping on 3. Two
of the contested findings are genuinely arguable and the memo presents both
readings:

- **CR-0014 (concentration)** — strict fires because p.23 states only *floors*
  ("Atleast 80% of Fund" in roads and solar) and no cap of any kind exists;
  lenient does not fire because a quantified allocation policy under a "Strict
  Guardrails" heading plus a stated 20–22 position target substantially
  constitutes a disclosed policy.
- **CR-0016 (valuation)** — strict fires because no methodology, valuer, or
  independent review is described anywhere while marks are being struck and
  reported (p.17); lenient does not fire because valuation sits inside a formal
  quarterly IC sub-committee review (p.41), the auditor is named (p.37), and
  third-party DD is evidenced (p.29).

Both readings cite real pages. Resolving them would require the PPM, which the
memo says in as many words. That is the honest output.

### Diligence: what can and cannot be checked

Every verdict here was established by an actual fetch, not inferred — and one
of them was established **wrongly**, which is worth stating plainly. On the
reference run **7 of 7 checks were `unavailable`**, and the SEBI pair was
`unavailable` for a reason that did not exist: a geo-fence inferred from a
stalled TLS handshake that was really Cloudflare rejecting a default user-agent.
Re-verified 2026-07-21 with browser headers, SEBI answers normally. The lesson
is not that `unavailable` was rendered dishonestly — the mechanism worked — but
that **a reachability verdict gating a VETO criterion needs a positive control
before it is trusted.**

| Source | State | Consequence |
|---|---|---|
| SEBI register + enforcement | **WORKS over plain HTTP** (corrected 2026-07-21) | Was wrongly recorded as geo-fenced; the real gate is Cloudflare rejecting a default UA. Both registers are server-side rendered Struts pages — session cookie + form token, no JS, no CAPTCHA. CR-0001/CR-0002 are now evaluated for real. |
| MCA21 | **Login + CAPTCHA** | Not attempted. Deliberate access controls on a government system; route via a licensed provider. |
| ZaubaCorp | **WORKS over plain HTTP** (upgraded 2026-07-21) | Returns the correct CIN on 3/3 attempts once the shared browser header set is sent; raw `curl` with the same UA still 403s, so it is the full header set that matters. Anti-bot edge — the `unavailable` branch is retained for when it regresses. |
| IFSCA | **Browser-only** (empty table over HTTP) | Guarded by a row-count assertion — see VERIFIED item 7. |
| Tofler | **Not used, by policy** | robots.txt disallows exactly the search/company paths a scraper needs. There is no code path that fetches it. |

`sebi_registration_lookup` deliberately does **not** issue a request: the block
is at TLS and takes 25s to time out, and the outcome is already known with
certainty. The empirical evidence is carried in the `reason` string so the
artifact justifies itself rather than saying an unexplained "unavailable".

### ASSUMED — not verified

- **`--max-budget-usd` actually aborts.** Passed through and tracked
  cumulatively across stages in `BudgetTracker`, but never driven to the ceiling
  on a real run. The cross-stage accounting is ours and is tested; the flag's own
  behaviour is not.
- **SIGTERM → exit 143.** Handler installed, not tested under a real signal.
- **Non-analysable documents → exit 10.** The rejection path is coded and
  unit-tested, but only ever run against one analysable document.
- **Scanned/image-only PDFs.** `extract_pages` raises if no page yields text; not
  tested with a real scanned deck.
- **Exit 11 on a real deck.** The veto halt is exercised by unit tests and by the
  spurious CR-0001 fire before it was fixed, but no document in hand legitimately
  fires a veto, so the veto-form memo has only been rendered from a synthetic
  scorecard.
- **`passed` and `failed` diligence outcomes end to end.** Every check on the
  reference run was `unavailable`, so the `passed` and `failed` branches are
  covered by unit tests against synthetic responses, not by a live source.

---

## Where the PRD is wrong or underspecified

1. ~~**§7 citations vs. structured output**~~ — **RESOLVED.** The PRD has since
   been corrected and now specifies schema-enforced citation fields plus
   mechanical quote-vs-page verification, which is what this build does at every
   stage. The corrected §7 matches the implementation; no deviation remains.
   Re-read and confirmed.
2. **§5 stage 2 "text-first-then-structure"** — specifies a two-pass extraction
   (verbatim passages, then structure). This build uses **one** structured pass
   whose schema requires a verbatim `quote` beside every `value`, which serves
   the same anti-hallucination purpose at half the cost and latency. Given
   structured output's measured flakiness, a second pass would double the
   failure surface. Deviation is deliberate; revisit if quote verification
   degrades.
3. **§3 artifact contract omits `document_date`** from classification, but §8
   criterion 6 requires firing CR-0017 on document staleness, which needs it.
   Added to the classification schema.
4. **§11's seed tier distribution is now 2/9/6, not 3/8/6.** `CR-0003` (no
   attributable prior track record) was retired and reissued as `CR-0018` at
   RED_FLAG tier on 2026-07-21 by stakeholder decision, recorded inline in
   `criteria.yaml` and in PRD 03 §12. A veto would silently reject every
   genuinely first-time manager, and a veto is invisible in a way a red flag is
   not — the analysis stops rather than surfacing the concern for judgement. An
   institution that wants it disqualifying promotes it to VETO in its own set,
   which is what per-institution criteria authoring is for. Still 17 criteria.
5. **§11 seed criteria supply only 5 of 9 required fields.** Code, name,
   severity, detection guidance, and rationale are given;
   `category`, `weight`, `evidence_requirement`, and `remediation_prompt` are
   not. They are **authored in `criteria/default/criteria.yaml` and flagged in a
   header comment** — `evidence_requirement` drives grounding and should be
   reviewed before any finding is relied on. All weights are 1.0 because the PRD
   gives no basis for differentiating them.
6. **§4 `l1 validate` "warns on criteria whose guidance contains no concrete
   noun"** — implemented as a hardcoded noun list, which is a crude heuristic
   that will produce false positives on legitimate rules. All 17 seed criteria
   pass, so it is currently untested against a rule that should trip it.
7. **§6.4 numeric traceability** — now implemented, and the tiered-fee problem
   predicted here was real. `normalised` is legitimately null for the management
   fee, so the sweep matches against `as_written` and source quotes as well.
   Three further exclusions were necessary and are deliberate holes, each
   justified in `memo_checks.py`: page citations and criterion codes (provenance,
   not claims), markdown heading/list numbers (structure), and integers ≤100
   (counts the memo computes about its own findings, e.g. "4 red flags").
   **The last is the widest hole** — a fabricated small integer would pass. The
   alternative is failing memos for correct arithmetic over their own content.
8. **§8 acceptance criterion 6 is factually wrong** (CR-0017 staleness) and the
   brief's CR-0012 expectation is wrong. Both are documented above with the
   source text checked. The acceptance test for CR-0017 pins the arithmetic
   rather than the verdict so it does not rot.
9. **§5 stage 3's `unavailable` policy needs a code-level enforcement clause.**
   The PRD states the policy but implies it is satisfied by recording the
   outcome. It is not — see VERIFIED item 6. The PRD should say that a criterion
   whose check is unavailable is forced to unevaluated deterministically,
   independent of the evaluator's own conclusion.
10. **§9's open question about page-level citation for slide decks is real, and
   §7's column-format limitation is the dominant cause.** Verification rates
   measured across runs: classification 7/7 and 7/8, extraction 49/49, scoring
   62/66 to 70/80. **Every failure inspected was a multi-line column block** —
   the page 38 fee table and the page 20 strategy block recur. The text is on the
   page; `pdftotext -layout`'s padding is not reproducible.

   Handling, confirmed by inspection: whitespace-normalised comparison absorbs
   the common case; a residual mismatch is recorded as `quote_verified: false`,
   **retained rather than dropped** (CR-0034 kept 11 verified quotes alongside 1
   unverified), warned to `errors.jsonl`, and rendered with a marker in memo
   section 12. A quote citing a page outside the document is treated differently
   — that is fabricated provenance, not a layout artifact, and it is dropped.
   Nothing is silently presented as verified.
11. **§9's open question on contested findings is answered by this build:
    surface, do not tiebreak.** Three contested findings on the reference run,
    two of which are genuinely arguable with real evidence on both sides. A
    tiebreak pass would have produced a cleaner artifact by discarding the
    signal that the evidence is ambiguous.

---

## Architecture

```
engine/
  l1/
    cli.py              # argparse, exit codes, resume/stage orchestration
    errors.py           # exception → exit code mapping (PRD §2)
    fsutil.py           # atomic writes, sha256, sync-path detection (§6.6)
    artifacts.py        # envelope, invariants 6.1 + 6.3       ← the core
    criteria.py         # YAML loading, lint, content hashing (§4)
    pdf.py              # page extraction, page-marked prompt rendering
    claude_runner.py    # subprocess, retry, budget, fallback
    run.py              # run.json, status.jsonl, ingestion
    memo_checks.py      # invariants 6.2 + 6.4, section 11 completeness
    quoteverify.py      # 3-tier quote verification, shared by every stage
    unresolved.py       # structured open-question contract + kind-safety policy
    diligence_sources.py# external source adapters, three-outcome CheckResult
    stages/
      common.py         # shared grounding rules
      classification.py # stage 1
      extraction.py     # stage 2
      diligence.py      # stage 3 — deterministic, zero model calls
      scoring.py        # stage 4 — dual-pass, veto handling  ← the product value
      memo.py           # stage 5 — 4 of 12 sections are mechanical renders;
                        #   writes 05-memo/ (index + 12 files) + 05-memo.json
  criteria/default/     # 17 seed criteria from PRD 03 §11
  tests/                # 256 fast + 65 slow
```

`artifacts.py` and `memo_checks.py` are where the invariants live; everything
else is plumbing around them. Stages communicate only through disk artifacts, so
a stage structurally cannot read a value that was never written to its input.

### Invariant enforcement

- **6.1** — `assert_inputs_present()` is the first line of every stage and
  validates presence, JSON-readability, stage identity, schema version,
  non-null result, and the mandatory `unresolved` key. It has **no
  strict/force parameter**, and a test asserts none is ever added.
- **6.2** — `assert_recommendation_agrees()` + `assert_veto_consistency()` run
  **before the memo is written**, comparing the memo's structured recommendation
  against the scorecard's. The two are produced independently — the
  recommendation is computed deterministically in `_summarise()` and the memo
  renders it — which is what makes the comparison meaningful rather than a model
  checking itself.
- **6.3** — `write_artifact()` validates before writing, so an invalid artifact
  never reaches disk where the next stage would consume it as valid. Tests
  assert the file is absent after a rejected write.
- **6.4** — `assert_numerics_traceable()` regex-sweeps the assembled markdown and
  matches every numeric against `build_traceable_corpus()`: all text in all prior
  artifact envelopes (structured values, `unresolved` prose, `absence_evidence`,
  evidence quotes), the source page text as a fallback, and section 12's
  engine-computed tallies. Unmatched numbers raise before the memo is written.
  No model is asked to verify its own arithmetic. See VERIFIED item 8 for the
  false positives that shaped this and the tests that keep it strict.
- **6.5** — the three gates are all closed questions ("does this number appear",
  "does this string match", "is this entry present"). There is no "is this
  analysis good" pass anywhere in the engine.
- **6.6** — temp-then-rename with `fsync` in the destination directory;
  identity is sha256, never the filename; source copied to an engine-chosen
  `00-source.pdf`; sync-tree paths warn.

### The three-state discipline

The engine's central safety property is that "we could not check" is never
rendered as "we checked and it was fine". It is enforced at three layers:

12. `CheckResult.__post_init__` rejects any outcome outside
   `passed`/`failed`/`unavailable`, and rejects `unavailable` without a reason.
13. `_enforce_blocked_criteria` forces any criterion whose check was unavailable
   into `unevaluated` / `veto_unevaluated`, with `fired: null` — never `false`,
   so a consumer filtering on `fired == False` cannot sweep up unperformed
   checks.
14. The memo renders unavailable checks with their reason in section 11, and the
   diligence prompt block tells the evaluator explicitly that it may draw no
   conclusion in either direction.

### Demonstrating an invariant fails

```bash
cp -R /tmp/l1-run /tmp/l1-broken
rm /tmp/l1-broken/01-classification.json
python3 -m l1.cli analyze "../00-inbox/Neo Infra Income Opportunities Fund-II Feb'26.pdf" \
    --criteria criteria/default --out /tmp/l1-broken --stage extraction
echo $?   # 20
# [6.1-missing-input] required input artifact for stage 'classification' is absent: ...
```

---

### Demonstrating the unreachable-source policy holds

```bash
python3 -m pytest tests/test_scoring_memo.py::TestUnreachableSourcePolicy -v
# proves a fired VETO on an unavailable source is forced to veto_unevaluated,
# can never reach the exit-11 halt, and preserves the model's original reading
```

---

## Next steps

15. **Assert the returned criterion codes equal the active set.** Not because of
   a known bug — VERIFIED item 16 turned out to be a moving expectation, not a
   substitution — but because nothing in the engine would currently *catch* one.
   Today only an acceptance test would, and only after the run. A deterministic
   post-pass in scoring is cheap and closes the gap on principle.
16. ~~**Re-run diligence from an Indian IP.**~~ **DONE 2026-07-21, and the
   premise was wrong.** SEBI needed browser headers, not a different egress —
   its Cloudflare edge returns HTTP 530 to a default UA and 200 to a browser
   one. Both SEBI checks now run live, so CR-0001 and CR-0002 are evaluated
   rather than permanently `veto_unevaluated`. Residual SEBI work: the register
   indexes AIF *trusts*, not managers or schemes, so resolving a scheme to its
   parent trust still needs the PPM; and enforcement coverage is currently the
   Orders listing only, not recovery proceedings or unserved summons.
17. **Wire a browser into the ZaubaCorp and IFSCA adapters.** Both work in a real
   browser and both correctly report `unavailable` from plain HTTP today, so this
   is a localised change behind an existing interface. It would turn the
   corporate-identity half of diligence from unavailable to live.
18. **Reduce scoring cost.** At ~$2.19 it is 68% of the run. The dual pass is
   worth it, but the second pass currently re-sends all 52 pages; sending only
   the pages cited by the first pass plus the extraction summary is the obvious
   experiment. Measure the contested rate before and after — if it moves, the
   saving is not free.
19. **Exercise a real veto end to end** on a document that legitimately fires one,
   to confirm the veto-form memo and exit 11 on live output rather than a
   synthetic scorecard.
20. Drive `--max-budget-usd` to its ceiling on a real run and confirm exit 21.
21. **Build the LLM-as-judge regression** (PRD §8), cross-family so the judge is
   not the model that wrote the memo. The deterministic assertions are done and
   catch structural regressions; nothing currently catches prose quality drift.
