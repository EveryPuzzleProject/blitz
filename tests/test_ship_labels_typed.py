"""blitz ship, 2026-11-13: two things a person does on the proof page that the import used to refuse.

1. A printed line's label (label:B<n>: what the line is, which the gxd export's Notes rule picks by) is applied to the
   row's `printed`, with a record of class decision; a value that isn't a label, or a line that can't take one, holds
   the puzzle (edits-unapplied). "title" isn't a label: it is kept on the record as what the reviewer said.
2. A clue a person typed where the packet has no text (the ship check's clue-empty) makes the puzzle whole, on the word
   of someone the ship rule's typed_clues names (the owner by default), never from an AI's edit; it ships as typed by
   hand (class typed, the xd's "Typed by hand:" block, the record's typed and counts.typed), never as a reading fix.

The linked-ends cases run on the real packet of New York World No. 11 (tests/data/linked); the ordinary one on test_ship's XD.
Run with: uv run --with pytest pytest tests/test_ship_labels_typed.py"""

import json

import pytest

from blitz.ship import (AGENT, SITE, TYPED_HEAD, Rule, as_shipped, label_problems, plan, provenance, record, rule_of, write)
from blitz.work import Stop
from test_ship import XD, _batch, proof
from test_ship_linked import LEDGER, NO11, PERSON, RULE, batch, packet, row, said

OWNER = f"oops6498 ({SITE})"  # RULE's owner


# ---- 1. a printed line's label ----

def test_a_label_edit_is_applied_to_printed_with_a_decision_record(tmp_path):
    # B8 "CROSWORD PUZZLES": the text step's "section", discarded. The owner keeps it and says it is the intro
    repo, proofs = batch(tmp_path, {NO11: [said(OWNER, SITE, {"keep:B8": True, "label:B8": "intro"})]})
    p = plan(repo, proofs, RULE, "b")
    r = row(p, NO11)
    assert (r["status"], r["rule"]) == ("shippable", "owner")
    x = p["passing"][NO11]
    assert "label:B8" in x["edits"] and "Printed with puzzle:\nCROSWORD PUZZLES\nSOLUTION NEXT WEEK." in x["text"]
    assert "Title:" not in x["text"]                                    # a label makes no header
    write(repo, p, "2026-11-13")
    (prov,) = provenance(repo)
    assert prov["printed"][0] == {"label": "intro", "text": "CROSWORD PUZZLES"}
    recs = {e["key"]: e for e in prov["edits"]["records"]}
    assert {k: (e["what"], e["class"], e["before"], e["after"]) for k, e in recs.items()} == {
        "keep:B8": ("printed line kept", "decision", "not kept", "kept"),
        "label:B8": ("printed line label", "decision", "section", "intro")}
    assert recs["label:B8"]["line"] == "CROSWORD PUZZLES" and recs["label:B8"]["kept"] is True
    # the as-shipped file says the same as the provenance row
    p = plan(repo, proofs, RULE, "b")
    doc = as_shipped(p, record(p))[NO11]
    assert doc["printed"] == prov["printed"] and [e["key"] for e in doc["edits"]["records"]] == ["keep:B8", "label:B8"]


def test_a_label_alone_changes_only_what_the_line_is(tmp_path):
    # B17 "SOLUTION NEXT WEEK." is kept as instructions; relabelled other, its text stays in the block, its label in printed changes
    repo, proofs = batch(tmp_path, {NO11: [said(OWNER, SITE, {"label:B17": "other"})]})
    p = plan(repo, proofs, RULE, "b")
    x = p["passing"][NO11]
    assert x["text"] == packet(NO11)[0]                                 # the xd's text is the packet's: a label isn't in it
    doc = as_shipped(p, record(p))[NO11]
    assert doc["printed"][0] == {"label": "other", "text": "SOLUTION NEXT WEEK."}


