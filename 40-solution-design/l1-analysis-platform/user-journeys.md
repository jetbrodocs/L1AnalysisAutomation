---
title: "User Journeys — L1 Analysis Platform"
status: draft
created: 2026-07-20
updated: 2026-07-20
tags: [prd, user-journeys, narrative, roles]
---

# User Journeys — L1 Analysis Platform

> **Companion document to the PRDs.** Per `00-inbox/prd-guide.md` §10, this is a narrative, not a contract. The PRDs say what to build; this says what it should feel like to use.
>
> Every journey below uses the real reference case: **Neo Infra Income Opportunities Fund II (NIIOF-II)**, a SEBI Category II AIF targeting ~₹5,000 crore in infrastructure credit, whose 52-page February 2026 deck is the platform's standing end-to-end test (`00-overview.md` §8). The data is real. The people are invented but the roles are not.

---

## Cast

| Person | Role | Where they sit |
|---|---|---|
| **Priya Raghavan** | Analyst | Investment team. Covers private credit and infrastructure |
| **Ashwin Menon** | Super Admin (Head of Research) | Investment team. Owns the criteria set. Reports to the CIO |
| **Meera Krishnan** | IC Member | Investment committee. External member, meets monthly |
| **Devika Rao** | ODD Reviewer | Risk & GRC. **Reports to the COO, not the CIO** |
| **Sanjay Iyer** | Standalone CLI user | Consultant. No login to the platform at all |

---

## Priya Raghavan — Analyst

### Who she is

Priya covers private credit and infrastructure at a mid-sized Indian allocator. She receives somewhere between eight and fifteen fund decks a week, mostly by email from placement agents, and she is the bottleneck the platform exists to relieve. Before the platform, a deck that arrived on Monday might get properly read on Thursday, and whether it got read properly depended on how her week was going.

### Her typical workflow

**Monday morning: a deck arrives**

1. A placement agent emails Priya a PDF: `Neo Infra Income Opportunities Fund-II Feb'26.pdf`, 5.6 MB.
2. She opens the platform, clicks **Upload Document**, and drags the file onto the drop zone. She does not rename it. She does not need to — the platform addresses it by content hash, not filename, and the apostrophe in `Feb'26` that would break a filesystem-keyed system is simply metadata here.
3. The upload completes in about two seconds. The screen shows: *"DOC-2026-000142 · sha256 2b176083… · 52 pages · classified as Pitch Deck."*
4. A banner appears: **"This appears to be Neo Infra Income Opportunities Fund II from Neo Asset Management Private Limited. We do not currently track this fund. Create a new Deal?"**
5. Priya recognises the manager. She types "Neo" into the manager field and the platform offers **MGR-0037 — Neo Asset Management Private Limited**, showing *3 prior deals, 1 commitment, 1 pass*. She selects it.
6. The banner updates: **"Known manager. This will be tracked as a RE-UP. Entry stage: Initial Screening."** Below it, in smaller text: *"Prior fund: NIIOF-I (DL-2024-0031) — Committed ₹200 crore, March 2024. ODD rating: Satisfactory with Observations."*
7. Priya sets priority to **Normal**, confirms the AIF category as **Cat II**, and clicks **Submit for Analysis**.
8. The screen confirms: *"DL-2026-0089 created. RUN-2026-000318 queued. Criteria set CS-2026-0001 v3 (17 criteria)."*

She goes to make coffee. This has taken ninety seconds.

**Monday morning, four minutes later: watching it run**

9. Priya opens **Run Progress** on RUN-2026-000318. She sees five stages, not a spinner:

```
✓ Classification    completed   12s
● Extraction        running     4m 12s   —  core schema 3 of 7
○ Diligence         pending
○ Scoring           pending
○ Memo              pending
```

10. The progress line updates every few seconds. This matters more than it sounds — before, a long-running job with no feedback would have her wondering at minute four whether it had hung, and she would have refreshed, cancelled, and resubmitted at least once.
11. Twenty-six minutes after submission, the run completes. Cost: **$1.42**. A notification appears in her queue: *"MEMO-2026-000318 ready — NIIOF-II — Recommendation: PURSUE."*

