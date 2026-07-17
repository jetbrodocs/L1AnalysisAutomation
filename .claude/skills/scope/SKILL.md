---
name: scope
description: Writing the independent, self-contained scope document for stakeholder sign-off — references nothing else in the project, exports to a branded PDF. Use when creating or editing files in scope/.
---

# Scope

## When to Use

Apply this skill when creating or editing files in the `scope/` folder.

The scope document is what you hand to stakeholders to **sign off** on. It is usually a single
`scope.md` (occasionally a few files). It exists outside the numbered flow because it can be produced
at any point — after process maps, after analysis, or before PRDs — whenever a sign-off is needed.

## The One Rule: Self-Contained

The scope document **references nothing else in the project.** No links to observations, process
maps, analysis, or PRDs. A stakeholder reading it should understand the full scope without opening
any other file or having access to the repository.

This means: pull the relevant facts INTO the scope document. Restate them in plain, stakeholder-
friendly language. Do not write "see `proc-intake.md`" — write out what matters here.

Why: the scope doc is shared and signed off as a standalone artifact. It must stand on its own and
must not break or go stale because some other file moved or changed.

## What a Scope Document Contains

A good scope document, written for a non-technical stakeholder, typically covers:

- **What is being built / done** — the deliverable, in plain language.
- **What is included** — the concrete scope, feature by feature or area by area.
- **What is explicitly NOT included** — out-of-scope items, stated clearly to prevent assumptions.
- **Assumptions and dependencies** — what must be true or provided for this scope to hold.
- **Sign-off** — space for the stakeholder to approve (name, date).

Keep it concrete and specific. Avoid internal jargon a stakeholder wouldn't know.

## Template

Use the template at `templates/scope.md`.

## Export to PDF

The scope document is shared as a branded PDF. When exporting:

- Apply JetBro brand guidelines from `jetbro-brand/CLAUDE.md` (colors, typography, logo, accent line).
- Import `jetbro-brand/tokens.css` and use the `.jetbro-accent-line` class for separators — it
  renders correctly in PDF (solid orange in print, not a black bar).

## Dates

The scope document is a sign-off artifact — its date matters. Set `created:` and always update
`updated:` to today's date on every edit. Include the date visibly on the document itself so a signed
copy records which version was approved.
