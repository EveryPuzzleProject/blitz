"""Make the illustrations for docs/blog/judge.html from the cached Judge scans.

Public-domain material only: Judge pages printed before 1931. (Never GAMES.)

    uv run python tools/blog/judge_images.py [--ia ../xword-ocr/.cache/ia]

Page images come from xword-ocr's archive.org cache (<ia>/<identifier>/leafNNNN.jpg);
a puzzle's pages are its Source and Solution-Source headers in ../judge/xd/. The other
figures are copies of ones already made for xword-ocr/docs/process-notes.md.
"""
import argparse
import shutil
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "blog" / "img"
WIDTH = 720  # web size


def save(im, name, width=WIDTH):
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    im.convert("RGB").save(OUT / name, quality=82, optimize=True, progressive=True)
    print(name, im.size, (OUT / name).stat().st_size // 1024, "KB")


def it_misread(ia):
    """The 1927-05-07 key for New X Word Puzzle No. 1 (judge1927-04-30), with the three
    squares the OCR read as I boxed: TEST (r3c13), CABOT (r5c8), CAT (r12c9)."""
    page = Image.open(ia / "sim_judge_1927-05-07_92" / "leaf0030.jpg")
    im = page.crop((1900, 2780, 2800, 3620)).convert("RGB")
    x0, y0, cw, ch = 45, 78, 49.1, 48.5  # the key's 15x15 grid inside the crop
    d = ImageDraw.Draw(im)
    for r, c in [(3, 13), (5, 8), (12, 9)]:  # 1-indexed, as in the ledger
        x, y = x0 + (c - 1) * cw, y0 + (r - 1) * ch
        d.rectangle((x - 3, y - 3, x + cw + 3, y + ch + 3), outline=(200, 30, 30), width=6)
    save(im, "judge1927-05-07-key-i-for-t.jpg", 560)


def faces(ia):
    """No. 6 (judge1924-12-06): two face-shaped grids, 'Before Reading Judge' and
    '—and After'."""
    page = Image.open(ia / "sim_judge_1924-12-06_87" / "leaf0034.jpg").convert("RGB")
    im = page.crop((300, 1180, 2650, 3200))
    # The previous puzzle's answer key sits below the first face; paper-coloured
    # fill over it keeps the figure about the two faces.
    ImageDraw.Draw(im).rectangle((0, 1560, 1100, im.height), fill=(250, 250, 250))
    save(im, "judge1924-12-06-faces.jpg")


def contact_sheet(xword_ocr):
    """Part of the contact sheets an agent reviewer saw for No. 46 (judge1928-04-07): the
    title, byline and first two clues, and the answer-key square the OCR couldn't read
    (9 Across, .UK = AUK)."""
    sheets = xword_ocr / "harvests" / "judge" / "tasks-agent1" / "judge1928-04-07" / "sheets"
    top = Image.open(sheets / "sheet_1.png").convert("RGB").crop((0, 0, 1000, 614))
    cell = Image.open(sheets / "sheet_6.png").convert("RGB").crop((0, 0, 1000, 268))
    im = Image.new("RGB", (1000, top.height + cell.height), "white")
    im.paste(top, (0, 0))
    im.paste(cell, (0, top.height))
    save(im, "judge1928-04-07-contact-sheet.jpg", 600)


# docs/blog/img/judge1928-04-07-proof-{key,clues}.jpg are screenshots of the proof page
# (blitz.xwordapp.com/review/?p=judge1928-04-07, 2026-10-12), not made here.


def copies(xword_ocr):
    img = xword_ocr / "docs" / "img"
    for name in ["judge1924-11-01-first-crossword.jpg", "judge1925-facing-pages.jpg",
                 "judge1924-11-22-no4-judge-grid.jpg", "judge1930-page-detected-grids.jpg",
                 "judge56-rectified-vs-detected.jpg", "judge1925-answer-grid-crossings.jpg"]:
        shutil.copyfile(img / name, OUT / name)
        print(name, "(copied)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xword-ocr", type=Path, default=ROOT.parent / "xword-ocr")
    ap.add_argument("--ia", type=Path)
    a = ap.parse_args()
    ia = a.ia or a.xword_ocr / ".cache" / "ia"
    OUT.mkdir(parents=True, exist_ok=True)
    it_misread(ia)
    faces(ia)
    contact_sheet(a.xword_ocr)
    copies(a.xword_ocr)


if __name__ == "__main__":
    main()