**Monday afternoon: reading the memo**

12. Priya opens the **Memo Reader**. The recommendation is at the top, where it belongs:

> **1. Recommendation — PURSUE**
> Pursue to a manager meeting. Eleven items require clarification before an IDD decision, four of them material to the return profile.

13. Directly beneath the header, in the memo's summary bar, a line she cannot miss: **"⚠ 3 items could not be determined — jump to section 11."** It is not collapsed, not in a tab, not below twelve sections of scrolling.
14. She clicks it and lands on section 11:

> **11. What We Could Not Determine**
> - **SEBI registration number** — no registration number appears in any of the 52 pages. The SEBI intermediary register was reachable and returned a match on manager name, but the fund-level registration could not be confirmed from the document.
> - **Net-to-investor return figure** — no net IRR figure located anywhere in the document.
> - **NIIOF-I realised DPI** — the predecessor's performance is described as tracking to target; no realised distribution figure is stated.

15. Priya scrolls back to section 4, **Risk Factors**. Three red flags fired. The first:

> **CR-0010 — Gross-only return disclosure** · RED FLAG · HIGH
> Returns are stated on a gross basis throughout with no corresponding net-to-investor figure.
> **Evidence**: p.5 *"Gross Returns ~ 18-20% p.a."* · p.37 *"Expected IRR ~ 18-20% p.a."*
> **Absence evidence**: No net-to-investor IRR figure located in any of 52 pages. Searched for: "net IRR", "net return", "net to investor", "after fees", post-fee illustrations, and the fee/waterfall section on pp. 40–43.

16. She clicks **p.37**. The source deck opens to page 37 with the quote highlighted — the actual page image, so she can see the chart the number sits next to. Two clicks from an assertion to the words that support it.
17. This is the finding she would have caught herself, on page 37, on Thursday. The engine caught it on Monday and told her what it searched to be sure the net figure was genuinely absent rather than merely unfound.
18. She marks section 4 **Reviewed** with `r`, and moves on with `j`.

**Monday afternoon: an override**

19. Section 4's third finding is **CR-0017 — Stale marketing document** · RED FLAG · LOW, firing because the deck is dated February 2026 and it is now July.
20. Priya knows something the document cannot contain: she spoke to the placement agent last week and the terms are unchanged; Neo is running a longer fundraise than planned because they are being selective about LPs. The finding is technically correct and materially misleading.
21. She clicks **Override** — and the form stops her. External knowledge is not one of the five override reasons. Instead it says: *"This isn't a misreading of the document — it's information the document doesn't contain. Add it as evidence so the next analysis can use it."* and offers **Add attestation** on `CR-0017`.
22. She takes it. The attestation form requires a source, which she fills: *"Confirmed with placement agent 14 July 2026 — terms unchanged since Feb, fundraise extended deliberately for LP selection, not for lack of demand."* It is recorded as **analyst-attested**, labelled as such wherever it appears, and will feed the next run rather than annotating this one.
23. The current memo body does **not** change and the score is **not** recalculated. Priya notices the distinction and, on reflection, prefers it: had she overridden, she would have annotated one memo and changed nothing while believing she had corrected the analysis. As an attestation, the same sentence propagates into v2 and can actually stop `CR-0017` firing — with her name on it.

> **Why the form refused.** Override and attestation look interchangeable to a user and behave oppositely: an override is inert, an attestation feeds the next run and costs 8–16 minutes and ~$2–4. Same knowledge, same words, entirely different outcome depending on which button the analyst happened to find first. PRD 05 §"Why `EXTERNAL_KNOWLEDGE` was removed" is the rule; this is what it looks like from the analyst's side.

**Monday afternoon: the triage decision**

23. Priya finishes all twelve sections. The memo status moves to **Reviewed**.
24. She clicks **Triage**. The form asks for a decision and a rationale, and shows the memo's recommendation: **PURSUE**.
25. She selects **PURSUE**, cites findings `CR-0010` and `CR-0011`, and writes: *"Manager is known and NIIOF-I has performed in line. The gross-only disclosure and the unrealised predecessor record are both real and both answerable in a meeting. Recommend manager meeting with the section 10 asks put in writing beforehand. Re-up, so ODD refresh rather than full."*
26. She submits. `agreed_with_memo` computes to **true**. The deal moves — separately, deliberately — when she clicks **Advance to IDD**.
27. She requests an ODD review, type **Refresh**, referencing ODD-2024-0006 from NIIOF-I, with scope notes: *"Focus on valuation policy for unlisted infra credit — L1 flagged CR-0016 as not addressed in the deck."*

