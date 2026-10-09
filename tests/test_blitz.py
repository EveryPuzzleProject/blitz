"""Run with: uv run --with pytest pytest"""

import json

from PIL import Image

from blitz.crops import make_sheets
from blitz.packet import entries, route, structural_checks, text_view
from blitz.review import choose_targets, feedback, finish


def _ocr(**extra):
    o = {
        "xdid": "test1929-01-01",
        "grid": ["...#", "....", "....", "#..."],
        "answers": ["CAT#", "ARIA", "BOND", "#END"],
        "answers_low_confidence": ["r2c3"],
        "clues": {k: {"text": t, "box": [10, 20 * i, 200, 20 * i + 15]} for i, (k, t) in enumerate({
            "A1": "Feline.", "A4": "Opera song.", "A6": "Agent's tie.", "A7": "Finish.",
            "D1": "Taxi.", "D2": "Long tune.", "D3": "Trial run.", "D5": "Wager."}.items())},
        "meta_boxes": {"title": [10, 200, 200, 220]},
    }
    o.update(extra)
    return o


def _packet(tmp_path, ocr):
    d = tmp_path / ocr["xdid"]
    d.mkdir()
    (d / "ocr.json").write_text(json.dumps(ocr))
    Image.new("L", (400, 400), 255).save(d / "page.jpg")
    for f in ("grid.png", "answers.png"):
        Image.new("L", (160, 160), 255).save(d / f)
    return d


def test_entries_and_a_clean_puzzle():
    e = entries(_ocr())
    assert e["A1"][0] == "CAT" and e["A4"][0] == "ARiA" and e["D1"][0] == "CAB"
    assert structural_checks(_ocr()) == {} and route(_ocr()) == ("text", [])
    assert "A4    ARiA" in text_view(_ocr())


def test_a_key_of_another_size_goes_to_the_full_review():
    assert route(_ocr(answers=["CAT", "ARI", "BON"]))[0] == "full"


def test_finish_applies_only_what_was_seen():
    o = _ocr()
    o["clues"]["A1"]["box"] = None  # the OCR never found A1's text
    draft = {"ready": True, "corrections": {"clue:A1": "A cat.", "clue:A4": "An aria."}, "answers": {"D5": "ADS"}}
    review, _ = finish(o, draft, ["box:300,300,390,320", "cell:r3c4"])
    assert review["corrections"] == {"clue:A1": "A cat.", "cell:r4c4": "S"}
    assert "clue:A4" in review["unsure"]


def test_sheets_add_up_and_report_what_has_no_crop(tmp_path):
    o = _ocr()
    o["clues"]["A7"]["box"] = None
    d = _packet(tmp_path, o)
    first = make_sheets(d, choose_targets(o, ["clue:A1", "entry:D1"]))
    assert first["sheets"] and ("meta:byline" in dict(first["missed"]))
    second = make_sheets(d, ["clue:A1", "clue:A4", "clue:A7", "grid:all"])
    assert [c for s in second["sheets"] for c in s["crops"]] == ["clue:A4", "grid:all"]
    assert dict(second["missed"]).keys() == {"clue:A7"}
    shown = json.loads((d / "sheets" / "shown.json").read_text())["shown"]
    assert {"clue:A1", "entry:D1", "clue:A4", "grid:all"} <= set(shown)


def test_feedback_groups_notes(tmp_path):
    for x, kinds in (("p1", ["heading-in-clue"]), ("p2", ["heading-in-clue", "byline"])):
        (tmp_path / x).mkdir()
        (tmp_path / x / "review.json").write_text(json.dumps({"tool_notes": [{"kind": k, "note": "n"} for k in kinds]}))
    text = feedback(sorted(tmp_path.iterdir()))
    assert "## heading-in-clue: 2 notes, 2 puzzles" in text and text.index("heading-in-clue") < text.index("byline")


def test_finish_lists_odd_words_the_review_left_in():
    o = _ocr()
    o["clues"]["A4"]["text"] = "Opera sonq."  # an OCR slip
    o["clues"]["A6"]["text"] = "Agent's tie, thez."
    review, _ = finish(o, {"ready": True, "confirm": ["clue:A4"], "as_printed": {"A6": "dialect"},
                           "corrections": {"clue:A1": "Felinee."}}, ["clue:A1"])
    assert review["odd_left"] == {"A4": ["sonq"]}  # confirm doesn't settle it; the reviewer's own word isn't flagged


def test_a_clue_crop_spans_its_column(tmp_path):
    from blitz.crops import crop

    o = _ocr()
    o["clues"]["A4"]["box"] = [10, 20, 30, 35]  # a box around the number only
    d = _packet(tmp_path, o)
    assert crop(d, "clue:A4", o).width > crop(d, "box:10,20,30,35", o).width * 4


