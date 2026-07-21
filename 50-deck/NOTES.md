---
title: "Speaker Notes: L1 Analysis Platform allocator deck"
status: draft
created: 2026-07-21
updated: 2026-07-21
tags: [deck, speaker-notes, allocator, sales]
---

# Speaker Notes: L1 Analysis Platform

**Audience.** Institutional allocators: endowments, family offices, funds-of-funds, PMS/AIF houses running multi-manager products. People who read fund decks for a living and will spot overclaiming instantly.

**Deck.** `index.html`, 16 slides. Arrow keys / space / PageUp / PageDown to navigate, `Home` / `End` to jump, `◐` toggles light and dark. Deep-link a slide with `#7`. Prints one slide per landscape page.

---

## The reference fund is anonymised. Keep it that way.

The deck never names the fund, its manager, its predecessor vehicle, its service providers, or the government counterparty. This is deliberate and it is not cosmetic.

The source document is marked **Private & Confidential**. This deck is shown to other allocators, who are that manager's peers and in some cases its competitors. Presenting an identifiable competitor's confidential deck contents to that audience is a genuine problem, not a stylistic one, and an allocator who sees us do it will correctly wonder what we would say about *their* documents.

**In Indian infrastructure credit, the combination is identifying even without the name.** Fund size, sector, vintage, the named service-provider set, and the counterparty authority together identify the manager to anyone in the room. That is why the providers are described by tier ("Big Four auditor, tier-one legal counsel, bank custodian, established RTA") and the authority as "central government counterparties".

**If asked directly whose deck it is:** decline, and let the decline do the work. *"It is a live Category II AIF and the document is marked confidential, so I am not going to name it. You would want the same answer if it were yours."* That answer sells better than the name would.

Every number is intact: the weights, the counts, the citations, the page numbers, the arithmetic. **The analysis is the point; the fund's identity is not.**

---

## The argument's structure

The deck runs a five-beat argument, and the order is deliberate:

1. **Their problem, not ours** (slide 2). Open on the constraint they already feel. Never open on the product.
2. **What goes in and what comes out** (slide 3). The shape of the thing, before any detail.
3. **The framework, then the evidence** (slides 5 to 9). State what the analysis examines before showing it applied, then show what it found on a real deck and the memo itself. The demo *is* the argument.
4. **Trust, ownership, and the system around it** (slides 8 to 13). Why the output can be believed, why the rules become theirs, and what the platform does between runs. This is the commercial core.
5. **Limits, then ask** (slides 15 to 16). Volunteering the gaps is what makes everything before it credible.

**The through-line to repeat:** *the engine reads and evidences; the analyst judges.* Every slide should ladder back to that. It is both the honest claim and the defensible one.

**Tone.** Understated. The material is strong enough that enthusiasm reads as overselling. Let the page citations do the persuading.

> **Positioning guardrail.** This is an analyst co-pilot, never an automated analyst. If someone says "so it replaces the first-pass analyst", correct it immediately. The engine produces a decision gate ("pursue / hold / pass, and here is what to ask"), never investment advice.

---

## Slide-by-slide

### 1. Title
**Say:** "What I'm going to show you is pre-MVP. The analysis engine works end to end; the management interface is specified, not built. Everything I show from the engine is real output from a real 52-page Category II AIF deck."

Lead with the pre-MVP stamp rather than letting them discover it. With this audience, volunteering the state of the product buys credibility for everything that follows.

### 2. The problem
**Say:** "The pattern we built against is that diligence capacity, not deal flow, is the binding constraint, and allocators are resolving it by shrinking the funnel."

⚠️ **Handle the sourcing carefully, and note precisely what is and isn't established.**

**The figures are sound.** They were verified against primary sources earlier in the project. Two attributions confirmed: the **23% expecting to cut GP relationships** is Coller Capital's Global Private Capital Barometer, and the **two-month IC memo** is the Addepar/Stanford study of 54 institutions.

**What is missing is independent re-verification at deck-build time.** The search budget was exhausted before the five could be re-checked against their primary reports. That is a different and weaker claim than "the numbers are doubtful", and worth holding the distinction: the risk is a stale year or a figure that traces to secondary coverage, not fabrication.

