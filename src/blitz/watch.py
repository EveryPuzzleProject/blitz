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
            cu = (_read(d / "review.json") or {}).get("checkup") or {}
            puzzles.append({"xdid": d.name, "status": st, "updated": t, "verdict": dec.get("verdict", ""),
                            "grade": cu.get("grade", ""),
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
        if "report" in body:  # a problem the review missed, reported from the scan
            dec.setdefault("reports", {})[str(body["report"])] = str(body.get("text", ""))
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


PAGE = (Path(__file__).parent / "review.html").read_text(encoding="utf-8")  # also the public site's page (site.py)


if __name__ == "__main__":
    main()
