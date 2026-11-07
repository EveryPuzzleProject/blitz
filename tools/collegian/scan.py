"""Find Mike Shenk's crossword in the Daily Collegian (Penn State), issue by issue.

Harvest stage only: locate the puzzle's page in each issue and keep what was downloaded.
Nothing here reads a puzzle; it scores each page's OCR text for the look of a crossword
(Across/Down heads, a run of numbered clues, "Answers in tomorrow's Collegian classifieds").

    python tools/collegian/scan.py issues          # the issue list for the run -> issues.tsv
    python tools/collegian/scan.py scan [--limit N] [--from DATE --to DATE]
    python tools/collegian/scan.py report
    python tools/collegian/scan.py pages [--limit N]   # the puzzle pages' images -> pages/, pages.tsv

Data lives outside the repo (COLLEGIAN_DIR, default ~/Projects/collegian-scans):
    cache/manifest/<date>.json     the issue's IIIF manifest (page list, image ids)
    cache/ocr/<date>/seq-<n>.txt   every page's OCR text we fetched (never discarded)
    issues.tsv                     one row per issue: verdict, page, score, evidence
    scan_log.jsonl                 what each page scored (so a verdict can be traced)
    pages/<date>/seq-<n>-page.jpg  each puzzle page whole, 1000 px tall (to see the layout and place the puzzle)
    pages/<date>/seq-<n>-puzzle.jpg  the puzzle's box padded 12% each side, at the archive's native resolution
    pages.tsv                      xword-ocr's folder source (docs/sources.md): the page row, then its crop
                                   (`crop_of`), each with its archive url; `page` is the archive's seq
    pages_fetch.jsonl              every image fetched, with its IIIF url

`pages` takes the page a person settled (decisions.jsonl) plus extra_pages.jsonl (pages beyond one per
date: the 1978-01-20 p1 reprint stub), and the box from box_fixes.jsonl, else crops.tsv, else the extra
page's own. Files already on disk are never fetched again. Then:
    cd ../xword-ocr && uv run xword-ocr harvest --folder ~/Projects/collegian-scans --pubid collegian --out harvests/collegian

Archive: https://panewsarchive.psu.edu/lccn/sn85054904/ (open, IIIF, per-page OCR).
Pages are scanned from the LAST page backwards, because the puzzle is usually near the
end of an issue; the scan stops at the first strong hit. Pages with only part of the
signal are kept as "weak" and sent to a person (see review.py).
"""
import argparse
import concurrent.futures as cf
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://pana.ulprod.k8s.libraries.psu.edu"
LCCN = "sn85054904"
FIRST, LAST = "1976-03-01", "1981-06-30"   # census: first 1976-03-11/12, last found 1981-05-15
HEAD = {"User-Agent": "EPP-blitz collegian harvest (research; contact via github.com/EveryPuzzleProject)"}
DATA = Path(os.environ.get("COLLEGIAN_DIR", Path.home() / "Projects" / "collegian-scans"))
COLS = ["date", "pages", "verdict", "seq", "score", "evidence", "scanned", "decided_by", "guess"]

_lock = threading.Lock()


def get(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=HEAD)
            return urllib.request.urlopen(req, timeout=90).read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            err = e
        except Exception as e:  # network blips: back off and retry
            err = e
        time.sleep(2 * (i + 1))
    raise RuntimeError(f"{url}: {err}")


def score(text):
    """What a crossword page looks like in OCR text. Returns (level, evidence dict)."""
    across = len(re.findall(r"^\W*Across\b", text, re.M | re.I))
    down = len(re.findall(r"^\W*Down\b", text, re.M | re.I))
    nums = len(re.findall(r"^\W*\d{1,2}\s+[A-Z][a-z]", text, re.M))
    ans = bool(re.search(r"answers?\s+(in|to)\s+tomorrow|tomorrow.s\s+(collegian|paper)", text, re.I))
    shenk = bool(re.search(r"sh[ea]nk", text, re.I))
    ev = dict(across=across, down=down, nums=nums, answers_line=ans, shenk=shenk)
    if (ans and nums >= 20) or (across and down and nums >= 20):
        return "strong", ev
    if ans or (across and down) or nums >= 25:
        return "weak", ev
    return "none", ev


def issue_list():
    p = DATA / "cache" / "collection.json"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(get(f"{BASE}/lccn/{LCCN}.json"))
    labels = [m["label"] for m in json.loads(p.read_text("utf8"))["manifests"]]
    return sorted(d for d in labels if FIRST <= d <= LAST)


def manifest(date):
    p = DATA / "cache" / "manifest" / f"{date}.json"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        b = get(f"{BASE}/lccn/{LCCN}/{date}/ed-1.json")
        if b is None:
            return None
        p.write_bytes(b)
    return json.loads(p.read_text("utf8"))


