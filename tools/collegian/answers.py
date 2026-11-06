"""The printed answer key for every Collegian puzzle: find it, match it, save it into the folder source.

Where the keys are, as the matches showed it: 1976 to Nov 1977 on another page of the same issue ("Answers on
p. 21"; the answers page says "answers to page 4 puzzle" and "Compliments of the Penn State Bookstore"); Dec 1977 to
Aug 1978 in the same day's classifieds ("Answers in Collegian Classifieds"); from Sep 1978 in the next issue's
classifieds ("Answers to Yesterday's Puzzle"). Four milestones, each a file in the data folder (COLLEGIAN_DIR),
each read by the next and by the view:

    python tools/collegian/answers.py candidates     # -> answer_candidates.jsonl  (text only: cached OCR)
    cd ../xword-ocr && uv run python ../blitz/tools/collegian/answers.py detect [--rank N]   # -> answer_grids.jsonl
    python tools/collegian/answers.py match          # -> answer_matches.jsonl, answer_puzzles.jsonl
    python tools/collegian/answers.py save           # -> pages/<issue>/seq-<n>-key-<date>.jpg, answer_keys.jsonl, pages.tsv
    python tools/collegian/answers.py report

`detect` and `match` alternate: `detect --rank 1` looks at each puzzle's best candidate page, `match` says which
puzzles now have a key, `detect --rank 2` looks at the next candidate only for the puzzles still without one,
and so on (`run` does the loop). A person settles what is left on review.py's /answers sheet
(answer_decisions.jsonl, the last line per puzzle date wins), and `save` takes those too.

1. candidates (answer_candidates.jsonl, one line per puzzle). For puzzle date D on page s, from the archive's
   own OCR text: the puzzle page's pointer ("Answers on p. N" -> page N of issue D, and its neighbours, since the
   archive's seq can be off by one from the printed page number); pages of D that point back ("answers to
   puzzle, page s") or carry the sponsor line; pages of the next archive issue headed "Yesterday's puzzle" /
   "Answers to ...", classifieds pages (the "CLASSIFIED ADS" head or a run of For Rent / Roommate / Lost heads),
   and the next issue's puzzle page; the page whose OCR repeats the puzzle's rows (a key's row reads as words
   broken at its black squares, so the words' lengths are the row's runs of white squares); where the keys of
   puzzles matched within 30 days were (same issue or next, so many pages from its end: learned, re-learned each
   round); the next issue's last pages as a last resort. Each candidate keeps its evidence and is ranked by it;
   `browse` names the issues a person looks through on /answers.

2. detect (answer_grids.jsonl, one line per page looked at). The page at half the archive's native width
   (2400-2500 px for a single page, ~5000 for a 1979-81 two-page spread, so cells come out ~16 px), xword-ocr's
   `detect_grids` on the page and on overlapping 1600 px tiles (it stops at the first lattice it cannot build,
   so on a busy classifieds page a small key never gets a turn; findings.md), every grid recorded with corners in
   archive pixels, rows/cols, black/white cells and `has_letters`; the page's own puzzle is marked `own_puzzle`.
   A puzzle page already in grids.jsonl is not fetched again: its recorded grids are reused (that is where the
   36 second grids come from). Images are cached under cache/answers/ (gitignored), never discarded.

3. match: region hashes, not a nearest search. Every puzzle's black/white pattern (grids.jsonl, the main
   grid) is cut into all its 5x5 windows; each window's 25 cells are a hash key, indexed with the puzzle and the
   window's position. A detected grid's windows vote: a window that hits puzzle P at position (r0, c0), while it
   sits at (r, c) in the grid, votes for (P, offset r0-r, c0-c), with weight log(N / df), df being how many
   puzzles contain that window (an all-white 5x5 is in nearly every puzzle and says nothing; a window with an
   odd black square says a lot). The top 12 (puzzle, offset) by vote are then checked cell by cell; a grid is
   matched when it is the puzzle's size at offset (0, 0) and at most max(3, cells/40) cells differ. A misread
   cell spoils only the windows that contain it, so a few misreads still leave the right puzzle on the
   shortlist; a grid detected only in part still votes for its puzzle at its true offset and is reported as
   "partial", for a person, never accepted. Shenk reused grids (190 of 860 patterns are shared exactly), so among
   the patterns within 2 cells of the best, the puzzle in the key's own issue or the one before wins, then the
   one whose candidate list named the page with more text evidence; a tie that is still a tie is "unclear". The
   record names the patterns it was chosen over. Last, the paper's habit is learned from the neighbours: where
   70% of the keys matched within 30 days (90 in a thin month) sit at one distance, a key at the other goes to a
   person as "odd-distance". Nothing in it knows about the Collegian: it needs only patterns and issue order, so
   it can move into xword-ocr beside `match_solutions` (findings.md).

4. save. For each puzzle's key: a native-resolution crop of the key (its corners, padded 25% of the grid's
   size each side, so the heading shows) as pages/<issue the key was printed in>/seq-<n>-key-<puzzle date>.jpg,
   the whole page 1000 px tall if that page is not in the folder yet, and rows in pages.tsv under the issue the
   key was printed in (xword-ocr docs/sources.md: "save the answers too, under the issue they were printed in"),
   with `note` naming the puzzle it answers and where its box came from.
"""
import argparse
import concurrent.futures as cf
import importlib.util
import json
import math
import re
import threading
import time
from collections import Counter, defaultdict
from pathlib import Path

_spec = importlib.util.spec_from_file_location("collegian_scan", Path(__file__).with_name("scan.py"))
scan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scan)
DATA = scan.DATA

CANDS = DATA / "answer_candidates.jsonl"
GRIDS = DATA / "answer_grids.jsonl"
MATCHES = DATA / "answer_matches.jsonl"
PUZZLES = DATA / "answer_puzzles.jsonl"
DECISIONS = DATA / "answer_decisions.jsonl"
KEYS = DATA / "answer_keys.jsonl"
CACHE = DATA / "cache" / "answers"
K = 5                  # window size for the region hashes
TILE, TILE_STEP = 1600, 1000   # detect on overlapping tiles of the half-width page too (px of the fetched image)
METHOD = "page+tiles-1600/1000"
SHORTLIST = 4          # candidate evidence score that puts a page on /answers' short list (and in detect --shortlist)
KEY_PAD = 0.25         # each side of a key's crop, as a share of the grid's size
_lock = threading.Lock()


