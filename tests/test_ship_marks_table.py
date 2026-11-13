"""The rule for a misprint mark beside the edits on its row, cell by cell as design/ship.md's table has it ("A marked
row ships as printed"): who marked (owner, AI reviewer, helper, guest, ignored account), whose edit is on the row (the
marker's own, another's, none), and whether the mark is valid or malformed. Includes the cold review's probes of
2026-11-13 (three passes).

Run with: uv run --with pytest --extra site pytest tests/test_ship_marks_table.py"""

from blitz.ship import AGENT, SITE, Rule, corrected, plan, record
from test_ship import CHECK, OK, XD, _batch
from test_ship_edits import AI_BY, P, PERSON, said, shipped

OWNER = "Reviewer 2"                 # the owner's own tools: kind owner
GUEST = f"a helper 3f2a ({SITE})"    # a guest on the site: kind helper, as a helper is
COCK = XD.replace("A3. Two ~", "A3. Cockail party ~")
MARK = [{"key": "clue:A3", "printed": "Cockail", "meant": "Cocktail"}]
BAD = [{"key": "clue:A3", "printed": "Cockail", "meant": "Cock\ntail"}]        # malformed: a line break in the words meant
EARLY, LATE = "2026-10-21T00:00:00Z", "2026-10-23T00:00:00Z"


def owner(edits, typos=None, comments=(), at=EARLY):
    return said(OWNER, "watch", edits, comments, typos=typos, at=at)


def site(who, edits, typos=None, comments=(), at=LATE):
    return said(who, SITE, edits, comments, typos=typos, at=at)


def ships(p):
    return p["passing"].get(P)


def held(p):
    return p["rows"][0]["reason"] if not ships(p) else ""


def a3(p):
    return next(ln for ln in ships(p)["text"].split("\n") if ln.startswith("A3."))


# ---- owner, AI reviewer: valid ----

def test_owner_or_ai_valid_own_edit_the_row_check(tmp_path):
    for i, (by, via, extra) in enumerate(((OWNER, "watch", ()), (AI_BY, AGENT, (CHECK,)))):
        _, _, p = shipped(tmp_path / f"keep{i}", said(by, via, {"clue:A3": "Cockail parties"}, typos=MARK), *extra, xd=COCK)
        assert a3(p) == "A3. Cockail parties ~ CDE" and ships(p)["corrections"][0]["fits"] == "printed"
        assert ships(p)["edit_records"][0]["class"] == "unclassed"                            # no comment: unclassed
        _, _, p = shipped(tmp_path / f"back{i}", said(by, via, {"clue:A3": "Cocktail parties"}, typos=MARK), *extra, xd=COCK)
        assert a3(p) == "A3. Cockail parties ~ CDE"                                           # the words meant go back
        for j, edit in enumerate(("cocktail party", "Cocktail party Cocktail", "Drinks party")):  # the first pass's probes
            _, _, p = shipped(tmp_path / f"h{i}{j}", said(by, via, {"clue:A3": edit}, typos=MARK), *extra, xd=COCK)
            assert held(p) == "misprint-edit", edit
    # a second word changed beside a mark on another: classed on its own evidence
    _, _, p = shipped(tmp_path / "other", owner({"clue:A3": "Cocktail party"}, [{"key": "clue:A3", "printed": "party", "meant": "parti"}]), xd=COCK)
    assert ships(p)["edit_records"][0]["class"] == "unclassed"
    _, _, p = shipped(tmp_path / "said", owner({"clue:A3": "Cocktail party"}, [{"key": "clue:A3", "printed": "party", "meant": "parti"}],
                                              [("clue:A3", "The scan reads Cocktail.")]), xd=COCK)
    assert ships(p)["edit_records"][0]["class"] == "reading"