def ocr(date, seq):
    p = DATA / "cache" / "ocr" / date / f"seq-{seq}.txt"
    if not p.exists():
        b = get(f"{BASE}/lccn/{LCCN}/{date}/ed-1/seq-{seq}/ocr.txt")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b if b is not None else b"")
    return p.read_text("utf8", "replace")


def read_rows():
    p = DATA / "issues.tsv"
    rows = {}
    if p.exists():
        for line in p.read_text("utf8").splitlines()[1:]:
            f = line.split("\t")
            r = dict(zip(COLS, f + [""] * (len(COLS) - len(f))))
            rows[r["date"]] = r
    return rows


def write_rows(rows):
    DATA.mkdir(parents=True, exist_ok=True)
    out = ["\t".join(COLS)] + ["\t".join(str(r.get(c, "")) for c in COLS) for _, r in sorted(rows.items())]
    tmp = DATA / "issues.tsv.tmp"
    tmp.write_text("\n".join(out) + "\n", "utf8")
    tmp.replace(DATA / "issues.tsv")


def scan_issue(date):
    m = manifest(date)
    if m is None:
        return dict(date=date, verdict="not-in-archive")
    n = len(m["sequences"][0]["canvases"])
    weak, log = [], []
    for seq in range(n, 0, -1):          # last page first
        level, ev = score(ocr(date, seq))
        log.append(dict(date=date, seq=seq, level=level, **ev))
        if level == "strong":
            verdict, hit = "found", (seq, ev)
            break
        if level == "weak":
            weak.append((seq, ev))
    else:
        hit = None
        verdict = "check" if weak else "no-hit"
    if hit is None and weak:
        hit = weak[0]
    row = dict(date=date, pages=n, verdict=verdict, scanned=time.strftime("%Y-%m-%d"))
    if hit:
        row.update(seq=hit[0], score=("strong" if verdict == "found" else "weak"), evidence=json.dumps(hit[1]))
    with _lock, open(DATA / "scan_log.jsonl", "a", encoding="utf8") as f:
        for r in log:
            f.write(json.dumps(r) + "\n")
    return row


def cmd_issues(a):
    ds = issue_list()
    rows = read_rows()
    for d in ds:
        rows.setdefault(d, dict(date=d, verdict="pending"))
    write_rows(rows)
    print(f"{len(ds)} issues {ds[0]}..{ds[-1]} -> {DATA/'issues.tsv'}")


def cmd_scan(a):
    cmd_issues(a)
    rows = read_rows()
    todo = [d for d, r in rows.items() if r["verdict"] == "pending" and (not a.start or d >= a.start) and (not a.end or d <= a.end)]
    if a.limit:
        todo = todo[: a.limit]
    print(f"scanning {len(todo)} issues with {a.workers} workers", flush=True)
    done = 0
    with cf.ThreadPoolExecutor(a.workers) as ex:
        for row in ex.map(scan_issue, todo):
            rows[row["date"]].update(row)
            done += 1
            if done % 25 == 0:
                write_rows(rows)
                print(f"  {done}/{len(todo)} ({row['date']})", flush=True)
    write_rows(rows)
    cmd_report(a)


def cmd_prior(a):
    """For issues without a strong hit, guess the page from found issues nearby in time.

    The puzzle's page is regular within an era (page 4 through 1976-77, for example) but
    the OCR often misses the puzzle itself. The guess is only a place for a person to look
    first; it is recorded as 'seq|nearby-agreeing/nearby-found' so the view can say why.
    """
    from collections import Counter
    from datetime import date as D
    rows = read_rows()
    found = [(D.fromisoformat(d), int(r["seq"])) for d, r in rows.items() if r["verdict"] == "found" and r["seq"]]
    n = 0
    for d, r in rows.items():
        if r["verdict"] == "found" or not r["pages"]:
            continue
        day = D.fromisoformat(d)
        near = [s for dd, s in found if abs((dd - day).days) <= 45 and s <= int(r["pages"])]
        if near:
            seq, k = Counter(near).most_common(1)[0]
            r["guess"] = f"{seq}|{k}/{len(near)}"
            n += 1
    write_rows(rows)
    print(f"{n} issues got an era guess")


def alto(date, seq):
    """The page's ALTO OCR (word positions), kept gzipped under cache/alto/."""
    import gzip
    p = DATA / "cache" / "alto" / date / f"seq-{seq}.xml.gz"
    if not p.exists():
        b = get(f"{BASE}/lccn/{LCCN}/{date}/ed-1/seq-{seq}/ocr.xml") or b""
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(gzip.compress(b))
    return gzip.decompress(p.read_bytes())


