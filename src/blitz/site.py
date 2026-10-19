"""The public review site: helpers without Claude check agents' reviews in the browser.

- `build`: docs/review/ (served by GitHub Pages): the proof page, the batch page and the key-squares
  page, with config.js connecting them to Supabase and the files.
- `publish`: a folder of reviewed puzzles to the site: their packet files to R2 (an S3-compatible
  bucket, public read), and a row each in Supabase's `puzzles` table.
- `fetch_decisions`: everything helpers recorded, combined per puzzle in the shape
  `xword-ocr import-reviews --decisions` takes.
- The batch page (docs/review/batch/, src/blitz/batch.html, the page the local watch serves at /batch/):
  every puzzle of a batch sorted by what the pipeline found, read from a snapshot on R2
  (sitebatch.py, `blitz site-publish-batch`).
- The key-squares page (docs/review/squares/, src/blitz/squares.html): one card per doubtful
  answer-key square. `publish` puts a folder's key-squares.json (`blitz key-squares`) in the
  `flags` table, and helpers' Keep / Change answers come back from `flag_checks`
  (site/schema-6-key-squares.sql).

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
         "answers.png", "answer_page.jpg", "_src/page.jpg", "_src/clue_page.jpg", "_src/continued_page.jpg")
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


SQUARES_DESC = ("Look at one letter of an old crossword's printed answer key at a time, and say whether we read it "
                "right. Part of the Every Puzzle Project, which is turning early crosswords into searchable, preserved records.")
SQUARES_HEAD = (REVIEW_HEAD.replace("<title>Check old crosswords: Every Puzzle Project</title>",
                                    "<title>Key squares: Every Puzzle Project</title>")
                .replace(REVIEW_DESC, SQUARES_DESC).replace("Help check old crosswords", "Check answer-key letters")
                .replace(f"{SITE}/review/", f"{SITE}/review/squares/"))


BATCH_DESC = ("Every puzzle in a batch of old crosswords, sorted by what the pipeline found when it read the scans, "
              "with why. Part of the Every Puzzle Project, which is turning early crosswords into searchable, preserved records.")
BATCH_HEAD = (REVIEW_HEAD.replace("<title>Check old crosswords: Every Puzzle Project</title>",
                                  "<title>The batch: Every Puzzle Project</title>")
              .replace(REVIEW_DESC, BATCH_DESC).replace("Help check old crosswords", "A batch of old crosswords")
              .replace(f"{SITE}/review/", f"{SITE}/review/batch/"))


def build(root: Path) -> Path:
    """The review pages and (once) a config to fill in:
    - docs/review/: the proof page (src/blitz/proof.html): check the finished puzzle against the scan;
    - docs/review/squares/: the key-squares page (squares.html): one doubtful answer-key square at a time;
    - docs/review/batch/: the batch page (batch.html): a batch's puzzles sorted by what the pipeline found;
    All three share docs/review/config.js. (The earlier change-by-change page, /review-old/, and the
    /review2/ redirect were taken off the site on 2026-10-19; review.html is still `blitz watch`.)"""
    out = root / "docs" / "review"
    out.mkdir(parents=True, exist_ok=True)
    if not (out / "config.js").exists():
        shutil.copy2(root / "site" / "config.example.js", out / "config.js")
    page = (Path(__file__).parent / "proof.html").read_text(encoding="utf-8")
    old = "<script>\nconst params"
    assert old in page
    page = page.replace(old, '<script src="config.js"></script>\n'
                             f'<script src="{SUPABASE_JS}"></script>\n' + old)
    page = page.replace("<title>Proof a puzzle</title>", REVIEW_HEAD)
    (out / "index.html").write_text(page, encoding="utf-8", newline="\n")

    sq = out / "squares"
    sq.mkdir(parents=True, exist_ok=True)
    page = (Path(__file__).parent / "squares.html").read_text(encoding="utf-8")
    old = "<script>\nconst SITE"
    assert old in page
    page = page.replace(old, '<script src="../config.js"></script>\n'
                             f'<script src="{SUPABASE_JS}"></script>\n' + old)
    page = page.replace("<title>Key squares</title>", SQUARES_HEAD)
    (sq / "index.html").write_text(page, encoding="utf-8", newline="\n")

    bt = out / "batch"
    bt.mkdir(parents=True, exist_ok=True)
    page = (Path(__file__).parent / "batch.html").read_text(encoding="utf-8")
    old = "<script>\nconst $"
    assert old in page
    page = page.replace(old, '<script src="../config.js"></script>\n' + old)
    page = page.replace("<title>Batch</title>", BATCH_HEAD)
    (bt / "index.html").write_text(page, encoding="utf-8", newline="\n")

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


def _rest_all(path: str, page: int = 1000) -> list:
    """Every row of a GET, a page at a time (the API returns at most 1000 rows per request)."""
    out, sep = [], "&" if "?" in path else "?"
    while True:
        rows = _rest("GET", f"{path}{sep}limit={page}&offset={len(out)}") or []
        out += rows
        if len(rows) < page:
            return out


def _pub(xdid: str) -> str:
    return xdid[:len(xdid) - len(xdid.lstrip("abcdefghijklmnopqrstuvwxyz"))] or "misc"  # judge1931-10-03 -> judge


def _thumb(packet: Path, size: int = 160) -> bytes | None:
    """A small picture of the puzzle's grid (its crop from the scan, grid.png) for the site's Browse
    list, so helpers can tell puzzles apart at a glance. None when the packet has no grid crop."""
    import io

    from PIL import Image

    src = packet / "grid.png"
    if not src.exists():
        return None
    with Image.open(src) as im:
        im = im.convert("L")
        im.thumbnail((size, size), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _page_small(packet: Path, width: int = 420) -> bytes | None:
    """The puzzle's page (page.jpg) small enough to read its layout at a glance: shown on a dropped
    puzzle's card, so a helper sees what was dropped without opening it."""
    import io

    from PIL import Image

    src = packet / "page.jpg"
    if not src.exists():
        return None
    with Image.open(src) as im:
        im = im.convert("RGB")
        im.thumbnail((width, width * 2), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=78, optimize=True)
    return buf.getvalue()


