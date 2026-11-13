"""blitz ship on a linked-ends puzzle (the New York World's FUN, 1913-14; design/ship.md, "Linked ends"): the
reviewers' edits are applied to an xd whose clue lines are labelled by their end squares' numbers, each with its
record under the three-case rule, and an edit that can't be applied safely holds the puzzle and says why.

tests/data/linked holds four real packets of batch nyw-1914-c1, run c14 (puzzle.xd as the pipeline wrote it;
ocr.json and review.json cut down to what ship reads; triage.json with the ship check of xword-ocr
claude/linked-ends-shipcheck) and, in ledger.jsonl, a real record for each from the publication's ledger: the AI
reviewer's Ready on Nos. 11 and 12, the owner's Ready on earlier versions of Nos. 7 and 8. SMALL is made up.

Run with: uv run --with pytest pytest tests/test_ship_linked.py"""

import json
import shutil
from pathlib import Path

from blitz.ship import (AGENT, LINE_LABELS, NOTES_HEAD, SITE, Rule, _printed, apply_edits, apply_linked, corrected, edit_records, linked, plan,
                        provenance, read_linked, record, refused, write)
from test_ship import proof

DATA = Path(__file__).parent / "data" / "linked"
NO7, NO8, NO11, NO12 = "nyw1914-02-01-L001", "nyw1914-02-08-L001", "nyw1914-03-01-L000", "nyw1914-03-08-L000"
LEDGER = {json.loads(ln)["id"][6:]: json.loads(ln) for ln in (DATA / "ledger.jsonl").read_text(encoding="utf-8").splitlines()}
PERSON = f"pat ({SITE})"
RULE = Rule(ai_ready="both", owner=("oops6498",))

SMALL = """Title: T
Clues: linked ends: see Numbering


__I__
_BEE_
PAIDX
_TAX_
__A__


1-2. An insect ~ BEE
3-4. What we get ~ PAIDX
5-6. Third ~ TAX

7-8. Middle ~ IEIAA
1-5. Down two ~ BAT
2-6. Down three ~ EDX


Numbering:
__7__
_1.2_
3...4
_5.6_
__8__
"""


def packet(pid):
    d = DATA / pid
    return ((d / "puzzle.xd").read_text(encoding="utf-8"), json.loads((d / "ocr.json").read_text(encoding="utf-8")),
            json.loads((d / "review.json").read_text(encoding="utf-8")))


def said(by, via, edits, comments=(), at="2026-11-12T00:00:00Z", answer="ready", **more):
    r = proof(by, answer, at, via)
    r["proof"]["review"].update(edits=edits, comments=[{"key": k, "text": t, "why": True} for k, t in comments], **more)
    return r


def records(xd, text, *recs, ocr=None, review=None):
    e = edit_records(xd, text, list(recs), RULE, "p", ocr, review)
    return e, {r["key"]: r for r in e["records"]}


def batch(tmp_path, said_by_pid, pids=(NO7, NO8, NO11, NO12)):
    """A publication repo and a run's packets from the real fixtures; a record's review is put on the packet's
    current version unless it names one (the ledger's own records keep the version they were given on)."""
    repo, proofs = tmp_path / "nyw", tmp_path / "h" / "proof" / "c14"
    (repo / "fixes").mkdir(parents=True)
    recs, triage = [], []
    for pid in pids:
        shutil.copytree(DATA / pid, proofs / pid)
        triage.append({"pid": pid, **json.loads((DATA / pid / "triage.json").read_text(encoding="utf-8"))})
        fp = json.loads((DATA / pid / "review.json").read_text(encoding="utf-8"))["xd_fp"]
        for r in said_by_pid.get(pid, []):
            r = json.loads(json.dumps(r))
            if r["id"] == "proof:p":
                r["id"] = f"proof:{pid}"
                r["proof"]["review"]["xd"] = fp
            recs.append(r)
    (repo / "fixes" / "decisions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")
    t = tmp_path / "h" / "triage" / "c14"
    t.mkdir(parents=True)
    (t / "triage.json").write_text(json.dumps({"puzzles": triage}), encoding="utf-8")
    return repo, proofs


def row(p, pid):
    return next(r for r in p["rows"] if r["pid"] == pid)


# ---- reading a linked-ends xd ----

def test_a_linked_ends_xd_is_read_by_its_own_record_and_written_back_as_it_was():
    for pid in (NO7, NO8, NO11, NO12):
        xd, ocr, review = packet(pid)
        assert linked(xd) and apply_linked(xd, {}, ocr, review) == (xd, [], [])
        assert read_linked(xd)["error"] == "" and len(read_linked(xd)["line"]) == 32
    m = read_linked(packet(NO11)[0])
    assert (m["label"]["A2"], m["clues"]["A2"]) == ("1-2", "To unite in matrimony.")          # the across words first
    assert (m["label"]["D1"], m["label"]["D23"], m["clues"]["D23"]) == ("33-34", "35-36", "A sudden alide.")  # the apex and the foot
    assert m["words"]["D1"] == [(0, 6), (1, 6), (2, 6), (3, 6)]                               # '_' is outside the puzzle
    assert (m["nums"][(0, 6)], m["nums"][(12, 6)], m["given"]) == ("33", "36", set())
    assert not linked(SMALL.replace("Clues: linked ends: see Numbering\n", ""))


