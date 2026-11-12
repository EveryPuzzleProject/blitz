"""Static record pages: one page per puzzle the project transcribed from print.

A record page is the complete public account of one puzzle: what was printed (the
scanned pages, the answer key), what we transcribed (grid and clues as printed), and
what was done to get there (OCR, AI and human review, fixes). It is the page The
Cross Reference links to ("See it as printed"), so its URL is a permalink:

    https://everypuzzleproject.org/<pub>/<xdid without the pub prefix>/

e.g. judge1924-11-01 -> /judge/1924-11-01/, judge1924-11-15b -> /judge/1924-11-15b/.

Inputs, all recorded by earlier milestones (this page computes nothing of its own):
- the publication repo: xd/<xdid>.xd, gxd-exports.tsv (proof, package, scan links),
  status.tsv, fixes/corrections.jsonl (every review decision with who made it);
- the puzzle's review package on R2 (package_url): page.jpg, clue_page.jpg,
  answers.png, grid.png, ocr.json (the OCR reading and each clue's box on its
  page image) and review.json (where each change came from).
"""
from __future__ import annotations

import csv
import html
import json
import re
import shutil
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

SITE = "https://everypuzzleproject.org"
PUBS = {"judge": "Judge", "games": "GAMES"}
MAINTAINER = "Alex DeJarnatt"  # named on pages as "the project's maintainer" (no personal byline)
PACKAGE_FILES = ["ocr.json", "review.json", "page.jpg", "clue_page.jpg", "answers.png", "grid.png"]

esc = html.escape


def record_path(pub: str, xdid: str) -> str:
    """The record page's path under the site: /judge/1924-11-01/."""
    stem = xdid[len(pub):] if xdid.startswith(pub) else xdid
    return f"/{pub}/{stem}/"


def record_url(pub: str, xdid: str) -> str:
    return SITE + record_path(pub, xdid)


# ---------------------------------------------------------------- reading inputs

def read_tsv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def parse_xd(text: str) -> dict:
    parts = re.split(r"\n\n\n+", text.replace("\r\n", "\n").strip("\n"))
    head = {}
    for line in parts[0].split("\n"):
        k, sep, v = line.partition(": ")
        if sep:
            head[k] = v
    rebus = dict(kv.split("=", 1) for kv in head.get("Rebus", "").split() if "=" in kv)
    rows = [[rebus.get(ch, ch) for ch in r] for r in (parts[1] if len(parts) > 1 else "").split("\n") if r.strip()]
    clues = {}
    for line in (parts[2] if len(parts) > 2 else "").split("\n"):
        m = re.match(r"^([AD]\d+)\. (.*)$", line)
        if m:
            text_, _, ans = m.group(2).rpartition(" ~ ")
            clues[m.group(1)] = text_ if _ else m.group(2)
    notes = "\n\n\n".join(parts[3:]).strip() if len(parts) > 3 else ""
    return {"head": head, "rows": rows, "clues": clues, "notes": notes}


def build_grid(rows: list[list[str]], clues: dict) -> dict:
    """Cells with numbers and the words, numbered the standard way or the old way that
    also numbers unchecked single squares across, whichever fits the printed clues."""
    R, C = len(rows), len(rows[0]) if rows else 0
    white = lambda r, c: 0 <= r < R and 0 <= c < C and rows[r][c] != "#"

    def numbering(singles):
        nums, labels, n = {}, set(), 0
        for r in range(R):
            for c in range(C):
                if not white(r, c):
                    continue
                a = not white(r, c - 1) and (white(r, c + 1) or (singles and not white(r - 1, c) and not white(r + 1, c)))
                d = not white(r - 1, c) and white(r + 1, c)
                if a or d:
                    n += 1
                    nums[(r, c)] = n
                    if a: labels.add(f"A{n}")
                    if d: labels.add(f"D{n}")
        return nums, labels

    def score(nb):
        return len(set(clues) - nb[1]) + len(nb[1] - set(clues))

    plain, alt = numbering(False), numbering(True)
    nums, labels = alt if score(alt) < score(plain) else plain
    words = []
    for (r0, c0), n in sorted(nums.items(), key=lambda kv: kv[1]):
        for d in "AD":
            if f"{d}{n}" not in labels:
                continue
            sq, r, c = [], r0, c0
            while white(r, c):
                sq.append((r, c))
                if d == "A": c += 1
                else: r += 1
            ans = "".join(rows[r][c] if re.fullmatch(r"[A-Za-z]+", rows[r][c]) else "·" for r, c in sq)
            words.append({"id": f"{d}{n}", "dir": d, "n": n, "cells": sq, "answer": ans.upper(),
                          "text": clues.get(f"{d}{n}", "[no clue printed]")})
    return {"R": R, "C": C, "nums": nums, "words": words}


