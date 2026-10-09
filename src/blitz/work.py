"""Claiming puzzles, downloading them, and sending reviews back: the git and
GitHub side of a blitz run.

A run is one branch and one draft pull request. Its state is kept in
`../blitz-work/session.json` (beside the checkout, never in it): the branch,
the pull request, who reviews (Claude or a person by hand), the model, and
the puzzles claimed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tarfile
import time
from datetime import datetime
from pathlib import Path

REPO = "EveryPuzzleProject/blitz"
SITE = "https://everypuzzleproject.github.io/blitz"
CLAIM_HOURS = 48


class Stop(Exception):
    """A problem the person has to fix; the message says how."""


def run(*args: str, check: bool = True, cwd: Path | None = None) -> str:
    p = subprocess.run(list(args), capture_output=True, text=True, encoding="utf-8", cwd=cwd)
    if check and p.returncode:
        raise Stop(f"`{' '.join(args)}` failed:\n{(p.stderr or p.stdout).strip()}")
    return p.stdout


def repo_root(start: Path | None = None) -> Path:
    d = (start or Path.cwd()).resolve()
    for p in (d, *d.parents):
        if (p / "publications" / "ORDER").exists():
            return p
    raise Stop("Run this inside your blitz checkout (the folder with publications/).")


def work_dir(root: Path) -> Path:
    w = root.parent / "blitz-work"
    w.mkdir(exist_ok=True)
    return w


def publication_notes(root: Path, pub: str) -> str:
    """What reviewers need to know about one publication: review-notes.md in its
    own repo (EveryPuzzleProject/<pub>), from a checkout beside blitz or else
    from GitHub; for a publication without a repo yet, publications/<pub>/NOTES.md."""
    local = root.parent / pub / "review-notes.md"
    if local.exists():
        return local.read_text(encoding="utf-8")
    old = root / "publications" / pub / "NOTES.md"
    if old.exists():
        return old.read_text(encoding="utf-8")
    import urllib.request

    try:
        url = f"https://raw.githubusercontent.com/EveryPuzzleProject/{pub}/main/review-notes.md"
        return urllib.request.urlopen(url, timeout=30).read().decode("utf-8")
    except OSError:
        return ""


def load_session(root: Path) -> dict | None:
    f = work_dir(root) / "session.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def save_session(root: Path, s: dict) -> None:
    (work_dir(root) / "session.json").write_text(json.dumps(s, indent=1), encoding="utf-8")


def doctor(root: Path) -> list[str]:
    """What's missing before a run can start (empty when ready)."""
    problems = []
    for tool, hint in (("git", "https://git-scm.com"), ("gh", "https://cli.github.com")):
        if not shutil.which(tool):
            problems.append(f"Install {tool}: {hint}")
    if shutil.which("gh") and subprocess.run(["gh", "auth", "status"], capture_output=True).returncode:
        problems.append("Log in to GitHub: gh auth login")
    if shutil.which("git") and "upstream" not in run("git", "remote", cwd=root, check=False).split():
        problems.append(f"Add the main repository as 'upstream': git remote add upstream https://github.com/{REPO}.git")
    return problems


def _puzzles(root: Path, pub: str) -> list[dict]:
    lines = (root / "publications" / pub / "puzzles.tsv").read_text(encoding="utf-8").replace("\r", "").splitlines()
    cols = lines[0].split("\t")
    return [dict(zip(cols, l.split("\t"))) for l in lines[1:] if l.strip()]


def pick(root: Path, n: int, only: str = "") -> list[tuple[str, str, str]]:
    """The next n open puzzles, oldest first: (pub, xdid, release tag). Open =
    released, not reviewed on upstream main, and not named in an open pull
    request updated in the last 48 hours."""
    prs = json.loads(run("gh", "pr", "list", "--repo", REPO, "--state", "open", "--limit", "200",
                         "--json", "updatedAt,body") or "[]")
    cutoff = time.time() - CLAIM_HOURS * 3600
    claimed = " ".join(p["body"] or "" for p in prs
                       if datetime.fromisoformat(p["updatedAt"].replace("Z", "+00:00")).timestamp() > cutoff)
    reviewed = {Path(f).parent.name for f in run("git", "ls-tree", "-r", "--name-only", "upstream/main", "publications",
                                                 cwd=root).splitlines() if f.endswith("/review.json")}
    out = []
    for pub in (root / "publications" / "ORDER").read_text(encoding="utf-8").split():
        if only and pub != only:
            continue
        for p in _puzzles(root, pub):
            if p.get("state") == "open" and p["xdid"] not in reviewed and p["xdid"] not in claimed:
                out.append((pub, p["xdid"], p.get("packet", "")))
                if len(out) == n:
                    return out
    return out