**What success looks like for Priya**

By Monday evening, a deck that arrived that morning has been read, scored against house policy, evidenced to the page, triaged with a written rationale, and handed to ODD — and the eleven questions for the manager meeting are already written, in section 10, ready to be sent. She spent about forty minutes on it, most of it reading and thinking. Before, this was Thursday's job and took most of an afternoon, and the eleven questions were whatever she remembered to ask.

### When things go wrong

**The engine fails mid-run.** Wednesday, a different deck. Priya's run shows **FAILED — STAGE_FAILURE at diligence, attempt 1 of 3, next retry 14:22**. She does nothing; the sweeper requeues it and attempt 2 completes. She sees the failure only in the run history, which is where it belongs.

**The engine burns the budget.** A 340-page PPM exits **21 — budget exceeded** at $4.00. Not retryable. Priya opens the run, sees the failure, and asks Ashwin to raise the ceiling — she cannot do it herself, and she is glad, because the ceiling is the only thing standing between the platform and a surprise bill.

**A duplicate arrives.** Friday, a second placement agent forwards the same Neo deck. Priya uploads it out of habit. The platform responds instantly: *"Duplicate of DOC-2026-000142, uploaded 20 July by you. No analysis queued."* On the Deal Detail page a line now reads *"This deck has reached us from 2 sources."* She notes it — broad marketing rather than selective approach, which is mildly informative about how Neo is running the raise.

**The wrong Deal is proposed.** A deck arrives for "Neo Special Situations Fund I". The platform proposes attaching it to DL-2026-0089 (NIIOF-II) because the manager matches. Priya catches it and clicks **Create New Deal instead**. Had she not, two funds' evidence would have merged into one memo — which is exactly why the platform proposes and never auto-attaches.

**No criteria set is active.** On her very first day using a fresh deployment, Priya uploads a deck and hits: *"No active criteria set covers Cat II. A criteria set must be activated before deals can be analysed."* The seed set ships in Draft deliberately (PRD 03 §11). She messages Ashwin. It is an annoying first-run experience and it is the correct one — nobody should be scored against rules no human has looked at.

---

## Ashwin Menon — Super Admin (Head of Research)

### Who he is

Ashwin runs research and owns house diligence policy. He is the person who decides what the institution rejects, which makes him the person who authors criteria. He does not read every deck; he reads the ones that matter and he reads the aggregate.

### His typical workflow

**Quarterly: tuning the criteria set**

1. Ashwin opens **Criterion Performance**. Two columns matter, side by side: fire rate and override rate.
2. `CR-0017` (stale document) has fired on **71%** of deals this quarter and been overridden on **48%** of those firings, most commonly for `CRITERION_TOO_BROAD` — and it carries the platform's highest count of analyst attestations, nearly all saying some version of *"spoke to the manager, terms unchanged."* That is a badly calibrated rule firing constantly, with analysts disagreeing half the time and routinely doing manual work to neutralise it.
3. He also sees `CR-0035` (independent investment committee) with **0 firings in 40 deals**. A rule that never fires is either perfectly satisfied by every manager — implausible — or worded so that nothing can satisfy it.
4. Ashwin opens CS-2026-0001. It is **ACTIVE**, so every edit control is gone, replaced by a single **Clone to Draft** button. He clones it to CS-2026-0002.
5. He edits `CR-0017`'s detection guidance to *"more than nine months prior to analysis, or references a first-close or final-close date that has already elapsed without a stated extension"* — narrowing it to the case that actually signals something.
6. He rewrites `CR-0035`'s guidance, which had required the IC's *authority over deal approval* to be *stated*, a phrasing almost no deck satisfies even when an independent IC exists.
7. He activates CS-2026-0002 with `supersedes_set_id` = CS-2026-0001. The platform requires the supersession because both sets scope Cat II and two active sets would silently compete.
8. **Deals scored last week keep their v3 attribution.** Priya's NIIOF-II memo still says CS-2026-0001 v3, and its criteria content hash still matches. Ashwin's edit did not retroactively reinterpret a memo somebody already acted on.

