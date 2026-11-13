"""What a person can check before the import (design/ship.md, "The xd as it will ship"): the exact xd ship would write,
recorded beside the ship record with its edit records; where the packet's printed lines land in the xd (for the proof
page's preview of the notes); a person's own "printed this way, but wrong" (typos / key_corrections from the proof
page), which ships the text as printed and is corrected at the gxd export; and a printed line with a paragraph break,
end to end.

Run with: uv run --with pytest --extra site pytest tests/test_ship_preview.py"""

import json

from blitz.ship import (AGENT, AS_SHIPPED, SITE, Rule, _printed, apply_linked, as_shipped, corrected, edit_records, from_site, plan,
                        printed_place, provenance, record, to_gxd, write, write_record)
from test_ship import CHECK, XD
from test_ship_edits import AI_BY, BOTH, P, PERSON, said, shipped, xd_of
from test_ship_linked import LEDGER, NO7, NO12, RULE, batch, packet, row


# ---- 1. the xd as it will ship -------------------------------------------------------------

def test_the_record_carries_the_exact_xd_ship_writes_beside_it_with_its_edit_records(tmp_path):
    repo, _, p = shipped(tmp_path, said(PERSON, SITE, {"clue:A3": "Deux"}, [("clue:A3", "The crop reads Deux.")]))
    rec = record(p)
    docs = as_shipped(p, rec)
    doc = docs[P]
    assert doc["status"] == "shippable" and doc["xdid"] == "games1978-03-01" and doc["at"] == rec["at"]
    (e,) = doc["edits"]["records"]
    assert (e["key"], e["before"], e["after"], e["class"], e["by"]) == ("clue:A3", "Two", "Deux", "reading", "a helper")  # no helper's name
    assert as_shipped(p, record(p, False), public=False)[P]["edits"]["records"][0]["by"] == PERSON
    row_ = next(r for r in rec["puzzles"] if r["pid"] == P)
    assert row_["as_shipped"] == doc["xd_fp"]
    f = write_record(repo, p)
    on_disk = json.loads((f.parent / "b" / AS_SHIPPED / f"{P}.json").read_text(encoding="utf-8"))
    write(repo, p, "2026-11-13")
    assert on_disk["xd"] == xd_of(repo)                                                      # what --write wrote, byte for byte
    assert provenance(repo)[0]["xd"] == on_disk["xd_fp"]


def test_the_sites_file_of_a_puzzle_that_no_longer_passes_is_removed_at_publish():
    from blitz.ship import stale_as_shipped
    keys = ["batch/b/ship.json", "batch/b/as-shipped/p1.json", "batch/b/as-shipped/p2.json", "batch/c/as-shipped/p3.json"]
    assert stale_as_shipped(keys, "b", {"p1": {}}) == ["batch/b/as-shipped/p2.json"]


def test_a_puzzle_that_no_longer_passes_loses_its_file(tmp_path):
    repo, proofs, p = shipped(tmp_path, said(PERSON, SITE, {}))
    f = write_record(repo, p)
    assert (f.parent / "b" / AS_SHIPPED / f"{P}.json").exists()
    (repo / "fixes" / "decisions.jsonl").write_text("", encoding="utf-8")
    write_record(repo, plan(repo, proofs, BOTH, "b"))
    assert not (f.parent / "b" / AS_SHIPPED / f"{P}.json").exists()


# ---- 2. where the printed lines land -----------------------------------------------------

def test_the_record_says_where_each_printed_line_lands_and_whether_an_edit_is_applied(tmp_path):
    xd, ocr, review = packet(NO12)
    place = printed_place(xd, ocr, review)
    kept = [ln["n"] for ln in ocr["lines"] if ln.get("keep")]
    assert place["lines"] == kept and place["edits"] == "applied" and place["head"] == "Printed with puzzle:"
    assert place["fixed"] == [25]                                                            # the Number's line: not kept or dropped
    plain = "Title: T\n\n\nA\n\n\nA1. x ~ A\n\n\nPrinted with puzzle:\nhello\n"
    o = {"lines": [{"n": 1, "text": "hello", "label": "intro", "keep": True}, {"n": 2, "text": "ad", "label": "other", "keep": False}]}
    assert printed_place(plain, o, {})["edits"] == "held"                                    # not applied to an ordinary puzzle yet
    assert printed_place(plain.replace("hello", "bye"), o, {})["lines"] is None              # the xd isn't the packet's kept lines
    assert printed_place(plain, {}, {}) is None
    repo, proofs = batch(tmp_path, {}, pids=(NO12,))
    assert next(r for r in record(plan(repo, proofs, RULE, "nyw-1914-c1"))["puzzles"])["printed"]["lines"] == kept