def clue_box(xml, img_w, img_h, core_only=False):
    """Where the puzzle is on a page, from its OCR lines: the dense cluster of clue lines
    ("12 Stool", "Across", "Down"), widened to take in the grid beside it. Image pixels.
    This is a locator for a person to confirm by eye, not a reading of the puzzle."""
    import statistics
    import xml.etree.ElementTree as ET
    ns = "{http://www.loc.gov/standards/alto/ns-v2#}"
    root = ET.fromstring(xml)
    pg = root.find(f".//{ns}Page")
    pw, ph = float(pg.get("WIDTH")), float(pg.get("HEIGHT"))
    pts, nums, credits, heads, edges = [], [], [], [], []   # clue lines; cell numbers; the sponsor's credit line; Across headings; every line's box
    for tl in root.iter(f"{ns}TextLine"):
        strs = list(tl.iter(f"{ns}String"))
        text = " ".join(s.get("CONTENT", "") for s in strs)
        hx, hy, hw, hh = (float(tl.get(k)) for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT"))
        edges.append((hx, hy, hx + hw, hy + hh))
        if re.match(r"^\W*Across\b", text) and len(text) < 14:
            heads.append((hx, hy, hx + hw, hy + hh))
        if re.search(r"compliments\s+of|mcallister\s+building", text, re.I):
            x, y, w, h = (float(tl.get(k)) for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT"))
            credits.append((x, y, x + w, y + h))
        if re.match(r"^\W*(\d{1,2}\s+[A-Z][a-z]|Across\b|Down\b)", text):
            x, y, w, h = (float(tl.get(k)) for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT"))
            pts.append((x, y, x + w, y + h))
        else:
            for s in strs:
                if re.fullmatch(r"\d{1,2}", s.get("CONTENT", "")):
                    x, y, w, h = (float(s.get(k)) for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT"))
                    nums.append((x, y, x + w, y + h))
    if len(pts) < 12:
        return None
    if credits:
        pass                    # 1976-78 layout (sponsor's credit line): the clue lines are used as they are
    elif heads:
        def near(h):
            return [q for q in pts if h[0] - 0.03 * pw < q[0] < h[0] + 0.28 * pw and h[1] - 0.03 * ph < q[1] < h[1] + 0.40 * ph]
        best = max((near(h) for h in heads), key=len)
        if len(best) >= 12:
            pts = best
    else:
        # no heading read: clue columns are long tidy stacks of lines (same left edge, even spacing);
        # take the longest stack and the stacks beside it, leaving out scores, ads and other numbered lists
        hs = statistics.median(p[3] - p[1] for p in pts)
        cols = []
        for p in sorted(pts, key=lambda p: p[0]):
            for c in cols:
                if abs(c[0][0] - p[0]) < 0.012 * pw:
                    c.append(p)
                    break
            else:
                cols.append([p])
        stacks = []
        for c in cols:
            c.sort(key=lambda p: p[1])
            cur = [c[0]]
            for p in c[1:]:
                if p[1] - cur[-1][3] < 2.5 * hs:
                    cur.append(p)
                else:
                    stacks.append(cur)
                    cur = [p]
            stacks.append(cur)
        stacks = [s for s in stacks if len(s) >= 6]
        if stacks:
            main = max(stacks, key=len)
            mx0, mx1 = min(p[0] for p in main), max(p[2] for p in main)
            my0, my1 = min(p[1] for p in main), max(p[3] for p in main)
            near = [p for s in stacks for p in s
                    if mx0 - 0.25 * pw < p[0] < mx1 + 0.25 * pw and my0 - (my1 - my0) < p[1] < my1 + (my1 - my0)]
            if len(near) >= 12:
                pts = near

    def dense(boxes, radius, need):
        """boxes that have at least `need` others within `radius` (drops stray lines and page numbers)."""
        out = []
        for b in boxes:
            near = sum(1 for o in boxes if o is not b and abs(o[0] - b[0]) < radius and abs(o[1] - b[1]) < radius)
            if near >= need:
                out.append(b)
        return out

    def bbox(boxes):
        return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]

    core = dense(pts, 0.14 * pw, 3)
    if len(core) < 12:
        core = pts
    x0, y0, x1, y1 = bbox(core)
    if core_only:      # just where the clue lines are, in image pixels: the caller brings the grid
        return [round(x0 * img_w / pw), round(y0 * img_h / ph), round(x1 * img_w / pw), round(y1 * img_h / ph), len(pts)]
    # the grid: cell numbers in a window around the clues (it can be left, right, above or below them)
    bw, bh = x1 - x0, y1 - y0
    win = [n for n in nums if x0 - 2.5 * bw < n[0] < x1 + 1.5 * bw and y0 - 0.3 * bh < n[1] < y1 + 0.05 * bh
           and not (x0 <= n[0] and n[2] <= x1 and y0 <= n[1] and n[3] <= y1)]
    grid = dense(win, 0.05 * pw, 3)
    if len(grid) >= 15:
        gx0, gy0, gx1, gy1 = bbox(grid)
        x0, y0, x1, y1 = min(x0, gx0), min(y0, gy0), max(x1, gx1), max(y1, gy1)
    # 1976-78: the Bookstore's credit line ("Compliments of the Penn State Bookstore...") sits under the puzzle
    under = [c for c in credits if x0 - 0.5 * bw < (c[0] + c[2]) / 2 < x1 + 0.5 * bw and y0 < c[1] < y1 + 1.5 * bh]
    if len(grid) >= 15:
        pass
    elif under:                                        # the clues span the puzzle's width; the credit line is its floor
        y1 = max(c[3] for c in under)
    elif (x0 + x1) / 2 > 0.55 * pw:                   # clues left, grid running to the page's right edge
        x1 = x1 + 1.2 * bw
        y1 = y1 + 0.1 * bh
    else:                                              # the OCR didn't read the cell numbers: the grid sits beside the clues
        x0, x1 = x0 - 1.5 * bw, x1 + 1.5 * bw
        y0, y1 = y0 - 0.3 * bh, y1 + 0.1 * bh
    if under:
        y1 = max(y1, max(c[3] for c in under))
    elif (x0 + x1) / 2 > 0.55 * pw:                   # a puzzle on the right half: its grid runs to the text's right edge
        right = [e[2] for e in edges if e[0] > x0 and y0 - 0.6 * bh < e[1] < y1]   # incl. the running header above it
        if right:
            x1 = max(x1, max(right))
    if img_w > 9000 and x1 - x0 > 0.34 * pw:          # a two-page spread (1979-81): the puzzle is about 27% of its width,
        x0 = x1 - 0.32 * pw                            # so a wider box is loose on the left (comics); keep the right edge
    mx, my = 0.03 * pw, 0.02 * ph                      # a margin, and room for the title line above
    x0, x1 = max(0, x0 - mx), min(pw, x1 + mx)
    y0, y1 = max(0, y0 - 2 * my), min(ph, y1 + my)
    sx, sy = img_w / pw, img_h / ph
    return [round(x0 * sx), round(y0 * sy), round((x1 - x0) * sx), round((y1 - y0) * sy), len(pts)]


def cmd_crops(a):
    """crops.tsv: for each issue's puzzle page, a box around the puzzle (from the OCR's line positions)."""
    dec = {}
    p = DATA / "decisions.jsonl"
    if p.exists():
        for line in p.read_text("utf8").splitlines():
            if line.strip():
                r = json.loads(line)
                dec[r["date"]] = r
    todo = []
    for date, r in sorted(read_rows().items()):
        d = dec.get(date)
        seq = (d.get("seq") if d and d["verdict"] == "found" else (r["seq"] if not d and r["verdict"] == "found" else None))
        if seq:
            todo.append((date, int(seq)))

    def one(t):
        date, seq = t
        m = manifest(date)
        cv = m["sequences"][0]["canvases"][seq - 1]
        try:
            box = clue_box(alto(date, seq), cv["width"], cv["height"])
        except Exception as e:
            return date, seq, None, f"error {e}"
        return date, seq, box, "ocr-clue-lines" if box else "no-clue-lines"

    out = ["date\tseq\tx\ty\tw\th\tclue_lines\tmethod"]
    n = 0
    with cf.ThreadPoolExecutor(a.workers) as ex:
        for date, seq, box, how in ex.map(one, todo):
            out.append("\t".join([date, str(seq)] + ([str(v) for v in box] if box else ["", "", "", "", ""]) + [how]))
            n += bool(box)
            if len(out) % 100 == 0:
                print(f"  {len(out)-1}/{len(todo)}", flush=True)
    (DATA / "crops.tsv").write_text("\n".join(out) + "\n", "utf8")
    print(f"{n}/{len(todo)} pages got a box -> {DATA/'crops.tsv'}")


def cmd_boxes(a):
    """crops.tsv from the grids (grids.py) and the OCR's clue lines.

    A puzzle's box is its grid plus its clue lists and title. Where the OCR read the clue lines near the grid,
    the box is the union of the two. Where it didn't (most of 1976-78), the box is the grid widened by the
    typical grid-to-clues margins of the pages where both were found, per layout (single page / spread)."""
    import statistics
    recs = {}
    for line in (DATA / "grids.jsonl").read_text("utf8").splitlines():
        if line.strip():
            r = json.loads(line)
            recs[r["date"]] = r
    rows = []
    for date, r in sorted(recs.items()):
        gs = [g for g in r["grids"] if g["rows"] >= 11 and g["cols"] >= 9 and not g["has_letters"]]
        if not gs:
            rows.append((date, r["seq"], None, None, "no-grid"))
            continue
        q = gs[0]["quad"]
        gb = [min(p[0] for p in q), min(p[1] for p in q), max(p[0] for p in q), max(p[1] for p in q)]
        W, H = r["page"]
        core = None
        try:
            c = clue_box(alto(date, r["seq"]), W, H, core_only=True)
        except Exception:
            c = None
        gw, gh = gb[2] - gb[0], gb[3] - gb[1]
        if c:
            ccx, ccy = (c[0] + c[2]) / 2, (c[1] + c[3]) / 2
            near = abs(ccx - (gb[0] + gb[2]) / 2) < 3 * gw and abs(ccy - (gb[1] + gb[3]) / 2) < 2.2 * gh
            small = (c[2] - c[0]) < 3.2 * gw and (c[3] - c[1]) < 2.2 * gh
            core = c[:4] if near and small else None
        kind = ("spread" if W > 9000 else "single") + ("-big-grid" if gs[0]["rows"] >= 17 else "")   # 1976-77 framed layout
        rows.append((date, r["seq"], gb, core, kind, W, H, gs[0]["pitch"]))
    # margins (in grid widths/heights) of the union over the grid, from pages where the clue lines were found
    fam = {}
    for kind in sorted({x[4] for x in rows if len(x) > 5}):
        offs = []
        for d, seq, gb, core, k, *rest in [x for x in rows if len(x) > 5]:
            if k == kind and core:
                gw, gh = gb[2] - gb[0], gb[3] - gb[1]
                offs.append(((gb[0] - min(gb[0], core[0])) / gw, (gb[1] - min(gb[1], core[1])) / gh,
                             (max(gb[2], core[2]) - gb[2]) / gw, (max(gb[3], core[3]) - gb[3]) / gh))
        fam[kind] = [statistics.median(o[i] for o in offs) for i in range(4)] if offs else [0.05, 0.1, 0.05, 0.1]
        print(f"{kind}: {len(offs)} pages with clue lines near the grid; typical margins (grid widths/heights) "
              f"left {fam[kind][0]:.2f} top {fam[kind][1]:.2f} right {fam[kind][2]:.2f} bottom {fam[kind][3]:.2f}")
    out = ["date\tseq\tx\ty\tw\th\tclue_lines\tmethod"]
    counts = {}
    for row in rows:
        if len(row) == 5:                      # no grid found: fall back to the box around the OCR's clue lines, if any
            W, H = recs[row[0]]["page"]
            try:
                b = clue_box(alto(row[0], row[1]), W, H)
            except Exception:
                b = None
            how = "clue-lines-only (no grid found)" if b else "no-grid"
            out.append("\t".join([row[0], str(row[1])] + ([str(v) for v in b[:4]] + [str(b[4])] if b else ["", "", "", "", ""]) + [how]))
            counts[how] = counts.get(how, 0) + 1
            continue
        date, seq, gb, core, kind, W, H, pitch = row
        gw, gh = gb[2] - gb[0], gb[3] - gb[1]
        if core:
            x0, y0, x1, y1 = min(gb[0], core[0]), min(gb[1], core[1]), max(gb[2], core[2]), max(gb[3], core[3])
            how = "grid+clue-lines"
        else:
            m = fam[kind]
            x0, y0, x1, y1 = gb[0] - m[0] * gw, gb[1] - m[1] * gh, gb[2] + m[2] * gw, gb[3] + m[3] * gh
            how = "grid+typical-margins"
        # the title and byline sit above the grid (a line in 1976-77; the big "Crossword by Mike Shenk" header in 1978-81)
        if "big-grid" in kind and "spread" not in kind:   # 1976-77: a title/byline line above, the sponsor's credit line below
            y0, y1 = y0 - 2.5 * pitch, y1 + 3 * pitch
        else:
            y0 = min(y0, gb[1] - 0.45 * gh)
        mx, my = 0.03 * (x1 - x0), 0.03 * (y1 - y0)
        x0, y0, x1, y1 = max(0, x0 - mx), max(0, y0 - my), min(W, x1 + mx), min(H, y1 + my)
        out.append("\t".join([date, str(seq), str(round(x0)), str(round(y0)), str(round(x1 - x0)), str(round(y1 - y0)), "", how]))
        counts[how] = counts.get(how, 0) + 1
    # boxes a person drew by hand (review.py /boxes) win over everything above
    fixes = {}
    fp = DATA / "box_fixes.jsonl"
    if fp.exists():
        for line in fp.read_text("utf8").splitlines():
            if line.strip():
                r = json.loads(line)
                fixes[r["date"]] = r
    index = {l.split("\t")[0]: i for i, l in enumerate(out) if i > 0}
    for d, r in fixes.items():
        if r.get("box") and d in index:
            x, y, w, h = r["box"]
            out[index[d]] = "\t".join([d, str(r["seq"]), str(x), str(y), str(w), str(h), "", "hand-placed by a person"])
            counts["hand-placed by a person"] = counts.get("hand-placed by a person", 0) + 1
    (DATA / "crops.tsv").write_text("\n".join(out) + "\n", "utf8")
    print(counts, "->", DATA / "crops.tsv")


def cmd_publish(a):
    """Write the public index (no images) for the `collegian` repo from the scans data.

    puzzles.tsv: one row per issue: the page a person (or the OCR) settled on, with a link
    into Penn State's archive. exceptions.tsv is copied. Derived output: edit the sources.
    """
    import datetime
    dec = {}
    p = DATA / "decisions.jsonl"
    if p.exists():
        for line in p.read_text("utf8").splitlines():
            if line.strip():
                r = json.loads(line)
                dec[r["date"]] = r
    out = Path(a.to)
    out.mkdir(parents=True, exist_ok=True)
    lines = ["date\tweekday\tstatus\tpage\tkind\tdecided_by\tarchive_url"]
    n = {}
    for date, r in sorted(read_rows().items()):
        d = dec.get(date)
        if d:
            status, seq, kind, by = d["verdict"], d.get("seq") or "", d.get("kind", "regular"), "person"
        else:
            status, seq, kind, by = r["verdict"], r.get("seq", ""), "", "ocr"
        if status != "found":
            seq = kind = ""
        url = f"https://panewsarchive.psu.edu/lccn/{LCCN}/{date}/ed-1/seq-{seq}/" if seq else ""
        wd = datetime.date.fromisoformat(date).strftime("%a")
        lines.append("\t".join([date, wd, status, str(seq), kind, by, url]))
        n[status] = n.get(status, 0) + 1
    (out / "puzzles.tsv").write_text("\n".join(lines) + "\n", "utf8")
    ex = DATA / "exceptions.tsv"
    if ex.exists():
        (out / "exceptions.tsv").write_text(ex.read_text("utf8"), "utf8")
    print(f"{len(lines) - 1} issues -> {out/'puzzles.tsv'}  {n}")


PAGE_H = 1000   # the whole page, 1000 px tall (spreads ~1300 wide): layout, headlines and the puzzle's place show; reading is the crop's job
PAD = 0.12      # each side of a puzzle's box, as a share of the box: err on too much (grid, clues, title, byline)


def _last_by_date(name):
    out = {}
    p = DATA / name
    if p.exists():
        for line in p.read_text("utf8").splitlines():
            if line.strip():
                r = json.loads(line)
                out[r["date"]] = r
    return out


def puzzle_pages():
    """Every puzzle page to collect, in date and page order: (date, seq, box, box_source, notes).

    The page is the one a person settled in decisions.jsonl (last line per date wins); extra_pages.jsonl adds
    pages beyond one per date (the 1978-01-20 p1 reprint stub). The box is the hand-placed one in
    box_fixes.jsonl if any, else crops.tsv's, else the extra page's own; all in archive (native) pixels."""
    import csv
    crops = {}
    p = DATA / "crops.tsv"
    if p.exists():
        with open(p, encoding="utf8", newline="") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                if r["x"]:
                    crops[(r["date"], int(r["seq"]))] = ([int(r[k]) for k in "xywh"], r["method"])
    fixes = {(d, int(r["seq"])): (r["box"], f"hand-placed by a person ({r.get('how', '')})")
             for d, r in _last_by_date("box_fixes.jsonl").items() if r.get("box")}
    notes = {}
    ex = DATA / "exceptions.tsv"
    if ex.exists():
        for line in ex.read_text("utf8").splitlines()[1:]:
            f = line.split("\t")
            if len(f) >= 3 and f[1].isdigit() and f[2] in ("reprint-stub", "flag-on-import"):
                notes.setdefault((f[0], int(f[1])), []).append(f"{f[2]} (exceptions.tsv)")
    out = {}
    for d, r in _last_by_date("decisions.jsonl").items():
        if r["verdict"] == "found" and r.get("seq"):
            k = (d, int(r["seq"]))
            box, how = fixes.get(k) or crops.get(k) or (None, "no box recorded")
            n = list(notes.get(k, []))
            if r.get("kind") and r["kind"] != "regular":
                n.append(r["kind"])
            out[k] = (box, how, n)
    p = DATA / "extra_pages.jsonl"
    if p.exists():
        for line in p.read_text("utf8").splitlines():
            if line.strip():
                r = json.loads(line)
                k = (r["date"], int(r["seq"]))
                box, how = fixes.get(k) or (r["box"], f"{r['how']} (extra_pages.jsonl, {r['by']})")
                out[k] = (box, how, list(notes.get(k, [])) or [r.get("kind", "extra page")])
    return [(d, s, *v) for (d, s), v in sorted(out.items())]


def padded(box, W, H):
    x, y, w, h = box
    px, py = round(PAD * w), round(PAD * h)
    x0, y0 = max(0, x - px), max(0, y - py)
    return [x0, y0, min(W, x + w + px) - x0, min(H, y + h + py) - y0]


def page_files(date, seq):
    return f"pages/{date}/seq-{seq}-page.jpg", f"pages/{date}/seq-{seq}-puzzle.jpg"


def cmd_pages(a):
    """Fetch each puzzle page's images into pages/ and write pages.tsv (xword-ocr's folder source).

    Per page: the whole page PAGE_H px tall, and the puzzle's box padded by PAD at the archive's native
    resolution (a `crop_of` crop, the one the harvest reads). Resumable: a file already on disk is never
    fetched again (and never replaced). Each fetch is logged in pages_fetch.jsonl with its IIIF url."""
    todo = puzzle_pages()
    if a.limit:
        todo = todo[: a.limit]
    jobs = []
    for date, seq, box, how, notes in todo:
        cv = manifest(date)["sequences"][0]["canvases"][seq - 1]
        iid = cv["images"][0]["resource"]["@id"]
        W, H = cv["width"], cv["height"]
        page_f, crop_f = page_files(date, seq)
        jobs.append((DATA / page_f, f"{BASE}{iid}/full/,{PAGE_H}/0/default.jpg"))
        region = padded(box, W, H) if box else [0, 0, W, H]
        jobs.append((DATA / crop_f, f"{BASE}{iid}/{','.join(map(str, region))}/full/0/default.jpg"))
    need = [j for j in jobs if not j[0].exists()]
    print(f"{len(todo)} puzzle pages, {len(jobs)} images, {len(need)} to fetch with {a.workers} workers", flush=True)
    t0, done, nbytes = time.time(), 0, 0

    def fetch(job):
        path, url = job
        t = time.time()
        b = get(url)
        if not b:
            return path, url, 0, "not found"
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(b)
        tmp.replace(path)
        if a.pause:
            time.sleep(a.pause)
        return path, url, len(b), f"{time.time() - t:.1f}s"

    with cf.ThreadPoolExecutor(a.workers) as ex:
        for path, url, n, how in ex.map(fetch, need):
            done += 1
            nbytes += n
            with _lock, open(DATA / "pages_fetch.jsonl", "a", encoding="utf8") as f:
                f.write(json.dumps(dict(file=path.relative_to(DATA).as_posix(), url=url, bytes=n, result=how,
                                        at=time.strftime("%Y-%m-%dT%H:%M:%S"))) + "\n")
            if not n:
                print(f"  FAILED {path.relative_to(DATA)}: {url}", flush=True)
            if done % 50 == 0 or done == len(need):
                el = time.time() - t0
                print(f"  {done}/{len(need)}  {nbytes / 1e6:.0f} MB  {el / 60:.1f} min", flush=True)
    if not a.limit:
        write_pages_tsv()


def write_pages_tsv():
    """pages.tsv (xword-ocr's folder source): per issue, in seq order, the page's own row, then its crops: the
    puzzle's (cmd_pages) and any answer key printed on it (answers.py save, answer_keys.jsonl). Leaves count in
    this order, which is the archive's scan order (seq), not the printed page number (the archive gives none).
    A key goes under the issue it was printed in (docs/sources.md), with its note naming the puzzle it answers and
    its `answers` column the file of that puzzle's crop row: the pairing as answer_keys.jsonl records it (the
    region-hash match or the person's pick on /answers), never re-matched here; the harvest uses it as given."""
    import datetime
    pages = {}          # (date, seq) -> [page row, crop rows...]
    missing = 0

    def cap(f):
        return datetime.date.fromtimestamp((DATA / f).stat().st_mtime).isoformat()
    for date, seq, box, how, notes in puzzle_pages():
        page_f, crop_f = page_files(date, seq)
        if not (DATA / page_f).exists() or not (DATA / crop_f).exists():
            missing += 1
            continue
        url = f"https://panewsarchive.psu.edu/lccn/{LCCN}/{date}/ed-1/seq-{seq}/"
        cv = manifest(date)["sequences"][0]["canvases"][seq - 1]
        region = padded(box, cv["width"], cv["height"]) if box else [0, 0, cv["width"], cv["height"]]
        pnote = "; ".join([f"whole page at {PAGE_H} px tall (archive image {cv['width']}x{cv['height']})"] + notes)
        cnote = "; ".join([f"archive pixels {','.join(map(str, region))} at native resolution: the box from {how}, "
                           f"padded {round(PAD * 100)}% each side" if box else "no box recorded: the whole page"] + notes)
        pages[(date, seq)] = [[page_f, f"collegian-{date}", date, str(seq), url, cap(crop_f), pnote, "", ""],
                              [crop_f, f"collegian-{date}", date, str(seq), url, cap(crop_f), cnote, page_f, ""]]
    keys = DATA / "answer_keys.jsonl"
    nkeys = 0
    keyrows = []        # (key file, the puzzle crop it answers)
    for line in (keys.read_text("utf8").splitlines() if keys.exists() else []):
        if not line.strip():
            continue
        k = json.loads(line)
        if not (DATA / k["file"]).exists() or not (DATA / k["page_file"]).exists():
            missing += 1
            continue
        date, seq = k["issue"], k["seq"]
        url = f"https://panewsarchive.psu.edu/lccn/{LCCN}/{date}/ed-1/seq-{seq}/"
        W, H = k["page_size"]
        if (date, seq) not in pages:
            pages[(date, seq)] = [[k["page_file"], f"collegian-{date}", date, str(seq), url, cap(k["page_file"]),
                                   f"whole page at {PAGE_H} px tall (archive image {W}x{H}); carries an answer key", "", ""]]
        knote = (f"answer key to the puzzle of {k['date']} (page {k['puzzle_seq']} of that issue), printed in this issue; "
                 f"archive pixels {','.join(map(str, k['region']))} at native resolution: {k['how']}; padded each side")
        # the puzzle it answers, by its crop row (k["date"], not k["id"]: the 1978-01-20 p1 stub's id is "...-seq1")
        answers = page_files(k["date"], k["puzzle_seq"])[1]
        keyrows.append((k["file"], answers))
        pages[(date, seq)].append([k["file"], f"collegian-{date}", date, str(seq), url, cap(k["file"]), knote,
                                   k["page_file"], answers])
        nkeys += 1
    files = {r[0] for rs in pages.values() for r in rs}
    orphans = [f"{kf} -> {pf}" for kf, pf in keyrows if pf not in files]
    if orphans:
        raise SystemExit(f"{len(orphans)} answer keys name a puzzle crop that is not a row of pages.tsv: " + "; ".join(orphans[:5]))
    rows = ["\t".join(["file", "issue", "date", "page", "url", "captured", "note", "crop_of", "answers"])]
    for _, rs in sorted(pages.items()):
        rows += ["\t".join(r) for r in rs]
    (DATA / "pages.tsv").write_text("\n".join(rows) + "\n", "utf8")
    print(f"{len(pages)} pages, {nkeys} answer keys -> {DATA / 'pages.tsv'}" + (f"; {missing} not yet fetched" if missing else ""))


def cmd_report(a):
    rows = read_rows()
    from collections import Counter
    c = Counter(r["verdict"] for r in rows.values())
    print("verdicts:", dict(c))
    seqfrom = Counter()
    for r in rows.values():
        if r["verdict"] == "found" and r["seq"] and r["pages"]:
            seqfrom[int(r["pages"]) - int(r["seq"])] += 1
    print("found: pages from the end (0 = last page):", sorted(seqfrom.items()))
    yr = Counter((r["date"][:4], r["verdict"]) for r in rows.values())
    for y in sorted({k[0] for k in yr}):
        print(y, {v: n for (yy, v), n in yr.items() if yy == y})


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("issues").set_defaults(fn=cmd_issues)
    q = sub.add_parser("scan")
    q.add_argument("--limit", type=int)
    q.add_argument("--from", dest="start")
    q.add_argument("--to", dest="end")
    q.add_argument("--workers", type=int, default=4)
    q.set_defaults(fn=cmd_scan)
    sub.add_parser("report").set_defaults(fn=cmd_report)
    q = sub.add_parser("crops", help="find a box around each puzzle from the OCR's line positions -> crops.tsv")
    q.add_argument("--workers", type=int, default=4)
    q.set_defaults(fn=cmd_crops)
    sub.add_parser("boxes", help="crops.tsv from the grids (grids.py) plus the OCR's clue lines").set_defaults(fn=cmd_boxes)
    q = sub.add_parser("publish", help="write the public index (puzzles.tsv, exceptions.tsv) for the collegian repo")
    q.add_argument("--to", default=str(Path.home() / "Projects" / "collegian"))
    q.set_defaults(fn=cmd_publish)
    q = sub.add_parser("pages", help="fetch each puzzle page (whole page reduced, puzzle crop native) -> pages/, pages.tsv")
    q.add_argument("--limit", type=int, help="fetch only the first N pages (pages.tsv is written only for a full run)")
    q.add_argument("--workers", type=int, default=3)
    q.add_argument("--pause", type=float, default=0.5, help="seconds each worker waits after a fetch")
    q.set_defaults(fn=cmd_pages)
    sub.add_parser("prior",help="guess the page of issues without a hit from found issues nearby").set_defaults(fn=cmd_prior)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