**Recommended posture:** keep the "pending verification" caveats on the slide until someone re-pulls the underlying reports. For this audience, a caveat you volunteer costs far less than a confident citation that turns out to be secondary coverage. Present them as *"the pattern we built against, and I'll send you the sourcing"* rather than asserting them. Slides 6 to 8 carry the argument and rest entirely on our own run; do not let a soft citation here undermine them.

The 23% line is the real point: the cost is a smaller opportunity set, not slower diligence.

### 3. In and out (data flow)
**New slide.** It exists because stakeholders kept asking "what actually goes in and what comes out" and the deck previously answered that only in prose, four slides later.

**Say:** "A PDF and your own criteria go in. A memo, scored findings with page citations, a routed worklist, and machine-readable JSON come out. Here is where the time and money actually go."

Three things to land:
- **The inputs include their criteria**, not just the document. That is the seed of slide 10's argument and it is worth planting early.
- **Scoring is two-thirds of both clock and cost** because it is the stage that runs twice. This is the honest explanation for why a run costs what it does, and it pre-empts "why is it slow".
- **Diligence costs $0.00** because it calls registers rather than a model. Worth saying out loud, because it shows not everything is an LLM call.

The per-stage numbers are measured from run `022c6853`, not modelled. If asked, the total is 17 minutes and $5.70, which is above the documented $2 to $4 band. See the economics note below before quoting a range.

### 4. What it is
**Say:** "Five stages, each receiving every prior stage's output."

Two details to land:
- **The verdict is computed, not written.** The recommendation falls out of the scorecard arithmetic deterministically. No model decides HOLD.
- **Scoring runs twice**, lenient and strict. Where the passes disagree the engine refuses to resolve it and prints both readings. Disagreement is surfaced, not averaged away.

Mention the laptop point: no server, no login. A confidential PPM never leaves the building.

### 5. What the analysis examines
**New slide, and it answers the question this deck previously could not.** An allocator's first question is whether your diligence framework matches how they think about manager selection. Slide 3 covers mechanics; this one covers substance. It sits before the findings deliberately, so they know the framework before they see it applied.

**Say:** "Six dimensions, seventeen criteria, three tiers. This is what a deal gets scored against."

Three points make it land rather than reading as a feature list:

1. **Governance is the largest category by design.** Seven of seventeen. Operational risk predicts fund failure more strongly than financial risk does, so the framework is weighted towards how allocators actually lose money rather than towards what is easiest to extract from a deck. Say this one out loud; it is the point that signals the framework was built by someone who has thought about failure modes.

2. **Only the regulatory criteria are vetoes.** Both of them. Those are legal preconditions rather than investment judgements: a fund without valid registration cannot accept commitments at all. Everything else is weighted judgement and never a hard stop. **This is also the cleanest way to make the personalisation story concrete** rather than asserted: an institution that wants "no attributable track record" to be disqualifying promotes it to a veto in its own set. That is exactly the move slide 10 describes, and here they can see the shape of what they would be editing.

3. **These are our defaults and they are placeholders.** The slide says so. Do not soften it into "best practice defaults". The institution replaces them, and that is the product rather than a caveat.

**Reading the visual:** tile width is proportional to criteria count, so governance visibly dominates. Colour encodes tier only (red = veto, amber = red flag, green = green flag), never category, and every count is printed next to its bar so nothing depends on size or colour alone.

**If asked "is seventeen enough?"** No, and it is not meant to be. Seventeen is a demonstrable seed set, not a diligence framework. The honest answer is that a real institutional set is larger and more specific, and that the workshop on slide 16 is where that gets built.

### 6. What it found
**The evidence slide. Slow down here.**

**Say:** "Every one of these is real, from one run, and every one carries the page it came from."

Walk three, not six. Pick by audience:
- **CR-0010.** Returns stated gross throughout, no net-to-investor figure anywhere in 52 pages. Fees, hurdle and carry *are* disclosed, so net is derivable, but derivability is not disclosure.
- **CR-0011.** The predecessor's ~21% is a *tracking* number: marked, not realised. The engine worked out that Rs 2,222cr of the Rs 2,985cr portfolio is still awaiting counterparty approvals to close.
- **No GP commitment** anywhere in 52 pages, reported as an explicit absence with the search terms listed.