def test_clue_lines_that_do_not_fit_the_grids_words_take_no_clue_or_square_edit():
    lost = SMALL.replace("5-6. Third ~ TAX\n", "")                                             # a line gone: the rest can't be placed
    assert "5 clue line(s) for the 6 word(s)" in read_linked(lost)["error"]
    text, done, cant = apply_linked(lost, {"clue:A4": "x", "meta:title": "New"})
    assert (text, done) == (lost, []) and "clue:A4" in cant[0] and "5 clue line(s)" in cant[0]
    assert apply_linked(lost, {"meta:title": "New"})[0].startswith("Title: New\n")              # a header needs no clue line
    swapped = SMALL.replace("1-2. An insect ~ BEE\n3-4. What we get ~ PAIDX\n", "3-4. What we get ~ PAIDX\n1-2. An insect ~ BEE\n")
    assert "labelled 3-4 is listed where A2's belongs" in read_linked(swapped)["error"]         # the list and the numbers disagree


# ---- the kinds of edit, on the real packets and the ledger's own records ----

def test_a_clue_edit_lands_on_its_words_line_which_keeps_its_pair():
    xd, ocr, review = packet(NO11)
    rec = LEDGER[NO11]                                                                          # the AI's Ready: line:B15, clue:D23
    edits = rec["proof"]["review"]["edits"]
    assert refused(edits, xd) == []
    text, done, cant = apply_linked(xd, edits, ocr, review)
    assert cant == [] and sorted(done) == ["clue:D23", "line:B15"]
    assert "35-36. A sudden slide. ~ SLIP\n" in text and "alide" not in text
    assert text == xd.replace("A sudden alide.", "A sudden slide.")                            # nothing else moved
    e, by = records(xd, text, rec, ocr=ocr, review=review)
    assert e["missing"] == [] and list(by) == ["clue:D23"]                                      # line:B15 is what the packet already had
    d23 = by["clue:D23"]
    assert (d23["what"], d23["before"], d23["after"], d23["pair"], d23["class"], d23["kind"]) == (
        "clue", "A sudden alide.", "A sudden slide.", "35-36", "reading", "ai")
    assert "SLIP fits" in d23["why"] and d23["evidence"]["proof"].endswith("?p=p&k=clue:D23")


def test_a_key_square_read_again_changes_the_answers_of_the_words_through_it():
    xd, ocr, review = packet(NO12)
    rec = LEDGER[NO12]                                                                          # the AI's Ready: cell:r4c8 = L
    text, done, cant = apply_linked(xd, rec["proof"]["review"]["edits"], ocr, review)
    assert (done, cant) == (["cell:r4c8"], [])
    assert "___SETTLER___\n" in text and "5-6. One who inhabits a new country. ~ SETTLER\n" in text and "2-9. Measures. ~ ELLS\n" in text
    assert "." not in text.split("\n\n\n")[1]
    e, by = records(xd, text, rec, ocr=ocr, review=review)
    r = by["cell:r4c8"]
    assert e["missing"] == [] and (r["what"], r["class"], r["before"], r["after"]) == ("key square", "reading", ".", "L")
    assert r["words"] == {"A6": ["SETT.ER", "SETTLER"], "D3": ["EL.S", "ELLS"]}
    assert NOTES_HEAD not in e["text"]                                                          # a reading, not a misprint: no note


def test_a_printed_lines_text_and_keep_reach_the_xd_and_the_lines_the_export_reads():
    xd, ocr, review = packet(NO7)
    rec = LEDGER[NO7]                                                                           # the owner's: keep:B3, keep:B5, line:B4, clue:A19
    edits = rec["proof"]["review"]["edits"]
    text, done, cant = apply_linked(xd, edits, ocr, review)
    assert cant == [] and sorted(done) == ["clue:A19", "keep:B3", "keep:B5", "line:B4"]
    block = text.split("Printed with puzzle:\n")[1].split("\n\n")[0].split("\n")
    assert block == [edits["line:B4"]]                                                          # three lines were kept: one stays, as corrected
    assert "23-24. A friend of Roosevelt. ~ RIIS\n" in text
    e, by = records(xd, text, rec, ocr=ocr, review=review)
    assert e["missing"] == []
    assert (by["keep:B3"]["what"], by["keep:B3"]["class"], by["keep:B3"]["before"], by["keep:B3"]["after"]) == (
        "printed line kept", "decision", "kept", "not kept")
    assert by["keep:B3"]["line"].startswith("The cross-word puzzles apparent")
    assert (by["line:B4"]["what"], by["line:B4"]["class"], by["line:B4"]["after"], by["line:B4"]["kept"]) == (
        "printed line", "reading", edits["line:B4"], True)
    assert by["line:B4"]["before"].startswith("parently are getting more popu.") and "no  way to add a paragraph" in by["line:B4"]["why"]
    assert (by["clue:A19"]["before"], by["clue:A19"]["pair"], by["clue:A19"]["kind"]) == ("[missing]", "23-24", "owner")
    assert [p["text"] for p in _printed(ocr, review, edits)] == [edits["line:B4"]]
    assert len(_printed(ocr, review)) == 3                                                      # and without them, as before


