"""The grid on each puzzle page, found by xword-ocr's detector.

A harvest milestone: for every issue whose puzzle page a person settled, find the crossword grid(s) on that
page and record where each is (corners, in the archive's own pixels), its size, and its black/white cells.
Uses xword-ocr's `detect_grids` (lattice of white cells, then of grid-line crossings), so this runs in
xword-ocr's environment:

    cd ../xword-ocr && uv run python ../blitz/tools/collegian/grids.py [--limit N] [--workers 4]

Writes grids.jsonl in the data folder (COLLEGIAN_DIR): one line per page, with the xword-ocr commit it was
made with. Re-running skips pages already recorded for the same commit.

The black/white pattern is kept because a puzzle's answer grid (printed the next day) has the same pattern,
which is how the answer keys will be matched to their puzzles.
"""
import argparse
import concurrent.futures as cf
import importlib.util
import io
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
from PIL import Image

spec = importlib.util.spec_from_file_location("collegian_scan", Path(__file__).with_name("scan.py"))
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)

from xword_ocr.grid import detect_grids   # noqa: E402  (xword-ocr's environment)

OUT = scan.DATA / "grids.jsonl"
_lock = threading.Lock()


def xo_rev():
    import xword_ocr
    try:
        return subprocess.run(["git", "-C", str(Path(xword_ocr.__file__).parent), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def settled_pages():
    """(date, seq) for every issue a person settled as having a puzzle (the last decision wins)."""
    dec = {}
    p = scan.DATA / "decisions.jsonl"
    for line in p.read_text("utf8").splitlines():
        if line.strip():
            r = json.loads(line)
            dec[r["date"]] = r
    return sorted((d, int(r["seq"])) for d, r in dec.items() if r["verdict"] == "found" and r.get("seq"))


def symmetric(cells):
    R, C = len(cells), len(cells[0])
    return all(cells[r][c] == cells[R - 1 - r][C - 1 - c] for r in range(R) for c in range(C))


def plausible(grids):
    """the main grid is a crossword-shaped lattice: roughly square and 180-degree symmetric"""
    if not grids:
        return False
    g = grids[0]
    return symmetric(g["cells"]) and abs(g["rows"] - g["cols"]) <= 1 and g["rows"] >= 11


def work(item, rev, retry=False):
    date, seq = item
    cv = scan.manifest(date)["sequences"][0]["canvases"][seq - 1]
    iid = cv["images"][0]["resource"]["@id"]
    W, H = cv["width"], cv["height"]
    spread = W > 9000
    # a two-page spread needs more pixels for the same cell size; a retry goes bigger
    widths = [4800, 6400] if retry and spread else [3600] if spread else [3600, 4800] if retry else [2400]
    best = None
    for width in widths:
        b = scan.get(f"{scan.BASE}{iid}/full/{width},/0/default.jpg")
        gray = np.asarray(Image.open(io.BytesIO(b)).convert("L"))
        k = W / gray.shape[1]
        t = time.time()
        found = []
        for g in detect_grids(gray, max_dim=max(gray.shape)):
            found.append(dict(rows=int(g.rows), cols=int(g.cols), pitch=round(float(g.pitch) * k, 1),
                              quad=[[round(float(x) * k), round(float(y) * k)] for x, y in g.quad],
                              cells=["".join(r) for r in g.cells], has_letters=bool(g.has_letters)))
        rec = dict(date=date, seq=seq, page=[W, H], scale=round(k, 3), width_used=width, detect_s=round(time.time() - t, 2),
                   xword_ocr=rev, grids=found)
        if best is None or (plausible(found) and not plausible(best["grids"])) or (not best["grids"] and found):
            best = rec
        if plausible(found):
            break
    return best


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--retry-bad", action="store_true",
                    help="redo the pages whose recorded grid is missing or not a plausible crossword, at higher resolution")
    a = ap.parse_args()
    rev = xo_rev()
    if a.retry_bad:
        recs = {}
        for line in OUT.read_text("utf8").splitlines():
            if line.strip():
                r = json.loads(line)
                recs[(r["date"], r["seq"])] = r
        bad = [k for k, r in recs.items() if not plausible(r["grids"])]
        print(f"retrying {len(bad)} of {len(recs)} pages at higher resolution", flush=True)
        fixed = 0
        with cf.ThreadPoolExecutor(a.workers) as ex:
            for k, r in zip(bad, ex.map(lambda t: work(t, rev, retry=True), bad)):
                if plausible(r["grids"]):
                    fixed += 1
                recs[k] = r
        OUT.write_text("\n".join(json.dumps(recs[k]) for k in sorted(recs)) + "\n", "utf8")
        print(f"now plausible: {fixed} of {len(bad)} retried")
        return
    done = set()
    if OUT.exists():
        for line in OUT.read_text("utf8").splitlines():
            if line.strip():
                r = json.loads(line)
                if r["xword_ocr"] == rev:
                    done.add((r["date"], r["seq"]))
    todo = [t for t in settled_pages() if t not in done]
    if a.limit:
        todo = todo[: a.limit]
    print(f"xword-ocr {rev}: {len(todo)} pages to do ({len(done)} already recorded)", flush=True)
    n = 0
    with cf.ThreadPoolExecutor(a.workers) as ex, open(OUT, "a", encoding="utf8") as f:
        for r in ex.map(lambda t: work(t, rev), todo):
            with _lock:
                f.write(json.dumps(r) + "\n")
                f.flush()
            n += 1
            if n % 50 == 0:
                print(f"  {n}/{len(todo)}", flush=True)
    print("done")


if __name__ == "__main__":
    main()