**Point at CR-0012 deliberately.** It is the one marked *contested*, in slate rather than red: it fired on the strict pass and not the lenient one, at low confidence. That is the engine declining to resolve its own disagreement, a feature worth naming out loud, because it is what a system optimising for a clean-looking output would hide.

**The line that lands:** *"A fund that does not disclose its sponsor commitment has told you something."*

Note the green flag too. The tier-one provider set fired correctly. It is not a pessimism machine.

### 7. Actual memo output
**Say:** "This is unedited. Left is the recommendation; right is one risk finding."

Point at the two things a sceptic checks:
- The memo states **"No veto fired, but no veto was cleared either"**. It refuses to let an unperformed check read as a pass.
- The right-hand finding shows the engine **doing arithmetic across a table**: Rs 520cr + Rs 1,502cr + Rs 200cr = Rs 2,222cr of a Rs 2,985cr portfolio still awaiting approval. That is the sort of thing a reader skims past on page 17.

> **Note on the em dashes in these two panels.** They are the engine's own words on a slide labelled *verbatim*, so they stay. Everywhere else in the deck they were removed. If you are editing this deck, do not "clean up" the quoted panels: a quotation that has been silently reworded is no longer a quotation, and this deck's entire argument is that quoted material is checkable.

### 8. Why it is trustworthy
**The commercial core. This is the differentiator, not the automation.**

**Say:** "Anyone can generate a memo. The question is why you'd believe it."

- Every quote is checked in code against the page it cites. **102 of 105 matched.** Not trusted from the model.
- Numbers must trace to an extracted value **or the run fails**.
- The memo **cannot contradict its own scorecard**, enforced at the stage boundary.
- **An unreachable source is never an adverse finding.** Unverifiable claims never move the score in either direction.

The FinanceBench figure (81% incorrectly answered or refused over public filings) explains why constraint matters here. Use it to frame, not to dunk on competitors.

### 9. The co-pilot loop
**Say:** "The run produced 57 open questions. That is the product's main surface, not its failure mode."

The routing is the insight, **33 / 5 / 19**:
- **33** answerable from a document we don't have. Request the PPM; many close in one action.
- **5** answerable by an analyst. Attest with a required source, recorded as attested, never as document-grounded.
- **19** externally blocked. **Do not send these to the manager.** Routed to an owner instead (Infrastructure 11, Procurement 5, Analyst 3).

**Why this matters:** a co-pilot that treats all three identically is annoying. Inviting an analyst to "answer" an unperformed register check is a broken affordance.

**Ticking a box never closes a question**, only a re-run does. Otherwise you could close 57 questions in 57 clicks without the engine reading a page.

### 10. Why it becomes yours
**Say:** "Our 17 seed criteria are placeholders. The seed deliberately does not even activate itself, so an admin has to look at the rules before any deal is scored."

- Sets are **versioned and frozen**; editing an active set clones a draft.
- Every memo records **which rules scored it**, so a memo read six months later is interpretable under the rules that produced it.
- **Tier is a policy choice.** We moved "no attributable track record" from veto to red flag, because a veto silently rejects every first-time manager. An institution that wants it disqualifying promotes it to veto in their own set. That is exactly what criteria authoring is for.

### 11. The management system: roles and pipeline
**New slide.** The deck previously said nothing about the platform around the engine, which was the stakeholder's specific gap.

**Say:** "Everything from here to slide 13 is specified, not built. I'll flag that again on the limits slide."

**The ODD asymmetric veto is the detail that lands with this audience**, because it mirrors how their own ODD function actually works and most software gets it wrong.

- ODD is **not a stage** a deal passes through. It is a parallel track with its own entity, lifecycle, rating scale and reporting line.
- **A failing review blocks advancement into commitment. A passing review advances nothing.** There is no event by which ODD moves a deal forward, because in reality there is no such power.
- It is enforced **at the permission layer**, not by UI convention: the ODD Reviewer holds no `DEAL_TRIAGED` and no `DEAL_STAGE_ADVANCED` permission. There is literally no event they can emit that moves a deal forward. An ODD Reviewer does not even see the pipeline board.

