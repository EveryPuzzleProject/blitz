"""Count Judge's early-crossword habits in ../judge/xd and print the chart SVG for
docs/blog/judge.html ("Rules that weren't rules yet").

    python tools/blog/judge_charts.py [--xd ../judge/xd]

An unchecked square is a letter in only one entry (no neighbour across, or none down).
A two-letter entry is a run of exactly two letters. '#', '_' (outside a shaped grid)
and '.' (unknown letter, in puzzles with no key) don't count as letters.
"""
import argparse
import collections
import glob
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def counts(xd_dir):
    puz, unchecked, two = collections.Counter(), collections.Counter(), collections.Counter()
    for f in sorted(glob.glob(os.path.join(xd_dir, "*.xd"))):
        parts = open(f, encoding="utf-8").read().split("\n\n\n")
        year = os.path.basename(f)[5:9]
        grid = parts[1].strip().splitlines() if len(parts) > 2 else []
        if not grid or len(set(map(len, grid))) != 1:
            continue
        h, w = len(grid), len(grid[0])

        def op(r, c):
            return 0 <= r < h and 0 <= c < w and grid[r][c] not in "#_."
        puz[year] += 1
        for r in range(h):
            for c in range(w):
                if not op(r, c):
                    continue
                if not ((op(r, c - 1) or op(r, c + 1)) and (op(r - 1, c) or op(r + 1, c))):
                    unchecked[year] += 1
                for dr, dc in ((0, 1), (1, 0)):
                    if not op(r - dr, c - dc):
                        n = 0
                        while op(r + dr * n, c + dc * n):
                            n += 1
                        two[year] += n == 2
    return puz, unchecked, two


def svg(per_year):
    """Bars of unchecked squares per puzzle, one per year."""
    years = sorted(per_year)
    x0, y0, bw, gap, hmax, top = 34, 168, 26, 9, 140, 28
    vmax = 30
    out = [f'<svg viewBox="0 0 {x0 + len(years) * (bw + gap)} 200" role="img" '
           'aria-label="Unchecked squares per puzzle, by year: about 27 in 1924, under 1 in 1938">']
    for v in (0, 10, 20, 30):
        y = y0 - v / vmax * hmax
        out.append(f'  <line x1="{x0 - 4}" x2="{x0 + len(years) * (bw + gap)}" y1="{y:.0f}" y2="{y:.0f}" class="grid"></line>')
        out.append(f'  <text x="{x0 - 8}" y="{y + 4:.0f}" text-anchor="end" class="muted-t">{v}</text>')
    for i, yr in enumerate(years):
        v = per_year[yr]
        x = x0 + i * (bw + gap)
        hgt = max(v / vmax * hmax, 1)
        out.append(f'  <path d="M{x},{y0} v{-hgt + 4:.1f} q0,-4 4,-4 h{bw - 8} q4,0 4,4 v{hgt - 4:.1f} z" '
                   f'class="bar"><title>{yr}: {v:.1f} unchecked squares per puzzle</title></path>')
        if yr in years[::2] or yr == years[-1]:
            out.append(f'  <text x="{x + bw / 2:.0f}" y="{y0 + 18}" text-anchor="middle" class="muted-t">{yr}</text>')
    for yr in (years[0], years[-1]):
        i = years.index(yr)
        x = x0 + i * (bw + gap) + bw / 2
        out.append(f'  <text x="{x:.0f}" y="{y0 - per_year[yr] / vmax * hmax - 6:.0f}" text-anchor="middle">{per_year[yr]:.0f}</text>')
    out.append("</svg>")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xd", default=ROOT.parent / "judge" / "xd")
    a = ap.parse_args()
    puz, unchecked, two = counts(a.xd)
    years = [y for y in sorted(puz) if y != "1939"]  # 1939: two puzzles, both without keys
    for y in sorted(puz):
        print(y, puz[y], "unchecked/puzzle %.1f" % (unchecked[y] / puz[y]), "two-letter/puzzle %.1f" % (two[y] / puz[y]))
    print("total unchecked", sum(unchecked.values()), "two-letter", sum(two.values()))
    print(svg({y: unchecked[y] / puz[y] for y in years}))


if __name__ == "__main__":
    main()
