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
page.jpg, answer_page.jpg, grid.png, answers.png, _src/), named by the xdid; and for the folder, triage.json, the
record blitz ship reads (each puzzle's ship check: ship_check).
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
KEEP = ("instructions", "intro", "credit", "other")  # kept with the puzzle by default (its notes); the rest discarded


def line_label(said: str, page: str = "puzzle") -> str:
    """The proof page's label (ship.LINE_LABELS) for what the reader called a printed line ("solution caption",
    "heading (left of grid)", "intro (garbled)"): a line printed with the solution is where its answers are."""
    said = (said or "").lower()
    if page == "solution" or said.startswith("solution"):
        return "answers"
    head = said.split(" (")[0].strip()
    if head in LABELS:
        return LABELS[head]
    if head in ("heading", "banner"):
        return "section"
    if head in ("subheading", "tagline"):
        return "intro"
    return "other"


def _words(t: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (t or "").lower()))


def header_line(value: str, lines: list[dict]) -> int | None:
    """The printed line a header was read from: the first whose words are the value's, or hold them."""
    v = _words(value)
    if not v:
        return None
    return next((L["n"] for L in lines if _words(L["text"]) == v), None) or next(
        (L["n"] for L in lines if f" {v} " in f" {_words(L['text'])} "), None)


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
        lab = line_label(L.get("label", ""), L.get("page", "puzzle"))
        lines.append({"n": i, "text": L.get("text", ""), "box": L.get("box"), "label": lab,
                      "keep": lab in KEEP, "by": "hand-read", "printed_as": L.get("label", ""),
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
    # the xd's headers as the reader wrote them: the proof page's headers table shows each, named as the reader's, with
    # the printed line it was read from where one has its words (that line is the header's, not kept as a note)
    metadata = []
    for i, (f, x) in enumerate((("title", "Title"), ("number", "Number"), ("date", "Date"), ("author", "Author"),
                                ("editor", "Editor")), 1):
        if not h.get(x):
            continue
        n = header_line(h[x], lines[:len(bx.get("lines", []))]) if f != "date" else None
        metadata.append({"id": f"H{i}", "name": f"{f.title()} ({READ_BY})", "value": h[x], "field": f,
                         "says": f"as printed in line B{n}" if n else "the date of the issue it's in" if f == "date"
                         else "read by hand; no printed line has these words", **({"line": n} if n else {})})
        bare = re.sub(r"^(no|number) ", "", _words(lines[n - 1]["text"])) if n and f == "number" else _words(lines[n - 1]["text"]) if n else ""
        if n and bare == _words(h[x]):  # the line is the header itself ("No 12" for Number: 12): not a note as well
            lines[n - 1]["keep"] = False
            lines[n - 1]["header"] = f
    ocr = {"xdid": xdid, "source": "", "title": h.get("Title", ""), "author": h.get("Author", ""), "byline": "",
           "puzzle_number": h.get("Number", ""), "editor": h.get("Editor", ""), "issue_date": h.get("Date", ""),
           "feature": "", "read_by": READ_BY, "grid": blank,
           "answers": grid, "answers_low_confidence": [], "grid_asymmetric_squares": [],
           "clue_image": "page.jpg", "scales": {n: 1.0 for n in files.values() if (out / n).exists()},
           "clues": clues, "lines": lines, "evidence": {},
           "metadata": metadata,
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
    (out / "checks.json").write_text(json.dumps(checks_record(raw, ocr), indent=1, ensure_ascii=False), encoding="utf-8")
    bad = sum(1 for c in clues.values() if c.get("flags"))
    return {"xdid": xdid, "clues": len(clues), "outside": len(outside), "lines": len(lines), "givens": len(givens),
            "flagged": bad, "key": bool(bx.get("key")), "pair_form": bool(pair_form)}


# ---- the ship check: what keeps a hand-read xd from shipping, recorded with the packets -----------------
# blitz ship reads a triage record per puzzle (xword-ocr's triage.json for a harvest's run). A hand-read batch has no
# harvest, so hand-packets writes the record itself, in the packets' folder (triage.json), in the same shape: every
# puzzle "ready" for review, and its ship check of the xd, the same kinds of finding as xword-ocr shipcheck.check.
# `incomplete` is what no Ready makes whole (ship holds the puzzle on it), less what a person's edits fill (a key
# square read on the proof page: ship.filled_by). A run with no clue line, or a clue line with no text, is what the
# paper printed (the reader's own check, newyorkworld worldxd.py, notes it and passes: FUN left some words unclued,
# and No. 28 printed no clues at all), so it is a finding the reviewer sees, not a hold; a run whose every square
# is a given (printed in the grid) wants no clue and isn't one.

INCOMPLETE = ("clue-extra", "grid-unsolved", "answer-differs")


def _items(code: str, what: str, items: list[str]) -> dict:
    return {"code": code, "detail": f"{what}: " + " ".join(items[:8]) + (f" (+{len(items) - 8})" if len(items) > 8 else ""),
            "items": items}


def ship_check(text: str, ocr: dict | None = None) -> dict:
    """{ok, findings, incomplete, xd_fp} for a hand-read xd (ocr: its packet's, which says which of a pair-form
    puzzle's clues are on runs). Findings: no-title, no-author; clue-missing (a run of the grid with no clue line),
    clue-extra (a clue line naming no run), clue-empty, grid-unsolved (squares with no letter: '?' or '.', the key
    not printed or not read), answer-differs (a clue's answer isn't the grid's letters); in the World's own form,
    clue-off-grid for each clue no run can name (said, not holding: the xd keeps it under its pair)."""
    xd = parse_xd(text)
    grid, h = xd["grid"], xd["headers"]
    runs = slots(grid)
    pair_form = bool(xd["labels"]) or bool(h.get("Numbering"))
    f = []
    if not h.get("Title"):
        f.append({"code": "no-title", "detail": "no Title header"})
    if not (h.get("Author") or h.get("Byline")):
        f.append({"code": "no-author", "detail": "no Author or Byline header"})
    order = lambda k: (k[0], int(k[1:])) if re.fullmatch(r"[AD]\d+", k) else ("Z", 0)
    if pair_form:
        on = {(c or {}).get("printed"): k for k, c in ((ocr or {}).get("clues") or {}).items()}
        placed = {on[lab]: lab for lab in xd["order"] if lab in on}
        off = [lab for lab in xd["order"] if lab not in on]
        if off:
            f.append(_items("clue-off-grid", "clues no across or down run can name (kept under their printed pair)", off))
    else:
        placed = {lab: lab for lab in xd["order"]}
        gchars = {ln.split()[0] for ln in xd["styles"] if "given" in ln}
        given = {(r, c) for r, row in enumerate(xd["design"]) for c, ch in enumerate(row) if ch in gchars}
        missing = sorted({k for k, sq in runs.items() if not set(sq) <= given} - set(placed), key=order)
        extra = sorted(set(placed) - set(runs), key=order)
        if missing:
            f.append(_items("clue-missing", "runs with no clue line (none printed, as read)", missing))
        if extra:
            f.append(_items("clue-extra", "clues the grid has no slot for", extra))
    empty = [k for k, lab in placed.items() if not xd["clues"][lab]["text"].strip()]
    if pair_form:
        empty += [lab for lab in xd["order"] if lab not in placed.values() and not xd["clues"][lab]["text"].strip()]
    if empty:
        f.append(_items("clue-empty", "clues with no text (none printed, as read)", sorted(empty, key=order)))
    cells = [f"r{r + 1}c{c + 1}" for r, row in enumerate(grid) for c, ch in enumerate(row) if not NS(ch) and not ch.isalpha()]
    if cells:
        f.append({"code": "grid-unsolved", "detail": f"{len(cells)} square(s) unsolved", "cells": cells})
    differs = [k for k, lab in placed.items() if k in runs and xd["clues"][lab]["answer"]
               and "?" not in xd["clues"][lab]["answer"] and not cells
               and xd["clues"][lab]["answer"] != "".join(grid[r][c] for r, c in runs[k])]
    if differs:
        f.append(_items("answer-differs", "clues whose answer isn't the grid's letters", sorted(differs, key=order)))
    return {"ok": not f, "findings": f, "incomplete": [x["detail"] for x in f if x["code"] in INCOMPLETE],
            "xd_fp": hashlib.sha1(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()[:12]}


# a finding's row on the proof page: the header's, the clue's, the printed line's (a clue no run can name)
FINDING_ROW = {"no-title": ["meta:title"], "no-author": ["meta:author"]}


def checks_record(text: str, ocr: dict) -> dict:
    """The packet's checks.json, what the proof page's "What the checks found" draws: the ship check's findings, each
    linked to its rows (xword-ocr proofreview.checks_record's shape, from "hand-read check")."""
    ship = ship_check(text, ocr)
    off = {ln["text"].split(". ", 1)[0]: ln["n"] for ln in ocr.get("lines") or [] if ln.get("printed_as", "").startswith("a clue no")}
    items = []
    for f in ship["findings"]:
        if f["code"] == "clue-off-grid":
            keys = [f"line:B{off[x]}" for x in f.get("items") or [] if x in off]
        else:
            keys = FINDING_ROW.get(f["code"]) or [f"clue:{x}" for x in f.get("items") or []]
        items.append({"key": keys[0] if keys else "grid" if f.get("cells") else "notes", **({"keys": keys} if len(keys) > 1 else {}),
                      **({"cells": f["cells"]} if f.get("cells") else {}), "what": f["detail"], "from": "hand-read check",
                      "code": f["code"], "incomplete": f["detail"] in ship["incomplete"]})
    return {"xd_fp": ship["xd_fp"], "decision": "ready", "ship": ship, "items": items}


def write_triage(dest: Path, xdids: list[str]) -> Path:
    """dest/triage.json: each built packet's ship check (ship_check), as ship reads a harvest's triage record. Packets
    built earlier and not rebuilt now keep their rows."""
    path = dest / "triage.json"
    have = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    rows = {r["pid"]: r for r in have.get("puzzles") or []}
    for xdid in xdids:
        d = dest / xdid
        ocr = json.loads((d / "ocr.json").read_text(encoding="utf-8"))
        ship = ship_check((d / "puzzle.xd").read_text(encoding="utf-8"), ocr)
        rows[xdid] = {"pid": xdid, "decision": "ready", "reasons": [], "blocking": [], "ship": ship}
    out = {"by": "blitz hand-packets", "about": "puzzles read by hand: each one's ship check of its xd (blitz handread.ship_check)",
           "puzzles": [rows[k] for k in sorted(rows)]}
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def build_all(src: Path, pages: Path, dest: Path, xdids: list[str] | None = None, model: str = "") -> list[dict]:
    xds = sorted(p for p in src.glob("*.xd") if not xdids or p.stem in xdids)
    if not xds:
        raise Stop(f"No xd files in {src}" + (f" for {', '.join(xdids)}" if xdids else ""))
    dest.mkdir(parents=True, exist_ok=True)
    made = [build(p, pages, dest, model) for p in xds]
    write_triage(dest, [m["xdid"] for m in made])
    return made


# ---- an AI's Ready on puzzles read by hand: the record of a review done outside the review site ----------
# The World's Nos. 1-33 were read twice, blind (newyorkworld hand-read/second-read/VERDICTS.md): every disagreement
# looked at on the scan, every answer checked against the grid and the printed key. The owner's decision
# (2026-11-25): ship them on that, an AI's Ready, and send a puzzle back to review only if an error turns up. This
# writes that Ready into the publication's ledger, one proof:<pid> record per packet, on the packet's version, so
# ship counts it under a batch rule with ai_ready "ai" (ship-rule.json "batches"), and the record says what it rests on.

def ai_ready_records(proof_root: Path, by: str, note: str, hold=(), at: str = "") -> list[dict]:
    """A Ready by an AI (via the ship's AGENT) for each packet in proof_root but those in hold, on the packet's
    version (review.json xd_fp). note: what it rests on, which ship's review_of() quotes on the puzzle's record."""
    from datetime import datetime, timezone

    from .ship import AGENT
    at = at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    out = []
    for d in sorted(p for p in Path(proof_root).iterdir() if (p / "review.json").exists()):
        if d.name in hold:
            continue
        fp = json.loads((d / "review.json").read_text(encoding="utf-8")).get("xd_fp", "")
        review = {"edits": {}, "comments": [], "status": {}, "note": note, "xd": fp}
        out.append({"id": f"proof:{d.name}", "answer": "ready", "note": note, "fix": "", "by": by, "at": at, "via": AGENT,
                    "proof": {"xdid": d.name, "review": review, "at": at}})
    return out