**If someone says "our ODD reports to the COO, not the CIO":** that is the right reaction, and the answer is that the model assumes exactly that. The reporting line is the reason the permission split exists.

**The passed-deals point is the cheap differentiator.** Most allocators do not track what they declined, so they cannot answer *how good are we at saying no?* The data already exists at the moment of declining; nothing asks them to record it in a form that aggregates. The line that lands: *"This manager is back with Fund III. You passed on Fund II. Here is exactly why, in the words of the analyst who decided."*

### 12. Documents, versions, and the causal diff
**Say:** "Documents are addressed by content hash, so a deal accumulates its own history."

- **Content-addressed and deduplicated.** The storage key is `sha256(bytes)`; the filename is display metadata. Two analysts forwarding the same deck produce one blob and one deduplication event.
- **A deal accumulates documents across vintages.** Fund II's deck sits alongside Fund I's, so you can see how a manager's story changed rather than only what it says today. Allocators do not have this from a folder of decks named by whoever saved them.
- **The re-run loop.** An open question closes by uploading a document or attesting a fact with a checkable source. Re-run produces a new *version*; prior versions stay frozen and downloadable.
- **The diff is causal, not textual.** Two memos from a non-deterministic model differ on nearly every line, so a prose diff would make the tool look like it changed its mind arbitrarily. The finding-level diff names the evidence, the page, and the prior state.

⚠️ **The CR-0030 example on this slide is marked ILLUSTRATIVE and you must present it that way.** It is drawn verbatim from PRD 08 §4, where it is a worked example of the diff format. It is **not** real engine output, and `screen-version-history.md` §9.4 flags the PPM page references as invented for illustration. Say *"this is the format, on a worked example"*. Do not say "here is a diff we produced". The badge on the slide says ILLUSTRATIVE for exactly this reason; if you talk over it as though it were real output, the badge becomes a fig leaf rather than a disclosure.

### 13. The information request writes itself
**New slide, and the newest feature. Specified, not built.**

**Say:** "The memo already knows what is missing and why. So it can write the request to the manager."

The argument is that this falls out of structure the engine already produces, rather than being a new capability bolted on:
- Every unresolved item states **what is missing and what was searched for**.
- Every criterion carries a **`remediation_prompt`**: what to ask if it fires.
- The memo's section 10 already assembles those into asks.

Two details to show:
- **It is specific.** Not "please send more information", but the net-to-investor IRR for the predecessor fund, the key-person provision, the valuation policy for unlisted assets, GP commitment as a percentage of fund size. Those five items on the slide are the real `remediation_prompt` texts from the criteria file, lightly compressed for the slide.
- **It excludes the externally-blocked items automatically.** No manager can answer a question about a register the platform could not reach. The routing already exists in the data as `kind = EXTERNALLY_BLOCKED`, so **the email is correct by construction rather than by the analyst remembering.** That is the sentence worth saying slowly.

**An analyst reviews and sends it.** Do not let this be heard as "the system emails your managers automatically". It drafts; a person sends.

### 14. Economics and scale
**Say:** "These are measured on the reference deck, not modelled."

$2 to $4 and 8 to 16 minutes per full analysis is the documented band. **Flag the 6× variance honestly**, and budget the worst case rather than the median.

Then the three structural points: stateless per run (parallelises without coordination), event-sourced management layer (every state change auditable, with an actor and a timestamp), on-premise or laptop (SEBI confidentiality). Market-agnostic core: another regime is a change of criteria and diligence sources, not a rewrite.

### 15. The limits
**Do not rush this slide. It earns more credibility than it costs.**

**Say:** "We'd rather you hear these from us."

- **Pre-MVP.** Engine real, management UI specified. Slides 3 and 6 to 9 are real output; slides 11 to 13, including the generated information request, are specification.
- **Two regulatory checks were unevaluated on the reference run, and regulatory verification is in build.** See the correction note below. Do not describe this as a geo-fence.
- **~4% of quotes fail mechanical verification** on column-heavy slides. Retained and flagged, never hidden. The verifier is tuned strict on purpose.
- **Contested findings vary between runs.** Surfaced, not smoothed.

### 16. The ask
**Say:** "The engine is validated on one deck. What it needs now is your rules and your decks."