def test_owner_valid_anothers_edit_the_row_check_governs_it(tmp_path):
    # a helper edited the row toward the words meant; the owner's later mark governs the row: printed back
    _, _, p = shipped(tmp_path, site(PERSON, {"clue:A3": "Cocktail party"}, at=EARLY), owner({}, MARK, at=LATE), xd=COCK)
    assert a3(p) == "A3. Cockail party ~ CDE" and ships(p)["corrections"][0]["kind"] == "owner"


def test_owner_valid_no_edit_proposed_for_the_export_or_invalid_when_its_words_are_absent(tmp_path):
    repo, _, p = shipped(tmp_path, owner({}, MARK), xd=COCK)
    c = ships(p)["corrections"][0]
    assert c["fits"] == "printed" and a3(p) == "A3. Cockail party ~ CDE"
    assert corrected(ships(p)["text"], [c])[2][0]["done"] == "applied"
    _, _, p = shipped(tmp_path / "x", owner({}, [{"key": "clue:A3", "printed": "Mocktail", "meant": "Cocktail"}]), xd=COCK)
    assert held(p) == "mark-invalid"


# ---- owner, AI reviewer: malformed ----

def test_owner_or_ai_malformed_holds_whoever_edited(tmp_path):
    cases = ((owner({"clue:A3": "Cockail parties"}, BAD),),                                    # own edit
             (site(PERSON, {"clue:A3": "Cockail parties"}, at=EARLY), owner({}, BAD, at=LATE)),  # another's edit
             (owner({}, BAD),),                                                                  # no edit
             (said(AI_BY, AGENT, {}, typos=BAD), CHECK))                                         # the AI's
    for i, recs in enumerate(cases):
        _, _, p = shipped(tmp_path / str(i), *recs, xd=COCK)
        assert held(p) == "mark-invalid", i


# ---- helper, guest: valid ----

def test_helper_or_guest_valid_own_edit_the_row_check_and_a_proposal(tmp_path):
    for i, who in enumerate((PERSON, GUEST)):
        _, _, p = shipped(tmp_path / f"a{i}", site(who, {"clue:A3": "Cocktail party"}, MARK), xd=COCK)   # the second pass's probe
        assert a3(p) == "A3. Cockail party ~ CDE" and ships(p)["corrections"] == [] and ships(p)["proposals"][0]["status"] == "waiting for the owner"
        _, _, p = shipped(tmp_path / f"b{i}", site(who, {"clue:A3": "cocktail party"}, MARK), xd=COCK)
        assert held(p) == "misprint-edit"


def test_helper_or_guest_valid_anothers_edit_ships_as_it_is(tmp_path):
    # the third pass's probe: the owner read the clue again (with a comment); a guest's later mark says the print is wrong
    tow = XD.replace("A3. Two ~", "A3. Tow ~")
    fix = owner({"clue:A3": "Two"}, comments=[("clue:A3", "The crop reads Two.")])
    for i, mark in enumerate(([{"key": "clue:A3", "printed": "Tow", "meant": "Two"}],
                              [{"key": "clue:A3", "printed": "Mocktail", "meant": "Cocktail"}])):  # and one naming absent words
        _, _, p = shipped(tmp_path / str(i), fix, site(GUEST, {}, mark), xd=tow)
        x = ships(p)
        assert a3(p) == "A3. Two ~ CDE" and x["edit_records"][0]["class"] == "reading" and x["edit_records"][0]["by"] == OWNER
        assert x["corrections"] == [] and x["proposals"][0]["status"] == "waiting for the owner"


def test_helper_or_guest_valid_no_edit_nothing_changes(tmp_path):
    for i, mark in enumerate((MARK, [{"key": "clue:A3", "printed": "Mocktail", "meant": "Cocktail"}])):
        _, _, p = shipped(tmp_path / str(i), site(GUEST, {}, mark), xd=COCK)
        assert a3(p) == "A3. Cockail party ~ CDE" and ships(p)["corrections"] == [] and ships(p)["proposals"]


# ---- helper, guest: malformed ----

