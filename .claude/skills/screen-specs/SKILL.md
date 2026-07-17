---
name: screen-specs
description: Per-screen UX detail derived from a PRD — layout, data points, CTAs, validations, and conditional states. Use when creating or editing files in a screen-specs/ subfolder inside 40-solution-design/.
---

# Screen Specs

## When to Use

Apply this skill when creating or editing files in a `screen-specs/` subfolder inside
`40-solution-design/<prd-folder>/`.

Screen specs are the per-screen UX detail layer. They bridge the gap between a high-level PRD and the
actual UI/UX and developer handoff — so nothing about a screen gets assumed or invented during design
or development.

## Where Screen Specs Live (and why)

Screen specs are **paired with a PRD**, not a standalone top-level folder:

```
40-solution-design/
└── prd-NN-<name>/
    ├── prd.md             the PRD these screens derive from
    └── screen-specs/
        ├── screen-<a>.md  one file per screen
        └── screen-<b>.md
```

This pairing is deliberate: every screen spec derives from a specific PRD. If there is no PRD folder,
there is nowhere to put screen specs — so they can never be written before the PRD exists.

## Entry Rule

Do NOT create screen specs until the parent PRD exists (`prd.md` in the same folder). Screen specs
describe the screens *of that PRD*. One `screen-specs/` folder per PRD.

## What Every Screen File Must Capture

Use one file per screen. Each screen file must include:

1. **Screen name + module/PRD** — what the screen is called and which PRD/module it belongs to.
2. **Entry points** — every way a user reaches this screen. For each entry: where the user comes from
   (which screen or source), the trigger (nav item, button/link, deep link, redirect, action result),
   and any condition or context passed in (a selected record, a filter, a role/permission). If a
   screen can be reached more than one way, list them all — this is how navigation gaps get caught.
3. **UX layout** — the sections, hierarchy, and visual structure of the screen. Describe what is
   where: header, main content, sidebars, modals, etc.
4. **Data points displayed** — every piece of data shown on the screen. For each: the label, the
   value/format, and its source (which entity/field/API it comes from).
5. **CTAs** — every button, link, and action on the screen, with its intended behavior (what happens
   when the user activates it, where it goes, what it triggers).
6. **Validations** — every validation rule that applies on the screen (required fields, formats,
   ranges, dependencies, error messages).
7. **Conditional states** — empty state, loading state, error state, restricted-access state, and any
   other state the screen can be in. Describe what the user sees in each.

If you can't fill one of these in, mark it `[TODO: what's needed]` — never invent UI detail.

## Per-Module Screen List

For each module/PRD, also maintain a complete screen list: every screen name with a one-line purpose.
This is the index of what screens exist for that PRD.

## Template

Use the template at `templates/screen-spec.md`.

## Dates

Set `created:` when you start the file and update `updated:` to today's date on every edit. A stale
date is worse than none — see `documentation-writer`.

## Branding

When producing a styled/PDF version of screen specs, apply JetBro brand guidelines from
`jetbro-brand/CLAUDE.md`.
