# Local Preview Links

Quick reference for everything running locally. All three servers were responding when this file was last updated.

> **These are local servers, not deployments.** They stop when the machine sleeps or the session ends. If a link is dead, see [Restarting](#restarting) at the bottom.

---

## 📊 Client Deck — port 8124

**→ http://localhost:8124/index.html**

Presentation for prospective clients (institutional allocators). Arrow keys to navigate.

Speaker notes and the numbers-provenance table live in `50-deck/NOTES.md` — worth reading before presenting, particularly the run-to-run variance section.

---

## 🖥️ Memo Reader Prototype — port 8123

The interactive design prototype. This is how the memo should look and behave once Phlo renders it.

| Page | Link | What to try |
|---|---|---|
| **Index** | http://localhost:8123/index.html | The landing page — recommendation, scorecard, open-question counts |
| **Section** | http://localhost:8123/section.html | §4 Risk Factors — **click any citation** to open the evidence drawer |
| **Open questions** | http://localhost:8123/open-questions.html | All 57, routed three ways — **try to answer a blocked one** |

**Worth doing in order:**

1. Click a citation → the drawer opens with the cited page text and the quote highlighted. Escape closes it.
2. Find an `unverified` citation → the drawer draws **no highlight** and says why. Honest about what it could not confirm.
3. Try to answer a **blocked** question → there is nothing to click. Verified structurally: 10 blocked sections, **zero** form controls. Not a disabled button — genuinely absent.
4. Try an attestation with a weak source → type `confirmed` or `PPM` and it rejects with a real message.
5. `Cmd+P` → print layout, since PRD 08 exports these as PDFs.

---

## 📄 Documentation & PRDs — port 8000

**→ http://localhost:8000/**

Every markdown file in the repo, with Mermaid diagrams rendered and line-level commenting.

| Document | Link |
|---|---|
| **Overview** — architecture, co-pilot loop, constraints | http://localhost:8000/40-solution-design/l1-analysis-platform/00-overview.md |
| **Criteria** — the personalisation story | http://localhost:8000/40-solution-design/l1-analysis-platform/03-criteria.md |
| **Analysis engine** — the CLI contract | http://localhost:8000/40-solution-design/l1-analysis-platform/06-analysis-engine.md |
| **Evidence loop** — answer questions, re-run | http://localhost:8000/40-solution-design/l1-analysis-platform/07-evidence-loop.md |
| **Version history** — causal diffs | http://localhost:8000/40-solution-design/l1-analysis-platform/08-version-history.md |
| **User journeys** — five roles, narrative | http://localhost:8000/40-solution-design/l1-analysis-platform/user-journeys.md |
| **Regulatory sources** — what is actually reachable | http://localhost:8000/30-analysis/india-regulatory-data-sources.md |
| **Engine README** — implemented vs specified | http://localhost:8000/engine/README.md |

**Click any line to leave a comment.** Comments anchor to line number *plus* quoted text, so they survive edits. They live in browser localStorage — nothing is written to the repo. The **Copy feedback** button produces a paste-ready block you can hand straight back to me.

---

## 📁 Real engine output (not a server — open directly)

The most recent verified run:

```
/tmp/l1-final-verify/05-memo/00-index.md      ← start here
/tmp/l1-final-verify/05-memo/11-open-questions.md   ← 57 questions, ~45KB
/tmp/l1-final-verify/04-scoring.json          ← findings with evidence
/tmp/l1-final-verify/run.json                 ← telemetry: tokens, cost, per stage
```

Run summary: exit 0, $5.70, 17 min, 649,664 tokens, 121/124 quotes verified, 5 red flags, 2 contested, 2 unevaluated vetoes.

```bash
# human-readable summary of any run
cd engine && python3 -m l1.cli inspect /tmp/l1-final-verify
```

---

## Restarting

If a port is dead:

```bash
cd /Users/sharva/DocumentSpaces/L1AnalysisAutomation

# 8000 — markdown/PRD preview
nohup python3 .claude/skills/preview-md/preview_md.py > /tmp/preview.log 2>&1 &

# 8123 — memo reader prototype
cd 40-solution-design/l1-analysis-platform/screen-specs/prototype && \
  nohup python3 -m http.server 8123 > /tmp/proto.log 2>&1 &

# 8124 — client deck
cd 50-deck && nohup python3 -m http.server 8124 > /tmp/deck.log 2>&1 &
```

Check what is alive:

```bash
for p in 8000 8123 8124; do
  printf "%s: " "$p"
  curl -s -o /dev/null -w "HTTP %{http_code}\n" --max-time 3 "http://localhost:$p/" || echo down
done
```

---

## Note

The prototype and deck are **design artifacts**, not running software. The engine produces markdown; Phlo will eventually render it as a real web app. These show how it should look — nothing imports them.
