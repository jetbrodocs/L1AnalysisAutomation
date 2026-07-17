# Project Configuration

## Project Description

<!-- Replace this with a 2-3 sentence description of the project -->
[TODO: Describe the project — what site, facility, or system is being documented? What is the goal of the documentation effort?]

## Domain Glossary

| Term | Definition |
|---|---|
| <!-- Add terms as you encounter them --> | |

## Skills

This project includes skills installed in `.claude/skills/`. Claude Code auto-discovers these from their descriptions. You can also invoke them manually. Each skill that owns a folder names that folder explicitly — so output never has to be guessed.

| Skill | Owns folder | Trigger |
|---|---|---|
| `/documentation-writer` | — (all output) | Always apply as baseline for all documentation output |
| `/observation-capture` | `10-observations/` | Capturing observed reality or Q&A exchanges |
| `/process-mapping` | `20-process-maps/` | Building sequential flows from observations |
| `/analysis` | `30-analysis/` | Deep-dives, comparisons, or tech-stack/implementation decisions |
| `/solution-design` | `40-solution-design/` | Writing PRDs / requirements (after tech stack is decided) |
| `/screen-specs` | `40-solution-design/<prd>/screen-specs/` | Per-screen UX detail derived from a PRD |
| `/scope` | `scope/` | Writing the independent stakeholder sign-off document |
| `/documentation-reviewer` | — (method) | Reviewing/auditing docs; findings fold back into source docs |
| `jetbro-brand` | — (all styled output) | Always active — applies to all styled/visual output (HTML, PDF, slides, reports) |

**Layering:** `documentation-writer` is the foundation — it loads automatically for any writing task. `jetbro-brand` is always active for any styled or visual output. Specialized skills layer on top based on context.

**Skill priority:** This is a documentation project, not a code project. Always prefer this project's documentation skills over general-purpose coding skills (e.g., superpowers, test-driven-development, frontend-design). Do not invoke coding-oriented skills unless the user explicitly asks for code.

## Folder Structure

**Strict purpose, flexible order.** Each folder's *purpose* is enforced — put a document only in the folder whose purpose it matches. The *order* between folders is flexible: you can write scope after process maps, or after analysis, or jump back to observations any time. The numbered prefixes are for grouping and sorting, not a mandatory sequence. **Each folder has an entry rule — check it before writing there.**

| Folder | Purpose | Entry rule (what belongs / does NOT) |
|---|---|---|
| `00-inbox/` | Raw notes, uploads, unprocessed material | Anything raw. No rule. |
| `10-observations/` | Observed reality + Q&A exchanges | Belongs: what was observed or what people told you. NOT: analysis, conclusions, flows. |
| `20-process-maps/` | Sequential process flows, user journeys, data flow | Belongs: a sequence/flow built from observations. NOT: raw captures, design, analysis. |
| `30-analysis/` | Deep-dives only — research, comparisons, **tech-stack/implementation decisions** (optional) | Belongs: a genuine deep-dive or a tech decision. NOT: routine notes, observations, process steps. |
| `40-solution-design/` | PRDs, requirements, data model, architecture. One folder per PRD: `prd-NN-<name>/` with `prd.md` + `screen-specs/` | 🔒 **Guard: do NOT start until the tech stack/implementation approach is decided (in `30-analysis/`).** |
| `60-change-logs/` | Records of changes made to the system over time | Belongs: a record of a change to the system. NOT: review/gap-analysis findings (those fold into source docs). |
| `scope/` | Independent stakeholder sign-off doc(s) — exports to branded PDF | 🔒 **Must be self-contained — references nothing else in the project.** |

## Team

| Name | Role | Notes |
|---|---|---|
| <!-- Add team members --> | | |

## Branding

All styled or visual output (HTML pages, PDF documents, slides, reports, dashboards) must use JetBro brand guidelines from `.claude/skills/jetbro-brand/`. This includes:

- **Colors:** Use the JetBro palette (accent `#c45a32`, text `#1a1a1a`, etc.)
- **Typography:** Bricolage Grotesque for headings, Outfit for body text, Space Mono for code/data
- **Logo:** Include from `jetbro-brand/logo.svg` where appropriate
- **Accent line:** Use the signature gradient separator between sections
- **CSS tokens:** Import from `jetbro-brand/tokens.css` for web output

Plain markdown files (observations, process maps, analysis, screen specs) do not need visual branding — the brand applies when producing formatted deliverables (scope PDFs, reports, slides).

## Date Awareness (read this on every session)

Documents carry `created:` and `updated:` dates in their frontmatter. These matter — not everyone checks git history.

- **When writing/editing any doc:** always set `updated:` to today's date. A stale date is worse than none.
- **When reading any doc:** note its `updated:` date relative to today. If it is old, treat the content as **possibly outdated** — verify before relying on it, especially for decisions, tech choices, and scope. Do not assume an old document reflects the current state.
- **Git is the source of truth** for when a file actually changed: `git log -1 --format=%cs <file>`. If it disagrees with the frontmatter, trust git.

## Project-Specific Rules

<!-- Add any rules that apply only to this project -->
<!-- Examples: -->
<!-- - All observations must be reviewed within 48 hours of capture -->
<!-- - Use metric units only -->
<!-- - Reference SAP transaction codes where applicable -->