def download(root: Path, pub: str, xdid: str, tag: str) -> Path:
    """Fetch and unpack a puzzle's packet into ../blitz-work/<xdid>/."""
    work = work_dir(root)
    run("gh", "release", "download", tag, "--repo", REPO, "--pattern", f"{xdid}.tar.gz", "--dir", str(work), "--clobber")
    with tarfile.open(work / f"{xdid}.tar.gz") as t:
        try:
            t.extractall(work, filter="data")
        except TypeError:  # Python < 3.12
            t.extractall(work)
    return work / xdid


def start(root: Path, n: int, pub: str = "", by: str = "claude", model: str = "", list_me: bool = False) -> dict:
    """Claim n puzzles with a draft pull request and get them ready to review."""
    from .packet import write_text

    problems = doctor(root)
    if problems:
        raise Stop("\n".join(problems))
    old = load_session(root)
    if old and any(not p.get("sent") for p in old["puzzles"]):
        raise Stop(f"You have puzzles from {old['pr']} still to send (blitz status). Finish or drop that run "
                   f"first (blitz drop).")
    run("git", "fetch", "-q", "upstream", cwd=root)
    run("git", "checkout", "-q", "--detach", "upstream/main", cwd=root)
    picks = pick(root, n, pub)
    if not picks:
        raise Stop(f"Every open puzzle{' of ' + pub if pub else ''} is taken right now. Thanks for offering! "
                   f"Try again in a day or two.")
    user = run("gh", "api", "user", "--jq", ".login").strip()
    branch = f"{'hand' if by == 'hand' else 'review'}-{user}-{datetime.now():%Y%m%d-%H%M}"
    run("git", "checkout", "-q", "-b", branch, "upstream/main", cwd=root)
    puzzles = []
    for p, x, tag in picks:
        print(f"Getting {x} ...", flush=True)
        d = download(root, p, x, tag)
        (root / "publications" / p / "reviews" / x).mkdir(parents=True, exist_ok=True)
        shutil.copy2(d / "ocr.json", root / "publications" / p / "reviews" / x / "ocr.json")
        lane, why = write_text(d)
        if by == "hand":
            _hand_editor(root, p, d)
        puzzles.append({"pub": p, "xdid": x, "lane": lane, "why": why, "sent": False})
    if list_me and not (root / "contributors" / user).exists():
        (root / "contributors" / user).write_text("", encoding="utf-8")
    xdids = " ".join(p["xdid"] for p in puzzles)
    run("git", "add", "publications", "contributors", cwd=root)
    run("git", "commit", "-q", "-m", f"Claim {xdids}", cwd=root)
    run("git", "push", "-q", "-u", "origin", "HEAD", cwd=root)
    s = {"branch": branch, "user": user, "by": by, "model": model, "pr": "", "puzzles": puzzles}
    body = work_dir(root) / f"pr-{branch}.md"
    body.write_text(_body(s), encoding="utf-8")
    s["pr"] = run("gh", "pr", "create", "--draft", "--repo", REPO, "--title",
                  f"Review {xdids}{' (by hand)' if by == 'hand' else ''}", "--body-file", str(body),
                  cwd=root).strip().splitlines()[-1]
    save_session(root, s)
    return s


def _body(s: dict) -> str:
    who = "Reviewing by hand." if s["by"] == "hand" else f"Reviewing with {s['model'] or 'Claude'}."
    return who + "\n\n" + "".join(f"- [{'x' if p['sent'] else ' '}] {p['xdid']}\n" for p in s["puzzles"])


def _hand_editor(root: Path, pub: str, d: Path) -> None:
    shutil.copy2(root / "tools" / "hand" / "edit.html", d / "edit.html")
    images = sorted(f.name for f in d.iterdir() if f.suffix in (".jpg", ".png"))
    ocr = (d / "ocr.json").read_text(encoding="utf-8")
    (d / "data.js").write_text(
        f'window.PUZZLE = {{"ocr": {ocr}, "images": {json.dumps(images)}, '
        f'"instructions": "https://github.com/{REPO}/blob/main/publications/{pub}/INSTRUCTIONS.md"}};\n',
        encoding="utf-8")


def find(root: Path, s: dict, xdid: str) -> dict:
    p = next((p for p in s["puzzles"] if p["xdid"] == xdid), None)
    if p is None:
        raise Stop(f"{xdid} isn't one of the puzzles in this run ({', '.join(q['xdid'] for q in s['puzzles'])}).")
    return p


