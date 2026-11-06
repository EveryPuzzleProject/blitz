"""Make a 1200x630 social card (Open Graph / link-preview image) for a project site:
a public-domain scan on the right, a few words on the left.

    python img/social_card.py --image img/judge1924-11-15-cover-crossword.jpg \
        --label "Every Puzzle Project" --words "Preserving every crossword ever printed" \
        --url everypuzzleproject.org --out img/social-card.png

The default arguments make this site's card. blitz (blitz.xwordapp.com) keeps a copy of
this script and makes its own card with its own words. Only public-domain images go on
a card: Judge pages printed before 1931 are fine; nothing from GAMES or Newspapers.com.
Fonts: Palatino Linotype and Segoe UI if installed (Windows), else Georgia / DejaVu.
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
W, H = 1200, 630
BG, INK, MUTED, ACCENT, LINE = "#faf8f3", "#1d1b17", "#6b665c", "#2f5d9e", "#d9d3c6"


def font(names, size):
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


SERIF_BOLD = ["palab.ttf", "Palatino Linotype Bold", "georgiab.ttf", "DejaVuSerif-Bold.ttf"]
SANS = ["segoeui.ttf", "Segoe UI", "arial.ttf", "DejaVuSans.ttf"]
SANS_BOLD = ["segoeuib.ttf", "Segoe UI Bold", "arialbd.ttf", "DejaVuSans-Bold.ttf"]


def wrap(draw, text, fnt, width):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=fnt) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    return lines + [line]


def make(image, label, words, url, out):
    card = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(card)

    # The scan, on the right, scaled to the card's height with a margin and a soft shadow.
    scan = Image.open(image).convert("RGB")
    margin = 36
    sh = H - 2 * margin
    scan = scan.resize((round(scan.width * sh / scan.height), sh), Image.LANCZOS)
    sx, sy = W - margin - scan.width, margin
    shadow = Image.new("RGBA", (scan.width + 40, scan.height + 40), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle((20, 20, scan.width + 20, scan.height + 20), fill=(0, 0, 0, 70))
    from PIL import ImageFilter
    shadow = shadow.filter(ImageFilter.GaussianBlur(12))
    card.paste(shadow, (sx - 20, sy - 14), shadow)
    card.paste(scan, (sx, sy))
    draw.rectangle((sx - 1, sy - 1, sx + scan.width, sy + scan.height), outline=LINE)

    # The words, on the left.
    left, col = 64, sx - 64 - 48
    y = 70
    # A little 3x3 crossword mark, then the label.
    cell = 10
    for r in range(3):
        for c in range(3):
            black = (r, c) in ((0, 0), (2, 2))
            draw.rectangle((left + c * cell, y + r * cell, left + (c + 1) * cell - 1, y + (r + 1) * cell - 1),
                           fill=INK if black else "#ffffff", outline=INK)
    f_label = font(SANS_BOLD, 26)
    draw.text((left + 3 * cell + 14, y - 3), label, font=f_label, fill=INK)
    y += 3 * cell + 56

    size = 68
    while True:
        f_words = font(SERIF_BOLD, size)
        lines = wrap(draw, words, f_words, col)
        lh = round(size * 1.12)
        if len(lines) * lh <= H - y - 120 or size <= 40:
            break
        size -= 4
    for ln in lines:
        draw.text((left, y), ln, font=f_words, fill=INK)
        y += lh

    f_url = font(SANS, 26)
    draw.text((left, H - 70), url, font=f_url, fill=ACCENT)

    card.save(out, optimize=True)
    print(out, card.size, Path(out).stat().st_size // 1024, "KB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image", default=ROOT / "docs" / "img" / "judge1924-11-15-cover-crossword.jpg")
    ap.add_argument("--label", default="Every Puzzle Project · Blitz")
    ap.add_argument("--words", default="Check old crosswords against their scans")
    ap.add_argument("--url", default="blitz.xwordapp.com")
    ap.add_argument("--out", default=ROOT / "docs" / "img" / "social-card.png")
    a = ap.parse_args()
    make(a.image, a.label, a.words, a.url, a.out)
