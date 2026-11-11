"""blitz ship keeps a record of every edit (design/ship.md, "The record of every edit"), in three cases:
a reading fix is applied and recorded in provenance; a misprint in a clue or a header stays as printed in the
shipped xd and travels as a proposal that the gxd export applies, with its note; a misprinted key letter is
corrected at ship, with a note in the xd and its record. An edit with no whole record holds the puzzle.

Run with: uv run --with pytest pytest tests/test_ship_edits.py"""

import json

from blitz.ship import (AGENT, NOTES_HEAD, SITE, Rule, apply_edits, backfill, corrected, edit_records, export, packet_edits, plan,
                        provenance, record, unrecorded, with_notes, write)
from test_ship import CHECK, OK, XD, _batch, proof

P = "games1978-03-01-L030"
PERSON = f"pat ({SITE})"
AI_BY = "Claude (AI proof reviewer, m)"
BOTH = Rule(ai_ready="both")
KEY_NOTE = ("The printed answer key gave 2 Down as BDF (and so 3 Across as CDE), presumably in error (D at row 2, column 2). "
            "It has been corrected to BXF and CXE (X).")


def said(by, via, edits, comments=(), typos=None, at="2026-10-22T00:00:00Z"):
    r = proof(by, "ready", at, via)
    r["proof"]["review"].update(edits=edits, comments=[{"key": k, "text": t, "why": True} for k, t in comments],
                                **({"typos": typos} if typos is not None else {}))
    return r


def shipped(tmp_path, *recs, xd=XD):
    repo, proofs = _batch(tmp_path, {P: list(recs)}, {P: OK})
    (proofs / P / "puzzle.xd").write_text(xd, encoding="utf-8")
    return repo, proofs, plan(repo, proofs, BOTH, "b")


def row_of(repo):
    return provenance(repo)[0]


def xd_of(repo):
    return (repo / "xd" / "games1978-03-01.xd").read_text(encoding="utf-8")


# ---- case 1: a reading fix is applied, and recorded in provenance only ----

def test_a_clue_edit_ships_with_what_it_replaced_who_made_it_and_its_class(tmp_path):
    repo, _, p = shipped(tmp_path, said(PERSON, SITE, {"clue:A3": "Deux", "clue:A1^Easy": "Un"}, [("clue:A3", "The crop reads Deux.")]))
    write(repo, p, "2026-11-11")
    row = row_of(repo)
    by = {r["key"]: r for r in row["edits"]["records"]}
    a3 = by["clue:A3"]
    assert (a3["what"], a3["before"], a3["after"]) == ("clue", "Two", "Deux")
    assert (a3["by"], a3["kind"], a3["via"], a3["stage"]) == (PERSON, "helper", SITE, "proof review")
    assert a3["why"] == "The crop reads Deux." and a3["evidence"]["proof"].endswith(f"?p={P}&k=clue:A3")
    assert a3["class"] == "reading"                                    # the reviewer's comment on the row is the evidence
    easy = by["clue:A1^Easy"]
    assert (easy["what"], easy["before"], easy["after"], easy["class"]) == ("second clue set", "Uno", "Un", "unclassed")  # nothing says which
    assert NOTES_HEAD not in xd_of(repo) and row["notes"] == [] and row["corrections"] == []


def test_a_key_square_read_wrongly_is_a_reading_fix_with_the_answers_through_it(tmp_path):
    repo, _, p = shipped(tmp_path, said(AI_BY, AGENT, {"cell:r2c2": "x"}, [("grid:r2c2", "The key shows X.")]), CHECK)
    write(repo, p, "2026-11-11")
    (r,) = row_of(repo)["edits"]["records"]
    assert (r["key"], r["what"], r["class"], r["before"], r["after"], r["kind"]) == ("cell:r2c2", "key square", "reading", "D", "X", "ai")
    assert r["words"] == {"A3": ["CDE", "CXE"], "D2": ["BDF", "BXF"]} and r["why"] == "The key shows X."
    assert NOTES_HEAD not in xd_of(repo)                               # a misread is not a misprint: no note


def test_a_header_edit_records_the_header_it_changed_or_added(tmp_path):
    repo, _, p = shipped(tmp_path, said("Reviewer 2", "watch", {"meta:title": "New", "meta:byline": "by A", "meta:author": "A"}))
    write(repo, p, "2026-11-11")
    by = {r["key"]: r for r in row_of(repo)["edits"]["records"]}
    assert (by["meta:title"]["before"], by["meta:title"]["after"], by["meta:title"]["header"], by["meta:title"]["kind"]) == ("T", "New", "Title", "owner")
    assert (by["meta:byline"]["before"], by["meta:byline"]["after"]) == ("", "by A")   # a header the packet's xd didn't have
    assert "meta:author" not in by                                                     # the same value: no edit