def test_a_shape_fix_that_renumbers_the_words_or_strands_a_number_is_not_applied():
    xd, ocr, review = packet(NO8)
    edits = LEDGER[NO8]["proof"]["review"]["edits"]                                             # the owner's: r3c10 is not a square, r9c11 is S
    assert refused(edits, xd) == []
    text, done, cant = apply_linked(xd, edits, ocr, review)
    assert (text, done) == (xd, []) and len(cant) == 2                                          # nothing applied in part
    assert cant[0].startswith("grid:r3c10: the fix changes which words the grid has or how they are numbered")
    assert "the clues have to be placed again (assembly)" in cant[0]
    assert "leaves a printed number on a square outside the puzzle (4 at r3c10)" in cant[1]


def test_a_shape_fix_that_keeps_the_grids_words_is_applied_with_its_numbers():
    # the made-up grid: r3c5 (the X of PAIDX) is not a square of the puzzle, and the 4 printed there is at r3c4
    fix = {"grid:r3c5": "_", "cell:r3c5": "_"}
    assert "leaves a printed number on a square outside the puzzle (4 at r3c5)" in apply_linked(SMALL, fix)[2][0]
    edits = {**fix, "num:r3c5": "", "num:r3c4": "4"}
    rec = said(PERSON, SITE, edits, [("grid:r3c5", "The crop shows no square there.")])
    text, done, cant = apply_linked(SMALL, edits)
    assert cant == [] and sorted(done) == sorted(edits)
    assert "PAID_\n" in text and "3-4. What we get ~ PAID\n" in text and "\n3..4_\n" in text
    assert "7-8. Middle ~ IEIAA\n" in text                                                      # no other word ran through it
    e, by = records(SMALL, text, rec)
    g = by["grid:r3c5"]
    assert e["missing"] == [] and (g["what"], g["class"], g["before"], g["after"], g["with"]) == ("grid square", "reading", "X", "_", ["cell:r3c5"])
    assert g["words"] == {"A4": ["PAIDX", "PAID"]} and "cell:r3c5" not in by
    assert (by["num:r3c4"]["before"], by["num:r3c4"]["after"], by["num:r3c5"]["before"], by["num:r3c5"]["after"]) == ("", "4", "4", "")
    assert by["num:r3c4"]["class"] == "unclassed"                                               # nothing said about the number: applied, and listed
    # a square added with no letter, a square that makes a new word, a letter for a square outside the puzzle
    assert "gives it no letter" in apply_linked(SMALL, {"grid:r1c2": "."})[2][0]
    assert "changes which words the grid has" in apply_linked(SMALL, {"grid:r1c2": ".", "cell:r1c2": "Q"})[2][0]
    assert "a letter for a square that is outside the puzzle" in apply_linked(SMALL, {"cell:r1c1": "Q"})[2][0]
    assert "say two things about one square" in apply_linked(SMALL, {"grid:r3c5": "_", "cell:r3c5": "Q"})[2][0]


def test_a_squares_number_corrected_relabels_its_words_line_and_the_numbering_section():
    rec = said(PERSON, SITE, {"num:r3c5": "9"}, [("num:r3c5", "The square prints 9.")])
    text, done, cant = apply_linked(SMALL, {"num:r3c5": "9"})
    assert (done, cant) == (["num:r3c5"], [])
    assert "3-9. What we get ~ PAIDX\n" in text and "\n3...9\n" in text
    assert text == SMALL.replace("3-4. What", "3-9. What").replace("3...4", "3...9")            # the other lines keep their labels
    e, by = records(SMALL, text, rec)
    n = by["num:r3c5"]
    assert e["missing"] == [] and (n["what"], n["class"], n["before"], n["after"], n["pairs"]) == (
        "square number", "reading", "4", "9", {"A4": ["3-4", "3-9"]})
    # a number taken away: the line carries its slot's own label, as the pipeline writes a word with an end unread
    text = apply_linked(SMALL, {"num:r3c5": ""})[0]
    assert "A4. What we get ~ PAIDX\n" in text and "\n3....\n" in text and read_linked(text)["error"] == ""
    # letters given to every square of BEE would make it a word printed in the grid, with no clue: not the import's
    cant = apply_linked(SMALL, {"num:r2c2": "B", "num:r2c3": "E", "num:r2c4": "E"})[2]
    assert "change which words are printed in the grid" in cant[0]
    assert "isn't one of the puzzle's" in apply_linked(SMALL, {"num:r1c1": "3"})[2][0]
    assert "1-61" in apply_linked(SMALL, {"num:r3c5": "88"})[2][0]                               # the section has no symbol past 61


