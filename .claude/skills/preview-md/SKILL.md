---
name: preview-md
description: >
  Live-preview the repository's Markdown files in a browser with an index page,
  auto-refresh (no blink), client-side Mermaid rendering, and line-level inline
  comments that export as paste-ready, line-referenced feedback. Use when the
  user wants to preview/review markdown in a browser, leave comments on specific
  lines, or get review feedback out of a doc. PORTABLE: copy this whole
  `preview-md/` folder into any repo and it works there with no changes.
---

# preview-md

A zero-config local Markdown previewer for reviewing docs in the browser. The
entire skill is **self-contained in this folder** (`SKILL.md` + `preview_md.py`),
so it can be copied into any other repository and run as-is.

## What it does

- **Index** at `/` — lists every `.md` in the repo (skips `.git`, `node_modules`,
  `build`, `repos`, `inbox`, etc.). Click a file to preview.
- **Live preview** — renders with `python-markdown`; the page polls and only
  swaps content when the file changes on disk, so there's **no flicker**.
- **Mermaid** diagrams render client-side via CDN.
- **Inline comments** — click any line to attach a note. Each comment is anchored
  to its **line number + the quoted line text** (robust if lines later shift).
- **Persistence** — comments are saved in the browser's `localStorage`, keyed per
  file, so they survive refresh / closing the tab.
- **Copy feedback** button — produces a clean, paste-ready block:
  ```
  docs/architecture/01-current-state-architecture.md

  L66 · "the middleware reaches SAP over RFC."
    > tighten this sentence

  L82 · "Support user ... not a system role"
    > add why we know this
  ```
  Paste that into Claude and it can apply the edits by line + quote.
- **Clear all** button — wipes this file's comments.

Nothing is ever written to the repo — comments live only in the browser.

## How to run it

The user is typically not CLI-fluent — launch it for them with the Bash tool,
**in the background**, from the repo you want to preview:

```bash
python3 .claude/skills/preview-md/preview_md.py
```

Then tell the user to open **http://localhost:8000/**. Options:

- `--port 8765` — use a different port (if 8000 is busy).
- `docs/` (positional) — limit the index to a subtree.
- `--root <path>` — set the repo root explicitly. By default it auto-detects the
  nearest `.git` directory walking up from the current working directory, falling
  back to CWD — this is what makes the skill portable.

Stop it with the background-task stop tool when the review session is done.

## Requirements

- Python 3.8+
- `python-markdown` (`pip install markdown`). If it's missing the script exits
  with that instruction. (In this repo it's already present — the doc-pack
  `build_pdf.py` uses it too.)

## Using the feedback

When the user pastes a "Copy feedback" block, treat each `Lnn · "quote"` as the
anchor: find that quoted text in the named file (the line number is a hint; the
quote is the source of truth if numbers have drifted) and apply the `>` comment
as the requested change. Confirm ambiguous matches before editing.

## Portability note

To reuse in another project: copy the `preview-md/` folder into that repo's
`.claude/skills/` (or anywhere — the script finds the repo root itself). No paths
in the script are hard-coded to this repo.
