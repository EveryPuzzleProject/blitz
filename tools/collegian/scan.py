"""Find Mike Shenk's crossword in the Daily Collegian (Penn State), issue by issue.

Harvest stage only: locate the puzzle's page in each issue and keep what was downloaded.
Nothing here reads a puzzle; it scores each page's OCR text for the look of a crossword
(Across/Down heads, a run of numbered clues, "Answers in tomorrow's Collegian classifieds").

    python tools/collegian/scan.py issues          # the issue list for the run -> issues.tsv
    python tools/collegian/scan.py scan [--limit N] [--from DATE --to DATE]
    python tools/collegian/scan.py report

Data lives outside the repo (COLLEGIAN_DIR, default ~/Projects/collegian-scans):
    cache/manifest/<date>.json     the issue's IIIF manifest (page list, image ids)
    cache/ocr/<date>/seq-<n>.txt   every page's OCR text we fetched (never discarded)
    issues.tsv                     one row per issue: verdict, page, score, evidence
    scan_log.jsonl                 what each page scored (so a verdict can be traced)

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
FIRST, LAST = "1976-03-01", "1981-06-30"   # catalog: first 1976-03-11/12, last found 1981-05-15
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


def clue_box(xml, img_w, img_h):
    """Where the puzzle is on a page, from its OCR lines: the dense cluster of clue lines
    ("12 Stool", "Across", "Down"), widened to take in the grid beside it. Image pixels.
    This is a locator for a person to confirm by eye, not a reading of the puzzle."""
    import statistics
    import xml.etree.ElementTree as ET
    ns = "{http://www.loc.gov/standards/alto/ns-v2#}"
    root = ET.fromstring(xml)
    pg = root.find(f".//{ns}Page")
    pw, ph = float(pg.get("WIDTH")), float(pg.get("HEIGHT"))
    pts, nums, credits = [], [], []   # clue lines; the small numbers in the grid's cells; the sponsor's credit line
    for tl in root.iter(f"{ns}TextLine"):
        strs = list(tl.iter(f"{ns}String"))
        text = " ".join(s.get("CONTENT", "") for s in strs)
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
    else:                                              # the OCR didn't read the cell numbers: the grid sits beside the clues
        x0, x1 = x0 - 1.5 * bw, x1 + 1.5 * bw
        y0, y1 = y0 - 0.3 * bh, y1 + 0.1 * bh
    if under:
        y1 = max(y1, max(c[3] for c in under))
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
    q = sub.add_parser("publish", help="write the public index (puzzles.tsv, exceptions.tsv) for the collegian repo")
    q.add_argument("--to", default=str(Path.home() / "Projects" / "collegian"))
    q.set_defaults(fn=cmd_publish)
    sub.add_parser("prior", help="guess the page of issues without a hit from found issues nearby").set_defaults(fn=cmd_prior)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
