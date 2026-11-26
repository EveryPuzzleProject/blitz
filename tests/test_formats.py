"""blitz check-format: a proof packet against formats/proof-packet.md."""

import json
from pathlib import Path

import pytest
from PIL import Image

from blitz import formats

XD = "Title: A test\nAuthor: A. Setter\nDate: 1930-01-04\nSource: https://example.org/scan\n\n\nCAT\nA#O\nBAT\n\n\nA1. A pet. ~ CAT\n"


def make(tmp: Path, name: str = "test1930-01-04") -> Path:
    """The smallest packet today's writers make: every field the format requires, nothing more."""
    d = tmp / name
    (d / "_src").mkdir(parents=True)
    for img in ("page.jpg", "grid.png", "answers.png"):
        Image.new("L", (8, 8), 255).save(d / img)
    ocr = {"xdid": name, "source": "https://example.org/scan", "title": "A test", "author": "A. Setter",
           "byline": "by A. Setter", "puzzle_number": "", "editor": "", "feature": "", "issue_date": "1930-01-04",
           "grid": ["...", ".#.", "..."], "answers": ["CAT", "A#O", "BAT"], "answers_low_confidence": ["r1c2"],
           "grid_asymmetric_squares": [], "clue_image": "page.jpg", "scales": {"page.jpg": 0.5},
           "clues": {"A1": {"text": "A pet.", "box": [1, 2, 3, 4]}},
           "lines": [{"n": 1, "text": "A test", "box": [1, 1, 5, 2], "keep": False, "label": "other", "by": "rule"}],
           "evidence": {"title": 1}, "metadata": [{"id": "M1", "name": "Issue date", "value": "1930-01-04"}]}
    review = {"ready": True, "model": "AI reviewer", "reviewer": "AI reviewer", "reviewer_line": "AI reviewer",
              "corrections": {}, "confirm": [], "sic": {}, "unsure": {}, "note": "", "verdict": "", "requests": [],
              "findings": [], "blanks": {}, "tool_notes": [], "matches_xd": True,
              "xd_fp": formats.puzzle_fingerprint(XD), "xd_fp_same": []}
    (d / "puzzle.xd").write_text(XD, encoding="utf-8")
    (d / "ocr.json").write_text(json.dumps(ocr), encoding="utf-8")
    (d / "review.json").write_text(json.dumps(review), encoding="utf-8")
    return d


def edit(d: Path, name: str, fn) -> None:
    v = json.loads((d / name).read_text(encoding="utf-8"))
    fn(v)
    (d / name).write_text(json.dumps(v), encoding="utf-8")


def problems(d: Path) -> list[str]:
    return [t for lv, t in formats.check_packet(d) if lv == "problem"]


def test_a_whole_packet_passes(tmp_path):
    d = make(tmp_path)
    assert formats.check_packet(d) == []
    assert formats.check([tmp_path])["packets"] == 1


def test_process_headers_are_not_the_version(tmp_path):
    # Source says how the puzzle was made: changing it leaves xd_fp, and the packet, good
    d = make(tmp_path)
    (d / "puzzle.xd").write_text(XD.replace("example.org/scan", "example.org/other"), encoding="utf-8")
    assert problems(d) == []


def test_an_xd_the_packet_does_not_show(tmp_path):
    d = make(tmp_path)
    (d / "puzzle.xd").write_text(XD.replace("A pet.", "A feline."), encoding="utf-8")
    assert any("doesn't show its xd" in t for t in problems(d))


@pytest.mark.parametrize("name, fn, says", [
    ("ocr.json", lambda v: v.pop("clues"), "no 'clues'"),
    ("ocr.json", lambda v: v.update(grid=["...", ".#"]), "rows differ in length"),
    ("ocr.json", lambda v: v.update(grid=["..x", ".#.", "..."]), "'grid' has 'x'"),
    ("ocr.json", lambda v: v.update(answers=["CAT", "A#O"]), "answers are 2x3, the grid 3x3"),
    ("ocr.json", lambda v: v["clues"]["A1"].update(box=[1, 2, 3]), "box is not four numbers"),
    ("ocr.json", lambda v: v["clues"]["A1"].update(image="clue_page.jpg"), "clue_page.jpg: named in ocr.json"),
    ("ocr.json", lambda v: v.update(answers_low_confidence=["A1"]), "not a square like r3c5"),
    ("ocr.json", lambda v: v.update(format="proof-packet/9"), "is not one this check knows"),
    ("review.json", lambda v: v.update(ready="yes"), "'ready' is str, not bool"),
    ("review.json", lambda v: v.pop("xd_fp"), "no 'xd_fp'"),
    ("review.json", lambda v: v.update(unsure=[]), "'unsure' is list, not dict"),
])
def test_what_breaks_a_reader_is_a_problem(tmp_path, name, fn, says):
    d = make(tmp_path)
    edit(d, name, fn)
    assert any(says in t for t in problems(d)), problems(d)