def fetch_package(url: str, cache: Path) -> Path:
    """The puzzle's review package, downloaded once into cache/<xdid>/."""
    cache.mkdir(parents=True, exist_ok=True)
    for name in PACKAGE_FILES:
        dest, missing = cache / name, cache / (name + ".missing")
        if dest.exists() or missing.exists():
            continue
        req = urllib.request.Request(url + name, headers={"User-Agent": "EveryPuzzleProject-records/1"})  # R2 refuses urllib's default
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                dest.write_bytes(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:  # the package has no such file (e.g. no separate clue page)
                missing.write_text("")
            else:
                raise
    return cache


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def image_size(path: Path):
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        return None


# ---------------------------------------------------------------- the review history

MAINTAINER_NAMES = (MAINTAINER, "oops6498")  # the maintainer's review-site account too


def who(by: str) -> tuple[str, str, str]:
    """A reviewer as the public page names them, (name, "ai"|"person", why): agents by
    model, the maintainer by role; volunteers aren't named without their opt-in. `why`
    is the reason the record gives in parentheses, if any."""
    m = re.match(r"^([^(]*?)\s*(?:\((.*)\))?\s*(?:,.*)?$", by)
    lead, why = (m.group(1), m.group(2) or "") if m else (by, "")
    why = re.sub(r"^(per )?(Alex DeJarnatt|oops6498)(, \d{4}-\d\d-\d\d)?:?\s*", "", why)
    why = re.sub(r"^\d{4}-\d\d-\d\d:?\s*", "", why).strip()
    model = re.search(r"Claude [A-Z][a-z]+ [\d.]+", by)
    if by.startswith("agent:") or lead.startswith("Claude"):
        return (model.group(0) if model else "Claude"), "ai", why if not by.startswith("agent:") else ""
    if lead.startswith(MAINTAINER_NAMES):
        return "the project's maintainer", "person", why
    return "a volunteer on the review site", "person", ""


def history(rows: list[dict], tool_notes: list[dict]) -> dict:
    """What each reviewer did, grouped by reviewer, from fixes/corrections.jsonl."""
    by = defaultdict(lambda: {"confirm": 0, "correct": [], "looks-right": False, "needs-work": False, "first": "", "kind": ""})
    for r in rows:
        name, kind, why = who(r["by"])
        r = {**r, "why": why}
        g = by[name]
        g["kind"] = kind
        g["first"] = min(g["first"] or r["at"], r["at"])
        if r["action"] == "confirm":
            g["confirm"] += 1
        elif r["action"] == "correct" and r["was"] != r["value"]:
            g["correct"].append(r)
        elif r["action"] == "looks-right":
            g["looks-right"] = True
        elif r["action"] == "needs-work":
            g["needs-work"] = True
    hand = [n for n in tool_notes if "hand fix" in n.get("note", "")]
    return {"reviewers": sorted(by.items(), key=lambda kv: kv[1]["first"]), "hand": hand}


# ---------------------------------------------------------------- the page

def long_date(d: str) -> str:
    try:
        y, m, dd = map(int, d.split("-"))
        dt = date(y, m, dd)
        return f"{dt.strftime('%B')} {dt.day}, {dt.year}"
    except Exception:
        return d


def item_label(item: str) -> str:
    kind, _, key = item.partition(":")
    if kind == "clue":
        return f"{key[1:]} {'Across' if key[0] == 'A' else 'Down'}"
    if kind == "meta":
        return {"title": "Title", "author": "Author", "byline": "Byline", "puzzle_number": "Puzzle number"}.get(key, key)
    if kind in ("cell", "grid"):
        m = re.match(r"r(\d+)c(\d+)", key)
        return f"Square at row {m.group(1)}, column {m.group(2)}" if m else item
    if kind == "other":
        return "Text printed with the puzzle"
    return item


def scan_figure(fid: str, src: str, size, boxes: dict, caption: str, link: str) -> str:
    """A scanned page with the OCR's recorded box for each clue drawn over it (hidden
    until a clue is pointed at)."""
    marks = ""
    if size:
        W, H = size
        for k, (x0, y0, x1, y1) in boxes.items():
            marks += (f'<span class="mark" data-k="{k}" style="left:{100*x0/W:.2f}%;top:{100*y0/H:.2f}%;'
                      f'width:{100*(x1-x0)/W:.2f}%;height:{100*(y1-y0)/H:.2f}%"></span>')
    ratio = f' style="aspect-ratio:{size[0]}/{size[1]};--ar:{size[0]/size[1]:.4f}"' if size else ""
    ia = f' · <a href="{esc(link)}">this page at the Internet Archive</a>' if link else ""
    return (f'<figure class="scan" id="{fid}"><div class="page"{ratio}><img src="{esc(src)}" alt="{esc(caption)}" loading="lazy">{marks}</div>'
            f'<figcaption>{esc(caption)}{ia}</figcaption></figure>')


def render(pub: str, xdid: str, xd: dict, exp: dict, status: dict, ocr: dict, review: dict,
           corrections: list[dict], img: dict, sizes: dict, nav: dict, gxd_id: str) -> str:
    head, name = xd["head"], PUBS.get(pub, pub)
    g = build_grid(xd["rows"], xd["clues"])
    d = head.get("Date", exp.get("date", ""))
    number = head.get("Number", exp.get("number", ""))
    title = head.get("Title", "") or "Crossword"
    author = head.get("Author", "")
    byline = head.get("Byline", "")
    provenance = head.get("Provenance", "")
    url = record_url(pub, xdid)
    keyed = any(re.search(r"[A-Za-z]", "".join(r)) for r in xd["rows"])

    # og: who made it and when it ran; facts that won't change.
    where = f"{name} No. {number}" if number else name
    og_title = (f"{title}, {long_date(d)}" if name.lower() in title.lower() else f"{title}: {where}, {long_date(d)}")
    og_desc = (f"A crossword{f' by {author}' if author else ''} from {name}, {long_date(d)}, as it was printed: "
               f"the scanned pages, our transcription, and how it was checked. Every Puzzle Project.")

    # The OCR's box for each clue, on the page it was read from.
    clue_img = ocr.get("clue_image") or "page.jpg"
    boxes = {k: v["box"] for k, v in (ocr.get("clues") or {}).items() if isinstance(v, dict) and v.get("box")}
    separate_clues = clue_img == "clue_page.jpg" and "clue_page.jpg" in img
    ocr_text = {k: v.get("text", "") for k, v in (ocr.get("clues") or {}).items() if isinstance(v, dict)}

    figs = []
    if "page.jpg" in img:
        figs.append(scan_figure("scan-page", img["page.jpg"], sizes.get("page.jpg"), {},
                                f"The puzzle as printed in {name}" + (f", {long_date(d)}" if d else ""), head.get("Source", "")))
    if separate_clues:
        figs.append(scan_figure("scan-clues", img["clue_page.jpg"], sizes.get("clue_page.jpg"), {},
                                "Its clues, printed on the facing page", head.get("Clue-Source", "")))
    # Beside the transcription: the page the clues were read from, with the OCR's box for each.
    cmp_name = "clue_page.jpg" if separate_clues else "page.jpg"
    compare = (scan_figure("scan-compare", img[cmp_name], sizes.get(cmp_name), boxes,
                           "Where each clue was read (boxes recorded by the OCR)", "") if cmp_name in img else "")
    key_fig = ""
    if "answers.png" in img:
        sol = head.get("Solution-Source", "")
        ia = f' · <a href="{esc(sol)}">that page at the Internet Archive</a>' if sol else ""
        key_fig = (f'<figure class="key"><img src="{esc(img["answers.png"])}" alt="The printed answer key" loading="lazy">'
                   f'<figcaption>The answer key, printed in a later issue{ia}</figcaption></figure>')

    # The transcription.
    cells = ""
    for r in range(g["R"]):
        for c in range(g["C"]):
            ch = xd["rows"][r][c]
            if ch == "#":
                cells += '<div class="cell blk"></div>'
                continue
            n = g["nums"].get((r, c))
            letters = ch.upper() if re.fullmatch(r"[A-Za-z]+", ch) else ""
            ws = " ".join(w["id"] for w in g["words"] if (r, c) in w["cells"])
            inner = esc(letters) if len(letters) < 2 else f'<span class="rb">{esc(letters)}</span>'
            cells += f'<div class="cell" data-w="{ws}">{f"<span class=num>{n}</span>" if n else ""}{inner}</div>'

    changed = {}
    for r in corrections:
        if r["action"] == "correct" and r["was"] != r["value"] and r["item"].startswith("clue:"):
            changed[r["item"][5:]] = r

    # The xd's notes: text printed with the puzzle and misprints kept as printed are shown;
    # "OCR review flags" and "Warnings" are pipeline bookkeeping, told better by the history below.
    shown, misprints = [], {}
    for para in re.split(r"\n\s*\n", xd["notes"]):
        first = para.split("\n", 1)[0]
        if first.startswith(("OCR review flags", "Warnings")) or not para.strip():
            continue
        if first.startswith("Misprints"):
            for line in para.split("\n")[1:]:
                m = re.match(r"^([AD]\d+): .* → (.*)$", line)
                if m:
                    misprints[m.group(1)] = m.group(2)
        shown.append(para)
    notes_text = "\n\n".join(shown)

    def clue_list(dirn):
        out = []
        for w in g["words"]:
            if w["dir"] != dirn:
                continue
            fix = changed.get(w["id"])
            ans = f'<span class="ans">{esc(w["answer"])}</span>' if keyed else ""
            dot = (f'<span class="fixed" title="{esc("The OCR read: " + (ocr_text.get(w["id"]) or fix["was"]))}">•</span>'
                   if fix else "")
            if w["id"] in misprints:
                dot += f'<span class="fixed sic" title="{esc("Meant: " + misprints[w["id"]])}">sic</span>'
            out.append(f'<li data-k="{w["id"]}"><b>{w["n"]}</b><span>{esc(w["text"])}'
                       f'{ans}{dot}</span></li>')
        return "".join(out)

    # How it was checked.
    h = history(corrections, review.get("tool_notes") or [])
    steps = []
    src = head.get("Source", "")
    page_a = f' (<a href="{esc(src)}">page</a>)' if src else ""
    key_note = "; its answer key in a later issue" if head.get("Solution-Source") else ""
    steps.append(f"<li><b>Found.</b> The puzzle was located in the Internet Archive's scan of {esc(name)}{page_a}{key_note}.</li>")
    n_clues = len(ocr_text)
    steps.append(f'<li><b>Read by OCR.</b> The project\'s OCR found the grid, read {n_clues} clues'
                 f'{" and the printed answer key" if ocr.get("answers") else ""}, and recorded where on the page each clue sits '
                 f'(point at a clue below to see it).</li>')
    for name_, gstat in h["reviewers"]:
        bits = []
        if gstat["confirm"]:
            bits.append(f"confirmed {gstat['confirm']} readings against the scan")
        if gstat["correct"]:
            bits.append(f"corrected {len(gstat['correct'])}")
        if gstat["looks-right"]:
            bits.append("checked the whole puzzle and marked it right")
        if gstat["needs-work"]:
            bits.append("sent it back for another look")
        if not bits:
            continue
        label = "Checked by AI" if gstat["kind"] == "ai" else "Checked by a person"
        fixes = ""
        if gstat["correct"]:
            fixes = "<ul class=fixes>" + "".join(
                f'<li><span class=item>{esc(item_label(r["item"]))}</span> '
                f'<del>{esc(r["was"]) or "(nothing)"}</del> → <ins>{esc(r["value"]) or "(removed)"}</ins>'
                + (f' <span class="why">({esc(r["why"])})</span>' if r.get("why") else "") + '</li>'
                for r in gstat["correct"][:40]) + (f"<li class=muted>and {len(gstat['correct']) - 40} more</li>" if len(gstat["correct"]) > 40 else "") + "</ul>"
        steps.append(f'<li><b>{label}.</b> {esc(name_[0].upper() + name_[1:])} {", ".join(bits[:-1]) + (" and " if len(bits) > 1 else "") + bits[-1]}.{fixes}</li>')
    if h["hand"]:
        steps.append(f'<li><b>Hand fixes.</b> {len(h["hand"])} {"value was" if len(h["hand"]) == 1 else "values were"} set by a '
                     f'recorded fix in the publication\'s fix file: '
                     + ", ".join(esc(item_label(n["target"])) for n in h["hand"]) + ".</li>")
    st = status.get("state", "")
    if st == "reviewed" or status.get("blitz_state") == "restored":
        steps.append("<li><b>Done.</b> The transcription matches the printed puzzle, misprints in the clues kept as printed.</li>")

    banner = ""
    if st and st != "reviewed":
        banner = '<div class="banner">This transcription is still being checked; some readings may change.</div>'
    if not keyed:
        banner += '<div class="banner">No printed answer key has been found for this puzzle yet, so only the grid and clues are transcribed.</div>'

    xref = f"https://crosswordreference.com/puzzle/{pub}/{gxd_id}" if gxd_id else ""
    links = []
    if xref:
        links.append(f'<a href="{xref}">This puzzle on The Cross Reference</a>: its answers and clues among every other crossword')
    links.append(f'<a href="https://github.com/EveryPuzzleProject/{pub}/blob/main/xd/{xdid}.xd">{esc(xdid)}.xd</a>, the transcription as a file')
    if exp.get("proof_url"):
        links.append(f'<a href="{esc(exp["proof_url"])}">The review page</a>, where every reading sits beside its crop of the scan')
    if exp.get("package_url"):
        links.append(f'<a href="{esc(exp["package_url"])}ocr.json">The OCR packet</a> (what the OCR read, as data)')

    def navlink(k, label):
        x = nav.get(k)
        return f'<a href="{record_path(pub, x[0])}">{label} {esc(x[1])}</a>' if x else "<span></span>"

    by = f'<div class="by">by {esc(author)}</div>' if author else ""
    if byline and byline.lower().removeprefix("by ").strip() != author:
        by += f'<div class="byline">{esc(byline)}</div>'
    date_link = esc(long_date(d))
    note_block = ""
    if shown:
        note_block = f'<h2>Notes</h2><div class="notes">{esc(notes_text)}</div>'
    date_note = head.get("Date-Note", "")

    og_img = img.get("og.jpg", "")
    og_meta = (f'<meta property="og:image" content="{esc(og_img)}"><meta property="og:image:width" content="1200">'
               f'<meta property="og:image:height" content="630">'
               f'<meta property="og:image:alt" content="The grid as printed in {esc(name)}">') if og_img else ""
    prev_a, next_a = navlink("prev", "←"), navlink("next", "→")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(og_title)} · Every Puzzle Project</title>
