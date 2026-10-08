"""A puzzle packet as text: numbering, whole-puzzle checks, and `text.md`.

A packet is one puzzle's folder as the OCR pipeline (xword-ocr) writes it:
`ocr.json` (what the OCR read, with each clue's box on the page), `page.jpg`
(and `clue_page.jpg` when the clues are on another page; `continued_page.jpg`
when a clue list goes on to another page, its clues naming it as their
"image"), `grid.png` and
`answers.png` (the grid and the printed answer key, straightened at 40 pixels
a square), and `_src/` (the pages at full resolution, for crops). Everything
here reads only that folder.
"""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
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


def grid_fix_check(ocr: dict, corrections: dict) -> dict | None:
    """A reviewer's grid fixes (grid:r1c5 = "#") change which squares get numbers. Compare how the grid's entries
    line up with the clue list the magazine printed (as the OCR read it) before and after the fixes. Returns None
    if there are no grid fixes or the numbering is no worse; otherwise what got worse: the entries the fix created
    that have no printed clue ("created"), and any of those the reviewer then marked "[no clue printed]"
    ("covered"). A grid fix that fits the printed numbers makes the two lists agree better, not worse."""
    fixes = {k[5:]: v for k, v in corrections.items() if k.startswith("grid:") and re.fullmatch(r"r\d+c\d+", k[5:])}
    if not fixes or not ocr.get("grid"):
        return None
    grid = [list(r) for r in ocr["grid"]]
    for sq, v in fixes.items():
        r, c = (int(x) for x in sq[1:].split("c"))
        if 0 < r <= len(grid) and 0 < c <= len(grid[0]):
            grid[r - 1][c - 1] = "#" if v == "#" else "."
    printed = set(ocr["clues"])
    labels = lambda g: {lab for lab, *_ in number_grid(["".join(row) for row in g])}
    before, after = sorted(labels(ocr["grid"]) ^ printed), sorted(labels(grid) ^ printed)
    if len(after) <= len(before):
        return None
    created = sorted((labels(grid) - labels(ocr["grid"])) - printed)
    covered = [k for k in created if corrections.get(f"clue:{k}") == NO_CLUE]
    return {"before": before, "after": after, "created": created, "covered": covered}


NO_CLUE = "[no clue printed]"  # how the log records a clue the magazine never printed


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
    cont = list_continues(ocr)
    if cont:
        found["clue list continues on another page"] = list(cont.values())
    gone = {k for lab in cont for k in entries(ocr) if k[0] == lab}  # reported once, above
    empty = [k for k, v in clues.items() if not v.get("text", "").strip() and k not in gone]
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


GRADES = {"check": "check closely", "look": "worth a look", "clean": "looks clean"}


