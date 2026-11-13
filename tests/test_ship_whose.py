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
    # where the owner's edit keeps the printed words, their edit says what the row is: it declines the mark (since the
    # second cold pass, 2026-11-13)
    _, _, p = shipped(tmp_path / "agree", owner({"clue:A3": "Cockail parties"}), site(GUEST, {}, MARK), xd=COCK)
    assert a3(p) == "A3. Cockail parties ~ CDE" and ships(p)["corrections"] == []
    assert ships(p)["proposals"][0]["status"] == "declined by the owner"


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


# ---- the owner declines a mark: "not a misprint" (the second cold pass, 2026-11-13) ----

def _declines(r, *marks, by=GUEST):
    r["proof"]["review"]["declines"] = [{**m, "by": by} for m in marks]
    return r


def test_the_reviewers_probe_the_owner_declines_a_guests_or_a_helpers_mark(tmp_path):
    from blitz.ship import export, write
    for i, who in enumerate((GUEST, PERSON)):
        # the mark alone: it takes effect
        _, _, p = shipped(tmp_path / f"m{i}", site(who, {}, MARK, at=EARLY), owner({}, at=LATE), xd=COCK)
        assert ships(p)["corrections"][0]["by"] == who
        # the owner's explicit "not a misprint": declined, never at the export
        repo, _, p = shipped(tmp_path / f"d{i}", site(who, {}, MARK, at=EARLY), _declines(owner({}, at=LATE), *MARK, by=who), xd=COCK)
        x = ships(p)
        assert a3(p) == "A3. Cockail party ~ CDE" and x["corrections"] == []
        (q,) = x["proposals"]
        assert (q["status"], q["by"], q["declined_by"]) == ("declined by the owner", who, OWNER) and "not a misprint" in q["says"]
        assert next(r for r in record(p)["puzzles"])["proposals"][0]["status"] == "declined by the owner"
        write(repo, p, "2026-11-13")
        res = export(repo, tmp_path / f"out{i}", "games")
        assert res["corrections"] == {"applied": 0, "noted": 0, "not applied": 0}
        assert "Cocktail" not in (tmp_path / f"out{i}" / "corrections.tsv").read_text(encoding="utf-8")
        # the owner edits the row back to the print, with a comment: their edit declines it too, and says so
        fix = owner({"clue:A3": "Cockail party"}, comments=[("clue:A3", "as printed, not a typo")], at=LATE)
        _, _, p = shipped(tmp_path / f"e{i}", site(who, {}, MARK, at=EARLY), fix, xd=COCK)
        x = ships(p)
        assert a3(p) == "A3. Cockail party ~ CDE" and x["corrections"] == [] and "keeps the printed words" in x["proposals"][0]["says"]


def test_the_owners_own_mark_is_not_declined_by_their_own_edit(tmp_path):
    _, _, p = shipped(tmp_path, owner({"clue:A3": "Cockail parties"}, MARK), site(GUEST, {}, MARK), xd=COCK)
    assert [c["by"] for c in ships(p)["corrections"]] == [OWNER]


def test_taking_the_decline_back_lets_the_mark_take_effect(tmp_path):
    later = owner({}, at="2026-10-24T00:00:00Z")                         # the owner's latest record has no decline
    _, _, p = shipped(tmp_path, site(GUEST, {}, MARK, at=EARLY), later, xd=COCK)
    assert ships(p)["corrections"][0]["by"] == GUEST


def test_a_declined_key_correction_leaves_the_letter_as_printed(tmp_path):
    kc = [{"key": "cell:r2c2", "printed": "D", "corrected": "X", "edited": True}]
    dec = {"key": "cell:r2c2", "printed": "D", "meant": "X"}
    g = site(GUEST, {"cell:r2c2": "X"}, at=EARLY)
    g["proof"]["review"]["key_corrections"] = kc
    _, _, p = shipped(tmp_path / "edit", g, _declines(owner({}, at=LATE), dec))
    x = ships(p)
    assert "\nCDE\n" in x["text"] and x["notes"] == [] and x["proposals"][0]["status"] == "declined by the owner"
    # the packet already had the letter meant (corrected before review): the decline puts the printed letter back, recorded
    g = site(GUEST, {}, at=EARLY)
    g["proof"]["review"]["key_corrections"] = [{**kc[0], "edited": False}]
    _, _, p = shipped(tmp_path / "packet", g, _declines(owner({}, at=LATE), dec), xd=XD.replace("\nCDE\n", "\nCXE\n").replace("CDE", "CXE"))
    x = ships(p)
    assert "\nCDE\n" in x["text"] and [(e["key"], e["class"], e["before"], e["after"], e["by"]) for e in x["edit_records"]] == [
        ("cell:r2c2", "decision", "X", "D", OWNER)]


