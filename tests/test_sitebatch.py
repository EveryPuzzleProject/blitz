"""blitz site-publish-batch's snapshot: the watch's answers as files, URLs relative, the volunteer view."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from blitz import sitebatch

BATCH = {
    "run": "run12", "runs": ["run12", "run11"], "current": "run12", "pubid": "games",
    "run_notes": {"run12": {"what": "the current run"}, "run11": {"what": "old"}},
    "counts": {"ship": 1}, "notes": {"labels": []}, "mastheads": None, "rerun": None, "spend": None,
    "causes": {"causes": [{"id": "c", "pids": ["games1977-09-01-L026"],
                           "puzzles": [{"pid": "games1977-09-01-L026", "thumb": "/batch/thumb/run12/games1977-09-01-L026.png",
                                        "choice": "ship"}]}]},
    "puzzles": [
        {"pid": "games1977-09-01-L026", "choice": "ship", "by": "alex", "note": "fine", "at": "x", "proof": "ready",
         "diagnosis": None, "thumb": "/batch/thumb/run12/games1977-09-01-L026.png", "page": "",
         "maps": [{"n": 0, "page": "games_1977-09, leaf 30", "image": "/batch/pageimg/run12/games1977-09-01-L026/0.jpg"}]},
        {"pid": "games1977-09-01-L028", "choice": "drop", "by": "triage", "note": "a game board", "at": "y",
         "thumb": "", "page": "/batch/page/run12/games1977-09-01-L028.jpg",
         "maps": [{"n": 0, "page": "games_1977-09, leaf 30", "image": "/batch/pageimg/run12/games1977-09-01-L028/0.jpg"}]},
    ],
}


def _watch():
    seen = []

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            u = urlparse(self.path)
            seen.append(self.path)
            if u.path == "/api/batch":
                body = json.dumps(BATCH).encode()
            elif u.path.startswith("/api/overlay/"):
                body = json.dumps({"page": "p", "size": [10, 20], "boxes": [{"kind": "region", "box": [1, 2, 3, 4],
                                   "source": "assembly.json (run12/x, abc)"}], "image": "/batch/pageimg/..."}).encode()
            else:
                body = self.path.encode()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, seen


def test_snapshot(tmp_path):
    srv, seen = _watch()
    try:
        out = tmp_path / "snap"
        snap = sitebatch.snapshot(f"http://127.0.0.1:{srv.server_port}", out, "games-1977-79", "GAMES 1977-79")
    finally:
        srv.shutdown()
    on_disk = json.loads((out / "batch.json").read_text(encoding="utf-8"))
    assert on_disk == snap
    assert snap["snapshot"]["name"] == "games-1977-79" and snap["snapshot"]["dropped"] == 1
    # the maintainer's tools and other runs stay local
    assert not {"notes", "mastheads", "rerun", "spend"} & set(snap)
    assert snap["runs"] == ["run12"] and list(snap["run_notes"]) == ["run12"]
    a, b = snap["puzzles"]
    # Ready / Not ready are the proof page's: the ledger's ship isn't shown; a drop is
    assert a["choice"] == "" and a["by"] == "" and "proof" not in a and "diagnosis" not in a
    assert b["choice"] == "drop" and b["note"] == "a game board"
    assert snap["causes"]["causes"][0]["puzzles"][0]["choice"] == ""
    # every URL relative to the folder, and there; a page shared by two puzzles fetched once
    assert a["thumb"] == "thumbs/games1977-09-01-L026.png" and (out / a["thumb"]).exists()
    assert b["page"] == "page/games1977-09-01-L028.jpg" and (out / b["page"]).exists()
    assert a["maps"][0]["image"] == b["maps"][0]["image"] == "pages/games_1977-09_leaf_30.jpg"
    assert a["maps"][0]["full"] == "pages/games_1977-09_leaf_30-1400.jpg"
    assert sum(p.startswith("/batch/pageimg/") for p in seen) == 2
    assert snap["causes"]["causes"][0]["puzzles"][0]["thumb"] == a["thumb"]
    ov = json.loads((out / a["maps"][0]["overlay"]).read_text(encoding="utf-8"))
    assert ov["boxes"][0]["source"].startswith("assembly.json") and ov["image"] == a["maps"][0]["image"]
    assert sitebatch.publish(out, dry_run=True)[0].startswith("batch/games-1977-79/")
