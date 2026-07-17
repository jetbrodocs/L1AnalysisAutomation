---
name: process-mapping
description: Building sequential process flows from observations — main flow, decision points, exception paths, and cross-references. Use when creating or editing process documentation in 20-process-maps/.
---

# Process Mapping

## When to Use

Apply this skill when creating or editing files in the `20-process-maps/` folder. Process maps are built from observations — they organize raw capture into a sequential, followable description of how work flows.

## What Belongs Here

- Sequential process flows, user journeys, and data flow built from observations.

**Does NOT belong here:** raw observations (those stay in `10-observations/`); analysis or
comparisons (those go to `30-analysis/`); requirements, data models, or PRDs (those go to
`40-solution-design/`). A process map is a *sequence*, not a capture and not a design.

## What Makes a Good Process Doc

Apply the **"could someone follow this"** test: if a new employee read this process document, could they execute the process (with supervision) on their first day? If not, it's missing steps, decision points, or context.

Good process docs:
- **Follow a clear sequence.** Each step leads to the next. The reader never wonders "what happens now?"
- **Name every handoff.** When work moves from one person, system, or area to another, that transition is explicit.
- **Separate the main flow from branches.** The normal path is easy to follow. Exceptions and decision points are clearly marked.
- **Connect to observations.** Every process step should trace back to an observation. If it doesn't, flag it as `[UNVERIFIED]`.

## How to Build From Observations

1. **List all observations** related to this process area.
2. **Identify the sequence.** What happens first? What triggers the process? What ends it?
3. **Map handoffs.** Where does work move between people, stations, or systems?
4. **Write the main flow first.** Document the "everything goes right" path as numbered steps.
5. **Add decision points.** Where does the flow branch? What determines which path is taken?
6. **Add exception paths.** What happens when something goes wrong at each step?
7. **Cross-reference.** Link each step back to the observation(s) that describe it.

## Full Process Template

Use the template at `templates/process.md`. It includes:

- **Process Overview** — Name, purpose, frequency, trigger, end condition
- **Roles Involved** — Who participates and what they do
- **Inputs and Outputs** — What goes in, what comes out
- **Process Steps** — Numbered main flow with decision points and exceptions
- **Connected Processes** — What feeds this process, what it feeds
- **Systems and Tools** — Technology used at each step
- **Known Issues** — Current problems, workarounds, risks
- **Open Questions** — Unresolved items

## Representing Flow in Markdown

### Numbered Steps (Main Flow)

```markdown
1. Operator receives pallet at dock door 3.
2. Operator scans pallet barcode with handheld scanner.
3. System displays expected contents and PO number.
4. Operator counts items and compares to expected quantity.
```

### Decision Points (Indented Branches)

```markdown
5. Operator checks if quantity matches expected.
   - **If match:** Operator confirms receipt in system. Go to step 6.
   - **If mismatch:** Operator flags discrepancy. Go to Exception A.
```

### Exception Paths (Labeled Blocks)

```markdown
### Exception A: Quantity Mismatch

A1. Operator notes actual vs. expected quantity on discrepancy form.
A2. Supervisor reviews discrepancy within 1 hour.
A3. Supervisor contacts supplier or adjusts PO.
A4. Return to main flow at step 6 once resolved.
```

### Simple Text Diagrams

For complex flows, a text diagram can help orient the reader:

```
Dock → Scan → Count → [Match?] → Yes → Confirm → Putaway
                         ↓ No
                    Discrepancy → Supervisor → Resolve → Confirm
```

Keep text diagrams simple. They supplement the numbered steps — they don't replace them.
