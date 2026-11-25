"""The handoff formats, checked: `blitz check-format <path>`.

Each handoff between the project's parts has a document in `formats/` and a check here. A check reads
files and says where they differ from the document; it reads no scan and works nothing out about a
puzzle. Version 1 of a format is what was on disk on 2026-11-25, so a file with no `format` field is
version 1.

Two kinds of line come back:

- problem: a reader of the format would break or be misled (a missing file, a field of the wrong
  type, an image named and not there, an xd that isn't the version the packet says it is).
- note: the file is a valid older form, or lacks something today's writers always write.

So far: the proof packet (formats/proof-packet.md), the annotated xd (formats/annotated-xd.md) and the
assembly record (formats/assembly-record.md).
"""

from __future__ import annotations

import gzip
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


def _kind(text: str) -> str:
    """A line with its ids and values taken out, for counting lines of one kind."""
    return re.sub(r"(?<= has )'[^']*'|(?<=xdid )'[^']*'|\([^)]*\)|[AD]\d+|B\d+|\[\d+\]|\d+x\d+|^\S+\.(jpg|png)(?=: named)"
                  r"|(?<=clue field ')\S+|(?<=: )['\"].*$", "…", text)


def check(paths: list[Path], artifacts: Path | None = None) -> dict:
    """{packets, xds, assemblies, problems, notes, by_text: {(level, kind): count}, lines: [(name, level, text)]}
    for what is at or under the paths: packet folders, .xd files, a folder of either, or a harvest's assembly
    records (its assembly/ folder, or one issue's file). artifacts: the store the records' outputs are in
    (xword-ocr .cache/artifacts), to check those too."""
    lines, counts, n, nx, na = [], {}, 0, 0, 0
    for path in map(Path, paths):
        records = assembly_files(path)
        if records:
            na += len(records)
            for f in records:
                for level, text in check_assembly(f, artifacts):
                    lines.append((f.name, level, text))
                    counts[(level, _kind(text))] = counts.get((level, _kind(text)), 0) + 1
            continue
        found = packets_under(path)
        xds = [path] if path.is_file() and path.suffix == ".xd" else             sorted(path.glob("*.xd")) if path.is_dir() and not found else []
        if not found and not xds:
            text = "no packet and no .xd file here (a packet is a folder with ocr.json)"
            lines.append((str(path), "problem", text))
            counts[("problem", text)] = counts.get(("problem", text), 0) + 1
        got = [(p.name, check_packet(p)) for p in found]
        got += [(f.name, check_xd(f.read_text(encoding="utf-8"))) for f in xds]
        n, nx = n + len(found), nx + len(xds)
        for name, res in got:
            for level, text in res:
                lines.append((name, level, text))
                counts[(level, _kind(text))] = counts.get((level, _kind(text)), 0) + 1
    return {"packets": n, "xds": nx, "assemblies": na, "problems": sum(1 for _, lv, _ in lines if lv == "problem"),
            "notes": sum(1 for _, lv, _ in lines if lv == "note"), "by_text": counts, "lines": lines}


# ---- the assembly record (formats/assembly-record.md) --------------------------------------------

ASSEMBLY = "assembly-record"
ASSEMBLY_VERSIONS = (1,)
READINGS = ("hands-off", "reviewed", "hands-off-without-drops")
ISSUE_FILE = re.compile(r"\d{4}-\d{2}-\d{2}\.json")
SHA = re.compile(r"sha256:[0-9a-f]{64}")
INPUT_NAMES = ("issues", "given_keys", "left_out")
RECORD = {"stage": STR, "version": STR, "settings": OBJ, "inputs": OBJ, "output": STR, "made": STR, "code": STR}
BODY = {"pubid": STR, "date": STR, "variant": STR, "pages_read": LIST, "puzzles": LIST, "loose": LIST, "pages": LIST,
        "state": OBJ}
PAGE_READ = {"scan": STR, "leaf": (int,), "role": STR, "restarted": BOOL}
PUZZLE = {"grid": OBJ, "title": STR, "clues": OBJ, "flags": LIST, "cryptic": BOOL}
PLACE = {"scan": STR, "leaf": (int,), "box": LIST}