Three asks: a criteria workshop (they keep the set regardless), three already-screened decks (compare our memo to the conclusion they reached, the only benchmark that counts), and one pilot deal run end to end through the loop.

**The third ask changed.** It used to be an India-hosted runner, which is no longer needed. The pilot deal replaces it and is the better ask anyway: it tests the workflow rather than the engine, which is the part we have the least evidence for.

**Close on:** *"If the analysis isn't good enough to change an analyst's mind, no amount of management-system polish rescues it. That's why we built the engine first, and why we're showing you its output before its interface."*

---

## Correction: the SEBI checks were never geo-fenced

**This changed on 2026-07-21 and the deck has been updated. Do not present the old story.**

The earlier diagnosis was that SEBI's register was geo-fenced from our network egress, that two veto-tier checks therefore could not be performed, and that the fix was an India-hosted runner. **That was wrong.** It is still repeated in `07-evidence-loop.md` §3, in the screen specs, and in the reference run's own section 11 text, none of which have been corrected yet. The deck no longer says it.

**What is actually true, verified directly:**

- The machine is **already in India** (Reliance Jio, Ahmedabad). `run.json` records `egress_country: IN`.
- `curl` with its **default user-agent** gets **HTTP 530**.
- `curl` with a **browser user-agent** gets **HTTP 200** and 57KB of real SEBI content.

It was ordinary bot filtering on a default client string, not a network block, and not geography. **Both SEBI-dependent veto criteria are implementable now** and an engine agent is building them.

**How to present it:** *"Two veto-tier regulatory checks were unevaluated on this run. We originally diagnosed a geo-fence; that was wrong. The register rejects a default client string and returns normally to a browser user-agent, so it's ordinary bot filtering. Both checks are implementable and in build. Until they ship, the honest claim is document-grounded analysis with regulatory verification pending."*

**Why volunteer that we got it wrong.** Because the reference run's own output still contains the old diagnosis in detail, and a technically curious allocator who reads section 11 will find it. Being the one who corrects it is far better than being caught by it. It also demonstrates the thing the deck claims: findings are checkable, so when a finding is wrong it can be found and fixed.

**If asked "so will the recommendation change?"** Possibly, and that is the point of the version model. `CR-0001` is a CRITICAL veto. If it fires on a re-run, the recommendation becomes VETOED. A veto becoming evaluable is the most consequential kind of diff the platform can produce.

---

## The three questions you will be asked

### 1. "How do I know it isn't hallucinating? These systems make things up."

**Answer:** "You don't have to trust it, that's the design. Three mechanical guarantees, none of which involves asking a model to check itself:

- Every quote is verified **in code** against the text of the page it cites. On the reference run, 102 of 105 matched. The three that didn't are **flagged as unverified**, not dropped and not presented as verified.
- Every number in the memo must trace to an extracted value, **or the run fails**. That's an invariant, not a quality target.
- The memo cannot contradict its own scorecard, checked at the stage boundary.

And the verifier is deliberately tuned strict. We could close that last 4% with fuzzy matching, but then it would start accepting quotes that aren't on the cited page. A visible unverified quote is safe; a silently accepted fabricated one is the failure this whole design exists to prevent."

**If pushed:** the engine doesn't invent concerns. It reports criteria hits ("CR-0010 fired, here is the evidence") against rules the institution authored.

### 2. "Your criteria aren't our house view. Why would we use someone else's judgement?"

**Answer:** "You wouldn't, and you're not being asked to. The 17 criteria you saw are seeds, explicitly placeholders. The seed set ships in draft and **deliberately does not activate itself**, so an admin has to review the rules before a single deal is scored.

You author the red flags, green flags and vetoes. You set the thresholds. You choose the tier, and tier is a real policy lever: we moved 'no attributable track record' from veto to red flag because a veto silently rejects every first-time manager. If you *want* that disqualifying, you promote it to veto in your set.

Sets are versioned and frozen on activation, and every memo records which rule set scored it. So when your IC challenges a recommendation eight months later, you can answer exactly which rules produced it. Change a rule, re-run, and watch the score move."

### 3. "You can't actually check SEBI registration. Isn't that the whole point for an Indian AIF?"

