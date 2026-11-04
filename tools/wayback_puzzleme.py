#!/usr/bin/env python
"""Recover Washington Post crosswords from raw Wayback Machine captures of their
PuzzleMe (Amuse Labs) player pages.

Replay of those captures shows "Access Denied", but the raw capture (the `id_`
flag) still holds the whole puzzle as a `window.rawc` blob, which xword-dl's
decoder reads (gxd-downloader's amuse adapter and converter, used as a library;
set GXD_DOWNLOADER to its checkout). Output is .xd plus the decoded payload JSON.

  python tools/wayback_puzzleme.py cdx   --sets wapo-eb wapo-daily wapo-whm --years 2021 2022 2023
  python tools/wayback_puzzleme.py fetch --sets wapo-eb --years 2022
  python tools/wayback_puzzleme.py report

Everything lands in recovered/ (cdx/*.tsv listings, raw/ HTML cache, puz/ files,
manifest.tsv). Requests are paced (default 6 s apart) and retried; an empty CDX
result is only trusted if a control query succeeds right after it.
"""
import argparse
import base64
import csv
import datetime
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "recovered"
GXD_DOWNLOADER = Path(os.environ.get("GXD_DOWNLOADER", Path.home() / "Projects" / "gxd-downloader"))
PLAYER = "cdn1.amuselabs.com/wapo/crossword"
PACE = 6.0
_last = [0.0]


def get(url, tries=5):
    """curl --compressed, paced, retried. Returns (status, body) or (0, '')."""
    for attempt in range(tries):
        wait = PACE - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        r = subprocess.run(["curl", "--compressed", "-s", "-L", "-m", "90", "-w", "\n%{http_code}", url],
                           capture_output=True)
        body, _, code = r.stdout.rpartition(b"\n")
        code = int(code or 0)
        text = body.decode("utf-8", "replace")
        if code == 200 and "Temporarily Offline" not in text[:2000]:
            return code, text
        if code == 404:
            return code, text
        time.sleep(PACE * (attempt + 2))  # back off on 429/5xx/"Temporarily Offline"
    return 0, ""


def cdx_query(params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    code, text = get("https://web.archive.org/cdx/search/cdx?" + q)
    if not code:
        return None
    return [ln.split(" ") for ln in text.splitlines() if ln.strip()]


def cdx_listing(set_name, year, force=False):
    """All captures (any status) of the player for one set in one year -> cdx/<set>-<year>.tsv"""
    path = OUT / "cdx" / f"{set_name}-{year}.tsv"
    if path.exists() and not force:
        return [ln.split("\t") for ln in path.read_text().splitlines()]
    q = {"url": PLAYER + "*", "output": "txt", "fl": "timestamp,original,statuscode,digest",
         "from": f"{year}0101", "to": f"{year}1231", "limit": "100000"}
    qs = "&".join(f"{k}={v}" for k, v in q.items())
    qs += f"&filter=original:.*set={set_name}.*"
    code, text = get("https://web.archive.org/cdx/search/cdx?" + qs)
    if not code:
        print(f"  {set_name} {year}: CDX failed", file=sys.stderr)
        return None
    rows = [ln.split(" ") for ln in text.splitlines() if ln.strip()]
    if not rows:
        # an empty result isn't evidence: run a control query that must hit
        ctl = cdx_query({"url": PLAYER + "?id=ebirnholz_220306%26set=wapo-eb", "output": "txt",
                         "fl": "timestamp", "limit": "1"})
        if not ctl:
            print(f"  {set_name} {year}: empty, control failed -> NOT recorded", file=sys.stderr)
            return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join("\t".join(r) for r in rows) + ("\n" if rows else ""))
    return rows


def puzzle_id(original):
    qs = parse_qs(urlparse(original).query)
    return (qs.get("id") or [""])[0]


def best_per_id(rows):
    """One capture per puzzle id: the earliest with the most common digest (simple: earliest)."""
    by = {}
    for ts, orig, status, digest in rows:
        if status != "200":
            continue
        pid = puzzle_id(orig)
        if pid and (pid not in by or ts < by[pid][0]):
            by[pid] = (ts, orig, digest)
    return by