def dropped(folder: Path) -> dict[str, dict]:
    """The folder's puzzles dropped as not crosswords: {pid: {by, note}}, from its dropped.json
    (xword-ocr proof-packets writes it from the publication's ledger, drop:<pid>). They go on the
    site marked dropped, out of the review page's lists, under Browse's "Dropped" with a Restore
    button; a person's keep in the ledger takes a puzzle off dropped.json."""
    f = folder / "dropped.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def publish(folder: Path, batch: str = "", dry_run: bool = False, skip: tuple[str, ...] = (),
            squares_only: bool = False) -> list[str]:
    """Put a folder's reviewed puzzles on the site (except the puzzles in skip: e.g. ones already imported),
    and its key squares (key-squares.json from `blitz key-squares`) if it has them. squares_only: only the
    key squares and the key images their cards crop, without opening the puzzles' review pages.
    Puzzles in the folder's dropped.json go up marked dropped, with who dropped them and why
    (site/schema-7-drops.sql); a puzzle no longer on that list goes up open again.
    Returns the puzzles published."""
    drops = dropped(folder)
    squares = (json.loads((folder / "key-squares.json").read_text(encoding="utf-8"))
               if (folder / "key-squares.json").exists() else None)
    if squares_only and not squares:
        raise Stop(f"No key-squares.json in {folder}: make it with  blitz key-squares {folder} --pub <pub>")
    packets = [d for d in sorted(folder.iterdir())
               if (d / "review.json").exists() and (d / "ocr.json").exists() and d.name not in skip
               and (not squares_only or d.name in squares["puzzles"])]
    if not packets:
        raise Stop(f"No reviewed puzzles (with review.json) in {folder}.")
    # A puzzle as it stands now (task-packets --current-review) goes up only when the page
    # will show its xd file, built from committed data, so the site is a known version.
    refused = []
    for d in packets:
        rv = json.loads((d / "review.json").read_text(encoding="utf-8"))
        if rv.get("model") != "earlier reviews":
            continue
        if not rv.get("matches_xd"):
            refused.append(f"{d.name}: the page wouldn't show its xd ({'; '.join((rv.get('mismatches') or ['not checked'])[:3])})")
        elif any(not v or v.endswith("+changes") for v in (rv.get("built_from") or {"": ""}).values()):
            refused.append(f"{d.name}: built from uncommitted data ({rv.get('built_from')}): commit, then rebuild")
    if refused:
        raise Stop(f"{len(refused)} packets refused:\n  " + "\n  ".join(refused[:30]))
    if squares:
        # a skipped puzzle's cards stay as they are on the site (publish_squares leaves them alone)
        squares = {**squares, "puzzles": [x for x in squares["puzzles"] if x not in skip],
                   "flags": [f for f in squares["flags"] if f["xdid"] not in skip]}
        # the cards were read from the publication's repo: the same commit as the packets, and committed
        made = squares.get("built_from") or ""
        packet_commits = {(json.loads((d / "review.json").read_text(encoding="utf-8")).get("built_from") or {}).get(squares["pub"])
                          for d in packets} - {None}
        if not made or made.endswith("+changes"):
            raise Stop(f"key-squares.json was made from uncommitted {squares['pub']} data ({made or 'unknown'}): "
                       f"commit, then run blitz key-squares again")
        if packet_commits and packet_commits != {made}:
            raise Stop(f"key-squares.json was made from {squares['pub']} {made}, the packets from "
                       f"{', '.join(sorted(packet_commits))}: rebuild whichever is older")
        missing = sorted({f["xdid"] for f in squares["flags"]} - {d.name for d in packets})
        if missing:
            raise Stop(f"key-squares.json has cards for puzzles that aren't reviewed packets here: {', '.join(missing[:10])}")
    if dry_run:
        if squares:
            print(f"  and {len(squares['flags'])} key squares in {len({f['xdid'] for f in squares['flags']})} puzzles")
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
    base = lambda x: f"{public.rstrip('/')}/{_pub(x)}/{x}"
    if squares_only:
        need = {f["xdid"]: f["card"]["img"] for f in squares["flags"] if f["card"].get("img")}
        for d in packets:
            if d.name in need and (d / need[d.name]).exists():
                s3.upload_file(str(d / need[d.name]), bucket, f"{_pub(d.name)}/{d.name}/{need[d.name]}", ExtraArgs={
                    "ContentType": mimetypes.guess_type(need[d.name])[0] or "application/octet-stream",
                    "CacheControl": "no-cache"})
        publish_squares(squares, base, batch or folder.name)
        return [d.name for d in packets]
    for d in packets:
        pub = _pub(d.name)
        files = {}
        for f in FILES:
            src = d / f
            if src.exists():
                s3.upload_file(str(src), bucket, f"{pub}/{d.name}/{f}", ExtraArgs={
                    "ContentType": mimetypes.guess_type(f)[0] or "application/octet-stream",
                    "CacheControl": "no-cache" if f.endswith(".json") else "public, max-age=86400"})
                files[f] = True
        thumb = _thumb(d)
        if thumb:
            s3.put_object(Bucket=bucket, Key=f"{pub}/{d.name}/thumb.png", Body=thumb, ContentType="image/png",
                          CacheControl="public, max-age=86400")
            files["thumb.png"] = True
        small = _page_small(d) if d.name in drops else None
        if small:
            s3.put_object(Bucket=bucket, Key=f"{pub}/{d.name}/page-small.jpg", Body=small, ContentType="image/jpeg",
                          CacheControl="public, max-age=86400")
            files["page-small.jpg"] = True
        rv = json.loads((d / "review.json").read_text(encoding="utf-8"))
        ocr = json.loads((d / "ocr.json").read_text(encoding="utf-8"))
        status = "escalated" if rv.get("escalate") else ("ready" if rv.get("ready") else "needs a person")
        title = (rv.get("corrections") or {}).get("meta:title") or ocr.get("title", "")
        cu = rv.get("checkup") or {}
        rows.append({"xdid": d.name, "pub": pub, "batch": batch or folder.name, "title": title[:200],
                     "base_url": f"{public.rstrip('/')}/{pub}/{d.name}", "files": files,
                     "review_status": status, "open": True,
                     "checkup": {"grade": cu.get("grade", ""), "high": sum(w["level"] == "high" for w in cu.get("warnings", [])),
                                 "medium": sum(w["level"] == "medium" for w in cu.get("warnings", []))} if cu else None,
                     "dropped": ({"by": drops[d.name].get("by", ""), "note": drops[d.name].get("note", "")[:500]}
                                 if d.name in drops else None)})
        print(f"  {d.name}: {len(files)} files")
    try:
        _rest("POST", "puzzles?on_conflict=xdid", rows, prefer="resolution=merge-duplicates,return=minimal")
    except urllib.error.HTTPError as e:  # the checkup column (schema-4-checkup.sql) isn't there yet: publish without it
        msg = e.read().decode("utf-8", "replace")
        if "dropped" in msg:  # no dropped column (schema-7-drops.sql) yet
            if drops:
                raise Stop(f"{len(drops)} puzzles here are dropped as not crosswords, and the site has no place to mark "
                           "them yet: run site/schema-7-drops.sql once in the Supabase SQL editor, then publish again.")
            _rest("POST", "puzzles?on_conflict=xdid", [{k: v for k, v in r.items() if k != "dropped"} for r in rows],
                  prefer="resolution=merge-duplicates,return=minimal")
            return [r["xdid"] for r in rows]
        if "checkup" not in msg:
            raise
        print("  (no checkup column yet: run site/schema-4-checkup.sql to show grades in the list)")
        _rest("POST", "puzzles?on_conflict=xdid", [{k: v for k, v in r.items() if k not in ("checkup", "dropped")} for r in rows],
              prefer="resolution=merge-duplicates,return=minimal")
    if squares:
        publish_squares(squares, base, batch or folder.name)
    return [r["xdid"] for r in rows]


