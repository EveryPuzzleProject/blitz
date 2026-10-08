"""Turning a reviewer's draft into review.json, and choosing what it must see.

A reviewer (Claude or a person) reads text.md, asks for crops with `blitz
sheets`, and writes draft.json. `finish` turns that into review.json:
corrected answer words become square fixes, and a correction to anything
never shown on a sheet becomes "unsure": nothing is fixed from the text alone.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .crops import TARGET
from .packet import (TEXT_FLAGS, _MERGED, entries, grid_fix_check, is_notice, load, odd_words, proposals, proposed_text,
                     structural_checks, title_check)

MAX_CROPS = 60
FEW_DISPUTED = 4  # more disputed squares than this get one whole-grid crop instead
UNRELIABLE = ('number-corrected', 'text-moved', 'line-recovered', 'low-ocr-score', 'missing', 'no-text')
MAX_BOX_H = 400  # a box: crop taller than this isn't a look at one clue
ITEM_OK = re.compile(r"clue:[AD]\d+|cell:r\d+c\d+|grid:r\d+c\d+|other:\d+|meta:(title|author|byline|puzzle_number)")


def _in_clue_area(ocr: dict, r: tuple, image: str | None = None) -> bool:
    """Does the region overlap the area the OCR found clues in (not the grid or the title)?"""
    boxes = [v["box"] for v in ocr["clues"].values() if v.get("box") and v.get("image") == image]
    if not boxes:
        return True
    x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
    x1, y1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
    return r[0] < x1 and x0 < r[2] and r[1] < y1 and y0 < r[3]


def covered(item: str, seen: list[str], ocr: dict, regions: dict | None = None) -> bool:
    """Was this item on a crop the reviewer saw? `regions` is the draft's
    {"clue:D56": [x0, y0, x1, y1]}: where the reviewer says a clue really is."""
    try:
        return _covered(item, seen, ocr, regions)
    except (ValueError, IndexError):
        return False


def _covered(item: str, seen: list[str], ocr: dict, regions: dict | None = None) -> bool:
    kind, _, key = item.partition(":")
    if kind in ("meta", "other"):
        return True  # title, byline and captions are always shown
    if kind == "clue":
        if f"clue:{key}" in seen:
            return True
        clue = ocr["clues"].get(key) or {}
        b = clue.get("box")
        # Where the OCR put this clue can't be trusted when it flagged the clue itself (renumbered, text
        # moved in, low score, merged with the next one): then any clue-sized box: crop counts as a look.
        shaky = any(f.split(":")[0] in UNRELIABLE for f in clue.get("flags") or []) or bool(_MERGED.search(clue.get("text", "")))
        region = (regions or {}).get(f"clue:{key}")
        img = clue.get("image")  # a clue printed on the next page (continued_page.jpg): next: crops
        for t in seen:
            if t.startswith(("box:", "next:")):
                if not b:  # the OCR never found this clue: the reviewer's own box crop is the evidence
                    return True
                if t.startswith("next:") != bool(img):
                    continue  # a crop of the other page
                x0, y0, x1, y1 = (float(v) for v in t.partition(":")[2].split(","))
                if b[0] < x1 and x0 < b[2] and b[1] < y1 and y0 < b[3]:
                    return True
                if region and region[0] < x1 and x0 < region[2] and region[1] < y1 and y0 < region[3]:
                    return True  # the reviewer said where the clue really is, and looked there
                if shaky and y1 - y0 <= MAX_BOX_H and _in_clue_area(ocr, (x0, y0, x1, y1), img):
                    return True
        return False
    if kind in ("cell", "grid"):
        r, c = (int(v) for v in key[1:].split("c"))
        for t in seen:
            tk, _, tv = t.partition(":")
            if tk == kind and tv == "all":
                return True
            if tk == kind and tv:
                rr, cc = (int(v) for v in tv[1:].split("c"))
                if abs(rr - r) <= 1 and abs(cc - c) <= 1:
                    return True
            if kind == "cell" and ((tk == "row" and int(tv) == r) or (tk == "col" and int(tv) == c)):
                return True
            if kind == "cell" and tk == "entry" and (r - 1, c - 1) in entries(ocr).get(tv, ("", []))[1]:
                return True
        return False
    return True


def choose_targets(ocr: dict, asked: list[str]) -> list[str]:
    """The crops to show: title, byline and captions, the reviewer's own list,
    and what a careful proofreader would never skip whether or not it was
    asked for (odd words, flagged clues, unsure letters, disputed squares)."""
    targets = []
    for t in asked:
        m = TARGET.fullmatch(t.strip())
        if m and m.group(0) not in targets:
            targets.append(m.group(0))
    caps = [k for k, t in (ocr.get("captions") or {}).items() if not is_notice(t)]  # the recurring notice needs no look
    top = ["meta:top"] if title_check(ocr) or "meta:top" in targets else []  # the page-top band, for a title that may be wrong
    targets = (["meta:title", "meta:byline"] + top + [f"caption:{k}" for k in caps]
               + [t for t in targets if t.startswith("caption:") and t[8:] not in caps]  # asked for by name
               + [t for t in targets if not t.startswith(("meta:", "caption:"))])
    props = proposals(ocr)
    for k, v in ocr["clues"].items():
        rough = (odd_words(v.get("text", "")) or k in props
                 or any(f.split(":")[0] in TEXT_FLAGS for f in v.get("flags") or []))
        if rough and v.get("box") and f"clue:{k}" not in targets:  # no box, no crop: the text says it's missing
            targets.append(f"clue:{k}")
    checks = structural_checks(ocr)
    disputed = checks.get("black squares differ from the answer key", []) + [
        sq for pair in checks.get("grid not symmetric", []) for sq in pair.split("/")]
    if len(disputed) > FEW_DISPUTED:  # often a grid printed that way: one look at the whole of it
        disputed = ["all"]
    for sq in disputed:
        for t in (f"grid:{sq}", f"cell:{sq}"):
            if t not in targets:
                targets.append(t)
    for cell in ocr.get("answers_low_confidence") or []:
        if not covered("cell:" + cell, targets, ocr):
            targets.append("cell:" + cell)
    return targets[:MAX_CROPS + 3 + len(ocr.get("captions") or {})]


def _as_list(v, key: str = "item") -> list[dict]:
    """Accept {"clue:A1": "text"} as well as [{"item": "clue:A1", "value": "text"}]."""
    if isinstance(v, dict):
        return [{key: k, "value": x} for k, x in v.items()]
    return list(v or [])


def _as_dict(v) -> dict:
    if isinstance(v, dict):
        return v
    return {str(x): "" for x in v or []}


def finish(ocr: dict, draft: dict, seen: list[str]) -> tuple[dict, list[str]]:
    """review.json from a draft. Returns (review, what was ignored)."""
    ent = entries(ocr)
    corrections, ignored = {}, []
    unsure = {i["item"]: i["value"] for i in _as_list(draft.get("unsure"))}
    fixes = _as_list(draft.get("corrections"))
    regions = draft.get("regions") if isinstance(draft.get("regions"), dict) else {}
    for a in _as_list(draft.get("answers"), "entry"):  # a corrected word -> the squares that change
        word, sq = ent.get(a["entry"].strip().removeprefix("entry:"), ("", []))
        value = a["value"].strip().upper()
        if not sq or len(value) != len(sq) or not ocr.get("answers"):
            ignored.append(f"entry:{a['entry']}={a['value']}")
            continue
        for (r, c), ch in zip(sq, value):
            if ocr["answers"][r][c].upper() != ch:
                fixes.append({"item": f"cell:r{r + 1}c{c + 1}", "value": ch})
    for c in fixes:
        item, value = c["item"].strip(), c["value"]
        clue_text = (ocr["clues"].get(item[5:]) or {}).get("text", "x") if item.startswith("clue:") else ""
        if (not ITEM_OK.fullmatch(item)
                or (item.startswith("grid:") and value not in ("#", "."))
                or (item.startswith("cell:") and len(value) > 1)
                or (item.startswith("clue:") and re.fullmatch(r"[A-Z]+", value)
                    and not re.fullmatch(r"[A-Z ]+", clue_text))):  # an answer word put in a clue
            ignored.append(f"{item}={value}")
            continue
        if covered(item, seen, ocr, regions):
            corrections[item] = value
        else:
            unsure[item] = f"not checked against the scan (proposed: {value})"
    # What text.md showed as the tools' proposal (page number, "Solution of..." heading, broken clue number
    # taken off) is the reviewer's text for that clue unless they gave their own.
    proposed = {}
    for k, (text, _) in proposals(ocr).items():
        item = f"clue:{k}"
        if item in corrections or item in unsure or any(c["item"].strip() == item for c in fixes):
            continue
        if covered(item, seen, ocr, regions):
            corrections[item] = proposed[item] = text
        else:
            unsure[item] = f"not checked against the scan (proposed: {text})"
    for k, t in (ocr.get("captions") or {}).items():  # the magazine's recurring notice is never part of a puzzle
        if is_notice(t) and f"other:{k}" not in corrections and not any(c["item"].strip() == f"other:{k}" for c in fixes):
            corrections[f"other:{k}"] = proposed[f"other:{k}"] = ""
    escalate = draft.get("escalate") or ""
    review = {
        "escalate": escalate, "ready": bool(draft.get("ready")) and not escalate,
        "remaining": draft.get("remaining", "minor"), "remaining_note": draft.get("remaining_note", ""),
        "note": draft.get("note", ""), "corrections": corrections,
        "sic": {i["item"].partition(":")[2] or i["item"]: i["value"] for i in _as_list(draft.get("sic"))},
        "regions": {}, "confirm": list(draft.get("confirm") or []), "unsure": unsure,
    }
    if draft.get("tool_notes"):
        review["tool_notes"] = list(draft["tool_notes"])
    # Odd words still in the finished clues: each must be corrected, kept as sic, or said to be printed so.
    ok = {k.partition(":")[2] or k for k in list(review["sic"]) + list(_as_dict(draft.get("as_printed")))}
    left = {}
    for k, v in ocr["clues"].items():
        text = corrections.get(f"clue:{k}", v.get("text", ""))
        read = set(odd_words(v.get("text", "")))  # only the OCR's own odd words: not the reviewer's
        odd = [w for w in odd_words(text) if w in read] if text and k not in ok and f"clue:{k}" not in unsure else []
        if odd:
            left[k] = odd
    if draft.get("as_printed"):
        review["as_printed"] = _as_dict(draft["as_printed"])
    if left:
        review["odd_left"] = left
    junk = {}  # a page number or heading still on a clue the reviewer typed out
    for item, value in corrections.items():
        k = item[5:]
        if item.startswith("clue:") and item not in proposed and k in ocr["clues"] and value:
            again, notes = proposed_text({**ocr, "clues": {**ocr["clues"], k: {**ocr["clues"][k], "text": value}}}, k)
            if notes and again != value and not all(n.startswith("put back") for n in notes):
                junk[k] = notes
    if junk:
        review["junk_left"] = junk
    final_title = corrections.get("meta:title", ocr.get("title", ""))
    bad = title_check(ocr, final_title)
    if bad and "meta:title" not in review["confirm"]:
        review["title_left"] = {"title": final_title, "why": bad[0], "probably": bad[1]}
    gfc = grid_fix_check(ocr, corrections)
    if gfc and "grid:fix" not in review["confirm"]:
        review["grid_check"] = gfc
    if proposed:
        review["from_text_md"] = sorted(proposed)
    if ignored:
        review["note"] = (review["note"] + " Ignored (not a valid correction): " + "; ".join(ignored)).strip()
    return review, ignored


def finish_packet(packet: Path, model: str = "") -> tuple[dict, list[str]]:
    """Read draft.json and sheets/shown.json, write review.json."""
    ocr = load(packet)
    draft = json.loads((packet / "draft.json").read_text(encoding="utf-8"))
    shown = packet / "sheets" / "shown.json"
    seen = json.loads(shown.read_text(encoding="utf-8"))["shown"] if shown.exists() else []
    review, ignored = finish(ocr, draft, seen)
    if model:
        review["model"] = model
    (packet / "review.json").write_text(json.dumps(review, indent=1, ensure_ascii=False), encoding="utf-8")
    return review, ignored


def feedback(packets: list[Path]) -> str:
    """The reviewers' tool_notes across puzzles, grouped by kind, as Markdown."""
    groups: dict[str, list[tuple[str, str, str]]] = {}
    unchecked, sic, escalated = [], [], []
    for d in packets:
        f = d / "review.json"
        if not f.exists():
            continue
        rv = json.loads(f.read_text(encoding="utf-8"))
        x = d.name
        for n in rv.get("tool_notes") or []:
            if isinstance(n, str):
                n = {"kind": "other", "note": n}
            groups.setdefault(str(n.get("kind") or "other"), []).append(
                (x, str(n.get("target", "")), str(n.get("note", ""))))
        unchecked += [f"{x} {k}" for k, v in (rv.get("unsure") or {}).items() if str(v).startswith("not checked")]
        sic += [f"{x} {k}: {v}" for k, v in (rv.get("sic") or {}).items()]
        if rv.get("escalate"):
            escalated.append(f"{x}: {rv['escalate']}")
    lines = ["# Reviewer feedback", ""]
    for kind, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        lines += [f"## {kind}: {len(items)} notes, {len({x for x, _, _ in items})} puzzles", ""]
        lines += [f"- {x}{' ' + t if t else ''}: {n}" for x, t, n in items] + [""]
    for title, items in (("Escalated", escalated), ("Corrections not applied (never on a sheet)", unchecked),
                         ("Kept as sic (check these are clean misprints, not damaged type)", sic)):
        if items:
            lines += [f"## {title}: {len(items)}", ""] + [f"- {i}" for i in items] + [""]
    return "\n".join(lines)
