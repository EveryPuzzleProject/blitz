"""The key-squares page's flag list: the answer-key squares worth a person's glance.

A person checks each one on /review/squares/ (Keep, Change, or type a letter), with a crop of the
printed key beside the answers and clues through the square. Flags come from:

- the OCR: letters it was unsure of (A left out: hand-lettered A's are flagged far too often, and
  are almost always right), where the xd still has the OCR's letter, in keys no person has read
  through yet;
- the word check: an answer of 4+ letters that isn't a known crossword answer (counted from gxd's
  .xd files, the publication's own left out) but becomes one by changing one easily confused letter
  (I/T, D/O, S/E, C/G, ...).

Every publication has its own wordplay (Judge printed EIUGE, TGA, GNIT and ENTAN on purpose), so
the check learns from the record instead of a hand-kept list: an answer through a square a person
confirmed is a known answer for that publication, and a square a person has corrected or
confirmed isn't flagged again.

`build` reads a folder of packets (task-packets --current-review: answers.png, ocr.json) and the
publication's repo (xd/, fixes/corrections.jsonl), and writes key-squares.json in the folder;
`blitz site-publish` puts it on the site.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from .work import Stop

# Letters the OCR (or a printer) easily takes for one another: a suggestion changes one of these.
# Hand-lettered keys add their own: Judge's R came out as Z or G, M as S, B as E, I as R, P as D
# and S as T (found in its keys in gxd, 2026-10-12), so those pairs go both ways too.
CONFUSED = {"I": "TELJR", "T": "ILS", "D": "OP", "O": "DQC", "S": "EMT", "E": "SFCB", "C": "EGO",
            "G": "CR", "L": "IT", "F": "EP", "P": "FD", "H": "N", "N": "H", "R": "BZGI", "B": "RE",
            "U": "V", "V": "U", "Z": "R", "M": "S"}
MIN_LEN = 4        # shorter answers are too often abbreviations and initials
RARE = 2           # an answer used fewer times than this in gxd is "not a known answer"
COMMON = 20        # ...and a suggestion must be used at least this often
SKIP_UNSURE = "A"  # the OCR's unsure letters not worth a card (hand-lettered A's)
WINDOW = 7         # the crop shows this many squares across and down, the flagged one near the middle
PAGE = "key-squares"
PERSON = lambda by: not str(by or "").startswith(("agent", "Claude"))


def parse_xd(text: str) -> dict:
    """The parts of an xd file the cards need: headers, the grid rows, and the clues
    as [(label, clue, answer)] in file order."""
    parts = text.replace("\r\n", "\n").split("\n\n\n")
    head = {}
    for line in parts[0].splitlines():
        k, sep, v = line.partition(": ")
        if sep:
            head[k.strip()] = v.strip()
    grid = [r for r in parts[1].split("\n") if r.strip()] if len(parts) > 1 else []
    clues = []
    for m in re.finditer(r"^([AD]\d+)\. (.*) ~ (\S*)\s*$", "\n\n\n".join(parts[2:]), re.M):
        clues.append((m[1], m[2], m[3]))
    return {"head": head, "grid": grid, "clues": clues}


def entries(grid: list[str]) -> list[tuple[str, list[tuple[int, int]]]]:
    """Every answer's squares, in the usual numbering: [("A1", [(r, c), ...]), ...]."""
    R, C = len(grid), max((len(r) for r in grid), default=0)
    blk = lambda r, c: r < 0 or c < 0 or r >= R or c >= len(grid[r]) or grid[r][c] in "#_"
    out, n = [], 0
    for r in range(R):
        for c in range(C):
            if blk(r, c):
                continue
            a = blk(r, c - 1) and not blk(r, c + 1)
            d = blk(r - 1, c) and not blk(r + 1, c)
            if a or d:
                n += 1
            if a:
                cells, cc = [], c
                while not blk(r, cc):
                    cells.append((r, cc))
                    cc += 1
                out.append((f"A{n}", cells))
            if d:
                cells, rr = [], r
                while not blk(rr, c):
                    cells.append((rr, c))
                    rr += 1
                out.append((f"D{n}", cells))
    return out


def label_clues(xd: dict) -> tuple[dict[str, tuple[list, str, str]], list[str]]:
    """{label: (squares, answer, clue)}, using the xd's own labels and clues. They're paired with the
    grid's answers in order, direction by direction, so a puzzle numbered its own way (two grids
    stacked, a skipped number) still lines up; where the answers don't match, the grid's numbering
    is used without clues, with a warning."""
    grid = xd["grid"]
    word = lambda cells: "".join(grid[r][c] for r, c in cells).upper()
    out, warn = {}, []
    for d in "AD":
        mine = [(l, cells) for l, cells in entries(grid) if l[0] == d]
        theirs = [c for c in xd["clues"] if c[0][0] == d]
        if [word(cells) for _, cells in mine] == [a.upper() for _, _, a in theirs]:
            for (_, cells), (label, clue, _) in zip(mine, theirs):
                out[label] = (cells, word(cells), clue)
        else:
            warn.append(f"the {'Across' if d == 'A' else 'Down'} answers don't line up with the grid: no clues shown")
            for label, cells in mine:
                out[label] = (cells, word(cells), "")
    return out, warn


