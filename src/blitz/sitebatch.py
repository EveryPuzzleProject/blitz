"""The batch page on the review site: a snapshot of what the local viewer shows for a batch.

The batch page (src/blitz/batch.html) reads one batch's records: locally from the watch (xword-ocr
watch: /api/batch, /api/overlay/<run>/<pid>/<n> and the images it serves), on the review site from
static files. `snapshot` asks a running watch for exactly what its page fetches and writes it as those
files; `publish` puts them on R2 under batch/<name>/ and lists the batch in batch/batches.json.

Nothing here reads a milestone or works anything out: the snapshot is the watch's answers, so the
hosted page draws the boxes the local one does, each with its source (blitz CLAUDE.md: views never
compute). What a volunteer doesn't need is left out: the maintainer's tools (the Notes rule, the
Editor rule, the import, the text step's re-run and spend) and the ledger's ship / hold, since Ready
and Not ready are the proof page's (the site's database). Drops stay: they're the Not a crossword list.
"""

from __future__ import annotations

import json
import mimetypes
import re
import shutil
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .work import Stop

# what the page reads from /api/batch; the rest (the tools' data) stays local
KEEP = ("run", "current", "pubid", "counts", "causes", "puzzles")
# a puzzle's ledger fields a volunteer doesn't see: the proof page's decisions and who made them
VOLUNTEER_DROP = ("proof", "diagnosis", "said", "held_for_you", "rule")


def _get(watch: str, path: str) -> bytes:
    try:
        with urllib.request.urlopen(watch.rstrip("/") + path, timeout=300) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise Stop(f"The watch answered {e.code} for {path}: {e.read()[:300].decode('utf-8', 'replace')}")
    except urllib.error.URLError as e:
        raise Stop(f"No watch at {watch} ({e.reason}): start it (xword-ocr watch --out <harvest> ...) and try again.")


def _slug(s: str) -> str:
    return re.sub(r"[^\w.-]+", "_", s).strip("_")


def snapshot(watch: str, out: Path, name: str, title: str = "", run: str = "") -> dict:
    """The batch page's data for one run (default: the watch's current run, from the publication's
    pipeline/triage/runs.json) as static files in out: batch.json, overlay/<pid>-<n>.json, pages/,
    thumbs/ and page/, every URL in them relative to out. Returns batch.json's contents."""
    q = "?run=" + urllib.parse.quote(run) if run else ""
    d = json.loads(_get(watch, "/api/batch" + q))
    if d.get("error"):
        raise Stop(f"The watch: {d['error']}")
    run = d["run"]
    if out.exists():
        if not (out / "batch.json").exists():
            raise Stop(f"{out} exists and isn't a batch snapshot: give another --out.")
        shutil.rmtree(out)
    out.mkdir(parents=True)
    got: set[str] = set()

    def fetch(url: str, rel: str) -> str:
        if rel not in got:
            f = out / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(_get(watch, url))
            got.add(rel)
        return rel

    for p in d["puzzles"]:
        pid = p["pid"]
        p["thumb"] = fetch(p["thumb"], f"thumbs/{pid}.png") if p.get("thumb") else ""
        p["page"] = fetch(p["page"], f"page/{pid}.jpg") if p.get("page") else ""
        for m in p.get("maps") or []:
            page = _slug(m["page"])  # one file a page, however many puzzles are on it
            src = m["image"]
            m["image"] = fetch(src, f"pages/{page}.jpg")
            m["full"] = fetch(src + "?w=1400", f"pages/{page}-1400.jpg")
            ov = json.loads(_get(watch, f"/api/overlay/{urllib.parse.quote(run)}/{pid}/{m['n']}"))
            ov["image"] = m["image"]
            m["overlay"] = f"overlay/{pid}-{m['n']}.json"
            (out / "overlay").mkdir(exist_ok=True)
            (out / m["overlay"]).write_text(json.dumps(ov, ensure_ascii=False), encoding="utf-8")
        if p.get("choice") != "drop":
            p.update(choice="", by="", note="", at="")
        for k in VOLUNTEER_DROP:
            p.pop(k, None)
    thumbs = {p["pid"]: p["thumb"] for p in d["puzzles"]}
    for c in (d.get("causes") or {}).get("causes", []):
        for x in c.get("puzzles", []):
            x["thumb"] = thumbs.get(x["pid"], "")
            if x.get("choice") != "drop":
                x["choice"] = ""
    snap = {k: d[k] for k in KEEP if k in d}
    snap["run_notes"] = {run: (d.get("run_notes") or {})[run]} if run in (d.get("run_notes") or {}) else {}
    snap["runs"] = [run]
    snap["snapshot"] = {"name": name, "title": title or name, "run": run,
                        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "puzzles": len(d["puzzles"]), "dropped": sum(p.get("choice") == "drop" for p in d["puzzles"])}
    (out / "batch.json").write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    return snap


def publish(out: Path, dry_run: bool = False) -> list[str]:
    """A snapshot folder to the site's bucket under batch/<name>/ (what was there before is replaced),
    and the batch first in batch/batches.json. Returns the keys written."""
    from .site import _env

    snap = json.loads((out / "batch.json").read_text(encoding="utf-8"))["snapshot"]
    files = sorted(f for f in out.rglob("*") if f.is_file())
    prefix = f"batch/{snap['name']}/"
    keys = [prefix + f.relative_to(out).as_posix() for f in files]
    if dry_run:
        return keys
    account, key_id, secret, bucket = _env("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")
    try:
        import boto3
    except ImportError:
        raise Stop("Publishing needs boto3: run it as  uv run --extra site blitz site-publish-batch ...")
    s3 = boto3.client("s3", endpoint_url=f"https://{account}.r2.cloudflarestorage.com",
                      aws_access_key_id=key_id, aws_secret_access_key=secret, region_name="auto")
    old = set()
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        old |= {o["Key"] for o in page.get("Contents", [])}
    for f, k in zip(files, keys):
        s3.upload_file(str(f), bucket, k, ExtraArgs={
            "ContentType": mimetypes.guess_type(f.name)[0] or "application/octet-stream",
            "CacheControl": "no-cache" if f.suffix == ".json" else "public, max-age=86400"})
    stale = sorted(old - set(keys))  # an earlier snapshot's files this one doesn't have
    for i in range(0, len(stale), 1000):
        s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": k} for k in stale[i:i + 1000]]})
    try:
        idx = json.loads(s3.get_object(Bucket=bucket, Key="batch/batches.json")["Body"].read())
    except s3.exceptions.NoSuchKey:
        idx = {}
    rows = [b for b in idx.get("batches", []) if b["name"] != snap["name"]]
    idx = {"_about": "The batches on the review site's batch page (blitz site-publish-batch), newest first.",
           "batches": [snap, *rows]}
    s3.put_object(Bucket=bucket, Key="batch/batches.json", Body=json.dumps(idx, indent=1).encode("utf-8"),
                  ContentType="application/json", CacheControl="no-cache")
    return keys