def submit(root: Path, xdid: str) -> dict:
    """Send one finished review: into the pull request, ticked in its body,
    with a private copy of the puzzle to solve. Returns links for the person."""
    s = load_session(root)
    if not s:
        raise Stop("No run here. Start one with: blitz start")
    p = find(root, s, xdid)
    d = work_dir(root) / xdid
    review = d / "review.json"
    if s["by"] == "hand":  # the editor saves to Downloads
        saved = sorted((Path.home() / "Downloads").glob(f"{xdid}.review*.json"), key=lambda f: f.stat().st_mtime)
        if saved and (not review.exists() or saved[-1].stat().st_mtime > review.stat().st_mtime):
            shutil.copy2(saved[-1], review)
    if not review.exists():
        raise Stop(f"No review for {xdid} yet. "
                   + ("In the editor, press Save review." if s["by"] == "hand" else f"Run: blitz finish {xdid}"))
    rv = apply_decisions(json.loads(review.read_text(encoding="utf-8")), d, s["user"])
    if s["by"] == "hand":
        rv["by"] = "hand"
    if run("git", "branch", "--show-current", cwd=root).strip() != s["branch"]:
        run("git", "checkout", "-q", s["branch"], cwd=root)
    dest = root / "publications" / p["pub"] / "reviews" / xdid / "review.json"
    dest.write_text(json.dumps(rv, indent=1, ensure_ascii=False), encoding="utf-8")
    import sys

    check = subprocess.run([sys.executable, "tools/check_reviews.py"], cwd=root, capture_output=True, text=True)
    if check.returncode:
        raise Stop(f"That review isn't well-formed:\n{check.stdout.strip()}")
    run("git", "add", str(dest.relative_to(root)), cwd=root)
    run("git", "commit", "-q", "-m", f"Review {xdid}{' (by hand)' if s['by'] == 'hand' else ''}", cwd=root)
    run("git", "push", "-q", cwd=root)
    p["sent"] = True
    save_session(root, s)
    body = work_dir(root) / f"pr-{s['branch']}.md"
    body.write_text(_body(s), encoding="utf-8")
    run("gh", "pr", "edit", s["pr"], "--repo", REPO, "--body-file", str(body), cwd=root)
    # A private copy to solve, as a souvenir: stays in the work folder, never pushed.
    for f in ("tools/local-solver/solve.html", "docs/puzzle.js", "docs/style.css"):
        if (root / f).exists():
            shutil.copy2(root / f, d / Path(f).name)
    (d / "data.js").write_text(f'window.PUZZLE = {{"ocr": {(d / "ocr.json").read_text(encoding="utf-8")}, '
                               f'"review": {json.dumps(rv, ensure_ascii=False)}}};\n', encoding="utf-8")
    done = all(q["sent"] for q in s["puzzles"])
    if done:
        run("gh", "pr", "ready", s["pr"], "--repo", REPO, cwd=root)
    return {"record": f"{SITE}/view.html?p={p['pub']}/{xdid}&from={s['user']}:{s['branch']}",
            "solve": str((d / "solve.html").resolve()), "pr": s["pr"], "all_sent": done, "review": rv}


def apply_decisions(rv: dict, packet: Path, who: str = "") -> dict:
    """The review less the changes rejected on the watch page (decisions.json),
    with a record of the check: who, the verdict, and what was rejected and why."""
    dec = json.loads((packet / "decisions.json").read_text(encoding="utf-8")) if (packet / "decisions.json").exists() else {}
    items, notes = dec.get("items") or {}, dec.get("notes") or {}
    if not items and not dec.get("verdict") and not dec.get("reports"):
        return rv
    rv = dict(rv)
    out = {}
    for item in [k for k, v in items.items() if v == "reject"]:
        if item.startswith("sic:"):
            value = (rv.get("sic") or {}).get(item[4:])
            rv["sic"] = {k: v for k, v in (rv.get("sic") or {}).items() if k != item[4:]}
        else:
            value = (rv.get("corrections") or {}).get(item)
            rv["corrections"] = {k: v for k, v in (rv.get("corrections") or {}).items() if k != item}
        if value is not None:
            out[item] = {"value": value, "note": notes.get(item, "")}
    rv["checked"] = {"by": who, "verdict": dec.get("verdict", ""), "note": dec.get("note", ""), "rejected": out,
                     "reports": dec.get("reports") or {}}
    return rv


def export_decisions(folder: Path) -> dict:
    """Every puzzle's decisions in a folder, in the shape the maintainer's
    import takes (xword-ocr import-reviews --decisions)."""
    out = {}
    for d in sorted(folder.iterdir()):
        f = d / "decisions.json"
        if f.exists():
            dec = json.loads(f.read_text(encoding="utf-8"))
            out[d.name] = {k: dec.get(k, default) for k, default in
                           (("items", {}), ("notes", {}), ("verdict", ""), ("note", ""), ("reports", {}))}
    return {"puzzles": out}


def drop(root: Path) -> dict | None:
    """Forget the current run (its claims expire on their own after 48 hours)."""
    s = load_session(root)
    if s:
        (work_dir(root) / "session.json").rename(work_dir(root) / f"session-{s['branch']}.json")
    return s
