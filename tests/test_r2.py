"""Uploading to the site's bucket: what's skipped, what's sent, and the watch's address."""

import hashlib
import threading

from blitz import r2
from blitz.sitebatch import watch_url


class FakeBucket:
    """An S3 client over a dict: list_objects_v2 pages and single-part ETags (the MD5), as R2 does."""

    def __init__(self, page_size=2):
        self.objects: dict[str, bytes] = {}
        self.sent: list[str] = []
        self.page_size = page_size
        self.lock = threading.Lock()
        self.etag_override: dict[str, str] = {}

    def upload_fileobj(self, f, bucket, key, Config=None, ExtraArgs=None):
        with self.lock:
            self.objects[key] = f.read()
            self.sent.append(key)

    def get_paginator(self, name):
        assert name == "list_objects_v2"
        bucket = self

        class P:
            def paginate(self, Bucket, Prefix):
                keys = sorted(k for k in bucket.objects if k.startswith(Prefix))
                for i in range(0, max(len(keys), 1), bucket.page_size):
                    chunk = keys[i:i + bucket.page_size]
                    yield {"Contents": [{"Key": k, "Size": len(bucket.objects[k]),
                                         "ETag": '"%s"' % bucket.etag_override.get(k, hashlib.md5(bucket.objects[k]).hexdigest())}
                                        for k in chunk]} if chunk else {}
        return P()


def test_unchanged_needs_same_size_and_md5():
    data = b"hello"
    md5 = hashlib.md5(data).hexdigest()
    assert r2.unchanged(data, (md5, 5))
    assert r2.unchanged(data, (md5.upper(), 5))
    assert not r2.unchanged(data, None)  # not on the bucket
    assert not r2.unchanged(data, (md5, 6))  # size differs
    assert not r2.unchanged(b"hellO", (md5, 5))  # same size, other bytes
    assert not r2.unchanged(data, (md5 + "-2", 5))  # a multipart ETag isn't an MD5: upload again


def test_listing_reads_every_page():
    b = FakeBucket(page_size=2)
    for i in range(5):
        b.objects[f"x/{i}"] = bytes([i])
    b.objects["y/0"] = b"other prefix"
    got = r2.listing(b, "bucket", "x/")
    assert sorted(got) == [f"x/{i}" for i in range(5)]
    assert got["x/3"] == (hashlib.md5(bytes([3])).hexdigest(), 1)


def test_sync_skips_what_the_bucket_has_and_says_so(tmp_path):
    b = FakeBucket()
    (tmp_path / "a.json").write_bytes(b'{"a": 1}')
    (tmp_path / "b.png").write_bytes(b"png")
    puts = [r2.Put("p/a.json", src=tmp_path / "a.json", cache="no-cache"), r2.Put("p/b.png", src=tmp_path / "b.png"),
            r2.Put("p/thumb.png", body=b"thumb", type="image/png")]
    first = r2.sync(b, "bucket", puts, r2.listing(b, "bucket", "p/"))
    assert sorted(first["uploaded"]) == ["p/a.json", "p/b.png", "p/thumb.png"] and first["skipped"] == []
    assert first["bytes"] == 8 + 3 + 5
    # nothing changed: nothing sent
    b.sent.clear()
    again = r2.sync(b, "bucket", puts, r2.listing(b, "bucket", "p/"))
    assert again["uploaded"] == [] and sorted(again["skipped"]) == ["p/a.json", "p/b.png", "p/thumb.png"]
    assert b.sent == [] and again["bytes"] == 0
    assert "uploaded 0 files" in r2.summary(again) and "skipped 3" in r2.summary(again)
    # one file changed, one object on the bucket has a multipart ETag: just those two go up
    (tmp_path / "a.json").write_bytes(b'{"a": 2}')
    b.etag_override["p/b.png"] = "abc-3"
    third = r2.sync(b, "bucket", puts, r2.listing(b, "bucket", "p/"))
    assert sorted(third["uploaded"]) == ["p/a.json", "p/b.png"] and third["skipped"] == ["p/thumb.png"]
    assert b.objects["p/a.json"] == b'{"a": 2}'
    # force: all of them
    forced = r2.sync(b, "bucket", puts, r2.listing(b, "bucket", "p/"), force=True)
    assert len(forced["uploaded"]) == 3 and forced["skipped"] == []


def test_sync_runs_in_parallel(tmp_path):
    """Uploads overlap: with 8 workers, 8 uploads that each wait for the others all get in at once."""
    gate = threading.Barrier(8, timeout=5)

    class Slow(FakeBucket):
        def upload_fileobj(self, f, bucket, key, Config=None, ExtraArgs=None):
            gate.wait()  # times out (BrokenBarrierError) if the uploads ran one at a time
            super().upload_fileobj(f, bucket, key, Config, ExtraArgs)

    b = Slow()
    res = r2.sync(b, "bucket", [r2.Put(f"k/{i}", body=bytes([i])) for i in range(8)], {}, workers=8)
    assert len(res["uploaded"]) == 8


def test_watch_url_never_says_localhost():
    assert watch_url("http://localhost:8772") == "http://127.0.0.1:8772"
    assert watch_url("http://LOCALHOST:8766/") == "http://127.0.0.1:8766"
    assert watch_url("http://localhost") == "http://127.0.0.1"
    assert watch_url("http://127.0.0.1:8772") == "http://127.0.0.1:8772"
    assert watch_url("http://[::1]:8772") == "http://[::1]:8772"  # asked for IPv6 by name: left alone
    assert watch_url("https://watch.example:8443/x") == "https://watch.example:8443/x"
