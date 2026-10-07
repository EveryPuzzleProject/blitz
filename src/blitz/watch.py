"""Watch reviews happen: a live page for a folder of puzzle packets.

    blitz watch [folder]

Each puzzle folder holds what a text-first review leaves behind as it goes:
`sheets/shown.json` (the crops the reviewer asked to see, in order),
`draft.json` (its verdict) and `review.json` (after `finish`). The page polls
those files and shows, per puzzle, where on the scan the reviewer looked, the
contact sheets it read, what it changed (hover a change to see it on the
scan, click to zoom there), and a preview of the puzzle that results, as a
grid and as xd text.
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
from urllib.parse import parse_qs, unquote, urlparse

DOCS = Path(__file__).resolve().parents[2] / "docs"  # the blitz site: puzzle.js builds the corrected puzzle


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


def _status(d: Path) -> tuple[str, float]:
    review, t_draft, t_review = _read(d / "review.json"), _mtime(d / "draft.json"), _mtime(d / "review.json")
    t_sheets = _mtime(d / "sheets" / "shown.json")
    if review is not None and t_review >= t_draft:
        st = "escalated" if review.get("escalate") else ("ready" if review.get("ready") else "needs a person")
    elif t_draft:
        st = "writing"
    elif t_sheets:
        st = "looking"
    else:
        st = "waiting"
    return st, max(t_sheets, t_draft, t_review)


def batch_state(root: Path) -> dict:
    puzzles = []
    for d in sorted(root.iterdir()):
        if d.is_dir() and (d / "ocr.json").exists():
            st, t = _status(d)
            dec = _read(d / "decisions.json") or {}
            puzzles.append({"xdid": d.name, "status": st, "updated": t, "verdict": dec.get("verdict", ""),
                            "rejected": sum(1 for v in (dec.get("items") or {}).values() if v == "reject")})
    return {"root": root.name, "now": time.time(), "puzzles": puzzles}


def puzzle_detail(d: Path) -> dict:
    """Everything the page shows about one puzzle, read fresh."""
    ocr = _read(d / "ocr.json") or {}
    shown = _read(d / "sheets" / "shown.json") or {"shown": [], "sheets": []}
    draft, review = _read(d / "draft.json"), _read(d / "review.json")
    st, updated = _status(d)
    if draft is not None and (review is None or _mtime(d / "draft.json") > _mtime(d / "review.json")):
        try:  # a draft not finished yet: show what finishing it would give
            from .review import finish

            review, _ = finish(ocr, draft, shown.get("shown", []))
            review["_draft"] = True
        except Exception:
            pass
    events = []
    for s in shown.get("sheets", []):
        f = d / "sheets" / Path(s["file"]).name
        events.append({"t": _mtime(f), "what": "sheet", "file": f"{d.name}/sheets/{f.name}", "crops": s["crops"]})
    for name in ("draft", "review"):
        if (d / f"{name}.json").exists():
            events.append({"t": _mtime(d / f"{name}.json"), "what": name})
    src = {n: (d / "_src" / n).exists() for n in ("page.jpg", "clue_page.jpg")}
    return {
        "xdid": d.name, "status": st, "updated": updated, "ocr": ocr, "review": review or {},
        "shown": shown.get("shown", []), "events": sorted(events, key=lambda e: e["t"]),
        "has": {f: (d / f).exists() for f in ("page.jpg", "clue_page.jpg", "grid.png", "answers.png")}, "src": src,
        "decisions": _read(d / "decisions.json") or {"items": {}, "notes": {}, "verdict": "", "note": ""},
    }


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

    def do_POST(self):
        """Save a decision from the page: {"x", "item", "decision": "accept"|"reject", "note"} or
        {"x", "verdict": "looks-right"|"needs-work"|"", "note"}, into <puzzle>/decisions.json."""
        if urlparse(self.path).path != "/api/decide":
            return self._send(b"not found", "text/plain", 404)
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except ValueError:
            return self._send(b"bad json", "text/plain", 400)
        x = str(body.get("x", ""))
        d = self.root / x
        if not re.fullmatch(r"[\w-]+", x) or not (d / "ocr.json").exists():
            return self._send(b"no such puzzle", "text/plain", 404)
        dec = _read(d / "decisions.json") or {}
        dec.setdefault("items", {})
        dec.setdefault("notes", {})
        if "item" in body:
            item = str(body["item"])
            if body.get("decision") in ("reject", "accept"):
                dec["items"][item] = body["decision"]
                if body["decision"] == "reject":
                    dec["notes"][item] = str(body.get("note", ""))
                else:
                    dec["notes"].pop(item, None)
            else:
                dec["items"].pop(item, None)
                dec["notes"].pop(item, None)
        if "verdict" in body:
            dec["verdict"] = body["verdict"] if body["verdict"] in ("looks-right", "needs-work") else ""
            dec["note"] = str(body.get("note", ""))
        dec["at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        (d / "decisions.json").write_text(json.dumps(dec, indent=1, ensure_ascii=False), encoding="utf-8")
        self._send(json.dumps(dec).encode("utf-8"), "application/json")

    def do_GET(self):
        u = urlparse(self.path)
        path = unquote(u.path)
        if path in ("/", "/index.html"):
            return self._send(PAGE.encode("utf-8"), "text/html; charset=utf-8")
        if path == "/api/state":
            return self._send(json.dumps(batch_state(self.root)).encode("utf-8"), "application/json")
        if path == "/api/puzzle":
            x = (parse_qs(u.query).get("x") or [""])[0]
            d = self.root / x
            if not re.fullmatch(r"[\w-]+", x) or not (d / "ocr.json").exists():
                return self._send(b"{}", "application/json", 404)
            return self._send(json.dumps(puzzle_detail(d)).encode("utf-8"), "application/json")
        if path == "/puzzle.js":
            f = DOCS / "puzzle.js"
            body = f.read_bytes() if f.exists() else b"function buildPuzzle(){return null}"
            return self._send(body, "text/javascript; charset=utf-8")
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
    p = argparse.ArgumentParser(description="watch reviews of a folder of puzzle packets")
    p.add_argument("folder")
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8770)))
    p.add_argument("--no-browser", action="store_true")
    a = p.parse_args(argv)
    if not Path(a.folder).is_dir():
        sys.exit(f"no folder {a.folder}")
    serve(Path(a.folder), a.port, not a.no_browser)


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Review watch</title>
<style>
:root{--bg:#f7f5f0;--panel:#fff;--ink:#1d1d1b;--muted:#6b6860;--line:#e2ded4;--accent:#b4501e;--look:#1f6fd1;--fix:#c2410c;--hot:#d97706;--ok:#15803d;--warn:#b45309;--bad:#b91c1c}
@media (prefers-color-scheme:dark){:root{--bg:#171614;--panel:#211f1c;--ink:#ece8df;--muted:#a19c90;--line:#38342e;--accent:#e08a5a;--look:#6aa8ff;--fix:#fb923c;--hot:#facc15;--ok:#4ade80;--warn:#fbbf24;--bad:#f87171}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,sans-serif}
header{display:flex;gap:16px;align-items:baseline;padding:10px 16px;border-bottom:1px solid var(--line);flex-wrap:wrap}
h1{font-size:17px;margin:0}.muted{color:var(--muted)}.counts span{margin-right:10px}
.wrap{display:grid;grid-template-columns:220px 1fr;height:calc(100vh - 46px)}
@media (max-width:800px){.wrap{grid-template-columns:1fr;height:auto}}
nav{border-right:1px solid var(--line);overflow:auto}
.p{display:flex;justify-content:space-between;gap:8px;padding:7px 12px;border-bottom:1px solid var(--line);cursor:pointer}
.p:hover{background:var(--panel)}.p.sel{background:var(--panel);box-shadow:inset 3px 0 var(--accent)}
.chip{font-size:11px;padding:1px 7px;border-radius:9px;border:1px solid currentColor;white-space:nowrap;height:fit-content}
.s-waiting{color:var(--muted)}.s-looking{color:var(--look)}.s-writing{color:var(--warn)}.s-ready{color:var(--ok)}.s-needs{color:var(--warn)}.s-escalated{color:var(--bad)}
.live::before{content:"";display:inline-block;width:7px;height:7px;border-radius:50%;background:currentColor;margin-right:5px;animation:pulse 1.2s infinite}
@keyframes pulse{50%{opacity:.25}}
main{overflow:auto;padding:12px 16px}
.top{display:flex;justify-content:space-between;gap:12px;align-items:baseline;flex-wrap:wrap}
.tabs{display:flex;gap:4px;margin:10px 0 8px;border-bottom:1px solid var(--line)}
.tabs button{border:0;background:none;color:var(--muted);padding:6px 12px;cursor:pointer;font:inherit;border-bottom:2px solid transparent}
.tabs button.on{color:var(--ink);border-color:var(--accent)}
.cols{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:14px}
@media (max-width:1100px){.cols{grid-template-columns:1fr}}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:8px}
.lbl{font-size:12px;color:var(--muted);margin-bottom:4px;display:flex;justify-content:space-between;gap:8px;align-items:center;flex-wrap:wrap}
.lbl button{font:inherit;font-size:12px;border:1px solid var(--line);background:var(--bg);color:var(--ink);border-radius:4px;padding:1px 7px;cursor:pointer}
.lbl button.on{border-color:var(--accent)}
.viewer{position:relative;overflow:hidden;height:70vh;min-height:360px;background:#888;border-radius:4px;cursor:grab;touch-action:none}
.viewer.drag{cursor:grabbing}
.stage{position:absolute;left:0;top:0;transform-origin:0 0}
.stage img{display:block;width:100%;user-select:none;-webkit-user-drag:none}
.small{position:relative}.small img{display:block;width:100%}
.hl{position:absolute;border:2px solid var(--look);background:color-mix(in srgb,var(--look) 12%,transparent);pointer-events:none;border-radius:2px}
.hl.fix{border-color:var(--fix);background:color-mix(in srgb,var(--fix) 15%,transparent)}
.hl.hot{border-color:var(--hot);border-width:3px;background:color-mix(in srgb,var(--hot) 30%,transparent);box-shadow:0 0 0 3px color-mix(in srgb,var(--hot) 40%,transparent);z-index:2}
.hl.dim{opacity:.15}
.cards{display:flex;flex-direction:column;gap:6px;max-height:70vh;overflow:auto}
.card{background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:6px 9px;cursor:pointer}
.card:hover,.card.hot{border-color:var(--hot);box-shadow:0 0 0 2px color-mix(in srgb,var(--hot) 35%,transparent)}
.card b{font-size:12px;color:var(--muted);font-weight:600}
.card .acts{float:right;display:flex;gap:4px}.card .acts button{font:inherit;font-size:12px;border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:4px;padding:0 7px;cursor:pointer}
.card .acts button.on.ok{border-color:var(--ok);color:var(--ok)}.card .acts button.on.no{border-color:var(--bad);color:var(--bad);font-weight:700}
.card.acc{border-left:4px solid var(--ok)}.card.rej{border-color:var(--bad);border-left:4px solid var(--bad)}.card.rej .body{text-decoration:line-through;opacity:.7}
.card .why{width:100%;margin-top:4px;font:inherit;font-size:12px;padding:2px 5px;border:1px solid var(--bad);border-radius:4px;background:var(--panel);color:var(--ink)}
.verdict{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:6px 0 2px;font-size:13px}.verdict button{font:inherit;font-size:13px;border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:5px;padding:3px 10px;cursor:pointer}
.verdict button.on.good{border-color:var(--ok);color:var(--ok);font-weight:600}.verdict button.on.bad{border-color:var(--bad);color:var(--bad);font-weight:600}.verdict input{flex:1;min-width:180px;font:inherit;font-size:13px;padding:3px 6px;border:1px solid var(--line);border-radius:5px;background:var(--panel);color:var(--ink)}
.mark{font-size:12px;margin-left:4px}
del{color:var(--bad)}ins{color:var(--ok);text-decoration:none;font-weight:600}
.sheets{display:flex;gap:8px;overflow-x:auto;padding-bottom:6px}
.sheets img{height:150px;border:1px solid var(--line);border-radius:4px;cursor:zoom-in;background:#fff}
.feed{font-size:13px;margin:0;padding-left:0;list-style:none}.feed li{margin:2px 0;padding:3px 6px;border-radius:4px}
.feed li[data-ev]{cursor:default}.feed li[data-ev]:hover{background:color-mix(in srgb,var(--hot) 20%,transparent)}
h3{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin:14px 0 6px}
.zoom{position:fixed;inset:0;background:rgba(0,0,0,.8);display:none;align-items:center;justify-content:center;z-index:9;cursor:zoom-out}
.zoom img{max-width:95vw;max-height:95vh;background:#fff}
label{font-size:13px}
.board{display:grid;grid-template-columns:repeat(var(--cols),1fr);border:2px solid #111;width:min(100%,520px);aspect-ratio:var(--cols)/var(--rows);background:#111;gap:1px}
.cell{background:#fff;color:#111;position:relative;display:flex;align-items:flex-end;justify-content:center;font:600 clamp(9px,1.6vw,17px)/1 Georgia,serif;padding-bottom:6%}
.cell.blk{background:#111}.cell .num{position:absolute;left:2px;top:1px;font:9px/1 system-ui,sans-serif;color:#444}
.cell.chg{background:#fde7c7}.cell .unk{color:#999}
.preview{display:grid;grid-template-columns:minmax(0,520px) minmax(0,1fr);gap:18px}
@media (max-width:1100px){.preview{grid-template-columns:1fr}}
.cl{columns:2 260px;font-size:13px}.cl h4{margin:0 0 4px}.cl ol{list-style:none;margin:0 0 10px;padding:0}.cl li{margin:1px 0;break-inside:avoid}
.cl li.chg{background:color-mix(in srgb,var(--hot) 22%,transparent);border-radius:3px}.cl .n{display:inline-block;min-width:26px;font-weight:600}
.cl .ans{color:var(--muted);font-size:11px;margin-left:6px;letter-spacing:.04em}
pre.xd{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:10px;overflow:auto;max-height:60vh;font-size:12px;white-space:pre}
.hint{font-size:12px;color:var(--muted)}
</style></head><body>
<header><h1>Review watch: <span id="root"></span></h1><span class="counts" id="counts"></span>
<label><input type="checkbox" id="follow" checked> follow the latest activity</label></header>
<div class="wrap"><nav id="list"></nav><main id="main"><p class="muted">Waiting for reviews…</p></main></div>
<div class="zoom" id="zoom"><img alt="contact sheet"></div>
<script src="puzzle.js"></script>
<script>
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let S = null, sel = null, P = null, tab = 'review', pageImg = 'page.jpg', hot = null, focusCrops = null;
const view = {};  // per puzzle and page: {s, x, y, fit}
const ago = t => { const s = Math.max(0, Math.round(S.now - t)); return s < 60 ? `${s}s ago` : s < 3600 ? `${Math.round(s/60)} min ago` : `${Math.round(s/3600)} h ago`; };
const chip = st => `<span class="chip s-${st.split(' ')[0]} ${['looking','writing'].includes(st) ? 'live' : ''}">${esc(st)}</span>`;
const label = it => it.replace(/^clue:/, '').replace(/^cell:/, 'key square ').replace(/^grid:/, 'grid square ').replace(/^meta:/, '').replace(/^other:/, 'caption ');

function wordDiff(a, b) {
  const A = a.split(/(\s+)/), B = b.split(/(\s+)/), n = A.length, m = B.length;
  const L = Array.from({length: n + 1}, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) L[i][j] = A[i] === B[j] ? L[i+1][j+1] + 1 : Math.max(L[i+1][j], L[i][j+1]);
  let i = 0, j = 0, out = '';
  while (i < n || j < m) {
    if (i < n && j < m && A[i] === B[j]) { out += esc(A[i]); i++; j++; }
    else if (j < m && (i >= n || L[i][j+1] >= L[i+1][j])) { out += B[j].trim() ? `<ins>${esc(B[j])}</ins>` : esc(B[j]); j++; }
    else { out += A[i].trim() ? `<del>${esc(A[i])}</del>` : esc(A[i]); i++; }
  }
  return out;
}

// ---- where a target or a change sits on the images ----
const O = () => P.ocr;
function pageBox(t) {  // [image name, box in that image's packet pixels] or null
  const i = t.indexOf(':'), k = t.slice(0, i), v = t.slice(i + 1), ci = O().clue_image || 'page.jpg';
  if (k === 'clue') { const c = O().clues[v]; return c && c.box ? [ci, c.box] : null; }
  if (k === 'box') return [ci, v.split(',').map(Number)];
  if (k === 'meta') { const b = (O().meta_boxes || {})[v === 'author' ? 'byline' : v]; return b ? ['page.jpg', b] : null; }
  if (k === 'caption' || k === 'other') { const b = (O().meta_boxes || {})['other' + v]; return b ? ['page.jpg', b] : null; }
  return null;
}
function entrySquares(id) {
  const g = O().grid, R = g.length, C = g[0].length, white = (r, c) => r >= 0 && c >= 0 && r < R && c < C && g[r][c] !== '#';
  let n = 0;
  for (let r = 0; r < R; r++) for (let c = 0; c < C; c++) {
    if (!white(r, c)) continue;
    const a = !white(r, c - 1) && white(r, c + 1), d = !white(r - 1, c) && white(r + 1, c);
    if (!(a || d)) continue; n++;
    if (id === 'A' + n && a) { const sq = []; for (let cc = c; white(r, cc); cc++) sq.push([r, cc]); return sq; }
    if (id === 'D' + n && d) { const sq = []; for (let rr = r; white(rr, c); rr++) sq.push([rr, c]); return sq; }
  }
  return [];
}
function squares(t) {  // [image, [[r0, c0, h, w]]] on grid.png or answers.png
  const i = t.indexOf(':'), k = t.slice(0, i), v = t.slice(i + 1), R = O().grid.length, C = O().grid[0].length;
  if (!['cell','grid','row','col','entry'].includes(k)) return null;
  const img = k === 'grid' ? 'grid.png' : 'answers.png';
  if (v === 'all') return [img, [[0, 0, R, C]]];
  const m = /^r(\d+)c(\d+)$/.exec(v);
  if (m) return [img, [[+m[1]-1, +m[2]-1, 1, 1]]];
  if (k === 'row') return [img, [[+v-1, 0, 1, C]]];
  if (k === 'col') return [img, [[0, +v-1, R, 1]]];
  const sq = entrySquares(v); if (!sq.length) return null;
  const r = sq.map(s => s[0]), c = sq.map(s => s[1]);
  return [img, [[Math.min(...r), Math.min(...c), Math.max(...r) - Math.min(...r) + 1, Math.max(...c) - Math.min(...c) + 1]]];
}
// The places a change shows up: a clue fix also lights its answer in the key, a key fix its grid square.
function places(item) {
  const out = [item];
  if (item.startsWith('clue:')) out.push('entry:' + item.slice(5));
  if (item.startsWith('cell:')) out.push('grid:' + item.slice(5));
  return out;
}

// ---- overlays ----
function boxesFor(name) {
  const fixed = new Set(Object.keys(P.review.corrections || {}));
  const hotSet = new Set(hot ? places(hot) : []);
  const want = [...new Set(P.shown.concat([...hotSet]).concat(focusCrops || []))];
  const out = [];
  for (const t of want) {
    let cls = hotSet.has(t) ? 'hot' : fixed.has(t) ? 'fix' : '';
    if (focusCrops && !focusCrops.includes(t) && cls !== 'hot') cls += ' dim';
    const pb = pageBox(t);
    if (pb && pb[0] === name) { const [x0, y0, x1, y1] = pb[1]; out.push({t, x: x0 - 3, y: y0 - 3, w: x1 - x0 + 6, h: y1 - y0 + 6, cls}); }
    const sq = squares(t);
    if (sq && sq[0] === name) for (const s of sq[1]) out.push({t, sq: s, cls});
  }
  return out;
}
function drawSmall(id, name) {
  const im = document.getElementById(id); if (!im || !im.naturalWidth) return;
  const wrap = im.parentElement; wrap.querySelectorAll('.hl').forEach(e => e.remove());
  const R = O().grid.length, C = O().grid[0].length, k = im.clientWidth / im.naturalWidth, cw = im.naturalWidth / C, ch = im.naturalHeight / R;
  for (const b of boxesFor(name)) {
    if (!b.sq) continue;
    const [r, c, h, w] = b.sq, d = document.createElement('div');
    d.className = 'hl ' + b.cls; d.title = b.t;
    Object.assign(d.style, {left: c * cw * k + 'px', top: r * ch * k + 'px', width: w * cw * k + 'px', height: h * ch * k + 'px'});
    wrap.appendChild(d);
  }
}

// ---- the zoomable page ----
let pageW = 0;  // the page's width in packet pixels (the boxes' units)
function cur() {
  const key = P.xdid + pageImg, vw = $('#viewer');
  if (!view[key] && vw && pageW) { const s = vw.clientWidth / pageW; view[key] = {s, x: 0, y: 0, fit: s}; }
  return view[key] || {s: 1, x: 0, y: 0, fit: 1};
}
function applyView() {
  const v = cur(), st = $('#stage'); if (!st) return;
  st.style.transform = `translate(${v.x}px,${v.y}px) scale(${v.s})`;
  st.querySelectorAll('.hl').forEach(d => d.style.borderWidth = (d.classList.contains('hot') ? 3 : 2) / v.s + 'px');
}
function drawPage() {
  const st = $('#stage'), im = $('#pageimg'); if (!st || !im || !im.naturalWidth) return;
  pageW = im.naturalWidth * (P.src[pageImg] ? ((O().scales || {})[pageImg] || 1) : 1);
  st.style.width = pageW + 'px';
  st.querySelectorAll('.hl').forEach(e => e.remove());
  for (const b of boxesFor(pageImg)) {
    if (b.sq) continue;
    const d = document.createElement('div'); d.className = 'hl ' + b.cls; d.title = b.t;
    Object.assign(d.style, {left: b.x + 'px', top: b.y + 'px', width: b.w + 'px', height: b.h + 'px'});
    st.appendChild(d);
  }
  applyView();
}
function zoomAt(px, py, f) {
  const v = cur(), s = Math.min(Math.max(v.s * f, v.fit * 0.8), v.fit * 12);
  v.x = px - (px - v.x) * s / v.s; v.y = py - (py - v.y) * s / v.s; v.s = s; applyView();
}
function zoomTo(box) {  // a box (packet pixels) in the middle of the viewer, large enough to read
  const vw = $('#viewer'); if (!vw || !pageW) return; const v = cur();
  const [x0, y0, x1, y1] = box, W = vw.clientWidth, H = vw.clientHeight;
  v.s = Math.max(v.fit, Math.min(W / ((x1 - x0) + 200), H / ((y1 - y0) + 300), v.fit * 8));
  v.x = W / 2 - (x0 + x1) / 2 * v.s; v.y = H / 2 - (y0 + y1) / 2 * v.s; applyView();
}
function bindViewer() {
  const vw = $('#viewer'); if (!vw) return;
  vw.onwheel = e => { e.preventDefault(); const r = vw.getBoundingClientRect(); zoomAt(e.clientX - r.left, e.clientY - r.top, e.deltaY < 0 ? 1.2 : 1 / 1.2); };
  let drag = null;
  vw.onpointerdown = e => { drag = {x: e.clientX, y: e.clientY}; vw.classList.add('drag'); vw.setPointerCapture(e.pointerId); };
  vw.onpointermove = e => { if (!drag) return; const v = cur(); v.x += e.clientX - drag.x; v.y += e.clientY - drag.y; drag = {x: e.clientX, y: e.clientY}; applyView(); };
  vw.onpointerup = () => { drag = null; vw.classList.remove('drag'); };
  vw.ondblclick = e => { const r = vw.getBoundingClientRect(); zoomAt(e.clientX - r.left, e.clientY - r.top, 2); };
}
function redraw() { drawPage(); drawSmall('gridimg', 'grid.png'); drawSmall('ansimg', 'answers.png'); }

function setHot(item, zoom) {
  hot = item;
  document.querySelectorAll('.card').forEach(c => c.classList.toggle('hot', c.dataset.item === item));
  if (item && zoom) {
    const pb = places(item).map(pageBox).find(Boolean);
    if (pb) {
      if (pb[0] !== pageImg && P.has[pb[0]]) { pageImg = pb[0]; renderMain(); hot = item; const im = $('#pageimg'); im.onload = () => { drawPage(); zoomTo(pb[1]); }; return; }
      zoomTo(pb[1]);
    }
  }
  redraw();
}

// ---- rendering ----
function renderList() {
  const counts = {};
  S.puzzles.forEach(p => counts[p.status] = (counts[p.status] || 0) + 1);
  $('#counts').innerHTML = ['waiting','looking','writing','ready','needs a person','escalated'].filter(s => counts[s]).map(s => `<span>${chip(s)} ${counts[s]}</span>`).join('');
  $('#list').innerHTML = S.puzzles.map(p => `<div class="p ${p.xdid === sel ? 'sel' : ''}" data-x="${p.xdid}"><span>${esc(p.xdid)}<br><span class="muted" style="font-size:12px">${p.updated ? ago(p.updated) : ''}</span></span><span>${chip(p.status)}${p.verdict === 'looks-right' ? '<span class="mark" style="color:var(--ok)" title="you: looks right">✓</span>' : p.verdict === 'needs-work' ? '<span class="mark" style="color:var(--bad)" title="you: needs work">✗</span>' : ''}${p.rejected ? `<span class="mark" style="color:var(--bad)" title="changes you rejected">−${p.rejected}</span>` : ''}</span></div>`).join('');
  document.querySelectorAll('.p').forEach(el => el.onclick = () => { sel = el.dataset.x; $('#follow').checked = false; hot = null; focusCrops = null; focusCard = null; load(true); });
}

const D = () => P.decisions || {items: {}, notes: {}};
const rejected = key => D().items[key] === 'reject';
const accepted = key => D().items[key] === 'accept';
function card(item, key, title, body) {  // key: what a decision is about, as the importer names it
  const r = rejected(key), a = accepted(key);
  return `<div class="card ${r ? 'rej' : a ? 'acc' : ''}" data-item="${esc(item)}" data-key="${esc(key)}"><span class="acts">`
    + `<button class="ok ${a ? 'on' : ''}" data-act="accept" title="Accept (A)">✓</button><button class="no ${r ? 'on' : ''}" data-act="reject" title="Reject (R)">✗</button></span>`
    + `<b>${esc(title)}</b><br><span class="body">${body}</span>`
    + (r ? `<input class="why" data-note="${esc(key)}" placeholder="Rejected. Why? What does the scan show? (optional; Enter to save)" value="${esc(D().notes[key] || '')}">` : '')
    + `</div>`;
}
function progress() {
  const keys = [...document.querySelectorAll('.card[data-key]')].map(c => c.dataset.key);
  const done = keys.filter(k => D().items[k]).length;
  return keys.length ? `${done} of ${keys.length} checked` : '';
}
async function decide(payload) {
  const r = await fetch('api/decide', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({x: P.xdid, ...payload})});
  if (r.ok) { P.decisions = await r.json(); lastKey = renderKey(P); renderMain(); }
}
async function decideCard(el, act) {
  const key = el.dataset.key; if (!key) return;
  const i = [...document.querySelectorAll('.card')].indexOf(el);
  if (act === 'reject') {
    await decide({item: key, decision: 'reject', note: D().notes[key] || ''});
    focusCard = i;
    const box = document.querySelector(`[data-note="${CSS.escape(key)}"]`);
    if (box) box.focus();  // type a note, or press Esc / J to move on
  } else {
    await decide({item: key, decision: 'accept'});
    moveFocus(i + 1);
  }
}
function moveFocus(i) {
  const cs = [...document.querySelectorAll('.card')];
  if (!cs.length) return;
  focusCard = Math.min(cs.length - 1, Math.max(0, i));
  cs.forEach(c => c.classList.remove('hot'));
  cs[focusCard].classList.add('hot');
  cs[focusCard].scrollIntoView({block: 'nearest'});
  setHot(cs[focusCard].dataset.item, true);
}
function changesHtml() {
  const rv = P.review, o = O(), cards = [];
  for (const [item, now] of Object.entries(rv.corrections || {})) {
    const i = item.indexOf(':'), kind = item.slice(0, i), key = item.slice(i + 1);
    let was = '';
    if (kind === 'clue') was = (o.clues[key] || {}).text || '';
    else if (kind === 'meta') was = o[key] || '';
    else if (kind === 'other') was = (o.captions || {})[key] || '';
    else if (kind === 'cell') { const m = /r(\d+)c(\d+)/.exec(key); was = m && o.answers ? (o.answers[m[1]-1] || '')[m[2]-1] || '' : ''; }
    else if (kind === 'grid') { const m = /r(\d+)c(\d+)/.exec(key); was = m ? (o.grid[m[1]-1] || '')[m[2]-1] || '' : ''; }
    const body = kind === 'cell' || kind === 'grid' ? `<del>${esc(was || '?')}</del> → <ins>${esc(now)}</ins>`
      : now === '' ? `<del>${esc(was || '(removed)')}</del> <span class="muted">(removed)</span>` : wordDiff(was, now);
    cards.push(card(item, item, label(item), body));
  }
  for (const [k, v] of Object.entries(rv.sic || {})) cards.push(card('clue:' + k, 'sic:' + k, k + ': kept as printed (sic)', 'meant: ' + esc(v)));
  for (const [k, v] of Object.entries(rv.unsure || {})) cards.push(`<div class="card" data-item="${esc(k)}"><b>${esc(label(k))}: unsure</b><br>${esc(v)}</div>`);
  return cards.join('');
}

function xdText(Z) {  // the corrected puzzle as xd (a preview: the archive's own export is made upstream)
  const m = /(\d{4}-\d\d-\d\d)/.exec(Z.id), head = [['Title', Z.title], ['Author', Z.author], ['Byline', Z.byline], ['Date', m ? m[1] : ''], ['Source', Z.source]];
  const grid = Z.cells.map(row => row.map(x => !x ? '#' : x.sol || '.').join(''));
  const ans = w => w.cells.map(([r, c]) => (Z.cells[r][c] || {}).sol || '.').join('');
  const list = d => Z.words.filter(w => w.dir === d).map(w => `${d}${w.n}. ${w.text} ~ ${ans(w)}`).join('\n');
  return head.filter(h => h[1]).map(h => `${h[0]}: ${h[1]}`).join('\n') + '\n\n\n' + grid.join('\n') + '\n\n\n' + list('A') + '\n\n' + list('D') + '\n';
}

function previewHtml() {
  if (typeof buildPuzzle !== 'function') return '<p class="muted">The preview needs docs/puzzle.js from the blitz repository.</p>';
  const rv = {...P.review, corrections: Object.fromEntries(Object.entries(P.review.corrections || {}).filter(([k]) => !rejected(k))),
              sic: Object.fromEntries(Object.entries(P.review.sic || {}).filter(([k]) => !rejected('sic:' + k)))};
  const Z = buildPuzzle(O(), rv);
  if (!Z) return '<p class="muted">No preview.</p>';
  const corr = Object.keys(rv.corrections);
  const changedSq = new Set(corr.filter(k => k.startsWith('cell:') || k.startsWith('grid:')).map(k => k.slice(5)));
  const changedClue = new Set(corr.filter(k => k.startsWith('clue:')).map(k => k.slice(5)));
  const board = Z.cells.map((row, r) => row.map((x, c) => !x ? '<div class="cell blk"></div>'
    : `<div class="cell ${changedSq.has(`r${r+1}c${c+1}`) ? 'chg' : ''}">${x.num ? `<span class="num">${x.num}</span>` : ''}${x.sol ? esc(x.sol) : '<span class="unk">·</span>'}</div>`).join('')).join('');
  const ans = w => w.cells.map(([r, c]) => (Z.cells[r][c] || {}).sol || '·').join('');
  const list = d => Z.words.filter(w => w.dir === d).map(w => `<li class="${changedClue.has(w.id) ? 'chg' : ''}"><span class="n">${w.n}</span>${esc(w.text)}<span class="ans">${esc(ans(w))}</span></li>`).join('');
  return `<p class="hint">${P.review._draft ? 'From the draft (not finished yet). ' : ''}The puzzle with this review applied (less any change you rejected), as its record page will show it. Changed squares and clues are tinted.</p>
    <div class="preview"><div><h2 style="margin:0 0 2px;font:600 20px Georgia,serif">${esc(Z.title)}</h2>
      <div class="muted" style="margin-bottom:8px">${esc(Z.byline || Z.author)} · ${esc(Z.date)}</div>
      <div class="board" style="--cols:${Z.C};--rows:${Z.R}">${board}</div></div>
      <div class="cl"><h4>Across</h4><ol>${list('A')}</ol><h4>Down</h4><ol>${list('D')}</ol></div></div>
    <h3>xd</h3><pre class="xd">${esc(xdText(Z))}</pre>`;
}

function renderMain() {
  if (!P) return;
  const rv = P.review, o = O();
  const title = (rv.corrections || {})['meta:title'] || o.title || P.xdid;
  const ev = P.events.map((e, i) => e.what === 'sheet'
    ? `<li data-ev="${i}">${ago(e.t)}: looked at ${e.crops.length} crop${e.crops.length === 1 ? '' : 's'}: ${esc(e.crops.join(', '))}</li>`
    : `<li>${ago(e.t)}: ${e.what === 'draft' ? 'wrote its verdict (draft.json)' : 'finished (review.json)'}</li>`).reverse().join('');
  const notes = (rv.tool_notes || []).map(n => typeof n === 'string' ? n : `${n.kind}${n.target ? ' ' + n.target : ''}: ${n.note}`).map(n => `<li>${esc(n)}</li>`).join('');
  const sheets = P.events.filter(e => e.what === 'sheet').map(e => `<img src="${esc(e.file)}?t=${e.t}" title="${esc(e.crops.join(', '))}" alt="contact sheet">`).join('');
  const pages = ['page.jpg', 'clue_page.jpg'].filter(n => P.has[n]);
  if (!P.has[pageImg]) pageImg = 'page.jpg';
  const imgSrc = n => `${P.xdid}/${P.src[n] ? '_src/' : ''}${n}`;
  const cards = changesHtml();
  $('#main').innerHTML = `<div class="top"><div><h2 style="margin:0;font-size:18px">${esc(title)}</h2>
    <span class="muted">${esc(P.xdid)} · ${esc(o.byline || '')} · ${o.grid.length}x${o.grid[0].length}</span></div>${chip(P.status)}</div>
    ${rv.escalate ? `<p style="color:var(--bad)"><b>Escalated:</b> ${esc(rv.escalate)}</p>` : ''}
    ${rv.note ? `<p class="muted" style="margin:6px 0">${esc(rv.note)}</p>` : ''}
    ${['ready','needs a person','escalated'].includes(P.status) ? `<div class="verdict"><span class="muted">Your check:</span>`
      + `<button data-verdict="looks-right" class="good ${D().verdict === 'looks-right' ? 'on' : ''}">✓ Looks right</button>`
      + `<button data-verdict="needs-work" class="bad ${D().verdict === 'needs-work' ? 'on' : ''}">✗ Needs work</button>`
      + `<input id="vnote" placeholder="note (optional)" value="${esc(D().note || '')}">`
      + `<span class="hint">J/K next/previous change · A accept · R reject (then type why)</span></div>` : ''}
    <div class="tabs"><button data-tab="review" class="${tab === 'review' ? 'on' : ''}">The review</button><button data-tab="preview" class="${tab === 'preview' ? 'on' : ''}">The result (grid and xd)</button></div>
    ${tab === 'preview' ? previewHtml() : `
    <div class="cols"><div class="panel"><div class="lbl"><span><span style="color:var(--look)">■</span> looked at · <span style="color:var(--fix)">■</span> corrected · <span style="color:var(--hot)">■</span> selected · scroll to zoom, drag to move, double-click to zoom in</span>
        <span>${pages.length > 1 ? pages.map(n => `<button data-page="${n}" class="${n === pageImg ? 'on' : ''}">${n === 'page.jpg' ? 'Page' : 'Clue page'}</button>`).join(' ') : ''} <button id="fit">Fit</button></span></div>
        <div class="viewer" id="viewer"><div class="stage" id="stage"><img id="pageimg" src="${esc(imgSrc(pageImg))}" alt="scanned page" draggable="false"></div></div></div>
      <div style="display:flex;flex-direction:column;gap:10px">
        <div class="panel"><div class="lbl"><span>What it changed${rv._draft ? ' (draft)' : ''}: hover to find it, click to zoom there</span><span id="progress"></span></div>
          ${cards ? `<div class="cards">${cards}</div>` : `<p class="muted">${['waiting','looking'].includes(P.status) ? 'Nothing yet.' : 'No changes.'}</p>`}</div>
        ${P.has['answers.png'] ? `<div class="panel"><div class="lbl">Answer key</div><div class="small"><img id="ansimg" src="${esc(P.xdid)}/answers.png" alt="answer key"></div></div>` : ''}
        ${P.has['grid.png'] ? `<div class="panel"><div class="lbl">Grid</div><div class="small"><img id="gridimg" src="${esc(P.xdid)}/grid.png" alt="puzzle grid"></div></div>` : ''}
      </div></div>
    <h3>Activity: hover a step to see what it looked at</h3>${ev ? `<ul class="feed">${ev}</ul>` : '<p class="muted">Not started.</p>'}
    <h3>Contact sheets it read</h3>${sheets ? `<div class="sheets">${sheets}</div>` : '<p class="muted">None yet.</p>'}
    ${notes ? `<h3>Notes on the tools</h3><ul class="feed">${notes}</ul>` : ''}`}`;
  document.querySelectorAll('.tabs button').forEach(b => b.onclick = () => { tab = b.dataset.tab; renderMain(); });
  document.querySelectorAll('[data-page]').forEach(b => b.onclick = () => { pageImg = b.dataset.page; renderMain(); });
  if ($('#fit')) $('#fit').onclick = () => { const v = cur(); v.s = v.fit; v.x = 0; v.y = 0; applyView(); };
  document.querySelectorAll('.card').forEach((c, i) => {
    c.onmouseenter = () => setHot(c.dataset.item, false);
    c.onmouseleave = () => { if (focusCard !== i) setHot(null, false); };
    c.onclick = e => {
      focusCard = i;
      const b = e.target.closest('button[data-act]');
      if (b) decideCard(c, b.dataset.act); else setHot(c.dataset.item, true);
    };
  });
  document.querySelectorAll('[data-verdict]').forEach(b => b.onclick = () =>
    decide({verdict: D().verdict === b.dataset.verdict ? '' : b.dataset.verdict, note: $('#vnote').value}));
  if ($('#vnote')) $('#vnote').onchange = () => decide({verdict: D().verdict || '', note: $('#vnote').value});
  document.querySelectorAll('input[data-note]').forEach(box => {
    box.onclick = e => e.stopPropagation();
    box.onkeydown = e => {
      if (e.key === 'Enter' || e.key === 'Escape') {
        e.preventDefault();
        const i = [...document.querySelectorAll('.card')].indexOf(box.closest('.card'));
        const save = e.key === 'Enter' && box.value !== (D().notes[box.dataset.note] || '');
        (save ? decide({item: box.dataset.note, decision: 'reject', note: box.value}) : Promise.resolve()).then(() => moveFocus(i + 1));
      }
    };
    box.onchange = () => decide({item: box.dataset.note, decision: 'reject', note: box.value});
  });
  const cs = document.querySelectorAll('.card');
  if (focusCard !== null && cs[focusCard]) cs[focusCard].classList.add('hot');
  const pg = document.getElementById('progress'); if (pg) pg.textContent = progress();
  document.querySelectorAll('.feed li[data-ev]').forEach(li => {
    const e = P.events[+li.dataset.ev];
    li.onmouseenter = () => { focusCrops = e.crops || null; redraw(); };
    li.onmouseleave = () => { focusCrops = null; redraw(); };
  });
  document.querySelectorAll('.sheets img').forEach(im => im.onclick = () => { $('#zoom img').src = im.src; $('#zoom').style.display = 'flex'; });
  for (const [id, fn] of [['pageimg', drawPage], ['gridimg', () => drawSmall('gridimg', 'grid.png')], ['ansimg', () => drawSmall('ansimg', 'answers.png')]]) {
    const im = document.getElementById(id); if (im) { if (im.complete) fn(); else im.onload = fn; }
  }
  bindViewer();
}

let focusCard = null;
document.addEventListener('keydown', e => {
  if (!P || tab !== 'review' || e.target.matches('input, textarea') || e.ctrlKey || e.metaKey || e.altKey) return;
  const cs = [...document.querySelectorAll('.card')];
  if (!cs.length) return;
  const k = e.key.toLowerCase();
  if (k === 'j' || k === 'k') moveFocus(focusCard === null ? 0 : focusCard + (k === 'j' ? 1 : -1));
  else if (k === 'a' || k === 'r') { e.preventDefault(); decideCard(cs[focusCard === null ? 0 : focusCard], k === 'a' ? 'accept' : 'reject'); }
});
let lastKey = '';
const renderKey = p => p.xdid + JSON.stringify([p.status, p.shown.length, Object.keys(p.review.corrections || {}).length,
                                                p.events.length, p.decisions]);
async function load(force) {
  const p = await (await fetch('api/puzzle?x=' + encodeURIComponent(sel))).json();
  const key = renderKey(p);
  const typing = document.activeElement && document.activeElement.matches('input, textarea');
  if (!force && typing) { renderList(); return; }  // don't wipe a note being typed
  P = p;
  if (force || key !== lastKey) { lastKey = key; renderMain(); }
  renderList();
}
async function poll() {
  try {
    S = await (await fetch('api/state')).json();
    $('#root').textContent = S.root;
    if ($('#follow').checked || !sel) {
      const live = S.puzzles.filter(p => p.updated).sort((a, b) => b.updated - a.updated)[0];
      const next = live ? live.xdid : S.puzzles[0]?.xdid;
      if (next !== sel) { sel = next; hot = null; focusCrops = null; }
    }
    renderList();
    if (sel) await load(false);
  } catch (e) {}
  setTimeout(poll, 2000);
}
$('#zoom').onclick = () => $('#zoom').style.display = 'none';
window.onresize = () => P && redraw();
poll();
</script></body></html>
"""

if __name__ == "__main__":
    main()
