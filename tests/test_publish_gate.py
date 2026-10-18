import json

import pytest

from blitz.site import Stop, publish


def packet(root, name, **rv):
    d = root / name
    d.mkdir()
    (d / "ocr.json").write_text("{}", encoding="utf-8")
    (d / "review.json").write_text(json.dumps({"model": "earlier reviews", **rv}), encoding="utf-8")


def test_publish_refuses_a_page_that_wouldnt_show_its_xd(tmp_path):
    packet(tmp_path, "judge1925-02-21", matches_xd=False, mismatches=["r1c1: key shows 'I', xd has 'T'"])
    packet(tmp_path, "judge1925-02-28", matches_xd=True, built_from={"xword-ocr": "abc", "judge": "def+changes"})
    with pytest.raises(Stop) as e:
        publish(tmp_path, dry_run=True)
    assert "judge1925-02-21: the page wouldn't show its xd" in str(e.value)
    assert "judge1925-02-28: built from uncommitted data" in str(e.value)


def test_publish_takes_checked_packets(tmp_path):
    packet(tmp_path, "judge1925-02-21", matches_xd=True, built_from={"xword-ocr": "abc", "judge": "def"})
    assert publish(tmp_path, dry_run=True) == ["judge1925-02-21"]


def test_publish_leaves_out_the_puzzles_dropped_as_not_crosswords(tmp_path):
    packet(tmp_path, "games1977-11-01-L037", matches_xd=True, built_from={"xword-ocr": "abc", "games": "def"})
    packet(tmp_path, "games1977-11-01-L040", matches_xd=True, built_from={"xword-ocr": "abc", "games": "def"})
    (tmp_path / "dropped.json").write_text(json.dumps({"games1977-11-01-L037": {"by": "triage", "note": "a board game"}}),
                                           encoding="utf-8")
    assert publish(tmp_path, dry_run=True) == ["games1977-11-01-L040"]