**Monthly: the funnel**

9. Ashwin opens the **Funnel Report**. This quarter: 47 deals entered initial screening, 19 advanced to IDD, 6 reached IC, 3 committed.
10. He opens **Pass Reason Stats**. The most common reason for declining, by a distance, is `TRACK_RECORD_INSUFFICIENT` — 41% of passes, almost all at initial screening.
11. This is the number that changes his mind about something. The institution's stated policy is that it is open to emerging managers. Its revealed policy, measured across 28 declines, is that it screens them out at the first gate on track record. Nobody decided that. It emerged.
12. He also checks **memo agreement**: analysts agreed with the engine's recommendation on **83%** of decisions this quarter. He is more interested in the 17% than the 83%, and clicks through to read the seven decisions where a human went the other way.

**Occasionally: an override he cannot make**

13. A deal reaches IC with a blocking ODD rating. The investment team wants to proceed. Ashwin, as Super Admin, opens Deal Detail and finds that **the Advance to Commitment control is disabled**, with the reason stated: *"Blocked by ODD-2026-0021 — Unsatisfactory. This gate requires ODD concurrence."*
14. He can override it, but only by recording Devika's concurrence in the rationale — and Devika has not given it. He does not override. He calls her instead, which is what the control is designed to produce.

**What success looks like for Ashwin**

House policy is written down as rules rather than carried in people's heads, every change to it is attributable and dated, and the aggregate of forty individual screening decisions is visible as a picture of what the institution actually does — including where that differs from what it says it does.

---

## Meera Krishnan — IC Member

### Who she is

Meera is an external member of the investment committee. She meets the team monthly, reads what is sent to her, and has no involvement in the analysis. She has been on ICs for twenty years and her instinct with any new tool is to ask what it is hiding.

### Her typical workflow

**A week before the IC meeting**

1. Priya exports an **IC Packet** for NIIOF-II. The export form does not offer to exclude section 11 — the checkbox is present but fixed on, with a tooltip: *"What We Could Not Determine cannot be excluded from an export."* Meera never sees this, but it is the reason for what she reads next.
2. Meera receives EXP-2026-000051, a PDF. Its cover page reads:

> **NIIOF-II — Neo Infra Income Opportunities Fund II**
> Neo Asset Management Private Limited · SEBI Cat II AIF · Target ~₹5,000 crore
> Recommendation: **PURSUE** · Analyst: Priya Raghavan · 20 July 2026
> Scored against criteria set **CS-2026-0001 v3** · hash `2b17…3562`
> Re-up · Predecessor NIIOF-I, committed ₹200 crore March 2024

3. She reads section 1 and then, as she always does, goes looking for what is missing. She finds it in section 11 without having to look for it — three items, stated plainly, including that no net-to-investor return figure exists anywhere in a 52-page document asking for ₹5,000 crore.
4. **This is the moment the platform earns her trust.** Her experience of investment memos is that the gaps are the last thing anyone writes down and usually not written down at all. A memo that leads with what it could not establish is one she can interrogate.

**At the IC meeting**

5. Meera asks: *"Section 4 says the return disclosure is gross-only. How do we know there is no net figure — did anyone actually look, or did the tool just not find one?"*
6. Priya opens the memo on screen and reads the absence evidence aloud: the six search terms and the specific pages checked. Meera accepts it. Under the old process the honest answer would have been "I read the deck and I don't remember seeing one."
7. She asks about `CR-0017`, the staleness flag she can see was overridden. Priya's justification is right there against the finding, with her name and the date. Meera reads it and moves on.
8. The IC decision is not "commit". It is **PURSUE to a manager meeting**, with the section 10 asks sent in writing beforehand — which is what a real IC does with a screening memo, and what the memo recommended.

**When the answer is no**