def assembly_files(path: Path) -> list[Path]:
    """The assembly record files at a path: one issue's file (<date>.json under a folder named issue), a
    harvest's assembly/ folder, or its assembly/issue/ folder. [] when the path is none of these."""
    path = Path(path)
    if path.is_file():
        return [path] if ISSUE_FILE.fullmatch(path.name) and path.parent.name == "issue" else []
    if path.is_dir() and path.name == "assembly" and (path / "issue").is_dir():
        path = path / "issue"
    if path.is_dir() and path.name == "issue" and path.parent.name == "assembly":
        return sorted(f for f in path.iterdir() if ISSUE_FILE.fullmatch(f.name))
    return []


def artifact_path(store: Path, stage: str, h: str) -> Path:
    """Where a store keeps an artifact (xword-ocr artifacts.Store): <store>/<stage>/<ab>/<hash>.json.gz."""
    hexd = h.split(":", 1)[1]
    return Path(store) / stage / hexd[:2] / f"{hexd}.json.gz"


def _versioned(d: dict, name: str, out: list) -> None:
    fmt = d.get("format")
    if fmt is None:
        return  # version 1
    m = re.fullmatch(rf"{ASSEMBLY}/(\d+)", str(fmt))
    if not m:
        out.append(("problem", f"{name}: format is {fmt!r}, not {ASSEMBLY}/<n>"))
    elif int(m.group(1)) not in ASSEMBLY_VERSIONS:
        out.append(("problem", f"{name}: format {fmt} is newer than this check reads ({ASSEMBLY}/{ASSEMBLY_VERSIONS[-1]})"))


def check_assembly(f: Path, artifacts: Path | None = None) -> list[tuple[str, str]]:
    """One issue's assembly records (a file of a harvest's assembly/issue/) against formats/assembly-record.md;
    with artifacts (the store), each record's output too. Reads those files and nothing else."""
    out: list[tuple[str, str]] = []
    data = _load(f, out)
    if data is None:
        return out
    if not isinstance(data, dict):
        return [("problem", f"{f.name}: not an object of units")]
    date = f.stem
    if not data:
        out.append(("note", f"{f.name}: no records in it"))
    for unit, stages in data.items():
        m = re.fullmatch(r"issue:(\d{4}-\d{2}-\d{2})/([\w-]+)", unit)
        if not m:
            out.append(("problem", f"unit {unit!r} is not issue:<date>/<reading>"))
            continue
        if m.group(1) != date:
            out.append(("problem", f"unit {unit!r} is in the file of another issue ({f.name})"))
        reading = m.group(2)
        if reading not in READINGS:
            out.append(("note", f"unit {unit!r}: a reading this check doesn't know (it knows {', '.join(READINGS)})"))
        rec = stages.get("assembly") if isinstance(stages, dict) else None
        if not isinstance(rec, dict):
            out.append(("problem", f"{unit}: no assembly record"))
            continue
        _versioned(rec, unit, out)
        _fields(rec, RECORD, unit, out)
        if rec.get("stage") != "assembly":
            out.append(("problem", f"{unit}: stage is {rec.get('stage')!r}, not 'assembly'"))
        if isinstance(rec.get("version"), str) and not re.fullmatch(r"assembly/\d+", rec["version"]):
            out.append(("problem", f"{unit}: version is {rec['version']!r}, not assembly/<n>"))
        took = rec.get("took")
        if isinstance(took, bool) or not isinstance(took, (int, float)) or took < 0:
            out.append(("problem", f"{unit}: took is {took!r}, not the seconds its assembly took"))
        if isinstance(rec.get("made"), str) and not re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", rec["made"]):
            out.append(("problem", f"{unit}: made is {rec['made']!r}, not a time"))
        settings = rec.get("settings") if isinstance(rec.get("settings"), dict) else {}
        if not isinstance(settings.get("hands_off"), bool):
            out.append(("problem", f"{unit}: settings has no hands_off (true or false)"))
        elif reading in READINGS and settings["hands_off"] != reading.startswith("hands-off"):
            out.append(("problem", f"{unit}: settings.hands_off is {settings['hands_off']} for the {reading} reading"))
        inputs = rec.get("inputs") if isinstance(rec.get("inputs"), dict) else {}
        for name, h in inputs.items():
            if not (isinstance(h, str) and SHA.fullmatch(h)):
                out.append(("problem", f"{unit}: input {name!r} is not a sha256 hash"))
            if not (name in INPUT_NAMES or re.fullmatch(r"page:.+/\d{4}", name)):
                out.append(("note", f"{unit}: input {name!r} is not one the format names"))
        if "inputs" in rec and "issues" not in inputs:
            out.append(("problem", f"{unit}: inputs has no 'issues' (the issues read and their pages)"))
        if reading == "hands-off-without-drops" and "left_out" not in inputs:
            out.append(("note", f"{unit}: the reading without drops names no left_out input (no drop in this issue)"))
        output = rec.get("output")
        if isinstance(output, str) and not SHA.fullmatch(output):
            out.append(("problem", f"{unit}: output is not a sha256 hash"))
        elif isinstance(output, str) and artifacts is not None:
            out += _check_assembly_artifact(unit, date, reading, inputs, artifact_path(artifacts, "assembly", output), output)
    return out


