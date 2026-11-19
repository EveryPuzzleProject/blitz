"""blitz hand-packets: a puzzle read by hand from the scan (an xd and its boxes file) as a proof packet."""

import json
from pathlib import Path

from PIL import Image

from blitz import handread

MODERN = """## Metadata
Title: A test
Number: 3
Date: 1914-01-04
Notes: Read by hand.


## Grid
_CAT
_A__
_B__


## Clues
A1. A pet. ~ CAT
A1 ^Printed: 1-2
D1. A taxi. ~ CAB
D1 ^Printed: 1-3
D1 ^Note: misprint: the pair that fits is 1-4


## Design
G { given: true }

.G..
....
....
"""

PAIRS = """## Metadata
Date: 1914-04-19
Numbering: as-printed


## Grid
CAT
A_O
BOW


## Clues
1-2. A pet. ~ CAT
1-3. A taxi. ~ CAB
3-4. A bow. ~ BOW
2-4. A pull. ~ TOW
1-4. Diagonal. ~ C_W


## Labels
1 r1c1
2 r1c3
3 r3c1
4 r3c3
"""


def _make(tmp: Path, xdid: str, xd: str, clues: list[dict]) -> tuple[Path, Path]:
    src, pages = tmp / "src", tmp / "pages"
    src.mkdir(exist_ok=True)
    pages.mkdir(exist_ok=True)
    Image.new("RGB", (400, 300), "white").save(pages / "p.png")
    Image.new("RGB", (400, 300), "white").save(pages / "s.png")
    (src / f"{xdid}.xd").write_text(xd, encoding="utf-8")
    lat = {"corners": [[10, 10], [110, 10], [110, 85], [10, 85]], "rows": 3, "cols": 4}
    (src / f"{xdid}.boxes.json").write_text(json.dumps({
        "xdid": xdid, "pages": {"puzzle": "p.png", "solution": "s.png"},
        "grid": {"page": "puzzle", **lat}, "key": {"page": "solution", **lat},
        "lines": [{"label": "credit", "text": "By someone.", "page": "puzzle", "box": [5, 200, 100, 220]}],
        "clues": clues}), encoding="utf-8")
    return src, pages


def test_modern_form(tmp_path):
    src, pages = _make(tmp_path, "nyw1914-01-04", MODERN, [
        {"pair": "1-2", "text": "A pet.", "page": "puzzle", "box": [5, 100, 90, 120], "ref": "A1"},
        {"pair": "1-3", "text": "A taxi.", "page": "puzzle", "box": [5, 120, 90, 140], "ref": "D1"}])
    made = handread.build_all(src, pages, tmp_path / "out")
    assert made[0]["clues"] == 2 and made[0]["givens"] == 1 and not made[0]["flagged"]
    p = tmp_path / "out" / "nyw1914-01-04"
    ocr = json.loads((p / "ocr.json").read_text(encoding="utf-8"))
    assert ocr["read_by"] == handread.READ_BY
    # the printed numbers from the pairs: A1's 1-2 and D1's 1-3 both start on the given C, which shows its letter,
    # so the pairs and the given clash there: no label, and a note on the square saying what each gave
    assert ocr["square_numbers"] == {"r1c4": "2", "r3c2": "3"}
    assert ocr["grid"] == ["_...", "_.__", "_.__"] and ocr["answers"][0] == "_CAT"
    assert ocr["clues"]["A1"] == {"text": "A pet.", "printed": "1-2", "box": [5, 100, 90, 120]}
    assert {m["field"]: m["value"] for m in ocr["metadata"]} == {"title": "A test", "number": "3", "date": "1914-01-04"}
    rv = json.loads((p / "review.json").read_text(encoding="utf-8"))
    assert rv["corrections"] == {} and rv["matches_xd"] and not rv["ready"]
    notes = {t["target"]: t["note"] for t in rv["tool_notes"]}
    assert notes["clue:D1"].startswith("Note: misprint") and "cell:r1c2" in notes  # the ^Note, the given C
    assert "C (a given)" in notes["grid:r1c2"] and "1 (A1, D1)" in notes["grid:r1c2"]
    assert (p / "puzzle.xd").read_text(encoding="utf-8") == MODERN
    for f in ("page.jpg", "answer_page.jpg", "_src/page.jpg", "grid.png", "answers.png"):
        assert (p / f).exists(), f
    assert Image.open(p / "answers.png").size == (4 * 40, 3 * 40)


