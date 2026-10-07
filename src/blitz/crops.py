"""Crops of a packet's scan, and contact sheets of them for a reviewer to read.

Targets (what a reviewer can ask to see):
- clue:A14            the clue's printed text, outlined, with a line above and below
- box:x0,y0,x1,y1     any region, in the pixels the clue boxes use (page.jpg's)
- meta:title, meta:byline, caption:2
- entry:A14           that answer in the printed answer key
- cell:r5c7           a key square and its neighbours; row:5, col:7; cell:all for the whole key
- grid:r5c7           the empty puzzle grid around a square; grid:all for the whole grid
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .packet import entries, load

CELL_PX = 40  # grid.png / answers.png have this many pixels a square
SHEET_W, SHEET_H = 1000, 1400  # a contact sheet stays under the size a model would shrink
ORANGE = (230, 160, 0)

TARGET = re.compile(r"(clue:[AD]\d+|entry:[AD]\d+|cell:r\d+c\d+|grid:r\d+c\d+|cell:all|grid:all|row:\d+|col:\d+"
                    r"|box:\d+(\.\d+)?,\d+(\.\d+)?,\d+(\.\d+)?,\d+(\.\d+)?|meta:(title|byline)|caption:\d+)")


def _page(packet: Path, ocr: dict, name: str) -> tuple[Image.Image, float]:
    """The page at the best resolution the packet has, and the factor from
    box pixels (page.jpg's) to that image's pixels."""
    full = packet / "_src" / name
    if full.exists():
        return Image.open(full).convert("L"), 1.0 / (ocr.get("scales") or {}).get(name, 1.0)
    return Image.open(packet / name).convert("L"), 1.0


def crop(packet: Path, target: str, ocr: dict | None = None) -> Image.Image | str:
    """One target's crop, or a string saying why there is none."""
    ocr = ocr or load(packet)
    kind, _, key = target.partition(":")
    if kind in ("clue", "box", "meta", "caption"):
        name = "page.jpg" if kind in ("meta", "caption") else ocr.get("clue_image", "page.jpg")
        img, f = _page(packet, ocr, name)
        if kind == "clue":
            box = (ocr["clues"].get(key) or {}).get("box")
        elif kind in ("meta", "caption"):
            box = (ocr.get("meta_boxes") or {}).get(key if kind == "meta" else f"other{key}")
        else:
            box = [float(v) for v in key.split(",")]
        if not box:
            return (f"no box for {target} (a clue the OCR never found: crop its place with box:)" if kind == "clue"
                    else f"this packet has no box for {target}: look at page.jpg, or crop the place with box:")
        if kind == "clue":  # show the whole line: OCR boxes often stop short (or cover only the number)
            h = box[3] - box[1]
            col = [b["box"] for b in ocr["clues"].values() if b.get("box") and abs(b["box"][0] - box[0]) < 3 * max(h, 12)]
            box = [box[0], box[1], max([box[2]] + [b[2] for b in col]), box[3]]
        x0, y0, x1, y1 = (v * f for v in box)
        line = max(12.0, (y1 - y0) if kind != "box" else 30.0)
        if kind == "clue":
            line = min(line, 60.0)
        m = line if kind == "clue" else 0.0  # a clue gets a line of context above and below
        X0, Y0 = max(0, int(x0 - 0.3 * line - m)), max(0, int(y0 - m))
        X1, Y1 = min(img.width, int(x1 + 0.3 * line + m)), min(img.height, int(y1 + m))
        if X1 <= X0 or Y1 <= Y0:
            return f"{target} is outside the page"
        out = img.crop((X0, Y0, X1, Y1)).convert("RGB")
        if kind == "clue":
            ImageDraw.Draw(out).rectangle((x0 - X0 - 3, y0 - Y0 - 3, x1 - X0 + 3, y1 - Y0 + 3), outline=ORANGE, width=2)
        if f == 1.0 and line < 40:  # no full-resolution page: enlarge to about 40 px a line
            k = 40 / line
            out = out.resize((int(out.width * k), int(out.height * k)), Image.BICUBIC)
        return out
    src = "grid.png" if kind == "grid" else "answers.png"
    if not (packet / src).exists():
        return f"no {src} in this packet"
    img = Image.open(packet / src).convert("L")
    rows, cols = len(ocr["grid"]), len(ocr["grid"][0])
    if kind in ("cell", "grid") and key == "all":
        r0, r1, c0, c1 = 0, rows, 0, cols
    elif kind in ("cell", "grid"):
        r, c = (int(v) - 1 for v in key[1:].split("c"))
        if not (0 <= r < rows and 0 <= c < cols):
            return f"{target} is outside the {rows}x{cols} grid"
        r0, r1, c0, c1 = max(0, r - 1), min(rows, r + 2), max(0, c - 1), min(cols, c + 2)
    elif kind == "row":
        r0, r1, c0, c1 = int(key) - 1, int(key), 0, cols
    elif kind == "col":
        r0, r1, c0, c1 = 0, rows, int(key) - 1, int(key)
    elif kind == "entry":
        sq = entries(ocr).get(key, ("", []))[1]
        if not sq:
            return f"no entry {key}"
        r0, r1 = min(r for r, _ in sq), max(r for r, _ in sq) + 1
        c0, c1 = min(c for _, c in sq), max(c for _, c in sq) + 1
    else:
        return f"unknown target {target!r}"
    if not (0 <= r0 < r1 <= rows and 0 <= c0 < c1 <= cols):
        return f"{target} is outside the {rows}x{cols} grid"
    out = img.crop((c0 * CELL_PX, r0 * CELL_PX, c1 * CELL_PX, r1 * CELL_PX))
    if key != "all":
        out = out.resize((out.width * 2, out.height * 2), Image.BICUBIC)  # 80 px squares: easy to read
    return out.convert("RGB")


def _font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def contact_sheets(tiles: list[tuple[str, Image.Image]]) -> list[tuple[list[str], Image.Image]]:
    """Stack labelled crops into sheets of at most SHEET_W x SHEET_H."""
    sheets, cur, labels, h = [], [], [], 0
    font = _font(20)

    def flush():
        nonlocal cur, labels, h
        if cur:
            sheet = Image.new("RGB", (SHEET_W, h), "white")
            y = 0
            for t in cur:
                sheet.paste(t, (0, y))
                y += t.height
            sheets.append((labels, sheet))
        cur, labels, h = [], [], 0

    for label, img in tiles:
        s = min(1.0, SHEET_W / img.width, (SHEET_H - 30) / img.height)
        if s < 1.0:
            img = img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.LANCZOS)
        tile = Image.new("RGB", (SHEET_W, img.height + 30), "white")
        d = ImageDraw.Draw(tile)
        d.text((4, 4), label, fill=(200, 0, 0), font=font)
        tile.paste(img, (0, 30))
        d.line((0, tile.height - 1, SHEET_W, tile.height - 1), fill=(160, 160, 160), width=2)
        if h + tile.height > SHEET_H:
            flush()
        cur.append(tile)
        labels.append(label)
        h += tile.height
    flush()
    return sheets


