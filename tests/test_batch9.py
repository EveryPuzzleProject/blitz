"""Tool fixes from the Judge batch 9 review. Every case is a real one from the reviewers' notes
(harvests/judge/tasks-batch9/feedback.md in xword-ocr); the puzzle ids are in the test names or comments.

Run with: uv run --with pytest pytest"""

import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image

from blitz.crops import make_sheets
from blitz.packet import (heading_start, is_notice, last_in_column, list_continues, number_cut_off, number_grid,
                          proposals, proposed_text, route, spell_doubt, structural_checks, tail_number_hint,
                          text_view, title_check)
from blitz.review import choose_targets, covered, finish


def _col(texts, x0=825, flags=None):
    """One column of clue boxes, top to bottom: {label: clue}."""
    return {k: {"text": t, "box": [x0, 100 + 12 * i, x0 + 200, 112 + 12 * i], **({"flags": flags[k]} if flags and k in flags else {})}
            for i, (k, t) in enumerate(texts.items())}


def _ocr(clues, **extra):
    o = {"xdid": "judge1930-01-04", "grid": ["...", "...", "..."], "clues": clues, "title": "Judge's Crossword Puzzle No. 1"}
    o.update(extra)
    return o


# --- 1. page numbers and "Solution of ..." headings run into the last clue of a column ---

def test_page_number_after_the_last_down_clue_is_taken_off():  # judge1930-01-04 D11
    o = _ocr(_col({"D9": "Stop.", "D10": "Go.", "D11": "Runaway. 30"}))
    assert last_in_column(o, "D11") and not last_in_column(o, "D9")
    text, notes = proposed_text(o, "D11")
    assert text == "Runaway." and "page number" in notes[0]


def test_page_number_in_the_middle_of_a_column_is_left_alone():
    o = _ocr(_col({"D9": "Born in 1900. 30", "D10": "Go."}))
    assert proposed_text(o, "D9") == ("Born in 1900. 30", [])


def test_two_numbers_and_quotes_judge1930_09_20_and_1929_12_28():
    o = _ocr(_col({"D66": "Near.", "D67": "Toward. 300 30"}))
    assert proposed_text(o, "D67")[0] == "Toward."
    o = _ocr(_col({"A86": "Eh.", "A87": 'Man\'s name, meaning "rock." 30'}))
    assert proposed_text(o, "A87")[0] == 'Man\'s name, meaning "rock."'


def test_a_bare_number_without_a_sentence_end_is_flagged_not_cut():  # judge1930-02-08 A73
    o = _ocr(_col({"A72": "Eh.", "A73": "This is what dad calls 30"}))
    assert proposed_text(o, "A73")[1] == []
    assert "page number" in tail_number_hint(o, "A73")


def test_solution_heading_and_garbled_repeat_are_taken_off():
    # judge1930-03-15 D59
    o = _ocr(_col({"D58": "Eh.", "D59": "A hot potato (abbr.). 39. A not potato (abbr.). Solution of Last Week's Puzzle"}))
    text, notes = proposed_text(o, "D59")
    assert text == "A hot potato (abbr.)." and len(notes) == 2
    # judge1932-08-01b D63 (a different heading), judge1934-12-01b D71 (garbled)
    for raw, want in (("Stop here. Solution of Puzzle No. 267", "Stop here."),
                      ("Any old thing will do for this. Solrtion ofPuarle Ne 281", "Any old thing will do for this."),
                      ("A big Suieker. Solution of Last Week's Puzzle", "A big Suieker.")):
        assert proposed_text(_ocr(_col({"D1": "Eh.", "D2": raw})), "D2")[0] == want


def test_a_clue_that_is_only_the_heading_is_not_emptied():  # judge1930-04-26 D68
    o = _ocr(_col({"D67": "Eh.", "D68": "Solution of Last Week's Puzzle"}))
    assert proposed_text(o, "D68") == ("Solution of Last Week's Puzzle", [])


def test_a_real_clue_with_the_word_solution_is_not_cut():
    o = _ocr(_col({"D1": "Solution of a problem in algebra", "D2": "Eh."}))
    assert proposed_text(o, "D1")[1] == []
    assert heading_start("Solution of a problem in algebra", last=False) is None


def test_a_garbled_number_is_not_mistaken_for_a_word_in_the_repeat():  # judge1929-05-18 D70
    o = _ocr(_col({"D69": "Eh.", "D70": "Don't do this when you see red. 70. Don't do this when yod see red. "
                                         "Solution of Last Week's Puzzle SPAGHETTI"}))
    assert proposed_text(o, "D70")[0] == "Don't do this when you see red."


