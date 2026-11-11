"""blitz ship keeps a record of every edit it applies (design/ship.md, "The record of every edit"): what the
packet's xd had, what ships, who made the change, where to see it. A corrected misprint is also said in the
xd's notes; an edit with no whole record holds the puzzle.

Run with: uv run --with pytest pytest tests/test_ship_edits.py"""

import json

from blitz.ship import (AGENT, NOTES_HEAD, SITE, Rule, apply_edits, backfill, edit_records, export, packet_edits, plan, provenance,
                        record, unrecorded, with_notes, write)
from test_ship import CHECK, OK, XD, _batch, proof

P = "games1978-03-01-L030"
PERSON = f"pat ({SITE})"
AI_BY = "Claude (AI proof reviewer, m)"


def said(by, via, edits, comments=(), typos=None, at="2026-10-22T00:00:00Z"):
    r = proof(by, "ready", at, via)
    r["proof"]["review"].update(edits=edits, comments=[{"key": k, "text": t, "why": True} for k, t in comments],
                                **({"typos": typos} if typos is not None else {}))
    return r


def shipped(tmp_path, *recs, rule=Rule(ai_ready="both")):
    repo, proofs = _batch(tmp_path, {P: list(recs)}, {P: OK})
    p = plan(repo, proofs, rule, "b")
    return repo, proofs, p


def row_of(repo):
    return provenance(repo)[0]


def test_a_clue_edit_ships_with_what_it_replaced_and_who_made_it(tmp_path):
    repo, _, p = shipped(tmp_path, said(PERSON, SITE, {"clue:A3": "Deux", "clue:A1^Easy": "Un"}, [("clue:A3", "The crop reads Deux.")]))
    write(repo, p, "2026-11-11")
    e = row_of(repo)["edits"]
    assert e["applied"] == ["clue:A1^Easy", "clue:A3"] or sorted(e["applied"]) == ["clue:A1^Easy", "clue:A3"]
    by = {r["key"]: r for r in e["records"]}
    a3 = by["clue:A3"]
    assert (a3["what"], a3["before"], a3["after"]) == ("clue", "Two", "Deux")
    assert (a3["by"], a3["kind"], a3["via"], a3["stage"]) == (PERSON, "helper", SITE, "proof review")
    assert a3["why"] == "The crop reads Deux." and a3["evidence"]["proof"].endswith(f"?p={P}&k=clue:A3")
    assert (by["clue:A1^Easy"]["what"], by["clue:A1^Easy"]["before"], by["clue:A1^Easy"]["after"]) == ("second clue set", "Uno", "Un")
    # a reading fixed is not a misprint: the xd's notes say nothing of it
    assert NOTES_HEAD not in (repo / "xd" / "games1978-03-01.xd").read_text(encoding="utf-8") and row_of(repo)["notes"] == []


def test_a_key_square_edit_records_the_letter_and_the_answers_through_it(tmp_path):
    repo, _, p = shipped(tmp_path, said(AI_BY, AGENT, {"cell:r2c2": "x"}, [("grid:r2c2", "The key shows X.")]), CHECK)
    write(repo, p, "2026-11-11")
    (r,) = row_of(repo)["edits"]["records"]
    assert (r["key"], r["what"], r["before"], r["after"], r["kind"]) == ("cell:r2c2", "key square", "D", "X", "ai")
    assert r["words"] == {"A3": ["CDE", "CXE"], "D2": ["BDF", "BXF"]} and r["why"] == "The key shows X."


def test_a_header_edit_records_the_header_it_changed_or_added(tmp_path):
    repo, _, p = shipped(tmp_path, said("Reviewer 2", "watch", {"meta:title": "New", "meta:byline": "by A", "meta:author": "A"}))
    write(repo, p, "2026-11-11")
    by = {r["key"]: r for r in row_of(repo)["edits"]["records"]}
    assert (by["meta:title"]["before"], by["meta:title"]["after"], by["meta:title"]["header"], by["meta:title"]["kind"]) == ("T", "New", "Title", "owner")
    assert (by["meta:byline"]["before"], by["meta:byline"]["after"]) == ("", "by A")   # a header the packet's xd didn't have
    assert "meta:author" not in by                                                     # the same value: no edit