<meta name="description" content="{esc(og_desc)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Every Puzzle Project">
<meta property="og:title" content="{esc(og_title)}">
<meta property="og:description" content="{esc(og_desc)}">
<meta property="og:url" content="{url}">
{og_meta}
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="https://everypuzzleproject.org/site.css">
<style>
.kicker {{ font: 600 12px var(--sans); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }}
.by {{ font: 18px var(--serif); }} .byline {{ font-style: italic; color: var(--muted); }}
.lede {{ font: 18px/1.5 var(--serif); max-width: 46em; margin: 12px 0 0; }}
.banner {{ background: var(--accent-soft); border-radius: 6px; padding: 8px 12px; margin: 14px 0 0; font-size: 14px; }}
.printed {{ display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); gap: 24px; align-items: start; }}
.printed .side {{ display: grid; gap: 24px; }}
figure {{ margin: 0; }} figcaption {{ font-size: 13px; color: var(--muted); margin-top: 6px; }}
.scan .page {{ position: relative; background: #fff; border: 1px solid var(--line); }}
.scan img, .key img {{ display: block; width: 100%; height: auto; }}
.key img {{ border: 1px solid var(--line); background: #fff; max-width: 420px; }}
.mark {{ position: absolute; border: 2px solid var(--cur); background: rgba(240, 200, 74, .28); border-radius: 3px; opacity: 0; transition: opacity .12s; pointer-events: none; }}
.mark.on {{ opacity: 1; }}
.compare {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(260px, 38%); gap: 28px; align-items: start; }}
.beside {{ position: sticky; top: 12px; }}
.beside .page {{ width: min(100%, calc((100vh - 70px) * var(--ar, .75))); margin: 0 auto; }}
.record {{ display: grid; gap: 20px; container-type: inline-size; }}
@container (max-width: 520px) {{ .lists {{ grid-template-columns: 1fr; }} }}
.boardbox {{ container-type: inline-size; width: min(100%, calc(var(--cols) * 32px)); }}
.board {{ --sz: calc((100cqw - 4px) / var(--cols)); display: grid; grid-template-columns: repeat(var(--cols), 1fr);
  border: 2px solid #1d1b17; background: #1d1b17; gap: 1px; }}
.cell {{ aspect-ratio: 1; min-width: 0; background: #fff; color: #1d1b17; position: relative; display: flex; align-items: flex-end; justify-content: center; overflow: hidden;
  font: 600 calc(var(--sz) * .5)/1.3 var(--sans); }}
.cell.blk {{ background: #1d1b17; }} .cell.on {{ background: #f3e6b0; }}
.cell .num {{ position: absolute; top: 1px; left: 2px; font: 500 calc(var(--sz) * .28)/1 var(--sans); color: #6b665c; }}
.cell .rb {{ font-size: .5em; line-height: 1; padding-bottom: 3px; }}
.lists {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; min-width: 0; }}
.lists h3 {{ font: 600 13px var(--sans); text-transform: uppercase; letter-spacing: .08em; margin: 0 0 6px; color: var(--muted); }}
.lists ol {{ list-style: none; margin: 0; padding: 0; font: 15px/1.4 var(--serif); }}
.lists li {{ padding: 3px 4px; display: flex; gap: 8px; border-radius: 4px; cursor: default; }}
.lists li.on {{ background: var(--word); }}
.lists li b {{ font: 600 13px var(--sans); min-width: 22px; text-align: right; flex: none; padding-top: 1px; }}
.ans {{ font: 600 12px ui-monospace, monospace; letter-spacing: .06em; color: var(--accent); margin-left: 6px; white-space: nowrap; }}
.fixed {{ font: 600 11px var(--sans); color: var(--warm); margin-left: 5px; cursor: help; }}
.fixed.sic {{ color: var(--bad); }}
.steps {{ padding-left: 20px; max-width: 52em; }} .steps > li {{ margin: 0 0 10px; }}
.why {{ color: var(--muted); font-size: 13px; }}
.fixes {{ font-size: 14px; margin: 6px 0 0; padding-left: 18px; }} .fixes .item {{ color: var(--muted); }}
del {{ color: var(--bad); }} ins {{ color: var(--good); text-decoration: none; }}
.notes {{ white-space: pre-wrap; font: 15px/1.5 var(--serif); max-width: 46em; }}
.links li {{ margin: 4px 0; }}
.nav {{ display: flex; justify-content: space-between; gap: 16px; border-top: 1px solid var(--line); margin-top: 32px; padding-top: 12px; font-size: 15px; }}
@media (max-width: 800px) {{ .printed, .compare {{ display: block; }} .beside {{ display: none; }} .printed .side {{ margin-top: 20px; }} .lists {{ grid-template-columns: 1fr; margin-top: 20px; }} }}
</style>
</head>
<body>
<header class="epp-header"><div class="wrap"><a href="https://everypuzzleproject.org/">Every Puzzle Project</a><span class="epp-page"><a href="/{pub}/">{esc(name)}</a></span></div></header>
<main class="wrap">
<div class="kicker">{esc(name)}{f" · No. {esc(number)}" if number else ""} · {date_link}</div>
<h1>{esc(title)}</h1>
{by}
{f'<p class="lede">{esc(provenance)}</p>' if provenance else ""}
{banner}

<h2>As printed</h2>
<div class="printed">
  <div>{figs[0] if figs else '<p class="muted">The scan is not available.</p>'}</div>
  <div class="side">{"".join(figs[1:])}{key_fig}</div>
</div>

<h2>As transcribed</h2>
<p class="muted">The grid and clues exactly as printed, misprints and all. Point at a clue to see where it was read on the page.
<span class="fixed">•</span> the OCR misread it and a reviewer fixed the reading (point at the dot for what it read); <span class="fixed sic">sic</span> a misprint, kept as printed.</p>
<div class="compare">
  <div class="record">
    <div class="boardbox" style="--cols:{g["C"]}"><div class="board" role="img" aria-label="The puzzle grid{", with its answers" if keyed else ""}">{cells}</div></div>
    <div class="lists"><section><h3>Across</h3><ol>{clue_list("A")}</ol></section><section><h3>Down</h3><ol>{clue_list("D")}</ol></section></div>
  </div>
  <div class="beside">{compare}</div>
</div>
{note_block}

<h2>How it was checked</h2>
<ol class="steps">{"".join(steps)}</ol>
{f'<p class="muted">Date: {esc(date_note)}.</p>' if date_note else ""}

<h2>Elsewhere</h2>
<ul class="links">{"".join(f"<li>{l}</li>" for l in links)}</ul>

<nav class="nav">{prev_a}<a href="/{pub}/">All {esc(name)} puzzles</a>{next_a}</nav>
</main>
<script>
// Point at a clue: light its word in the grid and its box on the scan.
const on = k => {{
  document.querySelectorAll('.on').forEach(e => e.classList.remove('on'));
  if (!k) return;
  document.querySelectorAll(`li[data-k="${{k}}"], .mark[data-k="${{k}}"]`).forEach(e => e.classList.add('on'));
  document.querySelectorAll('.cell[data-w]').forEach(e => {{ if (e.dataset.w.split(' ').includes(k)) e.classList.add('on'); }});
}};
document.querySelectorAll('.lists li').forEach(li => {{
  li.addEventListener('mouseenter', () => on(li.dataset.k));
  li.addEventListener('click', () => on(li.dataset.k));
}});
document.querySelector('.lists')?.addEventListener('mouseleave', () => on(null));
</script>
</body>
</html>
"""


# ---------------------------------------------------------------- og image

def og_image(grid_png: Path, dest: Path) -> bool:
    """1200x630: the printed grid crop, centred on paper."""
    try:
        from PIL import Image
        with Image.open(grid_png) as g:
            g = g.convert("RGB")
            s = 570 / max(g.size)
            g = g.resize((round(g.width * s), round(g.height * s)), Image.LANCZOS)
            card = Image.new("RGB", (1200, 630), (250, 248, 243))
            card.paste(g, ((1200 - g.width) // 2, (630 - g.height) // 2))
            card.save(dest, quality=85)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- driver

def build(pub_repo: Path, out: Path, cache: Path, only: list[str] | None = None, images_base: str | None = None,
          copy_images: bool = False) -> list[Path]:
    """Write <out>/<stem>/index.html for each of the publication's puzzles.

    images_base: where the page's images are served from (default: the R2 package
    itself). copy_images: copy the cached images next to each page (for a local preview)."""
    pub = pub_repo.name
    exports = {r["xdid"]: r for r in read_tsv(pub_repo / "gxd-exports.tsv")}
    status = {r["xdid"]: r for r in read_tsv(pub_repo / "status.tsv")}
    corr = defaultdict(list)
    cpath = pub_repo / "fixes" / "corrections.jsonl"
    if cpath.exists():
        for line in cpath.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                corr[r["xdid"]].append(r)
    xdids = sorted(p.stem for p in (pub_repo / "xd").glob("*.xd"))
    meta = {}
    for x in xdids:
        h = parse_xd((pub_repo / "xd" / f"{x}.xd").read_text(encoding="utf-8"))["head"]
        meta[x] = f"No. {h['Number']}" if h.get("Number") else long_date(h.get("Date", ""))
    written = []
    for i, x in enumerate(xdids):
        if only and x not in only:
            continue
        xd = parse_xd((pub_repo / "xd" / f"{x}.xd").read_text(encoding="utf-8"))
        exp = exports.get(x, {})
        pkg = fetch_package(exp["package_url"], cache / x) if exp.get("package_url") else None
        ocr = load_json(pkg / "ocr.json") if pkg else {}
        review = load_json(pkg / "review.json") if pkg else {}
        page_dir = out / record_path(pub, x).strip("/").split("/", 1)[1]
        page_dir.mkdir(parents=True, exist_ok=True)
        img, sizes = {}, {}
        if pkg:
            for name in ("page.jpg", "clue_page.jpg", "answers.png"):
                if (pkg / name).exists():
                    sizes[name] = image_size(pkg / name)
                    if copy_images:
                        shutil.copy(pkg / name, page_dir / name)
                        img[name] = name
                    else:
                        img[name] = (images_base.rstrip("/") + f"/{pub}/{x}/" if images_base else exp["package_url"]) + name
            if (pkg / "grid.png").exists() and og_image(pkg / "grid.png", page_dir / "og.jpg"):
                img["og.jpg"] = record_url(pub, x) + "og.jpg"
        nav = {"prev": (xdids[i - 1], meta[xdids[i - 1]]) if i else None,
               "next": (xdids[i + 1], meta[xdids[i + 1]]) if i + 1 < len(xdids) else None}
        page = render(pub, x, xd, exp, status.get(x, {}), ocr, review, corr.get(x, []), img, sizes, nav,
                      exp.get("gxd_id", ""))
        (page_dir / "index.html").write_text(page, encoding="utf-8")
        written.append(page_dir / "index.html")
    return written
