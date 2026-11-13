"""What a person can check before the import (design/ship.md, "The xd as it will ship"): the exact xd ship would write,
recorded beside the ship record with its edit records; where the packet's printed lines land in the xd (for the proof
page's preview of the notes); a person's own "printed this way, but wrong" (typos / key_corrections from the proof
page), which ships the text as printed and is corrected at the gxd export; and a printed line with a paragraph break,
end to end.

Run with: uv run --with pytest --extra site pytest tests/test_ship_preview.py"""

import json

from blitz.ship import (AS_SHIPPED, SITE, _printed, apply_linked, as_shipped, corrected, edit_records, from_site, plan,
                        printed_place, provenance, record, to_gxd, write, write_record)
from test_ship_edits import BOTH, P, PERSON, said, shipped, xd_of
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


def test_a_title_marked_printed_wrong_ships_as_printed_and_is_corrected_at_export(tmp_path):
    typo = [{"key": "ev:title", "printed": "No. 5", "meant": "No. 7"}]
    from test_ship import XD
    repo, _, p = shipped(tmp_path, said(PERSON, SITE, {}, typos=typo), xd=XD.replace("Title: T", "Title: Cross-Word Puzzle No. 5"))
    (c,) = p["passing"][P]["corrections"]
    assert (c["fits"], c["printed"], c["meant"]) == ("printed", "No. 5", "No. 7")
    assert "Title: Cross-Word Puzzle No. 5" in p["passing"][P]["text"]                       # blitz ships it as printed
    doc = as_shipped(p, record(p))[P]
    assert doc["corrections"][0]["says"] == "The title is printed 'No. 5'; meant 'No. 7'." and doc["corrections"][0]["by"] == "a helper"
    write(repo, p, "2026-11-13")
    text, notes, rows = corrected(xd_of(repo), provenance(repo)[0]["corrections"])
    assert "Title: Cross-Word Puzzle No. 7" in text and rows[0]["done"] == "applied"
    assert notes == ["The title is printed 'No. 5'; corrected to 'No. 7'."]


def test_a_persons_edit_beside_their_own_mark_is_a_reading_not_unclassed(tmp_path):
    # the reviewer fixed a misread word in the clue and marked another word as the print's mistake
    typo = [{"key": "clue:A3", "printed": "Two", "meant": "Too"}]
    repo, _, p = shipped(tmp_path, said(PERSON, SITE, {"clue:A3": "Two more"}, typos=typo))
    (e,) = p["passing"][P]["edit_records"]
    assert e["class"] == "reading" and "misprint entry" in e["classed_by"]
    # an AI's edit with no comment is still unclassed: its mark doesn't speak for the rest of the edit
    from test_ship_edits import AI_BY
    from blitz.ship import AGENT
    from test_ship import CHECK
    repo, _, p = shipped(tmp_path / "ai", said(AI_BY, AGENT, {"clue:A3": "Two more"}, typos=typo), CHECK)
    assert p["passing"][P]["edit_records"][0]["class"] == "unclassed"


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