def publish_squares(squares: dict, base, batch: str) -> None:
    """The key squares' cards into `flags`. The list is the whole truth for its puzzles: their open
    cards that aren't in it any more (a person settled the square, or the key changed) are closed,
    never deleted, so helpers' checks on them stay for import. base(xdid): the packet's URL."""
    page = squares.get("page", "key-squares")
    rows = [{"xdid": f["xdid"], "sq": f["sq"], "page": page, "pub": f["pub"], "source": f["source"], "batch": batch,
             "open": True, "card": {**f["card"], "img": f"{base(f['xdid'])}/{f['card']['img']}" if f["card"].get("img") else None}}
            for f in squares["flags"]]
    try:
        for i in range(0, len(squares["puzzles"]), 80):
            chunk = ",".join(squares["puzzles"][i:i + 80])
            _rest("PATCH", f"flags?page=eq.{page}&open=eq.true&xdid=in.({chunk})", {"open": False}, prefer="return=minimal")
        for i in range(0, len(rows), 500):
            _rest("POST", "flags?on_conflict=xdid,page,sq", rows[i:i + 500], prefer="resolution=merge-duplicates,return=minimal")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        if "flags" in body and ("does not exist" in body or "schema cache" in body):
            raise Stop("The site has no key-squares tables yet: run site/schema-6-key-squares.sql in Supabase's SQL editor.")
        raise Stop(f"Couldn't publish the key squares: {e.code} {body[:300]}")
    print(f"  {len(rows)} key squares in {len({r['xdid'] for r in rows})} of {len(squares['puzzles'])} puzzles: "
          f"{SITE}/review/squares/?pub={squares.get('pub', '')}")


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
    # the review page's whole reviews (site/schema-5-proofs.sql): per helper, the decision, their edits
    # (field -> new value), comments, each part's verdict and a note. Not applied on import yet.
    for r in _rest("GET", "proofs?select=*&order=at") or []:
        rv = r.get("review") or {}
        get(r["xdid"]).setdefault("proofs", {})[r.get("who") or who(r)] = {
            "decision": r["decision"], "edits": rv.get("edits", {}), "comments": rv.get("comments", []),
            "parts": rv.get("status", {}), "note": rv.get("note", ""), "at": r["at"],
            "xd": rv.get("xd", "")}  # the xd version the page showed (packet xd_fp); "" before 2026-10-13
    # puts back of puzzles dropped as not crosswords (site/schema-7-drops.sql): per helper, a note and when;
    # the importer records each as a person's keep on drop:<pid> in the publication's ledger
    try:
        restores = _rest("GET", "restores?select=*&order=at") or []
    except urllib.error.HTTPError:  # no restores table yet
        restores = []
    for r in restores:
        get(r["xdid"]).setdefault("restores", {})[r.get("who") or who(r)] = {"note": r.get("note", ""), "at": r["at"]}
    for x, sq in fetch_squares().items():
        get(x)["squares"] = sq
    for x, p in out.items():
        p.update(consensus(said.get(x, {}), votes.get(x, {})))
    if agreed_only:
        out = {x: p for x, p in out.items() if p["agreement"] == "agreed"}
    return {"puzzles": out}


