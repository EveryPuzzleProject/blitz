"""A puzzle packet as text: numbering, whole-puzzle checks, and `text.md`.

A packet is one puzzle's folder as the OCR pipeline (xword-ocr) writes it:
`ocr.json` (what the OCR read, with each clue's box on the page), `page.jpg`
(and `clue_page.jpg` when the clues are on another page), `grid.png` and
`answers.png` (the grid and the printed answer key, straightened at 40 pixels
a square), and `_src/` (the pages at full resolution, for crops). Everything
here reads only that folder.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

RARE = 1.5  # a word whose zipf frequency is below this is "odd" (likely an OCR slip)
GARBLED = 0.35  # share of rough clues above which a puzzle goes to the full review
FEW_SQUARES = 2  # this many disputed squares or fewer is a text-review matter


def load(packet: Path) -> dict:
    return json.loads((packet / "ocr.json").read_text(encoding="utf-8"))


def number_grid(grid: list[str]) -> list[tuple[str, int, int, int]]:
    """Standard American numbering: (label, row, col, length) for every entry,
    Across and Down, in number order. '#' is a black square."""
    rows, cols = len(grid), len(grid[0]) if grid else 0
    white = lambda r, c: 0 <= r < rows and 0 <= c < cols and grid[r][c] != "#"
    out, n = [], 0
    for r in range(rows):
        for c in range(cols):
            if not white(r, c):
                continue
            a = not white(r, c - 1) and white(r, c + 1)
            d = not white(r - 1, c) and white(r + 1, c)
            if not (a or d):
                continue
            n += 1
            if a:
                k = 0
                while white(r, c + k):
                    k += 1
                out.append((f"A{n}", r, c, k))
            if d:
                k = 0
                while white(r + k, c):
                    k += 1
                out.append((f"D{n}", r, c, k))
    return out


def entries(ocr: dict) -> dict[str, tuple[str, list[tuple[int, int]]]]:
    """Clue label -> (answer as read from the key, its squares). Letters the
    reader wasn't sure of are lowercase; '.' is unreadable. Empty words without a key."""
    ans = ocr.get("answers")
    low = set(ocr.get("answers_low_confidence") or [])
    out = {}
    for label, r0, c0, length in number_grid(ocr["grid"]):
        sq = [(r0, c0 + k) if label[0] == "A" else (r0 + k, c0) for k in range(length)]
        word = ""
        if ans:
            for r, c in sq:
                ch = ans[r][c] if r < len(ans) and c < len(ans[r]) else "."
                word += ch.lower() if f"r{r + 1}c{c + 1}" in low else ch
        out[label] = (word, sq)
    return out


def structural_checks(ocr: dict) -> dict[str, list[str]]:
    """Whole-puzzle problems, each with the items involved."""
    found: dict[str, list[str]] = {}
    clues = ocr["clues"]
    empty = [k for k, v in clues.items() if not v.get("text", "").strip()]
    if empty:
        found["clue text missing"] = empty
    # The same text on two neighbouring clues is a reading slip (a list that
    # wrapped to the next column gets filled with copies).
    labels = list(clues)
    norm = [re.sub(r"\W+", " ", clues[k].get("text", "")).strip().lower() for k in labels]
    dup = sorted({labels[i + d] for i in range(len(labels) - 1) for d in (0, 1)
                  if len(norm[i]) >= 8 and norm[i] == norm[i + 1] and labels[i][0] == labels[i + 1][0]})
    if dup:
        found["same text on neighbouring clues"] = dup
    numbered = set(entries(ocr))
    if numbered != set(clues):
        found["clue numbers don't match the grid"] = sorted(numbered ^ set(clues))
    if ocr.get("grid_asymmetric_squares"):
        found["grid not symmetric"] = ocr["grid_asymmetric_squares"]
    ans, grid = ocr.get("answers"), ocr.get("grid") or []
    if ans and grid and (len(ans), len(ans[0])) != (len(grid), len(grid[0])):
        found["answer key is a different size from the grid"] = [
            f"key {len(ans)}x{len(ans[0])}, grid {len(grid)}x{len(grid[0])}"]
    if ans:
        diff = [f"r{i + 1}c{j + 1}" for i, row in enumerate(grid) for j, ch in enumerate(row)
                if i < len(ans) and j < len(ans[i]) and (ch == "#") != (ans[i][j] == "#")]
        if diff:
            found["black squares differ from the answer key"] = diff
    return found


@lru_cache(maxsize=None)
def _zipf(word: str) -> float:
    from wordfreq import zipf_frequency

    return zipf_frequency(word, "en")


_SUFFIXES = ("s", "es", "er", "ers", "est", "ed", "ing", "ish", "ly", "less", "maker", "ese")


def _plausible(w: str) -> bool:
    """A word, or a common word with a possessive or contraction ('s, 'd, 'll)
    or an ordinary ending (corkers, unkindest, owlish): not an OCR slip."""
    low = w.lower()
    if _zipf(low) >= RARE:
        return True
    bare = re.sub(r"'(s|d|ll|ve|re|m)$", "", low)  # not n't: "ean't" is a slip for "can't"
    if bare != low and len(bare) >= 4 and _zipf(bare) >= RARE:  # short stems: "wal's" is a slip for "walls"
        return True
    low = bare
    for suf in _SUFFIXES:
        if low.endswith(suf) and len(low) - len(suf) >= 3:
            stem = low[:-len(suf)]
            # the stem must be a common word, so a slip that happens to end in -er stays odd
            if any(_zipf(s) >= RARE + 1 for s in (stem, stem + "e", stem[:-1] if stem[-1:] == stem[-2:-1] else stem)):
                return True
    return False