# ---- 4. a person marks a printed misprint --------------------------------------------------

def test_a_persons_misprint_mark_comes_in_from_the_site_with_their_review():
    site = {"puzzles": {"p1": {"proofs": {"oops6498": {"decision": "ready", "at": "2026-11-13T00:00:00Z", "edits": {}, "xd": "fp",
                                                       "typos": [{"key": "ev:title", "printed": "No. 5", "meant": "No. 7"}],
                                                       "key_corrections": [{"key": "cell:r1c1", "printed": "X", "corrected": "Y"}]}}}}}
    (r,) = from_site(site, [], {"p1"})
    assert r["proof"]["review"]["typos"] == [{"key": "ev:title", "printed": "No. 5", "meant": "No. 7"}]
    assert r["proof"]["review"]["key_corrections"][0]["corrected"] == "Y"


OWNER_BY = "Reviewer 2"  # the owner's own tools (via watch): kind owner


def test_a_title_the_owner_marks_printed_wrong_ships_as_printed_and_is_corrected_at_export(tmp_path):
    typo = [{"key": "ev:title", "printed": "No. 5", "meant": "No. 7"}]
    repo, _, p = shipped(tmp_path, said(OWNER_BY, "watch", {}, typos=typo), xd=XD.replace("Title: T", "Title: Cross-Word Puzzle No. 5"))
    (c,) = p["passing"][P]["corrections"]
    assert (c["fits"], c["printed"], c["meant"], c["kind"]) == ("printed", "No. 5", "No. 7", "owner")
    assert "Title: Cross-Word Puzzle No. 5" in p["passing"][P]["text"]                       # blitz ships it as printed
    doc = as_shipped(p, record(p))[P]
    assert doc["corrections"][0]["says"] == "The title is printed 'No. 5'; meant 'No. 7'." and doc["proposals"] == []
    write(repo, p, "2026-11-13")
    text, notes, rows = corrected(xd_of(repo), provenance(repo)[0]["corrections"])
    assert "Title: Cross-Word Puzzle No. 7" in text and rows[0]["done"] == "applied"
    assert notes == ["The title is printed 'No. 5'; corrected to 'No. 7'."]


# ---- C. whose marks take effect: the owner's and the AI reviewer's (the owner's rule, 2026-11-13) ----

def test_only_the_owners_and_the_ais_marks_take_effect_a_helpers_or_a_guests_wait(tmp_path):
    typo = [{"key": "ev:title", "printed": "No. 5", "meant": "No. 7"}]
    xd = XD.replace("Title: T", "Title: Cross-Word Puzzle No. 5")
    for i, (rec, extra, counts) in enumerate(((said(OWNER_BY, "watch", {}, typos=typo), (), True),
                                              (said(AI_BY, AGENT, {}, typos=typo), (CHECK,), True),
                                              (said(PERSON, SITE, {}, typos=typo), (), False),                       # a helper
                                              (said(f"a helper 3f2a ({SITE})", SITE, {}, typos=typo), (), False))):  # a guest
        _, _, p = shipped(tmp_path / str(i), rec, *extra, xd=xd, rule=Rule(ai_ready="both", marks="owner"))   # people: test_ship_whose.py
        x = p["passing"][P]
        assert "Title: Cross-Word Puzzle No. 5" in x["text"]                                    # as printed, whoever marked it
        assert bool(x["corrections"]) == counts and bool(x["proposals"]) != counts
        if not counts:
            (q,) = x["proposals"]
            assert q["status"] == "waiting for the owner" and q["says"] == "The title is printed 'No. 5'; proposed: 'No. 7'."
            row = next(r for r in record(p)["puzzles"] if r["pid"] == P)
            assert row["proposals"][0]["status"] == "waiting for the owner" and "corrections" not in row
            assert as_shipped(p, record(p))[P]["proposals"][0]["by"] == "a helper"


