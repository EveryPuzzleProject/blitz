"""The edition step and the manifest (blitz design/ship.md, "The edition"; design/publishing-editions.md slice 1): the edition is
derived from the transcription in xd/ by rule (misprint corrections that count and weren't declined, each with a note;
the Notes rule's printed lines), held with a code when a mark can't be placed, made again only when its inputs change,
and listed in shipped.tsv with a status; the owner's "Publish the edition" decides which rows are published.

Run with: uv run --with pytest pytest tests/test_edition.py"""

import json

import pytest

from blitz import edition
from blitz.edition import FIXED_HEAD, NOTES_HEAD, make, older_path, read_manifest, run
from blitz.ship import AGENT, SITE, Rule, as_shipped, export, from_site, plan, record, write
from test_ship import CHECK, XD
from test_ship_edits import AI_BY, BOTH, P, said, shipped, xd_of
from test_ship_linked import LEDGER, NO11, PERSON, RULE, SMALL, batch

X = "games1978-03-01"
TOW = XD.replace("A3. Two ~", "A3. Tow ~")
TYPO = [{"key": "clue:A3", "printed": "Tow", "meant": "Two"}]
OWNER = "oops6498"


def ship_one(tmp_path, typos=TYPO, xd=TOW, owner=True):
    repo, proofs, p = shipped(tmp_path, said(AI_BY, AGENT, {}, typos=typos), CHECK, xd=xd)
    if owner:
        (repo / "fixes").mkdir(exist_ok=True)
        (repo / "fixes" / "ship-rule.json").write_text(json.dumps({"ai_ready": "both", "owner": [OWNER]}), encoding="utf-8")
    write(repo, p, "2026-11-16")
    return repo, proofs


def ledger_add(repo, *recs):
    with (repo / "fixes" / "decisions.jsonl").open("a", encoding="utf-8") as fh:
        fh.writelines(json.dumps(r) + "\n" for r in recs)


def publish(answer="publish", by=f"{OWNER} ({SITE})", at="2026-11-16T10:00:00Z", batch="b"):
    return {"id": f"publish-edition:{batch}", "answer": answer, "by": by, "at": at, "via": SITE if SITE in by else "watch", "note": ""}


def decline(key="clue:A3", printed="Tow", meant="Two", at="2026-11-16T11:00:00Z"):
    return {"id": f"proof:{P}", "answer": "ready", "by": f"{OWNER} ({SITE})", "at": at, "via": SITE, "note": "",
            "proof": {"review": {"xd": "", "edits": {}, "declines": [{"key": key, "printed": printed, "meant": meant}]}}}


# ---- one puzzle's edition ----

def test_a_correction_is_applied_with_a_note_and_the_notes_rule_takes_its_lines():
    printed = [{"label": "instructions", "text": "Fill in the grid."}, {"label": "credit", "text": "Puzzle by A."}]
    ed = make(TOW, TYPO, set(), ("intro", "instructions"), printed)
    assert ed["held"] == [] and "A3. Two ~ CDE" in ed["text"] and "A3. Tow" not in ed["text"]
    assert ed["text"].endswith(f"A1: missing\n\n{NOTES_HEAD}\nFill in the grid.\n\n{FIXED_HEAD}\nA3 is printed 'Tow'; corrected to 'Two'.\n")
    assert "Puzzle by A." not in ed["text"] and ed["notes"] == ["Fill in the grid."]
    assert make(TOW, TYPO, set(), ("intro", "instructions"), printed) == ed                 # deterministic
    assert edition.kinds(TOW, ed) == ["misprint", "notes"]
    plain = make(XD)
    assert plain["text"] == XD and edition.kinds(XD, plain) == []                          # nothing to do: the same text


def test_a_declined_mark_is_not_applied_and_is_listed_as_declined():
    ed = make(TOW, [{**TYPO[0], "by": AI_BY}], {("clue:A3", "Tow", "Two")})
    assert ed["text"] == TOW and ed["corrections"] == [] and ed["declined"] == [{"key": "clue:A3", "printed": "Tow", "meant": "Two", "by": AI_BY}]


