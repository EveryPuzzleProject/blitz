"""Record pages (blitz.records): URL scheme, numbering, notes and the review history."""
import json

from blitz.records import build, build_grid, parse_xd, record_url, who

XD = """Title: Judge's Crossword Puzzles
Author: A. Maker
Date: 1924-11-01
Number: 1
Source: https://archive.org/details/x/page/n34
Solution-Source: https://archive.org/details/y/page/n34
Provenance: Judge's first crossword.


#AB
CDE
FG#


A1. Two letters ~ AB
A3. Three ~ CDE
A4. Again ~ FG
D1. Down one ~ ADG
D2. Down two ~ BE
D3. Oops ~ CF


Printed with puzzle:
TRY THIS!

Misprints, kept as printed (printed → meant):
D3: Oops → Whoops

OCR review flags:
A1: fixed
"""


def test_record_url_drops_the_publication_prefix():
    assert record_url("judge", "judge1924-11-01") == "https://everypuzzleproject.org/judge/1924-11-01/"
    assert record_url("judge", "judge1924-11-15b") == "https://everypuzzleproject.org/judge/1924-11-15b/"


def test_grid_numbering_and_answers():
    xd = parse_xd(XD)
    g = build_grid(xd["rows"], xd["clues"])
    assert {w["id"] for w in g["words"]} == set(xd["clues"])
    assert {w["id"]: w["answer"] for w in g["words"]}["D1"] == "ADG"


def test_who_names_roles_not_volunteers():
    assert who("agent: Claude Fable 5.1 (batch 5)")[:2] == ("Claude Fable 5.1", "ai")
    assert who("Alex DeJarnatt (key-squares page)")[0] == "the project's maintainer"
    assert who("oops6498 (review site)")[0] == "the project's maintainer"
    assert who("someone (review site)")[0] == "a volunteer on the review site"
    name, kind, why = who("Claude (per Alex DeJarnatt, 2026-10-12: this was an advertisement)")
    assert (name, kind, why) == ("Claude", "ai", "this was an advertisement")


def test_build_writes_a_page_with_share_tags(tmp_path):
    repo = tmp_path / "judge"
    (repo / "xd").mkdir(parents=True)
    (repo / "fixes").mkdir()
    (repo / "xd" / "judge1924-11-01.xd").write_text(XD, encoding="utf-8")
    (repo / "fixes" / "corrections.jsonl").write_text(json.dumps(
        {"xdid": "judge1924-11-01", "item": "clue:A1", "action": "correct", "was": "Tw0 letters", "value": "Two letters",
         "flagged": False, "at": "2026-09-29T00:00:00Z", "by": "agent: Claude Opus 5.5 (pilot)"}) + "\n", encoding="utf-8")
    (repo / "gxd-exports.tsv").write_text("gxd_id\txdid\n" "judge1924-11-01\tjudge1924-11-01\n", encoding="utf-8")
    [page] = build(repo, tmp_path / "site", tmp_path / "cache")
    assert page == tmp_path / "site" / "1924-11-01" / "index.html"
    html = page.read_text(encoding="utf-8")
    assert '<meta property="og:url" content="https://everypuzzleproject.org/judge/1924-11-01/">' in html
    assert "· No. 1 ·" in html and "Judge&#x27;s first crossword." in html
    assert "crosswordreference.com/puzzle/judge/judge1924-11-01" in html
    assert "TRY THIS!" in html and "OCR review flags" not in html
    assert 'title="Meant: Whoops"' in html  # the kept misprint, marked on its clue
    assert "<del>Tw0 letters</del>" in html and "Claude Opus 5.5" in html
