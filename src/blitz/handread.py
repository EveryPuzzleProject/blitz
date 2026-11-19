"""Proof packets from puzzles read by hand from the scan, so they go through the review site like any other.

A hand-read puzzle has no OCR draft: a person (or an agent told to) read the page and wrote the xd, and
tied each clue and printed line to its box on the page (a boxes file). That reading is the puzzle's
starting version, as the OCR's is for the others: the proof page shows it as "read by hand", each clue
beside its crop of the scan, and every reviewer's change is laid over it and recorded as usual.

Input, per puzzle (the New York World's Nos. 1-33 are the first: newyorkworld `hand-read/`, READING.md):

- `<xdid>.xd`: the reading. Modern A/D clues, with the printed pair as clue metadata (`A6 ^Printed: 4-5`,
  `A6 ^Note: ...`), givens in a `## Design` section; or the World's own form (`Numbering:` header,
  `## Labels` section `<n> r<r>c<c>`, clues named by their end-square pair, `1-3. ...`).
- `<xdid>.boxes.json`: `pages` ({puzzle, solution}: file names in the pages folder), `grid` and `key`
  (the lattice: page, corners TL TR BR BL in page pixels, rows, cols), `lines` (each printed line:
  label, text, page, box) and `clues` (pair, text, answer, page, box, ref: the xd's clue label).
- `doubts-<xdid>.md` (optional): what the reader wasn't sure of; its text goes in as the reader's note.

Nothing here reads the scan for content: the crops are cut where the boxes file says, the grid and the
key are straightened from the lattice the reader recorded, and every value comes from the xd.

Output, per puzzle: a proof packet (the files `site-publish` puts up: ocr.json, review.json, puzzle.xd,
page.jpg, answer_page.jpg, grid.png, answers.png, _src/), named by the xdid.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

from .work import Stop

READ_BY = "read by hand"
LABELS = {"instructions": "instructions", "intro": "intro", "intro heading": "intro", "credit": "credit",
          "art credit": "credit"}


def parse_xd(text: str) -> dict:
    """The parts of an xd file this needs: headers, grid, clues (with their metadata lines), Design, Labels."""
    text = text.replace("\r\n", "\n")
    sections, name = {}, "Metadata"
    if not text.lstrip().startswith("## "):  # the old form: sections split by blank lines (not used here)
        raise Stop("not an xd file with ## sections")
    for line in text.split("\n"):
        m = re.match(r"^## (\w+)", line)
        if m:
            name = m.group(1)
            sections[name] = []
            continue
        sections.setdefault(name, []).append(line)
    headers = {}
    for line in sections.get("Metadata", []):
        if ":" in line and line.strip():
            k, v = line.split(":", 1)
            headers[k.strip()] = v.strip()
    grid = [ln for ln in sections.get("Grid", []) if ln.strip()]
    clues, meta, order = {}, {}, []
    for line in sections.get("Clues", []):
        if not line.strip():
            continue
        m = re.match(r"^(\S+?) \^(\w+): ?(.*)$", line)
        if m:
            meta.setdefault(m.group(1), {})[m.group(2)] = m.group(3)
            continue
        m = re.match(r"^(\S+?)\. ?(.*?) ~ (.*)$", line)
        if not m:
            raise Stop(f"a clue line I can't read: {line!r}")
        clues[m.group(1)] = {"text": m.group(2), "answer": m.group(3)}
        order.append(m.group(1))
    labels = {}
    for line in sections.get("Labels", []):
        m = re.match(r"^(\S+) r(\d+)c(\d+)$", line.strip())
        if m:
            labels[m.group(1)] = (int(m.group(2)) - 1, int(m.group(3)) - 1)
    design = [ln for ln in sections.get("Design", []) if ln.strip() and not re.match(r"^\S+ \{", ln)]
    styles = [ln for ln in sections.get("Design", []) if re.match(r"^\S+ \{", ln)]
    return {"headers": headers, "grid": grid, "clues": clues, "meta": meta, "order": order, "labels": labels,
            "design": design, "styles": styles}


def NS(ch: str) -> bool:
    """Not a square: a block, or outside the puzzle's shape."""
    return ch in "#_"