9. A different deal, three months later. Meera's committee declines it. She records **IC_DECLINED** with reason `TERMS_UNACCEPTABLE` and a rationale: *"2.5% on committed capital with a full catch-up and an 8% hurdle. We do not pay for beta. If they come back at 2% with no catch-up we would look again."*
10. That sentence is the one that matters eighteen months later, when the manager returns with revised terms and nobody remembers what the objection was.

**What success looks like for Meera**

She can tell, from the document in front of her, what the analysis established, what it could not, which rules produced the recommendation, where a human disagreed with the machine and why. She never has to ask "what aren't you telling me", because the memo's eleventh section answers it before she does.

---

## Devika Rao — ODD Reviewer

### Who she is

Devika conducts operational due diligence. She sits in Risk & GRC and **reports to the COO, not the CIO**. This is not an org-chart detail — it is the entire basis of her function. Her job is to be the person whose assessment does not improve when a deal is attractive.

### Her typical workflow

**Picking up a review**

1. Devika logs in. She does not see a pipeline board. There are no deal cards, no stage columns, no "Advance to IC" buttons anywhere in her navigation. Her landing screen is the **ODD Queue**.
2. Three reviews are open. ODD-2026-0022 — NIIOF-II — **Refresh**, requested by Priya Raghavan four days ago, target date 14 August. Scope notes: *"Focus on valuation policy for unlisted infra credit — L1 flagged CR-0016 as not addressed in the deck."*
3. She clicks **Pick Up**. She can read the L1 memo — the operational context is useful and the section 10 asks overlap with hers — but nothing on that screen lets her act on the deal.

**Conducting the review**

4. Because this is a **refresh**, the platform shows her ODD-2024-0006, her own review of NIIOF-I from two years ago: rating **Satisfactory with Observations**, with observations on fund administration handover and on the absence of a documented BCP test.
5. She scopes the refresh to what has changed since, plus the valuation question Priya raised. She does not re-do the full review, because a refresh is not a discounted full review — it is a different question, asked from a position of prior knowledge.
6. Over two weeks she conducts calls with Neo's COO and their fund administrator, reviews the valuation policy document Neo provides on request, and checks the BCP observation from last time.
7. She records findings by category — fund administration, valuation, compliance, cyber, BCP, key controls — and assigns a rating on **her own scale**: `SATISFACTORY_WITH_OBSERVATIONS`. Not a number. Not comparable to the L1 score of any deal. There is nowhere in the platform that averages her rating with the investment team's score, because those two things do not average.
8. She writes remediation: *"Valuation policy for unlisted infra credit is now documented but independent third-party valuation is annual, not semi-annual. Recommend semi-annual for a 7-year close-ended fund. Not blocking. Raise in the side letter."*
9. She submits. `is_blocking` computes to **false**.
10. **Nothing advances.** The deal does not move to IC. No decision is recorded. Priya gets a notification that the review is complete, and the deal's ODD badge changes from *in progress* to *satisfactory with observations*. That is the entirety of what a passing ODD review does, and it is correct — Devika has the power never to hire, never the power to hire.

**When the answer is no**

11. A different manager, six weeks later. Devika finds that the fund administrator is an affiliate of the sponsor, that valuation is performed in-house with no independent review, and that two key operational staff left in the last quarter without replacement.
12. She rates it **`UNSATISFACTORY`** and writes remediation requiring an independent administrator and third-party valuation before the fund is investable.
13. `is_blocking` computes to **true**. The Deal's Advance to Commitment control disables platform-wide, for everyone, including the Head of Research and the CIO.
14. The investment team is not pleased — the strategy is genuinely attractive and they have been working on it for four months. The CIO asks Devika whether the rating could be softened. She says no. **Nothing in the platform gives him a way to record a softer rating himself**: `events:ODD_REVIEW_COMPLETED:emit` is held by the ODD Reviewer role and by nobody else. He can override the gate, but only with her concurrence recorded in the rationale, under his name, permanently.
15. He does not. The deal sits blocked at IC until the manager appoints an independent administrator, which they do, four months later. Devika conducts a re-review and lifts the block.

**What success looks like for Devika**