def test_odd_words_catch_ocr_slips_but_not_ordinary_forms():
    from blitz.packet import odd_words

    for slip in ("When Seotehmen are", "ean't", "Chieago", "intoxieating", "quarre!", "wal's", "highor der", "Sometbing"):
        assert odd_words(slip), slip
    for fine in ("Frau's (boy) freund.", "These men were corkers.", "The unkindest cut.", "This often follows a demi-tasse.",
                 "England'd", "these'll", "Lobbyist's headquarters."):
        assert not odd_words(fine), fine


def test_rejected_changes_are_left_out_and_recorded(tmp_path):
    from blitz.work import apply_decisions, export_decisions

    d = tmp_path / "p1"
    d.mkdir()
    (d / "decisions.json").write_text(json.dumps({"items": {"clue:A1": "reject", "sic:D2": "reject"},
                                                  "notes": {"clue:A1": "scan says Feline."}, "verdict": "needs-work"}))
    rv = apply_decisions({"corrections": {"clue:A1": "Felines.", "cell:r1c1": "C"}, "sic": {"D2": "tune"}}, d, "me")
    assert rv["corrections"] == {"cell:r1c1": "C"} and rv["sic"] == {}
    assert rv["checked"]["rejected"]["clue:A1"] == {"value": "Felines.", "note": "scan says Feline."}
    assert export_decisions(tmp_path)["puzzles"]["p1"]["verdict"] == "needs-work"


def test_site_import_combines_helpers(monkeypatch):
    import blitz.site as site

    uid = {"a": "u1", "b": "u2"}
    data = {
        "profiles?select=user_id,display_name": [{"user_id": "u1", "display_name": "Ann"}, {"user_id": "u2", "display_name": ""}],
        "decisions?select=*&order=at": [
            {"xdid": "p1", "item": "clue:A1", "user_id": uid["a"], "decision": "accept", "note": ""},
            {"xdid": "p1", "item": "clue:A1", "user_id": uid["b"], "decision": "reject", "note": "scan says Feline."}],
        "verdicts?select=*&order=at": [
            {"xdid": "p1", "user_id": uid["a"], "verdict": "looks-right", "note": ""},
            {"xdid": "p1", "user_id": uid["b"], "verdict": "needs-work", "note": "A1"}],
        "reports?select=*&order=at": [{"xdid": "p1", "target": "clue:D2", "user_id": uid["a"], "text": "Long tune."}],
        "proofs?select=*&order=at": [{"xdid": "p1", "user_id": uid["b"], "who": "Bo", "decision": "ready", "at": "t",
                                      "review": {"edits": {"clue:A1": "Feline."}, "status": {"A": {"v": "ok"}}}}],
    }
    monkeypatch.setattr(site, "_rest", lambda method, path, *a, **k: data[path])
    p = site.fetch_decisions()["puzzles"]["p1"]
    assert p["items"] == {"clue:A1": "reject"} and p["notes"]["clue:A1"] == "a helper: scan says Feline."
    assert p["verdict"] == "needs-work" and p["reports"] == {"clue:D2": "Ann: Long tune."}
    assert p["by"]["Ann"] == {"clue:A1": "accept", "verdict": "looks-right"}
    assert p["proofs"]["Bo"]["edits"] == {"clue:A1": "Feline."} and p["proofs"]["Bo"]["decision"] == "ready"


# Moved from xword-ocr's test_triage.py when xword-ocr stopped doing review (2026-10-09).

def test_whole_puzzle_problems_go_to_the_full_review():
    o = _ocr()
    o["clues"]["D3"]["text"] = ""
    assert "clue text missing" in structural_checks(o)
    o = _ocr()
    o["clues"]["D3"]["text"] = o["clues"]["D2"]["text"]
    assert structural_checks(o)["same text on neighbouring clues"] == ["D2", "D3"]
    o = _ocr()
    o["clues"] = {("A5" if k == "A6" else k): v for k, v in o["clues"].items()}
    assert "clue numbers don't match the grid" in structural_checks(o)
    assert route(_ocr(answers=None)) == ("full", ["no answer key"])


def test_a_whole_grid_crop_covers_every_square():
    draft = {"corrections": {"cell:r4c4": "E"}, "tool_notes": [{"kind": "crop", "note": "x"}]}
    review, _ = finish(_ocr(), draft, ["cell:all"])
    assert review["corrections"] == {"cell:r4c4": "E"}
    assert review["tool_notes"] == [{"kind": "crop", "note": "x"}]


def test_a_few_missing_clues_are_not_a_continuation():
    from blitz.packet import number_grid

    grid = ["".join("#" if r % 2 and c % 2 else "." for c in range(25)) for r in range(25)]
    labels = [s[0] for s in number_grid(grid)]
    o = {"grid": grid, "answers": None, "clues": {k: {"text": f"clue {k}."} for k in labels}}
    for k in [k for k in labels if k[0] == "D"][:3]:
        o["clues"][k]["text"] = ""
    checks = structural_checks(o)
    assert "clue list continues on another page" not in checks and "clue text missing" in checks