def slots(grid: list[str]) -> dict[str, list[tuple[int, int]]]:
    """Every across and down run of two or more, numbered as any crossword (the proof page's numbering)."""
    H, W, out, n = len(grid), len(grid[0]), {}, 0
    for r in range(H):
        for c in range(W):
            if NS(grid[r][c]):
                continue
            a = (c == 0 or NS(grid[r][c - 1])) and c + 1 < W and not NS(grid[r][c + 1])
            d = (r == 0 or NS(grid[r - 1][c])) and r + 1 < H and not NS(grid[r + 1][c])
            if a or d:
                n += 1
            for ok, key, dr, dc in ((a, "A", 0, 1), (d, "D", 1, 0)):
                if ok:
                    cells, rr, cc = [], r, c
                    while rr < H and cc < W and not NS(grid[rr][cc]):
                        cells.append((rr, cc))
                        rr, cc = rr + dr, cc + dc
                    out[f"{key}{n}"] = cells
    return out


def printed_numbers(xd: dict, runs: dict, givens: dict) -> tuple[dict, list]:
    """The labels printed in the squares of a modern-form xd, from its clues' pairs: ({(r, c): label}, clashes).

    A clue's `^Fits: a-b` (the pair that fits the grid, where the paper misprinted it), else its `^Printed: a-b`,
    names its word's first square a and its last b. A given square (givens: {(r, c): its letter}) shows its letter,
    as the paper printed it there; a pair that labels it otherwise is a clash. clashes: [((r, c), {label: [clues]})]
    for a square the pairs give two labels: it gets none (the reviewer types the printed one), and nothing guesses."""
    said: dict = {sq: {v: ["a given"]} for sq, v in givens.items()}
    for label in xd["order"]:
        m = xd["meta"].get(label, {})
        a, sep, b = (m.get("Fits") or m.get("Printed") or "").partition("-")
        if not sep or label not in runs or not a.strip() or not b.strip():
            continue
        cells = runs[label]
        for sq, v in ((cells[0], a.strip()), (cells[-1], b.strip())):
            said.setdefault(sq, {}).setdefault(v, []).append(label)
    nums, clashes = {}, []
    for sq, vals in sorted(said.items()):
        if len(vals) == 1:
            nums[sq] = next(iter(vals))
        else:
            clashes.append((sq, vals))
    return nums, clashes


def _quad(im, corners, rows: int, cols: int, cell: int = 40):
    """The lattice straightened: corners TL TR BR BL (page pixels) to a rows x cols image, cell px a square."""
    from PIL import Image

    (tl, tr, br, bl) = corners
    w, h = cols * cell, rows * cell
    return im.transform((w, h), Image.QUAD, (*tl, *bl, *br, *tr), Image.BICUBIC)


def _jpg(src: Path, dst: Path) -> None:
    from PIL import Image

    with Image.open(src) as im:
        im.convert("RGB").save(dst, "JPEG", quality=88)