def test_title_is_not_a_label_it_is_kept_as_what_the_reviewer_said(tmp_path):
    repo, proofs = batch(tmp_path, {NO11: [said(OWNER, SITE, {"keep:B8": True, "label:B8": "title"})]})
    p = plan(repo, proofs, RULE, "b")
    assert row(p, NO11)["status"] == "shippable"
    x = p["passing"][NO11]
    assert "Title:" not in x["text"] and "Printed with puzzle:\nCROSWORD PUZZLES\n" in x["text"]  # the keep is applied
    rec = next(e for e in x["edit_records"] if e["key"] == "label:B8")
    assert (rec["class"], rec["before"], rec["after"], rec["said"]) == ("decision", "section", "section", "title")
    assert "a title is a header" in rec["note"]
    assert as_shipped(p, record(p))[NO11]["printed"][0] == {"label": "section", "text": "CROSWORD PUZZLES"}


@pytest.mark.parametrize("edits, says", [
    ({"label:B8": "banner"}, "is not a label of a printed line"),
    ({"label:B99": "intro"}, "the packet has no such printed line"),
    ({"label:B15": "intro"}, "where a header was read from"),           # B15 gives the Number
])
def test_a_label_the_xd_cannot_hold_holds_the_puzzle(tmp_path, edits, says):
    repo, proofs = batch(tmp_path, {NO11: [said(OWNER, SITE, edits)]})
    r = row(plan(repo, proofs, RULE, "b"), NO11)
    assert (r["status"], r["reason"], r["queue"]) == ("held", "edits-unapplied", "broken") and says in r["why"]


def test_label_problems_on_a_line_with_no_keep_recorded():
    ocr = {"lines": [{"n": 1, "text": "x", "label": "other"}, {"n": 2, "text": "y", "label": "intro", "keep": True}], "evidence": {}}
    assert label_problems({"label:B2": "credit"}, ocr) == []
    assert "records no keep" in label_problems({"label:B1": "intro"}, ocr)[0]
    assert label_problems({"label:B1": "intro", "keep:B1": True}, ocr) == []
    assert label_problems({"clue:A1": "x"}, ocr) == []


def test_a_label_edit_on_an_ordinary_puzzle_is_applied_too(tmp_path):
    pid = "games1978-03-01-L030"
    rec = proof("Reviewer 2", "ready", "2026-11-13T00:00:00Z", xd="fp")
    rec["proof"]["review"]["edits"] = {"label:B1": "instructions"}
    repo, proofs = _batch(tmp_path, {pid: [rec]}, {pid: {"decision": "ready", "ship": {"ok": True}}})
    (proofs / pid / "ocr.json").write_text(json.dumps({"lines": [{"n": 1, "text": "Fill in the grid.", "label": "intro", "keep": True}],
                                                       "evidence": {}}), encoding="utf-8")
    p = plan(repo, proofs, Rule(), "b")
    assert row(p, pid)["status"] == "shippable" and p["passing"][pid]["text"] == XD
    doc = as_shipped(p, record(p))[pid]
    assert doc["printed"] == [{"label": "instructions", "text": "Fill in the grid."}]
    assert [(e["key"], e["class"], e["before"], e["after"]) for e in doc["edits"]["records"]] == [("label:B1", "decision", "intro", "instructions")]


# ---- 2. a clue typed by a person ----

def _no_text_for_d23(proofs, tmp_path):
    """No. 11 as if its D23 had been read as nothing: the xd's line [missing], the ship check's clue-empty naming it."""
    f = proofs / NO11 / "puzzle.xd"
    f.write_text(f.read_text(encoding="utf-8").replace("35-36. A sudden alide. ~ SLIP", "35-36. [missing] ~ SLIP"), encoding="utf-8")
    t = tmp_path / "h" / "triage" / "c14" / "triage.json"
    tri = json.loads(t.read_text(encoding="utf-8"))
    for x in tri["puzzles"]:
        if x["pid"] == NO11:
            x["ship"]["findings"].append({"code": "clue-empty", "detail": "clues with no text: D23", "items": ["D23"]})
            x["ship"]["incomplete"] = ["clues with no text: D23"]
    t.write_text(json.dumps(tri), encoding="utf-8")


