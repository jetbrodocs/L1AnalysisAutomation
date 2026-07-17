---
name: documentation-writer
description: Writing standards and formatting rules for all documentation. Apply as baseline for any writing or editing task — observations, process maps, analysis, solution designs, screen specs, scope, or change logs.
---

# Documentation Writer

## When to Use

Apply this skill whenever you are writing, drafting, or editing any documentation file — observations, process maps, analysis documents, solution designs, or any other structured content. This is the baseline writing standard for all documentation output.

## Writing Principles

1. **Be concrete.** Name the thing, the person, the system, the number. "The operator scans each pallet barcode" beats "items are scanned."
2. **Be specific.** Include quantities, durations, frequencies, and dimensions when known. "Takes 3-5 minutes per batch" beats "takes some time."
3. **Keep sentences short.** One idea per sentence. If a sentence has more than one comma, split it.
4. **No filler.** Cut words like "basically," "essentially," "in order to," "it should be noted that." Say the thing directly.
5. **Honest gaps.** If you don't know something, say so explicitly. Write `[UNKNOWN: reason]` or `[TODO: what's needed]`. Never fabricate details to fill space.
6. **Active voice.** "The supervisor approves the form" not "the form is approved by the supervisor." Passive voice hides who does the work.
7. **Domain language.** Use the terms the team uses. If they say "traveler" instead of "work order," use "traveler." Define terms in the project glossary.

## Pre-Writing Checklist

Before generating any documentation:

- [ ] Confirm which template to use (check `templates/` folder)
- [ ] Identify the source material (observation notes, interview transcript, existing docs)
- [ ] List what you know vs. what you don't know
- [ ] Check the project glossary in `CLAUDE.md` for correct terminology

Do not start writing until you can answer: "What is the source of the information in this document?"

## Branding

When producing styled or visual output (HTML, PDF, slides, reports) — not plain markdown — apply JetBro brand guidelines from `jetbro-brand/CLAUDE.md`. Use the JetBro color palette, typography (Bricolage Grotesque / Outfit / Space Mono), logo, and accent line. Import CSS tokens from `jetbro-brand/tokens.css` for web output.

## Post-Writing Checklist

After completing a draft:

- [ ] Every section has content or an explicit `[TODO]` marker
- [ ] Open questions are listed at the end of the document
- [ ] Each open question is specific enough to answer without re-reading the whole document
- [ ] File name follows kebab-case convention
- [ ] Frontmatter is complete (title, status, created, updated, tags)

## Frontmatter Standard

Every documentation file must begin with YAML frontmatter:

```yaml
---
title: "Descriptive Title of This Document"
status: draft | in-review | approved
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [relevant, tags, here]
---
```

Valid status values:
- `draft` — initial capture, not yet reviewed
- `in-review` — under active review, questions outstanding
- `approved` — reviewed, gaps resolved, accepted as accurate

## Dates Are Mandatory

Dates carry the document's freshness. Treat them as required, not optional.

- **On create:** set `created:` and `updated:` to today's date.
- **On every edit:** update `updated:` to today's date. Always. No exception.
- A **stale `updated:` date is worse than none** — it actively misleads a reader into trusting old
  content as current.

**Git is the source of truth.** Frontmatter dates are self-reported and can be wrong. The ground
truth for when a file last actually changed is `git log -1 --format=%cs <file>`. When the frontmatter
date and git disagree, trust git — and fix the frontmatter.

## File Naming Convention

- Use kebab-case: `receiving-inspection.md`, not `Receiving Inspection.md`
- No spaces, no underscores, no capital letters in file names
- Prefix with category if helpful: `obs-receiving-inspection.md`, `proc-material-intake.md`
- Index files are named `_index.md`
