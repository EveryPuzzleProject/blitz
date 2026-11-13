"""Whose input counts (the owner's rule of 2026-11-13, "the other reviewers can have power to mark shit up and do whatever
they want, given that we can always go back and fix it"): with the ship rule's marks / grid_fixes / typed_clues at
"people", the default, a helper's or a guest's input counts as the owner's; an ignored account's never does; an AI's
keeps its own limits. One person's edit is never changed by another's mark, and where two people disagree the owner's
stands, else the puzzle is the owner's question. design/ship.md, "Whose input counts" and the marks table.

Run with: uv run --with pytest --extra site pytest tests/test_ship_whose.py"""

from blitz.ship import AGENT, SITE, record
from test_ship import CHECK, XD
from test_ship_edits import AI_BY, PERSON, said
from test_ship_marks_table import BAD, COCK, EARLY, GUEST, LATE, MARK, OWNER, a3, held, owner, ships, shipped, site

MEANT2 = [{"key": "clue:A3", "printed": "Cockail", "meant": "Cock tail"}]  # another reading of the same misprint


def test_a_helpers_or_guests_valid_mark_takes_effect_like_the_owners(tmp_path):
    for i, who in enumerate((PERSON, GUEST)):
        _, _, p = shipped(tmp_path / f"none{i}", site(who, {}, MARK), xd=COCK)           # no edit: proposed for the export
        x = ships(p)
        assert a3(p) == "A3. Cockail party ~ CDE" and x["proposals"] == []
        assert [(c["fits"], c["by"]) for c in x["corrections"]] == [("printed", who)]
        _, _, p = shipped(tmp_path / f"own{i}", site(who, {"clue:A3": "Cocktail party"}, MARK), xd=COCK)  # own edit: the row check
        assert a3(p) == "A3. Cockail party ~ CDE" and ships(p)["corrections"][0]["fits"] == "printed"
        _, _, p = shipped(tmp_path / f"bad{i}", site(who, {"clue:A3": "cocktail party"}, MARK), xd=COCK)
        assert held(p) == "misprint-edit"


def test_a_helpers_key_correction_is_made_with_its_note(tmp_path):
    rec = site(GUEST, {"cell:r2c2": "X"})
    rec["proof"]["review"]["key_corrections"] = [{"key": "cell:r2c2", "printed": "D", "corrected": "X", "edited": True}]
    _, _, p = shipped(tmp_path, rec)
    x = ships(p)
    assert x["edit_records"][0]["class"] == "key correction" and x["notes"] and x["edit_records"][0]["by"] == GUEST


def test_a_helpers_malformed_mark_or_one_naming_absent_words_is_dropped_and_holds_nothing(tmp_path):
    for i, mark in enumerate((BAD, [{"key": "clue:A3", "printed": "Mocktail", "meant": "Cocktail"}])):
        _, _, p = shipped(tmp_path / str(i), site(GUEST, {}, mark), xd=COCK)
        x = ships(p)
        assert x["corrections"] == [] and x["proposals"][0]["status"] == "not taken"   # never reaches the export
    _, _, p = shipped(tmp_path / "o", owner({}, [{"key": "clue:A3", "printed": "Mocktail", "meant": "Cocktail"}]), xd=COCK)
    assert held(p) == "mark-invalid"                                                   # the owner's still holds


def test_a_helpers_mark_on_the_owners_edit_the_owners_edit_stands(tmp_path):
    fix = owner({"clue:A3": "Cocktail party"}, comments=[("clue:A3", "The crop reads Cocktail.")])
    _, _, p = shipped(tmp_path / "differ", fix, site(GUEST, {}, MARK), xd=COCK)
    x = ships(p)
    assert a3(p) == "A3. Cocktail party ~ CDE" and x["edit_records"][0]["class"] == "reading" and x["corrections"] == []
    assert x["proposals"][0]["status"] == "not taken" and "the owner's edit on the row stands" in x["proposals"][0]["says"]
    # where the owner's edit keeps the printed words, the two agree: the mark takes effect
    _, _, p = shipped(tmp_path / "agree", owner({"clue:A3": "Cockail parties"}), site(GUEST, {}, MARK), xd=COCK)
    assert a3(p) == "A3. Cockail parties ~ CDE" and ships(p)["corrections"][0]["by"] == GUEST


