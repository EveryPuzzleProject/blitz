"""The deployed review pages (docs/review/) are built from src/blitz/*.html by `blitz site-build`.
A change to a page's source that isn't rebuilt leaves the live site running the old page against
new packets (2026-10-19: the proof page's A1 ^Easy rows showed as "no A1^Easy in our grid" because
#32 changed proof.html but not docs/review/index.html). This fails until the build is committed."""

import shutil
from pathlib import Path

from blitz.site import build

ROOT = Path(__file__).resolve().parents[1]
PAGES = ["index.html", "squares/index.html", "batch/index.html"]


def test_docs_review_is_built_from_the_current_source(tmp_path):
    (tmp_path / "site").mkdir()
    shutil.copy2(ROOT / "site" / "config.example.js", tmp_path / "site" / "config.example.js")
    out = build(tmp_path)
    stale = [p for p in PAGES
             if (out / p).read_text(encoding="utf-8") != (ROOT / "docs" / "review" / p).read_text(encoding="utf-8")]
    assert not stale, f"docs/review is out of date for {stale}: run `blitz site-build` and commit docs/review/"
