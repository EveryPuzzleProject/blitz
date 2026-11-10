"""Check the batch page's question links against real packets: does each land on a row, and is the question shown?

    uv run --with playwright python tools/check_question_links.py <ship.json> [--sample N] --base URL [--base2 URL] --out FILE.md

For every puzzle the ship record holds on a question (or a sample of N spread over its groups), the proof page
is opened on a dev server (tools/review_dev.py) at the puzzle's first question, as "Answer it" opens it, and
each of its questions is checked on the page as drawn:

    row      the row the question points at is on the page (the proof page's own rowTarget)
    top      the question's text is in the box at the top of the page
    at row   the question is shown at the row too (its callout, or a reviewer's comment that says it)
    lands    for the first question: the page is scrolled to the row (or stays at the top when there is none)

--base2 is a second server with the packets as the live site has them (review_dev --without puzzle.xd), so the
table can say what a person sees today and what they see once the packets are published again.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

JS = """(asks) => asks.map((a, i) => {
  const t = rowTarget(a.row), q = document.getElementById('question');
  const calls = [...document.querySelectorAll('.qcall')].some(c => c.textContent.includes(a.text.slice(0, 60)));
  const said = a.row && commentsFor(a.row).some(([, c]) => (c.text || '').includes(a.text));
  let lands = null;
  if (i === 0) {
    const el = t && a.row ? (t.tagName === 'SECTION' ? t : t) : q, r = el ? el.getBoundingClientRect() : null;
    lands = !!r && r.bottom > 0 && r.top < innerHeight;
  }
  return {row: !!t, top: !!q && q.textContent.includes(a.text.slice(0, 60)), at: !!t && (calls || said || !a.row), lands};
})"""


def sample(rows: list[dict], n: int) -> list[dict]:
    """About n question puzzles spread over the groups (every group at least 3), in the walk's order."""
    groups: dict[str, list] = {}
    for r in sorted(rows, key=lambda r: r["order"]):
        groups.setdefault(r["group"] or "own", []).append(r)
    take = {g: min(len(v), 3) for g, v in groups.items()}
    while sum(take.values()) < min(n, len(rows)):
        for g, v in groups.items():
            if take[g] < len(v) and sum(take.values()) < n:
                take[g] += 1
    out = []
    for g, v in groups.items():  # spread through the group, not its first few
        step = len(v) / take[g]
        out += [v[int(i * step)] for i in range(take[g])]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("ship", type=Path)
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--base", required=True)
    ap.add_argument("--base2", default="")
    ap.add_argument("--names", default="published again,as live today")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    rec = json.loads(a.ship.read_text(encoding="utf-8"))
    rows = [r for r in rec["puzzles"] if r["queue"] == "question"]
    rows = sample(rows, a.sample) if a.sample else sorted(rows, key=lambda r: r["order"])
    bases = [b for b in (a.base, a.base2) if b]
    names = a.names.split(",")[:len(bases)]
    yn = lambda v: "yes" if v else "NO"
    lines = [f"### {rec['batch']}: {len(rows)} puzzles, {sum(len(r['asks']) for r in rows)} questions", "",
             "| puzzle | group | question about | " + " | ".join(f"{n}: row" for n in names) + " | "
             + " | ".join(f"{n}: shown at top" for n in names) + " | " + " | ".join(f"{n}: shown at row" for n in names)
             + " | " + " | ".join(f"{n}: lands" for n in names) + " |",
             "|---|---|---|" + "---|" * (4 * len(names))]
    tally = {n: {"asks": 0, "row": 0, "top": 0, "at": 0, "first": 0, "lands": 0} for n in names}
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True)
        page = b.new_page(viewport={"width": 1280, "height": 900})
        for r in rows:
            got = []
            for base in bases:
                page.goto(f"{base}/review/?p={r['pid']}&k={r['asks'][0]['row']}".replace("^", "%5E"))
                page.wait_for_selector("#summary", timeout=60000)
                page.wait_for_timeout(1300)  # the page goes to the row twice, the second time after 900 ms
                got.append(page.evaluate(JS, r["asks"]))
            for i, ask in enumerate(r["asks"]):
                cells = [yn(g[i]["row"]) for g in got] + [yn(g[i]["top"]) for g in got] + [yn(g[i]["at"]) if g[i]["row"] else "no row" for g in got] \
                    + [("" if g[i]["lands"] is None else yn(g[i]["lands"])) for g in got]
                lines.append(f"| {r['pid'] if i == 0 else ''} | {(r['group'] or 'own') if i == 0 else ''} | {ask['row'] or '(the puzzle)'} | " + " | ".join(cells) + " |")
                for n, g in zip(names, got):
                    t = tally[n]
                    t["asks"] += 1; t["row"] += g[i]["row"]; t["top"] += g[i]["top"]; t["at"] += g[i]["row"] and g[i]["at"]
                    if g[i]["lands"] is not None:
                        t["first"] += 1; t["lands"] += g[i]["lands"]
            print(r["pid"], flush=True)
        b.close()
    head = [f"Totals for {rec['batch']}:", ""] + [
        f"- {n}: {t['row']} of {t['asks']} questions have their row on the page; {t['top']} of {t['asks']} are shown at the top; "
        f"{t['at']} of {t['row']} rows show the question at the row; {t['lands']} of {t['first']} first links land where they should."
        for n, t in tally.items()]
    a.out.write_text("\n".join(head + [""] + lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(head))


if __name__ == "__main__":
    main()