def checkup(ocr: dict, review: dict) -> dict:
    """What a checker should know about a reviewed puzzle, worst first. Each warning is
    {id, level: high | medium | info, text, items}; the grade is the worst level:
      check  something structural or unsettled (a clue or entry that doesn't pair up, a grid the reviewer
             changed, a key that doesn't fit, items the reviewer was unsure of, a very heavy edit)
      look   worth knowing (no answer key, a grid that isn't symmetric, a lot of hard-to-read key letters,
             a remaining issue the reviewer noted)
      clean  nothing beyond the information notes."""
    corr = review.get("corrections") or {}
    out: list[dict] = []
    add = lambda id, level, text, items=(): out.append({"id": id, "level": level, "text": text, "items": list(items)})
    grid = [list(r) for r in ocr["grid"]]
    changed = []
    for k, v in corr.items():
        m = re.fullmatch(r"grid:r(\d+)c(\d+)", k)
        if m and 0 < int(m[1]) <= len(grid) and 0 < int(m[2]) <= len(grid[0]) and (grid[int(m[1]) - 1][int(m[2]) - 1] == "#") != (v == "#"):
            changed.append((k, grid[int(m[1]) - 1][int(m[2]) - 1] == "#", v == "#"))
            grid[int(m[1]) - 1][int(m[2]) - 1] = "#" if v == "#" else "."
    # the clue list as it will be published: the OCR's, with the review's text, minus clues the review removed
    texts = {k: v.get("text", "") for k, v in ocr["clues"].items()}
    for k, v in corr.items():
        if k.startswith("clue:"):
            texts[k[5:]] = v
    texts = {k: v for k, v in texts.items() if corr.get("clue:" + k) != ""}
    entries_ = {lab for lab, *_ in number_grid(["".join(r) for r in grid])}
    printed_none = sorted(k for k, v in texts.items() if v == NO_CLUE)
    missing = sorted(entries_ - set(texts))
    extra = sorted(set(texts) - entries_)
    blank_ok = {str(k).partition(":")[2] or str(k) for k in (review.get("as_printed") or {})}  # printed blank on purpose
    empty = sorted(k for k, v in texts.items() if not v.strip() and k not in blank_ok)
    blank = sorted(k for k, v in texts.items() if not v.strip() and k in blank_ok)
    if review.get("escalate"):
        add("escalated", "high", f"The reviewer couldn't finish this one: {review['escalate']}")
    elif not review.get("ready"):
        add("not-ready", "high", "The reviewer marked this puzzle as needing a person.")
    if changed:
        say = ", ".join(f"{k[5:]}: {'black' if was else 'white'} → {'black' if now else 'white'}" for k, was, now in changed)
        add("grid-changed", "high", f"The reviewer changed the grid ({say}). That is rare and changes the numbering: check each square against the scan.",
            [k for k, *_ in changed])
    gc = review.get("grid_check")
    if gc:
        add("grid-numbering", "high", f"The grid change makes the numbering worse: {', '.join(gc.get('created') or [])} would have no printed clue.", gc.get("created"))
    if missing:
        add("missing-clues", "high", f"{len(missing)} {'entry in the grid has' if len(missing) == 1 else 'entries in the grid have'} no clue: {', '.join(missing)}.", missing)
    if extra:
        add("extra-clues", "high", f"{len(extra)} {'clue has' if len(extra) == 1 else 'clues have'} no matching entry in the grid: {', '.join(extra)}.", extra)
    if empty:
        add("empty-clues", "high", f"{len(empty)} {'clue has' if len(empty) == 1 else 'clues have'} no text: {', '.join(empty)}.", empty)
    sc = structural_checks({**ocr, "grid": ["".join(r) for r in grid]})
    for key, text in (("answer key is a different size from the grid", "The answer key is a different size from the grid."),
                      ("black squares differ from the answer key", "The grid's black squares differ from the answer key's.")):
        if key in sc:
            add("key-mismatch", "high", text, sc[key][:8])
    unsure = review.get("unsure") or {}
    # what the reviewer couldn't settle: punctuation is a smaller worry than letters, or text the scan cuts off
    punct = {k: v for k, v in unsure.items() if "punctuation" in str(v).lower()}
    letters = {k: v for k, v in unsure.items() if k not in punct}
    label = lambda d: ", ".join(f"{k.partition(':')[2] or k} ({v})" for k, v in sorted(d.items())[:6]) + (" …" if len(d) > 6 else "")
    if letters:
        add("unsure", "high", f"The reviewer wasn't sure about: {label(letters)}.", sorted(letters))
    if punct:
        add("unsure-punctuation", "medium", f"The reviewer wasn't sure of the punctuation in: {label(punct)}.", sorted(punct))
    nclue = sum(1 for k in corr if k.startswith("clue:"))
    if nclue >= 40:
        add("heavy-edit", "high", f"Heavily corrected: {nclue} clue corrections (most puzzles have about 6).")
    elif nclue >= 20:
        add("heavy-edit", "medium", f"Heavily corrected: {nclue} clue corrections (most puzzles have about 6).")
    rem = str(review.get("remaining") or "").lower()
    if rem in ("major", "blocker"):
        add("remaining", "high", "The reviewer left a " + rem + " issue: " + (review.get("remaining_note") or "(no note)"))
    elif rem == "minor":
        add("remaining", "medium", "The reviewer left a minor issue: " + (review.get("remaining_note") or "(no note)"))
    if not ocr.get("answers"):
        add("no-answers", "medium", "No answer key: the answers for this puzzle weren't found (often printed in a later issue), so they can't be checked; only the clues, grid and numbering are here.")
    else:
        hard = [c for c in (ocr.get("answers_low_confidence") or [])]
        if len(hard) >= 8:
            add("hard-letters", "medium", f"{len(hard)} answer-key letters were hard to read (the reviewer has checked them).", hard[:12])
    if ocr.get("grid_asymmetric_squares"):
        confirmed = any(re.fullmatch(r"grid:r\d+c\d+/r\d+c\d+", c) for c in review.get("confirm") or [])
        add("asymmetric", "info" if confirmed else "medium", "The grid isn't symmetric" + (" (the reviewer confirmed it is printed that way)." if confirmed else "."))
    if printed_none:
        add("no-clue-printed", "info", f"The magazine printed no clue for {', '.join(printed_none)}.", printed_none)
    if blank:
        add("blank-clue", "info", f"The clue for {', '.join(blank)} is printed blank (kept as printed).", blank)
    if review.get("sic"):
        add("sic", "info", f"{len(review['sic'])} printed {'misprint' if len(review['sic']) == 1 else 'misprints'} kept as printed.", sorted(review["sic"]))
    if ocr.get("continued_page"):
        add("continued", "info", "The clue list continues on the next page of the issue; those clues come from there.")
    rank = {"high": 0, "medium": 1, "info": 2}
    out.sort(key=lambda w: rank[w["level"]])
    grade = "check" if any(w["level"] == "high" for w in out) else "look" if any(w["level"] == "medium" for w in out) else "clean"
    return {"grade": grade, "warnings": out}