def test_the_owner_can_decline_an_ais_mark_and_a_waiting_proposal(tmp_path):
    from blitz.ship import Rule
    _, _, p = shipped(tmp_path / "ai", said(AI_BY, AGENT, {}, typos=MARK), CHECK, _declines(owner({}, at=LATE), *MARK, by=AI_BY), xd=COCK)
    assert ships(p)["corrections"] == [] and ships(p)["proposals"][0]["status"] == "declined by the owner"
    # marks: owner: a guest's mark waits for the owner, who declines it
    _, _, p = shipped(tmp_path / "wait", site(GUEST, {}, MARK, at=EARLY), _declines(owner({}, at=LATE), *MARK), xd=COCK,
                      rule=Rule(ai_ready="both", marks="owner"))
    assert ships(p)["proposals"][0]["status"] == "declined by the owner" and ships(p)["corrections"] == []


def test_a_decline_given_after_the_puzzle_shipped_holds_at_the_export(tmp_path):
    import json
    from blitz.ship import export, write
    repo, proofs, p = shipped(tmp_path, site(GUEST, {}, MARK, at=EARLY), owner({}, at=LATE), xd=COCK)
    write(repo, p, "2026-11-13")
    with (repo / "fixes" / "decisions.jsonl").open("a", encoding="utf-8") as fh:  # the owner declines it later
        fh.write(json.dumps({**_declines(owner({}, at="2026-11-14T00:00:00Z"), *MARK), "id": "proof:" + p["rows"][0]["pid"]}) + "\n")
    res = export(repo, tmp_path / "out", "games")
    assert res["corrections"] == {"applied": 0, "noted": 0, "not applied": 0}


def test_declines_come_through_from_the_site():
    from blitz.ship import from_site
    recs = from_site({"games1978-03-01-L030": {"proofs": {"oops6498": {"decision": "ready", "at": "2026-11-13T00:00:00Z",
                                                                      "declines": [{"key": "clue:A3", "printed": "Cockail", "meant": "Cocktail"}]}}}},
                     [], {"games1978-03-01-L030"})
    assert recs[0]["proof"]["review"]["declines"][0]["key"] == "clue:A3"


def test_a_key_correction_declined_after_shipping_holds_the_puzzle_back_from_the_export(tmp_path):
    import json
    from blitz.ship import export, plan, write
    g = site(GUEST, {"cell:r2c2": "X"}, at=EARLY)
    g["proof"]["review"]["key_corrections"] = [{"key": "cell:r2c2", "printed": "D", "corrected": "X", "edited": True}]
    repo, proofs, p = shipped(tmp_path, g, owner({}, at=LATE))
    write(repo, p, "2026-11-13")
    assert "\nCXE\n" in (repo / "xd" / "games1978-03-01.xd").read_text(encoding="utf-8")
    pid = p["rows"][0]["pid"]
    later = _declines(owner({}, at="2026-11-14T00:00:00Z"), {"key": "cell:r2c2", "printed": "D", "meant": "X"})
    later["id"], later["proof"]["review"]["xd"] = "proof:" + pid, "fp"          # the owner's later Ready, on this version
    with (repo / "fixes" / "decisions.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(later) + "\n")
    res = export(repo, tmp_path / "out", "games")
    held = (tmp_path / "out" / "held-back.tsv").read_text(encoding="utf-8")
    assert "games1978-03-01\tkey-declined:" in held and "r2c2 D->X" in held and "re-ship it first" in held
    assert not list((tmp_path / "out").rglob("*.xd"))
    # re-shipped: the letter as printed, and the export takes it
    p = plan(repo, proofs, __import__("test_ship_edits").BOTH, "b")
    assert p["rows"][0]["status"] == "shippable" and "\nCDE\n" in p["passing"][pid]["text"]
    assert p["passing"][pid]["proposals"][0]["says"].startswith("The key letter at r2c2: marked as printed")
    write(repo, p, "2026-11-14")
    export(repo, tmp_path / "out2", "games")
    assert "key-declined" not in (tmp_path / "out2" / "held-back.tsv").read_text(encoding="utf-8")


def test_a_guests_decline_is_shown_not_taken(tmp_path):
    _, _, p = shipped(tmp_path, owner({}, MARK, at=EARLY), _declines(site(GUEST, {}, at=LATE), *MARK, by=OWNER), xd=COCK)
    x = ships(p)
    assert [c["by"] for c in x["corrections"]] == [OWNER]                              # the owner's mark stands
    (q,) = x["proposals"]
    assert (q["what"], q["status"], q["by"]) == ("decline", "not taken", GUEST) and "only the owner declines" in q["says"]
