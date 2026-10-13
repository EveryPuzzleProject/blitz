"""Make the illustrations for docs/blog/pelham.html.

    python tools/blog/pelham_images.py [--xword-ocr ../xword-ocr] [--shots DIR]

Judge pages (1924, public domain) come from xword-ocr's archive.org cache
(<xword-ocr>/.cache/ia/<identifier>/leafNNNN.jpg). The alumni-directory entry and the
1987 obituary are screenshots Alex DeJarnatt took (directory.png, obituary.png in --shots);
the post credits their sources.

docs/blog/img/hbs-student-pioneers-1915-1930.jpg is a grid of the twelve portraits on Baker
Library's Student Pioneers page (HBS), Pelham outlined; hbs-pelham-annotated.png is a screenshot
of his page's header with the degree year boxed and our note added. Both were made by hand
(2026-10-12), not by this script. hbs-yearbook-pelham.png is the heading and Pelham's entry cut
from page 57 of the Harvard Business School Yearbook (an Ancestry.com image Ben Zimmer found),
also by hand (2026-10-13).
"""
import argparse
import shutil
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "blog" / "img"


def save(im, name, width):
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    im.convert("RGB").save(OUT / name, quality=84, optimize=True, progressive=True)
    print(name, im.size)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xword-ocr", type=Path, default=ROOT.parent / "xword-ocr")
    ap.add_argument("--shots", type=Path)
    a = ap.parse_args()
    ia = a.xword_ocr / ".cache" / "ia"
    OUT.mkdir(parents=True, exist_ok=True)

    # No. 4 (22 Nov 1924; archive.org files the issue under 15 Nov): the whole puzzle page.
    p4 = Image.open(ia / "sim_judge_1924-11-15_87" / "leaf0034.jpg").convert("RGB")
    s4 = p4.height / 800  # coordinates below were read off an 800px-tall preview
    save(p4.crop((int(40 * s4), int(60 * s4), int(510 * s4), int(760 * s4))), "judge1924-11-22-page.jpg", 720)
    # Its credit note, beside the answer keys.
    save(p4.crop((int(225 * s4), int(500 * s4), int(335 * s4), int(580 * s4))), "judge1924-11-22-credit.jpg", 420)

    # No. 6 (6 Dec 1924): its credit note. (The faces image is judge_images.py's.)
    p6 = Image.open(ia / "sim_judge_1924-12-06_87" / "leaf0034.jpg").convert("RGB")
    s6 = p6.height / 800
    save(p6.crop((int(290 * s6), int(240 * s6), int(510 * s6), int(300 * s6))), "judge1924-12-06-credit.jpg", 520)

    if a.shots:
        for src, dst in [("directory.png", "harvard-alumni-directory-1970-pelham.png"),
                         ("obituary.png", "detroit-free-press-1987-pelham.png")]:
            shutil.copyfile(a.shots / src, OUT / dst)
            print(dst, "(copied)")


if __name__ == "__main__":
    main()