def test_a_broken_clue_number_read_as_a_euro_sign_is_taken_off():
    # judge1934-12-01 A66, judge1936-04-01 A26, judge1935-07-01 D60, judge1934-12-01b D56, judge1934-02-01b A70
    for raw, want in (("€6. A Port you'd love to touch.", "A Port you'd love to touch."),
                      ("€. This was ever thus.", "This was ever thus."),
                      ("€0. If this goes far enough, it will achieve anonymousness.",
                       "If this goes far enough, it will achieve anonymousness."),
                      ("5€. A. water duck (old spelling).", "A. water duck (old spelling)."),
                      ("θ. The man you love to hate.", "The man you love to hate.")):
        assert proposed_text(_ocr(_col({"A1": "Eh.", "A2": raw})), "A2")[0] == want
    assert proposed_text(_ocr(_col({"A1": "5 percent. Of what."})), "A1")[1] == []


def test_text_md_shows_the_proposal_and_says_so():
    o = _ocr(_col({"D10": "Go.", "D11": "Runaway. 30"}))
    t = text_view(o)
    assert "D11" in t and "Runaway.  [" in t and "removed the page number '30'" in t
    assert "Runaway. 30" not in t and "the tools' proposal" in t


# --- 2. a clue list that goes on in a page the packet lacks ---

def _wide(n_text, across_text=True):
    """A 25x25 grid with 13 Across and 13 Down entries; the first n_text Down clues have text."""
    grid = ["".join("#" if r % 2 and c % 2 else "." for c in range(25)) for r in range(25)]
    labels = [e[0] for e in number_grid(grid)]
    clues = {k: {"text": f"clue {k}.", "box": [800, 100 + i, 1000, 112 + i]} for i, k in enumerate(labels)
             if k[0] == "A" or int(k[1:]) <= n_text}
    for k in labels:
        if k[0] == "D" and k not in clues:
            clues[k] = {"text": "", "box": None, "flags": ["missing"]}
    return _ocr(clues, grid=grid, answers=None)


def test_a_down_list_that_stops_early_is_a_list_continuing_elsewhere():  # the 15 escalated 1930 puzzles
    o = _wide(3)
    found = list_continues(o)
    assert list(found) == ["D"] and "only 3 of 13" in found["D"]
    checks = structural_checks(o)
    assert "clue list continues on another page" in checks
    assert "clue text missing" not in checks  # said once, above, not as a list of 8 clue numbers
    assert route(o)[0] == "full" and route(o)[1][0].startswith("clue list continues on another page")
    assert "- clue list continues on another page: Down: only 3 of 13" in text_view(o)


def test_a_few_missing_clues_are_not_a_continuation():
    o = _wide(13)
    for k in [k for k in o["clues"] if k[0] == "D"][:3]:
        o["clues"][k]["text"] = ""
    assert list_continues(o) == {}
    assert "clue text missing" in structural_checks(o)


# --- 3. title ---

def test_titles_that_picked_up_a_neighbouring_heading_are_suspect():
    for title, proposed in (("Judge's Crossword Puzzle No. 146 Horizontal", "Judge's Crossword Puzzle No. 146"),
                            ("Let us mail Judge's Crossword Puzzle No. 148", "Judge's Crossword Puzzle No. 148"),
                            ("The Judge's Crossword Puzzle No. 398 ANSWERS TO", "The Judge's Crossword Puzzle No. 398"),
                            ("Judge's Crossword Puzzle No. 172 These spin rattling good tails. Horizontal",
                             "Judge's Crossword Puzzle No. 172")):
        why, got = title_check(_ocr({}, title=title))
        assert got == proposed and "extra words" in why
    assert title_check(_ocr({}, title="ARE YOU SURE?", xdid="judge1938-03-01"))[1] == ""


def test_clean_titles_and_other_publications_are_not_questioned():
    for title in ("Judge's Crossword Puzzle No. 146", "The Judge's Crossword Puzzle No. 396", "Judge's . Crossword Puzzle No. 218",
                  "Judge's Crossword No. 162", "Judge's Crossword Puzzle 334"):
        assert title_check(_ocr({}, title=title)) is None
    assert title_check(_ocr({}, title="Anything at all", xdid="games1978-01")) is None


def test_a_suspect_title_adds_the_page_top_crop_and_says_so():
    o = _ocr({}, title="Judge's Crossword Puzzle No. 146 Horizontal")
    assert "meta:top" in choose_targets(o, [])
    assert "meta:top" not in choose_targets(_ocr({}), [])
    assert "[suspect: extra words" in text_view(o)


def test_meta_top_is_a_band_across_the_page(tmp_path):
    o = _ocr({}, meta_boxes={"title": [200, 300, 900, 340]})
    d = tmp_path / o["xdid"]
    d.mkdir()
    (d / "ocr.json").write_text(json.dumps(o))
    Image.new("L", (1200, 1600), 255).save(d / "page.jpg")
    made = make_sheets(d, ["meta:top"])
    assert made["missed"] == [] and made["sheets"][0]["crops"] == ["meta:top"]
    assert Image.open(made["sheets"][0]["file"]).width == 1000  # the whole page width, scaled to the sheet