def test_a_mark_it_cant_place_holds_the_edition_and_it_never_guesses():
    ed = make(XD.replace("A3. Two ~", "A3. Tow Tow ~"), TYPO)                                # the printed word twice
    assert ed["text"] is None and [h["code"] for h in ed["held"]] == ["mark-unplaced"]
    ed = make(XD, [{"key": "clue:A3", "printed": "Tow", "meant": "Trois"}])                  # neither word is there
    assert ed["text"] is None and ed["held"][0]["code"] == "mark-unplaced"
    ed = make(TOW, [{"key": "clue:A3", "printed": "", "meant": "Two"}])                      # malformed
    assert ed["text"] is None and ed["held"][0]["code"] == "mark-invalid"
    ed = make(TOW, [{"key": "cell:r1c1", "printed": "A", "meant": "B"}])                     # a key letter is ship's, not the edition's
    assert ed["held"][0]["code"] == "mark-invalid"
    # the text review had already put the word right (ship's fits "already"): the note alone, not a hold
    ed = make(XD, [{"key": "clue:A3", "printed": "Tow", "meant": "Two"}])
    assert ed["held"] == [] and ed["corrections"][0]["done"] == "noted" and "A3 is printed 'Tow'; corrected to 'Two'." in ed["text"]


def test_a_key_correction_the_owner_declined_since_holds_the_edition():
    rec = {"key": "cell:r2c2", "class": "key correction", "misprint": {"printed": "D", "meant": "X"}}
    ed = make(XD, [], {("cell:r2c2", "D", "X")}, records=[rec])
    assert ed["text"] is None and ed["held"][0]["code"] == "key-declined" and "r2c2 D->X" in ed["held"][0]["why"]


def test_a_linked_ends_edition_corrects_the_clue_and_names_the_pair():
    ed = make(SMALL, [{"key": "clue:A2", "printed": "insect", "meant": "inspect"}], set(), ("instructions",),
              [{"label": "instructions", "text": "Solve it."}])
    assert ed["held"] == [] and "1-2. An inspect ~ BEE\n" in ed["text"]
    assert ed["text"].endswith(f"{NOTES_HEAD}\nSolve it.\n\n{FIXED_HEAD}\nThe clue for 1-2 is printed 'insect'; corrected to 'inspect'.\n")
    assert ed["text"].split("\n\n\n")[:3] != SMALL.split("\n\n\n")[:3] and "Numbering:" in ed["text"]  # its sections kept


# ---- a publication's editions and its manifest ----

def test_ship_writes_the_edition_its_record_and_the_manifest_and_leaves_xd_alone(tmp_path):
    repo, _ = ship_one(tmp_path)
    text = xd_of(repo)
    assert "A3. Tow ~ CDE" in text                                                         # the transcription, as printed
    ed = (repo / "edition" / f"{X}.xd").read_text(encoding="utf-8")
    assert "A3. Two ~ CDE" in ed and ed.endswith("A3 is printed 'Tow'; corrected to 'Two'.\n")
    rec = json.loads((repo / "pipeline" / "edition.json").read_text(encoding="utf-8"))["puzzles"][X]
    assert rec["status"] == "made" and rec["inputs"]["transcription_sha256"] == edition.sha256(text.encode())
    assert rec["inputs"]["marks"] == [["clue:A3", "Tow", "Two", AI_BY]] and rec["marks_from"] == "the ship plan"
    (row,) = read_manifest(repo).values()
    assert list(row) == list(edition.COLS)
    assert (row["status"], row["why"], row["published"], row["record_url"]) == ("held", "not-published: the edition of the batch b has not been published", "", "")
    assert (row["transcription"], row["edition"], row["batch"], row["shipped_at"]) == (f"xd/{X}.xd", f"edition/{X}.xd", "b", "2026-11-16")
    assert row["edition_sha256"] == edition.sha256(ed.encode()) and len(row["transcription_sha256"]) == 64
    assert row["proof_url"].endswith(f"?p={P}")


def test_a_second_run_changes_nothing(tmp_path):
    repo, _ = ship_one(tmp_path)
    files = {f: f.read_bytes() for f in [repo / "shipped.tsv", repo / "edition" / f"{X}.xd", repo / "pipeline" / "edition.json", repo / "xd" / f"{X}.xd"]}
    r = run(repo, "games", today="2026-11-17")
    assert (r["made"], r["remade"], r["unchanged"]) == (0, 0, 1)
    assert all(f.read_bytes() == b for f, b in files.items())                              # byte-identical, made_at kept