CONTINUES_MIN = 10  # a list with at least this many clues without text ...
CONTINUES_SHARE = 0.5  # ... and at least this share of its entries probably goes on elsewhere


def list_continues(ocr: dict) -> dict[str, str]:
    """Across or Down lists that probably go on in a place the packet doesn't
    have (a page not scanned). The sign: more than half the list's entries
    (and ten or more) have no text at all. A clue the OCR merely missed or
    swallowed is a handful (at most about a quarter of a list in 520 puzzles);
    a list cut off at the foot of a column has most of its clues missing.
    Returns {"A" or "D": a sentence for text.md}."""
    ent, clues, out = entries(ocr), ocr["clues"], {}
    for d, name in (("A", "Across"), ("D", "Down")):
        labs = [k for k in ent if k[0] == d]
        gone = [k for k in labs if not (clues.get(k) or {}).get("text", "").strip()]
        if len(gone) >= CONTINUES_MIN and len(gone) >= CONTINUES_SHARE * len(labs):
            have = [k for k in labs if k not in gone]
            out[d] = (f"{name}: only {len(have)} of {len(labs)} clues have text ({', '.join(have[:6])}"
                      f"{'...' if len(have) > 6 else ''}); {gone[0]}..{gone[-1]} are missing. The list "
                      f"probably goes on in a page that isn't in this packet (look for an ad or a rule where it "
                      f"stops) - escalate, don't restore the clues one by one"
                      + ("" if have == labs[:len(have)] else
                         "; the few clues that have text are probably misnumbered (they belong to the first numbers)"))
    return out


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
    for m in re.finditer(r"[^\W_ºª]+(?:-[^\W_ºª]+)*(?:'[a-z]+)?", text):
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


# ---- what the OCR ran into a clue from beside it, and what the tools propose ----
# The page number and "Solution of Last Week's Puzzle" printed under a clue
# column are read into the column's last clue; a broken clue number becomes a
# euro sign; the spell step "fixes" real words. Each is detected here and
# proposed: text.md shows the proposed text and says what changed, and
# `finish` applies it unless the reviewer wrote their own text for that clue.
_HEADINGS = ("solution of last week's puzzle", "solution of puzzle no", "solution to puzzle no",
             "solution to last month's puzzle", "solution of last month's puzzle")
_PAGE_TAIL = re.compile(r"(?<=[.!?\"”’')\]])\s+(\d{2,3}(?:\s+\d{2,3})?)\s*$")
_BARE_NUMBER_TAIL = re.compile(r"\s(\d{2})\s*$")
_LEAD_JUNK = re.compile(r"^(?:[€θ%$£]\s*\d{0,2}|\d{1,2}\s*[€θ])\s*\.\s+(?=\S)")
_NUMBER_SLOT = re.compile(r"\s(\S{1,3})\.(?=\s)")
SPELL_SURE = 1.0  # wordfreq knows a word this well: probably a word, not a misread