def load_decoder():
    sys.path.insert(0, str(GXD_DOWNLOADER))
    from gxd_downloader.adapters import amuse
    from gxd_downloader.convert import Context
    from gxd_downloader.convert import amuse as conv
    return amuse, conv, Context


def extract_rawc(html):
    for line in html.splitlines():
        if "window.rawc" in line or "window.puzzleEnv.rawc" in line:
            parts = line.strip().split("'")
            if len(parts) > 1:
                return parts[1]
    m = re.search(r'<script[^>]*id="params"[^>]*>(.*?)</script>', html, re.S)
    if m:
        return json.loads(m.group(1)).get("rawc") or ""
    return ""


def decode_rawc(rawc, dec):
    """Plain base64 JSON (early-2022 Sundays) or the adapter's scrambled form."""
    amuse = dec[0]
    try:
        return base64.b64decode(rawc, validate=True).decode("utf-8")
    except Exception:
        pass
    text = amuse.unscramble(rawc)
    if not text:
        raise ValueError("adapter could not unscramble rawc")
    return text


def date_from(pid, data, set_name):
    m = re.match(r"ebirnholz_(\d{6})$|tca(\d{6})$", pid)
    if m:
        s = m.group(1) or m.group(2)
        return datetime.date(2000 + int(s[:2]), int(s[2:4]), int(s[4:])).isoformat()
    ts = int(data.get("publishTime", 0) or 0) // 1000
    return datetime.date.fromtimestamp(ts).isoformat() if ts else ""


def fetch_one(pid, set_name, ts, orig, dec):
    """Returns manifest row dict."""
    row = dict(id=pid, set=set_name, timestamp=ts, title="", author="", date="", status="")
    raw = OUT / "raw" / f"{set_name}__{pid}__{ts}.html"
    if raw.exists():
        html = raw.read_text(encoding="utf-8", errors="replace")
    else:
        code, html = get(f"https://web.archive.org/web/{ts}id_/{orig}")
        if not code:
            row["status"] = "fetch-failed"
            return row
        if code == 404:
            row["status"] = "404"
            return row
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_text(html, encoding="utf-8")
    rawc = extract_rawc(html)
    if not rawc:
        row["status"] = "no-rawc"
        return row
    try:
        text = decode_rawc(rawc, dec)
        data = json.loads(text)
        row["title"] = data.get("title", "").strip()
        row["author"] = data.get("author", "").strip()
        row["date"] = date_from(pid, data, set_name)
        ctx = dec[2](set_name, datetime.date.fromisoformat(row["date"]) if row["date"] else None,
                     f"{pid}.json", orig)
        xd = dec[1].convert(text.encode("utf-8"), ctx)
    except Exception as e:  # noqa
        row["status"] = f"decode-failed: {type(e).__name__}: {e}"[:120]
        return row
    base = OUT / "xd" / set_name / f"{row['date'] or 'nodate'}_{pid}"
    base.parent.mkdir(parents=True, exist_ok=True)
    base.with_suffix(".json").write_text(text, encoding="utf-8")
    base.with_suffix(".xd").write_text(xd.to_xd(), encoding="utf-8")
    row["status"] = "ok"
    return row


MANIFEST_FIELDS = ["id", "set", "timestamp", "title", "author", "date", "status"]


def read_manifest():
    p = OUT / "manifest.tsv"
    if not p.exists():
        return {}
    with open(p, newline="", encoding="utf-8") as f:
        return {(r["set"], r["id"]): r for r in csv.DictReader(f, delimiter="\t")}