def test_printed_numbers_from_the_pairs():
    xd = handread.parse_xd(MODERN.replace("1-2", "C-2").replace("D1 ^Printed: 1-3", "D1 ^Printed: C-9\nD1 ^Fits: C-3"))
    runs = handread.slots(xd["grid"])
    nums, clashes = handread.printed_numbers(xd, runs, {(0, 1): "C"})
    assert nums == {(0, 1): "C", (0, 3): "2", (2, 1): "3"} and clashes == []  # ^Fits over ^Printed; the given's letter
    nums, clashes = handread.printed_numbers(handread.parse_xd(MODERN.replace("D1 ^Printed: 1-3", "D1 ^Printed: 5-3")), runs, {})
    assert (0, 1) not in nums and clashes == [((0, 1), {"1": ["A1"], "5": ["D1"]})]  # two labels: none, said


def test_pair_form_names_runs_and_lists_the_rest(tmp_path):
    src, pages = _make(tmp_path, "nyw1914-04-19", PAIRS, [
        {"pair": "1-2", "text": "A pet.", "page": "puzzle", "box": [5, 100, 90, 120]},
        {"pair": "1-4", "text": "Diagonal.", "page": "puzzle", "box": [5, 140, 90, 160]}])
    made = handread.build_all(src, pages, tmp_path / "out")[0]
    assert made["pair_form"] and made["outside"] == 1
    ocr = json.loads((tmp_path / "out" / "nyw1914-04-19" / "ocr.json").read_text(encoding="utf-8"))
    assert ocr["clues"]["A1"]["printed"] == "1-2" and ocr["clues"]["D1"]["printed"] == "1-3"
    assert ocr["clues"]["A1"]["box"] == [5, 100, 90, 120]
    assert ocr["square_numbers"]["r3c3"] == "4"
    # every pair whose ends bound a run is named by it; the diagonal 1-4 is a printed line with its crop
    assert set(ocr["clues"]) == {"A1", "D1", "A3", "D2"} and ocr["hand_read"]["outside"] == ["1-4"]
    line = ocr["lines"][-1]
    assert line["text"] == "1-4. Diagonal. ~ C_W" and line["box"] == [5, 140, 90, 160]


def test_lines_headers_and_checks_record(tmp_path):
    src, pages = _make(tmp_path, "nyw1914-01-04", MODERN, [
        {"pair": "1-2", "text": "A pet.", "page": "puzzle", "box": [5, 100, 90, 120], "ref": "A1"}])
    b = json.loads((src / "nyw1914-01-04.boxes.json").read_text(encoding="utf-8"))
    b["lines"] = [{"label": "heading", "text": "A TEST.", "page": "puzzle", "box": [1, 1, 9, 9]},
                  {"label": "number", "text": "No. 3", "page": "puzzle", "box": [1, 1, 9, 9]},
                  {"label": "intro heading", "text": "Number 3 of a test, by Pat.", "page": "puzzle", "box": [1, 1, 9, 9]},
                  {"label": "solution caption", "text": "Last week's answers.", "page": "solution", "box": [1, 1, 9, 9]}]
    (src / "nyw1914-01-04.boxes.json").write_text(json.dumps(b), encoding="utf-8")
    handread.build_all(src, pages, tmp_path / "out")
    p = tmp_path / "out" / "nyw1914-01-04"
    ocr = json.loads((p / "ocr.json").read_text(encoding="utf-8"))
    # the line that is the header is the header's, not a note; one that only holds its words stays a note
    assert [(L["label"], L["keep"], L.get("header")) for L in ocr["lines"]] == [
        ("section", False, "title"), ("other", False, "number"), ("intro", True, None), ("answers", False, None)]
    assert {m["field"]: m["says"] for m in ocr["metadata"]} == {
        "title": "as printed in line B1", "number": "as printed in line B2", "date": "the date of the issue it's in"}
    checks = json.loads((p / "checks.json").read_text(encoding="utf-8"))
    assert checks["xd_fp"] == json.loads((p / "review.json").read_text(encoding="utf-8"))["xd_fp"]
    assert {i["code"]: (i["key"], i["from"], i["incomplete"]) for i in checks["items"]} == {
        "no-author": ("meta:author", "hand-read check", False)}