def test_what_older_packets_lack_is_a_note(tmp_path):
    d = make(tmp_path)
    edit(d, "review.json", lambda v: v.pop("reviewer"))
    (d / "grid.png").unlink()
    got = formats.check_packet(d)
    assert [lv for lv, _ in got] == ["note", "note"]


def test_the_asymmetric_squares_are_pairs(tmp_path):
    d = make(tmp_path)
    edit(d, "ocr.json", lambda v: v.update(grid_asymmetric_squares=["r1c2/r3c2"]))
    assert problems(d) == []


def test_the_older_task_form(tmp_path):
    # xword-ocr task-packets (Judge): no puzzle.xd, no lines or headers table; valid, and said
    d = make(tmp_path)
    (d / "puzzle.xd").unlink()
    edit(d, "ocr.json", lambda v: [v.pop(k) for k in ("lines", "evidence", "metadata", "editor", "feature",
                                                     "issue_date", "puzzle_number")])
    edit(d, "review.json", lambda v: [v.pop(k) for k in ("xd_fp", "xd_fp_same", "reviewer", "reviewer_line",
                                                        "verdict", "requests", "findings", "blanks")])
    got = formats.check_packet(d)
    assert [lv for lv, _ in got] == ["note"] and "older task form" in got[0][1]


def test_checks_json(tmp_path):
    d = make(tmp_path)
    fp = formats.puzzle_fingerprint(XD)
    (d / "checks.json").write_text(json.dumps({"xd_fp": fp, "decision": "ready", "ship": {"ok": True, "findings": [],
                                   "incomplete": [], "xd_fp": fp}, "items": [{"key": "grid", "what": "x", "from": "triage"}]}))
    assert formats.check_packet(d) == []
    edit(d, "checks.json", lambda v: v["items"].append({"key": "grid"}))
    assert any("items[1]" in t for t in problems(d))


def _ai(by, model, answer, comments, edits=None, second_opinion=None):
    review = {"edits": edits or {}, "comments": comments, "status": {}, "note": "", "xd": "fp"}
    if second_opinion is not None:
        review["second_opinion"] = second_opinion
    return {"record": "proof:p", "ledger": "games/fixes/decisions.jsonl", "by": by, "model_id": model, "answer": answer,
            "note": "", "at": "2026-11-25T10:00:00Z", "xd_fp": "fp", "review": review}


def test_ai_review_json_the_kind_of_each_flag_and_the_second_opinion(tmp_path):
    d = make(tmp_path)
    first_by, second_by = "Claude (AI proof reviewer, claude-opus-5-5)", "Claude (AI proof reviewer, claude-sonnet-5-5)"
    flag = {"key": "grid", "text": "Flag for the maintainer: r1c2 is O in the key. Change r1c2 to O?", "kind": "grid-reading"}
    first = _ai(first_by, "claude-opus-5-5", "notready", [flag])
    first["second"] = _ai(second_by, "claude-sonnet-5-5", "ready", [], {"cell:r1c2": "O"},
                          {"of": first_by, "of_at": "2026-11-25T10:00:00Z", "of_answer": "notready",
                           "of_flags": [{"key": "grid", "kind": "grid-reading"}],
                           "settles": [{"key": "grid", "kind": "grid-reading", "edit": {"cell:r1c2": "O"}}]})
    (d / "ai_review.json").write_text(json.dumps(first), encoding="utf-8")
    assert formats.check_packet(d) == []
    # a flag with no kind: a review from before kinds, said in a note
    edit(d, "ai_review.json", lambda v: v["review"]["comments"][0].pop("kind"))
    assert [t for lv, t in formats.check_packet(d) if lv == "note"] == ["ai_review.json: no flag has a kind (a review from before kinds: it holds the puzzle)"]
    # a kind not in the set; a second opinion on the first's model; a settle naming an edit the review doesn't make
    edit(d, "ai_review.json", lambda v: v["review"]["comments"][0].update(kind="a hunch"))
    edit(d, "ai_review.json", lambda v: v["second"].update(model_id="claude-opus-5-5"))
    edit(d, "ai_review.json", lambda v: v["second"]["review"]["edits"].update({"cell:r1c2": "Q"}))
    said = problems(d)
    assert any("kind 'a hunch'" in t for t in said) and any("on the first's model" in t for t in said)
    assert any("settles[0] names an edit the review doesn't make" in t for t in said)


