---
name: documentation-reviewer
description: A review and gap-analysis METHOD applied across observations, process maps, and analysis — completeness, consistency, and depth checks. Has no folder of its own. Use when asked to review, audit, or find gaps in docs.
---

# Documentation Reviewer

## What This Is

This is a **method, not a destination.** Reviewing is something you *do to* the early documentation
(`10-observations/`, `20-process-maps/`, and `30-analysis/`) — it does not have its own folder.

Apply this skill when asked to review, audit, check, or perform a gap analysis on documentation. This
covers reviewing individual files, entire folders, or cross-referencing multiple documents for
consistency.

## Where Findings Go

Review findings **fold back into the source documents** — they do not get written to a separate
folder:

- **Gaps** become `[TODO: ...]` markers and entries in the source doc's "Open Questions" section.
- **Direct fixes** (typos, formatting, missing/stale frontmatter) are applied to the source doc.
- **Questions** are raised with the user so the source doc can be filled in.

Do not create a "review log" file. (Note: `60-change-logs/` is a different thing — it records changes
made to the *system*, not documentation-review findings.)

## Review Process

Follow these steps in order:

1. **Read the scope.** Understand what you're reviewing — a single file, a folder, or the full project. Confirm with the user if unclear.
2. **Check against criteria.** Run through the completeness, consistency, and depth checks below.
3. **Ask questions.** List every gap as a specific, answerable question. Don't just flag problems — frame them as questions someone can respond to.
4. **Fold findings back.** Apply direct fixes to the source docs; add `[TODO]` markers and open
   questions where information is missing. Report the questions to the user.

## Completeness Checks

- [ ] All template sections are filled in or have explicit `[TODO]` markers
- [ ] Inputs and outputs are listed for every process step
- [ ] Exception paths are documented, not just the happy path
- [ ] People/roles are named for each activity
- [ ] Timing information is present (duration, frequency, or schedule)
- [ ] Connected processes are referenced (what comes before, what comes after)

## Consistency Checks

- [ ] Terminology matches the project glossary in `CLAUDE.md`
- [ ] The same thing isn't called different names in different files
- [ ] Numbers are consistent across documents (if receiving says "20 pallets/day" and shipping says "15 pallets/day," flag it)
- [ ] Time estimates are consistent (a 30-minute process shouldn't be part of a 20-minute parent process)
- [ ] Role names are consistent (don't mix "operator" and "technician" for the same person)

## Freshness Checks

- [ ] Frontmatter `updated:` matches reality. Compare it to git: `git log -1 --format=%cs <file>`.
      If git shows a newer change than the frontmatter, the date is stale — fix it.
- [ ] Flag documents whose `updated:` date is old. Old docs may carry outdated decisions, tech
      choices, or scope. Note them so the user can confirm they're still current.

## Depth Checks

- [ ] The document explains *why*, not just *what* (why is this step done this way?)
- [ ] Business rules are stated explicitly, not implied
- [ ] Workarounds and informal practices are documented
- [ ] Decision criteria are specific ("if weight > 50 lbs" not "if the item is heavy")
- [ ] Edge cases are addressed (what happens when something fails, is missing, or is wrong?)

## Question Quality Rules

Every question you raise must be:

1. **Specific.** Tied to a file and section. "What units does the scale read in?" not "Tell me more about weighing."
2. **Answerable.** Someone can respond without re-reading the entire document. Include enough context in the question itself.
3. **Non-redundant.** Don't ask for information that's already in the document.
4. **Actionable.** The answer will result in a concrete update to the documentation.

Bad: "Can you clarify the inspection process?"
Good: "In `obs-receiving-inspection.md` > Visual Checks: what specific defects does the operator look for? The current list says 'visible damage' — can you list the top 3-5 defect types?"

## Reporting a Review

A review does not produce a file. Instead:

1. **Apply direct fixes** to the source docs — typos, formatting, missing/stale frontmatter — and
   say what you changed.
2. **Add `[TODO]` markers** in the source docs where information is missing, and list the gap in that
   doc's "Open Questions" section.
3. **Report a summary to the user**: 2-3 sentences on the overall state, the gaps found (with
   file/section and severity), and the questions that need answers. Keep this in the conversation —
   don't write it to a folder.