# ---- case 2: a misprint in a clue or a header stays as printed; the gxd export corrects it ----

def test_a_clue_misprint_ships_as_printed_and_the_export_corrects_it_with_its_note(tmp_path):
    typos = [{"key": "clue:A3", "printed": "Tow", "meant": "Two"},      # no edit: the reviewer only names it
             {"key": "clue:D1", "printed": "Fuor", "meant": "Four"},    # the text review had already put this word right
             {"key": "meta:title", "printed": "T", "meant": "The"}]
    repo, proofs, p = shipped(tmp_path, said(AI_BY, AGENT, {}, typos=typos), CHECK, xd=XD.replace("A3. Two ~", "A3. Tow ~"))
    assert [(c["key"], c["fits"]) for c in p["passing"][P]["corrections"]] == [("clue:A3", "printed"), ("clue:D1", "already"), ("meta:title", "printed")]
    assert record(p)["puzzles"][0]["corrections"][0] == {"key": "clue:A3", "printed": "Tow", "meant": "Two", "fits": "printed",
                                                         "says": "A3 is printed 'Tow'; meant 'Two'."}   # for the proof page
    write(repo, p, "2026-11-11")
    text, row = xd_of(repo), row_of(repo)
    assert "A3. Tow ~ CDE" in text and text.startswith("Title: T\n") and NOTES_HEAD not in text       # as printed
    assert row["edits"]["records"] == [] and row["notes"] == []
    a3 = row["corrections"][0]
    assert (a3["printed"], a3["meant"], a3["by"], a3["kind"]) == ("Tow", "Two", AI_BY, "ai") and a3["evidence"]["proof"].endswith("&k=clue:A3")
    assert plan(repo, proofs, BOTH, "b")["rows"][0]["status"] == "shipped"                             # written once
    res = export(repo, tmp_path / "out", "games")
    out = (tmp_path / "out" / "games" / "1978" / "games1978-03-01.xd").read_text(encoding="utf-8")
    assert "A3. Two ~ CDE" in out and out.startswith("Title: The\n")
    assert out.endswith("A3 is printed 'Tow'; corrected to 'Two'.\n\nD1 is printed 'Fuor'; corrected to 'Four'.\n\n"
                        "The title is printed 'T'; corrected to 'The'.\n")
    assert res["corrections"] == {"applied": 2, "noted": 1, "not applied": 0}
    rows = (tmp_path / "out" / "corrections.tsv").read_text(encoding="utf-8").splitlines()
    assert rows[1].split("\t")[:6] == ["games1978-03-01", "clue:A3", "Tow", "Two", AI_BY, "applied"] and rows[2].split("\t")[5] == "noted"
    assert xd_of(repo) == text                                                                         # the publication's xd is untouched


def test_a_misprint_corrected_as_an_edit_is_taken_back_out_and_the_rest_of_the_edit_stands(tmp_path):
    typos = [{"key": "clue:A3", "printed": "Tow", "meant": "Two"}]
    # the OCR also misread the word: the reviewer's edit fixes the reading and the misprint at once
    repo, _, p = shipped(tmp_path, said(AI_BY, AGENT, {"clue:A3": "Two of them"}, typos=typos), CHECK, xd=XD.replace("A3. Two ~", "A3. T0w of thern ~"))
    write(repo, p, "2026-11-11")
    row = row_of(repo)
    assert "A3. Tow of them ~ CDE" in xd_of(repo)                       # the reading fixed, the misprint as printed
    (r,) = row["edits"]["records"]
    assert (r["before"], r["after"], r["class"]) == ("T0w of thern", "Tow of them", "unclassed") and "beside" in r
    (c,) = row["corrections"]
    assert (c["fits"], c["edit"]) == ("printed", "Two of them")
    # the edit is the misprint's correction and nothing else: nothing is applied at all
    _, _, p = shipped(tmp_path / "b", said(AI_BY, AGENT, {"clue:A3": "Two"}, typos=typos), CHECK, xd=XD.replace("A3. Two ~", "A3. Tow ~"))
    x = p["passing"][P]
    assert "A3. Tow ~ CDE" in x["text"] and x["edit_records"] == [] and x["corrections"][0]["fits"] == "printed"
    # an edit that doesn't have the word meant: the printed text can't be put back, so it doesn't ship
    _, _, p = shipped(tmp_path / "c", said(AI_BY, AGENT, {"clue:A3": "Deux"}, typos=typos), CHECK)
    assert p["rows"][0]["reason"] == "edit-unrecorded" and "can't be put back" in p["rows"][0]["why"]