# ---- the word list ----

def answer_counts(gxd: Path, exclude_pub: str, cache: Path | None = None) -> Counter:
    """How often each answer appears in gxd's .xd files, less the publication's own (so its
    misreadings don't vouch for themselves). Cached per publication until gxd's commit changes
    (a gxd that isn't a git checkout is counted every time)."""
    import subprocess

    if not gxd.is_dir():
        raise Stop(f"No gxd checkout at {gxd}: give it with --gxd (the word check counts its answers).")
    try:
        head = subprocess.run(["git", "-C", str(gxd), "rev-parse", "HEAD"], capture_output=True, text=True,
                              timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        head = ""
    cache = cache or Path.home() / ".cache" / "blitz" / f"gxd-answers-{exclude_pub}.json"
    stamp = f"{gxd.resolve()}|{head}"
    if head and cache.exists():
        try:
            c = json.loads(cache.read_text(encoding="utf-8"))
            if c.get("stamp") == stamp:
                return Counter(c["counts"])
        except (OSError, ValueError):
            pass
    ans = re.compile(r" ~ ([A-Z]+)\s*$", re.M)
    own = re.compile(rf"{re.escape(exclude_pub)}\d")
    counts, n = Counter(), 0
    for f in gxd.rglob("*.xd"):
        if not own.match(f.name):
            counts.update(ans.findall(f.read_text(encoding="utf-8", errors="replace")))
            n += 1
    if not n:
        raise Stop(f"No .xd files under {gxd}: give the gxd checkout with --gxd.")
    if head:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"stamp": stamp, "files": n, "counts": counts}), encoding="utf-8")
    return counts


def suggest(answer: str, counts: Counter, known: set[str]) -> tuple[int, str, int] | None:
    """(the square's index, the suggested answer, how often gxd has it) if the answer isn't a known
    one but one easily-confused letter away from a common one; else None."""
    if len(answer) < MIN_LEN or not answer.isalpha() or answer in known or counts[answer] >= RARE:
        return None
    best = None
    for i, ch in enumerate(answer):
        for alt in CONFUSED.get(ch, ""):
            v = answer[:i] + alt + answer[i + 1:]
            if counts[v] >= COMMON and (best is None or counts[v] > best[2]):
                best = (i, v, counts[v])
    return best


# ---- the record: what people have already checked ----

def ledger(repo: Path) -> list[dict]:
    path = repo / "fixes" / "corrections.jsonl"
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def learned(records: list[dict], xds: dict[str, dict]) -> tuple[dict[str, set[str]], set[str], set[str]]:
    """What people have settled: per puzzle, the key squares a person corrected or confirmed; the
    answers through a square a person confirmed, as the publication's own known answers; and the
    puzzles whose whole key a person has read (their latest verdict is looks-right, or they
    confirmed check:answers), where the OCR's unsure letters were in front of them already.
    (The word check still looks at those: it found misread letters in puzzles marked done.)"""
    checked: dict[str, set[str]] = {}
    known: set[str] = set()
    verdict: dict[str, str] = {}
    read: set[str] = set()
    for r in records:
        if not PERSON(r.get("by")):
            continue
        if r.get("item") == "puzzle" and r.get("action") in ("looks-right", "needs-work"):
            verdict[r["xdid"]] = r["action"]
        if r.get("item") == "check:answers" and r.get("action") == "confirm":
            read.add(r["xdid"])
        if not str(r.get("item", "")).startswith("cell:"):
            continue
        sq = r["item"][5:]
        checked.setdefault(r["xdid"], set()).add(sq)
        if r.get("action") == "confirm" and r["xdid"] in xds:
            m = re.fullmatch(r"r(\d+)c(\d+)", sq)
            rc = (int(m[1]) - 1, int(m[2]) - 1) if m else None
            for cells, answer, _ in xds[r["xdid"]]["labels"].values():
                if rc in cells:
                    known.add(answer)
    return checked, known, read | {x for x, v in verdict.items() if v == "looks-right"}


def built_from(repo: Path) -> str:
    """The publication repo's commit the list was made from, "+changes" if xd/ or fixes/ differ from it."""
    import subprocess

    git = lambda *a: subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, timeout=60).stdout.strip()
    try:
        head = git("rev-parse", "--short=7", "HEAD")
        dirty = git("status", "--porcelain", "--", "xd", "fixes")
    except (OSError, subprocess.SubprocessError):
        return ""
    return head + ("+changes" if dirty else "") if head else ""


# ---- the cards ----

