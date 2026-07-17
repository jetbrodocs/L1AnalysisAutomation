---
name: solution-design
description: Translating process documentation into digital solution requirements — data models, architecture, API design, and tech decisions. Use when creating or editing files in 40-solution-design/.
---

# Solution Design

## When to Use

Apply this skill when creating or editing files in the `40-solution-design/` folder. Solution design bridges the gap between documented processes and a digital system that supports or replaces them.

## 🔒 Entry Guard — Tech Stack First

**Do NOT begin solution design until the tech stack and implementation approach are decided.**

Before writing anything in `40-solution-design/`, confirm there is an approved technology/
implementation decision (normally an `status: approved` document in `30-analysis/` — see the
`analysis` skill). If that decision has not been made, STOP and tell the user: solution design needs
a decided stack and implementation approach first. Don't guess the stack and proceed.

## Folder Structure — One Folder Per PRD

`40-solution-design/` is organized **per PRD**. Each PRD gets its own folder, paired with its screen
specs:

```
40-solution-design/
├── prd-01-<name>/
│   ├── prd.md             the PRD
│   └── screen-specs/      per-screen UX detail (see the screen-specs skill)
│       ├── screen-<a>.md
│       └── screen-<b>.md
└── prd-02-<name>/
    ├── prd.md
    └── screen-specs/
```

- PRD folders are numbered: `prd-NN-<name>/` in kebab-case (e.g. `prd-01-inventory-intake/`).
- Cross-cutting files (data model, architecture, requirements) can live at the top of
  `40-solution-design/` if they span multiple PRDs.
- Screen specs are written using the `screen-specs` skill — see it for the per-screen format.

## The Bridge Concept

Solution design is not about digitizing the current process as-is. It's about designing the improved version — informed by everything captured in observations and process maps, but not constrained by it.

The question shifts from "how does this work today?" to "how should this work with the right technology?"

Key principles:
- **Preserve what works.** Don't change things that aren't broken.
- **Eliminate unnecessary steps.** If a step exists only because of a manual limitation, it may not need to exist.
- **Automate the obvious.** Data entry, notifications, calculations, and lookups are automation candidates.
- **Keep humans where judgment matters.** Quality decisions, exception handling, and customer interactions often need people.

## What Goes in Solution Design

The `40-solution-design/` folder typically contains these files:

| File | Purpose |
|---|---|
| `requirements.md` | Functional and non-functional requirements extracted from process docs |
| `data-model.md` | Entities, attributes, and relationships |
| `architecture.md` | System components and how they connect |
| `api.md` | API endpoints or integration points |
| `mvp-scope.md` | What's in v1 vs. what's deferred |
| `tech-decisions.md` | Technology choices and rationale |

Not every project needs all of these. Create files as they become relevant.

## Extracting Requirements From Process Docs

For each process step, ask:

1. **Does this step need to exist in the digital system?** Some steps disappear with automation. Some become background jobs. Some stay manual.
2. **Who interacts with the system at this step?** Define the user role and what they need to see or do.
3. **What data is created, read, updated, or deleted?** This feeds the data model.
4. **What business rules apply?** Validation rules, calculations, conditional logic, approval thresholds.
5. **What can go wrong?** Error states, edge cases, and how the system should handle them.

Document each requirement with:
- A unique ID (e.g., `REQ-001`)
- The source process step (e.g., "from `proc-material-intake.md`, step 4")
- A clear description of what the system must do
- Acceptance criteria (how you know it's working)

## Tech Decision Record Format

When making a technology or architecture choice, document it with this structure:

```markdown
## TDR-001: [Decision Title]

**Status:** proposed | accepted | deprecated
**Date:** YYYY-MM-DD

### Context

What situation or requirement prompted this decision? Reference specific process docs or requirements.

### Options Considered

1. **Option A** — Brief description. Pros: ... Cons: ...
2. **Option B** — Brief description. Pros: ... Cons: ...
3. **Option C** — Brief description. Pros: ... Cons: ...

### Decision

Which option was chosen.

### Rationale

Why this option was selected over alternatives. Be specific about the deciding factors.

### Consequences

What this decision means for the project — both positive trade-offs and constraints it introduces.
```

Record decisions as they're made, not after the fact. Future team members will thank you for the context.

## Branding

When producing styled deliverables from solution design work (architecture diagrams as HTML, requirement documents as PDF, presentation decks), apply JetBro brand guidelines from `jetbro-brand/CLAUDE.md`. Use the JetBro color palette, typography, and accent line. Import CSS tokens from `jetbro-brand/tokens.css` for web output.
