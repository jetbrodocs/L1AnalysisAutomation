#!/usr/bin/env python3
"""
Portable repo-wide live Markdown preview with inline comments.

Drop this whole `preview-md/` skill folder into ANY repo — it has no dependency
on the host repo's layout. It serves every .md file in the repo with:

  - `/`           index of every .md file (click to preview)
  - `/view?f=...` renders a doc; auto-refreshes (no blink) as you edit on disk
  - line-level **inline comments**: click any line to attach a note, anchored to
    its line number + the quoted line text
  - comments persist in the browser's **localStorage** (survive refresh/close)
  - **Copy feedback** -> paste-ready block (file · line · quote · comment);
    **Clear all** wipes this file's comments

Repo root detection (portable): walk up from CWD to the nearest `.git`; if none,
use the current working directory. Override with a positional path or --root.

Dependencies: Python 3.8+ and `python-markdown` (pip install markdown). Mermaid
diagrams render client-side via CDN. Nothing is written to the repo — comments
live only in your browser.

Usage (run from the repo you want to preview):
  python3 .claude/skills/preview-md/preview_md.py
  python3 .claude/skills/preview-md/preview_md.py --port 8765
  python3 .claude/skills/preview-md/preview_md.py docs/   # limit to a subtree
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import http.server
import json
import re
import socketserver
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse, parse_qs, quote

try:
    import markdown
except ImportError:
    sys.exit("This skill needs python-markdown:  pip install markdown")

MERMAID_FENCE = "```mermaid"
MERMAID_RE = re.compile(r"```mermaid\n(.*?)\n```", re.DOTALL)
SKIP_DIRS = {".git", "node_modules", "build", "__pycache__", ".playwright-mcp",
             "repos", "inbox", ".next", "dist", "vendor", ".venv", "venv"}
MD_EXT = ["extra", "tables", "toc", "fenced_code", "sane_lists", "attr_list"]

# diagrams are rendered server-side to PNG (via mmdc) and cached by content hash,
# so the browser receives a finished <img> — no client-side mermaid, no flicker.
_MMD_CACHE = Path(tempfile.gettempdir()) / "preview-md-diagrams"
_MMD_OK = True  # flips False if mmdc/npx is unavailable, then we fall back to a code box


def render_mermaid_to_img(code: str) -> str:
    """Render one mermaid block to a base64 <img>, cached by content hash."""
    global _MMD_OK
    _MMD_CACHE.mkdir(exist_ok=True)
    digest = hashlib.sha1(code.encode()).hexdigest()[:12]
    png = _MMD_CACHE / f"{digest}.png"
    if not png.exists() and _MMD_OK:
        src = _MMD_CACHE / f"{digest}.mmd"
        src.write_text(code)
        try:
            subprocess.run(["npx", "-y", "@mermaid-js/mermaid-cli", "-i", str(src),
                            "-o", str(png), "-b", "white", "-s", "2"],
                           check=True, capture_output=True, text=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            _MMD_OK = False
    if png.exists():
        b64 = base64.b64encode(png.read_bytes()).decode()
        return (f'<div class="mermaid"><img src="data:image/png;base64,{b64}" '
                f'alt="diagram" style="max-width:100%"/></div>')
    # fallback: show the source if mmdc isn't available
    return (f'<pre style="background:#fff4ec;border:1px solid #f0c9a8;padding:8px;'
            f'white-space:pre-wrap">[mermaid — install Node/npx to render]\n\n'
            f'{code}</pre>')


def find_repo_root(start: Path) -> Path:
    """Walk up to the nearest .git; fall back to start (cwd)."""
    p = start.resolve()
    for cand in [p, *p.parents]:
        if (cand / ".git").exists():
            return cand
    return p


# --------------------------------------------------------------------------- #
def list_md(root: Path, base: Path) -> list[Path]:
    out = []
    for p in sorted(root.rglob("*.md")):
        if any(part in SKIP_DIRS for part in p.relative_to(base).parts):
            continue
        out.append(p)
    return out


def render_doc(md_path: Path) -> tuple[str, str]:
    raw = md_path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    # render each ```mermaid``` block to a server-side <img> BEFORE markdown runs,
    # so markdown leaves the finished HTML block untouched (no client-side mermaid).
    md_with_imgs = MERMAID_RE.sub(lambda m: "\n\n" + render_mermaid_to_img(m.group(1)) + "\n\n", raw)
    html = markdown.markdown(md_with_imgs, extensions=MD_EXT)
    raw_json = json.dumps(lines)
    h = hashlib.sha1((html + raw_json).encode()).hexdigest()[:12]
    body = (f'<div id="rawlines" data-lines=\'{raw_json.replace(chr(39), "&#39;")}\'></div>'
            f'<article id="doc">{html}</article>')
    return h, body


def index_page(files: list[Path], base: Path) -> str:
    rows, last_dir = [], None
    for p in files:
        rel = p.relative_to(base).as_posix()
        d = str(Path(rel).parent)
        if d != last_dir:
            rows.append(f"<h3>{d}/</h3>"); last_dir = d
        rows.append(f'<div class="row"><a href="/view?f={quote(rel)}">📄 {p.name}</a></div>')
    return INDEX_HTML.replace("{ROWS}", "\n".join(rows)).replace("{N}", str(len(files)))


INDEX_HTML = """<!doctype html><html><head><meta charset="utf-8">
<title>Markdown preview</title>
<style>
 body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:820px;margin:0 auto;padding:32px;color:#1a1d24}
 h1{color:#1f4e79} h3{color:#5b6470;margin:20px 0 4px;font-size:13px;text-transform:uppercase;letter-spacing:.04em}
 .row{padding:3px 0} a{color:#1f4e79;text-decoration:none} a:hover{text-decoration:underline}
</style></head><body>
<h1>Markdown preview</h1><p>{N} markdown files. Click to preview (live + inline comments).</p>
{ROWS}
</body></html>"""


VIEW_HTML = r"""<!doctype html><html><head><meta charset="utf-8">
<title>{FILE} — preview</title>
<style>
 body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:#1a1d24;line-height:1.55;font-size:15px;margin:0;padding:0}
 .wrap{display:flex}
 main{flex:1;max-width:860px;margin:0 auto;padding:0 32px 64px}
 aside{width:330px;border-left:1px solid #dfe3e8;padding:14px;position:sticky;top:0;height:100vh;overflow:auto;background:#fafbfc;font-size:13px}
 h1{color:#1f4e79;border-bottom:3px solid #1f4e79;padding-bottom:6px}
 h2{color:#1f4e79;border-bottom:1px solid #dfe3e8;padding-bottom:3px;margin-top:28px}
 table{border-collapse:collapse;width:100%;margin:12px 0;font-size:13px}
 th,td{border:1px solid #dfe3e8;padding:6px 9px;text-align:left;vertical-align:top}
 th{background:#f4f6f8} tr:nth-child(even) td{background:#fafbfc}
 code{background:#f4f6f8;padding:1px 5px;border-radius:3px;font-size:90%}
 blockquote{border-left:4px solid #1f4e79;background:#f4f7fb;margin:12px 0;padding:8px 14px}
 .topbar{position:sticky;top:0;background:#fff;border-bottom:2px solid #1f4e79;padding:8px 32px;z-index:20;display:flex;gap:14px;align-items:center;font-size:13px}
 .topbar a{color:#1f4e79;text-decoration:none;font-weight:600}
 #dot{color:#0a0}
 .mermaid{text-align:center;margin:16px 0}
 #doc :is(p,li,h1,h2,h3,td,blockquote){position:relative}
 .ln{cursor:pointer;border-radius:3px}
 .ln:hover{background:#fff7e6;outline:1px dashed #f0c9a8}
 .ln.has{background:#fff4ec}
 .cbtn{background:#1f4e79;color:#fff;border:0;padding:5px 10px;border-radius:5px;cursor:pointer;font-size:12px}
 .cbtn.sec{background:#b54708}
 .cmt{border:1px solid #dfe3e8;background:#fff;border-radius:6px;padding:8px;margin:8px 0}
 .cmt .meta{color:#5b6470;font-size:11px;margin-bottom:4px}
 .cmt .q{font-style:italic;color:#243;border-left:3px solid #1f4e79;padding-left:6px;margin:3px 0}
 .cmt .act{float:right;font-size:11px}
 .cmt .act a{cursor:pointer;color:#1f4e79;text-decoration:none}
 .cmt .act a.d{color:#c00}
 .cmt .act a:hover{text-decoration:underline}
 /* comment modal */
 #ov{display:none;position:fixed;inset:0;background:rgba(20,25,35,.45);z-index:100}
 #modal{display:none;position:fixed;z-index:101;top:50%;left:50%;transform:translate(-50%,-50%);
        width:460px;max-width:92vw;background:#fff;
        border:1px solid #cdd6e0;border-radius:10px;box-shadow:0 18px 50px rgba(0,0,0,.28);
        padding:16px;font-size:14px}
 #modal h4{margin:0 0 6px;color:#1f4e79;font-size:14px}
 #modal .mq{font-style:italic;color:#243;background:#f4f7fb;border-left:3px solid #1f4e79;
            padding:6px 10px;border-radius:4px;margin:6px 0;font-size:12.5px;max-height:80px;overflow:auto}
 #modal textarea{width:100%;border:1px solid #cdd6e0;border-radius:6px;font:inherit;font-size:13px;
                 min-height:84px;padding:8px;box-sizing:border-box;resize:vertical}
 #modal .row{display:flex;gap:8px;align-items:center;margin-top:10px}
 #modal .row .sp{flex:1}
 #modal .hint{color:#8a93a0;font-size:11px}
</style></head><body>
<div class="topbar">
  <a href="/">⌂ index</a>
  <strong>{FILE}</strong>
  <span style="color:#888">live <span id="dot">●</span></span>
  <span style="flex:1"></span>
  <button class="cbtn" onclick="copyAll()">Copy feedback</button>
  <button class="cbtn sec" onclick="clearAll()">Clear all</button>
</div>
<div class="wrap">
  <main><div id="content">loading…</div></main>
  <aside><h3 style="margin-top:4px">Comments</h3><div id="clist"></div></aside>
</div>
<div id="ov" onclick="closeModal()"></div>
<div id="modal">
  <h4 id="mwhere">Comment</h4>
  <div class="mq" id="mquote"></div>
  <textarea id="mtext" placeholder="Type your comment… (⌘/Ctrl+Enter to save, Esc to cancel)"></textarea>
  <div class="row">
    <span class="hint" id="mhint"></span>
    <span class="sp"></span>
    <button class="cbtn sec" id="mdel" style="display:none" onclick="modalDelete()">Delete</button>
    <button class="cbtn" style="background:#9aa3ad" onclick="closeModal()">Cancel</button>
    <button class="cbtn" onclick="modalSave()">Save</button>
  </div>
</div>
<script>
const FILE = "{FILE}";
const KEY = "mdcmt:" + FILE;
let comments = JSON.parse(localStorage.getItem(KEY) || "{}");
let rawLines = [], lastHash = "";
function save(){ localStorage.setItem(KEY, JSON.stringify(comments)); renderList(); }
// best-effort: find the source line number whose text matches this block's
// visible text. Returns 0 if no confident match (comment still works, anchored
// to the visible quote).
function findLine(text){
  const probe = text.trim();
  if(!probe) return 0;
  // try progressively shorter prefixes of the visible text
  for(const n of [30,18,10]){
    const frag = probe.slice(0,n);
    for(let i=0;i<rawLines.length;i++){
      if(rawLines[i].includes(frag)) return i+1;
    }
  }
  return 0;
}
function tagLines(){
  // EVERY block is clickable. key = sequential block index (stable per render),
  // so a comment is never lost just because line-matching failed.
  const blocks = document.querySelectorAll('#doc :is(p,li,h1,h2,h3,h4,td,blockquote)');
  let idx = 0;
  blocks.forEach(el=>{
    const text = el.textContent.trim();
    if(!text) return;
    idx++;
    el.dataset.k = idx;
    el.dataset.ln = findLine(text);
    el.dataset.quote = text.slice(0,120);
    el.classList.add('ln');
    if(comments[idx]) el.classList.add('has');
    el.addEventListener('click', (e)=>{ if(e.target.tagName==='A') return; openComment(el); });
  });
}
let activeEl = null;
function openComment(el){
  activeEl = el;
  const k = el.dataset.k, ln = el.dataset.ln || 0, quote = el.dataset.quote || '';
  const c = comments[k];
  document.getElementById('mwhere').textContent = 'Comment on ' + (ln>0 ? ('line '+ln) : '(line n/a)');
  document.getElementById('mquote').textContent = '"' + quote + '"';
  document.getElementById('mhint').textContent = c ? 'editing existing comment' : '';
  document.getElementById('mdel').style.display = c ? '' : 'none';
  const ta = document.getElementById('mtext');
  ta.value = c?.text || '';
  // modal is centered in the viewport via CSS (top/left/transform)
  document.getElementById('ov').style.display='block';
  document.getElementById('modal').style.display='block';
  ta.focus();
}
function closeModal(){ document.getElementById('ov').style.display='none';
  document.getElementById('modal').style.display='none'; activeEl=null; }
function modalSave(){
  if(!activeEl) return;
  const k=activeEl.dataset.k, ln=Number(activeEl.dataset.ln||0), quote=activeEl.dataset.quote||'';
  const txt=document.getElementById('mtext').value.trim();
  if(txt==='') delete comments[k]; else comments[k]={ln, quote, text:txt};
  activeEl.classList.toggle('has', !!comments[k]); save(); closeModal();
}
function modalDelete(){ if(!activeEl) return; const k=activeEl.dataset.k;
  delete comments[k]; activeEl.classList.remove('has'); save(); closeModal(); }
document.addEventListener('keydown',(e)=>{
  if(document.getElementById('modal').style.display!=='block') return;
  if(e.key==='Escape') closeModal();
  if((e.metaKey||e.ctrlKey)&&e.key==='Enter') modalSave();
});
function renderList(){
  const keys = Object.keys(comments).sort((a,b)=>(comments[a].ln||0)-(comments[b].ln||0));
  document.getElementById('clist').innerHTML = keys.length ? keys.map(k=>{
    const c = comments[k]; const where = c.ln>0 ? ('L'+c.ln) : 'line n/a';
    return `<div class="cmt">
      <span class="act"><a onclick="copyOne('${k}')">copy</a> · <a class="d" onclick="delC('${k}')">delete</a></span>
      <div class="meta">${where}</div>
      <div class="q">"${(c.quote||'').replace(/</g,'&lt;')}"</div>
      <div>${c.text.replace(/</g,'&lt;')}</div></div>`;
  }).join('') : '<p style="color:#888">No comments yet. Click any line/paragraph to add one.</p>';
}
function fmtOne(c){ const where=c.ln>0?('L'+c.ln):'(line n/a)';
  return `${FILE}\n\n${where} · "${c.quote}"\n  > ${c.text}\n`; }
function copyOne(k){ const c=comments[k]; if(!c) return;
  const t=fmtOne(c);
  navigator.clipboard.writeText(t).then(()=>flash('Comment copied'),()=>prompt('Copy this:',t)); }
function flash(msg){ const d=document.getElementById('dot'); const o=d.textContent;
  d.textContent='✓ '+msg; setTimeout(()=>{d.textContent=o;}, 1200); }
function delC(k){ delete comments[k]; save(); document.querySelectorAll(`[data-k="${k}"]`).forEach(e=>e.classList.remove('has')); }
function clearAll(){ if(confirm('Clear all comments on this file?')){ comments={}; save(); document.querySelectorAll('.ln.has').forEach(e=>e.classList.remove('has')); } }
function copyAll(){
  const keys = Object.keys(comments).sort((a,b)=>(comments[a].ln||0)-(comments[b].ln||0));
  if(!keys.length){ alert('No comments to copy.'); return; }
  let out = FILE + "\n\n";
  keys.forEach(k=>{ const c=comments[k]; const where=c.ln>0?('L'+c.ln):'(line n/a)';
    out += `${where} · "${c.quote}"\n  > ${c.text}\n\n`; });
  navigator.clipboard.writeText(out).then(()=>alert('Feedback copied — paste it into Claude.'),
    ()=>prompt('Copy this:', out));
}
let polling = false;
async function poll(){
  if(polling) return;            // never overlap (renderMermaid is async)
  polling = true;
  try{
    const r = await fetch('/api?f='+encodeURIComponent(FILE));
    const j = await r.json();
    if(j.hash!==lastHash){
      document.getElementById('content').innerHTML=j.html;
      const isl=document.getElementById('rawlines');
      rawLines = isl ? JSON.parse(isl.dataset.lines.replace(/&#39;/g,"'")) : [];
      tagLines();                // diagrams are already finished <img>s from the server
      lastHash=j.hash;
    }
    document.getElementById('dot').style.color='#0a0';
  }catch(e){ document.getElementById('dot').style.color='#c00'; }
  finally{ polling=false; }
}
renderList(); poll(); setInterval(poll, 1200);
</script>
</body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    root: Path = Path.cwd()
    base: Path = Path.cwd()

    def _send(self, body: bytes, ctype: str):
        self.send_response(200); self.send_header("Content-Type", ctype)
        self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            self._send(index_page(list_md(self.root, self.base), self.base).encode(),
                       "text/html; charset=utf-8")
        elif u.path == "/view":
            f = (parse_qs(u.query).get("f") or [""])[0]
            self._send(VIEW_HTML.replace("{FILE}", f).encode(), "text/html; charset=utf-8")
        elif u.path == "/api":
            f = (parse_qs(u.query).get("f") or [""])[0]
            target = (self.base / f).resolve()
            if not target.exists() or self.base not in target.parents:
                self._send(b'{"hash":"x","html":"<p>not found</p>"}', "application/json"); return
            h, html = render_doc(target)
            self._send(json.dumps({"hash": h, "html": html}).encode(),
                       "application/json; charset=utf-8")
        else:
            self.send_error(404)

    def log_message(self, *a):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("subdir", nargs="?", default=None, help="limit listing to a subtree")
    ap.add_argument("--root", default=None, help="repo root (default: nearest .git up from CWD)")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    base = Path(args.root).resolve() if args.root else find_repo_root(Path.cwd())
    Handler.base = base
    Handler.root = (base / args.subdir).resolve() if args.subdir else base
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", args.port), Handler) as httpd:
        rel = Handler.root.relative_to(base) if Handler.root != base else Path(".")
        print(f"Markdown preview: http://localhost:{args.port}/   (root: {base.name}/{rel})")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
