"""The public review site: helpers without Claude check agents' reviews in the browser.

- `build`: docs/review/ (served by GitHub Pages): the review page (review.html, the same page
  `blitz watch` serves) in helper mode, with site.js connecting it to Supabase and the files.
- `publish`: a folder of reviewed puzzles to the site: their packet files to R2 (an S3-compatible
  bucket, public read), and a row each in Supabase's `puzzles` table.
- `fetch_decisions`: everything helpers recorded, combined per puzzle in the shape
  `xword-ocr import-reviews --decisions` takes.

Secrets come from ~/.blitz-site.env (KEY=value lines) or the environment, never from files in the
repository:
SUPABASE_URL, SUPABASE_SERVICE_KEY (publish and import), and R2_ACCOUNT_ID, R2_ACCESS_KEY_ID,
R2_SECRET_ACCESS_KEY, R2_BUCKET, R2_PUBLIC_URL (publish).
"""

from __future__ import annotations

import json
import mimetypes
import os
import shutil
import urllib.error
import urllib.request
from pathlib import Path

from .work import Stop

# What a helper's page needs from a packet (the clue crops and agent sheets stay local).
FILES = ("ocr.json", "review.json", "sheets/shown.json", "page.jpg", "clue_page.jpg", "continued_page.jpg", "grid.png",
         "answers.png", "_src/page.jpg", "_src/clue_page.jpg", "_src/continued_page.jpg")
SUPABASE_JS = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"


SECRETS = Path.home() / ".blitz-site.env"  # KEY=value lines; outside every repository


def _env(*names: str) -> list[str]:
    if SECRETS.exists():  # the environment wins over the file
        for line in SECRETS.read_text(encoding="utf-8").splitlines():
            k, sep, v = line.strip().partition("=")
            if sep and not k.startswith("#") and k.strip() not in os.environ:
                os.environ[k.strip()] = v.strip().strip('"').strip("'")
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise Stop(f"Set {', '.join(missing)} in {SECRETS} (KEY=value lines) or in your environment "
                   f"(see site/README.md).")
    return [os.environ[n] for n in names]


SITE = "https://blitz.xwordapp.com"
REVIEW_DESC = ("Check an AI's transcriptions of 1920s-30s Judge crosswords against the scanned pages. "
               "Part of the Every Puzzle Project, which is turning early crosswords into searchable, preserved records.")
CARD_ALT = "Judge magazine's November 15, 1924 cover, a full-page crossword, beside the words: Bringing old crosswords back"
FAVICON = '<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 3 3%27%3E%3Crect width=%273%27 height=%273%27 fill=%27%23fff%27/%3E%3Crect width=%271%27 height=%271%27 fill=%27%231d1b17%27/%3E%3Crect x=%272%27 y=%272%27 width=%271%27 height=%271%27 fill=%27%231d1b17%27/%3E%3C/svg%3E">'
# Link previews (Slack, Discord, iMessage, social): the title, a description and the project's card.
REVIEW_HEAD = chr(10).join([
    "<title>Check old crosswords: Every Puzzle Project</title>",
    f'<meta name="description" content="{REVIEW_DESC}">',
    '<meta property="og:type" content="website">',
    '<meta property="og:site_name" content="Every Puzzle Project">',
    '<meta property="og:title" content="Help check old crosswords">',
    f'<meta property="og:description" content="{REVIEW_DESC}">',
    f'<meta property="og:url" content="{SITE}/review/">',
    f'<meta property="og:image" content="{SITE}/img/social-card.png">',
    '<meta property="og:image:width" content="1200">',
    '<meta property="og:image:height" content="630">',
    f'<meta property="og:image:alt" content="{CARD_ALT}">',
    '<meta name="twitter:card" content="summary_large_image">',
    '<meta name="theme-color" content="#f7f5f0">',
    FAVICON,
])


def build(root: Path) -> Path:
    """docs/review/: the page, its adapter, and (once) a config to fill in."""
    out = root / "docs" / "review"
    out.mkdir(parents=True, exist_ok=True)
    page = (Path(__file__).parent / "review.html").read_text(encoding="utf-8")
    old = '<script src="puzzle.js"></script>'
    assert old in page
    page = page.replace(old, '<script src="config.js"></script>\n'
                             f'<script src="{SUPABASE_JS}"></script>\n'
                             '<script src="site.js"></script>\n'
                             '<script src="../puzzle.js"></script>')
    page = page.replace("<title>Review watch</title>", REVIEW_HEAD)
    (out / "index.html").write_text(page, encoding="utf-8", newline="\n")
    shutil.copy2(root / "site" / "site.js", out / "site.js")
    if not (out / "config.js").exists():
        shutil.copy2(root / "site" / "config.example.js", out / "config.js")
    build_proof(root)
    return out