def test_a_helpers_mark_on_another_helpers_edit_is_the_owners_question(tmp_path):
    fix = site(PERSON, {"clue:A3": "Cocktail party"}, comments=[("clue:A3", "The crop reads Cocktail.")], at=EARLY)
    _, _, p = shipped(tmp_path, fix, site(GUEST, {}, MARK), xd=COCK)
    r = p["rows"][0]
    assert (r["reason"], r["queue"]) == ("mark-disputed", "question") and not p["passing"]
    assert [a["who"] for a in r["asks"]] == [PERSON, GUEST] and all(a["row"] == "clue:A3" for a in r["asks"])
    assert [a["who"] for a in next(x for x in record(p)["puzzles"])["asks"]] == ["a helper", "a helper"]  # no account named on the site


def test_the_owners_mark_on_a_helpers_edit_governs_the_row(tmp_path):
    _, _, p = shipped(tmp_path, site(GUEST, {"clue:A3": "Cocktail party"}, at=EARLY), owner({}, MARK, at=LATE), xd=COCK)
    # the owner's mark says the helper's edit corrected the print, which blitz never ships: the words go back as printed
    assert a3(p) == "A3. Cockail party ~ CDE" and ships(p)["corrections"][0]["by"] == OWNER


def test_two_peoples_marks_that_disagree(tmp_path):
    # two helpers: neither is taken, the owner decides
    _, _, p = shipped(tmp_path / "two", site(PERSON, {}, MARK, at=EARLY), site(GUEST, {}, MEANT2), xd=COCK)
    r = p["rows"][0]
    assert (r["reason"], r["queue"]) == ("mark-disputed", "question") and len(r["asks"]) == 2
    # the owner and a helper: the owner's is taken, the helper's not
    _, _, p = shipped(tmp_path / "owner", owner({}, MARK), site(GUEST, {}, MEANT2), xd=COCK)
    x = ships(p)
    assert [(c["meant"], c["by"]) for c in x["corrections"]] == [("Cocktail", OWNER)]
    assert x["proposals"][0]["status"] == "not taken" and "the owner's mark" in x["proposals"][0]["says"]
    # a person and the AI reviewer: the person's is taken; the AI never overrides a person
    _, _, p = shipped(tmp_path / "ai", said(AI_BY, AGENT, {}, typos=MEANT2), CHECK, site(GUEST, {}, MARK), xd=COCK)
    x = ships(p)
    assert [c["by"] for c in x["corrections"]] == [GUEST] and x["proposals"][0]["by"] == AI_BY
    # the same words from two people: one correction, no question
    _, _, p = shipped(tmp_path / "same", site(PERSON, {}, MARK, at=EARLY), site(GUEST, {}, MARK), xd=COCK)
    assert len(ships(p)["corrections"]) == 1 and ships(p)["proposals"] == []


def test_two_peoples_key_letters_that_disagree(tmp_path):
    def kc(r, letter):
        r["proof"]["review"]["key_corrections"] = [{"key": "cell:r2c2", "printed": "D", "corrected": letter, "edited": False}]
        return r
    _, _, p = shipped(tmp_path / "two", kc(site(PERSON, {}, at=EARLY), "X"), kc(site(GUEST, {}), "Y"))
    assert p["rows"][0]["reason"] == "mark-disputed"
    _, _, p = shipped(tmp_path / "owner", kc(owner({}), "X"), kc(site(GUEST, {}), "Y"))
    x = ships(p)
    assert "\nCXE\n" in x["text"] and x["edit_records"][0]["by"] == OWNER and x["proposals"][0]["status"] == "not taken"
    assert XD.count("CDE")  # the packet's letter was D


def test_peoples_grid_fixes_that_disagree_hold_the_puzzle_for_the_owner(tmp_path):
    import json
    from test_ship_linked import NO11, RULE, batch, row, said as said_l
    from blitz.ship import plan
    repo, proofs = batch(tmp_path, {NO11: [said_l(f"oops6498 ({SITE})", SITE, {})]})
    o = json.loads((proofs / NO11 / "ocr.json").read_text(encoding="utf-8"))
    o["reviewer_fixes"] = {"undecided": [{"key": "grid:r5c7", "values": [
        {"value": "_", "by": PERSON, "at": "2026-11-12T10:00:00Z", "kind": "helper"},
        {"value": ".", "by": GUEST, "at": "2026-11-12T11:00:00Z", "kind": "helper"}]}]}
    (proofs / NO11 / "ocr.json").write_text(json.dumps(o), encoding="utf-8")
    r = row(plan(repo, proofs, RULE, "b"), NO11)
    assert (r["status"], r["reason"], r["queue"]) == ("held", "fixes-disputed", "question")
    assert [(a["who"], a["row"]) for a in r["asks"]] == [(PERSON, "grid:r5c7"), (GUEST, "grid:r5c7")]
