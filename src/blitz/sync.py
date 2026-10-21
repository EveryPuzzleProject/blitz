"""blitz sync <pub>: the maintainer's loop for the review site's work, as one command that stops on
surprises (design/next-publication.md, item 4).

On 2026-10-11 each step of this loop was run by hand, and the ones that can damage the record (an
import from the wrong folder, verdicts outside the batch, xd changes nobody's proof explains) were
easy to get wrong. The loop:

    site-import          what helpers decided on the review site (or --decisions FILE)
    import, dry run      what it would add to the ledger, by who it credits; refuse surprises
    --go:
      import             append to the publication's ledger
      relink             rebuild every puzzle from the OCR plus the ledger
      signoff            record each ready proof of the current version against the xd it produced
      volunteer-sync     puzzles.tsv and xd/ in the publication's repo
      check              every changed xd belongs to a puzzle this import touched
    --commit             commit the publication's repo
    report               what changed, the state counts, what to do next

Pushing, rebuilding packets and publishing to the site stay steps the maintainer runs (printed at
the end): they change things outside this machine.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path

from .work import Stop

# Refuse an import that credits one name with more ledger lines than this (on 2026-10-11 a replayed
# folder would have credited ~600 agent corrections to the maintainer). --max-lines raises it.
MAX_LINES = 150


def _xo(xword_ocr: Path, *args: str) -> str:
    """Run an xword-ocr command in its checkout (it reads harvests/<pub> relative to there)."""
    p = subprocess.run(["uv", "run", "xword-ocr", *args], cwd=xword_ocr, capture_output=True, text=True,
                       encoding="utf-8", check=False)
    out = (p.stdout or "") + (p.stderr or "")
    out = "\n".join(line for line in out.splitlines() if "[RapidOCR]" not in line)
    if p.returncode:
        raise Stop(f"`xword-ocr {' '.join(args)}` failed:\n{out.strip()[-3000:]}")
    return out


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8",
                          check=False).stdout


def dry_run_credits(out: str) -> dict[str, Counter]:
    """From `import-reviews --dry-run`: {log file: Counter((who, action, kind) -> lines)}."""
    credits: dict[str, Counter] = {}
    log = None
    for line in out.split("DRY RUN", 1)[-1].splitlines():
        m = re.match(r"  (\S+\.jsonl): \d+ lines", line)
        if m:
            log = m.group(1)
            credits[log] = Counter()
            continue
        m = re.match(r"\s+(\d+)  (.+): (\S+) (\S*)$", line)
        if m and log:
            credits[log][(m.group(2), m.group(3), m.group(4))] += int(m.group(1))
    return credits


def surprises(credits: dict[str, Counter], dry: str, by: str, max_lines: int) -> list[str]:
    """What an import shouldn't do without a person looking first."""
    found = []
    ledger = credits.get("corrections.jsonl", Counter())
    per_name = Counter()
    for (who, _action, _kind), n in ledger.items():
        per_name[who] += n
    for who, n in per_name.items():
        if n > max_lines:
            found.append(f"{n} ledger lines would be credited to {who!r} (more than {max_lines}): "
                         "is this the right folder? (--max-lines to allow)")
    agent = sum(n for (who, _a, _k), n in ledger.items() if who == by)
    if agent:
        found.append(f"{agent} lines would be credited to {by!r} from the folder's own review.json files: a folder "
                     "of current-review packets should add none (only helpers' work comes in)")
    if "REJECTED" in dry:
        found.append("some reviews were rejected: " + "; ".join(l for l in dry.splitlines() if l.startswith("REJECTED"))[:500])
    return found