def test_a_corrected_misprint_is_said_in_the_xd_notes_and_the_export(tmp_path):
    typo = [{"key": "clue:A3", "printed": "Tow", "meant": "Two", "text": "A3 is printed 'Tow'; corrected to 'Two'."},
            {"key": "clue:D1", "printed": "Fuor", "meant": "Four"}]  # the text review had already put the word right: no edit
    xd = XD.replace("A3. Two ~", "A3. Tow ~")
    repo, proofs = _batch(tmp_path, {P: [said(AI_BY, AGENT, {"clue:A3": "Two"}, typos=typo), CHECK]}, {P: OK})
    (proofs / P / "puzzle.xd").write_text(xd, encoding="utf-8")
    p = plan(repo, proofs, Rule(ai_ready="both"), "b")
    lines = ["A3 is printed 'Tow'; corrected to 'Two'.", "D1 is printed 'Fuor'; corrected to 'Four'."]
    assert p["passing"][P]["notes"] == lines
    assert record(p)["puzzles"][0]["notes"] == lines                    # the ship record carries them: the proof page draws them
    write(repo, p, "2026-11-11")
    text = (repo / "xd" / "games1978-03-01.xd").read_text(encoding="utf-8")
    assert text.endswith("OCR review flags:\nA1: missing\n\n" + NOTES_HEAD + "\n" + "\n".join(lines) + "\n")
    row = row_of(repo)
    assert row["notes"] == lines and row["xd"] and [m["key"] for m in row["edits"]["misprints"]] == ["clue:A3", "clue:D1"]
    (r,) = row["edits"]["records"]
    assert (r["before"], r["after"], r["misprint"]) == ("Tow", "Two", {"printed": "Tow", "meant": "Two"})
    # written once: the plan made again finds it shipped as it stands
    assert plan(repo, proofs, Rule(ai_ready="both"), "b")["rows"][0]["status"] == "shipped"
    export(repo, tmp_path / "out", "games")
    assert (tmp_path / "out" / "games" / "1978" / "games1978-03-01.xd").read_text(encoding="utf-8").endswith("\n\n" + "\n\n".join(lines) + "\n")


def test_a_corrected_key_letter_is_said_in_the_form_the_judge_notes_use(tmp_path):
    typo = [{"key": "cell:r2c2", "printed": "D", "meant": "X"}]
    repo, _, p = shipped(tmp_path, said("Reviewer 2", "watch", {"cell:r2c2": "X"}, typos=typo))
    assert p["passing"][P]["notes"] == ["The printed answer key gave 2 Down as BDF (and so 3 Across as CDE), presumably in error. "
                                        "It has been corrected to BXF and CXE."]
    assert p["passing"][P]["edit_records"][0]["misprint"] == {"printed": "D", "meant": "X"}


def test_an_edit_with_nothing_to_say_what_it_replaced_holds_the_puzzle(tmp_path):
    repo, _, p = shipped(tmp_path, said(PERSON, SITE, {"clue:A9": "No such clue", "clue:A3": "Deux"}))
    row = p["rows"][0]
    assert (row["status"], row["reason"], row["queue"]) == ("held", "edit-unrecorded", "broken") and not p["passing"]
    assert "clue:A9" in row["why"] and row["broken"][0]["stage"] == "import"
    assert write(repo, p, "2026-11-11")["written"] == [] and not (repo / "xd").exists()


def test_a_misprint_correction_that_does_not_say_what_was_printed_holds_the_puzzle(tmp_path):
    for typo, word in (({"key": "clue:A3", "printed": "", "meant": "Deux"}, "printed"),
                       ({"key": "clue:A3", "printed": "Tow", "meant": "Three"}, "doesn't have")):
        _, _, p = shipped(tmp_path / word[:3], said(AI_BY, AGENT, {"clue:A3": "Deux"}, typos=[typo]), CHECK)
        assert p["rows"][0]["reason"] == "edit-unrecorded" and word in p["rows"][0]["why"]


def test_whatever_differs_from_the_packet_has_a_record_or_is_named_missing():
    out, _ = apply_edits(XD, {"clue:A3": "Deux"})
    e = edit_records(XD, out, [said(PERSON, SITE, {"clue:A3": "Deux"})])
    assert not e["missing"] and len(e["records"]) == 1
    e = edit_records(XD, out.replace("A5. Three", "A5. Trois").replace("Title: T", "Title: U"), [said(PERSON, SITE, {"clue:A3": "Deux"})])
    assert sorted(m.split(":")[0] + ":" + m.split(":")[1] for m in e["missing"]) == ["clue:A5", "meta:title"]
    # a decision that isn't a value of the xd, and the list it wrote into the clues (a candidate list taken in as the clues)
    e = edit_records(XD, XD.replace("D4. Six", "D4. Seis"), [said(PERSON, SITE, {"candidate:D-alt1": "clues"})])
    by = {r["key"]: r for r in e["records"]}
    assert not e["missing"] and by["candidate:D-alt1"]["what"] == "decision"
    assert (by["clue:D4"]["before"], by["clue:D4"]["after"], by["clue:D4"]["decided_by"]) == ("Six", "Seis", "candidate:D-alt1")


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
    del old["notes"]
    (repo / "provenance.jsonl").write_text(json.dumps(old) + "\n", encoding="utf-8")
    xd = (repo / "xd" / "games1978-03-01.xd").read_bytes()
    p = plan(repo, proofs, Rule(ai_ready="both"), "b")
    (row,) = unrecorded(repo, p, "2026-11-11")
    assert len(provenance(repo)) == 1 and "records" not in row_of(repo)["edits"]      # a dry run writes nothing
    assert row["shipped"] == old["shipped"] and row["backfilled"] == "2026-11-11" and row["edits"]["records"][0]["before"] == "Two"
    backfill(repo, p, "2026-11-11")
    assert row_of(repo)["edits"]["records"][0]["after"] == "Deux" and (repo / "xd" / "games1978-03-01.xd").read_bytes() == xd
    assert unrecorded(repo, plan(repo, proofs, Rule(ai_ready="both"), "b")) == []