def test_a_decline_remakes_exactly_that_edition_and_its_row_and_taking_it_back_restores_them(tmp_path):
    repo, _ = ship_one(tmp_path)
    before = (repo / "edition" / f"{X}.xd").read_bytes(), (repo / "shipped.tsv").read_bytes()
    ledger_add(repo, decline())
    r = run(repo, "games")
    assert (r["remade"], r["unchanged"]) == (1, 0)
    assert (repo / "edition" / f"{X}.xd").read_text(encoding="utf-8") == xd_of(repo)    # no correction, no notes: the transcription's text
    assert read_manifest(repo)[X]["edition_sha256"] != edition.sha256(before[0])
    ledger_add(repo, {**decline(), "at": "2026-11-16T12:00:00Z", "proof": {"review": {"xd": "", "edits": {}}}})  # the decline taken back
    assert run(repo, "games")["remade"] == 1
    assert ((repo / "edition" / f"{X}.xd").read_bytes(), (repo / "shipped.tsv").read_bytes()) == before


def test_only_the_owners_publish_mark_publishes_rows_and_taking_it_back_holds_them_again(tmp_path):
    repo, _ = ship_one(tmp_path)
    ledger_add(repo, publish(by=f"pat ({SITE})"))                                          # a helper's: nothing
    assert run(repo, "games")["published"] == {} and read_manifest(repo)[X]["status"] == "held"
    ledger_add(repo, publish())
    run(repo, "games")
    row = read_manifest(repo)[X]
    assert (row["status"], row["why"], row["published"]) == ("published", "", "2026-11-16")
    ledger_add(repo, publish("unpublish", at="2026-11-16T12:00:00Z"))
    run(repo, "games")
    assert read_manifest(repo)[X]["status"] == "held" and read_manifest(repo)[X]["published"] == ""


def test_a_held_edition_has_no_file_and_its_row_says_why(tmp_path):
    repo, _ = ship_one(tmp_path)
    ledger_add(repo, publish())
    run(repo, "games")
    assert (repo / "edition" / f"{X}.xd").exists()
    # the transcription changes under it (a re-ship) so the mark no longer finds its printed word once
    (repo / "xd" / f"{X}.xd").write_text(xd_of(repo).replace("A3. Tow ~", "A3. Tow or Tow ~"), encoding="utf-8")
    r = run(repo, "games")
    assert r["holds"] == {"mark-unplaced": 1} and not (repo / "edition" / f"{X}.xd").exists()
    row = read_manifest(repo)[X]
    assert row["status"] == "held" and row["why"].startswith("mark-unplaced: clue:A3") and row["edition"] == ""


def test_rows_are_never_dropped_a_puzzle_gone_from_xd_is_withdrawn(tmp_path):
    repo, _ = ship_one(tmp_path)
    (repo / "xd" / f"{X}.xd").unlink()
    run(repo, "games")
    row = read_manifest(repo)[X]
    assert row["status"] == "withdrawn" and row["why"].startswith("not in xd/")
    (repo / "provenance.jsonl").write_text("", encoding="utf-8")                           # even with no provenance row left
    run(repo, "games")
    assert read_manifest(repo)[X]["status"] == "withdrawn"


def test_a_record_page_url_is_written_only_when_the_page_is_recorded_as_published(tmp_path):
    repo, _ = ship_one(tmp_path)
    assert read_manifest(repo)[X]["record_url"] == ""                                      # never made up from the pattern
    (repo / "pipeline" / "record-pages.tsv").write_text(f"xdid\turl\n{X}\thttps://everypuzzleproject.org/games/1978-03-01/\n", encoding="utf-8")
    run(repo, "games")
    assert read_manifest(repo)[X]["record_url"] == "https://everypuzzleproject.org/games/1978-03-01/"


def test_refusals(tmp_path):
    with pytest.raises(ValueError, match="no provenance.jsonl"):
        run(tmp_path, "judge")
    with pytest.raises(ValueError, match="no gxd-exports.tsv rows"):
        older_path(tmp_path)
    repo, _ = ship_one(tmp_path / "s")
    with pytest.raises(ValueError, match="has provenance.jsonl"):
        older_path(repo)


def test_judges_one_off_manifest_lists_its_xd_as_editions_published_by_the_older_path(tmp_path):
    (tmp_path / "xd").mkdir()
    for x in ("judge1924-11-01", "judge1924-11-08"):
        (tmp_path / "xd" / f"{x}.xd").write_text(XD.replace("Title: T\n", f"Title: T\nDate: {x[5:]}\nNumber: 1\n"), encoding="utf-8")
    cols = "gxd_id\txdid\tdate\tnumber\tgxd_mr\texported\tproof_url\trecord_url\n"
    (tmp_path / "gxd-exports.tsv").write_text(cols + "judge-001\tjudge1924-11-01\t1924-11-01\t1\trabidrat/gxd!198\t2026-10-12\tP\tR\n"
                                              "judge-002\tjudge1924-11-08\t1924-11-08\t2\t\t\tP2\t\n", encoding="utf-8")
    assert older_path(tmp_path) == {"published": 1, "held": 1, "withdrawn": 0}
    a, b = read_manifest(tmp_path).values()
    assert (a["status"], a["published"], a["edition"], a["transcription"], a["record_url"], a["proof_url"]) == ("published", "2026-10-12", "xd/judge1924-11-01.xd", "", "R", "P")
    assert a["why"].startswith("older-path: published on 2026-10-12") and b["why"].startswith("not-published")
    assert not any("gxd" in v for r in (a, b) for v in r.values())                         # the manifest knows no downstream reader
    assert not (tmp_path / "edition").exists()