def test_the_export_leaves_alone_a_correction_it_cannot_place():
    text, notes, rows = corrected(XD, [{"key": "clue:A3", "printed": "Tow", "meant": "Deux", "by": "x"}, {"key": "clue:A9", "printed": "a", "meant": "b"}])
    assert text == XD and notes == [] and [r["done"] for r in rows] == ["not applied", "not applied"]


# ---- case 3: a misprinted key letter is corrected at ship, and said in the xd ----

def test_a_misprinted_key_letter_is_corrected_noted_in_the_xd_and_recorded(tmp_path):
    typos = [{"key": "cell:r2c2", "printed": "D", "meant": "X"}]
    repo, proofs, p = shipped(tmp_path, said("Reviewer 2", "watch", {"cell:r2c2": "X"}, [("cell:r2c2", "Crossings want X.")], typos))
    assert record(p)["puzzles"][0]["notes"] == [KEY_NOTE]              # the ship record carries it: the proof page draws it
    write(repo, p, "2026-11-11")
    text, row = xd_of(repo), row_of(repo)
    assert "A3. Two ~ CXE" in text and text.endswith("OCR review flags:\nA1: missing\n\n" + NOTES_HEAD + "\n" + KEY_NOTE + "\n")
    (r,) = row["edits"]["records"]
    assert (r["class"], r["before"], r["after"], r["misprint"], r["note"]) == ("key correction", "D", "X", {"printed": "D", "meant": "X"}, KEY_NOTE)
    assert r["by"] == "Reviewer 2" and r["evidence"]["proof"].endswith("&k=cell:r2c2") and row["notes"] == [KEY_NOTE]
    assert plan(repo, proofs, BOTH, "b")["rows"][0]["status"] == "shipped"
    export(repo, tmp_path / "out", "games")
    assert (tmp_path / "out" / "games" / "1978" / "games1978-03-01.xd").read_text(encoding="utf-8").endswith("\n\n" + KEY_NOTE + "\n")


def test_a_key_correction_named_without_an_edit_is_made_from_its_record(tmp_path):
    typos = [{"key": "cell:r2c2", "printed": "D", "meant": "X"}]
    _, _, p = shipped(tmp_path, said(AI_BY, AGENT, {}, typos=typos), CHECK)
    x = p["passing"][P]
    assert "A3. Two ~ CXE" in x["text"] and x["notes"] == [KEY_NOTE] and x["edit_records"][0]["class"] == "key correction"
    # the packet's key already has the letter meant (corrected before review): nothing changes, and it is said all the same
    _, _, p = shipped(tmp_path / "b", said(AI_BY, AGENT, {}, typos=[{"key": "cell:r2c2", "printed": "Q", "meant": "D"}]), CHECK)
    x = p["passing"][P]
    assert "A3. Two ~ CDE" in x["text"] and x["notes"][0].startswith("The printed answer key gave 2 Down as BQF")
    assert (x["edit_records"][0]["stage"], x["edit_records"][0]["class"]) == ("before review", "key correction")


def test_a_key_correction_with_no_whole_record_does_not_ship(tmp_path):
    for i, (edits, typo, word) in enumerate((({"cell:r2c2": "X"}, {"key": "cell:r2c2", "printed": "", "meant": "X"}, "doesn't say what the key printed"),
                                             ({"cell:r2c2": "X"}, {"key": "cell:r2c2", "printed": "D", "meant": "Y"}, "doesn't match the square"),
                                             ({}, {"key": "cell:r2c2", "printed": "Q", "meant": "Y"}, "doesn't match the square"),
                                             ({}, {"key": "cell:r9c9", "printed": "D", "meant": "X"}, "names no square"))):
        _, _, p = shipped(tmp_path / str(i), said(AI_BY, AGENT, edits, typos=[typo]), CHECK)
        row = p["rows"][0]
        assert (row["status"], row["reason"], row["queue"]) == ("held", "edit-unrecorded", "broken") and word in row["why"] and not p["passing"]


# ---- no record, no ship ----

