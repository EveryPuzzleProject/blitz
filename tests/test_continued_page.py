"""A clue list that goes on to another page (xword-ocr's continued_page.jpg).

Real case: judge1930-08-23, whose Down list stops at D10 at the foot of the
puzzle page (above an ad) and goes on, D11-D67, at the top of the next page
(archive.org leaf 32). xword-ocr reads both pages and writes the next page's
clues with "image": "continued_page.jpg" and boxes in that image's pixels.

Run with: uv run --with pytest pytest"""

import json

from PIL import Image

from blitz.crops import crop, make_sheets
from blitz.packet import last_in_column, text_view
from blitz.review import covered


def _ocr():
    clues = {
        "D9": {"text": "The damp grip of a Congressman (plural).", "box": [806, 690, 1010, 704]},
        "D10": {"text": "Here's how alimony begins.", "box": [806, 702, 960, 716]},
        # Same place on the next page as D9/D10 on this one: boxes of two images never mix.
        "D11": {"text": "This is always under your feet in the kitchen (plural).", "box": [72, 106, 370, 122],
                "image": "continued_page.jpg"},
        "D12": {"text": "This is blessed for Winchell.", "box": [73, 119, 240, 132], "image": "continued_page.jpg"},
    }
    return {"xdid": "judge1930-08-23", "grid": ["..", ".."], "title": "Judge's Crossword Puzzle No. 170",
            "clue_image": "page.jpg", "scales": {"page.jpg": 0.368, "continued_page.jpg": 0.368},
            "continued_page": {"image": "continued_page.jpg", "clues": ["D11", "D12"],
                               "source": "https://archive.org/details/sim_judge_1930-08-23_99/page/n32/mode/1up"},
            "clues": clues}


def _packet(tmp_path):
    o = _ocr()
    d = tmp_path / o["xdid"]
    d.mkdir()
    (d / "ocr.json").write_text(json.dumps(o))
    Image.new("L", (1200, 1600), 255).save(d / "page.jpg")
    nxt = Image.new("L", (1200, 1600), 255)
    nxt.paste(0, (80, 110, 300, 118))  # ink where D11 is printed on the next page
    nxt.save(d / "continued_page.jpg")
    return o, d


def test_text_md_says_which_clues_are_on_the_next_page():
    t = text_view(_ocr())
    assert "## Clues on the next page: D11..D12 (2)" in t
    assert "continued_page.jpg" in t and "page/n32" in t
    assert "D11" in t and "[next page]" in t
    assert "D11 72,106,370,122 (next page)" in t


def test_a_next_page_clue_is_cropped_from_the_next_page(tmp_path):
    o, d = _packet(tmp_path)
    im = crop(d, "clue:D11", o)
    assert not isinstance(im, str)
    assert im.convert("L").getextrema()[0] == 0  # the ink drawn on continued_page.jpg, not page.jpg (blank)
    im = crop(d, "next:60,100,380,130", o)
    assert not isinstance(im, str) and im.convert("L").getextrema()[0] == 0
    made = make_sheets(d, ["clue:D11", "next:60,100,380,130"])
    assert made["missed"] == []


def test_boxes_of_the_two_pages_are_not_compared():
    o = _ocr()
    # D10 is the last clue of its column on the clue page: D11/D12's boxes (other page) don't count as below it.
    o["clues"]["D11"]["box"] = [806, 760, 1010, 774]
    assert last_in_column(o, "D10")


def test_a_next_crop_covers_a_next_page_clue_and_a_box_crop_does_not():
    o = _ocr()
    assert covered("clue:D11", ["next:60,100,380,130"], o)
    assert not covered("clue:D11", ["box:60,100,380,130"], o)
    assert not covered("clue:D9", ["next:800,680,1020,710"], o)