def jl(path):
    out = []
    if path.exists():
        for line in path.read_text("utf8").splitlines():
            if line.strip():
                out.append(json.loads(line))
    return out


def write_jl(path, rows):
    tmp = path.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf8")
    tmp.replace(path)


def canvas(date, seq):
    return scan.manifest(date)["sequences"][0]["canvases"][seq - 1]


def n_pages(date):
    m = scan.manifest(date)
    return len(m["sequences"][0]["canvases"]) if m else 0


def archive_url(date, seq):
    return f"https://panewsarchive.psu.edu/lccn/{scan.LCCN}/{date}/ed-1/seq-{seq}/"


# ---------------------------------------------------------------------------------------------------------------
# 1. candidates
# ---------------------------------------------------------------------------------------------------------------

def puzzles():
    """Every puzzle: (date, seq, kind) from the pages scan.py collected (decisions + extra_pages)."""
    return [(d, s, (notes[0] if notes else "regular")) for d, s, _box, _how, notes in scan.puzzle_pages()]


def extra_pages():
    return {(r["date"], int(r["seq"])) for r in jl(DATA / "extra_pages.jsonl")}


def pid(date, seq, extras=None):
    """A puzzle's id: its date, or date-seqN for a second puzzle page of the date (the 1978-01-20 p1 stub)."""
    return f"{date}-seq{seq}" if (date, seq) in (extra_pages() if extras is None else extras) else date


POINTER = re.compile(r"answers?\s+(?:to\s+(?:the\s+)?puzzle\s+)?(?:are\s+)?on\s+p(?:age|g|\.|,)?\s*(\d{1,2})", re.I)
BACKREF = re.compile(r"\(\s*a\w{3,7}\s+to\s+puz\w*[,.]?\s+p\w{0,3}[*.,]?\s*(\d{1,2})", re.I)
LABEL = re.compile(r"yesterday.?s\s*puzzle|answers?\s+to\s+(?:yesterday|last|friday|today)", re.I)
CLASSIFIED_HEAD = re.compile(r"classified\s+ads|collegian\s*-\s*classified", re.I)
CLASSIFIED_WORDS = re.compile(r"^\W*(for\s+rent|for\s+sale|roommates?|lost|found|wanted|personals?|notices?|help\s+wanted|rides?|sublet)\b", re.I | re.M)
SPONSOR = re.compile(r"compliments\s+of\s+the\s+penn\s+state", re.I)


def page_evidence(date, seq):
    t = scan.ocr(date, seq)
    ev = []
    if LABEL.search(t):
        ev.append(("label", f"'{LABEL.search(t).group(0)}' in the OCR"))
    m = BACKREF.search(t)
    if m:
        ev.append(("backref:" + m.group(1), f"'{m.group(0)}' in the OCR"))
    if CLASSIFIED_HEAD.search(t) or len(CLASSIFIED_WORDS.findall(t)) >= 4:
        ev.append(("classifieds", "classifieds page (" + (CLASSIFIED_HEAD.search(t).group(0) if CLASSIFIED_HEAD.search(t)
                                                          else f"{len(CLASSIFIED_WORDS.findall(t))} ad heads") + ")"))
    if SPONSOR.search(t):
        ev.append(("sponsor", "the puzzle sponsor's line ('Compliments of the Penn State ...')"))
    return [(tag, " ".join(why.split())) for tag, why in ev]


LEARN_DAYS = 30


def row_runs(row):
    return tuple(len(x) for x in row.split("#") if x)


_LINES = {}


def page_lines(date, seq):
    """The page's OCR lines as the lengths of their capitalised words: a key's row reads as its words broken at
    the black squares, so it shows the row's runs of white cells."""
    k = (date, seq)
    if k not in _LINES:
        _LINES[k] = {tuple(len(x) for x in re.findall(r"[A-Z]{2,}", line))
                     for line in scan.ocr(date, seq).splitlines()} - {()}
    return _LINES[k]


def row_text(pattern, date, seq):
    """How many of the puzzle's distinct rows (with 2+ words) read, word lengths and all, as a line of the page."""
    lines = page_lines(date, seq)
    return sum(1 for r in {row_runs(x) for x in pattern} if len(r) >= 2 and r in lines)


_LEARNED = None


def learned(date, issues, i):
    """(issue offset, pages from the issue's end) -> (how many nearby matched keys were there, how many matched
    nearby), for the matched keys of puzzles within LEARN_DAYS of `date` (answer_puzzles.jsonl), patterns seen
    at least twice, the two commonest."""
    global _LEARNED
    import datetime
    if _LEARNED is None:
        pos = {d: j for j, d in enumerate(issues)}
        _LEARNED = []
        for r in jl(PUZZLES):
            k = r.get("key")
            if r["status"] == "matched" and k["issue"] in pos and r["date"] in pos:
                _LEARNED.append((datetime.date.fromisoformat(r["date"]), pos[k["issue"]] - pos[r["date"]],
                                 n_pages(k["issue"]) - k["seq"]))
    d0 = datetime.date.fromisoformat(date)
    near = [(off, fe) for d, off, fe in _LEARNED if abs((d - d0).days) <= LEARN_DAYS and d != d0 and off in EXPECTED]
    c = Counter(near)
    return {k: (n, len(near)) for k, n in c.most_common(2) if n >= 2}


