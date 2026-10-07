"""Watch reviewer agents work: a live page for a folder of puzzle packets.

    blitz watch [folder]

Each puzzle folder holds what a text-first review leaves behind as it goes:
`sheets/shown.json` (the crops the reviewer asked to see, in order),
`draft.json` (its verdict) and `review.json` (after `finish`). The page polls
those files and shows, per puzzle, where on the scan the reviewer is looking,
the contact sheets it read, and what it changed, beside a batch overview.

Standard library only (the page is plain HTML and script), so it also runs
on its own: python -m blitz.watch <folder>.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def entries(grid: list[str]) -> dict[str, list[list[int]]]:
    """Standard numbering: entry id (A1, D2) -> its squares [row, col], 0-based."""
    rows, cols = len(grid), len(grid[0]) if grid else 0
    white = lambda r, c: 0 <= r < rows and 0 <= c < cols and grid[r][c] != "#"
    out, n = {}, 0
    for r in range(rows):
        for c in range(cols):
            if not white(r, c):
                continue
            across = not white(r, c - 1) and white(r, c + 1)
            down = not white(r - 1, c) and white(r + 1, c)
            if across or down:
                n += 1
            if across:
                out[f"A{n}"] = [[r, cc] for cc in range(c, cols) if all(white(r, k) for k in range(c, cc + 1))]
            if down:
                out[f"D{n}"] = [[rr, c] for rr in range(r, rows) if all(white(k, c) for k in range(r, rr + 1))]
    return out


def puzzle_state(d: Path) -> dict:
    """Everything the page shows about one puzzle folder, read fresh."""
    ocr = _read(d / "ocr.json") or {}
    shown = _read(d / "sheets" / "shown.json") or {"shown": [], "sheets": []}
    draft, review = _read(d / "draft.json"), _read(d / "review.json")
    t_sheets, t_draft, t_review = (_mtime(d / "sheets" / "shown.json"), _mtime(d / "draft.json"),
                                   _mtime(d / "review.json"))
    sheet_files = sorted((d / "sheets").glob("sheet_*.png"), key=lambda p: int(re.sub(r"\D", "", p.stem) or 0))
    # Where the review is: the newest file it wrote says how far it got.
    if review is not None and t_review >= t_draft:
        status = "escalated" if review.get("escalate") else ("ready" if review.get("ready") else "needs a person")
    elif draft is not None:
        status = "writing"
    elif t_sheets:
        status = "looking"
    else:
        status = "waiting"
    events = [{"t": _mtime(f), "what": "sheet", "file": f"{d.name}/sheets/{f.name}",
               "crops": next((s["crops"] for s in shown.get("sheets", []) if Path(s["file"]).name == f.name), [])}
              for f in sheet_files]
    if t_draft:
        events.append({"t": t_draft, "what": "draft"})
    if t_review:
        events.append({"t": t_review, "what": "review"})
    rv = review if review is not None else {}
    clues = ocr.get("clues") or {}
    answers = ocr.get("answers") or []
    changes = []
    for item, value in (rv.get("corrections") or {}).items():
        kind, _, key = item.partition(":")
        was = ""
        if kind == "clue":
            was = (clues.get(key) or {}).get("text", "")
        elif kind == "cell":
            m = re.fullmatch(r"r(\d+)c(\d+)", key)
            if m and answers:
                r, c = int(m[1]) - 1, int(m[2]) - 1
                was = answers[r][c] if r < len(answers) and c < len(answers[r]) else ""
        elif kind == "meta":
            was = ocr.get(key, "")
        elif kind == "other":
            was = (ocr.get("captions") or {}).get(key, "") if isinstance(ocr.get("captions"), dict) else ""
        changes.append({"item": item, "was": was, "now": value})
    grid = ocr.get("grid") or []
    return {
        "xdid": d.name, "status": status, "updated": max([t_sheets, t_draft, t_review] + [e["t"] for e in events]),
        "title": (rv.get("corrections") or {}).get("meta:title") or ocr.get("title", ""),
        "byline": ocr.get("byline", ""), "size": f"{len(grid)}x{len(grid[0])}" if grid else "",
        "shown": shown.get("shown", []), "events": sorted(events, key=lambda e: e["t"]),
        "changes": changes, "sic": rv.get("sic") or {}, "unsure": rv.get("unsure") or {},
        "escalate": rv.get("escalate", ""), "note": rv.get("note", ""), "remaining": rv.get("remaining", ""),
        "tool_notes": rv.get("tool_notes") or (draft or {}).get("tool_notes") or [],
        "draft_only": review is None and draft is not None,
        # for drawing what was looked at on the scan
        "scale": (ocr.get("scales") or {}).get("page.jpg", 1.0), "clue_image": ocr.get("clue_image", "page.jpg"),
        "boxes": {k: v.get("box") for k, v in clues.items() if v.get("box")}, "meta_boxes": ocr.get("meta_boxes") or {},
        "grid": grid, "entries": entries(grid) if grid else {},
        "has": {f: (d / f).exists() for f in ("page.jpg", "grid.png", "answers.png")},
    }


def batch_state(root: Path) -> dict:
    puzzles = [puzzle_state(d) for d in sorted(root.iterdir()) if d.is_dir() and (d / "ocr.json").exists()]
    return {"root": root.name, "now": time.time(), "puzzles": puzzles}


class Handler(BaseHTTPRequestHandler):
    root: Path

    def log_message(self, *a):  # quiet
        pass

    def _send(self, body: bytes, ctype: str, code: int = 200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path in ("/", "/index.html"):
            return self._send(PAGE.encode("utf-8"), "text/html; charset=utf-8")
        if path == "/api/state":
            return self._send(json.dumps(batch_state(self.root)).encode("utf-8"), "application/json")
        f = (self.root / path.lstrip("/")).resolve()
        if self.root.resolve() not in f.parents or not f.is_file() or f.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            return self._send(b"not found", "text/plain", 404)
        self._send(f.read_bytes(), mimetypes.guess_type(f.name)[0] or "application/octet-stream")


def serve(root: Path, port: int = 8770, open_browser: bool = True) -> None:
    Handler.root = root
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    print(f"watching {root} at {url} (Ctrl+C to stop)")
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description="watch reviewer agents work on a folder of puzzle packets")
    p.add_argument("folder", help="folder of puzzle packets (one subfolder per puzzle)")
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8770)))
    p.add_argument("--no-browser", action="store_true")
    a = p.parse_args(argv)
    root = Path(a.folder)
    if not root.is_dir():
        sys.exit(f"no folder {root}")
    serve(root, a.port, not a.no_browser)


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Review watch</title>
<style>
:root{--bg:#f7f5f0;--panel:#fff;--ink:#1d1d1b;--muted:#6b6860;--line:#e2ded4;--accent:#b4501e;--look:#1f6fd1;--fix:#c2410c;--ok:#15803d;--warn:#b45309;--bad:#b91c1c}
@media (prefers-color-scheme:dark){:root{--bg:#171614;--panel:#211f1c;--ink:#ece8df;--muted:#a19c90;--line:#38342e;--accent:#e08a5a;--look:#6aa8ff;--fix:#fb923c;--ok:#4ade80;--warn:#fbbf24;--bad:#f87171}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,sans-serif}
header{display:flex;gap:16px;align-items:baseline;padding:12px 16px;border-bottom:1px solid var(--line);flex-wrap:wrap}
h1{font-size:17px;margin:0}.muted{color:var(--muted)}.counts span{margin-right:12px}
.wrap{display:grid;grid-template-columns:260px 1fr;min-height:calc(100vh - 50px)}
@media (max-width:800px){.wrap{grid-template-columns:1fr}}
nav{border-right:1px solid var(--line);overflow:auto;max-height:calc(100vh - 50px)}
.p{display:flex;justify-content:space-between;gap:8px;padding:7px 12px;border-bottom:1px solid var(--line);cursor:pointer}
.p:hover{background:var(--panel)}.p.sel{background:var(--panel);box-shadow:inset 3px 0 var(--accent)}
.chip{font-size:11px;padding:1px 7px;border-radius:9px;border:1px solid currentColor;white-space:nowrap}
.s-waiting{color:var(--muted)}.s-looking{color:var(--look)}.s-writing{color:var(--warn)}.s-ready{color:var(--ok)}
.s-needs{color:var(--warn)}.s-escalated{color:var(--bad)}
.live::before{content:"";display:inline-block;width:7px;height:7px;border-radius:50%;background:currentColor;margin-right:5px;animation:pulse 1.2s infinite}
@keyframes pulse{50%{opacity:.25}}
main{padding:14px 16px;overflow:auto;max-height:calc(100vh - 50px)}
.top{display:flex;justify-content:space-between;gap:12px;align-items:baseline;flex-wrap:wrap}
.scans{display:flex;gap:14px;flex-wrap:wrap;margin:10px 0}
.scan{position:relative;background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:6px}
.scan img{display:block;max-width:100%}.scan .lbl{font-size:12px;color:var(--muted);margin-bottom:4px}
.hl{position:absolute;border:2px solid var(--look);background:color-mix(in srgb,var(--look) 15%,transparent);pointer-events:none}
.hl.fix{border-color:var(--fix);background:color-mix(in srgb,var(--fix) 18%,transparent)}
.hl.new{animation:flash 1.5s 2}@keyframes flash{50%{border-width:4px}}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:8px;margin:8px 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:8px 10px}
.card b{font-size:12px;color:var(--muted);font-weight:600}
del{color:var(--bad)}ins{color:var(--ok);text-decoration:none;font-weight:600}
.sheets{display:flex;gap:8px;overflow-x:auto;padding-bottom:6px}
.sheets img{height:160px;border:1px solid var(--line);border-radius:4px;cursor:zoom-in;background:#fff}
.feed{font-size:13px;margin:0;padding-left:18px}.feed li{margin:2px 0}
h3{font-size:13px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin:16px 0 6px}
.zoom{position:fixed;inset:0;background:rgba(0,0,0,.8);display:none;align-items:center;justify-content:center;z-index:9;cursor:zoom-out}
.zoom img{max-width:95vw;max-height:95vh;background:#fff}
label{font-size:13px}
</style></head><body>
<header><h1>Review watch: <span id="root"></span></h1><span class="counts" id="counts"></span>
<label><input type="checkbox" id="follow" checked> follow the latest activity</label></header>
<div class="wrap"><nav id="list"></nav><main id="main"><p class="muted">Waiting for reviews…</p></main></div>
<div class="zoom" id="zoom"><img alt="contact sheet"></div>
<script>
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let S = null, sel = null, seenTargets = {};
const ago = t => { const s = Math.max(0, Math.round(S.now - t)); return s < 60 ? `${s}s ago` : s < 3600 ? `${Math.round(s/60)} min ago` : `${Math.round(s/3600)} h ago`; };
const chip = st => `<span class="chip s-${st.split(' ')[0]} ${['looking','writing'].includes(st) && S && S.now - 0 ? 'live' : ''}">${esc(st)}</span>`;
const label = it => it.replace(/^clue:/, '').replace(/^cell:/, 'square ').replace(/^meta:/, '').replace(/^other:/, 'caption ');

function wordDiff(a, b) {
  const A = a.split(/(\s+)/), B = b.split(/(\s+)/);
  const n = A.length, m = B.length, L = Array.from({length: n + 1}, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) L[i][j] = A[i] === B[j] ? L[i+1][j+1] + 1 : Math.max(L[i+1][j], L[i][j+1]);
  let i = 0, j = 0, out = '';
  while (i < n || j < m) {
    if (i < n && j < m && A[i] === B[j]) { out += esc(A[i]); i++; j++; }
    else if (j < m && (i >= n || L[i][j+1] >= L[i+1][j])) { out += B[j].trim() ? `<ins>${esc(B[j])}</ins>` : esc(B[j]); j++; }
    else { out += A[i].trim() ? `<del>${esc(A[i])}</del>` : esc(A[i]); i++; }
  }
  return out;
}

// What a crop target covers: page boxes (in original-page pixels) or grid squares.
function pageBox(P, t) {
  const [k, v] = [t.split(':')[0], t.slice(t.indexOf(':') + 1)];
  if (k === 'clue') return P.boxes[v];
  if (k === 'box') return v.split(',').map(Number);
  if (k === 'meta') return P.meta_boxes[v];
  if (k === 'caption') return P.meta_boxes['other' + v];
}
function squares(P, t) {
  const [k, v] = [t.split(':')[0], t.slice(t.indexOf(':') + 1)], R = P.grid.length, C = R ? P.grid[0].length : 0;
  if ((k === 'cell' || k === 'grid') && v === 'all') return [[0, 0, R, C]];
  let m = /^r(\d+)c(\d+)$/.exec(v);
  if ((k === 'cell' || k === 'grid') && m) return [[+m[1]-2, +m[2]-2, 3, 3]];
  if (k === 'row') return [[+v-1, 0, 1, C]];
  if (k === 'col') return [[0, +v-1, R, 1]];
  if (k === 'entry' && P.entries[v]) { const sq = P.entries[v]; const r = sq.map(s => s[0]), c = sq.map(s => s[1]);
    return [[Math.min(...r), Math.min(...c), Math.max(...r) - Math.min(...r) + 1, Math.max(...c) - Math.min(...c) + 1]]; }
  return [];
}

function overlay(img, P, which) {
  const wrap = img.parentElement; wrap.querySelectorAll('.hl').forEach(e => e.remove());
  if (!img.naturalWidth) return;
  const k = img.clientWidth / img.naturalWidth, fixed = new Set(P.changes.map(c => c.item));
  const fresh = new Set(P.shown.filter(t => !(seenTargets[P.xdid] || new Set()).has(t)));
  const add = (x, y, w, h, t) => { const d = document.createElement('div'); d.className = 'hl' + (fixed.has(t) ? ' fix' : '') + (fresh.has(t) ? ' new' : '');
    d.title = t; Object.assign(d.style, {left: img.offsetLeft + x * k + 'px', top: img.offsetTop + y * k + 'px', width: w * k + 'px', height: h * k + 'px'}); wrap.appendChild(d); };
  for (const t of P.shown) {
    if (which === 'page') { const b = pageBox(P, t); if (b) add(b[0] - 3, b[1] - 3, b[2] - b[0] + 6, b[3] - b[1] + 6, t); }  // boxes are in page.jpg pixels
    else {
      const kind = t.split(':')[0];
      if ((which === 'grid') !== (kind === 'grid')) continue;
      const R = P.grid.length, C = R ? P.grid[0].length : 1, cw = img.naturalWidth / C, ch = img.naturalHeight / R;
      for (const [r, c, h, w] of squares(P, t)) { const r0 = Math.max(0, r), c0 = Math.max(0, c);
        add(c0 * cw, r0 * ch, (Math.min(C, c + w) - c0) * cw, (Math.min(R, r + h) - r0) * ch, t); }
    }
  }
}

function renderList() {
  const counts = {};
  S.puzzles.forEach(P => counts[P.status] = (counts[P.status] || 0) + 1);
  $('#counts').innerHTML = ['waiting','looking','writing','ready','needs a person','escalated'].filter(s => counts[s]).map(s => `<span>${chip(s)} ${counts[s]}</span>`).join('');
  $('#list').innerHTML = S.puzzles.map(P => `<div class="p ${P.xdid === sel ? 'sel' : ''}" data-x="${P.xdid}"><span>${esc(P.xdid)}<br><span class="muted" style="font-size:12px">${P.updated ? ago(P.updated) : ''}</span></span>${chip(P.status)}</div>`).join('');
  document.querySelectorAll('.p').forEach(el => el.onclick = () => { sel = el.dataset.x; $('#follow').checked = false; render(); });
}

function renderMain() {
  const P = S.puzzles.find(p => p.xdid === sel); if (!P) return;
  const ev = P.events.slice().reverse().map(e => e.what === 'sheet' ? `<li>${ago(e.t)}: looked at ${e.crops.length} crop${e.crops.length === 1 ? '' : 's'}: ${esc(e.crops.join(', '))}</li>`
    : `<li>${ago(e.t)}: ${e.what === 'draft' ? 'wrote its verdict (draft.json)' : 'finished (review.json)'}</li>`).join('');
  const cards = P.changes.map(c => `<div class="card"><b>${esc(label(c.item))}</b><br>${c.item.startsWith('cell:') ? `<del>${esc(c.was || '?')}</del> → <ins>${esc(c.now)}</ins>` : c.now === '' ? `<del>${esc(c.was || '(removed)')}</del>` : wordDiff(c.was || '', c.now)}</div>`).join('');
  const sic = Object.entries(P.sic).map(([k, v]) => `<div class="card"><b>${esc(k)}: kept as printed</b><br>meant: ${esc(v)}</div>`).join('');
  const uns = Object.entries(P.unsure).map(([k, v]) => `<div class="card"><b>${esc(label(k))}: unsure</b><br>${esc(v)}</div>`).join('');
  const notes = P.tool_notes.map(n => typeof n === 'string' ? n : `${n.kind}${n.target ? ' ' + n.target : ''}: ${n.note}`).map(n => `<li>${esc(n)}</li>`).join('');
  const sheets = P.events.filter(e => e.what === 'sheet').map(e => `<img src="${esc(e.file)}?t=${e.t}" title="${esc(e.crops.join(', '))}" alt="contact sheet">`).join('');
  $('#main').innerHTML = `<div class="top"><div><h2 style="margin:0;font-size:18px">${esc(P.title || P.xdid)}</h2>
    <span class="muted">${esc(P.xdid)} · ${esc(P.byline)} · ${esc(P.size)}</span></div>${chip(P.status)}</div>
    ${P.escalate ? `<p style="color:var(--bad)"><b>Escalated:</b> ${esc(P.escalate)}</p>` : ''}
    ${P.note ? `<p class="muted">${esc(P.note)}</p>` : ''}
    <div class="scans">
      ${P.has['page.jpg'] ? `<div class="scan" style="flex:2 1 420px"><div class="lbl">The page: <span style="color:var(--look)">■</span> looked at · <span style="color:var(--fix)">■</span> corrected</div><img id="pg" src="${esc(P.xdid)}/page.jpg" alt="scanned page"></div>` : ''}
      <div style="display:flex;flex-direction:column;gap:14px;flex:1 1 260px">
      ${P.has['grid.png'] ? `<div class="scan"><div class="lbl">Grid</div><img id="gr" src="${esc(P.xdid)}/grid.png" alt="puzzle grid"></div>` : ''}
      ${P.has['answers.png'] ? `<div class="scan"><div class="lbl">Answer key</div><img id="an" src="${esc(P.xdid)}/answers.png" alt="answer key"></div>` : ''}</div>
    </div>
    <h3>What it changed${P.draft_only ? ' (draft, not finished yet)' : ''}</h3>
    ${cards || sic || uns ? `<div class="cards">${cards}${sic}${uns}</div>` : `<p class="muted">${P.status === 'waiting' || P.status === 'looking' ? 'Nothing yet.' : 'No changes.'}</p>`}
    <h3>Contact sheets it read</h3>${sheets ? `<div class="sheets">${sheets}</div>` : '<p class="muted">None yet.</p>'}
    <h3>Activity</h3>${ev ? `<ul class="feed">${ev}</ul>` : '<p class="muted">Not started.</p>'}
    ${notes ? `<h3>Notes on the tools</h3><ul class="feed">${notes}</ul>` : ''}`;
  const hook = (id, which) => { const im = document.getElementById(id); if (!im) return; const go = () => overlay(im, P, which); im.complete ? go() : im.onload = go; };
  hook('pg', 'page'); hook('gr', 'grid'); hook('an', 'cell');
  document.querySelectorAll('.sheets img').forEach(im => im.onclick = () => { $('#zoom img').src = im.src; $('#zoom').style.display = 'flex'; });
  seenTargets[P.xdid] = new Set(P.shown);
}

let lastKey = '';
function render() { renderList(); renderMain(); }
async function poll() {
  try {
    S = await (await fetch('api/state')).json();
    $('#root').textContent = S.root;
    if ($('#follow').checked || !sel) {
      const live = S.puzzles.filter(P => P.updated).sort((a, b) => b.updated - a.updated)[0];
      sel = live ? live.xdid : S.puzzles[0]?.xdid;
    }
    const P = S.puzzles.find(p => p.xdid === sel);
    const key = sel + JSON.stringify(P && [P.status, P.shown.length, P.changes.length, P.events.length]);
    if (key !== lastKey) { lastKey = key; render(); } else renderList();
  } catch (e) {}
  setTimeout(poll, 2000);
}
$('#zoom').onclick = () => $('#zoom').style.display = 'none';
window.onresize = () => S && renderMain();
poll();
</script></body></html>
"""

if __name__ == "__main__":
    main()