def test_an_edit_with_nothing_to_say_what_it_replaced_holds_the_puzzle(tmp_path):
    repo, _, p = shipped(tmp_path, said(PERSON, SITE, {"clue:A9": "No such clue", "clue:A3": "Deux"}))
    row = p["rows"][0]
    assert (row["status"], row["reason"], row["queue"]) == ("held", "edit-unrecorded", "broken") and not p["passing"]
    assert "clue:A9" in row["why"] and row["broken"][0]["stage"] == "import"
    assert write(repo, p, "2026-11-11")["written"] == [] and not (repo / "xd").exists()


def test_whatever_differs_from_the_packet_has_a_record_or_is_named_missing():
    out, _ = apply_edits(XD, {"clue:A3": "Deux"})
    e = edit_records(XD, out, [said(PERSON, SITE, {"clue:A3": "Deux"})])
    assert not e["missing"] and len(e["records"]) == 1 and e["text"] == out
    e = edit_records(XD, out.replace("A5. Three", "A5. Trois").replace("Title: T", "Title: U"), [said(PERSON, SITE, {"clue:A3": "Deux"})])
    assert sorted(m.split(":")[0] + ":" + m.split(":")[1] for m in e["missing"]) == ["clue:A5", "meta:title"]
    # a decision that isn't a value of the xd, and the list it wrote into the clues (a candidate list taken in as the clues)
    e = edit_records(XD, XD.replace("D4. Six", "D4. Seis"), [said(PERSON, SITE, {"candidate:D-alt1": "clues"})])
    by = {r["key"]: r for r in e["records"]}
    assert not e["missing"] and (by["candidate:D-alt1"]["what"], by["candidate:D-alt1"]["class"]) == ("decision", "decision")
    assert (by["clue:D4"]["before"], by["clue:D4"]["after"], by["clue:D4"]["decided_by"], by["clue:D4"]["class"]) == ("Six", "Seis", "candidate:D-alt1", "decision")


def test_with_notes_starts_the_notes_when_the_xd_has_none():
    bare = XD.split("\n\n\nOCR review flags")[0] + "\n"
    assert with_notes(bare, ["x"]) == bare + "\n\n" + NOTES_HEAD + "\nx\n" and with_notes(XD, []) == XD


def test_the_packets_own_changes_travel_too():
    ocr = {"clues": {"A1": {"text": "0ne"}}, "lines": [{"n": 3, "text": "For solvers"}], "answers": ["AB#", "CRE"], "title": ""}
    review = {"reviewer_line": "AI reviewer · m", "corrections": {"clue:A1": "One", "clue:D9": "Typed", "line:B3": "For solvers, a note",
                                                                  "cell:r2c2": "D", "meta:title": "T", "cell:r1c1": "A"},
              "tool_notes": [{"target": "clue:A1", "note": "zero read for O"}]}
    a1, d9, b3, sq, title = packet_edits(ocr, review)
    assert (sq["what"], sq["before"], sq["after"]) == ("key square", "R", "D") and (title["what"], title["before"], "read" in title) == ("header", "", False)
    assert (a1["before"], a1["after"], a1["by"], a1["stage"], a1["why"]) == ("0ne", "One", "AI reviewer · m", "text review", "zero read for O")
    assert d9["before"] == "" and d9["read"] is False and (b3["what"], b3["before"]) == ("printed line", "For solvers")


def test_backfill_gives_the_records_to_a_puzzle_shipped_before_they_were_kept(tmp_path):
    repo, proofs, p = shipped(tmp_path, said(PERSON, SITE, {"clue:A3": "Deux"}))
    write(repo, p, "2026-11-10")
    old = row_of(repo)
    old["edits"] = {"applied": ["clue:A3"], "from": [PERSON]}          # as ship wrote it before 2026-11-11
    del old["notes"], old["corrections"]
    (repo / "provenance.jsonl").write_text(json.dumps(old) + "\n", encoding="utf-8")
    xd = (repo / "xd" / "games1978-03-01.xd").read_bytes()
    p = plan(repo, proofs, BOTH, "b")
    (row,) = unrecorded(repo, p, "2026-11-11")
    assert len(provenance(repo)) == 1 and "records" not in row_of(repo)["edits"]      # a dry run writes nothing
    assert row["shipped"] == old["shipped"] and row["backfilled"] == "2026-11-11" and row["edits"]["records"][0]["before"] == "Two"
    backfill(repo, p, "2026-11-11")
    assert row_of(repo)["edits"]["records"][0]["after"] == "Deux" and (repo / "xd" / "games1978-03-01.xd").read_bytes() == xd
    assert unrecorded(repo, plan(repo, proofs, BOTH, "b")) == []