Her assessment is recorded on her own scale, under her own name, on her own reporting line, and cannot be entered by anyone in the investment team. When she says no, the software says no. When she says yes, the software says nothing at all — because a clean operational review was never a reason to invest, only the removal of a reason not to.

---

## Sanjay Iyer — Standalone CLI User

### Who he is

Sanjay is an independent consultant advising a family office on manager selection. He has no login to the platform, no account, and no interest in one. He has a laptop, a confidential PPM under an NDA, and a strong obligation not to upload it anywhere.

He is the reason Product A exists as a standalone tool (`00-overview.md` §3), and his journey is the test of whether that separation is real or nominal.

### His typical workflow

**Setting up**

1. Sanjay installs the CLI. He writes his own criteria set — two YAML files in a directory, no database, no admin UI:

```yaml
# set.yaml
set_id: "8f3a...c21e"
set_code: "SI-2026-0001"
name: "Family office — infra credit screen"
version: 1
asset_class_scope: ["CAT_II"]
schema_version: 1
```

2. He writes eleven criteria in `criteria.yaml`, borrowing the shape of the platform's defaults but with his client's actual constraints — a concentration limit reflecting their existing infra exposure, and a fee ceiling that reflects what they will actually pay.
3. He lints it:

```
$ l1 validate ./criteria
✓ 11 criteria, 1 veto, 6 red flags, 4 green flags
⚠ CR-0007: detection_guidance contains no concrete noun — may be unusable
✓ schema conformance OK
```

4. He rewrites CR-0007. The warning was right: he had written *"poor governance"*, which instructs nothing.

**Running an analysis**

5. He runs it against the Neo deck, which his client also received:

```bash
$ l1 analyze "Neo Infra Income Opportunities Fund-II Feb'26.pdf" \
    --criteria ./criteria \
    --out ./runs/niiof-ii \
    --max-budget-usd 3.00
```

6. Progress prints to his terminal as it goes. Twenty-four minutes. **$1.38.** Nothing left his machine except the model calls, and no document was uploaded to any service run by anyone selling him software.
7. He opens `05-memo/00-index.md` in his editor and has the whole answer on one screen: the recommendation, the red/green weights, which criteria fired, and how many open questions there are broken down by cause. The twelve sections sit beside it as separate files — same structure as the platform produces, because it is the same engine — and the relative links between them resolve in his editor with no server running. He jumps straight to `11-open-questions.md`, which tells him the deck contains no SEBI registration number and no net return figure, and for each one records what the engine searched for and where, so he does not repeat those searches by hand.
8. He greps the artifacts for what he wants to check independently:

```bash
$ jq '.result.findings[] | select(.fired) | {code: .criterion_code, pages: [.evidence[].page]}' \
    runs/niiof-ii/04-scoring.json
```

9. Every fired finding lists its pages. He opens the PDF to page 37 and confirms the gross-return quote himself. **This is the check the engine's design is built to survive**, and it survives it.

**When it does not work**

10. He runs it against a scanned PPM with no text layer. Exit **30 — invalid input**. The message names the problem: no extractable text. He does not waste twenty minutes and $1.40 discovering this at the memo stage.
11. He runs a 300-page PPM with a $3 ceiling. Exit **21 — budget exceeded**, at the diligence stage, having spent $2.98. The artifacts for classification and extraction are on disk and valid. He re-runs with `--resume` and a $6 ceiling; the completed stages are skipped and it finishes for another $2.10 rather than starting from zero.
12. He interrupts a run with Ctrl-C by accident. Exit **143**. He runs `--resume` and it picks up where it stopped.

**What he never does**

13. He never logs into a management system. He never uploads a document. He never sees a deal list, a pipeline board, a triage decision, or an ODD review. He receives no notification when a criteria set is activated, because there is no criteria set anywhere but his own directory.

**What success looks like for Sanjay**

He produces the same quality of screening memo as an institution running the full platform, from the same engine, against his own rules, with a confidential document that never left his laptop — and he can verify every finding against the source document himself in under a minute. If the management system he never uses were rebuilt from scratch tomorrow, nothing about his workflow would change.

---

## Handoffs Between Roles

The points where one person's output becomes another's input. These are where the platform either holds together or leaks.

