"""The review site on this machine, for working on its pages: an edit to src/blitz/proof.html or
batch.html shows in the open tab within a second, with no `blitz site-build`.

    uv run python tools/review_dev.py --data <folder> [--port 8795]

It serves the pages the way the site does (docs/review/, docs/review/batch/), so what you see is a
volunteer's view: config.js points the pages at this server instead of Supabase and R2, and a small
stand-in for supabase-js keeps the site's tables (puzzles, proofs, verdicts, restores) as JSON files
in <folder>/db/. Ready, Not ready, edits and comments save there; nothing touches the real site, the
harvest or a ledger.

<folder> holds a fixed copy of real data, made once:
    packets/<pid>/        proof packets (xword-ocr's harvests/<h>/proof/<run>/<pid>), and its dropped.json
    files/batch/          the batch page's snapshot: batches.json and <name>/ (blitz site-publish-batch)
A file missing from files/ (a snapshot's full-size page, say) is fetched once from the site's bucket.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import re
import threading
import time
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "blitz"
WATCH = [SRC / "proof.html", SRC / "batch.html", Path(__file__)]
BUCKET = "https://pub-52ac4a15c4ba43fe8e4af5a496733fb5.r2.dev"
KEYS = {"proofs": ("xdid", "user_id"), "verdicts": ("xdid", "user_id"), "restores": ("xdid", "user_id")}

# supabase-js, as much of it as the pages use: a session in localStorage, and table reads and upserts
# against this server's /sb/rest/v1/
SHIM = r"""(() => {
  const KEY = 'sb-localhost-auth-token';
  const sess = () => { try { return JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { return null; } };
  window.supabase = {createClient(url) {
    const rest = url + '/rest/v1/';
    const auth = {
      async getSession() { return {data: {session: sess()}, error: null}; },
      async signInAnonymously() {
        const s = {access_token: 'dev', user: {id: crypto.randomUUID(), is_anonymous: true}};
        localStorage.setItem(KEY, JSON.stringify(s));
        return {data: {session: s, user: s.user}, error: null};
      },
      async signOut() { localStorage.removeItem(KEY); return {error: null}; },
      onAuthStateChange() { return {data: {subscription: {unsubscribe() {}}}}; },
      async signInWithOAuth() { return {error: {message: 'no sign-in on the dev server'}}; },
      async signInWithIdToken() { return {error: {message: 'no sign-in on the dev server'}}; },
    };
    const send = (table, row) => fetch(rest + table, {method: 'POST', body: JSON.stringify(row)})
      .then(async r => r.ok ? {data: null, error: null} : {data: null, error: {message: await r.text()}});
    const from = table => {
      const q = [];
      const b = {
        select(s) { q.push('select=' + encodeURIComponent(s || '*')); return b; },
        eq(k, v) { q.push(k + '=eq.' + encodeURIComponent(v)); return b; },
        order(k, o) { q.push('order=' + k + (o && o.ascending === false ? '.desc' : '')); return b; },
        then(ok, bad) {
          return fetch(rest + table + '?' + q.join('&')).then(r => r.json())
            .then(data => ({data, error: null}), e => ({data: null, error: {message: String(e)}})).then(ok, bad);
        },
        upsert: row => send(table, row), insert: row => send(table, row),
      };
      return b;
    };
    return {auth, from};
  }};
})();
"""

# the open tab reloads when a watched file changes, and comes back to where it was scrolled
RELOAD = """<script>
(() => {
  const k = 'dev-scroll:' + location.href;
  try { const y = sessionStorage.getItem(k); if (y) { sessionStorage.removeItem(k);
    for (const t of [0, 300, 900, 1800]) setTimeout(() => scrollTo(0, +y), t); } } catch (e) {}
  const es = new EventSource('/__reload');
  let first = true;
  es.onmessage = () => { if (first) { first = false; return; }
    try { sessionStorage.setItem(k, String(scrollY)); } catch (e) {} location.reload(); };
})();
</script>
"""


def puzzles(data: Path) -> list[dict]:
    """The site's puzzles table for the copied packets, as site.publish writes it."""
    packets = data / "packets"
    drops = {}
    if (packets / "dropped.json").exists():
        d = json.loads((packets / "dropped.json").read_text(encoding="utf-8"))
        drops = d.get("dropped", d) if isinstance(d, dict) else {x["pid"]: x for x in d}
    rows = []
    for d in sorted(p for p in packets.iterdir() if (p / "review.json").exists()):
        rv = json.loads((d / "review.json").read_text(encoding="utf-8"))
        ocr = json.loads((d / "ocr.json").read_text(encoding="utf-8"))
        cu = rv.get("checkup") or {}
        files = {f.name: True for f in d.iterdir() if f.is_file()}
        if (d / "sheets" / "shown.json").exists():
            files["sheets/shown.json"] = True
        dr = drops.get(d.name) if isinstance(drops, dict) else None
        rows.append({"xdid": d.name, "pub": re.match(r"[a-z]+", d.name)[0], "batch": "games-1977-79",
                     "title": ((rv.get("corrections") or {}).get("meta:title") or ocr.get("title", ""))[:200],
                     "base_url": f"/packets/{d.name}", "files": files, "open": True,
                     "checkup": {"grade": cu.get("grade", ""),
                                 "high": sum(w["level"] == "high" for w in cu.get("warnings", [])),
                                 "medium": sum(w["level"] == "medium" for w in cu.get("warnings", []))} if cu else None,
                     "dropped": {"by": dr.get("by", ""), "note": dr.get("note", "")[:500]} if isinstance(dr, dict) else None})
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--port", type=int, default=8795)
    a = ap.parse_args()
    data = a.data.resolve()
    db = data / "db"
    db.mkdir(exist_ok=True)
    lock = threading.Lock()
    tables = {"puzzles": puzzles(data)}
    for t in KEYS:
        f = db / f"{t}.json"
        tables[t] = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
    version = [0]

    def watch():
        seen = {f: f.stat().st_mtime for f in WATCH}
        while True:
            time.sleep(0.25)
            for f in WATCH:
                m = f.stat().st_mtime
                if m != seen[f]:
                    seen[f] = m
                    version[0] += 1
                    print(f"  {f.name} changed: reloading")
    threading.Thread(target=watch, daemon=True).start()

    from blitz import site

    def page(name: str, depth: str) -> bytes:
        """The page as `blitz site-build` makes it, from the source as it is now."""
        p = (SRC / name).read_text(encoding="utf-8")
        if name == "proof.html":
            p = p.replace("<script>\nconst params", f'<script src="config.js"></script>\n<script src="shim.js"></script>\n<script>\nconst params')
            p = p.replace("<title>Proof a puzzle</title>", site.REVIEW_HEAD)
        else:
            p = p.replace("<script>\nconst $", '<script src="../config.js"></script>\n<script>\nconst $')
            p = p.replace("<title>Batch</title>", site.BATCH_HEAD)
        return p.replace("</body>", RELOAD + "</body>").encode()

    class H(SimpleHTTPRequestHandler):
        def log_message(self, fmt, *args):
            if not self.path.startswith("/__reload"):
                super().log_message(fmt, *args)

        def out(self, body: bytes, ctype: str, code: int = 200):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def file(self, f: Path):
            if not f.is_file():
                return self.out(b"not found", "text/plain", 404)
            # images cached as R2 serves them (a day), so the dev server is as quick as the site
            ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
            body = f.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-cache" if f.suffix == ".json" else "public, max-age=86400")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            u = urllib.parse.urlsplit(self.path)
            path = urllib.parse.unquote(u.path)
            host = f"http://{self.headers.get('Host', f'localhost:{a.port}')}"
            if path in ("/", "/review"):
                self.send_response(302); self.send_header("Location", "/review/"); self.end_headers(); return
            if path == "/review/":
                return self.out(page("proof.html", ""), "text/html; charset=utf-8")
            if path in ("/review/batch", "/review/batch/"):
                if path == "/review/batch":
                    self.send_response(302); self.send_header("Location", "/review/batch/"); self.end_headers(); return
                return self.out(page("batch.html", "../"), "text/html; charset=utf-8")
            if path == "/review/config.js":
                cfg = {"name": "blitz (dev)", "providers": [], "supabaseUrl": host + "/sb", "supabaseAnonKey": "dev",
                       "filesBase": host + "/files"}
                return self.out(f"window.BLITZ_SITE = {json.dumps(cfg)};\n".encode(), "text/javascript")
            if path == "/review/shim.js":
                return self.out(SHIM.encode(), "text/javascript")
            if path == "/__reload":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                v = version[0]
                try:
                    self.wfile.write(b"data: hello\n\n"); self.wfile.flush()
                    while True:
                        time.sleep(0.2)
                        if version[0] != v:
                            v = version[0]
                            self.wfile.write(b"data: reload\n\n"); self.wfile.flush()
                except (ConnectionError, OSError):
                    return
            if path.startswith("/sb/rest/v1/"):
                t = path.rsplit("/", 1)[1]
                rows = tables.get(t, [])
                q = urllib.parse.parse_qs(u.query)
                for k, vs in q.items():
                    for v in vs:
                        if v.startswith("eq."):
                            want = v[3:]
                            rows = [r for r in rows if str(r.get(k)).lower() == want.lower()]
                if "order" in q:
                    col, _, d = q["order"][0].partition(".")
                    rows = sorted(rows, key=lambda r: str(r.get(col) or ""), reverse=d == "desc")
                sel = q.get("select", ["*"])[0]
                if sel != "*":
                    cols = sel.split(",")
                    rows = [{c: r.get(c) for c in cols} for r in rows]
                return self.out(json.dumps(rows).encode(), "application/json")
            if path.startswith("/packets/"):
                return self.file(data / path.lstrip("/"))
            if path.startswith("/files/"):
                f = data / path.lstrip("/")
                if not f.exists():  # copied once from the site's bucket
                    try:
                        req = urllib.request.Request(BUCKET + urllib.parse.quote(path[len("/files"):]), headers={"User-Agent": "curl/8"})
                        body = urllib.request.urlopen(req, timeout=60).read()
                        f.parent.mkdir(parents=True, exist_ok=True)
                        f.write_bytes(body)
                    except Exception:
                        pass
                return self.file(f)
            self.out(b"not found", "text/plain", 404)

        def do_POST(self):
            path = urllib.parse.urlsplit(self.path).path
            if not path.startswith("/sb/rest/v1/"):
                return self.out(b"not found", "text/plain", 404)
            t = path.rsplit("/", 1)[1]
            if t not in KEYS:
                return self.out(f"no table {t}".encode(), "text/plain", 400)
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"null")
            with lock:
                for row in body if isinstance(body, list) else [body]:
                    key = tuple(row.get(k) for k in KEYS[t])
                    tables[t] = [r for r in tables[t] if tuple(r.get(k) for k in KEYS[t]) != key] + [row]
                (db / f"{t}.json").write_text(json.dumps(tables[t], indent=1), encoding="utf-8")
            print(f"  saved to {t}: {body.get('xdid') if isinstance(body, dict) else len(body)}")
            self.out(b"", "application/json", 201)

    print(f"The review site, from {SRC}, data from {data}")
    print(f"  http://localhost:{a.port}/review/batch/   (the way in)")
    print(f"  http://localhost:{a.port}/review/?p=games1978-05-01-L040")
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()


if __name__ == "__main__":
    main()