def test_nothing_here(tmp_path):
    assert formats.check([tmp_path])["problems"] == 1


# ---- the annotated xd

FIELD = """## Metadata
Title: A test
Author: A. Seter
Author-Correction: A. Setter
Date: 1914-01-04
Description: A small square.
Source: A Paper, 1914-01-04, p. 3


## Printed
heading: A TEST
heading (left of grid): Can You
solution caption: Last week's answer


## Grid
CAT
A#O
BAT


## Clues
A1. A pet ~ CAT
A1 ^Printed: 1-2
A1 ^Fits: 1-3
A1 ^Correction: A pet.
D1. A taxi. ~ CAB
D1 ^Answer-Correction: CAR
"""


def xd_problems(text: str) -> list[str]:
    return [t for lv, t in formats.check_xd(text) if lv == "problem"]


def test_the_field_form_passes():
    assert formats.xd_form(FIELD) == "field"
    assert formats.check_xd(FIELD) == []


def test_the_block_form_is_valid_and_said():
    got = formats.check_xd(XD)
    assert formats.xd_form(XD) == "block"
    assert [lv for lv, _ in got] == ["note"] and "block form" in got[0][1]


@pytest.mark.parametrize("old, new, says", [
    ("Source: A Paper", "Assembly: hands-off\nSource: A Paper", "'Assembly:' is provenance"),
    ("Author: A. Seter\n", "", "'Author-Correction:' has no 'Author:'"),
    ("Date: 1914-01-04", "Date: January 4", "no Date header as YYYY-MM-DD"),
    ("heading: A TEST", "A TEST", "## Printed: not 'label: text'"),
    ("A#O", "A#", "rows differ in length"),
    ("A1 ^Printed: 1-2\n", "", "^Fits: with no ^Printed:"),
    ("D1 ^Answer-Correction", "A1 ^Answer-Correction", "is not under its clue's line"),
    ("D1. A taxi. ~ CAB", "D1. A taxi.", "has no ' ~ '"),
    ("D1. A taxi. ~ CAB", "D1. A taxi. ~ CAB\n\nPuzzle notes:\nSome prose.", "not a clue line"),
    ("## Grid", "## Squares", "no '## Grid' section"),
])
def test_what_breaks_a_reader_of_the_field_form(old, new, says):
    assert old in FIELD
    assert any(says in t for t in xd_problems(FIELD.replace(old, new))), xd_problems(FIELD.replace(old, new))


@pytest.mark.parametrize("old, new, says", [
    ("solution caption:", "solution-caption:", "is written 'solution caption' elsewhere"),
    ("heading: A TEST", "masthead: A TEST", "label 'masthead' is new"),
    ("Description:", "Notes:", "retired as a catch-all"),
    ("D1 ^Answer-Correction", "D1 ^Easy", "is not one of EPP's"),
])
def test_what_is_only_a_note_in_the_field_form(old, new, says):
    got = formats.check_xd(FIELD.replace(old, new))
    assert [lv for lv, _ in got] == ["note"] and says in got[0][1], got


def test_check_takes_xd_files_and_folders(tmp_path):
    (tmp_path / "a.xd").write_text(FIELD, encoding="utf-8")
    (tmp_path / "b.xd").write_text(XD, encoding="utf-8")
    res = formats.check([tmp_path])
    assert (res["xds"], res["packets"], res["problems"], res["notes"]) == (2, 0, 0, 1)
    assert formats.check([tmp_path / "a.xd"])["xds"] == 1
