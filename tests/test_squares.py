import json
from collections import Counter

import pytest
from PIL import Image

from blitz.site import Stop, publish
from blitz.squares import build, suggest

XD = """Title: Test Puzzle No. 7
Number: 7
Date: 1931-04-04
Solution-Source: https://archive.org/details/x/page/n31


EIUGE
A#O#S
TAIES
E#D#T
SNEER


A1. Draw out ~ EIUGE
A6. Stories ~ TAIES
A7. Scoff ~ SNEER
D1. Consumes ~ EATES
D2. Old ~ UOIDE
D3. Rests ~ ESSTR
"""


def fixture(tmp_path, ledger=()):
    repo, folder = tmp_path / "judge", tmp_path / "tasks"
    (repo / "xd").mkdir(parents=True)
    (repo / "fixes").mkdir()
    (repo / "xd" / "judge1931-04-04.xd").write_text(XD, encoding="utf-8")
    (repo / "fixes" / "corrections.jsonl").write_text("".join(json.dumps(r) + "\n" for r in ledger), encoding="utf-8")
    d = folder / "judge1931-04-04"
    d.mkdir(parents=True)
    grid = [r for r in XD.split("\n\n\n")[1].split("\n") if r]
    (d / "ocr.json").write_text(json.dumps({"answers": grid, "answers_low_confidence": ["r3c2", "r3c4", "r5c3"]}),
                                encoding="utf-8")
    (d / "review.json").write_text(json.dumps({"model": "earlier reviews", "matches_xd": True,
                                               "built_from": {"judge": "abc"}}), encoding="utf-8")
    Image.new("L", (200, 200), 255).save(d / "answers.png")
    return folder, repo


COUNTS = Counter({"EDUCE": 140, "TALES": 50, "SNEER": 40})


def test_suggest_changes_one_confused_letter():
    assert suggest("EIUGE", Counter({"EDUCE": 140}), set()) is None  # two letters away
    assert suggest("TAIES", Counter({"TALES": 50}), set()) == (2, "TALES", 50)
    assert suggest("TAIES", Counter({"TALES": 50}), {"TAIES"}) is None  # the publication's own word
    assert suggest("TAIES", Counter({"TALES": 50, "TAIES": 3}), set()) is None  # a known answer


def test_suggest_knows_hand_lettered_key_misreads():
    # Misread letters found in Judge's keys after they reached gxd (2026-10-12)
    common = Counter({"BERTH": 184, "AIRED": 665, "DRUM": 426, "HARMONY": 29, "DROP": 1017,
                      "ELASTIC": 233, "SEERS": 768})
    assert suggest("BEZTH", common, set()) == (2, "BERTH", 184)      # R read as Z
    assert suggest("AIZED", common, set()) == (2, "AIRED", 665)
    assert suggest("DGUM", common, set()) == (1, "DRUM", 426)        # R read as G
    assert suggest("HARSONY", common, set()) == (3, "HARMONY", 29)   # M read as S
    assert suggest("DROD", common, set()) == (3, "DROP", 1017)       # P read as D
    assert suggest("ELATTIC", common, set()) == (3, "ELASTIC", 233)  # S read as T
    assert suggest("SIERS", common, set()) == (1, "SEERS", 768)      # E read as I


def test_cards_from_the_ocr_and_the_word_check(tmp_path):
    folder, repo = fixture(tmp_path)
    out = build(folder, "judge", repo, counts=COUNTS)
    by = {f["sq"]: f for f in out["flags"]}
    # the OCR was unsure of r3c2 (an A: left out), r3c4 and r5c3; TAIES is a letter off TALES
    assert sorted(by) == ["r3c3", "r3c4", "r5c3"]
    assert by["r3c3"]["source"] == "words" and by["r3c3"]["card"]["suggest"] == "L"
    assert by["r3c3"]["card"]["why"] == ["A6 reads TAIES, not a known answer; TALES is (50 times in gxd)"]
    assert by["r3c4"]["source"] == "ocr"
    c = by["r3c4"]["card"]
    # the xd's own labels (A6, where the grid alone would say A4) and clues
    assert c["letter"] == "E" and c["across"] == {"label": "A6", "answer": "TAIES", "i": 3, "clue": "Stories"}
    assert c["down"] is None   # r3c4 is only in an across answer
    assert by["r5c3"]["card"]["down"] == {"label": "D2", "answer": "UOIDE", "i": 4, "clue": "Old"}
    assert c["img"] == "answers.png" and c["crop"]["size"] == [200, 200] and c["crop"]["box"] == [120, 80, 40, 40]
    assert c["scan"].startswith("https://archive.org/")
    assert out["clean"] == []


def test_a_person_settles_a_square_and_their_word(tmp_path):
    ledger = [{"xdid": "judge1931-04-04", "item": "cell:r3c3", "action": "confirm", "by": "Alex (key-squares page)"},
              {"xdid": "judge1931-04-04", "item": "cell:r5c3", "action": "confirm", "by": "agent: Claude"}]
    folder, repo = fixture(tmp_path, ledger)
    out = build(folder, "judge", repo, counts=COUNTS)
    sqs = [f["sq"] for f in out["flags"]]
    assert "r3c3" not in sqs   # a person kept it, so TAIES is this publication's word
    assert "r5c3" in sqs       # an agent's confirm isn't a person's


def test_publish_takes_cards_made_from_the_packets_commit(tmp_path, capsys):
    folder, repo = fixture(tmp_path)
    build(folder, "judge", repo, counts=COUNTS)
    made = lambda c: (folder / "key-squares.json").write_text(json.dumps(
        {**json.loads((folder / "key-squares.json").read_text(encoding="utf-8")), "built_from": c}), encoding="utf-8")
    for commit, why in (("abc+changes", "uncommitted"), ("def", "the packets from abc")):
        made(commit)
        with pytest.raises(Stop) as e:
            publish(folder, dry_run=True, squares_only=True)
        assert why in str(e.value)
    made("abc")   # the packets' commit
    assert publish(folder, dry_run=True, squares_only=True) == ["judge1931-04-04"]
    assert "key squares in 1 puzzles" in capsys.readouterr().out


def test_a_person_who_read_the_whole_key_settles_the_ocr_cards(tmp_path):
    ledger = [{"xdid": "judge1931-04-04", "item": "puzzle", "action": "looks-right", "by": "Ann (review site)"}]
    folder, repo = fixture(tmp_path, ledger)
    out = build(folder, "judge", repo, counts=COUNTS)
    assert [(f["sq"], f["source"]) for f in out["flags"]] == [("r3c3", "words")]   # the word check still looks
