"""blitz: one command for a blitz run, from claiming puzzles to sending reviews.

    blitz doctor                         is everything set up?
    blitz start 3 [judge|games]          claim puzzles, download them, write text.md
          [--hand] [--model M] [--list-me]
    blitz status                         this run's puzzles and where each one is
    blitz instructions [pub]             how to review (for Claude, or you)
    blitz sheets <puzzle> <targets...>   crops of the scan on contact sheets
    blitz finish <puzzle>                draft.json -> review.json
    blitz submit <puzzle>                send a review to your pull request
    blitz watch [folder]                 a live page of the reviews as they happen
    blitz feedback [folder]              what reviewers said the tools got wrong
    blitz decisions [folder] [-o FILE]   your accept/reject decisions from the watch page, for import
    blitz drop                           forget this run (claims expire after 48 hours)

The public review site (helpers check agents' reviews in the browser; see site/README.md):
    blitz site-build                     write docs/review/ (the page, served by GitHub Pages)
    blitz site-publish <folder>          put a folder's reviewed puzzles on the site
    blitz site-import [-o FILE]          what helpers decided, for xword-ocr import-reviews --decisions
    blitz site-close <puzzle...>         take puzzles off the site

A <puzzle> is its id (judge1931-03-14), looked up in ../blitz-work, or a path
to any puzzle folder.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import work


def _root() -> Path:
    return work.repo_root()


def _packet(name: str) -> Path:
    p = Path(name)
    if (p / "ocr.json").exists():
        return p
    d = work.work_dir(_root()) / name
    if (d / "ocr.json").exists():
        return d
    raise work.Stop(f"No puzzle {name}: give its id from `blitz status`, or a path to its folder.")


def cmd_doctor(a) -> None:
    problems = work.doctor(_root())
    print("\n".join(problems) or "Ready: git, gh (logged in) and the upstream remote are all set.")


def cmd_start(a) -> None:
    s = work.start(_root(), a.count, a.pub or "", "hand" if a.hand else "claude", a.model or "", a.list_me)
    print(f"\nClaimed {len(s['puzzles'])} puzzles: {s['pr']}")
    _status(s)
    if s["by"] == "hand":
        print("\nOpen each puzzle's editor in your browser:")
        for p in s["puzzles"]:
            print(f"  {(work.work_dir(_root()) / p['xdid'] / 'edit.html').resolve()}")
        print("When you've saved a review from the editor: blitz submit <puzzle>")
    else:
        print("\nNext: review each one (blitz instructions), then blitz submit <puzzle>.")
        print("To watch the reviews as they happen: blitz watch")


def _status(s: dict) -> None:
    w = work.work_dir(_root())
    for p in s["puzzles"]:
        d = w / p["xdid"]
        state = ("sent" if p["sent"] else "reviewed, not sent" if (d / "review.json").exists()
                 else "drafted" if (d / "draft.json").exists() else "looking" if (d / "sheets").exists()
                 else "to review")
        dec = json.loads((d / "decisions.json").read_text(encoding="utf-8")) if (d / "decisions.json").exists() else {}
        rej = sum(1 for v in (dec.get("items") or {}).values() if v == "reject")
        if dec.get("verdict") or rej:
            state += f" (your check: {dec.get('verdict') or 'no verdict'}{f', {rej} rejected' if rej else ''})"
        lane = "" if p["lane"] == "text" else f"  (expect a whole-puzzle problem: {'; '.join(p['why'])})"
        print(f"  {p['xdid']:<18} {state}{lane}")


def cmd_status(a) -> None:
    s = work.load_session(_root())
    if not s:
        print("No run here yet. Start one: blitz start 3")
        return
    print(f"{s['pr']} ({s['branch']}, {'by hand' if s['by'] == 'hand' else s['model'] or 'Claude'})")
    _status(s)


def cmd_instructions(a) -> None:
    root = _root()
    pub = a.pub or ((work.load_session(root) or {}).get("puzzles") or [{}])[0].get("pub", "")
    print((root / "publications" / "REVIEW.md").read_text(encoding="utf-8"))
    notes = root / "publications" / pub / "NOTES.md"
    if pub and notes.exists():
        print("\n" + notes.read_text(encoding="utf-8"))


def cmd_text(a) -> None:
    from .packet import write_text

    for name in a.puzzles:
        d = _packet(name)
        lane, why = write_text(d)
        print(f"{d / 'text.md'}" + (f"  (whole-puzzle problem: {'; '.join(why)})" if why else ""))


def cmd_sheets(a) -> None:
    from .crops import TARGET, make_sheets
    from .packet import load
    from .review import choose_targets

    d = _packet(a.puzzle)
    bad = [t for t in a.targets if not TARGET.fullmatch(t.strip())]
    asked = [m.group(0) for t in a.targets if (m := TARGET.fullmatch(t.strip()))]
    made = make_sheets(d, choose_targets(load(d), a.targets), a.fresh)
    for s in made["sheets"]:
        print(f"{s['file']}: {', '.join(s['crops'])}")
    extra = [c for s in made["sheets"] for c in s["crops"] if c not in asked]
    if extra:
        print(f"also added (always shown: title, byline, captions, odd words, flags, unsure letters): {', '.join(extra)}")
    for t, why in made["missed"]:
        print(f"no crop for {t}: {why}")
    if bad:
        print(f"not a target: {', '.join(bad)}")
    mine = [(t, f) for t, f in made["already"] if t in asked]
    if mine:
        print("already on your sheets: " + ", ".join(f"{t} ({d / 'sheets' / f})" for t, f in mine))


def cmd_finish(a) -> None:
    from .review import finish_packet

    model = a.model or (work.load_session(_root()) or {}).get("model", "")
    for name in a.puzzles:
        d = _packet(name)
        if not (d / "draft.json").exists():
            raise work.Stop(f"No draft.json in {d}: write the review there first.")
        rv, ignored = finish_packet(d, model)
        unchecked = [k for k, v in rv["unsure"].items() if str(v).startswith("not checked")]
        print(f"{d.name}: {len(rv['corrections'])} corrections, {len(rv['sic'])} sic, {len(rv['unsure'])} unsure"
              + (f" (not on a sheet, so not applied: {', '.join(unchecked)})" if unchecked else "")
              + (f"; ignored: {'; '.join(ignored)}" if ignored else "")
              + (f"; escalated: {rv['escalate']}" if rv["escalate"] else ""))
        if rv.get("odd_left"):
            print("  Still odd after your review (OCR slips left in?): "
                  + "; ".join(f"{k} {' '.join(w)}" for k, w in rv["odd_left"].items())
                  + ".\n  Look at each on a sheet; then correct it, keep it as sic, or add it to \"as_printed\" "
                    "(a name, a pun or dialect printed that way), and run finish again.")


def cmd_submit(a) -> None:
    for x in a.puzzles:
        r = work.submit(_root(), x)
        rv = r["review"]
        print(f"Sent {x}: {len(rv.get('corrections') or {})} corrections, {len(rv.get('sic') or {})} misprints kept"
              f"{', escalated' if rv.get('escalate') else ''}.\n  Record: {r['record']}\n  Try it yourself: {r['solve']}")
        if r["all_sent"]:
            print(f"That was the last one: your pull request is ready for review. Thank you! {r['pr']}")


def cmd_watch(a) -> None:
    from .watch import serve

    serve(Path(a.folder) if a.folder else work.work_dir(_root()), a.port, not a.no_browser)


def cmd_feedback(a) -> None:
    from .review import feedback

    root = Path(a.folder) if a.folder else work.work_dir(_root())
    print(feedback(sorted(d for d in root.iterdir() if d.is_dir())))


def cmd_decisions(a) -> None:
    folder = Path(a.folder) if a.folder else work.work_dir(_root())
    text = json.dumps(work.export_decisions(folder), indent=1, ensure_ascii=False)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
        print(f"wrote {a.out}")
    else:
        print(text)


def cmd_site_build(a) -> None:
    from .site import build

    out = build(_root())
    print(f"wrote {out}: fill in {out / 'config.js'} if you haven't, then commit and push docs/review/")


def cmd_site_publish(a) -> None:
    from .site import publish

    done = publish(Path(a.folder), a.batch or "", a.dry_run)
    print(f"{'would publish' if a.dry_run else 'published'} {len(done)} puzzles")


def cmd_site_import(a) -> None:
    from .site import fetch_decisions

    data = fetch_decisions()
    text = json.dumps(data, indent=1, ensure_ascii=False)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
        n = data["puzzles"]
        print(f"wrote {a.out}: {len(n)} puzzles, {sum(1 for p in n.values() if p['verdict'])} with a verdict, "
              f"{sum(len(p['reports']) for p in n.values())} reports")
    else:
        print(text)


def cmd_site_close(a) -> None:
    from .site import close

    close(a.puzzles)
    print(f"closed {len(a.puzzles)} puzzles")


def cmd_drop(a) -> None:
    s = work.drop(_root())
    print(f"Dropped {s['pr']}; its claims expire after 48 hours." if s else "No run to drop.")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="blitz", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=__doc__.split("\n\n", 1)[1])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)
    q = sub.add_parser("start", help="claim puzzles with a draft pull request and download them")
    q.add_argument("count", type=int, nargs="?", default=3)
    q.add_argument("pub", nargs="?", help="judge or games (default: whichever is next)")
    q.add_argument("--hand", action="store_true", help="review by hand in the browser editor")
    q.add_argument("--model", help="the model Claude reviews with, e.g. claude-fable-5-1")
    q.add_argument("--list-me", action="store_true", help="add your GitHub name to the contributors page")
    q.set_defaults(fn=cmd_start)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    q = sub.add_parser("instructions")
    q.add_argument("pub", nargs="?")
    q.set_defaults(fn=cmd_instructions)
    q = sub.add_parser("text", help="(re)write text.md for puzzles")
    q.add_argument("puzzles", nargs="+")
    q.set_defaults(fn=cmd_text)
    q = sub.add_parser("sheets", help="crops of the scan on contact sheets (added to the puzzle's earlier ones)")
    q.add_argument("puzzle")
    q.add_argument("targets", nargs="*")
    q.add_argument("--fresh", action="store_true", help="start the puzzle's sheets over")
    q.set_defaults(fn=cmd_sheets)
    q = sub.add_parser("finish", help="turn draft.json into review.json")
    q.add_argument("puzzles", nargs="+")
    q.add_argument("--model")
    q.set_defaults(fn=cmd_finish)
    q = sub.add_parser("submit", help="send reviews to your pull request")
    q.add_argument("puzzles", nargs="+")
    q.set_defaults(fn=cmd_submit)
    q = sub.add_parser("watch", help="a live page of the reviews as they happen")
    q.add_argument("folder", nargs="?")
    q.add_argument("--port", type=int, default=8770)
    q.add_argument("--no-browser", action="store_true")
    q.set_defaults(fn=cmd_watch)
    q = sub.add_parser("feedback", help="the reviewers' notes on the tools, grouped")
    q.add_argument("folder", nargs="?")
    q.set_defaults(fn=cmd_feedback)
    q = sub.add_parser("decisions", help="your accept/reject decisions from the watch page, as one file for import")
    q.add_argument("folder", nargs="?")
    q.add_argument("-o", "--out")
    q.set_defaults(fn=cmd_decisions)
    sub.add_parser("drop").set_defaults(fn=cmd_drop)
    sub.add_parser("site-build", help="write docs/review/: the public review page").set_defaults(fn=cmd_site_build)
    q = sub.add_parser("site-publish", help="put a folder's reviewed puzzles on the public review site")
    q.add_argument("folder")
    q.add_argument("--batch", help="a name for this batch (default: the folder's name)")
    q.add_argument("--dry-run", action="store_true", help="list what would be published")
    q.set_defaults(fn=cmd_site_publish)
    q = sub.add_parser("site-import", help="what helpers decided on the site, for xword-ocr import-reviews --decisions")
    q.add_argument("-o", "--out")
    q.set_defaults(fn=cmd_site_import)
    q = sub.add_parser("site-close", help="take puzzles off the public review site")
    q.add_argument("puzzles", nargs="+")
    q.set_defaults(fn=cmd_site_close)
    a = p.parse_args(argv)
    try:
        a.fn(a)
    except work.Stop as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
