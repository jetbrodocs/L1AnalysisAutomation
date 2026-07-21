---
title: "Memo Reader — Visual Language & Prototype"
status: draft
created: 2026-07-21
updated: 2026-07-21
tags: [prototype, design, memo-reader, l1-analysis-platform]
---

# Memo Reader — Visual Language & Prototype

A working HTML prototype of the memo reader, rendering the **real output** of run
`299273b1-4ad1-4ce2-9a18-0bedf7dd67a9` on *Neo Infra Income Opportunities Fund II* — a 52-page
SEBI Cat II AIF deck, criteria set `CS-2026-0001` (DRAFT), recommendation **HOLD**.

No build step, no framework, no CDN beyond the Google Fonts link the brand guide specifies.
**Open `index.html` in a browser and it works.**

| File | Renders |
|---|---|
| `index.html` | `00-index.md` — the landing page: recommendation, scorecard, veto statement, question routing, section index |
| `section.html` | `04-risk-factors.md` — four findings with evidence, citations, severity, the contested split, and the unevaluated vetoes |
| `open-questions.html` | `11-open-questions.md` — 59 items across three kinds |
| `styles.css` | The shared visual system, importing `jetbro-brand/tokens.css` |

---

## The design plan

### Colour

The governing decision: **the brand accent never encodes status.**

`#c45a32` is reserved for navigation and structure — links, the accent line, the current-section
marker in the rail. It is never used for a finding's state. This keeps brand colour and semantic
colour on separate channels, so a red flag is never mistaken for a link and the accent never
competes with meaning.

Status is a separate ramp, validated with `dataviz/scripts/validate_palette.js`:

| Token | Light | Dark | Carries |
|---|---|---|---|
| `--st-red` | `#bf2d24` | `#cc5040` | Red flag fired |
| `--st-green` | `#0e7a52` | `#33a877` | Green flag fired |
| `--st-amber` | `#946200` | `#ad8620` | Layout-normalised quote; contested; analyst-attested |
| `--st-slate` | `#4f5b69` | `#93a1b3` | **Unevaluated / blocked** |

Validator results — both modes **ALL CHECKS PASS**:

```
light  #bf2d24,#0e7a52,#946200   lightness PASS · chroma PASS · CVD WARN 6.9 protan
                                 · normal-vision PASS 15.6 · contrast PASS
dark   #cc5040,#33a877,#ad8620   lightness PASS · chroma PASS · CVD WARN 7.7 deutan
                                 · normal-vision PASS 15.2 · contrast PASS
```

The CVD warnings sit in the 6–8 band, which the skill permits **only with secondary encoding**.
That condition is met everywhere: every status carries a mono glyph and a written label as well as
a colour (`▲ RED FLAG`, `● Green flags fired`, `□ VETO · NOT EVALUATED`). Nothing in this memo is
distinguished by colour alone.

**The slate is the most load-bearing colour choice in the system.** It is deliberately the one hue
nobody reads as a verdict — cool, low-chroma, and outside the red/green axis entirely. It fails the
dataviz chroma floor *by design*, because it is not a series colour: an unevaluated veto must never
render as a pass (a green tick) or a failure (a red cross), and PRD 05 §8 names this as the state
most likely to be mis-rendered. Grey with a hint of blue was the only honest answer.

Neutrals are warm-biased — the greys carry a trace of the accent's hue, so they read as chosen
rather than inherited. The dark ground is `#161614`, a warm near-black, not `#000`.

### Type

- **Bricolage Grotesque** — section titles, finding titles, the veto statement. Used with restraint.
- **Outfit** — body at 17px/1.65, weight 300. Generous, because this is read, not scanned.
- **Space Mono** — criterion codes, page citations, weights, hashes, question keys, owner routing.
  This is the "machine-checked" register, and it is doing real work: it marks the boundary between
  *what the engine measured* and *what the memo says about it*.