# ---- the ship record, the as-shipped file, the site ----

def test_the_record_and_the_as_shipped_file_carry_the_edition_and_whether_it_is_published(tmp_path):
    repo, proofs = ship_one(tmp_path)
    ledger_add(repo, publish())
    p = plan(repo, proofs, Rule(ai_ready="both", owner=(OWNER,)), "b")
    rec = record(p)
    assert rec["edition_published"] == {"published": True, "at": "2026-11-16T10:00:00Z", "by": "the owner"} and rec["editions_published"] == 1
    assert record(p, public=False)["edition_published"]["by"] == f"{OWNER} ({SITE})"
    assert rec["puzzles"][0]["edition"] == {"status": "made", "xd_fp": p["editions"][P]["xd_fp"], "held": [], "corrections": 1}
    doc = as_shipped(p, rec)[P]
    assert "A3. Tow ~" in doc["xd"] and "A3. Two ~" in doc["edition"]["xd"] and doc["edition"]["path"] == f"edition/{X}.xd"
    assert doc["edition"]["corrections"][0]["note"] == "A3 is printed 'Tow'; corrected to 'Two'."


def test_the_publish_mark_comes_in_from_the_site_as_a_ledger_record():
    site = {"puzzles": {}, "edition_publish": {"b": {OWNER: {"published": True, "note": "", "at": "t1"}, "pat": {"published": False, "note": "", "at": "t2"}}}}
    rows = from_site(site, [], set())
    assert [(r["id"], r["answer"], r["by"], r["via"]) for r in rows] == [("publish-edition:b", "publish", f"{OWNER} ({SITE})", SITE),
                                                                         ("publish-edition:b", "unpublish", f"pat ({SITE})", SITE)]
    assert from_site(site, rows, set()) == []                                               # already in the ledger: not made again


def test_ship_export_is_unchanged_by_the_edition_step(tmp_path):
    repo, _ = ship_one(tmp_path)
    export(repo, tmp_path / "a", "games")
    out = (tmp_path / "a" / "games" / "1978" / f"{X}.xd").read_text(encoding="utf-8")
    assert "A3. Two ~ CDE" in out and out.endswith("A3 is printed 'Tow'; corrected to 'Two'.\n")
    ledger_add(repo, publish())
    run(repo, "games")
    export(repo, tmp_path / "b", "games")
    for f in ("games/1978/games1978-03-01.xd", "receipts.tsv", "corrections.tsv", "held-back.tsv"):
        assert (tmp_path / "a" / f).read_bytes() == (tmp_path / "b" / f).read_bytes()
    assert not (tmp_path / "a" / "edition").exists()


def test_a_linked_ends_puzzle_gets_its_edition_through_ship(tmp_path):
    repo, proofs = batch(tmp_path, {NO11: [LEDGER[NO11], said(PERSON, SITE, {})]})
    write(repo, plan(repo, proofs, RULE, "nyw-1914-c1"), "2026-11-12")
    (row,) = read_manifest(repo).values()
    assert row["xdid"] == "nyw1914-03-01" and row["edition"] == "edition/nyw1914-03-01.xd"
    ed = (repo / "edition" / "nyw1914-03-01.xd").read_text(encoding="utf-8")
    assert "Clues: linked ends" in ed and "Numbering:" in ed


def test_the_exports_holds_are_not_the_editions_a_cryptic_with_no_key_is_published(tmp_path):
    """cryptic-no-key held a puzzle back from the gxd export (ship.NOT_EXPORTED): a downstream reader's rule, not the
    publication's. Its edition is made and published like any other."""
    repo, _ = ship_one(tmp_path)
    rows = [json.loads(ln) for ln in (repo / "provenance.jsonl").read_text(encoding="utf-8").splitlines()]
    rows[-1]["codes"] = ["cryptic-no-key"]
    (repo / "provenance.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    ledger_add(repo, publish())
    run(repo, "games")
    assert read_manifest(repo)[X]["status"] == "published"
