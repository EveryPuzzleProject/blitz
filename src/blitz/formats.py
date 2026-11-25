"""The handoff formats, checked: `blitz check-format <path>`.

Each handoff between the project's parts has a document in `formats/` and a check here. A check reads
files and says where they differ from the document; it reads no scan and works nothing out about a
puzzle. Version 1 of a format is what was on disk on 2026-11-25, so a file with no `format` field is
version 1.

Two kinds of line come back:

- problem: a reader of the format would break or be misled (a missing file, a field of the wrong
  type, an image named and not there, an xd that isn't the version the packet says it is).
- note: the file is a valid older form, or lacks something today's writers always write.

So far: the proof packet (formats/proof-packet.md).
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

PACKET = "proof-packet"
PACKET_VERSIONS = (1,)

# xword-ocr xd.PROCESS_HEADERS: headers that say how the puzzle was made, left out of xd_fp.
PROCESS_HEADERS = ("Source", "Solution-Source", "Clue-Source", "Assembly", "Text-Review",
                   "Proof-Packet", "Shipped", "Proof", "Proof-Edits", "Numbering-Rule")

CELL = re.compile(r"r\d+c\d+")
PAIR = re.compile(r"r\d+c\d+(/r\d+c\d+)?")  # a square and the one opposite it
FP = re.compile(r"[0-9a-f]{12}")
STR, BOOL, LIST, OBJ = (str,), (bool,), (list,), (dict,)

# field: types. Every form of the packet has these.
OCR_ALL = {"xdid": STR, "source": STR, "title": STR, "author": STR, "byline": STR, "grid": LIST,
           "answers": (list, type(None)), "answers_low_confidence": LIST, "grid_asymmetric_squares": LIST,
           "clue_image": STR, "scales": OBJ, "clues": OBJ}
# Also in the forms that carry puzzle.xd (assembled, read by hand).
OCR_XD = {"puzzle_number": STR, "editor": STR, "feature": STR, "issue_date": STR, "lines": LIST,
          "evidence": OBJ, "metadata": LIST}
REVIEW_ALL = {"ready": BOOL, "model": STR, "corrections": OBJ, "confirm": LIST, "sic": OBJ, "unsure": OBJ,
              "note": STR, "tool_notes": LIST, "matches_xd": BOOL}
REVIEW_XD = {"xd_fp": STR}
REVIEW_NOW = {"reviewer": STR, "reviewer_line": STR, "verdict": STR, "requests": LIST, "findings": LIST,
              "blanks": OBJ}  # what today's writers always write; older packets of a run may lack them
CHECKS = {"xd_fp": STR, "decision": STR, "ship": OBJ, "items": LIST}


def fingerprint(text: str) -> str:
    return hashlib.sha1(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()[:12]


def puzzle_fingerprint(text: str) -> str:
    """The xd's fingerprint without its process headers: a packet's xd_fp (xword-ocr xd.puzzle_fingerprint)."""
    head, sep, body = text.replace("\r\n", "\n").partition("\n\n")
    keep = [ln for ln in head.split("\n") if ln.partition(":")[0].strip() not in PROCESS_HEADERS]
    return fingerprint("\n".join(keep) + sep + body)


def form_of(packet: Path, ocr: dict) -> str:
    """Which writer's form a packet is: 'hand' (blitz hand-packets), 'assembled' (xword-ocr
    proof-packets), 'task' (xword-ocr task-packets, the older harvest's: no puzzle.xd)."""
    if ocr.get("hand_read") or ocr.get("read_by"):
        return "hand"
    return "assembled" if (packet / "puzzle.xd").exists() or "metadata" in ocr else "task"


def is_packet(path: Path) -> bool:
    return (path / "ocr.json").is_file()


def packets_under(path: Path) -> list[Path]:
    """The packet folders at or directly under a path."""
    if is_packet(path):
        return [path]
    return sorted(p for p in path.iterdir() if p.is_dir() and is_packet(p)) if path.is_dir() else []


def _load(f: Path, out: list) -> dict | None:
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except FileNotFoundError:
        out.append(("problem", f"{f.name}: missing"))
        return None
    except (OSError, ValueError) as e:
        out.append(("problem", f"{f.name}: not readable as JSON ({e})"))
        return None
    if not isinstance(d, dict):
        out.append(("problem", f"{f.name}: not an object"))
        return None
    return d


def _fields(d: dict, want: dict, name: str, out: list, level: str = "problem") -> None:
    for k, types in want.items():
        if k not in d:
            out.append((level, f"{name}: no '{k}'"))
        elif not isinstance(d[k], types) or (bool not in types and isinstance(d[k], bool)):
            out.append(("problem", f"{name}: '{k}' is {type(d[k]).__name__}, not {' or '.join(t.__name__ for t in types)}"))


def _box(v) -> bool:
    return isinstance(v, list) and len(v) == 4 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v)