def test_edits_that_cannot_be_applied_hold_the_puzzle_and_say_why():
    xd, ocr, review = packet(NO11)
    assert refused({"label:B3": "intro", "ev:number": "4", "clue:A2^Easy": "x", "candidate:A-alt1": "remove", "fitb:A2": "no"}, xd) == [
        "candidate:A-alt1", "clue:A2^Easy", "ev:number", "fitb:A2"]                     # a label is applied (test_ship_labels_typed.py)
    cant = lambda edits: apply_linked(xd, edits, ocr, review)[2]
    assert "the grid has no such word with a clue" in cant({"clue:A99": "x"})[0]
    # B15 is the line the Number was read from: its text may be corrected while it still shows the xd's Number
    assert cant({"line:B15": "No. 11."}) == []
    assert "where the number was read from" in cant({"line:B15": "No. 12"})[0] and "meta:" in cant({"line:B15": "No. 12"})[0]
    assert "isn't a line kept or dropped" in cant({"keep:B15": False})[0]
    assert "no such printed line" in cant({"line:B99": "x"})[0]
    assert cant({"line:B17": "a\nb"}) == []  # a paragraph break in a printed line: each part a line of the block
    assert "not an empty line" in cant({"line:B17": "a\n\nb"})[0]
    assert "isn't one line of text" in cant({"clue:A6": "a\nb"})[0]
    assert "an empty line" in cant({"line:B17": " "})[0]
    assert "the grid has no such square" in cant({"cell:r40c1": "A"})[0]
    assert "neither one letter nor a kind of square" in cant({"cell:r2c7": "AB"})[0]            # no rebus squares in 1914
    # with no packet to say which lines are kept, a line's edit has no place
    assert "aren't the packet's kept lines" in apply_linked(xd, {"keep:B17": False})[2][0]


def test_a_kept_line_added_or_the_last_one_dropped_makes_or_removes_the_block():
    xd, ocr, review = packet(NO11)                                                              # keeps B17 and B18
    none = apply_linked(xd, {"keep:B17": False, "keep:B18": False}, ocr, review)[0]
    assert "Printed with puzzle:" not in none and "\n\n\nAssembly flags:\nkey found in the next issue\n" in none
    assert none.split("\n\n\n")[:3] == xd.split("\n\n\n")[:3]
    back = apply_linked(none, {"keep:B17": True}, ocr, {**review, "corrections": {}})
    assert back[2] == ["keep:B17: the xd's printed lines aren't the packet's kept lines, so the edit has no place in it"]
    ocr0 = {**ocr, "lines": [{**ln, "keep": False} if "keep" in ln else ln for ln in ocr["lines"]]}
    text = apply_linked(none, {"keep:B17": True}, ocr0, review)[0]
    assert "\n\n\nPrinted with puzzle:\nSOLUTION NEXT WEEK.\n\nAssembly flags:\n" in text


# ---- the three cases, on a linked-ends xd ----

def test_a_misprinted_key_letter_is_corrected_with_a_note_that_names_the_words_by_their_pairs():
    rec = said("Claude (AI proof reviewer, m)", AGENT, {}, typos=[{"key": "cell:r2c3", "printed": "E", "meant": "O"}])
    e, by = records(SMALL, SMALL, rec)
    assert e["missing"] == [] and by["cell:r2c3"]["class"] == "key correction"
    assert "1-2. An insect ~ BOE\n" in e["text"] and "7-8. Middle ~ IOIAA\n" in e["text"]
    assert e["text"].endswith(NOTES_HEAD + "\nThe printed answer key gave 7-8 as IEIAA (and so 1-2 as BEE), presumably in error "
                              "(E at row 2, column 3). It has been corrected to IOIAA and BOE (O).\n")


def test_a_clue_misprint_stays_as_printed_and_the_export_corrects_it_naming_the_pair():
    rec = said("Claude (AI proof reviewer, m)", AGENT, {}, typos=[{"key": "clue:A2", "printed": "insect", "meant": "inspect"}])
    e, _ = records(SMALL, SMALL, rec)
    assert e["text"] == SMALL and e["records"] == []                                            # as printed
    (c,) = e["corrections"]
    assert (c["fits"], c["says"]) == ("printed", "The clue for 1-2 is printed 'insect'; meant 'inspect'.")
    text, notes, rows = corrected(SMALL, e["corrections"])
    assert "1-2. An inspect ~ BEE\n" in text and notes == ["The clue for 1-2 is printed 'insect'; corrected to 'inspect'."]
    assert rows[0]["done"] == "applied" and apply_edits(SMALL, {"clue:A2": "x"})[1] == ["clue:A2"]


# ---- through the ship path ----

def test_no_11_ships_on_a_persons_ready_with_the_ais_edit_applied_and_recorded(tmp_path):
    repo, proofs = batch(tmp_path, {NO11: [LEDGER[NO11]]})
    r = row(plan(repo, proofs, RULE, "nyw-1914-c1"), NO11)
    assert (r["status"], r["reason"], r["queue"]) == ("held", "no-ready", "unchecked")          # the AI alone: the check has its doubts
    repo, proofs = batch(tmp_path / "2", {NO11: [LEDGER[NO11], said(PERSON, SITE, {})]})
    p = plan(repo, proofs, RULE, "nyw-1914-c1")
    r = row(p, NO11)
    assert (r["status"], r["queue"], r["rule"], r["xdid"]) == ("shippable", "shippable", "people", "nyw1914-03-01")
    write(repo, p, "2026-11-12")
    text = (repo / "xd" / "nyw1914-03-01.xd").read_text(encoding="utf-8")
    assert text == packet(NO11)[0].replace("A sudden alide.", "A sudden slide.")
    (prov,) = provenance(repo)
    assert prov["edits"]["applied"] == ["clue:D23", "line:B15"] and [x["key"] for x in prov["edits"]["records"]] == ["clue:D23"]
    assert prov["edits"]["records"][0]["by"] == LEDGER[NO11]["by"] and prov["shipped"]["rule"] == "people"
    assert [x["text"] for x in prov["printed"]][0] == "SOLUTION NEXT WEEK."
    assert row(plan(repo, proofs, RULE, "nyw-1914-c1"), NO11)["status"] == "shipped"             # written once