def build_proof(root: Path) -> Path:
    """docs/review2/: the proof page (check the finished puzzle against the scan), a preview beside
    /review/. It shares /review/'s config.js for the puzzle list and the files' address."""
    out = root / "docs" / "review2"
    out.mkdir(parents=True, exist_ok=True)
    page = (Path(__file__).parent / "proof.html").read_text(encoding="utf-8")
    old = "<script>\nconst params"
    assert old in page
    page = page.replace(old, '<script src="../review/config.js"></script>\n' + old)
    page = page.replace("<title>Proof a puzzle</title>",
                        '<title>Check old crosswords (preview): Every Puzzle Project</title>\n'
                        '<meta name="robots" content="noindex">')
    (out / "index.html").write_text(page, encoding="utf-8", newline="\n")
    return out


def _rest(method: str, path: str, body=None, prefer: str = ""):
    url, key = _env("SUPABASE_URL", "SUPABASE_SERVICE_KEY")
    req = urllib.request.Request(url.rstrip("/") + "/rest/v1/" + path, method=method,
                                 data=json.dumps(body).encode("utf-8") if body is not None else None,
                                 headers={"apikey": key, "Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json", **({"Prefer": prefer} if prefer else {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        text = r.read().decode("utf-8")
    return json.loads(text) if text.strip() else None


def publish(folder: Path, batch: str = "", dry_run: bool = False, skip: tuple[str, ...] = ()) -> list[str]:
    """Put a folder's reviewed puzzles on the site (except the puzzles in skip: e.g. ones already imported).
    Returns the puzzles published."""
    packets = [d for d in sorted(folder.iterdir())
               if (d / "review.json").exists() and (d / "ocr.json").exists() and d.name not in skip]
    if not packets:
        raise Stop(f"No reviewed puzzles (with review.json) in {folder}.")
    if dry_run:
        return [d.name for d in packets]
    account, key_id, secret, bucket, public = _env("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY",
                                                   "R2_BUCKET", "R2_PUBLIC_URL")
    _env("SUPABASE_URL", "SUPABASE_SERVICE_KEY")
    try:
        import boto3
    except ImportError:
        raise Stop("Publishing needs boto3: run it as  uv run --extra site blitz site-publish ...")
    s3 = boto3.client("s3", endpoint_url=f"https://{account}.r2.cloudflarestorage.com",
                      aws_access_key_id=key_id, aws_secret_access_key=secret, region_name="auto")
    rows = []
    for d in packets:
        pub = d.name[:len(d.name) - len(d.name.lstrip("abcdefghijklmnopqrstuvwxyz"))] or "misc"  # judge1931-10-03 -> judge
        files = {}
        for f in FILES:
            src = d / f
            if src.exists():
                s3.upload_file(str(src), bucket, f"{pub}/{d.name}/{f}", ExtraArgs={
                    "ContentType": mimetypes.guess_type(f)[0] or "application/octet-stream",
                    "CacheControl": "no-cache" if f.endswith(".json") else "public, max-age=86400"})
                files[f] = True
        rv = json.loads((d / "review.json").read_text(encoding="utf-8"))
        ocr = json.loads((d / "ocr.json").read_text(encoding="utf-8"))
        status = "escalated" if rv.get("escalate") else ("ready" if rv.get("ready") else "needs a person")
        title = (rv.get("corrections") or {}).get("meta:title") or ocr.get("title", "")
        cu = rv.get("checkup") or {}
        rows.append({"xdid": d.name, "pub": pub, "batch": batch or folder.name, "title": title[:200],
                     "base_url": f"{public.rstrip('/')}/{pub}/{d.name}", "files": files,
                     "review_status": status, "open": True,
                     "checkup": {"grade": cu.get("grade", ""), "high": sum(w["level"] == "high" for w in cu.get("warnings", [])),
                                 "medium": sum(w["level"] == "medium" for w in cu.get("warnings", []))} if cu else None})
        print(f"  {d.name}: {len(files)} files")
    try:
        _rest("POST", "puzzles?on_conflict=xdid", rows, prefer="resolution=merge-duplicates,return=minimal")
    except urllib.error.HTTPError as e:  # the checkup column (schema-4-checkup.sql) isn't there yet: publish without it
        if "checkup" not in e.read().decode("utf-8", "replace"):
            raise
        print("  (no checkup column yet: run site/schema-4-checkup.sql to show grades in the list)")
        _rest("POST", "puzzles?on_conflict=xdid", [{k: v for k, v in r.items() if k != "checkup"} for r in rows],
              prefer="resolution=merge-duplicates,return=minimal")
    return [r["xdid"] for r in rows]


def consensus(verdicts: dict[str, str], items: dict[str, dict[str, str]]) -> dict:
    """How the helpers who checked a puzzle line up. verdicts: helper -> 'looks-right' | 'needs-work';
    items: change -> {helper: 'accept' | 'reject'}.
      agreed    two or more helpers, all said looks-right, nobody disagrees about any change
      disputed  someone said needs-work, or helpers differ on the verdict or on a change (conflicts lists them)
      single    one helper's verdict so far
      none      no verdict yet"""
    conflicts = sorted(i for i, v in items.items() if len(set(v.values())) > 1)
    kinds = set(verdicts.values())
    if not verdicts:
        status = "none"
    elif "needs-work" in kinds or len(kinds) > 1 or conflicts:
        status = "disputed"
    elif len(verdicts) >= 2:
        status = "agreed"
    else:
        status = "single"
    return {"eyes": len(verdicts), "agreement": status, "conflicts": conflicts}


def fetch_decisions(agreed_only: bool = False) -> dict:
    """Everything helpers recorded, per puzzle: rejected if anyone rejected (their notes kept, with
    who), the verdict "needs-work" if anyone said so, and every report. Also each helper's own rows."""
    names = {p["user_id"]: p["display_name"] or "a helper" for p in _rest("GET", "profiles?select=user_id,display_name") or []}
    who = lambda r: names.get(r["user_id"], "a helper")
    out: dict[str, dict] = {}
    get = lambda x: out.setdefault(x, {"items": {}, "notes": {}, "verdict": "", "note": "", "reports": {}, "by": {}})
    votes: dict[str, dict[str, dict[str, str]]] = {}   # puzzle -> change -> helper -> decision
    said: dict[str, dict[str, str]] = {}               # puzzle -> helper -> verdict
    for r in _rest("GET", "decisions?select=*&order=at") or []:
        p = get(r["xdid"])
        votes.setdefault(r["xdid"], {}).setdefault(r["item"], {})[r["user_id"]] = r["decision"]
        p["by"].setdefault(who(r), {})[r["item"]] = r["decision"]
        if r["decision"] == "reject":
            p["items"][r["item"]] = "reject"
            if r["note"]:
                p["notes"][r["item"]] = "; ".join(filter(None, [p["notes"].get(r["item"]), f"{who(r)}: {r['note']}"]))
        else:
            p["items"].setdefault(r["item"], "accept")
    for r in _rest("GET", "verdicts?select=*&order=at") or []:
        p = get(r["xdid"])
        if r["verdict"] == "needs-work" or not p["verdict"]:
            p["verdict"] = r["verdict"]
        if r["note"]:
            p["note"] = "; ".join(filter(None, [p["note"], f"{who(r)}: {r['note']}"]))
        p["by"].setdefault(who(r), {})["verdict"] = r["verdict"]
        said.setdefault(r["xdid"], {})[r["user_id"]] = r["verdict"]
    for r in _rest("GET", "reports?select=*&order=at") or []:
        p = get(r["xdid"])
        p["reports"][r["target"]] = "; ".join(filter(None, [p["reports"].get(r["target"]), f"{who(r)}: {r['text']}"]))
    for x, p in out.items():
        p.update(consensus(said.get(x, {}), votes.get(x, {})))
    if agreed_only:
        out = {x: p for x, p in out.items() if p["agreement"] == "agreed"}
    return {"puzzles": out}


def close(xdids: list[str]) -> None:
    """Take puzzles off the site (e.g. once imported)."""
    for x in xdids:
        _rest("PATCH", f"puzzles?xdid=eq.{x}", {"open": False}, prefer="return=minimal")