def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def heading_start(text: str, last: bool = True) -> int | None:
    """Where a run-in "Solution of Last Week's Puzzle" / "Solution of Puzzle No. N"
    heading starts (OCR-garbled spellings included), or None. It must end the
    text; unless the clue is the last of its column the match has to be close."""
    toks = [(m.start(), m.group(0)) for m in re.finditer(r"\S+", text)]
    for i, (pos, t) in enumerate(toks):
        w = re.sub(r"[^a-z]", "", t.lower())
        if len(w) < 6 or _sim(w, "solution") < 0.7 or len(text) - pos > 90:
            continue
        window = " ".join(x for _, x in toks[i:i + 5]).lower()
        best = max(_sim(window[:len(h)], h) for h in _HEADINGS)
        if best >= (0.6 if last else 0.75):
            return pos
    return None


def last_in_column(ocr: dict, label: str) -> bool:
    """No other clue box sits below this one in its column (so a page number
    printed under the column would be read into it). False when it has no box."""
    b = (ocr["clues"].get(label) or {}).get("box")
    if not b:
        return False
    img = (ocr["clues"].get(label) or {}).get("image")
    for k, v in ocr["clues"].items():
        c = v.get("box")
        if k == label or not c or v.get("image") != img:
            continue
        overlap = min(b[2], c[2]) - max(b[0], c[0])
        if overlap >= 0.5 * min(b[2] - b[0], c[2] - c[0]) and abs(b[0] - c[0]) < 60 and c[1] > b[1] + 5:
            return False
    return True


def _repeat_cut(text: str) -> int | None:
    """Where a garbled repeat of the clue starts ("... (abbr.). 39. A not potato
    (abbr.).": its own number, then a bad second reading of the same words)."""
    for m in _NUMBER_SLOT.finditer(text):
        tok = m.group(1)
        if not (any(ch.isdigit() for ch in tok) or (len(tok) <= 2 and _zipf(tok.lower()) < 5.5)):
            continue  # a garbled number (39, ss, 5o), not a word like "it" or "red"
        a, b = text[:m.start()].strip(), text[m.end():].strip()
        if len(a) >= 8 and a[-1] in ".!?)\"'" and len(b) >= 8 and _sim(b.lower(), a.lower()[-(len(b) + 3):]) >= 0.6:
            return m.start()
    return None


def _kind(flag: str) -> tuple:
    """What a `spell:x>y` fix substituted: ((seen, meant), ...)."""
    x, _, y = flag.partition(":")[2].partition(">")
    x, y = x.lower(), y.lower()
    if len(x) == len(y):  # substitutions in place (foree > force is one e read for c)
        return tuple((a, b) for a, b in zip(x, y) if a != b)
    return tuple((x[i1:i2], y[j1:j2]) for op, i1, i2, j1, j2 in SequenceMatcher(None, x, y).get_opcodes() if op != "equal")


def spell_doubt(flag: str) -> bool:
    """Is this `spell:x>y` fix one to doubt? The fix that is nearly always right
    in Judge is e->c (the press's broken c: "elean" for "clean"). Any other
    substitution, on a word x that wordfreq knows at all (dratted, Haled,
    middie: rare but real), is as likely a printed word as a misread; a short
    word changed in two places (ycu>yen, a broken 'you') is too."""
    x, _, y = flag.partition(":")[2].partition(">")
    if not (x and y):
        return False
    kind = _kind(flag)
    if all(k == ("e", "c") for k in kind):
        return False
    return (len(x) <= 4 and sum(max(len(a), len(b)) for a, b in kind) > 1) or _zipf(x.lower()) >= SPELL_SURE


def proposed_text(ocr: dict, label: str) -> tuple[str, list[str]]:
    """The clue's text with the run-in junk taken off, and what was taken off
    (no notes: nothing proposed). Never proposes an empty clue."""
    clue = ocr["clues"][label]
    flags = clue.get("flags") or []
    last = last_in_column(ocr, label)
    new, notes = clue.get("text", ""), []
    pos = heading_start(new, last or any(f.split(":")[0] in ("low-ocr-score", "text-moved") for f in flags))
    if pos is not None:
        cut = new[:pos].rstrip()
        if len(cut) >= 3:
            notes.append(f'removed the "Solution of..." heading that ends the column: "{new[pos:][:60]}"')
            new = cut
            r = _repeat_cut(new)
            if r is not None:
                notes.append(f'removed a garbled repeat of the clue: "{new[r:].strip()[:60]}"')
                new = new[:r].rstrip()
    m = _PAGE_TAIL.search(new) if last else None
    if m and len(new[:m.start()].strip()) >= 3:
        notes.append(f"removed the page number {m.group(1)!r} printed under the column")
        new = new[:m.start()].rstrip()
    m = _LEAD_JUNK.match(new)
    if m:
        notes.append(f"removed {m.group(0).strip()!r} from the start (a broken clue number)")
        new = new[m.end():]
    return new, notes