The hero figure (`HOLD`) is set in the **body sans, not the display face**. A recommendation is a
computed output; a display face would dress it as an opinion. This is a deliberate departure from
the usual "hero number gets the display font" reflex.

### Layout

A left section rail (collapsing to a horizontal scroller under 900px), a document column capped at
68ch, and full-bleed bands for the three things a reader must not scroll past: the DRAFT banner, the
scorecard, and the veto statement. Findings render as **document entries with a status rule on the
leading edge, not as cards** — four cards would read as a dashboard; this reads as a memo.

---

## The six design problems

### 1. Provenance visible at a glance

Three levels, encoded on **three channels simultaneously** — glyph, written label, colour:

| Level | Rendering | Meaning |
|---|---|---|
| Document-grounded | `✓ DOCUMENT` green | Page citation, quote checked against extracted page text |
| Attested-and-verified | `✎ ATTESTED` amber | Analyst supplied it and named a source; attributed and dated |
| Attested-unverified | `○ UNSOURCED` grey, **dashed** border | Analyst's word, no source. Never scored |

The dashed border on `UNSOURCED` is doing the accessibility work: it is the only one of the three
whose *border style* differs, so the distinction survives greyscale printing and full CVD. A
provenance key sits permanently in the rail on the index page and prints with the document.

### 2. Quote verification — three verdicts, honest about the rare failure

Real counts from `04-scoring.json` finding evidence: **61 exact, 5 layout, 4 unverified** (70
citations). The §12 ratio across the whole run is 101 of 105.

The `unverified` treatment was the most carefully calibrated element in the prototype. ~96% verify,
so the rare failure must read as *"we checked and could not confirm this"* — not as an error state.
What it gets:

- A **grey dashed left edge**, not red. Never a filled alarm block.
- The **quote shown in full**, never truncated or hidden.
- A note that names the cause and **attributes it to the extractor, not the manager**: *"The engine's
  extraction loses spatial layout on slide-derived pages, and this label sits in a two-column terms
  table."*
- The primary action is **Open the page image and read it yourself** — pushing the reader toward the
  source rather than asking them to trust the flag.
- Per the spec, **no highlight is drawn** on an unverified quote in the drawer; drawing a highlight
  the engine could not locate would be a fabrication.

`layout` gets amber and a plain explanation: *"The words are on the page; the line breaks are not
reproducible."* That sentence does the whole job.

### 3. Open questions — 59 across three kinds

The layout problem. Solved by making the three kinds **structurally different, not just differently
coloured** — because the difference between them *is* structural:

| Band | Edge | Affordance |
|---|---|---|
| Document-answerable (36) | solid green | `Upload a document` · `I can answer this myself` · `Not applicable` |
| Analyst-answerable (5) | solid amber | `Answer with a source` · `Not applicable` |
| **Blocked (18)** | **dotted slate** | **none — routes to an owner** |

The dotted edge is a broken line for a broken route. Every blocked item carries a slate notice
reading *"This check could not be performed. Nothing you can type or upload will resolve it,"*
followed by an **unblock list** (`→ Re-run from an Indian IP`, `→ Route through a licensed
provider`) that routes to an **owner**, never a text field.

The band opens with the statement that makes the rule legible without alarm:

> **There is no answer field on any item in this band.** That is deliberate. Inviting an analyst to
> type an answer to a geo-fenced register check is a broken affordance — it would produce an
> unsourced assertion where a register lookup belongs.
>
> **Absence of a check is not a finding.** None of these is a finding of no adverse history — each
> is the absence of a search.

Owner tallies (Infrastructure 10, Analyst 5, Procurement 3) appear in the band head and on the index,
so "do not ask the manager" always arrives with the answer to "then who?".