def odd_words(text: str) -> list[str]:
    """Words a proofreader would stop at: not plausible English (OCR slips like
    "intoxieating"), or a letter-digit mix."""
    out = []
    for m in re.finditer(r"[A-Za-z0-9]+(?:-[A-Za-z]+)*(?:'[a-z]+)?", text):
        whole = m.group(0)
        parts = whole.split("-")
        if len(parts) > 1 and _plausible("".join(parts)):  # demi-tasse
            continue
        for i, w in enumerate(parts):
            if any(ch.isdigit() for ch in w):
                if any(ch.isalpha() for ch in w) and not re.fullmatch(r"\d+(st|nd|rd|th|s)", w):
                    out.append(w)
            elif len(w) > 1 and not _plausible(w):
                out.append(w)
    return out


TEXT_FLAGS = ("spell", "low-ocr-score", "text-moved", "missing", "line-recovered", "no-text")
FLAG_HELP = {  # what the OCR's clue flags mean, for text.md
    "spell": "(spell:x>y) the OCR read x and the pipeline already changed it to y (the text shows y). "
             "Usually right; check that y is what's printed, since a real misprint must stay as printed.",
    "number-missing": "the OCR didn't read the clue's printed number (usually the box cut it off; often a "
                      "false alarm).",
    "number-corrected": "(number-corrected:N) the OCR read the number as N and the pipeline renumbered the clue "
                        "to fit the grid.",
    "low-ocr-score": "the OCR wasn't confident about this line.",
    "text-moved": "text was moved here from a neighbouring clue.",
    "line-recovered": "a line found next to the clue was added to it; check it belongs.",
    "missing": "the OCR found no text for this clue.",
    "no-text": "the clue's box held no text (a picture clue?).",
}
_MERGED = re.compile(r"\S\s+\d{1,3}\s*[.,]\s+[A-Z]")  # "...a kiss. 23. What..." inside one clue


def route(ocr: dict) -> tuple[str, list[str]]:
    """Which review a puzzle needs: "text" (text first, crops on request) or
    "full" (every image), with the reasons. Reviewers handle both; "full" says
    to expect a whole-puzzle problem and to escalate what can't be settled."""
    reasons = [f"{k}: {', '.join(v[:6])}" for k, v in structural_checks(ocr).items()
               if not (k in ("black squares differ from the answer key", "grid not symmetric")
                       and len(v) <= FEW_SQUARES)]
    if not ocr.get("answers"):
        reasons.append("no answer key")
    clues = list(ocr["clues"].values())
    rough = sum(1 for v in clues if odd_words(v.get("text", ""))
                or any(f.split(":")[0] in TEXT_FLAGS for f in v.get("flags") or []))
    if clues and rough / len(clues) > GARBLED:
        reasons.append(f"much garbled text ({rough} of {len(clues)} clues)")
    return ("full" if reasons else "text"), reasons


def text_view(ocr: dict) -> str:
    """The packet as text: what a proofreader reads before looking at the scan."""
    ent = entries(ocr)
    has_key = bool(ocr.get("answers"))
    lines = [f"# {ocr['xdid']}", "",
             f"Title: {ocr.get('title', '')}",
             f"Byline: {ocr.get('byline', '')}",
             f"Author: {ocr.get('author', '')}"]
    for k, t in (ocr.get("captions") or {}).items():
        lines.append(f"Caption {k}: {t}")
    lines += ["", "## Answer key" if has_key else "## Grid (no answer key linked)",
              "Lowercase = the letter reader wasn't sure; '.' = unreadable; '#' = black square.", "```"]
    rows = ocr["answers"] if has_key else ocr["grid"]
    low = set(ocr.get("answers_low_confidence") or [])
    for i, row in enumerate(rows):
        cells = "".join(ch.lower() if f"r{i + 1}c{j + 1}" in low else ch for j, ch in enumerate(row))
        lines.append(f"{i + 1:>2} {' '.join(cells)}")
    lines.append("```")
    checks = structural_checks(ocr)
    if checks:
        lines += ["", "## Structural checks"] + [f"- {k}: {', '.join(v[:12])}" for k, v in checks.items()]
    merged = [k for k, v in ocr["clues"].items() if _MERGED.search(v.get("text", ""))]
    if merged:
        lines += ["", f"Clue text that seems to run into another clue: {', '.join(merged)}"]
    used = {f.split(":")[0] for v in ocr["clues"].values() for f in v.get("flags") or []}
    legend = [f"- {k}: {FLAG_HELP[k]}" for k in FLAG_HELP if k in used]
    if legend:
        lines += ["", "Flags on the clues below:"] + legend
    for d, name in (("A", "Across"), ("D", "Down")):
        lines += ["", f"## {name}"]
        for k, v in ocr["clues"].items():
            if k[0] != d:
                continue
            word = ent.get(k, ("", []))[0]
            notes = list(v.get("flags") or [])
            odd = odd_words(v.get("text", ""))
            if odd:
                notes.append("odd: " + " ".join(odd))
            flags = f"  [{'; '.join(notes)}]" if notes else ""
            lines.append(f"{k:<5} {word or '?':<16} {v.get('text', '')}{flags}")
    boxes = [f"{k} {','.join(str(round(x)) for x in v['box'])}" for k, v in ocr["clues"].items() if v.get("box")]
    if boxes:  # for box: crops, e.g. widening a clue whose text runs past its box
        lines += ["", "## Clue boxes (x0,y0,x1,y1 in scan pixels)", "  ".join(boxes)]
    return "\n".join(lines) + "\n"


def write_text(packet: Path) -> tuple[str, list[str]]:
    """Write text.md into the packet; returns its route (lane, reasons)."""
    ocr = load(packet)
    (packet / "text.md").write_text(text_view(ocr), encoding="utf-8")
    return route(ocr)