def test_helper_or_guest_malformed_own_edit_keeps_the_printed_words_or_holds(tmp_path):
    for i, who in enumerate((PERSON, GUEST)):
        _, _, p = shipped(tmp_path / f"a{i}", site(who, {"clue:A3": "Cocktail party"}, BAD), xd=COCK)   # the third pass's probe
        assert held(p) == "misprint-edit"
        _, _, p = shipped(tmp_path / f"b{i}", site(who, {"clue:A3": "Cockail parties"}, BAD), xd=COCK)
        assert a3(p) == "A3. Cockail parties ~ CDE" and ships(p)["proposals"][0]["status"] == "not taken"
    # one that names no row: dropped, said, the edit classed on its own
    _, _, p = shipped(tmp_path / "nokey", site(GUEST, {"clue:A3": "Cocktail party"}, [{"key": "clue:Z9", "printed": "x", "meant": "y"}]), xd=COCK)
    assert a3(p) == "A3. Cocktail party ~ CDE" and ships(p)["proposals"][0]["status"] == "not taken"


def test_helper_or_guest_malformed_anothers_edit_or_none_nothing_changes(tmp_path):
    fix = owner({"clue:A3": "Cocktail party"}, comments=[("clue:A3", "The crop reads Cocktail.")])
    _, _, p = shipped(tmp_path / "other", fix, site(GUEST, {}, BAD), xd=COCK)
    assert a3(p) == "A3. Cocktail party ~ CDE" and ships(p)["proposals"][0]["status"] == "not taken"
    _, _, p = shipped(tmp_path / "none", site(GUEST, {}, BAD), xd=COCK)
    assert a3(p) == "A3. Cockail party ~ CDE" and ships(p)["proposals"][0]["status"] == "not taken"
    assert next(r for r in record(p)["puzzles"] if r["pid"] == P)["proposals"][0]["status"] == "not taken"


# ---- an ignored account ----

def test_an_ignored_accounts_mark_does_nothing(tmp_path):
    for i, mark in enumerate((MARK, BAD)):
        repo, proofs = _batch(tmp_path / str(i), {P: [owner({"clue:A3": "Cocktail party"}, comments=[("clue:A3", "The crop reads Cocktail.")]),
                                                    site(f"walkthrough test ({SITE})", {}, mark)]}, {P: OK})
        (proofs / P / "puzzle.xd").write_text(COCK, encoding="utf-8")
        p = plan(repo, proofs, Rule(ai_ready="both", ignore=("walkthrough test",)), "b")
        assert a3(p) == "A3. Cocktail party ~ CDE" and ships(p)["proposals"] == [] and ships(p)["corrections"] == []


# ---- a key letter ----

def test_a_key_letters_mark_by_whom_and_whose_edit(tmp_path):
    kc = [{"key": "cell:r2c2", "printed": "D", "corrected": "X", "edited": True}]

    def rec(r, k):
        r["proof"]["review"]["key_corrections"] = k
        return r
    _, _, p = shipped(tmp_path / "o", rec(owner({"cell:r2c2": "X"}), kc))                       # the owner's: corrected, noted
    assert ships(p)["edit_records"][0]["class"] == "key correction" and ships(p)["notes"]
    _, _, p = shipped(tmp_path / "h", rec(site(GUEST, {"cell:r2c2": "X"}), kc))                  # a guest's, with their own edit
    assert held(p) == "proposal-waits"
    _, _, p = shipped(tmp_path / "x", owner({"cell:r2c2": "X"}, comments=[("grid:r2c2", "The key shows X.")]), rec(site(GUEST, {}), kc))
    assert ships(p)["edit_records"][0]["class"] == "reading" and ships(p)["proposals"][0]["what"] == "key letter"  # another's: as it is
    _, _, p = shipped(tmp_path / "bad", rec(owner({}), [{"key": "cell:r2c2", "printed": "D", "corrected": "XY"}]))
    assert held(p) == "mark-invalid"