def build(xd_path: Path, pages: Path, dest: Path, model: str = "") -> dict:
    """One puzzle's proof packet in dest/<xdid>/. Returns a line of what it made, for the summary."""
    from PIL import Image

    xdid = xd_path.stem
    boxes_path = xd_path.with_name(f"{xdid}.boxes.json")
    if not boxes_path.exists():
        raise Stop(f"{xdid}: no boxes file ({boxes_path.name}): every text must be tied to its place on the page")
    raw = xd_path.read_text(encoding="utf-8")
    xd, bx = parse_xd(raw), json.loads(boxes_path.read_text(encoding="utf-8"))
    out = dest / xdid
    if out.exists():
        shutil.rmtree(out)
    (out / "_src").mkdir(parents=True)
    files = {"puzzle": "page.jpg", "solution": "answer_page.jpg"}
    for part, name in files.items():
        f = bx["pages"].get(part)
        if f:
            if not (pages / f).exists():
                raise Stop(f"{xdid}: page {f} is not in {pages}")
            _jpg(pages / f, out / "_src" / name)
            shutil.copyfile(out / "_src" / name, out / name)
    image_of = lambda part: files.get(part or "puzzle", "page.jpg")
    for part, png in (("grid", "grid.png"), ("key", "answers.png")):
        lat = bx.get(part)
        if lat and lat.get("corners"):
            with Image.open(pages / bx["pages"][lat["page"]]) as im:
                _quad(im.convert("RGB"), lat["corners"], lat["rows"], lat["cols"]).save(out / png)

    grid = xd["grid"]
    H, W = len(grid), len(grid[0])
    blank = ["".join(ch if NS(ch) else "." for ch in row) for row in grid]
    runs = slots(grid)
    by_cells = {tuple(v): k for k, v in runs.items()}
    pair_form = bool(xd["labels"]) or xd["headers"].get("Numbering")
    box_of = {}
    for c in bx.get("clues", []):
        box_of[c.get("ref") or c.get("pair")] = c
    clues, outside, notes = {}, [], []
    for label in xd["order"]:
        c, m = xd["clues"][label], xd["meta"].get(label, {})
        b = box_of.get(label) or {}
        key, printed = label, m.get("Printed", "")
        if pair_form:  # the World's own form: name the clue by the run its pair's two end squares bound
            printed = label
            ends = [xd["labels"].get(e) for e in label.split("-")]
            key = None
            if len(ends) == 2 and all(ends):
                (r0, c0), (r1, c1) = ends
                cells = ([(r0, cc) for cc in range(c0, c1 + 1)] if r0 == r1 and c1 > c0 else
                         [(rr, c0) for rr in range(r0, r1 + 1)] if c0 == c1 and r1 > r0 else [])
                key = by_cells.get(tuple(cells))
            if not key or key in clues:
                outside.append((label, c, b))
                continue
        elif not re.fullmatch(r"[AD]\d+", label):
            outside.append((label, c, b))
            continue
        entry = {"text": c["text"]}
        if printed:
            entry["printed"] = printed
        if b.get("box"):
            entry["box"] = b["box"]
            if image_of(b.get("page")) != "page.jpg":
                entry["image"] = image_of(b.get("page"))
        flags = []
        if key not in runs:
            flags.append("no such run in the grid")
        elif c["answer"] and "?" not in c["answer"] and "".join(grid[r][cc] for r, cc in runs[key]) != c["answer"]:
            flags.append(f"answer {c['answer']} isn't the grid's {''.join(grid[r][cc] for r, cc in runs[key])}")
        if flags:
            entry["flags"] = flags
        clues[key] = entry
        for k, v in m.items():
            if k not in ("Printed", "Fits"):  # the pair, and the pair that fits: the label and the grid's numbers show them
                notes.append({"kind": "source", "target": f"clue:{key}", "note": f"{k}: {v}"})

    lines = []
    for i, L in enumerate(bx.get("lines", []), 1):
        lines.append({"n": i, "text": L.get("text", ""), "box": L.get("box"), "label": LABELS.get(L.get("label", ""), "other"),
                      "keep": True, "by": "hand-read", "printed_as": L.get("label", ""),
                      **({"image": image_of(L.get("page"))} if image_of(L.get("page")) != "page.jpg" else {})})
    # a clue the modern numbering can't name (a diagonal word, a word inside a longer run): a printed line of
    # its own, with its pair and answer, so it is seen and checked beside its crop
    for label, c, b in outside:
        lines.append({"n": len(lines) + 1, "text": f"{label}. {c['text']} ~ {c['answer']}", "box": b.get("box"),
                      "label": "other", "keep": True, "by": "hand-read",
                      "printed_as": "a clue no across or down run can name",
                      **({"image": image_of(b.get("page"))} if b.get("page") and image_of(b.get("page")) != "page.jpg" else {})})

    givens = []
    if xd["design"]:
        gchars = {ln.split()[0] for ln in xd["styles"] if "given" in ln}
        for r, row in enumerate(xd["design"]):
            for c, ch in enumerate(row):
                if ch in gchars:
                    givens.append((r, c))
    for r, c in givens:
        notes.append({"kind": "source", "target": f"cell:r{r + 1}c{c + 1}",
                      "note": f"Given: the letter {grid[r][c]} is printed in this square of the puzzle (the xd's Design section)."})
    # the numbers printed in the squares, so the blank grid shows the paper's and each clue's label is its pair
    if pair_form:
        square_numbers, clashes = {f"r{r + 1}c{c + 1}": n for n, (r, c) in xd["labels"].items()}, []
    else:
        nums, clashes = printed_numbers(xd, runs, {sq: grid[sq[0]][sq[1]] for sq in givens})
        square_numbers = {f"r{r + 1}c{c + 1}": v for (r, c), v in nums.items()}
    for (r, c), said in clashes:
        notes.append({"kind": "source", "target": f"grid:r{r + 1}c{c + 1}",
                      "note": "The clues' pairs give this square two labels, so the blank grid shows none here: "
                              + "; ".join(f"{v} ({', '.join(ks)})" for v, ks in said.items()) + ". Type the printed one."})
    h = xd["headers"]
    ocr = {"xdid": xdid, "source": "", "title": h.get("Title", ""), "author": h.get("Author", ""), "byline": "",
           "puzzle_number": h.get("Number", ""), "editor": h.get("Editor", ""), "issue_date": h.get("Date", ""),
           "feature": "", "read_by": READ_BY, "grid": blank,
           "answers": grid, "answers_low_confidence": [], "grid_asymmetric_squares": [],
           "clue_image": "page.jpg", "scales": {n: 1.0 for n in files.values() if (out / n).exists()},
           "clues": clues, "lines": lines, "evidence": {},
           # the xd's headers as the reader wrote them: the proof page's headers table shows each, named as the reader's
           "metadata": [{"id": f"H{i}", "name": f"{f.title()} ({READ_BY})", "value": h[x], "field": f}
                        for i, (f, x) in enumerate((("title", "Title"), ("number", "Number"), ("date", "Date"),
                                                     ("author", "Author"), ("editor", "Editor")), 1) if h.get(x)],
           "square_numbers": square_numbers,
           "numbering": ("as printed (the xd's Labels section)" if pair_form else
                         "from each clue's printed pair (the xd's ^Printed, or ^Fits where the pair was misprinted): its first "
                         "number on the word's first square, its second on the last; a given square shows its letter"),
           "hand_read": {"boxes": boxes_path.name, "pages": bx["pages"], "pair_form": bool(pair_form),
                         "outside": [label for label, _, _ in outside]}}
    (out / "ocr.json").write_text(json.dumps(ocr, indent=1, ensure_ascii=False), encoding="utf-8")
    shutil.copyfile(xd_path, out / "puzzle.xd")
    doubts = xd_path.with_name(f"doubts-{xdid}.md")
    say = (f"Read by hand from the scan ({', '.join(bx['pages'].values())}); every clue and printed line is "
           f"tied to its box on the page ({boxes_path.name}). Check each against its crop.")
    if pair_form:
        say += (" Kept in the World's own numbering (its end-square pairs): "
                + (f"{len(outside)} clue(s) no across or down run can name are listed as printed lines. " if outside else "")
                + "Treated as a meta.")
    if doubts.exists():
        notes.append({"kind": "source", "target": "other", "note": doubts.read_text(encoding="utf-8")})
    review = {"ready": False, "model": READ_BY, "reviewer": READ_BY, "reviewer_line": f"{READ_BY}{' (' + model + ')' if model else ''}",
              "corrections": {}, "confirm": [], "sic": {}, "unsure": {}, "note": say, "verdict": say, "requests": [],
              "blanks": {}, "tool_notes": notes, "findings": [], "matches_xd": True,
              "xd_fp": hashlib.sha1(raw.replace("\r\n", "\n").encode("utf-8")).hexdigest()[:12],
              "hand_read": True}
    (out / "review.json").write_text(json.dumps(review, indent=1, ensure_ascii=False), encoding="utf-8")
    bad = sum(1 for c in clues.values() if c.get("flags"))
    return {"xdid": xdid, "clues": len(clues), "outside": len(outside), "lines": len(lines), "givens": len(givens),
            "flagged": bad, "key": bool(bx.get("key")), "pair_form": bool(pair_form)}


def build_all(src: Path, pages: Path, dest: Path, xdids: list[str] | None = None, model: str = "") -> list[dict]:
    xds = sorted(p for p in src.glob("*.xd") if not xdids or p.stem in xdids)
    if not xds:
        raise Stop(f"No xd files in {src}" + (f" for {', '.join(xdids)}" if xdids else ""))
    dest.mkdir(parents=True, exist_ok=True)
    return [build(p, pages, dest, model) for p in xds]