| From | To | What passes | Where it lives |
|---|---|---|---|
| Priya (Analyst) | The worker | A promoted document and a frozen criteria set | `DEAL_SUBMITTED` → queued run |
| The worker | Priya | A memo, findings, evidence, and a list of what could not be determined | `L1_MEMO_GENERATED` → Memo Reader |
| Priya | Devika (ODD) | A scoped review request, with L1 findings as scope notes | `ODD_REVIEW_REQUESTED` → ODD Queue |
| Devika | Priya | A rating on ODD's own scale, and possibly a block | `ODD_REVIEW_COMPLETED` → deal badge, gate state |
| Priya | Meera (IC) | An IC packet with section 11 intact and the criteria hash stamped | `MEMO_EXPORTED` → PDF |
| Meera | Priya | An IC decision with a rationale that survives the meeting | `DEAL_TRIAGED` (IC_APPROVED / IC_DECLINED) |
| Priya | Ashwin | Overrides, by criterion and by reason | `MEMO_FINDING_OVERRIDDEN` → Criterion Performance |
| Ashwin | Everyone | A revised criteria set that applies to future deals only | `CRITERIA_SET_ACTIVATED` |
| Priya (past) | Priya (future) | A pass reason and a rationale, retrievable when the manager returns | `DEAL_TRIAGED` (PASS) → Passed Deals |

**The handoff most likely to be underbuilt** is Priya → Ashwin. Overrides are generated as a by-product of an analyst doing their job, and they are the highest-quality signal available about whether the criteria set is any good. If they land in a report nobody opens, the criteria set never improves and the platform's central customisation mechanism ossifies at whatever the seed data said.

**The handoff most likely to be got wrong** is Devika → Priya. The temptation is to make a passing ODD review advance the deal — it feels like a completed step, and completed steps advance things. It must not. The moment ODD advancing a deal is possible, ODD is a stage in the investment team's pipeline, and the independence that makes the function worth having is gone.

---

## Cross-Cutting Failure Scenarios

Scenarios that touch several roles at once. Each one is a real thing that will happen.

### The manager sends an updated deck mid-diligence

Neo circulates a June 2026 update while NIIOF-II is in IDD with an ODD refresh in flight.

Priya uploads it. The platform recognises the manager and, more importantly, proposes attaching it to **DL-2026-0089** as document 2 — not creating a second Deal. She confirms. A second run queues against the same Deal.

Twenty-five minutes later there are two memos. The February one becomes **SUPERSEDED**, still fully readable. Priya opens **Memo Comparison**:

```
Target investments      20–22        →  16–18       ▼
Target size             ₹5,000 cr    →  ₹5,000 cr   —
Hurdle                  10%          →  10%         —
Carry                   no catch-up  →  no catch-up —
CR-0010 gross-only      FIRED        →  NOT FIRED   ✓ net IRR now disclosed p.41
CR-0011 unrealised      FIRED        →  FIRED       —
```

Neo has answered one of her eleven asks in the new deck and quietly narrowed the portfolio target. The second is the more interesting fact and it is not one she would have caught by reading two decks four months apart.

Devika's ODD refresh is unaffected — it is about operational infrastructure, not deck contents, and it does not restart.

### The worker dies mid-run

The worker host is OOM-killed twenty minutes into a twenty-six-minute run. No event is emitted; there is nobody left to emit one.

Priya sees the run still showing **RUNNING** for another few minutes. Nothing appears broken, which is mildly unsatisfying. The lease expires. The sweeper returns the run to **QUEUED**. A worker — the same one restarted, or another — reclaims it, finds the run directory with four valid stage artifacts, and invokes the engine with `--resume`. Only the memo stage re-runs. It completes ninety seconds later, for $0.20 rather than $1.42.

Priya's experience is a run that took twenty-eight minutes instead of twenty-six. She never learns why unless she opens the run history and notices `attempt_number: 2`.

**This is where PRD 02 §12.2's flagged gap bites.** There is no event recording *why* attempt 1 ended, because the process that would have recorded it was killed. An operator investigating later sees two attempts and no explanation.

### A veto fires