**Answer, updated 2026-07-21:** "It was the sharpest limitation we had, and we got the diagnosis wrong. We thought SEBI's register was geo-fenced. It isn't. The site rejects a default client user-agent and returns normally to a browser one, which is ordinary bot filtering. We're in India already. So both veto-tier checks, registration validity and enforcement history, are implementable now and are being built.

On the run I showed you, they are still reported as **unevaluated**, and section 11 is non-excludable so your IC sees that too. Three things hold regardless. First, the engine **never scores an unreachable source as adverse**: an unavailable check is reported as unavailable, never as a finding against the manager. Second, it also never reads as a pass: the memo says *'no veto fired, but no veto was cleared either.'* Third, no analyst attestation can substitute. 'The manager says they're registered' is precisely the claim an independent register check exists to verify, so we don't let anyone attest their way past it.

Until those checks ship, the honest claim is **document-grounded analysis with regulatory verification pending**, and we won't describe it as SEBI regulatory diligence until it is."

---

## Numbers you must get right

Every figure in the deck is traceable. Do not round or embellish.

**All figures below are from the clean verification run `022c6853` in `/tmp/l1-final-verify/`**, the newest and authoritative run. Earlier runs (`fd33c73e`, `299273b1`) are superseded; do not quote them.

| Claim | Value | Source |
|---|---|---|
| Source document | 52 pages, 5.6 MB, Feb 2026 | `run.json` |
| Citations verified | 102 of 105 (97.1%), across 25 pages | `05-memo/12-sources.md` |
| Quotes verified, all stages | 121 of 124 | `run.json` telemetry totals |
| Classification quotes | 7/7 | `status.jsonl` |
| Extraction quotes | 45/45 | `status.jsonl` |
| Scoring evidence quotes | 69/72 | `status.jsonl` |
| Criteria evaluated | 17 (2 veto / 9 red / 6 green) | `03-criteria.md` §11 |
| Red flags fired | 5: CR-0010, CR-0011, CR-0012, CR-0014, CR-0016 | `05-memo/01-recommendation.md` |
| Green flags fired | 1: CR-0033 | `05-memo/01-recommendation.md` |
| Weights | red 14.0 vs green 1.0 | `05-memo/01-recommendation.md` |
| Contested | 2: CR-0012, CR-0014 | `05-memo/09-contested-findings.md` |
| Vetoes unevaluated | 2: CR-0001, CR-0002 | `05-memo/01-recommendation.md` |
| Open questions | 57, routed 33 document / 5 analyst / 19 blocked | `05-memo/11-open-questions.md` |
| Blocked owners | Infrastructure 11, Procurement 5, Analyst 3 | `05-memo/11-open-questions.md` |
| Egress country | IN | `run.json` `environment.egress_country` |
| Cost / duration (documented band) | $2 to $4, 8 to 16 min (6× variance) | PRD 06 §7 |
| Cost / duration (clean verify run) | $5.70, ~17 min, **outside the PRD band** | `run.json` |
| Single-criterion re-test | 92s / $1.01 vs 23min / $6.06 full run | measured, engine README |

### Slide 3 per-stage figures

All from `run.json` `telemetry.stages`, run `022c6853`. Rounded to whole seconds and cents for the slide.

| Stage | Wall clock | Cost | Note |
|---|---|---|---|
| Classify | 29.81s | $0.5985 | 7/7 quotes verified |
| Extract | 159.35s | $1.1982 | 45/45 quotes verified |
| Verify (diligence) | 1.60s | $0.00 | 0 model calls; calls registers, not a model |
| Score | 642.71s | $2.9799 | 2 model calls, the lenient and strict passes |
| Memo | 200.72s | $0.9231 | 12 sections |
| **Total** | **1034.19s (~17 min)** | **$5.6997** | 5 model calls, 0 retries, 0 fallbacks |

Bar lengths on the slide are proportional to wall-clock seconds, and the seconds are printed alongside every bar, so length is never the only channel carrying the number.

### Slide 5 criteria framework

Every count is verified directly against `engine/criteria/default/criteria.yaml`, the file the engine actually reads. Not from a PRD, and not from the memo.