def proposals(ocr: dict) -> dict[str, tuple[str, list[str]]]:
    """Every clue whose text the tools propose to change: label -> (text, why)."""
    out = {}
    for k in ocr["clues"]:
        text, notes = proposed_text(ocr, k)
        if notes and text != ocr["clues"][k].get("text", ""):
            out[k] = (text, notes)
    return out


def tail_number_hint(ocr: dict, label: str) -> str:
    """A last-of-column clue ending in a bare number (no sentence end before it):
    probably the page number, but it could be part of the clue. Flag, don't cut."""
    t = ocr["clues"][label].get("text", "")
    m = _BARE_NUMBER_TAIL.search(t)
    if m and last_in_column(ocr, label) and not _PAGE_TAIL.search(t):
        return f"ends in {m.group(1)!r}: the page number run in?"
    return ""


_NOTICES = ("judge pays $10 for each puzzle printed.",
            "judge will run a crossword puzzle every week and will pay $25 for each puzzle accepted")


def _squash(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9$ ]", " ", t.lower())).strip()


def is_notice(caption: str) -> bool:
    """The magazine's recurring "Judge pays $10 for each puzzle printed", however garbled."""
    t = _squash(caption)
    return any(_sim(t[:len(_squash(n))], _squash(n)) >= 0.8 for n in _NOTICES)


JUDGE_TITLE = re.compile(r"((?:The\s+)?Judge['’]?s?\s*\.?\s*Cross\s?-?word(?:\s+Puzzle)?(?:\s+No\.?)?\s*\d{0,4})", re.I)


def title_check(ocr: dict, title: str | None = None) -> tuple[str, str] | None:
    """(why, proposed title or "") when the title looks like it picked up a
    neighbouring column's heading or an ad, else None. Only Judge's usual
    heading is known, so other publications' titles are never questioned."""
    title = (ocr.get("title") if title is None else title) or ""
    title = title.strip()
    xdid = str(ocr.get("xdid", ""))
    if not xdid.startswith("judge"):
        return None
    m = JUDGE_TITLE.search(title)
    if m:
        extra = (title[:m.start()] + " " + title[m.end():]).strip(" ,.-")
        if extra:
            return f'extra words "{extra}" (a column heading or ad beside the title?)', m.group(1).strip()
        return None
    if xdid[5:9] >= "1928":
        return "doesn't look like Judge's puzzle heading (an ad or another column's heading?)", ""
    return None


CUT_OFF = 12  # a box starting this many pixels right of its column-mates' started after the printed number