def cmd_candidates(a):
    issues = scan.issue_list()
    have = {d for d in issues if n_pages(d)}
    issues = [d for d in issues if d in have]
    pz = puzzles()
    puzzle_page = defaultdict(set)
    for d, s, _ in pz:
        puzzle_page[d].add(s)
    out = []
    extras = extra_pages()
    pats = puzzle_patterns()
    for d, s, kind in pz:
        i = issues.index(d)
        nxt = issues[i + 1] if i + 1 < len(issues) else None
        text = scan.ocr(d, s)
        ptr = [int(x) for x in POINTER.findall(text)]
        c = defaultdict(lambda: [0, []])

        def add(issue, seq, pts, why):
            if issue and 1 <= seq <= n_pages(issue):
                c[(issue, seq)][0] += pts
                c[(issue, seq)][1].append(why)
        # the puzzle page itself (a key beside the puzzle: the previous puzzle's, or this one's on a stub's page)
        for n in ptr:
            add(d, n, 10, f"the puzzle page says the answers are on p. {n}")
            add(d, n - 1, 3, f"next to p. {n}, which the puzzle page names (seq can be off by one)")
            add(d, n + 1, 3, f"next to p. {n}, which the puzzle page names (seq can be off by one)")
        for issue, w in ((d, 1.0), (nxt, 1.0)):
            if not issue:
                continue
            for q in range(1, n_pages(issue) + 1):
                own = issue == d and q in puzzle_page[d]
                for tag, why in page_evidence(issue, q):
                    if tag.startswith("backref:"):
                        if issue == d and int(tag[8:]) in (s, s - 1, s + 1):
                            add(issue, q, 10, f"points back to the puzzle's page: {why}")
                    elif tag == "label" and not own:
                        add(issue, q, 8 if issue == nxt else 4, f"key heading: {why}")
                    elif tag == "classifieds" and issue == nxt:
                        add(issue, q, 5, why)
                    elif tag == "sponsor" and issue == d and not own:
                        add(issue, q, 4, why)
        # where the keys of nearby puzzles were found (matched in an earlier round): the same issue or the next,
        # so many pages from its end. Learned from the matches, not told: a paper's habit shows in its neighbours.
        for (off, from_end), (n, m) in learned(d, issues, i).items():
            issue = issues[i + off] if i + off < len(issues) else None
            if issue:
                q = n_pages(issue) - from_end
                why = (f"where nearby keys were: {n} of {m} puzzles matched within {LEARN_DAYS} days had theirs in "
                       f"{'the same' if off == 0 else 'the next'} issue, {from_end} pages from its end")
                add(issue, q, 6 + min(3, n // 3), why)
                add(issue, q - 1, 2, "next to " + why[0].lower() + why[1:])
                add(issue, q + 1, 2, "next to " + why[0].lower() + why[1:])
        # the key read as text: the puzzle's rows (word lengths = runs of white cells) among a page's OCR lines
        pat = pats.get((d, s))
        if pat:
            for issue in (d, nxt):
                if not issue:
                    continue
                sc = {q: row_text(pat, issue, q) for q in range(1, n_pages(issue) + 1)
                      if not (issue == d and q == s)}
                for q, n in sc.items():
                    if n >= 2 and n == max(sc.values()):
                        add(issue, q, 4 + min(4, n), f"{n} of the puzzle's rows read as a line of this page's OCR "
                                                     "(word lengths = the row's runs of white squares)")
        if nxt:
            for q in puzzle_page.get(nxt, ()):
                add(nxt, q, 3, "the next issue's puzzle page (1976-78 keys often sit beside the new puzzle)")
            n = n_pages(nxt)
            for q in (n, n - 1):
                if (nxt, q) not in c:
                    add(nxt, q, 1, "era prior: the next issue's last pages (classifieds run near the end)")
        ranked = sorted(c.items(), key=lambda kv: (-kv[1][0], kv[0]))
        # the issues a person browses on /answers: the next one, and the puzzle's own when the evidence points there
        browse = ([d] if any(k[0] == d and v[0] >= 4 for k, v in ranked) else []) + ([nxt] if nxt else [])
        own_best = next((v[1][0] for k, v in ranked if k[0] == d), "")
        browse_why = {d: f"the puzzle's own issue: {own_best}", **({nxt: "the next issue"} if nxt else {})}
        out.append(dict(id=pid(d, s, extras), date=d, seq=s, kind=kind, next_issue=nxt, pointer=ptr, browse=browse,
                        browse_why={k: v for k, v in browse_why.items() if k in browse},
                        candidates=[dict(issue=k[0], seq=k[1], score=v[0], why=v[1]) for k, v in ranked]))
    write_jl(CANDS, out)
    top = Counter((r["candidates"][0]["why"][0].split(":")[0][:40] if r["candidates"] else "none") for r in out)
    print(f"{len(out)} puzzles -> {CANDS}; {sum(len(r['candidates']) for r in out)} candidate pages "
          f"({len({(c['issue'], c['seq']) for r in out for c in r['candidates']})} distinct)")
    for k, v in top.most_common(8):
        print(f"  {v:4}  best candidate: {k}")


# ---------------------------------------------------------------------------------------------------------------
# 2. detect
# ---------------------------------------------------------------------------------------------------------------

def recorded_puzzle_grids():
    """grids.jsonl: (date, seq) -> the record (the main grid first, then any second grids)."""
    return {(r["date"], r["seq"]): r for r in jl(DATA / "grids.jsonl")}


def detect_page(issue, seq, rev, own_quads):
    from PIL import Image
    import numpy as np
    from xword_ocr.grid import detect_grids
    cv = canvas(issue, seq)
    W, H = cv["width"], cv["height"]
    width = round(W / 2)               # half native: a key's ~33 px cells come out ~16 px, which detect_grids reads
    p = CACHE / issue / f"seq-{seq}-w{width}.jpg"
    url = f"{scan.BASE}{cv['images'][0]['resource']['@id']}/full/{width},/0/default.jpg"
    fetched = False
    if not p.exists():
        b = scan.get(url)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.with_suffix(".tmp").write_bytes(b)
        p.with_suffix(".tmp").replace(p)
        fetched = True
    gray = np.asarray(Image.open(p).convert("L"))
    k = W / gray.shape[1]
    t = time.time()
    found = []

    def add(g, x0, y0, where):
        quad = [[round((float(x) + x0) * k), round((float(y) + y0) * k)] for x, y in g.quad]
        new = dict(rows=int(g.rows), cols=int(g.cols), pitch=round(float(g.pitch) * k, 1), quad=quad,
                   cells=["".join(r) for r in g.cells], has_letters=bool(g.has_letters), found_in=where,
                   own_puzzle=any(_overlap(quad, q) > 0.5 for q in own_quads))
        for i, old in enumerate(found):     # the same grid from two tiles (or tile and page): keep the bigger reading
            if _overlap(quad, old["quad"]) > 0.5 or _overlap(old["quad"], quad) > 0.5:
                if new["rows"] * new["cols"] > old["rows"] * old["cols"]:
                    found[i] = new
                return
        found.append(new)
    for g in detect_grids(gray, max_dim=max(gray.shape)):
        add(g, 0, 0, "page")
    # detect_grids takes the biggest lattice first and stops at the first it cannot build, at most 4 a page: on a
    # busy classifieds page a small key never gets its turn. Overlapping tiles give every small grid its own look.
    h, w = gray.shape
    for y0 in range(0, max(1, h - TILE // 2), TILE_STEP):
        for x0 in range(0, max(1, w - TILE // 2), TILE_STEP):
            tile = gray[y0:y0 + TILE, x0:x0 + TILE]
            try:
                for g in detect_grids(tile, max_dim=max(tile.shape)):
                    add(g, x0, y0, f"tile {x0},{y0}")
            except Exception:
                pass
    return dict(issue=issue, seq=seq, page=[W, H], width_used=width, scale=round(k, 3), detect_s=round(time.time() - t, 2),
                xword_ocr=rev, image=p.relative_to(DATA).as_posix(), url=url, fetched=fetched, method=METHOD,
                source=f"detect_grids on the page at {width} px and on {TILE} px tiles", grids=found)


def _bbox(q):
    xs, ys = [p[0] for p in q], [p[1] for p in q]
    return min(xs), min(ys), max(xs), max(ys)


def _overlap(q1, q2):
    a, b = _bbox(q1), _bbox(q2)
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    area = (a[2] - a[0]) * (a[3] - a[1])
    return ix * iy / area if area else 0


def from_grids_jsonl(r):
    """A puzzle page already in grids.jsonl: its grids as an answer_grids record (no fetch). The first grid is
    the page's own puzzle; the rest (the 1976-78 second grids) are key candidates."""
    gs = []
    for i, g in enumerate(r["grids"]):
        gs.append(dict(g, own_puzzle=(i == 0)))
    return dict(issue=r["date"], seq=r["seq"], page=r["page"], width_used=r.get("width_used", 2400), scale=r["scale"],
                xword_ocr=r["xword_ocr"], image=None, url=None, fetched=False,
                source="grids.jsonl (the puzzle page's grids, recorded by grids.py)", grids=gs)


def _xo_rev():
    import subprocess
    import xword_ocr
    try:
        return subprocess.run(["git", "-C", str(Path(xword_ocr.__file__).parent), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def detect(rank, workers, pause, limit=None, shortlist=False):
    """Look at candidate pages of rank <= `rank` for every puzzle that has no settled key yet; with
    `shortlist`, at every candidate page with real evidence (score >= SHORTLIST), the pages /answers lists first,
    so that every grid on them is recorded and the sheet can show the keys themselves."""
    rev = _xo_rev()
    cands = jl(CANDS)
    done = {(r["issue"], r["seq"]) for r in jl(GRIDS) if r.get("method") == METHOD or r["image"] is None}
    rec = recorded_puzzle_grids()
    settled = {r["id"] for r in jl(PUZZLES) if r["status"] == "matched"} | set(person_decisions())
    todo, puzzle_pages_extra, seen = [], [], set()
    # extra puzzle pages (the 1978-01-20 stub) are not in grids.jsonl: detect their grid as a puzzle pattern
    for d, s, kind in puzzles():
        if (d, s) not in rec and (d, s) not in done:
            puzzle_pages_extra.append((d, s))
    for r in cands:
        if r["id"] in settled:
            continue
        pages = [(c["issue"], c["seq"]) for c in (
            [c for c in r["candidates"] if c["score"] >= SHORTLIST] if shortlist else r["candidates"][:rank])]
        for k in pages:
            if k not in done and k not in seen:
                seen.add(k)
                todo.append(k)
    todo = puzzle_pages_extra + todo
    if limit:
        todo = todo[:limit]
    new = []
    for k in list(todo):
        if k in rec:   # a puzzle page: reuse grids.jsonl
            new.append(from_grids_jsonl(rec[k]))
            todo.remove(k)
    print(f"rank <= {rank}: {len(todo)} pages to fetch and detect, {len(new)} puzzle pages reused from grids.jsonl", flush=True)
    t0, nbytes = time.time(), 0

    def work(k):
        own = [g["quad"] for g in rec.get(k, {}).get("grids", [])[:1]]
        r = detect_page(k[0], k[1], rev, own)
        if r["fetched"] and pause:
            time.sleep(pause)
        return r
    with open(GRIDS, "a", encoding="utf8") as f:
        for r in new:
            f.write(json.dumps(r) + "\n")
        with cf.ThreadPoolExecutor(workers) as ex:
            for i, r in enumerate(ex.map(work, todo), 1):
                if (r["issue"], r["seq"]) in puzzle_pages_extra:
                    r["source"] += " (an extra puzzle page: its grid is a puzzle pattern)"
                    for g in r["grids"][:1]:
                        g["own_puzzle"] = True
                f.write(json.dumps(r) + "\n")
                f.flush()
                nbytes += (DATA / r["image"]).stat().st_size if r["fetched"] else 0
                if i % 50 == 0 or i == len(todo):
                    print(f"  {i}/{len(todo)}  {nbytes / 1e6:.0f} MB fetched  {(time.time() - t0) / 60:.1f} min", flush=True)


# ---------------------------------------------------------------------------------------------------------------
# 3. match: region hashes
# ---------------------------------------------------------------------------------------------------------------

def _cells(rows_of_str):
    return [[ch == "#" for ch in row] for row in rows_of_str]


def windows(cells, k=K):
    R, C = len(cells), len(cells[0]) if cells else 0
    for r in range(R - k + 1):
        for c in range(C - k + 1):
            yield r, c, "".join("#" if cells[r + i][c + j] else "." for i in range(k) for j in range(k))


class RegionIndex:
    """Every puzzle's black/white pattern cut into k x k windows; a grid's windows vote for (puzzle, offset)."""

    def __init__(self, patterns, k=K):
        self.k, self.patterns = k, patterns          # id -> list of rows ("#" / ".")
        self.hits = defaultdict(list)                # window -> [(id, r, c)]
        df = defaultdict(set)
        for pid, rows in patterns.items():
            for r, c, h in windows(_cells(rows), k):
                self.hits[h].append((pid, r, c))
                df[h].add(pid)
        n = len(patterns)
        self.weight = {h: math.log((n + 1) / (len(s) + 0.5)) for h, s in df.items()}

    def vote(self, rows):
        votes = defaultdict(float)
        total = 0.0
        for r, c, h in windows(_cells(rows), self.k):
            w = self.weight.get(h, math.log(len(self.patterns) + 1))
            total += w
            for pid, r0, c0 in self.hits.get(h, ()):
                votes[(pid, r0 - r, c0 - c)] += w
        return votes, total

    def distance(self, rows, pid, dr, dc):
        """Hamming distance over the overlap of the grid placed at (dr, dc) in the puzzle, and the overlap's size."""
        P = self.patterns[pid]
        d = n = 0
        for r, row in enumerate(rows):
            for c, ch in enumerate(row):
                pr, pc = r + dr, c + dc
                if 0 <= pr < len(P) and 0 <= pc < len(P[0]):
                    n += 1
                    d += (ch == "#") != (P[pr][pc] == "#")
        return d, n


def puzzle_patterns():
    """id (date) -> the main grid's rows, from grids.jsonl plus extra puzzle pages detected in answer_grids.jsonl."""
    pats = {}
    for r in jl(DATA / "grids.jsonl"):
        if r["grids"]:
            pats[(r["date"], r["seq"])] = r["grids"][0]["cells"]
    extra = {(d, s) for d, s, _ in puzzles()} - set(pats)
    for r in jl(GRIDS):
        k = (r["issue"], r["seq"])
        if k in extra and r["grids"]:
            pats[k] = r["grids"][0]["cells"]
    return pats


EXPECTED = (0, 1)   # a key is printed in the puzzle's own issue (1976-77) or the next one; anything else is shown


def score_grid(index, rows, issue, dates_after, prior=None, top=12):
    """The region-hash verdict for one detected grid.

    Votes shortlist the puzzles (and where the grid sits in each); the cell distance decides. Patterns that are
    the same, or nearly (a puzzle maker reuses grids: 190 of the 860 Collegian patterns are shared exactly), can't
    be told apart by the key alone, so among the patterns within 2 cells of the best, the puzzle printed in the
    key's own issue or the one before wins (and between those two, the one whose candidate list named this page
    with more text evidence: `prior(pid)`), and the note says which patterns it was chosen over."""
    votes, total = index.vote(rows)
    if not votes or not total:
        return dict(verdict="no-vote")
    best_by_pid = {}
    for (pid, dr, dc), v in votes.items():
        if pid not in best_by_pid or v > best_by_pid[pid][0]:
            best_by_pid[pid] = (v, dr, dc)
    ranked = sorted(best_by_pid.items(), key=lambda kv: -kv[1][0])[:top]
    R, C = len(rows), len(rows[0])
    res = []
    for pid, (v, dr, dc) in ranked:
        d, n = index.distance(rows, pid, dr, dc)
        P = index.patterns[pid]
        res.append(dict(date=pid[0], seq=pid[1], score=round(v / total, 3), offset=[dr, dc], distance=d, overlap=n,
                        same_size=(len(P), len(P[0])) == (R, C), issues_after=dates_after(pid[0], issue)))
    limit = max(3, (R * C) // 40)
    whole = sorted([x for x in res if x["same_size"] and x["offset"] == [0, 0] and x["distance"] <= limit],
                   key=lambda x: (x["distance"], -x["score"]))
    if whole:
        d0 = whole[0]["distance"]
        near = [x for x in whole if x["distance"] <= d0 + 2]
        exp = [x for x in near if x["issues_after"] in EXPECTED]
        if exp:
            rank = lambda x: (x["distance"], -(prior((x["date"], x["seq"])) if prior else 0))  # noqa: E731
            w = min(exp, key=lambda x: (*rank(x), x["issues_after"]))
            twins = [x for x in exp if rank(x) == rank(w) and x["issues_after"] != w["issues_after"]]
            if twins:   # the same pattern in the key's own issue and the one before, and nothing to tell them apart
                return dict(verdict="unclear", best=w, runner_up=twins[0], close=[x for x in near if x is not w],
                            limit=limit, tie="the same pattern was printed in the key's issue and the one before: "
                                             + ", ".join(x["date"] for x in [w] + twins))
        elif len(near) == 1:
            w = near[0]
        else:
            w = None
        if w is not None:
            others = [x for x in near if x is not w]
            by_date = [x for x in others if x["distance"] <= w["distance"]]
            note = ("close patterns " + ", ".join(f"{x['date']} ({x['distance']} differ)" for x in others)
                    + ("; chosen by date (expected in the same or the next issue)" if by_date else
                       f"; this one is nearest ({w['distance']} differ)")) if others else ""
            rest = [x for x in res if x is not w and x not in others]
            ru = min(rest, key=lambda x: (x["distance"] if x["same_size"] else 999, -x["score"])) if rest else None
            return dict(verdict="matched", best=w, runner_up=ru, close=others, limit=limit, tie=note)
        return dict(verdict="unclear", best=near[0], runner_up=near[1], close=near[1:], limit=limit,
                    tie="patterns within 2 cells of each other, none printed the issue before: " + ", ".join(x["date"] for x in near))
    w = max(res, key=lambda x: x["score"])
    ru = next((x for x in res if x is not w), None)
    if w["score"] >= 0.3 and w["distance"] <= max(limit, w["overlap"] // 20):
        return dict(verdict="partial" if not (w["same_size"] and w["offset"] == [0, 0]) else "unclear",
                    best=w, runner_up=ru, limit=limit, tie="")
    return dict(verdict="no-match", best=w, runner_up=ru, limit=limit, tie="")


def cmd_match(a):
    t0 = time.time()
    pats = puzzle_patterns()
    index = RegionIndex(pats)
    issues = [d for d in scan.issue_list() if n_pages(d)]
    pos = {d: i for i, d in enumerate(issues)}

    def after(pdate, issue):
        return pos[issue] - pos[pdate] if pdate in pos and issue in pos else None
    prior = defaultdict(dict)     # candidate page -> {puzzle: text evidence score}
    for r in jl(CANDS):
        for c in r["candidates"]:
            prior[(c["issue"], c["seq"])][(r["date"], r["seq"])] = c["score"]
    grids_seen = {}
    for r in jl(GRIDS):
        grids_seen[(r["issue"], r["seq"])] = r     # last record per page wins
    matches = []
    for (issue, seq), r in sorted(grids_seen.items()):
        for gi, g in enumerate(r["grids"]):
            if g.get("own_puzzle") or min(g["rows"], g["cols"]) < K:
                continue
            pr = (lambda p, k=(issue, seq): prior.get(k, {}).get(p, 0))
            m = score_grid(index, g["cells"], issue, after, prior=pr)
            # a key printed upside down (Oct 1976) has the same black squares as its puzzle only if the grid is
            # symmetric: score it turned round too, and keep the better reading
            turned = ["".join(reversed(row)) for row in reversed(g["cells"])]
            if turned != g["cells"]:
                m2 = score_grid(index, turned, issue, after, prior=pr)
                rank = {"matched": 0, "unclear": 1, "partial": 2, "no-match": 3, "no-vote": 4}
                k1 = (rank[m["verdict"]], (m.get("best") or {}).get("distance", 999))
                k2 = (rank[m2["verdict"]], (m2.get("best") or {}).get("distance", 999))
                if k2 < k1:
                    m = dict(m2, turned=True)
            matches.append(dict(issue=issue, seq=seq, grid=gi, rows=g["rows"], cols=g["cols"], quad=g["quad"],
                                has_letters=g["has_letters"], source=r["source"], **m))
    # Identical patterns: which puzzle a shared grid answers is the paper's habit for that stretch of the run
    # (same issue, next issue), learned from the keys whose pattern is unique; only then the text evidence.
    # (1977-04-25 p16, "answers to page 4 puzzle", has the grid of 04-21, 04-22, 04-25 and 04-26: it is 04-25's.)
    import datetime

    def twins(m):
        return [x for x in m.get("close") or [] if x["distance"] <= m["best"]["distance"]]
    sure = [(datetime.date.fromisoformat(m["best"]["date"]), m["best"]["issues_after"])
            for m in matches if m["verdict"] == "matched" and not twins(m)]

    def habit(date):
        d0 = datetime.date.fromisoformat(date)
        for days in (LEARN_DAYS, 3 * LEARN_DAYS):
            c = Counter(off for d, off in sure if abs((d - d0).days) <= days)
            n = sum(c.values())
            if n >= 5:
                off, k = c.most_common(1)[0]
                return (off, k, n, days) if k >= 0.7 * n else None
        return None
    for m in matches:
        if m["verdict"] not in ("matched", "unclear") or not twins(m):
            continue
        tied = [m["best"]] + twins(m)
        fit = [x for x in tied if (h := habit(x["date"])) and x["issues_after"] == h[0]]
        if len(fit) == 1 and fit[0] is not m["best"] or (len(fit) == 1 and m["verdict"] == "unclear"):
            w = fit[0]
            off, k, n, days = habit(w["date"])
            m["close"] = [x for x in tied if x is not w] + [x for x in m.get("close") or [] if x not in tied]
            m["best"], m["verdict"] = w, "matched"
            m["tie"] = (f"the same grid as {', '.join(x['date'] for x in tied if x is not w)}; chosen by the paper's habit: "
                        f"{k} of {n} keys with a unique pattern within {days} days are {off} issue(s) after their puzzle")
    write_jl(MATCHES, matches)
    # per puzzle: the key it got, or why not
    by_puzzle = defaultdict(list)
    for m in matches:
        if m["verdict"] in ("matched", "unclear", "partial"):
            by_puzzle[(m["best"]["date"], m["best"]["seq"])].append(m)
    cands = {(r["date"], r["seq"]): r for r in jl(CANDS)}
    looked = set(grids_seen)
    extras = extra_pages()
    out = []
    for d, s, kind in puzzles():
        ms = by_puzzle.get((d, s), [])
        ok = sorted([m for m in ms if m["verdict"] == "matched"],
                    key=lambda m: (m["best"]["issues_after"] not in (0, 1), m["best"]["distance"], -m["best"]["score"]))
        c = cands.get((d, s), {}).get("candidates", [])
        rec = dict(id=pid(d, s, extras), date=d, seq=s, kind=kind, has_pattern=(d, s) in pats,
                   candidates_looked=[[x["issue"], x["seq"]] for x in c if (x["issue"], x["seq"]) in looked],
                   candidates_left=len([x for x in c if (x["issue"], x["seq"]) not in looked]))
        if ok:
            k = ok[0]
            rec.update(status="matched" if k["best"]["issues_after"] in EXPECTED else "odd-distance", key=dict(issue=k["issue"], seq=k["seq"], grid=k["grid"], quad=k["quad"],
                                                  rows=k["rows"], cols=k["cols"], score=k["best"]["score"],
                                                  distance=k["best"]["distance"], issues_after=k["best"]["issues_after"],
                                                  runner_up=k["runner_up"], tie=k["tie"], source=k["source"]),
                       expected=k["best"]["issues_after"] in (0, 1), other_keys=len(ok) - 1)
        elif ms:
            rec.update(status="unclear", near=[dict(issue=m["issue"], seq=m["seq"], grid=m["grid"], verdict=m["verdict"],
                                                    best=m["best"], runner_up=m["runner_up"]) for m in ms[:4]])
        elif (d, s) not in pats:
            rec.update(status="no-pattern", why="no grid recorded for this puzzle (grids.jsonl), so nothing to match a key to")
        else:
            rec.update(status="no-key-found")
        out.append(rec)
    # The paper's habit, learned from the neighbours: where at least 70% of the keys matched within LEARN_DAYS
    # sit at one distance (same issue, next issue), a key at the other distance goes to a person (odd-distance).
    import datetime
    got = [(datetime.date.fromisoformat(r["date"]), r["key"]["issues_after"], r["id"]) for r in out if r["status"] == "matched"]
    for r in out:
        if r["status"] != "matched":
            continue
        d0 = datetime.date.fromisoformat(r["date"])
        for days in (LEARN_DAYS, 3 * LEARN_DAYS):     # a thin month (end of term): look a little wider
            c = Counter(off for d, off, i in got if i != r["id"] and abs((d - d0).days) <= days)
            n = sum(c.values())
            if n >= 5:
                break
        if n >= 5:
            off, k = c.most_common(1)[0]
            if off != r["key"]["issues_after"] and k >= 0.7 * n:
                r["status"] = "odd-distance"
                r["odd"] = (f"{k} of {n} keys matched within {days} days are {off} issue(s) after their puzzle; "
                            f"this one is {r['key']['issues_after']}")
    write_jl(PUZZLES, out)
    c = Counter(r["status"] for r in out)
    v = Counter(m["verdict"] for m in matches)
    print(f"{len(matches)} detected grids scored in {time.time() - t0:.1f}s ({len(pats)} puzzle patterns, "
          f"{len(index.hits)} distinct {K}x{K} windows): {dict(v)}")
    print(f"puzzles: {dict(c)}")


# ---------------------------------------------------------------------------------------------------------------
# person decisions, save
# ---------------------------------------------------------------------------------------------------------------

def person_decisions():
    return {r["id"]: r for r in jl(DECISIONS)}


def key_for(rec, dec):
    """The key to save for one puzzle: a person's decision wins over the matcher. Returns dict or None."""
    p = dec.get(rec["id"])
    if p:
        if p["verdict"] != "key":      # none, unsure, or "not this puzzle's key" (rejected): nothing to save
            return None
        return dict(issue=p["issue"], seq=int(p["key_seq"]), quad=p.get("quad"), box=p.get("box"), grid=p.get("grid"),
                    how=(f"picked by {p['by']} on /answers ({p['at']}): " +
                         ("a grid xword-ocr's detect_grids found (answer_grids.jsonl)" if p.get("quad") else "a box drawn by hand")))
    if rec.get("status") == "matched":     # an odd-distance match waits for a person's yes on /answers
        k = rec["key"]
        ru = k["runner_up"]
        how = (f"grid found by xword-ocr detect_grids (answer_grids.jsonl: {k['source']}), matched by region hashes "
               f"(answer_matches.jsonl: score {k['score']}, {k['distance']} cells differ"
               + (f"; runner-up {ru['date']} score {ru['score']}, {ru['distance']} differ" if ru else "; no runner-up")
               + (f"; {k['tie']}" if k["tie"] else "") + ")")
        return dict(issue=k["issue"], seq=k["seq"], quad=k["quad"], box=None, grid=k["grid"], how=how)
    return None


def place_piece(cells, P):
    """Where a detected grid sits in the puzzle's pattern: (dr, dc, cells differing, cells compared) for the offset
    that fits best with at least 60% of the smaller grid overlapping; None if nothing fits within 10%."""
    r, c, R, C = len(cells), len(cells[0]), len(P), len(P[0])
    need = 0.6 * min(r * c, R * C)
    best = None
    for dr in range(-(r - 1), R):
        for dc in range(-(c - 1), C):
            d = n = 0
            for i in range(max(0, -dr), min(r, R - dr)):
                for j in range(max(0, -dc), min(c, C - dc)):
                    n += 1
                    d += (cells[i][j] == "#") != (P[i + dr][j + dc] == "#")
            if n >= need and (best is None or d / n < best[2] / best[3]):
                best = (dr, dc, d, n)
    return best if best and best[2] <= 0.1 * best[3] else None


def full_quad(quad, rows, cols, dr, dc, R, C):
    """The puzzle-sized grid's corners from a detected piece's corners (TL, TR, BR, BL): the piece's lattice
    (affine, from TL, TR and BL) carried out to the puzzle's rows and columns."""
    (x0, y0), (x1, y1), _, (x3, y3) = quad
    ux, uy = (x1 - x0) / cols, (y1 - y0) / cols
    vx, vy = (x3 - x0) / rows, (y3 - y0) / rows

    def at(u, v):
        return [round(x0 + u * ux + v * vx), round(y0 + u * uy + v * vy)]
    return [at(-dc, -dr), at(C - dc, -dr), at(C - dc, R - dr), at(-dc, R - dr)]


def extend_key(k, rec, grids, pats):
    """A key whose detected grid is only part of it (12x15 of a 15x15, a corner): the crop is carried out to the
    puzzle's full size, placed where the piece fits the puzzle's pattern. Returns (quad, note) or (None, '')."""
    if k.get("box") or k.get("grid") is None or (rec["date"], rec["seq"]) not in pats:
        return None, ""
    g = grids.get((k["issue"], k["seq"]))
    if not g or k["grid"] >= len(g["grids"]):
        return None, ""
    x = g["grids"][k["grid"]]
    P = pats[(rec["date"], rec["seq"])]
    R, C = len(P), len(P[0])
    if (x["rows"], x["cols"]) == (R, C):
        return None, ""
    fit = place_piece(x["cells"], P)
    if not fit:
        return None, ""
    dr, dc, d, n = fit
    return (full_quad(x["quad"], x["rows"], x["cols"], dr, dc, R, C),
            f"extended from the detected {x['rows']}x{x['cols']} piece to the puzzle's {R}x{C} (the piece fits it at "
            f"offset ({dr}, {dc}) in rows and columns, {d} of {n} cells differing)")


def key_region(k, W, H):
    if k.get("box"):
        x, y, w, h = k["box"]
        px, py = round(0.05 * w), round(0.05 * h)
    else:
        x0, y0, x1, y1 = _bbox(k["quad"])
        x, y, w, h = x0, y0, x1 - x0, y1 - y0
        px, py = round(KEY_PAD * w), round(KEY_PAD * h)
    x0, y0 = max(0, x - px), max(0, y - py)
    return [x0, y0, min(W, x + w + px) - x0, min(H, y + h + py) - y0]


def cmd_save(a):
    dec = person_decisions()
    grids = {(r["issue"], r["seq"]): r for r in jl(GRIDS)}
    pats = puzzle_patterns()
    before = {r["id"]: r for r in jl(KEYS)}
    ori = {r["id"]: r for r in jl(DATA / "key_orientation.jsonl")}     # a person's "printed upside down" (/crops)
    keys, extended = [], 0
    for rec in jl(PUZZLES):
        k = key_for(rec, dec)
        if not k:
            continue
        q, note = extend_key(k, rec, grids, pats)
        if q:
            k = dict(k, quad=q, how=k["how"] + "; " + note)
            extended += 1
        cv = canvas(k["issue"], k["seq"])
        W, H = cv["width"], cv["height"]
        region = key_region(k, W, H)
        iid = cv["images"][0]["resource"]["@id"]
        keys.append(dict(id=rec["id"], date=rec["date"], puzzle_seq=rec["seq"], issue=k["issue"], seq=k["seq"], region=region,
                         file=f"pages/{k['issue']}/seq-{k['seq']}-key-{rec['id']}.jpg",
                         page_file=f"pages/{k['issue']}/seq-{k['seq']}-page.jpg",
                         url=f"{scan.BASE}{iid}/{','.join(map(str, region))}/full/0/default.jpg",
                         page_url=f"{scan.BASE}{iid}/full/,{scan.PAGE_H}/0/default.jpg",
                         how=k["how"] + ("; the key was printed upside down: saved turned round (a person, /crops)"
                                          if ori.get(rec["id"], {}).get("upside_down") else ""),
                         turned=bool(ori.get(rec["id"], {}).get("upside_down")), page_size=[W, H]))
    jobs = []
    for k in keys:
        old = before.get(k["id"])
        changed = old is not None and (old["region"] != k["region"] or old["file"] != k["file"]
                                       or bool(old.get("turned")) != k["turned"])
        if not (DATA / k["file"]).exists() or changed:
            jobs.append((DATA / k["file"], k["url"]))
        if not (DATA / k["page_file"]).exists() and (DATA / k["page_file"], k["page_url"]) not in jobs:
            jobs.append((DATA / k["page_file"], k["page_url"]))
    print(f"{len(keys)} keys ({extended} extended from a detected piece to the puzzle's size); {len(jobs)} images to fetch", flush=True)
    t0, nb = time.time(), 0

    def fetch(job):
        path, url = job
        b = scan.get(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.with_suffix(".tmp").write_bytes(b)
        path.with_suffix(".tmp").replace(path)
        time.sleep(a.pause)
        return path, url, len(b)
    with cf.ThreadPoolExecutor(a.workers) as ex:
        for i, (path, url, n) in enumerate(ex.map(fetch, jobs), 1):
            nb += n
            with _lock, open(DATA / "pages_fetch.jsonl", "a", encoding="utf8") as f:
                f.write(json.dumps(dict(file=path.relative_to(DATA).as_posix(), url=url, bytes=n, result="answers.py save",
                                        at=time.strftime("%Y-%m-%dT%H:%M:%S"))) + "\n")
            if i % 50 == 0 or i == len(jobs):
                print(f"  {i}/{len(jobs)}  {nb / 1e6:.0f} MB  {(time.time() - t0) / 60:.1f} min", flush=True)
    # a key printed upside down is saved turned round (docs/sources.md: images the right way up); the archive's
    # url in pages.tsv still gives the page as printed
    from PIL import Image
    for k in keys:
        if k["turned"] and (DATA / k["file"]).exists():
            old = before.get(k["id"])
            fresh = any(j[0] == DATA / k["file"] for j in jobs)
            if fresh or not (old and old.get("turned")):
                with Image.open(DATA / k["file"]) as im:
                    turned = im.rotate(180)
                turned.save(DATA / k["file"], quality=92)
    write_jl(KEYS, keys)
    scan.write_pages_tsv()


def cmd_run(a):
    """Rounds: candidates (re-learned from the keys matched so far), detect the next rank, match."""
    global _LEARNED
    for rank in range(1, a.max_rank + 1):
        _LEARNED = None
        cmd_candidates(a)
        detect(rank, a.workers, a.pause)
        cmd_match(a)


def cmd_report(a):
    rows = jl(PUZZLES)
    dec = person_decisions()
    c = Counter(r["status"] for r in rows)
    print("puzzles:", dict(c), "| person decisions:", dict(Counter(r["verdict"] for r in dec.values())))
    ia = Counter(r["key"]["issues_after"] for r in rows if r["status"] == "matched")
    print("matched keys, issues after the puzzle:", sorted(ia.items(), key=lambda kv: (kv[0] is None, kv[0])))
    by_year = Counter((r["date"][:4], r["status"]) for r in rows)
    for y in sorted({k[0] for k in by_year}):
        print(" ", y, {s: n for (yy, s), n in by_year.items() if yy == y})
    sc = sorted(r["key"]["score"] for r in rows if r["status"] == "matched")
    if sc:
        print(f"winner score: min {sc[0]} median {sc[len(sc) // 2]}; distance: "
              f"{dict(Counter(r['key']['distance'] for r in rows if r['status'] == 'matched'))}")
        ru = [r["key"]["runner_up"]["score"] / r["key"]["score"] for r in rows if r["status"] == "matched" and r["key"]["runner_up"]]
        if ru:
            ru.sort()
            print(f"runner-up / winner score: median {ru[len(ru) // 2]:.2f}, max {ru[-1]:.2f}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("candidates").set_defaults(fn=cmd_candidates)
    q = sub.add_parser("detect")
    q.add_argument("--rank", type=int, default=1)
    q.add_argument("--shortlist", action="store_true", help="every candidate page with real evidence (the pages /answers lists first)")
    q.add_argument("--limit", type=int)
    q.add_argument("--workers", type=int, default=3)
    q.add_argument("--pause", type=float, default=0.5)
    q.set_defaults(fn=lambda a: detect(a.rank, a.workers, a.pause, a.limit, a.shortlist))
    sub.add_parser("match").set_defaults(fn=cmd_match)
    q = sub.add_parser("run", help="detect rank 1..N, matching after each round")
    q.add_argument("--max-rank", type=int, default=3)
    q.add_argument("--workers", type=int, default=3)
    q.add_argument("--pause", type=float, default=0.5)
    q.set_defaults(fn=cmd_run)
    q = sub.add_parser("save")
    q.add_argument("--workers", type=int, default=3)
    q.add_argument("--pause", type=float, default=0.5)
    q.set_defaults(fn=cmd_save)
    sub.add_parser("report").set_defaults(fn=cmd_report)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