A different deck. The manager has no SEBI registration number anywhere and the register lookup finds no matching entity. `CR-0001` fires at CRITICAL confidence.

The engine halts scoring, generates a **veto-form memo**, and exits **11**. The worker emits `DEAL_SCORED` with `veto_fired: true` and then `L1_MEMO_GENERATED`. The run is **COMPLETED**, not failed — the analysis succeeded and produced its most decision-relevant possible output.

Priya's queue shows: *"MEMO-2026-000341 ready — Recommendation: **VETOED**."* The memo leads with the veto reason. Sections 3, 6, 7 and 8 are thin, because scoring halted before full extraction completed, and the memo says so rather than leaving blanks.

She passes the deal in ninety seconds with reason `REGULATORY`. The whole thing cost $0.31 and about two minutes of her attention. Before, it would have cost her the forty minutes it takes to read a deck and notice what is missing.

### The SEBI register is unreachable

The diligence stage cannot reach SEBI's intermediary register. The registration check is recorded as **`unavailable`**, with the reason, and the run continues.

`CR-0001` — the registration veto — cannot be evaluated. It is recorded as **`VETO_UNEVALUATED`**, which is neither fired nor not-fired. The memo's section 11 carries: *"SEBI registration could not be verified — the intermediary register was unreachable at time of analysis (connection timeout). The document itself contains no registration number. This is an open item, not a clean result."*

**Nowhere in the memo or the UI does this render as a green tick.** The distinction between `unavailable` and `passed` is preserved from the engine's artifact through the worker's validation into the finding's `evaluation_state` and onto the screen. Priya sees an unevaluated veto, understands exactly what that means, and checks the register herself in the two minutes it takes.

### An analyst attests to something that was wrong

Priya attests against `CR-0011` (unrealised predecessor track record), writing *"seen NIIOF-I's Q2 numbers directly — distributions are real"* and citing a manager call. She is wrong: those numbers were marks, not realised distributions.

She re-runs. `CR-0011` stops firing, and v2's recommendation moves.

**The platform does not catch this, and nothing in the design claims it should.** No system that accepts human input can validate the human. What it does instead is make the error attributable and reversible:

- The attestation is labelled **analyst-attested**, never document-grounded, everywhere it appears. A reader can see at a glance that this finding rests on a person rather than a page.
- It carries her name, her stated source, and its date.
- **v1 is frozen and still downloadable**, with `CR-0011` firing on page-13 evidence exactly as the engine wrote it.
- The version diff attributes the flip to her attestation specifically — *"`CR-0011` fired → not-fired because of an analyst attestation dated 22 Jul, source: manager call."*

When the IC later asks how a fund with an unrealised track record cleared screening, the chain is intact: here is what the engine found, here is who said otherwise, here is the exact sentence they wrote. Compare v1 to v2 and the disagreement is one row.

Note the asymmetry this creates deliberately. An attestation is *more* consequential than an override — it propagates into the analysis rather than annotating it — so it demands a source and gets stronger provenance labelling. The more powerful action carries the heavier audit trail.

---

## What "Done" Looks Like, Per Role

| Role | The output they can point at |
|---|---|
| **Priya (Analyst)** | A deck that arrived Monday morning is triaged Monday afternoon with a written rationale, page-cited findings, and eleven questions ready to send. Her passed deals are retrievable by manager, with reasons, when someone comes back. |
| **Ashwin (Super Admin)** | House policy exists as versioned, attributable rules rather than in people's heads. He can see which rules fire, which never fire, which get overridden and why — and what the aggregate of forty individual decisions says about what the institution actually does. |
| **Meera (IC Member)** | A packet that states its recommendation first, its gaps explicitly, and the exact rule set that produced it. She can interrogate any claim to a page and a quote in two clicks, and she can see where a human disagreed with the machine. |
| **Devika (ODD Reviewer)** | Her assessment recorded on her own scale, on her own reporting line, enterable by nobody else. When she says no, the software says no. When she says yes, the software says nothing — which is exactly right. |
| **Sanjay (CLI user)** | A screening memo of the same quality, from the same engine, against his own rules, produced entirely on his own machine from a document that never left it. |