def test_an_ignored_accounts_marks_never_count_and_a_helpers_key_letter_waits_for_the_owner(tmp_path):
    from test_ship import _batch, OK
    rec = said(f"walkthrough test ({SITE})", SITE, {}, typos=[{"key": "ev:title", "printed": "T", "meant": "U"}])
    repo, proofs = _batch(tmp_path, {P: [rec, said(PERSON, SITE, {}, at="2026-10-23T00:00:00Z")]}, {P: OK})
    p = plan(repo, proofs, Rule(ai_ready="both", ignore=("walkthrough test",)), "b")
    assert p["passing"][P]["corrections"] == [] and p["passing"][P]["proposals"] == []        # not even a proposal
    # a helper who corrects a key letter on their own word: the letter isn't corrected in blitz; it is the owner's question
    kc = said(PERSON, SITE, {"cell:r2c2": "X"})
    kc["proof"]["review"]["key_corrections"] = [{"key": "cell:r2c2", "printed": "D", "corrected": "X", "edited": True}]
    _, _, p = shipped(tmp_path / "k", kc, rule=Rule(ai_ready="both", marks="owner"))
    row = p["rows"][0]
    assert (row["status"], row["reason"], row["queue"]) == ("held", "proposal-waits", "question") and not p["passing"]
    assert row["asks"][0]["row"] == "cell:r2c2" and "owner's word" in row["asks"][0]["text"]
    # the owner's own key correction is made, with its note
    kc = said(OWNER_BY, "watch", {"cell:r2c2": "X"})
    kc["proof"]["review"]["key_corrections"] = [{"key": "cell:r2c2", "printed": "D", "corrected": "X", "edited": True}]
    _, _, p = shipped(tmp_path / "o", kc)
    assert p["passing"][P]["edit_records"][0]["class"] == "key correction" and p["passing"][P]["notes"]


# ---- A. a marked row ships as printed; the rest of its edit is classed on its own evidence ----

def test_a_marked_row_never_ships_corrected_and_its_other_changes_keep_their_own_class(tmp_path):
    xd = XD.replace("A3. Two ~", "A3. Cockail party ~")
    typo = [{"key": "clue:A3", "printed": "Cockail", "meant": "Cocktail"}]
    # the reviewer's three ways round the mark: retyped in lowercase, typed twice, the printed word gone
    for i, edit in enumerate(("cocktail party", "Cocktail party Cocktail", "Drinks party")):
        _, _, p = shipped(tmp_path / str(i), said(OWNER_BY, "watch", {"clue:A3": edit}, typos=typo), xd=xd)
        row = p["rows"][0]
        assert (row["reason"], row["queue"]) == ("misprint-edit", "broken") and not p["passing"], edit
        assert "doesn't keep the printed “Cockail” once" in row["why"]
    # the words meant typed once in place of the printed ones: they go back as printed; the edit is unclassed
    _, _, p = shipped(tmp_path / "back", said(OWNER_BY, "watch", {"clue:A3": "Cocktail parties"}, typos=typo), xd=xd)
    x = p["passing"][P]
    assert "A3. Cockail parties ~" in x["text"] and x["edit_records"][0]["class"] == "unclassed" and "classed_by" not in x["edit_records"][0]
    # a second word changed beside a mark on another: the mark doesn't make it a reading fix
    typo2 = [{"key": "clue:A3", "printed": "party", "meant": "parti"}]
    _, _, p = shipped(tmp_path / "other", said(OWNER_BY, "watch", {"clue:A3": "Cocktail party"}, typos=typo2), xd=xd)
    (e,) = p["passing"][P]["edit_records"]
    assert "A3. Cocktail party ~" in p["passing"][P]["text"] and e["class"] == "unclassed"
    # with a comment on the row it is a reading fix, as any edit is
    _, _, p = shipped(tmp_path / "said", said(OWNER_BY, "watch", {"clue:A3": "Cocktail party"}, [("clue:A3", "The scan reads Cocktail.")],
                                              typos=typo2), xd=xd)
    assert p["passing"][P]["edit_records"][0]["class"] == "reading"


def test_a_helpers_or_a_guests_marked_row_ships_as_printed_too(tmp_path):
    """The second pass's probe: a helper marks "Cockail" as meaning "Cocktail" and edits the clue to "Cocktail party". Their
    own mark says the edit corrects the print, which blitz never ships, whoever makes it: the words go back as printed,
    and the correction still waits for the owner."""
    xd = XD.replace("A3. Two ~", "A3. Cockail party ~")
    typo = [{"key": "clue:A3", "printed": "Cockail", "meant": "Cocktail"}]
    for i, who in enumerate((PERSON, f"a helper 3f2a ({SITE})")):                              # a helper, a guest
        _, _, p = shipped(tmp_path / str(i), said(who, SITE, {"clue:A3": "Cocktail party"}, typos=typo), xd=xd,
                          rule=Rule(ai_ready="both", marks="owner"))
        x = p["passing"][P]
        assert "A3. Cockail party ~" in x["text"] and x["edit_records"] == [] and x["corrections"] == []
        assert x["proposals"][0]["status"] == "waiting for the owner"
        # and the same edit with another word read again: that ships, unclassed; the misprint stays as printed
        _, _, p = shipped(tmp_path / f"m{i}", said(who, SITE, {"clue:A3": "Cocktail parties"}, typos=typo), xd=xd)
        (e,) = p["passing"][P]["edit_records"]
        assert "A3. Cockail parties ~" in p["passing"][P]["text"] and e["class"] == "unclassed"
        # an edit that loses the printed words holds the puzzle, as the owner's does
        _, _, p = shipped(tmp_path / f"h{i}", said(who, SITE, {"clue:A3": "cocktail party"}, typos=typo), xd=xd)
        assert p["rows"][0]["reason"] == "misprint-edit" and not p["passing"]