def sync(pub: str, folder: Path, *, xword_ocr: Path, repo: Path, by: str, decisions: Path | None = None,
         go: bool = False, commit: bool = False, max_lines: int = MAX_LINES, work_dir: Path | None = None) -> dict:
    harvest = Path("harvests") / pub
    if not (xword_ocr / harvest).exists():
        raise Stop(f"No harvest at {xword_ocr / harvest}")
    if not (folder / ".").exists():
        raise Stop(f"No packets folder {folder}")
    dirty = _git(repo, "status", "--porcelain", "--untracked-files=no").strip()
    if dirty:
        raise Stop(f"{repo} has uncommitted changes: commit or stash them first, so this sync's changes are its own:\n{dirty[:800]}")
    report: dict = {"pub": pub, "steps": []}
    step = lambda s: (report["steps"].append(s), print(f"== {s}"))

    # 1. what helpers decided
    if decisions is None:
        from .site import fetch_decisions

        step("site-import")
        data = fetch_decisions()
        decisions = (work_dir or Path("../blitz-work")) / f"site-decisions-{pub}-{datetime.now():%Y%m%d-%H%M}.json"
        decisions.parent.mkdir(parents=True, exist_ok=True)
        decisions.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    puzzles = json.loads(Path(decisions).read_text(encoding="utf-8"))
    puzzles = puzzles.get("puzzles", puzzles)
    mine = {x: d for x, d in puzzles.items() if x.startswith(pub)}
    in_batch = {x for x in mine if (folder / x / "ocr.json").exists()}
    report["decisions"] = str(decisions)
    report["outside_batch"] = sorted(set(mine) - in_batch)
    def versions(x):  # the packet's xd_fp and the ones it carries (the same puzzle, only how we made it differs)
        rv = json.loads((folder / x / "review.json").read_text(encoding="utf-8"))
        return {rv.get("xd_fp") or "", *(rv.get("xd_fp_same") or [])}

    stale = sorted(x for x in in_batch for p in (mine[x].get("proofs") or {}).values()
                   if p.get("xd") and p["xd"] not in versions(x))
    report["proofs_of_older_versions"] = sorted(set(stale))

    # 2. the dry run
    step("import-reviews --dry-run")
    args = ["import-reviews", str(folder.resolve()), "--pubid", pub, "--by", by, "--decisions", str(Path(decisions).resolve()),
            "--fixes", str((repo / "fixes" / "fixes.toml").resolve())]
    dry = _xo(xword_ocr, *args, "--dry-run")
    credits = dry_run_credits(dry)
    report["would_append"] = {log: {f"{w}: {a} {k}".strip(): n for (w, a, k), n in c.items()} for log, c in credits.items()}
    found = surprises(credits, dry, by, max_lines)
    report["surprises"] = found
    if found or not go:
        return report

    # 3. the real thing
    before = {f.name: f.read_text(encoding="utf-8") for f in (repo / "xd").glob("*.xd")}
    step("import-reviews")
    report["import"] = _xo(xword_ocr, *args).strip().splitlines()[-6:]
    step("relink")
    _xo(xword_ocr, "relink", "--out", str(harvest), "--fixes", str((repo / "fixes" / "fixes.toml").resolve()))
    step("signoff")
    signed = _xo(xword_ocr, "signoff", "--out", str(harvest), "--fixes", str((repo / "fixes" / "fixes.toml").resolve()),
                 *sorted(in_batch))
    report["signoffs"] = [l for l in signed.splitlines() if l.startswith("signed off")]
    step("volunteer-sync")
    _xo(xword_ocr, "volunteer-sync", "--out", str(harvest), "--fixes", str((repo / "fixes" / "fixes.toml").resolve()))

    # 4. every xd that changed belongs to a puzzle this import touched
    step("check")
    after = {f.name: f.read_text(encoding="utf-8") for f in (repo / "xd").glob("*.xd")}
    changed = sorted(n[:-3] for n in set(before) | set(after) if before.get(n) != after.get(n))
    unexplained = [x for x in changed if x not in in_batch]
    report["xd_changed"] = changed
    report["xd_changed_unexplained"] = unexplained
    rows = [l.split("\t") for l in (repo / "puzzles.tsv").read_text(encoding="utf-8").splitlines()[1:] if l.strip()]
    report["states"] = dict(Counter(r[4] for r in rows if len(r) > 4))
    if unexplained:
        report["surprises"] = [(f"{len(unexplained)} xd file(s) changed that no proof in this batch touched: "
                                f"{' '.join(unexplained[:20])}. Nothing is committed; look with `git -C {repo} diff xd/`.")]
        return report
    if commit and _git(repo, "status", "--porcelain").strip():
        step("commit")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", f"Review site: {len(in_batch)} puzzles' proofs ({len(report['signoffs'])} signed off)")
        report["commit"] = _git(repo, "rev-parse", "--short", "HEAD").strip()
    return report


def print_report(r: dict, folder: Path, repo: Path, go: bool) -> None:
    print()
    for log, lines in (r.get("would_append") or {}).items():
        print(f"{'appended to' if go and not r['surprises'] else 'would append to'} {log}:")
        for k, n in sorted(lines.items()):
            print(f"  {n:5}  {k}")
    if r.get("outside_batch"):
        print(f"waiting for their own batch (not in {folder.name}): {' '.join(r['outside_batch'][:20])}")
    if r.get("proofs_of_older_versions"):
        print(f"proofs of an older version than this folder's packets (they won't sign off): "
              f"{' '.join(r['proofs_of_older_versions'][:20])}")
    if r["surprises"]:
        print("\nSTOPPED:")
        for s in r["surprises"]:
            print(f"  - {s}")
        return
    if not go:
        print("\nDry run only. Run again with --go to import, relink, sign off and sync (add --commit to commit).")
        return
    print(f"\n{len(r.get('signoffs', []))} signed off; {len(r.get('xd_changed', []))} puzzles changed; states: "
          + ", ".join(f"{n} {s}" for s, n in sorted(r.get("states", {}).items())))
    print("next:")
    if not r.get("commit"):
        print(f"  git -C {repo} add -A && git -C {repo} commit -m '...'")
    print(f"  git -C {repo} push")
    if r.get("xd_changed"):
        print(f"  rebuild the changed puzzles' packets (task-packets --current-review {' '.join(r['xd_changed'][:8])}"
              f"{' ...' if len(r['xd_changed']) > 8 else ''}) and site-publish them, so the site shows the new versions")