def test_an_edit_the_import_cannot_apply_holds_a_linked_ends_puzzle_as_broken(tmp_path):
    repo, proofs = batch(tmp_path, {NO11: [said(PERSON, SITE, {"line:B15": "No. 12"})]})
    r = row(plan(repo, proofs, RULE, "b"), NO11)
    assert (r["status"], r["reason"], r["queue"]) == ("held", "edits-unapplied", "broken")
    assert "can't apply to this linked-ends puzzle as it stands: line:B15" in r["why"] and r["broken"][0]["stage"] == "import"
    repo, proofs = batch(tmp_path / "2", {NO11: [said(PERSON, SITE, {"label:B17": "a heading"})]})
    r = row(plan(repo, proofs, RULE, "b"), NO11)
    assert (r["reason"], r["why"]) == ("edits-unapplied", "proof-page edits the import can't apply yet: label:B17: 'a heading' is not a label of a printed line (" + ", ".join(LINE_LABELS) + ")")
    assert record(plan(repo, proofs, RULE, "b"))["counts"]["queues"]["broken"] >= 1


def test_no_12_ships_when_a_ready_fills_the_one_unread_key_square(tmp_path):
    # the packet's key has one square unread (r4c8): the ship check calls the grid unsolved, which no Ready lifts...
    repo, proofs = batch(tmp_path, {NO12: [said(PERSON, SITE, {})]})
    r = row(plan(repo, proofs, RULE, "b"), NO12)
    assert (r["status"], r["reason"], r["why"]) == ("held", "incomplete", "Ready, but incomplete: 1 square(s) unsolved")
    # ...unless the edits that ship with the Ready give that square its letter: the AI's Ready has it (cell:r4c8 = L)
    repo, proofs = batch(tmp_path / "2", {NO12: [LEDGER[NO12], said(PERSON, SITE, {})]})
    p = plan(repo, proofs, RULE, "b")
    r = row(p, NO12)
    assert (r["status"], r["rule"], r["xdid"]) == ("shippable", "people", "nyw1914-03-08")
    assert r["why"].endswith('the ship check\'s "1 square(s) unsolved" is filled by the edits applied')
    write(repo, p, "2026-11-12")
    text = (repo / "xd" / "nyw1914-03-08.xd").read_text(encoding="utf-8")
    assert "___SETTLER___\n" in text and "." not in text.split("\n\n\n")[1]
    (prov,) = provenance(repo)
    (rec,) = prov["edits"]["records"]
    assert (rec["key"], rec["before"], rec["after"], rec["class"], rec["kind"]) == ("cell:r4c8", ".", "L", "reading", "ai")
    assert "filled by the edits applied" in prov["shipped"]["why"] and prov["check"]["findings"].count("grid-unsolved") == 1
    # the AI's Ready alone doesn't ship it: the check doesn't pass, so nothing counts as the one Ready
    repo, proofs = batch(tmp_path / "3", {NO12: [LEDGER[NO12]]})
    assert row(plan(repo, proofs, RULE, "b"), NO12)["reason"] == "no-ready"


def test_only_an_unread_square_with_its_letter_is_made_whole_by_an_edit():
    from blitz.ship import filled_by

    ship = {"findings": [{"code": "grid-unsolved", "detail": "2 square(s) unsolved", "cells": ["r1c1", "r2c2"]},
                         {"code": "clue-empty", "detail": "clues with no text: A5", "items": ["A5"]}],
            "incomplete": ["2 square(s) unsolved", "clues with no text: A5"]}
    assert filled_by(ship, {"cell:r1c1": "A", "cell:r2c2": "b", "clue:A5": "Typed"}) == ["2 square(s) unsolved"]  # not the clue...
    # ...unless it is in the typed edits: those of the people whose typed clue counts (Rule.typed_clues; tests/test_ship_labels_typed.py)
    assert filled_by(ship, {}, {"clue:A5": "Typed"}) == ["clues with no text: A5"]
    assert filled_by(ship, {}, {"clue:A5": "[missing]"}) == [] and filled_by(ship, {}, {"clue:A5": " "}) == []
    assert filled_by(ship, {"cell:r1c1": "A"}) == [] and filled_by(ship, {"cell:r1c1": "A", "cell:r2c2": "_"}) == []
    assert filled_by({"findings": [{"code": "grid-unsolved"}], "incomplete": ["2 square(s) unsolved"]}, {"cell:r1c1": "A"}) == []  # squares not named


def test_a_puzzle_triage_says_needs_work_is_broken_whoever_reviewed_an_earlier_version(tmp_path):
    # No. 7: the owner's Ready was on an earlier version, and triage says this one needs work (a block of clues unread).
    # It is the pipeline's, with the stage it points to: not "not checked yet", which asks a person to proofread it
    stale = said("Claude (AI proof reviewer, m)", AGENT, {}, answer="notready")
    stale["id"], stale["proof"]["review"]["xd"] = f"proof:{NO11}", "an-earlier-version"
    repo, proofs = batch(tmp_path, {NO7: [LEDGER[NO7]], NO11: [stale]})
    p = plan(repo, proofs, RULE, "b")
    r = row(p, NO7)
    assert (r["status"], r["reason"], r["queue"]) == ("held", "needs-work", "broken")
    assert r["why"].startswith("needs work: clues-unread; ") and r["why"].endswith("Ready was on an earlier version of the puzzle: look again")
    assert [(b["code"], b["stage"]) for b in r["broken"]] == [("clues-unread", "parts")] and r["asks"] == []
    assert r["reviewed"] and r["said"][0]["stale"]                                              # still said, and shown as given earlier
    # No. 11: all that was said is stale too, but triage says it is ready for review: that one is a proofread to ask for
    r = row(p, NO11)
    assert (r["reason"], r["queue"]) == ("proof-stale", "unchecked")