def _rows(rows, name: str, chars: str | None, out: list) -> tuple[int, int] | None:
    if not rows or not all(isinstance(r, str) for r in rows):
        out.append(("problem", f"ocr.json: '{name}' is not a list of rows of text"))
        return None
    if len({len(r) for r in rows}) != 1:
        out.append(("problem", f"ocr.json: '{name}' rows differ in length"))
        return None
    if chars is not None:
        odd = sorted({ch for r in rows for ch in r if ch not in chars})
        if odd:
            out.append(("problem", f"ocr.json: '{name}' has {' '.join(map(repr, odd))} (only {' '.join(chars)} there)"))
    return len(rows), len(rows[0])


def check_packet(packet: Path) -> list[tuple[str, str]]:
    """What differs from formats/proof-packet.md, as (level, text) lines: level 'problem' or 'note'."""
    packet = Path(packet)
    out: list[tuple[str, str]] = []
    ocr = _load(packet / "ocr.json", out)
    review = _load(packet / "review.json", out)
    if ocr is None:
        return out

    version = ocr.get("format", f"{PACKET}/1")
    m = re.fullmatch(rf"{PACKET}/(\d+)", version) if isinstance(version, str) else None
    if not m or int(m.group(1)) not in PACKET_VERSIONS:
        out.append(("problem", f"ocr.json: format {version!r} is not one this check knows "
                               f"({', '.join(f'{PACKET}/{v}' for v in PACKET_VERSIONS)})"))
        return out

    form = form_of(packet, ocr)
    if form == "task":
        out.append(("note", "the older task form: no puzzle.xd, no printed lines or headers table"))

    # ---- ocr.json
    _fields(ocr, OCR_ALL, "ocr.json", out)
    if form != "task":
        _fields(ocr, OCR_XD, "ocr.json", out)
    if isinstance(ocr.get("xdid"), str) and ocr["xdid"] != packet.name:
        out.append(("note", f"ocr.json: xdid '{ocr['xdid']}' is not the folder's name"))
    shape = _rows(ocr.get("grid"), "grid", ".#_", out) if isinstance(ocr.get("grid"), list) else None
    if isinstance(ocr.get("answers"), list) and ocr["answers"]:
        key = _rows(ocr["answers"], "answers", None, out)
        if shape and key and key != shape:
            out.append(("problem", f"ocr.json: answers are {key[0]}x{key[1]}, the grid {shape[0]}x{shape[1]}"))
    for name, pat, like in (("answers_low_confidence", CELL, "a square like r3c5"),
                            ("grid_asymmetric_squares", PAIR, "a square or a pair like r1c5/r15c11")):
        bad = [x for x in ocr.get(name) or [] if not (isinstance(x, str) and pat.fullmatch(x))] if isinstance(ocr.get(name), list) else []
        if bad:
            out.append(("problem", f"ocr.json: '{name}' has {bad[0]!r}, not {like}"))

    images: dict[str, str] = {}  # image name -> where it is named
    if isinstance(ocr.get("clue_image"), str):
        images[ocr["clue_image"]] = "clue_image"
    for k, v in (ocr.get("scales") or {}).items() if isinstance(ocr.get("scales"), dict) else ():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
            out.append(("problem", f"ocr.json: scales['{k}'] is not a positive number"))
        images[k] = "scales"
    for label, c in (ocr.get("clues") or {}).items() if isinstance(ocr.get("clues"), dict) else ():
        if not isinstance(c, dict) or not isinstance(c.get("text"), str):
            out.append(("problem", f"ocr.json: clue {label} has no text"))
            continue
        if "box" in c and c["box"] is not None and not _box(c["box"]):
            out.append(("problem", f"ocr.json: clue {label}'s box is not four numbers"))
        if isinstance(c.get("image"), str):
            images[c["image"]] = f"clue {label}"
    for i, ln in enumerate(ocr.get("lines") or [] if isinstance(ocr.get("lines"), list) else []):
        if not isinstance(ln, dict) or not isinstance(ln.get("n"), int) or not isinstance(ln.get("text"), str):
            out.append(("problem", f"ocr.json: lines[{i}] has no n or no text"))
            continue
        if "box" in ln and ln["box"] is not None and not _box(ln["box"]):
            out.append(("problem", f"ocr.json: line B{ln['n']}'s box is not four numbers"))
        if isinstance(ln.get("image"), str):
            images[ln["image"]] = f"line B{ln['n']}"
    for i, md in enumerate(ocr.get("metadata") or [] if isinstance(ocr.get("metadata"), list) else []):
        if not isinstance(md, dict) or not all(isinstance(md.get(k), str) for k in ("id", "name", "value")):
            out.append(("problem", f"ocr.json: metadata[{i}] has no id, name or value"))
        elif isinstance(md.get("image"), str):
            images[md["image"]] = f"metadata {md['id']}"
    for name in ("answer_page", "continued_page"):
        if isinstance(ocr.get(name), dict) and isinstance(ocr[name].get("image"), str):
            images[ocr[name]["image"]] = name
    if isinstance(ocr.get("cover"), str) and ocr["cover"]:
        images[ocr["cover"]] = "cover"

    # ---- files
    for name, where in sorted(images.items()):
        if name and not (packet / name).is_file():
            out.append(("problem", f"{name}: named in ocr.json ({where}) and not in the packet"))
    if not (packet / "page.jpg").is_file() and "page.jpg" not in images:
        out.append(("problem", "page.jpg: missing"))
    if not (packet / "grid.png").is_file():
        out.append(("note", "grid.png: missing (no straightened grid; the page shows the scan beside our grid)"))
    if isinstance(ocr.get("answers"), list) and ocr["answers"] and not (packet / "answers.png").is_file():
        out.append(("note", "answers.png: missing though the packet has a key"))
    if not (packet / "_src").is_dir():
        out.append(("note", "_src/: missing (no full-resolution pages for crops)"))

    # ---- review.json
    if review is not None:
        _fields(review, REVIEW_ALL, "review.json", out)
        if form != "task":
            _fields(review, REVIEW_XD, "review.json", out)
            _fields(review, REVIEW_NOW, "review.json", out, level="note")
        for name in ("corrections", "sic", "unsure"):
            bad = [k for k, v in (review.get(name) or {}).items() if not isinstance(v, str)] if isinstance(review.get(name), dict) else []
            if bad:
                out.append(("problem", f"review.json: {name}['{bad[0]}'] is not text"))

    # ---- puzzle.xd and the version it is
    xd_file = packet / "puzzle.xd"
    fps: list[str] = []
    if form != "task":
        if not xd_file.is_file():
            out.append(("problem", "puzzle.xd: missing"))
        elif review is not None and isinstance(review.get("xd_fp"), str):
            xd = xd_file.read_text(encoding="utf-8")
            if not FP.fullmatch(review["xd_fp"]):
                out.append(("problem", f"review.json: xd_fp {review['xd_fp']!r} is not 12 hex digits"))
            fps = [review["xd_fp"], *[f for f in review.get("xd_fp_same") or [] if isinstance(f, str)]]
            if puzzle_fingerprint(xd) not in fps and fingerprint(xd) not in fps:
                out.append(("problem", f"puzzle.xd: its fingerprint ({puzzle_fingerprint(xd)}) is not review.json's "
                                       f"xd_fp ({review['xd_fp']}): the packet doesn't show its xd"))

    # ---- checks.json (optional)
    if (packet / "checks.json").exists():
        checks = _load(packet / "checks.json", out)
        if checks is not None:
            _fields(checks, CHECKS, "checks.json", out)
            ship = checks.get("ship") if isinstance(checks.get("ship"), dict) else {}
            _fields(ship, {"ok": BOOL, "findings": LIST, "incomplete": LIST}, "checks.json ship", out)
            for i, it in enumerate(checks.get("items") or [] if isinstance(checks.get("items"), list) else []):
                if not isinstance(it, dict) or not all(isinstance(it.get(k), str) for k in ("key", "what", "from")):
                    out.append(("problem", f"checks.json: items[{i}] has no key, what or from"))
            if fps and isinstance(checks.get("xd_fp"), str) and checks["xd_fp"] not in fps:
                out.append(("note", f"checks.json: made for another version of the xd ({checks['xd_fp']})"))
    return out


def check(paths: list[Path]) -> dict:
    """{packets, problems, notes, by_text: {text: count}, lines: [(packet, level, text)]} for the packets
    at or under the paths."""
    lines, counts, n = [], {}, 0
    for path in paths:
        found = packets_under(Path(path))
        if not found:
            lines.append((str(path), "problem", "no packet here (a packet is a folder with ocr.json)"))
        for p in found:
            n += 1
            for level, text in check_packet(p):
                lines.append((p.name, level, text))
                # count by kind of line: the text with ids and values taken out
                kind = re.sub(r"(?<= has )'[^']*'|(?<=xdid )'[^']*'|\([^)]*\)|\b[AD]\d+\b|B\d+|\[\d+\]|\b\d+x\d+\b|^\S+\.(jpg|png)(?=: named)",
                              "…", text)
                counts[(level, kind)] = counts.get((level, kind), 0) + 1
    return {"packets": n, "problems": sum(1 for _, lv, _ in lines if lv == "problem"),
            "notes": sum(1 for _, lv, _ in lines if lv == "note"), "by_text": counts, "lines": lines}