| Dimension | Count | Tier split |
|---|---|---|
| Governance | 7 | 3 red, 4 green |
| Track record | 3 | 2 red, 1 green |
| Regulatory standing | 2 | 2 veto |
| Disclosure quality | 2 | 2 red |
| Fees and terms | 2 | 1 red, 1 green |
| Concentration | 1 | 1 red |
| **Total** | **17** | **2 veto / 9 red / 6 green** |

The category labels on the slide are the file's own `category` values, lightly expanded for reading: `governance`, `track_record`, `regulatory`, `disclosure`, `fees`, `concentration`. The tier totals match `03-criteria.md` §12 and the seed-set panel on slide 10.

**One weight worth knowing** if the question comes up: CR-0018 ("no attributable prior track record") carries **weight 3.0** while every other criterion is 1.0. That is the deliberate compromise behind the "moved from veto to red flag" story: it is not disqualifying, but it is weighted three times heavier than anything else in the set.

### Slide 13 information-request items

The five items shown are the real `remediation_prompt` texts from `engine/criteria/default/criteria.yaml`, compressed for slide width. They correspond to CR-0010, CR-0012, CR-0016, the GP-commitment criterion, and CR-0014. The memo's own section 10 assembles the same set and separates manager items from the internal infrastructure item, which is the routing the slide describes.

### Corrections made against the source brief

Claims that did **not** survive verification and were changed. Do not reintroduce them:

- **"p.25's headline says ~1,900 crore while its own table totals 1,860, and the engine refused to average or correct it."** **Cut from the deck.** The distinction is subtle and worth stating precisely, because a colleague re-checking the artifacts *will* find the number.

  The discrepancy is **real in the source document** (600+360+250+250+200+200 = 1,860 against a "~1,900 crore" headline). And the engine **does** cite 1,860; it appears in `04-scoring.json`, `05-memo.json`, `05-memo/04-risk-factors.md` and `09-contested-findings.md`. It uses the figure as **evidence of counterparty concentration** for CR-0014. It never compares it against page 25's own "~1,900 crore" headline (the string `1,900` appears nowhere in any artifact) and it never flags the inconsistency.

  So: *"the engine cited a figure from page 25"* is true. *"The engine caught the deck's headline contradicting its own table"* is not. Only the second would be impressive, and claiming it would be exactly the overclaiming this deck exists to avoid. **Do not present it.** It is, separately, a strong candidate for a future criterion: an internal-arithmetic-consistency check.

- **"~$2 to $6 per deck" / "8 to 23 minutes."** The deck uses **$2 to $4 and 8 to 16 minutes**, per PRD 06 §7.

  ⚠️ **Know this before you quote the band.** The clean verification run came in at **$5.70 and ~17 minutes**, outside the PRD's stated range. Slide 3 shows those real numbers; slide 13 shows the documented band. **If someone notices the two slides disagree, that is a fair catch and the answer is that the PRD band is being widened to match observed runs.** Given the acknowledged 6× variance, "single-digit dollars and under half an hour per deck" is the safest verbal framing. Do not quote a tight number you would have to walk back.

- **"92 seconds to test one criterion."** **Reinstated as usable, but not currently on a slide.** The figure is real and measured: 92s / $1.01 to re-test a single criterion, against 23min / $6.06 for a full run, sourced from the `test-criterion` agent's measured output (engine README). It is not in any PRD or run artifact, so cite it as *"measured, engine README"* rather than implying it is in the documented artifact set. Useful if slide 10 draws a question about iteration speed: changing one rule does not cost a full re-analysis.

  Note this is distinct from an **evidence re-run**, which *is* a full re-analysis at full price, which is why the confirmation dialog states the cost before the click.

- **"SEBI is geo-fenced."** **Removed entirely.** See the correction section above.

### Provenance of the management-system slides (11 to 13)

Everything on these three slides is specification, drawn from the PRDs. Nothing on them is running software.