def crop(size: tuple[int, int], rows: int, cols: int, r: int, c: int, cells: list[tuple[int, int]]) -> dict:
    """Where the card's crop of answers.png is, in the image's pixels: the window {x, y, w, h} around
    the square, the square's box, and the answer's squares to tint. The page draws it with CSS."""
    W, H = size
    cw, ch = W / cols, H / rows
    n, m = min(WINDOW, cols), min(WINDOW, rows)
    c0 = max(0, min(c - WINDOW // 2, cols - n))
    r0 = max(0, min(r - WINDOW // 2, rows - m))
    box = lambda rr, cc: [round(cc * cw), round(rr * ch), round(cw), round(ch)]
    return {"size": [W, H], "x": round(c0 * cw), "y": round(r0 * ch), "w": round(n * cw), "h": round(m * ch),
            "box": box(r, c), "tint": [box(rr, cc) for rr, cc in cells if r0 <= rr < r0 + m and c0 <= cc < c0 + n]}


def build(folder: Path, pub: str, repo: Path, gxd: Path | None = None, counts: Counter | None = None) -> dict:
    """The flag list for a folder of packets: writes <folder>/key-squares.json and returns it."""
    from PIL import Image

    packets = [d for d in sorted(folder.iterdir()) if (d / "ocr.json").exists() and d.name.startswith(pub)]
    if not packets:
        raise Stop(f"No {pub} packets (folders with ocr.json) in {folder}.")
    if counts is None:
        counts = answer_counts(gxd, pub)
    xds, warn = {}, []
    for d in packets:
        f = repo / "xd" / f"{d.name}.xd"
        if not f.exists():
            warn.append(f"{d.name}: no {f}, skipped")
            continue
        raw = f.read_bytes()
        xd = parse_xd(raw.decode("utf-8"))
        xd["sha"] = hashlib.sha1(raw).hexdigest()[:12]
        xd["labels"], w = label_clues(xd)
        warn += [f"{d.name}: {x}" for x in w]
        xds[d.name] = xd
    checked, known, read = learned(ledger(repo), xds)

    flags, clean = [], []
    for d in packets:
        x = d.name
        if x not in xds:
            continue
        xd, grid = xds[x], xds[x]["grid"]
        if not grid or all(ch in "#_" for row in grid for ch in row):
            continue
        ocr = json.loads((d / "ocr.json").read_text(encoding="utf-8"))
        at: dict[tuple[int, int], dict[str, str]] = {}
        for label, (cells, _, _) in xd["labels"].items():
            for rc in cells:
                at.setdefault(rc, {})[label[0]] = label
        png = d / "answers.png"
        size = Image.open(png).size if png.exists() else None
        rows, cols = len(grid), max(len(r) for r in grid)
        mine: dict[str, dict] = {}

        def add(r: int, c: int, source: str, why: str, sugg: str = "", word: str = "") -> None:
            sq = f"r{r + 1}c{c + 1}"
            if sq in checked.get(x, ()):
                return
            if sq in mine:
                f = mine[sq]
                f["source"] = "+".join(sorted(set(f["source"].split("+")) | {source}))
                f["card"]["why"].append(why)
                f["card"]["suggest"] = f["card"]["suggest"] or sugg
                return
            labs = at.get((r, c), {})
            show = word or labs.get("A") or labs.get("D")
            side = lambda d: ({"label": labs[d], "answer": xd["labels"][labs[d]][1],
                               "i": xd["labels"][labs[d]][0].index((r, c)), "clue": xd["labels"][labs[d]][2]}
                              if d in labs else None)
            mine[sq] = {"xdid": x, "sq": sq, "pub": pub, "source": source, "card": {
                "num": xd["head"].get("Number", ""), "title": xd["head"].get("Title", ""),
                "date": xd["head"].get("Date", ""), "letter": grid[r][c].upper(), "why": [why], "suggest": sugg,
                "across": side("A"), "down": side("D"),
                "img": "answers.png" if size else None,
                "crop": crop(size, rows, cols, r, c, xd["labels"][show][0] if show else []) if size else None,
                "scan": xd["head"].get("Solution-Source") or xd["head"].get("Source", ""), "xd": xd["sha"]}}

        for label, (cells, answer, _) in xd["labels"].items():
            s = suggest(answer, counts, known)
            if s:
                i, v, n = s
                add(*cells[i], "words", f"{label} reads {answer}, not a known answer; {v} is ({n} times in gxd)",
                    v[i], label)
        answers = ocr.get("answers") or []
        for sq in (ocr.get("answers_low_confidence") or []) if x not in read else []:
            m = re.fullmatch(r"r(\d+)c(\d+)", sq)
            if not m:
                continue
            r, c = int(m[1]) - 1, int(m[2]) - 1
            if r >= rows or c >= len(grid[r]) or grid[r][c] in "#_" or not grid[r][c].isalpha():
                continue
            letter = grid[r][c].upper()
            ocr_said = answers[r][c].upper() if r < len(answers) and c < len(answers[r]) else ""
            if letter in SKIP_UNSURE or letter != ocr_said:  # someone already changed it, so it was looked at
                continue
            add(r, c, "ocr", "The OCR was unsure of this letter")
        order = lambda f: tuple(int(v) for v in re.findall(r"\d+", f["sq"]))
        flags += sorted(mine.values(), key=order)
        if not mine:
            clean.append(x)
    out = {"page": PAGE, "pub": pub, "built_from": built_from(repo), "puzzles": [x for x in (d.name for d in packets) if x in xds],
           "flags": flags, "clean": clean, "warnings": warn}
    (folder / "key-squares.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out