def make_sheets(packet: Path, targets: list[str], fresh: bool = False) -> dict:
    """Crop the targets onto contact sheets in <packet>/sheets/, adding to the
    sheets already there (only what isn't shown yet). Returns what was made:
    {"sheets": [{"file", "crops"}], "missed": [(target, why)]}. shown.json
    keeps every crop shown so far: `finish` only applies corrections to those."""
    out = packet / "sheets"
    if fresh:
        shutil.rmtree(out, ignore_errors=True)
    out.mkdir(exist_ok=True)
    state_file = out / "shown.json"
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {"shown": [], "sheets": []}
    ocr = load(packet)
    tiles, missed, already = [], [], []
    where = {c: Path(sh["file"]).name for sh in state["sheets"] for c in sh["crops"]}
    for t in targets:
        if t in state["shown"]:
            already.append((t, where.get(t, "")))
            continue
        img = crop(packet, t, ocr)
        if isinstance(img, str):
            missed.append((t, img))
        else:
            tiles.append((t, img))
    made = []
    for labels, sheet in contact_sheets(tiles):
        f = out / f"sheet_{len(state['sheets']) + 1}.png"
        sheet.save(f)
        entry = {"file": str(f), "crops": labels}
        state["sheets"].append(entry)
        state["shown"] += labels
        made.append(entry)
    state_file.write_text(json.dumps(state, indent=1), encoding="utf-8")
    return {"sheets": made, "missed": missed, "already": already}