# ---- after the cold review of 2026-11-12 (blitz-work/reviews/2026-11-12-linked-ends-review.md) ----

NO9 = "nyw1914-02-15-L001"
AI_BY = "Claude (AI proof reviewer, m)"


def test_a_correction_the_import_cannot_make_holds_the_puzzle_and_nothing_says_it_was_made(tmp_path):
    # a key correction with no cell: edit (the entry alone is the correction), on an xd whose clue lines are out of
    # order: apply_linked refuses any square edit there, so the letter can't be corrected
    swapped = SMALL.replace("1-2. An insect ~ BEE\n3-4. What we get ~ PAIDX\n", "3-4. What we get ~ PAIDX\n1-2. An insect ~ BEE\n")
    rec = said(AI_BY, AGENT, {}, typos=[{"key": "cell:r2c3", "printed": "E", "meant": "O"}])
    e, by = records(swapped, swapped, rec)
    assert e["text"] == swapped and by == {} and e["notes"] == [] and e["corrections"] == []    # no note, no record: nothing changed
    assert len(e["cant"]) == 1 and "cell:r2c3" in e["cant"][0] and "labelled 3-4 is listed where A2's belongs" in e["cant"][0]
    # through the ship path, on No. 11's packet with two of its lines changed over: held for the import, in words
    owner = "oops6498 (review site)"  # a key letter is corrected on the owner's word only (2026-11-13)
    repo, proofs = batch(tmp_path, {NO11: [said(owner, SITE, {}, typos=[{"key": "cell:r2c7", "printed": "E", "meant": "X"}])]})
    xd = packet(NO11)[0]
    a, b = "1-2. To unite in matrimony. ~ WED\n", "3-4. A woman's costume for horseback riding. ~ HABIT\n"
    (proofs / NO11 / "puzzle.xd").write_text(xd.replace(a + b, b + a), encoding="utf-8")
    p = plan(repo, proofs, RULE, "b")
    r = row(p, NO11)
    assert (r["status"], r["reason"], r["queue"]) == ("held", "edits-unapplied", "broken") and NO11 not in p["passing"]
    assert "cell:r2c7" in r["why"] and "can't be made" in r["why"] and r["broken"][0]["stage"] == "import" and "notes" not in r
    # the same entry on the packet as it is: corrected, with its note
    repo, proofs = batch(tmp_path / "2", {NO11: [said(owner, SITE, {}, typos=[{"key": "cell:r2c7", "printed": "E", "meant": "X"}])]})
    p = plan(repo, proofs, RULE, "b")
    assert row(p, NO11)["status"] == "shippable" and "_____WXD_____\n" in p["passing"][NO11]["text"] and len(row(p, NO11)["notes"]) == 1
    # and the export says "applied" only for a correction of the print it did apply
    typo = [{"key": "clue:A2", "printed": "insect", "meant": "inspect"}]
    assert corrected(swapped, typo)[2][0]["done"] == "not applied" and corrected(swapped, typo)[:2] == (swapped, [])


def test_a_clue_edit_lands_only_on_the_line_the_proof_pages_row_is(tmp_path):
    # No. 9 (1914-02-15): the page's row A12 is the clue read with the pair 12-14 ("A small particle"); the xd's line
    # for the word A12 is "7-8. Belonging to me." An edit made looking at the one must not land on the other
    xd, ocr, review = packet(NO9)
    assert review["matches_xd"] is False and ocr["clues"]["A12"]["printed"] == "12-14" and read_linked(xd)["label"]["A12"] == "7-8"
    text, done, cant = apply_linked(xd, {"clue:A12": "A small particle."}, ocr, review)
    assert (text, done) == (xd, []) and len(cant) == 1
    assert "row A12 is the clue printed 12-14" in cant[0] and "line for that word is 7-8" in cant[0]
    assert apply_linked(xd, {"clue:A12": "x"}, {**ocr, "clues": {}}, review)[2][0].startswith("clue:A12: the packet records no such clue row")
    # on a packet whose rows are its xd's lines, the same check passes (No. 11's D23 is 35-36 on both)
    xd11, ocr11, review11 = packet(NO11)
    assert apply_linked(xd11, {"clue:D23": "A sudden slide."}, ocr11, review11)[2] == []
    assert apply_linked(xd11, {"clue:D23": "x"}, {**ocr11, "clues": list(ocr11["clues"].items())}, review11)[2] == []   # older packets: a list
    # a linked-ends packet that doesn't say its page shows its xd is not taken as agreeing: held, the packet's to rebuild
    repo, proofs = batch(tmp_path, {NO9: [said(PERSON, SITE, {"clue:A12": "A small particle."})], NO11: [said(PERSON, SITE, {})]}, pids=(NO9, NO11))
    for pid in (NO9, NO11):
        (proofs / pid / "review.json").write_text(json.dumps({"xd_fp": json.loads((DATA / pid / "review.json").read_text(encoding="utf-8"))["xd_fp"]}), encoding="utf-8")
    p = plan(repo, proofs, RULE, "b")
    assert [(row(p, pid)["reason"], row(p, pid)["queue"]) for pid in (NO9, NO11)] == [("packet-stale", "broken")] * 2


