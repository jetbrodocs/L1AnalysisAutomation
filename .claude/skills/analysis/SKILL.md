---
name: analysis
description: Deep-dive analysis, research, comparisons, and technology/implementation decisions. Use when creating or editing files in 30-analysis/.
---

# Analysis

## When to Use

Apply this skill when creating or editing files in the `30-analysis/` folder.

**This folder is optional.** Use it only when there is something that genuinely needs a deep dive.
If a question can be answered in an observation or a process map, it does not belong here.

## What Belongs in 30-analysis/

- **Research** — investigating a concept, technology, vendor, or approach in depth.
- **Comparisons** — weighing options against each other (tools, libraries, vendors, designs).
- **Concept deep-dives** — working through a hard or ambiguous part of the problem.
- **Technology and implementation decisions** — choosing the tech stack and deciding *how* the
  solution will be built. This is the work that must happen **before** solution design begins.

## What Does NOT Belong Here

- Raw observations (those go to `10-observations/`).
- Process steps or flows (those go to `20-process-maps/`).
- Requirements, data models, or PRDs (those go to `40-solution-design/`).
- Routine notes that aren't a deep dive.

If you're not doing a genuine deep-dive, comparison, or decision, you don't need this folder.

## The Tech-Stack Decision (gate to solution design)

Solution design cannot start until the tech stack and implementation approach are decided. That
decision normally happens here. When making it, produce a clear record that states:

- **What was decided** — the stack, frameworks, and overall implementation approach.
- **Options considered** — what else was on the table, with pros and cons.
- **Why** — the deciding factors.
- **Consequences** — constraints and trade-offs this introduces.

Mark the document `status: approved` once the decision is settled. Solution design reads this to
confirm it is allowed to begin.

## Template

Use the template at `templates/analysis.md`. It includes Summary, Findings, Recommendations, and
Open Questions. For technology decisions, the Tech Decision Record format in the `solution-design`
skill is a good structure to follow.

## Dates

Set `created:` when you start the document and update `updated:` to today's date every time you edit
it. A stale date is worse than none — see `documentation-writer`.