def _check_assembly_artifact(unit: str, date: str, reading: str, inputs: dict, f: Path, h: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if not f.is_file():
        return [("problem", f"{unit}: its artifact is not in the store ({f.parent.name}/{f.name})")]
    try:
        raw = gzip.decompress(f.read_bytes())
        body = json.loads(raw)
    except (OSError, ValueError) as e:
        return [("problem", f"{unit}: its artifact can't be read: {e}")]
    if "sha256:" + hashlib.sha256(raw).hexdigest() != h:
        out.append(("problem", f"{unit}: its artifact's bytes don't have the hash the record names"))
    if not isinstance(body, dict):
        return out + [("problem", f"{unit}: its artifact is not an object")]
    name = f"{unit} artifact"
    _versioned(body, name, out)
    _fields(body, BODY, name, out)
    if body.get("date") != date or body.get("variant") != reading:
        out.append(("problem", f"{name}: is of {body.get('date')} {body.get('variant')}, not this unit's issue and reading"))
    if not (body.get("next") is None or isinstance(body.get("next"), str)):
        out.append(("problem", f"{name}: next is neither a date nor null"))
    read = set()
    for i, p in enumerate(body.get("pages_read") if isinstance(body.get("pages_read"), list) else []):
        if not isinstance(p, dict):
            out.append(("problem", f"{name}: pages_read[{i}] is not an object"))
            continue
        _fields(p, PAGE_READ, f"{name} pages_read[{i}]", out)
        for k in ("analysis", "ocr", "image", "view", "extract"):
            if not (p.get(k) is None or isinstance(p.get(k), str) and SHA.fullmatch(p[k])):
                out.append(("problem", f"{name}: pages_read[{i}] {k} is neither a sha256 hash nor null"))
        if isinstance(p.get("scan"), str) and isinstance(p.get("leaf"), int):
            read.add(f"page:{p['scan']}/{p['leaf']:04d}")
    named = {n for n in inputs if n.startswith("page:")}
    if read != named:
        out.append(("problem", f"{name}: pages_read names {len(read)} pages, the record's inputs {len(named)}: "
                               f"they should be the same pages"))
    for i, z in enumerate(body.get("puzzles") if isinstance(body.get("puzzles"), list) else []):
        if not isinstance(z, dict):
            out.append(("problem", f"{name}: puzzles[{i}] is not an object"))
            continue
        _fields(z, PUZZLE, f"{name} puzzles[{i}]", out)
        if isinstance(z.get("grid"), dict):
            _fields(z["grid"], PLACE, f"{name} puzzles[{i}] grid", out)
            if "box" in z["grid"] and not _box(z["grid"]["box"]):
                out.append(("problem", f"{name}: puzzles[{i}] grid box is not [x0, y0, x1, y1]"))
        if isinstance(z.get("key"), dict):
            _fields(z["key"], PLACE, f"{name} puzzles[{i}] key", out)
        elif "key" not in z or z["key"] is not None:
            out.append(("problem", f"{name}: puzzles[{i}] key is neither a key nor null"))
        if isinstance(z.get("clues"), dict) and not all(isinstance(z["clues"].get(d), list) for d in ("A", "D")):
            out.append(("problem", f"{name}: puzzles[{i}] clues has no A and D lists"))
    for i, x in enumerate(body.get("loose") if isinstance(body.get("loose"), list) else []):
        if not isinstance(x, dict):
            out.append(("problem", f"{name}: loose[{i}] is not an object"))
            continue
        _fields(x, {"kind": STR, "label": STR, "why": STR, **PLACE}, f"{name} loose[{i}]", out)
    for i, p in enumerate(body.get("pages") if isinstance(body.get("pages"), list) else []):
        if not isinstance(p, dict):
            out.append(("problem", f"{name}: pages[{i}] is not an object"))
            continue
        _fields(p, {"scan": STR, "leaf": (int,), "boxes": LIST}, f"{name} pages[{i}]", out)
    return out


# ---- the annotated xd (formats/annotated-xd.md) -------------------------------------------------

XD = "annotated-xd"
SECTIONS = ("Metadata", "Printed", "Grid", "Clues", "Design", "Labels", "Notes")
# Field form. Kind 1: what the paper printed for this puzzle. Kind 3: EPP's own statements. And the
# scan citations the xd keeps (design/xd-fields.md).
PRINTED_HEADERS = ("Title", "Author", "Editor", "Number", "Date", "Copyright")
EPP_HEADERS = ("Description", "Incomplete", "Numbering")
CITATIONS = ("Source", "Solution-Source", "Clue-Source")
CLUE_KEYS = ("Printed", "Fits", "Correction", "Answer-Correction", "Note")
# Provenance (kind 4): in the block form's header, never in the field form's.
WORKING_HEADERS = ("Assembly", "Text-Review", "Proof-Packet", "Shipped", "Proof", "Proof-Edits", "Numbering-Rule",
                   "Solution", "Provenance")
# The labels a ## Printed line has carried so far (the World's Nos. 1-33), with blitz's own (ship.LINE_LABELS).
PRINTED_LABELS = ("heading", "subheading", "number", "intro", "intro heading", "instructions", "credit", "art credit",
                  "banner", "tagline", "note", "panel", "prize notice", "centre", "centre block", "solution heading",
                  "solution caption", "solution intro", "solution centre",
                  "test-solver", "kind", "answers", "section", "furniture", "other-puzzle", "other")
HEADER = re.compile(r"([A-Za-z][\w-]*): ?(.*)")
CLUE = re.compile(r"([AD]\d+|\d+-\d+|[A-Za-z]?\d+[a-z]?)\. ?(.*)")
CLUE_META = re.compile(r"(\S+) \^([\w-]+): ?(.*)")
DATE = re.compile(r"\d{4}(-\d{2}(-\d{2})?)?")


def xd_form(text: str) -> str:
    """'field' (## sections, design/xd-fields.md) or 'block' (parts set apart by two blank lines)."""
    return "field" if text.lstrip("﻿ \n").startswith("## ") else "block"


def _grid_rows(rows: list[str], out: list) -> None:
    rows = [r for r in rows if r.strip()]
    if not rows:
        out.append(("problem", "no grid"))
    elif len({len(r) for r in rows}) != 1:
        out.append(("problem", "the grid's rows differ in length"))


def _clue_lines(lines: list[str], out: list, field: bool) -> None:
    last, seen, metas = None, set(), {}
    for ln in lines:
        if not ln.strip():
            continue
        m = CLUE_META.fullmatch(ln)
        if m:
            ref, key = m.group(1), m.group(2)
            if ref != last:
                out.append(("problem", f"clue field '{ref} ^{key}:' is not under its clue's line"))
            if field and key not in CLUE_KEYS:
                out.append(("note", f"clue field '^{key}:' is not one of EPP's ({', '.join('^' + k for k in CLUE_KEYS)})"))
            metas.setdefault(ref, set()).add(key)
            continue
        m = CLUE.fullmatch(ln)
        if not m:
            out.append(("problem", f"not a clue line: {ln[:60]!r}"))
            continue
        last = m.group(1)
        if last in seen:
            out.append(("problem", f"clue {last} is there twice"))
        seen.add(last)
        if " ~" not in ln:
            out.append(("problem", f"clue {last} has no ' ~ ' before its answer"))
    for ref, keys in metas.items():
        if "Fits" in keys and "Printed" not in keys:
            out.append(("problem", f"clue {ref} has ^Fits: with no ^Printed:"))
    if not seen:
        out.append(("note", "no clue lines"))


def check_xd(text: str) -> list[tuple[str, str]]:
    """What differs from formats/annotated-xd.md, as (level, text) lines."""
    out: list[tuple[str, str]] = []
    text = text.replace("\r\n", "\n")
    if xd_form(text) == "block":
        out.append(("note", "the block form (the shape shipped before 2026-11-25)"))
        parts = text.strip("\n").split("\n\n\n")
        if len(parts) < 3:
            out.append(("problem", f"{len(parts)} parts set apart by two blank lines; a header, a grid and clues are three"))
            return out
        heads = {}
        for ln in parts[0].split("\n"):
            m = HEADER.fullmatch(ln)
            if not m:
                out.append(("problem", f"not a header line: {ln[:60]!r}"))
            else:
                heads[m.group(1)] = m.group(2)
        if not DATE.fullmatch(heads.get("Date", "")):
            out.append(("problem", "no Date header as YYYY-MM-DD"))
        _grid_rows(parts[1].split("\n"), out)
        _clue_lines(parts[2].split("\n"), out, field=False)
        return out

    sections: dict[str, list[str]] = {}
    cur = None
    for ln in text.split("\n"):
        m = re.fullmatch(r"## (.+)", ln)
        if m:
            cur = m.group(1).strip()
            if cur in sections:
                out.append(("problem", f"section '## {cur}' is there twice"))
            sections.setdefault(cur, [])
            if cur not in SECTIONS:
                out.append(("note", f"section '## {cur}' is not one the format names"))
        elif cur is not None:
            sections[cur].append(ln)
    for need in ("Metadata", "Grid", "Clues"):
        if need not in sections:
            out.append(("problem", f"no '## {need}' section"))
    if list(sections)[:1] != ["Metadata"]:
        out.append(("problem", "the first section is not '## Metadata'"))

    heads = {}
    for ln in sections.get("Metadata", []):
        if not ln.strip():
            continue
        m = HEADER.fullmatch(ln)
        if not m:
            out.append(("problem", f"not a header line: {ln[:60]!r}"))
            continue
        name = m.group(1)
        if name in heads:
            out.append(("problem", f"header '{name}:' is there twice"))
        heads[name] = m.group(2)
        if name in WORKING_HEADERS:
            out.append(("problem", f"header '{name}:' is provenance, which the field form keeps out of the xd"))
        elif name == "Notes":
            out.append(("note", "header 'Notes:' (retired as a catch-all: Description, ## Printed or provenance)"))
        elif name.endswith("-Correction"):
            if name[:-len("-Correction")] not in heads:
                out.append(("problem", f"header '{name}:' has no '{name[:-len('-Correction')]}:' before it"))
        elif name not in PRINTED_HEADERS + EPP_HEADERS + CITATIONS:
            out.append(("note", f"header '{name}:' is not one the format names"))
    if not DATE.fullmatch(heads.get("Date", "")):
        out.append(("problem", "no Date header as YYYY-MM-DD"))
    if "Source" not in heads:
        out.append(("note", "no Source header (the scan the puzzle was read from)"))

    for ln in sections.get("Printed", []):
        if not ln.strip():
            continue
        m = re.fullmatch(r"([a-z][a-z -]*?)(?: \([^()]+\))?: ?(.*)", ln)  # label, or label (which one)
        if not m:
            out.append(("problem", f"## Printed: not 'label: text': {ln[:60]!r}"))
        elif m.group(1) not in PRINTED_LABELS:
            spaced = m.group(1).replace("-", " ")
            out.append(("note", f"## Printed: label '{m.group(1)}' is written '{spaced}' elsewhere" if spaced in PRINTED_LABELS
                        else f"## Printed: label '{m.group(1)}' is new"))
    if "Grid" in sections:
        _grid_rows(sections["Grid"], out)
    if "Clues" in sections:
        _clue_lines(sections["Clues"], out, field=True)
    return out