def _typed(tmp_path, recs, rule=RULE):
    repo, proofs = batch(tmp_path, {NO11: recs})
    _no_text_for_d23(proofs, tmp_path)
    return repo, plan(repo, proofs, rule, "b")


def test_the_owners_typed_clue_makes_the_puzzle_whole_and_ships_typed_by_hand(tmp_path):
    repo, p = _typed(tmp_path, [said(OWNER, SITE, {"clue:D23": "A sudden slide."}, [("clue:D23", "That's what the scan says.")])])
    r = row(p, NO11)
    assert (r["status"], r["rule"]) == ("shippable", "owner")
    assert r["why"].endswith('"clues with no text: D23" is filled by the edits applied (D23 typed by a person: no text was read for it)')
    write(repo, p, "2026-11-13")
    text = (repo / "xd" / "nyw1914-03-01.xd").read_text(encoding="utf-8")
    assert "35-36. A sudden slide. ~ SLIP\n" in text
    note = ("The clue for 35-36 was typed by the owner on the proof page (2026-11-12): no text for it was read from the scan. "
            "Their comment: \"That's what the scan says.\"")
    assert text.endswith(f"\n\n{TYPED_HEAD}\n{note}\n")
    (prov,) = provenance(repo)
    rec = next(e for e in prov["edits"]["records"] if e["key"] == "clue:D23")
    assert (rec["class"], rec["before"], rec["after"], rec["by"], rec["note"]) == ("typed", "[missing]", "A sudden slide.", OWNER, note)
    assert prov["typed"] == [{"key": "clue:D23", "by": OWNER, "kind": "owner", "at": "2026-11-12T00:00:00Z", "note": note}]
    assert prov["notes"] == []                                          # not a note for gxd: the export's Notes rule never sees it
    p = plan(repo, proofs := tmp_path / "h" / "proof" / "c14", RULE, "b")
    rec_ = record(p)
    (x,) = [x for x in rec_["puzzles"] if x["pid"] == NO11]
    assert x["status"] == "shipped" and x["typed"] == [{"key": "clue:D23", "kind": "owner", "note": note}] and rec_["counts"]["typed"] == 1
    assert as_shipped(p, rec_)[NO11]["typed"][0]["by"] == "the owner"   # the site's copy names no account
    assert rec_["rule"]["typed_clues"] == "people"


def test_a_helpers_typed_clue_counts_unless_the_rule_says_owner(tmp_path):
    rec = said(PERSON, SITE, {"clue:D23": "A sudden slide."})
    _, p = _typed(tmp_path, [rec], Rule(ai_ready="both", owner=("oops6498",), typed_clues="owner"))
    r = row(p, NO11)
    assert (r["status"], r["reason"], r["rule"]) == ("held", "incomplete", "people")
    assert "D23 typed by a helper: a clue typed where none was read makes the puzzle whole only on the owner's word" in r["why"]
    _, p = _typed(tmp_path / "2", [rec])                                                    # typed_clues: people, the default
    assert row(p, NO11)["status"] == "shippable"
    assert next(e for e in p["passing"][NO11]["edit_records"] if e["key"] == "clue:D23")["kind"] == "helper"


