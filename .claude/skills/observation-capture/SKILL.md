---
name: observation-capture
description: Structured capture of site visit observations — activities, inputs, outputs, people, timing, and problems. Use when creating or editing observation documents in 10-observations/.
---

# Observation Capture

## When to Use

Apply this skill when creating or editing files in the `10-observations/` folder. Observations are the raw capture of what happens at a site, station, or work area. They are the foundation everything else is built on.

## What Belongs Here

- Observed reality from site visits, walkthroughs, and shadowing.
- Material that arrives via `00-inbox/` once you structure it.
- **Q&A exchanges** — answers from interviews, clarifications, and follow-up questions. Capture the
  question and the answer; these are observations of what people told you.

**Does NOT belong here:** analysis, conclusions, or recommendations (those go to `30-analysis/`);
process flows (those go to `20-process-maps/`). Observations describe *what is*, not *what it means*
or *what should change*.

## What Makes a Good Observation

Apply the **"could someone else understand it"** test: if a person who wasn't there reads this observation, could they describe the work back to you accurately? If not, it needs more detail.

Good observations are:
- **Descriptive, not prescriptive.** Document what happens, not what should happen.
- **Specific enough to act on.** Someone could design a system from this description.
- **Honest about gaps.** Mark anything you didn't see or couldn't confirm.

## Minimum Viable Observation

Every observation must capture at least these six elements:

1. **Activity** — What is being done? Name the task.
2. **Inputs** — What materials, information, or triggers start this activity?
3. **Outputs** — What is produced, moved, or changed?
4. **People** — Who does this work? What role? How many?
5. **Timing** — How long does it take? How often does it happen?
6. **Problems** — What goes wrong? What workarounds exist?

If you can't fill in one of these, mark it `[UNKNOWN]` with a note about why.

## Full Observation Template

Use the template at `templates/observation.md`. It includes all sections from the minimum viable observation plus:

- **Location/Station** — Physical or logical location
- **Equipment and Tools** — What's used to do the work
- **Systems** — Software, databases, or digital tools involved
- **Handoffs** — What happens before and after this activity
- **Photos/Diagrams** — References to any visual documentation
- **Raw Notes** — Unstructured capture from the visit

## Capture Tips

- **Push for specifics.** "How many?" "How long?" "How often?" "What happens when it breaks?" These are the questions that turn vague observations into useful ones.
- **Document workarounds.** The unofficial process is often more important than the official one. If someone uses a sticky note, a personal spreadsheet, or a phone call to get things done, capture that.
- **Don't skip the obvious.** Things that seem too simple to write down are often the things that get lost. "Operator visually checks the label" is worth recording.
- **Capture exceptions first.** The main flow is usually easy to get later. The weird edge cases ("but on Tuesdays when we get the international shipments...") are what you'll forget.
- **Note the environment.** Temperature, noise, lighting, space constraints — these affect how work gets done and what digital solutions are feasible.
- **Record exact language.** When someone says "we call that a traveler" or "that's the hot list," write down their exact terms. These go in the project glossary.