def test_an_ais_ready_never_fills_an_unread_square_for_itself(tmp_path):
    # No. 12 under ai_ready: either: the AI's Ready counts as the one Ready, and its own cell:r4c8 would fill the square
    either = Rule(ai_ready="either", owner=("oops6498",))
    repo, proofs = batch(tmp_path, {NO12: [LEDGER[NO12]]})
    r = row(plan(repo, proofs, either, "b"), NO12)
    assert (r["status"], r["reason"], r["queue"], r["rule"]) == ("held", "incomplete", "broken", "ai")
    assert r["why"] == "Ready, but incomplete: 1 square(s) unsolved"
    # with a helper's Ready beside it (rule: people), or the owner's (rule: owner), the same edit fills it
    for i, who in enumerate((PERSON, f"oops6498 ({SITE})")):
        repo, proofs = batch(tmp_path / str(i), {NO12: [LEDGER[NO12], said(who, SITE, {})]})
        r = row(plan(repo, proofs, either, "b"), NO12)
        assert (r["status"], r["rule"]) == ("shippable", ("people", "owner")[i]) and "filled by the edits applied" in r["why"]


# ---- a Not ready that waits on the pipeline ----

NO9 = "nyw1914-02-15-L001"
# the owner's Not ready on No. 9 as the ledger has it (2026-11-12): 29 square numbers, two squares of shape, two key
# letters, and "i renumbered the grid. doesn't look like the clues match and will need to be rebuilt."
OWNER_NO9 = next(json.loads(ln) for ln in (DATA / "owner-2026-11-12.jsonl").read_text(encoding="utf-8").splitlines() if NO9 in ln)


def test_a_not_ready_with_fixes_to_the_grid_waits_on_the_pipeline_and_does_not_lead_the_walk(tmp_path):
    repo, proofs = batch(tmp_path, {NO9: [OWNER_NO9], NO11: [LEDGER[NO11]], NO12: [LEDGER[NO12]]}, pids=(NO9, NO11, NO12))
    p = plan(repo, proofs, RULE, "nyw-1914-c1")
    r = row(p, NO9)
    assert (r["status"], r["reason"], r["queue"]) == ("held", "awaits-replace", "broken")
    assert r["asks"] == [] and r["reviewed"]
    b = r["broken"][0]
    assert (b["stage"], b["code"]) == ("assembly", "awaits-replace") and "2 square(s) of the grid's shape, 32 square number(s), 2 key letter(s)" in b["what"]
    assert [x["code"] for x in r["broken"][1:]] == ["incomplete", "incomplete"]            # and what the ship check finds, with its stages
    # what was said, kept on the card with nothing to answer
    assert [(a["kind"], a["text"]) for a in r["asked"]] == [("owner", "i renumbered the grid. doesn't look like the clues match and will need to be rebuilt.")]
    assert r["why"].startswith("waiting on the pipeline: oops6498 (review site) said Not ready with fixes to the grid")
    # nothing is held on a question, so the walk is the puzzles a person can do something about
    walk = [x["pid"] for x in sorted(p["rows"], key=lambda x: x["order"])]
    assert walk.index(NO9) > max(walk.index(NO11), walk.index(NO12))
    rec = record(p)
    assert rec["counts"]["queues"]["question"] == 0 and rec["counts"]["held_by"]["awaits-replace"] == 1
    pub = next(x for x in rec["puzzles"] if x["pid"] == NO9)
    assert pub["asked"][0]["who"] == "the owner" and "oops6498" not in json.dumps(pub)    # the site's copy names no account


def test_once_the_packet_is_made_from_those_fixes_it_goes_by_what_triage_says(tmp_path):
    repo, proofs = batch(tmp_path, {NO9: [OWNER_NO9]}, pids=(NO9,))
    f = proofs / NO9 / "ocr.json"
    ocr = json.loads(f.read_text(encoding="utf-8"))
    # as xword-ocr records what a reading was made from (linkedends.Fixes.record: the decisions, by whom and when)
    ocr["reviewer_fixes"] = {"decisions": [{"by": OWNER_NO9["by"], "at": OWNER_NO9["at"], "answer": "notready"}]}
    f.write_text(json.dumps(ocr), encoding="utf-8")
    # triage still says it needs work (No. 9's clue column): the pipeline's, with what the owner said kept on the card
    r = row(plan(repo, proofs, RULE, "b"), NO9)
    assert (r["reason"], r["queue"]) == ("needs-work", "broken") and r["asked"][0]["text"].startswith("i renumbered the grid")
    assert r["why"].startswith("needs work after the reviewer's fixes to the grid were read in: ")
    assert r["broken"] and all(b["code"] != "awaits-replace" for b in r["broken"])       # triage's blocking parts and their stages
    # triage says it is ready for review: the owner's to look at again, a question as any Not ready is
    t = tmp_path / "h" / "triage" / "c14" / "triage.json"
    tri = json.loads(t.read_text(encoding="utf-8"))
    tri["puzzles"][0].update(decision="ready", blocking=[])
    t.write_text(json.dumps(tri), encoding="utf-8")
    r = row(plan(repo, proofs, RULE, "b"), NO9)
    assert (r["reason"], r["queue"]) == ("owner-hold", "question") and "asked" not in r
    assert r["asks"][0]["text"].startswith("i renumbered the grid")