def test_a_guests_malformed_mark_is_dropped_with_a_note_and_holds_nothing(tmp_path):
    bad = [{"key": "clue:A3", "printed": "Two", "meant": "Tw\to"}]
    _, _, p = shipped(tmp_path, said(f"a helper 3f2a ({SITE})", SITE, {}, typos=bad))
    x = p["passing"][P]
    (q,) = x["proposals"]
    assert (q["status"], q["what"]) == ("not taken", "malformed") and "tab" in q["says"] and x["corrections"] == []
    assert next(r for r in record(p)["puzzles"] if r["pid"] == P)["proposals"][0]["status"] == "not taken"
    # the owner's malformed mark still holds
    _, _, p = shipped(tmp_path / "o", said(OWNER_BY, "watch", {}, typos=bad))
    assert p["rows"][0]["reason"] == "mark-invalid"


# ---- B. a mark or an edit that a clue or header can't hold ----------------------------------

def test_a_malformed_mark_holds_the_puzzle_and_never_reaches_the_export(tmp_path):
    xd = XD.replace("A3. Two ~", "A3. Cockail party ~")
    for i, (bad, says) in enumerate((({"key": "clue:A3", "printed": "Cockail", "meant": "Cock\ntail"}, "line break"),
                                     ({"key": "clue:A3", "printed": "Cockail", "meant": "Cock\ttail"}, "tab"),
                                     ({"key": "clue:A3", "printed": "Cockail", "meant": "x" * 201}, "over 200"),
                                     ({"key": "clue:A3", "printed": "Mocktail", "meant": "Cocktail"}, "isn't in the row's text"),
                                     ({"key": "clue:Z9", "printed": "a", "meant": "b"}, "names no clue"))):
        _, _, p = shipped(tmp_path / str(i), said(OWNER_BY, "watch", {}, typos=[bad]), xd=xd)
        row = p["rows"][0]
        assert (row["reason"], row["queue"]) == ("mark-invalid", "broken") and says in row["why"] and not p["passing"], says
    # the export never applies one, whatever an old provenance row says, and its corrections.tsv keeps one row per line
    text, notes, rows = corrected(xd, [{"key": "clue:A3", "printed": "Cockail", "meant": "Cock\ttail", "by": "x\ty"}])
    assert text == xd and notes == [] and rows[0]["done"] == "not applied"


def test_a_clue_or_header_edit_with_a_line_break_or_a_tab_is_refused_at_import(tmp_path):
    for i, (k, v) in enumerate((("clue:A3", "Two\nthree"), ("clue:A3", "Two\tthree"), ("meta:title", "A\tB"))):
        _, _, p = shipped(tmp_path / str(i), said(OWNER_BY, "watch", {k: v}))
        assert p["rows"][0]["reason"] == "edits-unapplied" and k in p["rows"][0]["why"] and not p["passing"]
    xd, ocr, review = packet(NO7)
    assert "tab" in apply_linked(xd, {"line:B4": "a\tb"}, ocr, review)[2][0]
    assert "isn't one line" in apply_linked(xd, {"clue:A6": "a\tb"}, ocr, review)[2][0]


# ---- 5. a printed line with a paragraph break, end to end ----------------------------------

def test_a_paragraph_break_in_a_printed_line_reaches_the_xd_the_record_and_the_export(tmp_path):
    xd, ocr, review = packet(NO7)
    edits = dict(LEDGER[NO7]["proof"]["review"]["edits"])
    first, _, rest = edits["line:B4"].partition(". ")
    edits["line:B4"] = first + ".\n" + rest                                                  # as the edit box saves Shift+Enter
    text, done, cant = apply_linked(xd, edits, ocr, review)
    assert cant == [] and "line:B4" in done
    block = text.split("Printed with puzzle:\n")[1].split("\n\n")[0].split("\n")
    assert block == [first + ".", rest]                                                       # two lines of the xd's block
    rec = json.loads(json.dumps(LEDGER[NO7]))
    rec["proof"]["review"]["edits"] = edits
    e = edit_records(xd, text, [rec], RULE, NO7, ocr, review)
    assert e["missing"] == [] and next(r for r in e["records"] if r["key"] == "line:B4")["after"] == edits["line:B4"]
    printed = _printed(ocr, review, edits)
    assert printed[0]["text"] == edits["line:B4"]
    gxd = to_gxd(text, [x["text"] for x in printed])
    assert first + ".\n" + rest in gxd                                                        # the export's notes keep the break
