"""Uploading to the review site's bucket (R2, S3-compatible): only what changed, several at a time.

Both publishes (site.publish, the packets; sitebatch.publish, the batch page's snapshot) put many small
files under one prefix. `sync` lists that prefix once, skips every file whose MD5 matches the object's
ETag there (for a single-part upload R2's ETag is the MD5 of its bytes), and uploads the rest in a thread
pool. Every file goes up in one part (MULTIPART_AT is far above anything a packet holds), so the next
publish can compare it; an object with a multipart ETag ("<md5>-<parts>") can't be compared and is
uploaded again. The counts it returns are what happened, never a guess: `uploaded` were sent, `skipped`
were found identical on the bucket by that listing.
"""

from __future__ import annotations

import hashlib
import io
import mimetypes
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

WORKERS = 16
MULTIPART_AT = 512 * 1024 * 1024  # one part up to here, so the ETag stays the file's MD5


@dataclass
class Put:
    """One object to have on the bucket: a file (src) or bytes made here (body)."""
    key: str
    src: Path | None = None
    body: bytes | None = None
    cache: str = "public, max-age=86400"
    type: str = ""

    def data(self) -> bytes:
        return self.body if self.body is not None else self.src.read_bytes()

    def content_type(self) -> str:
        return self.type or mimetypes.guess_type(self.key)[0] or "application/octet-stream"


def client(account: str, key_id: str, secret: str):
    import boto3
    try:
        from botocore.config import Config
        extra = {"config": Config(max_pool_connections=WORKERS * 2, retries={"max_attempts": 5, "mode": "standard"})}
    except ImportError:
        extra = {}
    return boto3.client("s3", endpoint_url=f"https://{account}.r2.cloudflarestorage.com",
                        aws_access_key_id=key_id, aws_secret_access_key=secret, region_name="auto", **extra)


def listing(s3, bucket: str, prefix: str) -> dict[str, tuple[str, int]]:
    """{key: (etag without quotes, size)} for everything under prefix."""
    out = {}
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        for o in page.get("Contents", []):
            out[o["Key"]] = (o.get("ETag", "").strip('"'), o.get("Size", -1))
    return out


def unchanged(data: bytes, remote: tuple[str, int] | None) -> bool:
    """Whether the bucket already has exactly these bytes: same size and the ETag is their MD5.
    A missing object, or a multipart ETag (which isn't an MD5), counts as changed."""
    if not remote:
        return False
    etag, size = remote
    return size == len(data) and "-" not in etag and etag.lower() == hashlib.md5(data).hexdigest()


def sync(s3, bucket: str, puts: list[Put], remote: dict[str, tuple[str, int]], force: bool = False,
         workers: int = WORKERS) -> dict:
    """Upload the puts not already on the bucket (remote: `listing` of their prefix), workers at a time.
    force: upload all of them. Returns {"uploaded": [keys], "skipped": [keys], "bytes": bytes sent}."""
    try:
        from boto3.s3.transfer import TransferConfig
        one_part = {"Config": TransferConfig(multipart_threshold=MULTIPART_AT, use_threads=False)}
    except ImportError:  # a stand-in client in the tests
        one_part = {}

    def one(p: Put):
        data = p.data()
        if not force and unchanged(data, remote.get(p.key)):
            return p.key, False, 0
        s3.upload_fileobj(io.BytesIO(data), bucket, p.key, **one_part,
                          ExtraArgs={"ContentType": p.content_type(), "CacheControl": p.cache})
        return p.key, True, len(data)

    up, skip, sent = [], [], 0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for key, did, n in pool.map(one, puts):
            (up if did else skip).append(key)
            sent += n
    return {"uploaded": up, "skipped": skip, "bytes": sent}


def summary(r: dict) -> str:
    return f"uploaded {len(r['uploaded'])} files ({r['bytes'] / 1e6:.1f} MB), skipped {len(r['skipped'])} already on the site"