def test_a_not_ready_with_no_fix_to_the_grid_stays_a_question(tmp_path):
    # a helper's Not ready with a note and a clue edit: a question for the owner, as before
    no = said(PERSON, SITE, {"clue:A12": "x"}, answer="notready", at="2026-11-12T01:00:00Z")
    # an AI reviewer's Not ready with a key letter: an AI's fixes are not the pipeline's to read in
    ai = said("Claude (AI proof reviewer, m)", AGENT, {"cell:r4c8": "L"}, answer="notready")
    repo, proofs = batch(tmp_path, {NO11: [no], NO12: [ai]}, pids=(NO11, NO12))
    p = plan(repo, proofs, RULE, "b")
    assert [(row(p, pid)["reason"], row(p, pid)["queue"]) for pid in (NO11, NO12)] == [("not-ready", "question")] * 2


def test_a_helpers_or_a_guests_grid_fixes_wait_for_the_re_place_unless_the_rule_says_owner(tmp_path):
    """grid_fixes: people (the default since 2026-11-13): a helper's or a guest's Not ready with fixes to the grid waits on
    the pipeline as the owner's does. grid_fixes: owner (the owner's rule of 2026-11-12, "Owner only for now"): the same
    edits from anyone but the owner wait for nothing, and stay a question."""
    edits = OWNER_NO9["proof"]["review"]["edits"]
    for who in (PERSON, f"guest-7f3a ({SITE})"):
        repo, proofs = batch(tmp_path / who[:5], {NO9: [said(who, SITE, edits, answer="notready")]}, pids=(NO9,))
        r = row(plan(repo, proofs, RULE, "b"), NO9)
        assert (r["reason"], r["queue"]) == ("awaits-replace", "broken") and r["awaits"]["who"] == who
        r = row(plan(repo, proofs, Rule(ai_ready="both", owner=("oops6498",), grid_fixes="owner"), "b"), NO9)
        assert (r["reason"], r["queue"]) == ("not-ready", "question") and "asked" not in r


def test_a_grid_fix_on_an_ordinary_puzzle_is_still_a_question(tmp_path):
    from test_ship import DOUBT, P, _batch

    no = said(PERSON, SITE, {"cell:r1c1": "A", "grid:r2c2": "#"}, answer="notready")
    repo, proofs = _batch(tmp_path, {P + "31": [no]}, {P + "31": DOUBT})
    r = plan(repo, proofs, Rule(ai_ready="both"), "b")["rows"][0]
    assert (r["reason"], r["queue"]) == ("not-ready", "question")                     # the import applies such edits from a Ready


def test_what_the_pipeline_read_in_from_the_owner_ships_with_an_edit_record(tmp_path):
    """A re-placed packet's base values include the owner's squares, key letters and numbers. No Ready's edit carries
    them, so ship records them from the packet's own record (ocr.json reviewer_fixes.squares, as xword-ocr writes it)."""
    repo, proofs = batch(tmp_path, {NO11: [said(PERSON, SITE, {})]}, pids=(NO11,))
    f = proofs / NO11 / "ocr.json"
    ocr = json.loads(f.read_text(encoding="utf-8"))
    who = {"by": OWNER_NO9["by"], "at": "2026-11-12T20:00:34Z"}
    ocr["reviewer_fixes"] = {"decisions": [{**who, "answer": "notready"}], "squares": [
        {"key": "grid:r4c3", "value": "_", "was": ".", **who},      # the shape: a reading of the printed grid
        {"key": "grid:r5c5", "value": ".", "was": ".", **who},      # what the stage had already: no change, no record
        {"key": "cell:r2c8", "value": "N", "was": ".", **who},      # a key letter: nothing says misread or misprinted
        {"key": "num:r1c7", "value": "29", **who}]}                 # a number: what stood there before isn't recorded
    f.write_text(json.dumps(ocr), encoding="utf-8")
    p = plan(repo, proofs, RULE, "b")
    assert row(p, NO11)["status"] == "shippable"
    write(repo, p, "2026-11-12")
    (prov,) = provenance(repo)
    got = [(x["key"], x["what"], x["class"], x["before"], x["after"], x["stage"], x["kind"]) for x in prov["edits"]["records"]]
    assert got == [("grid:r4c3", "grid square", "reading", ".", "_", "re-place", "owner"),
                   ("cell:r2c8", "key square", "unclassed", ".", "N", "re-place", "owner"),
                   ("num:r1c7", "square number", "reading", "", "29", "re-place", "owner")]
    assert prov["edits"]["records"][2]["before_recorded"] is False and prov["edits"]["records"][0]["by"] == OWNER_NO9["by"]
    assert prov["edits"]["records"][0]["evidence"]["proof"].endswith(f"{NO11}&k=grid:r4c3")