Scale is handled by a **bulk affordance first** (*"32 of these 36 name the PPM as the typical
source — upload one and re-run"*), a kind-jump nav, and stage subheads. The count with an affordance
is a co-pilot; the count alone is a complaint.

**Items are deliberately not deduplicated.** `economics.gp_commitment` appears three times because
extraction and scoring each searched for it with different term lists, and each occurrence records a
different search. Collapsing them would discard the second search record — which is precisely the
part of §11 that makes it a worklist rather than a disclaimer. The rail says so explicitly: *"59 is
the count of occurrences, not of distinct facts."*

### 4. The scorecard — carrying an 11:1 asymmetry honestly

Per `dataviz/choosing-a-form.md`, two numbers against a limit is a **meter**, not a chart, and
certainly not two stat tiles side by side. The form chosen is a **single shared baseline with one
maximum (11.0)**, so green renders as a 9.09% stub against a full red bar.

That geometry is the point. Two tiles reading "11.0" and "1.0" make the reader do the division;
a shared scale makes the asymmetry a fact on the page. Mark specs are followed: 14px track, square
at the baseline with a 4px rounded data end, track in a lighter step of the fill's own ramp, 2px
gaps between segments and in the count strip, `tabular-nums` on the aligned figures and
proportional figures on the hero.

**The red bar is segmented by contributing criterion** — 3.0 / 3.0 / 2.0 / 3.0, each segment
labelled, separated by the 2px surface gap. This is what makes the total *reproducible by eye*
rather than asserted: the reader sees the four parts and can add them. Verified by measurement —
the red segments fill 100% of the track and green renders at 0.092 of the red bar against an
expected 1/11 = 0.091.

Beneath it, a **"How these totals are computed"** disclosure publishes the engine's
`scoring_model`: the formula, the severity multiplier table (LOW 1.0 / MEDIUM 2.0 / HIGH 3.0 /
CRITICAL 5.0), and every per-criterion contribution with its own total row. An IC that cannot
reproduce the arithmetic behind a recommendation is right to distrust it, and this is cheap to show.

The count strip carries `4 red · 1 green · 1 contested · 2 unevaluated` — with **unevaluated in
slate**, so it reads as a fourth state rather than a variety of pass.

**Two disclosures the arithmetic makes possible, both surfaced:**

- **CR-0014 is contested and still contributes 2.0** — 18% of the red weight — carried on the strict
  reading. An IC should know how much of the score rests on a disagreement the engine refused to
  resolve. Accepting the lenient reading gives 9.0, which lands *exactly on* the `hold` threshold
  (`red ≥ 9.0 and red > 2 × green`, verified against `scoring.py`), so the recommendation holds
  either way but **has no margin above it.**
- **The unevaluated vetoes are never shown as `0.0`.** CR-0001 and CR-0002 carry `CRITICAL` severity
  — a ×5.0 multiplier, the heaviest in the model — and contribute nothing *because they did not
  fire, not because they are harmless*. A `0.0` beside a CRITICAL veto reads as "no problem here",
  which is the precise misreading state B exists to prevent. They render an **em dash in slate**
  with `not scored · CRITICAL 5.0 unapplied`, and the body states that their absence from the score
  is a gap in the arithmetic, not a point in the fund's favour.

### 5. "No veto fired — but no veto was cleared either."

Given a **dedicated full-bleed band** between the scorecard and the body, in slate, with the sentence
set in the display face at 24px as a statement rather than body copy.

Its marker is an **empty square** — neither tick nor cross. The shape *is* the meaning, and it is the
same `□` glyph used on every unevaluated veto badge and every blocked question, so the visual rhyme
carries across all three pages. The sentence gets its own horizontal band precisely so it cannot be
absorbed into a paragraph and skimmed as boilerplate.

### 6. The DRAFT criteria banner

Prominent but not swamping: a **hatched amber edge** rather than a filled amber block, aligned to the
content column rather than bled to the viewport edge (where it would read as chrome). A mono `DRAFT`
chip anchors it. It sits above the fund name on every page, is not dismissible, and prints.

Texture instead of fill is what keeps it from competing with the memo — a solid amber band across the
top of an IC document reads as an error page.

---

## Accessibility

- **No meaning in colour alone.** Every status carries a glyph *and* a label. `UNSOURCED` and
  `blocked` additionally differ in border *style* (dashed / dotted), surviving greyscale and CVD.
- Palette validated in both modes; CVD warnings are within the band the skill permits given the
  secondary encoding present throughout.
- Semantic HTML: real landmarks (`header`/`nav`/`main`/`aside`/`article`/`section`), real heading
  hierarchy, `<table>` with `<caption>` and `scope`, `aria-current="page"` on the rail,
  `role="img"` + `aria-label` on the meter bars describing the ratio in words.
- Visible focus ring on the accent; `prefers-reduced-motion` respected.
- Verdict glyphs are `aria-hidden` with the verdict repeated in visually-hidden text, so a screen
  reader hears "Verified exact" rather than a tick character.

## Print / PDF

Verified against the live DOM, not assumed:

- A4 with 18mm/20mm margins, 10pt body.
- The brand's **accent-line print fallback** and heading break rules come through the `tokens.css`
  import — not duplicated locally (confirmed: `--jetbro-accent` resolves to `#c45a32` and the print
  fallback rule is present via the import).
- `print-color-adjust: exact` on the **56 elements** that carry meaning in colour.
- **Absence evidence is forced open in print** (`.disclosure__body { display: block !important }`) —
  a collapsed negative-search record must not vanish from a PDF just because nobody expanded it.
- **§11 is non-excludable**: `.kind-band { display: block !important }`.
- Rail, action rows, and answer affordances are hidden; interactive chrome has no place in a PDF.

## Responsive

Verified by measurement at 380px and 760px across all three pages: **no page scrolls horizontally at
any width.** Tables scroll inside their own container. This required `min-width: 0` on
`.table-scroll` (as a grid child it otherwise sizes to content and pushes the page wide) plus
`overflow-wrap: anywhere` on hashes and run ids. The rail becomes a horizontal scroller below 900px.

---

## What is designed vs what is still open

### Designed and built
Provenance system · three quote verdicts · the three question kinds and their affordance asymmetry ·
scorecard meter · veto statement · DRAFT banner · contested split-reading treatment · section rail
with per-section badges · light and dark themes · print/PDF · responsive behaviour.

### Designed but not built in this prototype
- **The evidence drawer** (spec §3.5, §5). The two-click rule depends on it and it is the single
  biggest remaining piece. Citations here are anchors with hover states; they do not open a drawer.
  It needs the rendered page images from `00-pages/`, which the prototype does not load.
- **Inline answer forms.** The affordances are present and correctly routed by kind, but
  `Answer with a source` does not expand a form. The validation rules (V2–V4, especially the
  rejection of `"n/a"` as a source) are specified but not implemented.
- **Filters** (fired only / unanswered only / contested), review state per section, version banners.

### Resolved since the first draft

1. ~~**`kind` is not in the artifact.**~~ **Fixed in the PRD 06 contract** (2026-07-21). `unresolved`
   entries become structured objects carrying `kind`, `typical_source`, `blocker_class` and
   `unblock_owner`; an engine agent is implementing it. The prototype's three-band routing was
   derived by reading the memo markdown's groupings and should be re-pointed at the real fields once
   a fresh run carries them. **No layout change is expected** — the bands, affordance asymmetry and
   owner routing were built against exactly this shape.

2. ~~**Per-finding weights do not reconcile.**~~ **Fixed in `engine/l1/stages/scoring.py`**
   (2026-07-21). The cause was that `_summarise` computed `severity_multiplier × author_weight` but
   published only the author weight — correct arithmetic, invisibly applied, which is the worst
   combination. Findings now carry `severity_multiplier`, `author_weight`, `effective_weight` and
   `score_contribution`, and `result.scoring_model` publishes the formula, the severity table and
   every contribution.

   Independently verified by re-deriving the totals from the old run's findings:
   `3.0 + 3.0 + 2.0 + 3.0 = 11.0` red, `1.0` green — both matching the reported figures exactly.
   The prototype now renders `score_contribution` on every card with its derivation
   (`HIGH 3.0 × 1.0`), and segments the scorecard bar by contribution.

   **Note:** `04-scoring.json` in `/tmp/l1-split2/` is from the *old* run and still lacks these
   fields. The prototype's values are the verified derivations, not invented ones; a fresh run will
   carry them natively.

### Open — needs a decision before build

1. **"12 of 49" vs the real numbers.** The spec's header tile promises *"12 of these 49 typically
   resolve from a PPM"*. The actual run has **59** items, of which **36** are document-answerable and
   32 name the PPM. The prototype uses the real figures. The 12/49 in the spec is stale and should be
   corrected there; more importantly, **the derivation rule for the count must be fixed in the engine
   before it appears in the UI as a promise.**

2. **Duplicate occurrences.** 59 occurrences cover roughly 30 distinct facts. The prototype keeps
   them (with a note) on the argument that each records a separate search. If stakeholders prefer a
   deduplicated view, the search records must be nested under one item rather than dropped — but this
   should be an explicit decision, not a default.

3. **The `hold` threshold has no margin on this run.** Now visible for the first time because the
   arithmetic is published: red 11.0 clears `red ≥ 9.0` comfortably, but if CR-0014's contest were
   settled leniently the total would be **exactly 9.0** — on the boundary, not above it. The
   prototype states this in the contested note. Worth confirming with stakeholders whether a
   recommendation sitting exactly on a threshold should be surfaced more loudly than a footnote,
   and whether the 9.0 threshold is itself a considered value or a placeholder in a DRAFT criteria
   set that has never been approved.

### Flagged as unbuildable as specified

- **Spec §3.3 assumes one continuous scroll** ("Sections render in order 1→12 in a single scroll").
  The 2026-07-21 routing decision at the top of the spec supersedes this, but §3.3 was never
  rewritten and still contains the collapse-state rules for a single-document layout. Under
  per-section routing, "§11 is never collapsed by default" becomes trivially true — it has its own
  route — so the *stronger* reading is what is built: within its route it renders fully expanded, and
  the index links to it with its count and kind breakdown visible. **§3.3 should be rewritten to
  match the routing model.**

- **Spec §3.1 specifies four equal header tiles**, including an open-questions tile with a
  `[Upload a PPM]` affordance. Under per-section routing the tiles would have to repeat on all 13
  routes, which turns the most important content in the memo into persistent chrome. Built instead
  as: full-bleed scorecard and veto bands on the index, a compact mono meta-line on section routes,
  and the bulk PPM affordance placed **inside §11 where the questions are**. The requirement behind
  the tile — that §11 has the same prominence as the recommendation — is met by giving it equal
  billing on the index and a permanent count badge in the rail on every route.

- ~~**Spec §4.3 gives citation counts as 104 / 101 / 3.**~~ **Corrected in the spec** (2026-07-21,
  three places: §4.3 prose, the §12 quotation, and state P). The artifact says **105 / 101 / 4** in
  §12, and the scoring-stage evidence alone is **70 citations (61 exact / 5 layout / 4 unverified)**.
  Both are true of different populations, so the spec now carries an explicit note that a surface
  showing a ratio must say which population it is over — "101 of 105" and "61 of 70" describe
  different things, and a memo that blurs them undercuts its own verification claim. The prototype
  labels its denominators accordingly.

### Marked illustrative, not from the run

Two places where the prototype summarises rather than renders every item, both **explicitly labelled
in the page**: "20 more from scoring" (document band) and "10 more from scoring" (blocked band). The
full text of every one is in `11-open-questions.md`; they are collapsed here only to keep the
prototype page readable. **In the product every item renders in full** — §11 is never abridged.
Nothing else on any page is invented; all findings, quotes, page numbers, verdicts, search records,
and counts come from `/tmp/l1-split2/`.
