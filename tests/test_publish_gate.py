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
