"""The edition: the last step of each publication's process, and the manifest that lists what it published (blitz
design/publishing-editions.md, design/ship.md "The edition").

EPP publishes two layers of every puzzle. The transcription is the puzzle as printed, what `blitz ship` writes to
`xd/` (reading fixes and key-letter corrections applied, with their note). The edition is derived from it by rule
and never edited by hand: the clue and header misprint corrections that count under the ship rule (less any the
owner declined) are applied where that is mechanical (the printed words present once), each with a note saying
what was printed, and the publication's Notes rule picks which printed lines are the puzzle's notes. A mark the
step can't place holds that puzzle's edition, with a code; it never guesses.

    edition/<xdid>.xd        the edition (no file while it is held)
    pipeline/edition.json    what each edition was made from, so it is made again only when that changes
    shipped.tsv              the manifest: one row per puzzle EPP has ever advertised, with its status

`blitz ship` runs it when it writes or records; `blitz edition <pub>` runs it alone (after a mark is declined, or
the owner's "Publish the edition" given). It never touches `xd/`.

Helpers it shares with ship are imported where they are used: ship imports this module at its top (corrected(),
the Notes rule), so this one can't import ship at its own.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path

EDITION = "edition"  # edition/<xdid>.xd beside xd/
MANIFEST = "shipped.tsv"
RECORD = ("pipeline", "edition.json")
NOTED_NEEDS_EVIDENCE = True  # a mark whose words meant are already in the row gets its note only when a record shows the
#   printed words were there (the packet's text review, or an edit, swapped them); otherwise the edition is held
#   (mark-unplaced). The project manager's default of 2026-11-16, pending the owner's word: False writes the note anyway.
CODES = {  # triage codes the edition step publishes with a word in `why` (the edition's own list, not ship-export's)
    "cryptic-no-key": "a cryptic with no key grid: published with this code, pending the owner",
}
NOTES_HEAD = "Puzzle notes:"  # the printed lines the Notes rule takes: the puzzle's notes
FIXED_HEAD = "Misprints corrected:"  # one line per clue or header misprint the edition corrected, saying what was printed
COLS = ("xdid", "date", "number", "status", "why", "transcription", "transcription_sha256", "edition", "edition_sha256",
        "shipped_at", "batch", "published", "record_url", "proof_url", "updated_at", "form", "page_url")
# the columns a downstream reader (gxd-downloader) takes as a feed (the owner, 2026-11-25), at the end so a reader of the
# first fourteen is unchanged: updated_at, the date the row's file last changed (its edition, or its transcription while
# it has none); form, the file's shape (v1: the blank-line xd; v2: EPP's field form, blitz design/xd-fields.md); page_url,
# a page that resolves for the puzzle: its record page once one is published, its proof page until then
STATUSES = ("published", "held", "withdrawn")
# the ledger's publish-edition:<batch>: the owner's "Publish the edition" on the batch page, answer publish, or unpublish
# when taken back. Not the review site's "publish" (site-publish, ship --publish), which puts packets and records on the site.
PUBLISH = "publish-edition:"
NOTE_LABELS = ("intro", "instructions")  # the printed lines that are the puzzle's notes when the publication has no Notes rule
HOLDS = {  # an edition held: no file is written, and the manifest says why
    "mark-unplaced": "a misprint mark the edition can't place",
    "mark-invalid": "a misprint mark that can't be taken",
    "key-declined": "the owner declined a key-letter correction the transcription carries: ship it again first",
}


# ---- moved here from ship-export (2026-11-16): the correction of the print, and the Notes rule -----------------

def corrected(text: str, corrections: list[dict]) -> tuple[str, list[str], list[dict]]:
    """An xd with its corrections of the print (a clue's, a header's) applied: (the text, the editorial notes for
    the xd's notes, what became of each: [{key, printed, meant, by, done, note}]). done: applied (the printed word
    was there once, and the word meant is in its place), noted (the xd already had the word meant: the note alone),
    not applied (neither is there, or it can't be placed: nothing is changed, and nothing is said in the notes).
    The edition step and `blitz ship-export` both use it."""
    from .ship import HEADER, _TYPO_KEY, _count, _field, _label, _pairs, _read, _swap, apply_edits, mark_problem
    notes, rows = [], []
    for c in corrections or []:
        key, printed, meant = c.get("key") or "", c.get("printed") or "", c.get("meant") or ""
        heads, _, clues = _read(text)
        done, note = "not applied", ""
        if not mark_problem(c) and _TYPO_KEY.fullmatch(key) and not key.startswith("cell:"):
            cur = clues.get(key[5:]) if key.startswith("clue:") else heads.get(HEADER[_field(key)])
            if cur is not None and _count(cur, printed) == 1:  # the printed word, whole, once: the word meant takes its place
                ek = key if key.startswith("clue:") else f"meta:{_field(key)}"
                new, did = apply_edits(text, {ek: _swap(cur, printed, meant)})
                if ek in did:  # said to be applied only when it was (a linked-ends xd can refuse an edit)
                    text, done = new, "applied"
            elif cur is not None and not _count(cur, printed) and _count(cur, meant):
                done = "noted"
            note = f"{_label(key, _pairs(text))} is printed '{printed}'; corrected to '{meant}'." if done != "not applied" else ""
        if note:
            notes.append(note)
        rows.append({"key": key, "printed": printed, "meant": meant, "by": c.get("by", ""), "done": done, "note": note,
                     **({"kind": c["kind"]} if c.get("kind") else {})})  # whose: the public copies name people by it
    return text, notes, rows


def notes_labels(repo: Path, pub: str, records: list[dict] | None = None) -> tuple[tuple, str]:
    """The line labels whose kept lines are the puzzle's notes: the owner's Notes rule in the ledger
    (notes-rule:<pubid>, set on the batch page), else NOTE_LABELS. Returns (labels, where it came from)."""
    from .ship import ledger
    rec = next((r for r in reversed(ledger(repo) if records is None else records) if r.get("id") == f"notes-rule:{pub}"), None)
    if rec and rec.get("answer") is not None:
        return tuple((rec.get("notes_rule") or {}).get("labels") or []), f"the Notes rule of {rec.get('at', '')[:10]} by {rec.get('by', '')}"
    return NOTE_LABELS, "no Notes rule recorded: the default (intro, instructions)"


# ---- one puzzle's edition: a pure function of its inputs ----------------------------------------------------------

def _mark(c: dict) -> tuple[str, str, str]:
    return (str(c.get("key", "")), str(c.get("printed", "")).strip(), str(c.get("meant", "")).strip())


def _one_block_line(text: str) -> str:
    """A printed line as one entry of a notes block: no blank line inside it (that would end the block)."""
    return re.sub(r"\n\s*\n", "\n", str(text).replace("\r\n", "\n")).strip()


def _norm(key: str) -> str:
    """A mark's or an edit's key, with a header under either name (ev:title, meta:title) as meta:<field>."""
    from .ship import _field
    return f"meta:{_field(key)}" if _field(key) else key


def evidenced(c: dict, evidence: list[dict]) -> bool:
    """Whether a record shows the mark's printed words were in its row and were swapped for the words meant: a change
    the packet's text review made, or an edit record, on the same row, whose before has the printed words and whose
    after has the words meant."""
    from .ship import _count
    k, printed, meant = _norm(c.get("key", "")), str(c.get("printed", "")), str(c.get("meant", ""))
    return any(_norm(e.get("key", "")) == k and _count(str(e.get("before", "")), printed) and _count(str(e.get("after", "")), meant)
               for e in evidence or [])


def make(text: str, marks: list[dict] = (), declines=(), labels=NOTE_LABELS, printed: list[dict] = (),
         records: list[dict] = (), evidence: list[dict] = ()) -> dict:
    """One puzzle's edition from its transcription (`text`, the file in xd/) and what ship recorded: `marks`, the
    corrections of the print that count under the ship rule (provenance's `corrections`); `declines`, the owner's
    "not a misprint" as (key, printed, meant); `labels`, the Notes rule; `printed`, the kept printed lines with their
    labels; `records`, the transcription's edit records (a key-letter correction the owner has since declined holds
    the edition: the transcription itself is wrong until it is shipped again); `evidence`, the changes that show a
    row's printed words were swapped before it shipped (the packet's text-review changes and the edit records: see
    NOTED_NEEDS_EVIDENCE). Marks are applied in a fixed order (key, printed, meant).

    Returns {text (None when held), held: [{code, why}], corrections: [{key, printed, meant, by, done, note}],
    declined: [{key, printed, meant, by}], notes: [the Puzzle notes lines]}. Same inputs, same bytes."""
    from .ship import _TYPO_KEY, mark_problem, sectioned, with_notes
    if sectioned(text):
        # EPP's field form (blitz design/xd-fields.md): the paper's other words are in its ## Printed and each correction
        # is a field beside the print (^Correction, ^Answer-Correction), so the edition rewrites nothing and adds no
        # Puzzle notes block; a mark from the review site has no place to go in it yet, and holds the edition
        live = [c for c in marks or [] if _mark(c) not in {(k, p, m) for k, p, m in declines}]
        held = [{"code": "mark-unplaced", "why": f"{c.get('key', '')}: a misprint mark on a field-form xd: record it as ^Correction "
                 "in the transcription"} for c in live]
        return {"text": None if held else text, "held": held, "corrections": [], "declined": [], "notes": []}
    no = {(k, p, m) for k, p, m in declines}
    live = sorted((c for c in marks or [] if _mark(c) not in no), key=_mark)
    declined = [{k: c.get(k, "") for k in ("key", "printed", "meant", "by")} for c in marks or [] if _mark(c) in no]
    held = []
    undone = [e for e in records or [] if e.get("class") == "key correction" and e.get("misprint")
              and (e.get("key", ""), str(e["misprint"].get("printed", "")).strip(), str(e["misprint"].get("meant", "")).strip()) in no]
    if undone:
        held.append({"code": "key-declined", "why": "the owner declined the key correction(s) "
                     + ", ".join(f"{e['key'][5:]} {e['misprint'].get('printed')}->{e['misprint'].get('meant')}" for e in undone)
                     + " that the transcription carries: blitz ship --write ships it again with the letter as printed"})
    out, fixed, rows = corrected(text, live)
    for c, r in zip(live, rows):
        if r["done"] == "applied":
            continue
        if r["done"] == "noted":  # the row has the words meant, not the printed ones: an earlier step swapped them, if a record says so
            if not NOTED_NEEDS_EVIDENCE or evidenced(c, evidence):
                continue
            held.append({"code": "mark-unplaced", "why": f"{r['key']}: '{r['printed']}' -> '{r['meant']}': the row reads the words meant "
                         "and nothing records the printed words being there (no text-review change or edit swapped them)"})
            rows[rows.index(r)] = {**r, "done": "holds", "note": ""}  # its own state: the mark that holds the edition, no note
            continue
        bad = mark_problem(c) or not _TYPO_KEY.fullmatch(r["key"]) or r["key"].startswith("cell:")
        say = (f"{r['key']}: '{r['printed']}' -> '{r['meant']}': "
               + ("the mark is malformed or names no clue or header (" + (mark_problem(c) or "not a clue's or a header's key") + ")" if bad
                  else "neither the printed words (exactly once) nor the words meant are in the row"))
        held.append({"code": "mark-invalid" if bad else "mark-unplaced", "why": say})
    lines = [_one_block_line(p.get("text", "")) for p in printed or [] if p.get("label") in labels and str(p.get("text", "")).strip()]
    heads = [t for t in lines if {ln.strip() for ln in t.split("\n")} & {NOTES_HEAD, FIXED_HEAD}]
    if heads:  # a printed line that reads as one of the edition's block heads would split its notes wrongly
        held.append({"code": "notes-head", "why": f"a printed line the Notes rule takes reads as a block head of the edition: {heads[0][:80]!r}"})
    if not held:
        out = with_notes(with_notes(out, lines, NOTES_HEAD), fixed, FIXED_HEAD)
    return {"text": None if held else out, "held": held, "corrections": rows, "declined": declined, "notes": lines}


def sha256(data: str | bytes) -> str:
    """sha256 of text with LF line ends, so a fingerprint doesn't depend on a checkout's core.autocrlf."""
    b = data.encode("utf-8") if isinstance(data, str) else data
    return hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()


def code_version() -> str:
    """A fingerprint of the code that makes an edition's text, in place of a version bumped by hand: a change to any of
    it makes every edition again (run once, re-run only when invalidated)."""
    import inspect

    from . import ship
    parts = [inspect.getsource(f) for f in (make, corrected, evidenced, _norm, _one_block_line, ship.with_notes, ship._swap, ship._word,
                                            ship._count, ship.apply_edits, ship.apply_linked)]
    return sha256("\n".join(parts + [NOTES_HEAD, FIXED_HEAD, repr(NOTED_NEEDS_EVIDENCE)]))[:16]


def kinds(transcription: str, ed: dict) -> list[str]:
    """How an edition differs from its transcription, for reports: misprint (a clue or header corrected), notes
    (the Notes rule's block); [] when they are the same."""
    if not ed.get("text") or ed["text"] == transcription:
        return []
    return [k for k, on in (("misprint", any(r["done"] in ("applied", "noted") for r in ed["corrections"])), ("notes", bool(ed["notes"]))) if on]


# ---- the mark that publishes the edition ---------------------------------------------------------------------------------------------

def publications(records: list[dict], rule) -> dict[str, dict]:
    """{batch: {at, by}} for every batch whose edition the owner has published and not taken back: each batch's
    latest publish-edition:<batch> record by the owner, whose answer is publish. A record from the review site counts
    only when its `account` (the site's user_id) is one of the ship rule's `owner_ids`: the name typed on the proof
    page is never enough, since anyone can type it. A record from the owner's own tools (not via the review site or an
    agent) counts. Anyone else's does nothing."""
    from .ship import AGENT, SITE, _name
    latest = {}
    for r in records:
        rid = str(r.get("id", ""))
        via = r.get("via")
        mine = bool(r.get("account")) and r.get("account") in rule.owner_ids if via == SITE else via != AGENT
        if rid.startswith(PUBLISH) and mine and _name(r) not in rule.ignore:
            if r.get("at", "") >= latest.get(rid[len(PUBLISH):], {}).get("at", ""):
                latest[rid[len(PUBLISH):]] = r
    return {b: {"at": r.get("at", ""), "by": r.get("by", "")} for b, r in sorted(latest.items()) if r.get("answer") == "publish"}


def owner_declines(records: list[dict], pid: str, rule) -> set:
    """ship.owner_declines over a given list of ledger records (the ledger and the review site's records not in it
    yet): (key, printed, meant) from each of the owner's accounts' latest proof record on the puzzle."""
    from .ship import _name, kind_of
    latest = {}
    for r in records:
        if r.get("id") == f"proof:{pid}" and kind_of(r, rule) == "owner" and _name(r) not in rule.ignore:
            latest[r.get("by", "")] = r
    return {(str(d.get("key", "")), str(d.get("printed", "")).strip(), str(d.get("meant", "")).strip())
            for r in latest.values() for d in ((r.get("proof") or {}).get("review") or {}).get("declines") or [] if isinstance(d, dict)}


# ---- a publication's editions and its manifest ----------------------------------------------------------------------

def _tsv(path: Path) -> list[dict]:
    from .ship import _tsv as read
    return read(path)


def _row_tsv(r: dict) -> str:
    from .ship import CONTROL
    return "\t".join(CONTROL.sub(" ", str(r.get(c, "") or "")) for c in COLS)


def read_manifest(repo: Path) -> dict[str, dict]:
    return {r["xdid"]: r for r in _tsv(Path(repo) / MANIFEST)}


def write_manifest(repo: Path, rows: dict[str, dict]) -> Path:
    """shipped.tsv: a header and one row per xdid in xdid order. A row the earlier manifest had and `rows` lacks is
    kept, as withdrawn: a row is never dropped."""
    f = Path(repo) / MANIFEST
    old = read_manifest(repo)
    for x, r in old.items():
        if x not in rows:
            rows[x] = {**r, "status": "withdrawn", "why": r["why"] if r.get("status") == "withdrawn" else "not advertised any more: not in xd/"}
    feed_columns(repo, rows, old)
    f.write_text("\t".join(COLS) + "\n" + "".join(_row_tsv(rows[x]) + "\n" for x in sorted(rows)), encoding="utf-8", newline="\n")
    return f


def feed_columns(repo: Path, rows: dict[str, dict], old: dict[str, dict], today: str = "") -> None:
    """Fill each row's updated_at, form and page_url (COLS, the feed's columns). updated_at moves only when the row's file
    changes (its edition_sha256, or its transcription_sha256 while it has no edition): a row the earlier manifest had with
    the same hash keeps its date (one written before the column existed takes its shipped_at), any other gets today."""
    today = today or date.today().isoformat()
    for x, r in rows.items():
        was = old.get(x) or {}
        sha = r.get("edition_sha256") or r.get("transcription_sha256") or ""
        same = sha and sha == (was.get("edition_sha256") or was.get("transcription_sha256") or "")
        r["updated_at"] = (was.get("updated_at") or r.get("shipped_at") or today) if same else today
        t = Path(repo) / (r.get("transcription") or f"xd/{x}.xd")
        from .ship import sectioned
        r["form"] = ("v2" if sectioned(t.read_text(encoding="utf-8")) else "v1") if t.exists() else (was.get("form") or "")
        r["page_url"] = r.get("record_url") or r.get("proof_url") or ""


def _record_pages(repo: Path) -> dict[str, str]:
    """{xdid: url} of the record pages the publication has published (pipeline/record-pages.tsv: xdid, url). A URL is
    never made up from the pattern: a page that isn't published would answer 404."""
    return {r["xdid"]: r["url"] for r in _tsv(Path(repo) / "pipeline" / "record-pages.tsv") if r.get("xdid") and r.get("url")}


def _as_shipped(repo: Path, row: dict) -> dict | None:
    f = Path(repo) / "pipeline" / "ship" / str(row.get("batch", "")) / "as-shipped" / f"{row.get('pid', '')}.json"
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    except ValueError:
        return None


def inputs(repo: Path, row: dict, text: str, plan: dict | None = None) -> dict:
    """What a shipped puzzle's edition is made from, besides the transcription and the owner's declines: its marks,
    printed lines and edit records, from the freshest record of them that describes this very transcription: the
    ship plan being made (`blitz ship`), else the as-shipped file the last record left (pipeline/ship/<batch>/
    as-shipped/<pid>.json), else its provenance row (written when it shipped)."""
    from .ship import _printed, fingerprint
    fp = fingerprint(text)
    x = ((plan or {}).get("passing") or {}).get(row.get("pid", ""))
    from .ship import packet_edits
    if x and fingerprint(x["text"]) == fp:
        pk = plan["packs"][row["pid"]]
        return {"from": "the ship plan", "marks": x.get("corrections", []), "records": x.get("edit_records", []),
                "packet": packet_edits(pk["ocr"], pk["review"]),
                "printed": _printed(pk["ocr"], pk["review"], {k: v for k, v in (x.get("edit_values") or {}).items() if k in x["edits"]})}
    doc = _as_shipped(repo, row)
    if doc and doc.get("xd_fp") == fp:
        return {"from": "the as-shipped file", "marks": doc.get("corrections", []), "records": (doc.get("edits") or {}).get("records", []),
                "packet": (doc.get("edits") or {}).get("packet", []), "printed": doc.get("printed", [])}
    if row.get("xd") == fp:
        return {"from": "provenance.jsonl", "marks": row.get("corrections", []), "records": (row.get("edits") or {}).get("records", []),
                "packet": (row.get("edits") or {}).get("packet", []), "printed": row.get("printed", [])}
    return {"from": "", "marks": [], "records": [], "packet": [], "printed": []}  # nothing recorded describes this transcription


def _key(ins: dict) -> str:
    return sha256(json.dumps(ins, sort_keys=True, ensure_ascii=False))


def run(repo: Path, pub: str, plan: dict | None = None, today: str = "") -> dict:
    """Every shipped puzzle's edition, the record of what each was made from, and the manifest, from the repo alone:
    xd/, provenance, the ledger (the publish mark, the owner's declines) and the as-shipped files. `plan`: the ship plan
    being made, whose marks are the freshest (blitz ship takes the review site's records into the ledger before it
    calls this, so nothing here rests on data the repo doesn't hold). Returns a summary: {made, remade, unchanged, held,
    differ, kinds, holds, removed, sources, published_by_batch, rows}."""
    from .ship import PROOF_PAGE, _header, fingerprint, ledger, provenance, rule_of
    repo, today = Path(repo), today or date.today().isoformat()
    if not (repo / "provenance.jsonl").exists():
        raise ValueError(f"{repo} has no provenance.jsonl: nothing here was shipped by blitz ship. A publication that came by "
                         "the older path (Judge) gets its manifest from its own list of what it published: blitz edition <pub> --older-path")
    rule, records = rule_of(repo), ledger(repo)
    labels, labels_from = notes_labels(repo, pub, records)
    published = publications(records, rule)
    rec_file = repo.joinpath(*RECORD)
    old = json.loads(rec_file.read_text(encoding="utf-8")).get("puzzles", {}) if rec_file.exists() else {}
    prov = {r["xdid"]: r for r in provenance(repo)}
    pages = _record_pages(repo)
    files = {f.stem: f for f in sorted((repo / "xd").glob("*.xd"))}
    out_dir = repo / EDITION
    summary = {"made": 0, "remade": 0, "unchanged": 0, "held": 0, "differ": 0, "kinds": {}, "holds": {}, "puzzles": len(files),
               "notes_from": labels_from, "published": published, "removed": [], "sources": [], "published_by_batch": {}}
    made, rows, before = {}, {}, read_manifest(repo)
    version = code_version()
    for xdid in sorted(set(files) | set(prov)):
        row, f = prov.get(xdid), files.get(xdid)
        mrow = {"xdid": xdid, "batch": (row or {}).get("batch", ""), "shipped_at": ((row or {}).get("shipped") or {}).get("at", ""),
                "proof_url": PROOF_PAGE + row["pid"] if row and row.get("pid") else "", "record_url": pages.get(xdid, "")}
        if not f:  # withdrawn: the row keeps its last values; its edition file goes
            last = before.get(xdid) or {}
            rows[xdid] = {**mrow, **{k: v for k, v in last.items() if v}, "status": "withdrawn",
                          "why": last["why"] if last.get("status") == "withdrawn" else "not in xd/: shipped, then taken out"}
            if (out_dir / f"{xdid}.xd").exists():
                (out_dir / f"{xdid}.xd").unlink()
                summary["removed"].append(xdid)
            continue
        text = f.read_text(encoding="utf-8")
        mrow.update(date=_header(text, "Date"), number=_header(text, "Number"), transcription=f"xd/{xdid}.xd",
                    transcription_sha256=sha256(f.read_bytes()))  # LF line ends
        if not row:
            rows[xdid] = {**mrow, "status": "held", "why": "no-provenance: in xd/ with no provenance row (not shipped by blitz ship)"}
            continue
        src = inputs(repo, row, text, plan)
        ev = [e for e in list(src["packet"] or []) + list(src["records"] or []) if str(e.get("before", "")) != str(e.get("after", ""))]
        ins = {"version": version, "transcription_sha256": mrow["transcription_sha256"],
               "marks": sorted(list(_mark(c)) for c in src["marks"] or []),  # who marked it isn't hashed: copies name people differently
               "evidence": sorted([_norm(e.get("key", "")), str(e.get("before", "")), str(e.get("after", ""))] for e in ev),
               "unrecorded": not src["from"],
               "declines": sorted(list(d) for d in owner_declines(records, row.get("pid", ""), rule)),
               "notes_rule": list(labels), "printed": [[p.get("label", ""), p.get("text", "")] for p in src["printed"] or []],
               "key_corrections": sorted([e.get("key", ""), str(e["misprint"].get("printed", "")).strip(), str(e["misprint"].get("meant", "")).strip()]
                                         for e in src["records"] or [] if e.get("class") == "key correction" and e.get("misprint"))}
        key, prior = _key(ins), old.get(xdid) or {}
        target = out_dir / f"{xdid}.xd"
        same = (prior.get("inputs_sha256") == key and
                (target.exists() and sha256(target.read_bytes()) == prior.get("edition_sha256") if prior.get("status") == "made"
                 else not target.exists()))
        if same:
            ed_entry = prior
            summary["unchanged"] += 1
        else:
            ed = make(text, src["marks"], {tuple(d) for d in ins["declines"]}, labels, src["printed"], src["records"], ev)
            if not src["from"]:
                ed = {**ed, "text": None, "held": [{"code": "marks-stale", "why": "no record of its marks describes this transcription "
                                                    "(the ship plan, its as-shipped file and its provenance row all have another fingerprint)"}]}
            if prior and prior.get("marks_from") != src["from"]:
                summary["sources"].append({"xdid": xdid, "was": prior.get("marks_from", ""), "now": src["from"] or "nothing"})
            ed_entry = {"status": "held" if ed["held"] else "made", "inputs_sha256": key, "inputs": ins, "marks_from": src["from"],
                        "notes_from": labels_from, "made_at": today, "held": ed["held"], "corrections": ed["corrections"],
                        "declined": ed["declined"], "notes": ed["notes"], "kinds": kinds(text, ed),
                        "edition_sha256": sha256(ed["text"]) if ed["text"] is not None else ""}
            if ed["text"] is None:
                if target.exists():
                    target.unlink()
            else:
                out_dir.mkdir(exist_ok=True)
                target.write_text(ed["text"], encoding="utf-8", newline="\n")
            summary["remade" if prior else "made"] += 1
        made[xdid] = ed_entry
        for k in ed_entry.get("kinds") or []:
            summary["kinds"][k] = summary["kinds"].get(k, 0) + 1
        summary["differ"] += bool(ed_entry.get("kinds"))
        pub_mark = published.get(row.get("batch", ""))
        if ed_entry["status"] == "held":
            summary["held"] += 1
            for h in ed_entry["held"]:
                summary["holds"][h["code"]] = summary["holds"].get(h["code"], 0) + 1
            status, why = "held", "; ".join(f"{h['code']}: {h['why']}" for h in ed_entry["held"])
        elif not pub_mark:
            status, why = "held", f"not-published: the edition of the batch {row.get('batch', '')} has not been published"
        else:
            status, why = "published", "; ".join(f"{c}: {CODES[c]}" for c in row.get("codes") or [] if c in CODES)
            summary["published_by_batch"][row.get("batch", "")] = summary["published_by_batch"].get(row.get("batch", ""), 0) + 1
        rows[xdid] = {**mrow, "status": status, "why": why, "published": (pub_mark or {}).get("at", "")[:10] if status == "published" else "",
                      **({"edition": f"{EDITION}/{xdid}.xd", "edition_sha256": ed_entry["edition_sha256"]} if ed_entry["status"] == "made" else {})}
    rec_file.parent.mkdir(parents=True, exist_ok=True)
    rec_file.write_text(json.dumps({"_about": "blitz edition: what each puzzle's edition (edition/<xdid>.xd) was made from, so it is made "
                                              "again only when that changes. Format: blitz design/ship.md, \"The edition\".",
                                    "version": version, "puzzles": dict(sorted(made.items()))}, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
                        encoding="utf-8", newline="\n")
    write_manifest(repo, rows)
    summary["rows"] = {s: sum(r["status"] == s for r in read_manifest(repo).values()) for s in STATUSES}
    return summary


def older_path(repo: Path) -> dict:
    """The one-off manifest of a publication shipped by the older path, before the edition step (Judge). Its xd/ files
    are transcriptions (they carry Source:, Provenance: and the OCR's flags), not editions: each row lists its
    transcription and no edition, held, with a `why` saying its edition went out by the older path and not through this
    manifest. The list the older path kept (gxd-exports.tsv) gives record_url and proof_url, and a row it lists that
    xd/ lacks is withdrawn. No edition/ is written."""
    from .ship import _header
    repo = Path(repo)
    if (repo / "provenance.jsonl").exists():
        raise ValueError(f"{repo} has provenance.jsonl: its manifest comes from blitz ship (blitz edition <pub>), not the older path")
    exp = {r["xdid"]: r for r in _tsv(repo / "gxd-exports.tsv")}
    if not exp:
        raise ValueError(f"{repo} has no gxd-exports.tsv rows: nothing says which puzzles the older path published")
    rows = {}
    for f in sorted((repo / "xd").glob("*.xd")):
        text, e = f.read_text(encoding="utf-8"), exp.get(f.stem) or {}
        rows[f.stem] = {"xdid": f.stem, "date": _header(text, "Date"), "number": _header(text, "Number"), "status": "held",
                        "why": "older-path: shipped before the edition step; its edition went out by the older path, not through "
                               "this manifest, which lists the transcription only",
                        "transcription": f"xd/{f.stem}.xd", "transcription_sha256": sha256(f.read_bytes()),
                        "record_url": e.get("record_url", ""), "proof_url": e.get("proof_url", "")}
    for x, e in exp.items():
        if x not in rows:
            rows[x] = {"xdid": x, "date": e.get("date", ""), "number": e.get("number", ""), "status": "withdrawn",
                       "why": "in the older path's list, not in xd/", "record_url": e.get("record_url", ""), "proof_url": e.get("proof_url", "")}
    write_manifest(repo, rows)
    return {s: sum(r["status"] == s for r in read_manifest(repo).values()) for s in STATUSES}


# ---- what the ship plan shows: each passing puzzle's edition, and whether the batch's edition is published ----------------------------

def preview(repo: Path, pub: str, p: dict, records: list[dict], rule) -> dict[str, dict]:
    """{pid: the edition of the xd as it will ship} for every puzzle the plan passes, made by make() from what the
    plan recorded, for the ship record and the as-shipped files: {status (made | held), path, xd (None when held),
    xd_fp, sha256, held, corrections, declined, notes, kinds, notes_from}. The step itself (run) writes the file."""
    from .ship import _printed, fingerprint, packet_edits
    labels, labels_from = notes_labels(repo, pub, records)
    out = {}
    for pid, x in sorted((p.get("passing") or {}).items()):
        pk = p["packs"][pid]
        printed = _printed(pk["ocr"], pk["review"], {k: v for k, v in (x.get("edit_values") or {}).items() if k in x["edits"]})
        ev = [e for e in packet_edits(pk["ocr"], pk["review"]) + list(x.get("edit_records", [])) if str(e.get("before", "")) != str(e.get("after", ""))]
        ed = make(x["text"], x.get("corrections", []), owner_declines(records, pid, rule), labels, printed, x.get("edit_records", []), ev)
        out[pid] = {"status": "held" if ed["held"] else "made", "path": f"{EDITION}/{x['xdid']}.xd", "xd": ed["text"],
                    "xd_fp": fingerprint(ed["text"]) if ed["text"] is not None else "", "sha256": sha256(ed["text"]) if ed["text"] is not None else "",
                    "held": ed["held"], "corrections": ed["corrections"], "declined": ed["declined"], "notes": ed["notes"],
                    "kinds": kinds(x["text"], ed), "notes_from": labels_from}
    return out


def published_of(records: list[dict], rule, batch: str) -> dict:
    """Whether the batch's edition is published, for the ship record: {published: bool, at, by} (by: the owner's record's by)."""
    r = publications(records, rule).get(batch)
    return {"published": True, **r} if r else {"published": False, "at": "", "by": ""}
