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


def test_publish_marks_the_puzzles_dropped_as_not_crosswords(tmp_path, monkeypatch):
    import sys
    import types

    from PIL import Image

    from blitz import site

    packet(tmp_path, "games1977-11-01-L037", matches_xd=True, built_from={"xword-ocr": "abc", "games": "def"})
    packet(tmp_path, "games1977-11-01-L040", matches_xd=True, built_from={"xword-ocr": "abc", "games": "def"})
    for name in ("games1977-11-01-L037", "games1977-11-01-L040"):
        Image.new("L", (600, 600), 255).save(tmp_path / name / "grid.png")
        Image.new("RGB", (1200, 1600), "white").save(tmp_path / name / "page.jpg")
    (tmp_path / "dropped.json").write_text(json.dumps({"games1977-11-01-L037": {"by": "triage", "note": "triage: a board game"}}),
                                           encoding="utf-8")
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET", "SUPABASE_URL", "SUPABASE_SERVICE_KEY"):
        monkeypatch.setenv(k, "x")
    monkeypatch.setenv("R2_PUBLIC_URL", "https://r2.example")
    put = []

    class S3:
        def upload_file(self, src, bucket, key, ExtraArgs=None):
            put.append(key)

        def put_object(self, Bucket, Key, Body, **kw):
            put.append(Key)

    monkeypatch.setitem(sys.modules, "boto3", types.SimpleNamespace(client=lambda *a, **k: S3()))
    sent = []
    monkeypatch.setattr(site, "_rest", lambda method, path, body=None, prefer="": sent.append(body))
    assert publish(tmp_path) == ["games1977-11-01-L037", "games1977-11-01-L040"]  # dropped ones go up too, marked
    rows = {r["xdid"]: r for r in sent[0]}
    assert rows["games1977-11-01-L037"]["dropped"] == {"by": "triage", "note": "triage: a board game"}
    assert rows["games1977-11-01-L040"]["dropped"] is None  # not dropped (or kept since): open again
    assert rows["games1977-11-01-L037"]["files"].get("page-small.jpg") and rows["games1977-11-01-L037"]["files"].get("thumb.png")
    assert "page-small.jpg" not in rows["games1977-11-01-L040"]["files"]