# --- 4. the recurring notice ---

def test_the_recurring_notice_is_recognised_however_it_was_read():
    for t in ("Judge pays $10 for each puzzle printed.", "Judge pays $10 for each puzzle printed", "Judje pays $10 for each puzzle printed.",
              "Juige pays $10 for each puzzle printed.", "Judge pays $10 for each puzzte printed.",
              "Judge pays $10 for each·puzzle printed.", "Judge paye $10 for each puzle printed."):
        assert is_notice(t), t
    for t in ("Before Reading Judge", "technical even for the bridge player.", "G0. These must be in unusual shape in order to"):
        assert not is_notice(t), t


def test_the_notice_is_no_crop_and_finish_removes_it():
    o = _ocr({}, captions={"1": "Judge pays $10 for each puzzle printed."})
    assert "caption:1" not in choose_targets(o, [])
    assert "caption:1" in choose_targets(o, ["caption:1"])  # still there when asked for
    assert "recurring notice" in text_view(o)
    review, _ = finish(o, {"ready": True}, [])
    assert review["corrections"] == {"other:1": ""}
    kept, _ = finish(_ocr({}, captions={"1": "Before Reading Judge"}), {"ready": True}, ["caption:1"])
    assert kept["corrections"] == {}


# --- 5. number-missing that is only a box starting right of the number ---

def test_number_missing_where_the_box_starts_right_of_the_number():  # judge1930-03-08 A57/A59/A61 and D1-D7
    clues = _col({"A53": "Burglars.", "A55": "Eh.", "A57": "A small island.", "A62": "Old."})
    clues["A57"]["flags"] = ["number-missing"]
    clues["A57"]["box"][0] = 849  # the others start at 825
    o = _ocr(clues)
    assert number_cut_off(o, "A57")
    t = text_view(o)
    assert "A57" in t and "[number-cut-off]" in t
    clues["A57"]["box"][0] = 827  # starts where the others do: a real doubt
    assert not number_cut_off(o, "A57") and "[number-missing]" in text_view(o)


# --- 6. the spell step ---

def test_spell_fixes_to_real_words_are_doubted_but_the_broken_c_is_not():
    for flag in ("spell:dratted>drafted", "spell:Haled>Hated", "spell:middie>middle", "spell:farn>fam", "spell:ycu>yen"):
        assert spell_doubt(flag), flag
    for flag in ("spell:elean>clean", "spell:Seoteh>Scotch", "spell:colleetor>collector", "spell:eatch>catch"):
        assert not spell_doubt(flag), flag
    o = _ocr({"A51": {"text": "Something we wish our neighbor would do to that drafted piano.", "box": [1, 1, 9, 9],
                      "flags": ["spell:dratted>drafted"]}})
    assert "(spell-doubt)" in text_view(o) and "spell:dratted>drafted (spell-doubt)" in text_view(o)


# --- 7. finish ---

def test_finish_puts_the_proposal_in_the_review_unless_the_reviewer_wrote_the_clue():
    o = _ocr({**_col({"D10": "Go.", "D11": "Runaway. 30"}), **_col({"D19": "Eh.", "D20": "Stop. 30"}, x0=1200)})
    seen = ["clue:D11", "clue:D20"]
    review, _ = finish(o, {"ready": True}, seen)
    assert review["corrections"] == {"clue:D11": "Runaway.", "clue:D20": "Stop."}
    assert review["from_text_md"] == ["clue:D11", "clue:D20"]
    own, _ = finish(o, {"ready": True, "corrections": {"clue:D11": "Run away."}}, seen)
    assert own["corrections"]["clue:D11"] == "Run away."
    typed, _ = finish(o, {"ready": True, "corrections": {"clue:D11": "Runaway. 30"}}, seen)  # their own text, junk left in
    assert typed["junk_left"]["D11"]
    unseen, _ = finish(o, {"ready": True}, [])
    assert "clue:D11" in unseen["unsure"] and "clue:D11" not in unseen["corrections"]


def test_finish_says_when_the_title_is_still_wrong():
    o = _ocr({}, title="Judge's Crossword Puzzle No. 146 Horizontal")
    review, _ = finish(o, {"ready": True}, [])
    assert review["title_left"]["probably"] == "Judge's Crossword Puzzle No. 146"
    fixed, _ = finish(o, {"ready": True, "corrections": {"meta:title": "Judge's Crossword Puzzle No. 146"}}, [])
    assert "title_left" not in fixed and fixed["corrections"]["meta:title"] == "Judge's Crossword Puzzle No. 146"