def number_cut_off(ocr: dict, label: str) -> bool:
    """A clue flagged number-missing whose box starts well right of the other
    clues' boxes in its column: the box began after the printed number, which
    is there (201 of 253 such flags in batch 9 were this, by reviewers' notes)."""
    cl = ocr["clues"]
    box = (cl.get(label) or {}).get("box")
    if not box:
        return False
    peers = sorted(w["box"][0] for k, w in cl.items()
                   if k != label and w.get("box") and abs(w["box"][0] - box[0]) < 80
                   and w.get("image") == cl[label].get("image")
                   and not any(f == "number-missing" or f.startswith("number-corrected") for f in w.get("flags") or []))
    return bool(peers) and box[0] - peers[len(peers) // 2] >= CUT_OFF


TEXT_FLAGS = ("spell", "spell-hint", "low-ocr-score", "text-moved", "missing", "line-recovered", "no-text")
FLAG_HELP = {  # what the OCR's clue flags mean, for text.md
    "spell": "(spell:x>y) the OCR read x and the pipeline already changed it to y (the text shows y). "
             "Usually right; check that y is what's printed, since a real misprint must stay as printed.",
    "number-missing": "the OCR didn't read the clue's printed number and the box starts where the other boxes "
                      "do: look at the clue crop (it is sometimes a missing clue, sometimes just a smudge).",
    "number-cut-off": "(was number-missing) the clue's box starts to the right of the printed number, which is "
                      "there: ignore.",
    "spell-hint": "(spell-hint:x>y) the OCR read x; the pipeline did NOT change it, but y may be what's printed.",
    "spell-doubt": "(on a spell flag) the pipeline changed a word the dictionary half-knows (dratted>drafted): "
                   "the original may be what's printed. The crop decides.",
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
    bad_title = title_check(ocr)
    lines = [f"# {ocr['xdid']}", "",
             f"Title: {ocr.get('title', '')}"
             + (f"  [suspect: {bad_title[0]}{'; probably ' + repr(bad_title[1]) if bad_title[1] else ''}. "
                f"Look at meta:top, the band across the top of the page]" if bad_title else ""),
             f"Byline: {ocr.get('byline', '')}",
             f"Author: {ocr.get('author', '')}"]
    for k, t in (ocr.get("captions") or {}).items():
        lines.append(f"Caption {k}: {t}" + (f"  [the magazine's recurring notice, not part of the puzzle: "
                                            f"other:{k} is \"\" and `finish` removes it]" if is_notice(t) else ""))
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
    cont = ocr.get("continued_page") or {}
    on_next = set(cont.get("clues") or [])
    if on_next:
        labs = cont["clues"]
        lines += ["", f"## Clues on the next page: {labs[0]}..{labs[-1]} ({len(labs)})",
                  f"The clue list doesn't end on the clue page: these clues are printed on "
                  f"{cont.get('image', 'continued_page.jpg')} ({cont.get('source', '')}) and marked [next page] "
                  f"below. clue: crops show them there; crop other parts of that page with next:x0,y0,x1,y1."]
    merged = [k for k, v in ocr["clues"].items() if _MERGED.search(v.get("text", ""))]
    if merged:
        lines += ["", f"Clue text that seems to run into another clue: {', '.join(merged)}"]
    props = proposals(ocr)
    cut = {k for k, v in ocr["clues"].items() if "number-missing" in (v.get("flags") or []) and number_cut_off(ocr, k)}
    doubt = {k for k, v in ocr["clues"].items() if any(f.startswith("spell:") and spell_doubt(f) for f in v.get("flags") or [])}
    used = {f.split(":")[0] for v in ocr["clues"].values() for f in v.get("flags") or []}
    if cut:
        used.add("number-cut-off")
    if any("number-missing" in (v.get("flags") or []) for k, v in ocr["clues"].items() if k not in cut):
        used.add("number-missing")
    else:
        used.discard("number-missing")
    if doubt:
        used.add("spell-doubt")
    legend = [f"- {k}: {FLAG_HELP[k]}" for k in FLAG_HELP if k in used]
    if props:
        legend.append("- tool: the text shown for that clue is already the tools' proposal (the run-in page number, "
                      "\"Solution of...\" heading or broken clue number taken off); `finish` puts it in your review "
                      "unless you give the clue's text yourself.")
    if legend:
        lines += ["", "Flags on the clues below:"] + legend
    for d, name in (("A", "Across"), ("D", "Down")):
        lines += ["", f"## {name}"]
        for k, v in ocr["clues"].items():
            if k[0] != d:
                continue
            word = ent.get(k, ("", []))[0]
            text = props[k][0] if k in props else v.get("text", "")
            notes = ["number-cut-off" if f == "number-missing" and k in cut else
                     f + " (spell-doubt)" if f.startswith("spell:") and k in doubt and spell_doubt(f) else f
                     for f in v.get("flags") or []]
            if k in on_next:
                notes.insert(0, "next page")
            odd = odd_words(text)
            if odd:
                notes.append("odd: " + " ".join(odd))
            if k in props:
                notes += ["tool: " + n for n in props[k][1]]
            elif tail_number_hint(ocr, k):
                notes.append(tail_number_hint(ocr, k))
            flags = f"  [{'; '.join(notes)}]" if notes else ""
            lines.append(f"{k:<5} {word or '?':<16} {text}{flags}")
    boxes = [f"{k} {','.join(str(round(x)) for x in v['box'])}{' (next page)' if k in on_next else ''}"
             for k, v in ocr["clues"].items() if v.get("box")]
    if boxes:  # for box: crops, e.g. widening a clue whose text runs past its box
        lines += ["", "## Clue boxes (x0,y0,x1,y1 in scan pixels)", "  ".join(boxes)]
    return "\n".join(lines) + "\n"


def write_text(packet: Path) -> tuple[str, list[str]]:
    """Write text.md into the packet; returns its route (lane, reasons)."""
    ocr = load(packet)
    (packet / "text.md").write_text(text_view(ocr), encoding="utf-8")
    return route(ocr)