def write_manifest(rows):
    OUT.mkdir(exist_ok=True)
    with open(OUT / "manifest.tsv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, MANIFEST_FIELDS, delimiter="\t", extrasaction="ignore")
        w.writeheader()
        for k in sorted(rows, key=lambda k: (rows[k]["set"], rows[k]["date"], rows[k]["id"])):
            w.writerow(rows[k])


def cmd_cdx(a):
    for s in a.sets:
        for y in a.years:
            rows = cdx_listing(s, y, a.force)
            if rows is None:
                print(f"{s} {y}: UNKNOWN (query failed)")
            else:
                ids = best_per_id(rows)
                print(f"{s} {y}: {len(rows)} captures, {len(ids)} distinct ids")


def cmd_fetch(a):
    dec = load_decoder()
    manifest = read_manifest()
    for s in a.sets:
        for y in a.years:
            rows = cdx_listing(s, y)
            if rows is None:
                continue
            todo = sorted(best_per_id(rows).items())
            if a.limit:
                todo = todo[: a.limit]
            for pid, (ts, orig, _) in todo:
                old = manifest.get((s, pid))
                if old and old["status"].startswith("ok"):
                    continue
                r = fetch_one(pid, s, ts, orig, dec)
                manifest[(s, pid)] = r
                print(f"{s} {pid} {ts} {r['status']} {r['title']}")
                write_manifest(manifest)


def cmd_picker(a):
    """List a set's puzzles from its wp-picker page captures (titles and dates only: the picker
    holds no puzzle data) and record each in the manifest, 'not-captured' unless a player page was fetched."""
    manifest = read_manifest()
    code, text = get("https://web.archive.org/cdx/search/cdx?output=txt&fl=timestamp,statuscode,original"
                     f"&url=cdn1.amuselabs.com/wapo/wp-picker&matchType=prefix&filter=original:.*set={a.set}.*"
                     f"&filter=statuscode:200&from={a.year}&to={a.year}")
    caps = [ln.split(" ", 2) for ln in text.splitlines() if ln.count(" ") >= 2]
    print(f"{len(caps)} picker captures for {a.set} {a.year}")
    for ts, _, orig in sorted(caps, reverse=True):
        code, html = get(f"https://web.archive.org/web/{ts}id_/{orig}")
        tiles = re.findall(r'data-id="(\w+)".*?tile-title">(.*?)</div>.*?tile-date">(.*?)</div>', html, re.S)
        for pid, title, date in tiles:
            if (a.set, pid) in manifest and manifest[(a.set, pid)]["status"].startswith("ok"):
                continue
            d = datetime.datetime.strptime(date.strip(), "%d %B %Y").date().isoformat()
            manifest[(a.set, pid)] = dict(id=pid, set=a.set, timestamp=ts, title=title.strip(), author="",
                                          date=d, status="not-captured (listed in picker only)")
            print(a.set, pid, d, title.strip())
        if tiles:
            break
    write_manifest(manifest)


def cmd_report(a):
    cnt = {}
    for p in sorted((OUT / "cdx").glob("*.tsv")):
        s, y = p.stem.rsplit("-", 1)
        rows = [ln.split("\t") for ln in p.read_text().splitlines()]
        ids = best_per_id(rows)
        stamps = sorted(v[0] for v in ids.values())
        n302 = sum(1 for r in rows if r[2] != "200")
        cnt[(s, y)] = (len(rows), n302, len(ids), stamps[0][:8] if stamps else "", stamps[-1][:8] if stamps else "")
    print("set	year	captures	non200	ids200	first	last")
    for (s, y), v in sorted(cnt.items()):
        print(f"{s}\t{y}\t" + "\t".join(map(str, v)))
    m = read_manifest()
    tally = {}
    for r in m.values():
        k = (r["set"], r["date"][:4] or "?", r["status"].split(":")[0])
        tally[k] = tally.get(k, 0) + 1
    print("\nset\tyear\tstatus\tn")
    for k, n in sorted(tally.items()):
        print("\t".join(k) + f"\t{n}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("cdx", cmd_cdx), ("fetch", cmd_fetch)):
        p = sub.add_parser(name)
        p.add_argument("--sets", nargs="+", default=["wapo-eb"])
        p.add_argument("--years", nargs="+", type=int, default=[2022])
        p.add_argument("--force", action="store_true")
        p.add_argument("--limit", type=int, default=0)
        p.set_defaults(fn=fn)
    p = sub.add_parser("picker")
    p.add_argument("--set", default="wapo-whm")
    p.add_argument("--year", type=int, default=2022)
    p.set_defaults(fn=cmd_picker)
    sub.add_parser("report").set_defaults(fn=cmd_report)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