def fetch_squares(page: str = "key-squares") -> dict[str, dict]:
    """The key-squares page's cards and helpers' answers, per puzzle:
    {xdid: {"open": [sq, ...], "cards": {sq: {letter, suggest, source, open}}, "checks": {sq: {helper: {was, value, at}}}}}.
    A helper is the name they gave, or "a helper <id>" for a guest without one (and two people who gave
    the same name are told apart the same way). Nothing if the site has no such tables yet."""
    try:
        flags = _rest_all(f"flags?select=xdid,sq,source,open,card&page=eq.{page}&order=xdid,sq")
        checks = _rest_all(f"flag_checks?select=xdid,sq,user_id,who,was,value,at&page=eq.{page}&order=at")
    except urllib.error.HTTPError as e:
        if e.code in (400, 404):
            return {}
        raise
    out: dict[str, dict] = {}
    get = lambda x: out.setdefault(x, {"open": [], "cards": {}, "checks": {}})
    for f in flags:
        p = get(f["xdid"])
        p["cards"][f["sq"]] = {"letter": f["card"].get("letter", ""), "suggest": f["card"].get("suggest", ""),
                               "source": f["source"], "open": f["open"]}
        if f["open"]:
            p["open"].append(f["sq"])
    names: dict[str, set] = {}
    for c in checks:
        names.setdefault(c["who"] or "", set()).add(c["user_id"])
    for c in checks:
        who = c["who"] if c["who"] and len(names[c["who"]]) == 1 else f"{c['who'] or 'a helper'} {c['user_id'][:6]}"
        get(c["xdid"])["checks"].setdefault(c["sq"], {})[who] = {"was": c["was"], "value": c["value"], "at": c["at"]}
    return out


def close(xdids: list[str]) -> None:
    """Take puzzles off the site (e.g. once imported)."""
    for x in xdids:
        _rest("PATCH", f"puzzles?xdid=eq.{x}", {"open": False}, prefer="return=minimal")