| Claim on the slide | Source |
|---|---|
| Four roles: Analyst, Super Admin, IC Member, ODD Reviewer | `00-overview.md` §1; `01-intake.md` §6 roles table |
| ODD Reviewer reports to the COO, not the CIO | `04-triage.md` §1.2; `user-journeys.md` |
| "The power never to hire, never the power to hire" | `04-triage.md` §1.2, verbatim |
| Failing review blocks `DEAL_STAGE_ADVANCED` into `COMMITMENT`; passing advances nothing | `04-triage.md` §1.2 |
| ODD holds no `DEAL_TRIAGED` / `DEAL_STAGE_ADVANCED` permission | `04-triage.md` §6 |
| ODD Reviewer sees no pipeline board | `screen-deal-list.md` §7 state J |
| Six canonical stages, ODD deliberately not among them | `04-triage.md` §1.1 |
| Centre of gravity is `INITIAL_SCREENING` | `04-triage.md` §1.1 |
| Passed deals as a first-class outcome; the lost counterfactual | `04-triage.md` §1.4 |
| Storage key is `sha256(bytes)`; filename is metadata | `01-intake.md` §1, §2 |
| Deduplication produces one blob and one event | `01-intake.md` §1, §3 |
| A deal accumulates documents across vintages | `00-overview.md` §4; `01-intake.md` §1 |
| Upload a document or attest with a required source | `07-evidence-loop.md` §2.2, §2b |
| Re-run creates a new version; prior versions frozen and downloadable | `07-evidence-loop.md` §2.1 |
| The causal diff, and why a text diff fails | `08-version-history.md` §1, §4 |
| CR-0030 worked example (**illustrative**) | `08-version-history.md` §4.1; flagged invented in `screen-version-history.md` §9.4 |
| Criteria versioned, frozen on activation, memo records the set | `03-criteria.md` §1; `00-overview.md` §6.2 |
| Event-sourced, actor and timestamp on every state change | `00-overview.md` §5; every PRD's §3 event payloads |
| `remediation_prompt` per criterion feeds memo §10 Asks | `03-criteria.md` §2; `05-memo.md` §2.1 |
| `kind = EXTERNALLY_BLOCKED` routing excludes items from manager questions | `07-evidence-loop.md` §1, §3, §4 |
| 33 / 5 / 19 routing on the reference run | `05-memo/11-open-questions.md` |

⚠️ **One number discrepancy worth knowing.** PRD 07 describes the routing against an earlier 49-question run (12 / 25 / 6 there). The deck uses the current run's 57 questions routed 33 / 5 / 19, from the memo itself. If someone has read the PRD, the PRD is describing an older run, not contradicting the deck.

⚠️ **A second one, in the raw JSON.** `05-memo.json` carries six `ANALYST_ANSWERABLE` entries while the memo's own section 11 heading says five. The deck follows the memo. If challenged, the memo markdown is the artifact of record and the difference is one item's classification, not a change to the total of 57.

### Run-to-run variance: know this cold

Three runs exist and they do **not** agree. Open questions went 49 → 59 → **57**; red flags 4 → 4 → **5**; weights 11.0 → 11.0 → **14.0**. The deck cites the newest run (`022c6853`) throughout.

**If an allocator notices, do not get defensive. This is the honest answer:**

> "Runs vary. The contested findings are exactly where the two evaluation passes disagree, and we surface that rather than averaging it away. CR-0012 fired in this run at low confidence and contested; in an earlier run it did not fire at all. That variance is visible in the output instead of hidden by it, which is why prior versions stay frozen and why the memo prints both readings."

This is slide 15's fourth limit made concrete. It is a credibility opportunity, not a problem, but only if you volunteer it rather than being caught by it.

---

## Practical notes

- **Verify the slide-2 statistics before presenting**, or present them explicitly as framing. This is the one place the deck is exposed.
- **Do not name the fund.** See the anonymisation note at the top.
- Have `/tmp/l1-final-verify/05-memo/` open in a second window. If anyone asks "show me the rest", open `11-open-questions.md`: all 57 entries with their search accounts. It is the most convincing artifact in the project. **Note that its section 11 text still contains the superseded geo-fence diagnosis**, so be ready to explain that if you open it.
- If asked for a live run: it takes 8 to 16 minutes, so start it before the meeting and show the finished artifacts.
- Dark mode (`◐`) is better on a projector in a bright room.
- **Em dashes have been removed from the deck and these notes**, except inside verbatim quoted output on slides 7 and 12, where changing the text would misrepresent a quotation.