def test_an_ais_typed_clue_never_makes_the_puzzle_whole(tmp_path):
    # the AI's real Ready on No. 11 carries clue:D23 = "A sudden slide."; the owner's Ready beside it carries nothing
    assert LEDGER[NO11]["proof"]["review"]["edits"]["clue:D23"] == "A sudden slide."
    _, p = _typed(tmp_path, [LEDGER[NO11], said(OWNER, SITE, {})])
    r = row(p, NO11)
    assert (r["status"], r["reason"], r["rule"]) == ("held", "incomplete", "owner") and r["why"] == "Ready, but incomplete: clues with no text: D23"
    # the AI's Ready alone, with ai_ready either: the AI ships it, and its own edit makes nothing whole
    _, p = _typed(tmp_path / "2", [LEDGER[NO11]], Rule(ai_ready="either", owner=("oops6498",)))
    assert (row(p, NO11)["reason"], row(p, NO11)["rule"]) == ("incomplete", "ai")
    # the owner types the same text as the AI: it ships, recorded as the owner's typed clue
    _, p = _typed(tmp_path / "3", [LEDGER[NO11], said(OWNER, SITE, {"clue:D23": "A sudden slide."})])
    rec = next(e for e in p["passing"][NO11]["edit_records"] if e["key"] == "clue:D23")
    assert (rec["class"], rec["by"]) == ("typed", OWNER)


@pytest.mark.parametrize("text", ["", "  ", "[missing]", "A sudden\nslide."])
def test_a_typed_clue_with_no_text_makes_nothing_whole(tmp_path, text):
    _, p = _typed(tmp_path, [said(OWNER, SITE, {"clue:D23": text})])
    assert row(p, NO11)["reason"] in ("incomplete", "edits-unapplied")


def test_a_typed_clue_on_an_ordinary_puzzle(tmp_path):
    pid = "games1978-03-01-L031"
    rec = proof("Reviewer 2", "ready", "2026-11-13T00:00:00Z", xd="fp")  # the owner's own tools
    rec["proof"]["review"]["edits"] = {"clue:A3": "Two"}
    tri = {"decision": "ready", "ship": {"ok": False, "findings": [{"code": "clue-empty", "detail": "clues with no text: A3", "items": ["A3"]}],
                                         "incomplete": ["clues with no text: A3"]}}
    repo, proofs = _batch(tmp_path, {pid: [rec]}, {pid: tri})
    (proofs / pid / "puzzle.xd").write_text(XD.replace("A3. Two ~ CDE", "A3. [missing] ~ CDE"), encoding="utf-8")
    p = plan(repo, proofs, Rule(), "b")
    assert row(p, pid)["status"] == "shippable"
    x = p["passing"][pid]
    assert "A3. Two ~ CDE" in x["text"] and f"\n{TYPED_HEAD}\nA3 was typed by the owner on the proof page (2026-11-13): " in x["text"]
    assert [(e["key"], e["class"]) for e in x["edit_records"]] == [("clue:A3", "typed")]
    # a clue missing from the xd altogether (clue-missing) is not made whole by an edit: there is no line to put it on
    tri["ship"]["findings"][0]["code"] = "clue-missing"
    repo, proofs = _batch(tmp_path / "2", {pid: [rec]}, {pid: tri})
    assert row(plan(repo, proofs, Rule(), "b"), pid)["reason"] == "incomplete"


def test_the_rule_says_whose_typed_clue_counts(tmp_path):
    (tmp_path / "fixes").mkdir()
    assert (rule_of(tmp_path).typed_clues, rule_of(tmp_path).marks, rule_of(tmp_path).grid_fixes) == ("people",) * 3
    (tmp_path / "fixes" / "ship-rule.json").write_text(json.dumps({"typed_clues": "owner", "marks": "owner"}), encoding="utf-8")
    assert (rule_of(tmp_path).typed_clues, rule_of(tmp_path).marks, rule_of(tmp_path).grid_fixes) == ("owner", "owner", "people")
    (tmp_path / "fixes" / "ship-rule.json").write_text(json.dumps({"grid_fixes": "helpers"}), encoding="utf-8")
    with pytest.raises(Stop):
        rule_of(tmp_path)
    (tmp_path / "fixes" / "ship-rule.json").write_text(json.dumps({"typed_clues": "anyone"}), encoding="utf-8")
    with pytest.raises(Stop):
        rule_of(tmp_path)