# a box: crop that shows where the clue really is (judge1938-04-01 D65, judge1938-08-01b D56/D57/D60, judge1939-01-01 A5/D2)
def _shifted():
    return _ocr({
        "D55": {"text": "La Boheme and The Bohemian Girl are the", "box": [799, 310, 1093, 386], "flags": ["number-corrected:11"]},
        "D56": {"text": "an unlimited number (He could knock unca", "box": [800, 395, 1094, 472], "flags": ["number-corrected:16"]},
        "D58": {"text": "", "box": None, "flags": ["missing"]},
        "D54": {"text": "A town with a strange leaning.", "box": [494, 1372, 712, 1435]},
        "D51": {"text": "Fork's fingers.", "box": [495, 1340, 608, 1359]}})


def test_a_box_crop_of_where_a_misplaced_clue_really_is_counts():
    o = _shifted()
    seen = ["box:490,1105,795,1160"]  # the clue page's true place for D56: the OCR box is in another column
    assert covered("clue:D56", seen, o)  # flagged number-corrected: the OCR's box can't be trusted
    assert covered("clue:D58", seen, o)  # never found: any box crop is the evidence
    assert not covered("clue:D54", seen, o)  # a clue the OCR placed and trusted: only its own place counts
    assert covered("clue:D54", ["box:490,1360,800,1440"], o)
    assert not covered("clue:D56", ["box:10,10,300,3000"], o)  # not clue-sized
    assert not covered("clue:D56", ["box:0,0,10,10"], o)  # not where clues are


def test_the_reviewer_can_say_where_the_clue_is():
    o = _shifted()
    o["clues"]["D54"]["flags"] = []
    assert not covered("clue:D54", ["box:100,100,300,120"], o)
    assert covered("clue:D54", ["box:490,1105,795,1160"], o, {"clue:D54": [500, 1110, 790, 1150]})


def test_finish_applies_a_correction_seen_only_on_a_box_crop():
    o = _shifted()
    review, _ = finish(o, {"ready": True, "corrections": {"clue:D56": "Callous soloist."}}, ["box:490,1105,795,1160"])
    assert review["corrections"] == {"clue:D56": "Callous soloist."} and review["unsure"] == {}


# --- 8. sheets: no repeated warnings; auto-added clues need a box ---

def test_boxless_clues_are_not_auto_added_and_missing_crops_are_told_once(tmp_path, capsys):
    from blitz import cli

    o = _ocr({"D10": {"text": "", "box": None, "flags": ["missing"]}}, meta_boxes={"title": [10, 10, 100, 30]})
    assert choose_targets(o, []) == ["meta:title", "meta:byline"]
    d = tmp_path / o["xdid"]
    d.mkdir()
    (d / "ocr.json").write_text(json.dumps(o))
    Image.new("L", (400, 400), 255).save(d / "page.jpg")
    cli.main(["sheets", str(d)])
    first = capsys.readouterr().out
    assert first.count("no box for meta:byline") == 1
    cli.main(["sheets", str(d), "clue:D10", "clue:D11"])
    second = capsys.readouterr().out
    assert "meta:byline" not in second and "clue:D10, clue:D11" in second


# --- 9. printing to a Windows console ---

def test_feedback_survives_a_cp1252_console(tmp_path):  # judge1934-02-01b: the theta in a reviewer's note
    d = tmp_path / "judge1934-02-01b"
    d.mkdir()
    (d / "review.json").write_text(json.dumps(
        {"tool_notes": [{"kind": "other", "target": "clue:A70", "note": "a stray 'θ.' prefixed to the clue"}]}))
    r = subprocess.run([sys.executable, "-m", "blitz.cli", "feedback", str(tmp_path)], capture_output=True,
                       env={**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"})
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    assert "θ".encode("utf-8") in r.stdout


def test_consensus_agreed_disputed_single_none():
    from blitz.site import consensus

    assert consensus({}, {})["agreement"] == "none"
    assert consensus({"a": "looks-right"}, {})["agreement"] == "single"
    two = consensus({"a": "looks-right", "b": "looks-right"}, {"clue:A1": {"a": "accept", "b": "accept"}})
    assert two == {"eyes": 2, "agreement": "agreed", "conflicts": []}
    # one helper rejects a change the other accepted: disputed, and the change is named
    d = consensus({"a": "looks-right", "b": "looks-right"}, {"clue:A1": {"a": "accept", "b": "reject"}})
    assert d["agreement"] == "disputed" and d["conflicts"] == ["clue:A1"]
    # any needs-work is disputed, even from a single helper
    assert consensus({"a": "needs-work"}, {})["agreement"] == "disputed"
    assert consensus({"a": "looks-right", "b": "needs-work"}, {})["agreement"] == "disputed"
    # a lone reject with no one to disagree is not a conflict
    assert consensus({"a": "looks-right", "b": "looks-right"}, {"clue:A1": {"a": "reject"}})["agreement"] == "agreed"
