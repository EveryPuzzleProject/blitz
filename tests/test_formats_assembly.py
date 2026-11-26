"""blitz check-format: a harvest's assembly records against formats/assembly-record.md."""

import gzip
import hashlib
import json
from pathlib import Path

from blitz import formats

H = "sha256:" + "ab" * 32
PAGES = ("page:scan-a/0026", "page:scan-a/0063")


def make(tmp: Path, date: str = "1977-09-01", reading: str = "hands-off") -> tuple[Path, Path]:
    """The smallest record and artifact the writer makes: (the issue's file, the store)."""
    store = tmp / "artifacts"
    place = {"scan": "scan-a", "leaf": 26, "box": [10.0, 20.0, 300.0, 400.0]}
    body = {"format": "assembly-record/1", "pubid": "games", "date": date, "variant": reading, "next": None,
            "pages_read": [{"scan": "scan-a", "leaf": lf, "role": "issue", "analysis": H, "ocr": H, "image": None,
                            "view": H, "restarted": False, "extract": None} for lf in (26, 63)],
            "puzzles": [{"grid": {**place, "label": "grid 15x15", "size": [15, 15], "in_box": 0}, "title": "A Title",
                         "clues": {"A": [], "D": []}, "cryptic": False, "flags": [],
                         "key": {**place, "leaf": 63, "label": "answer grid 15x15", "differ": 0, "issue": "this"}}],
            "loose": [{**place, "kind": "clues", "label": "Across 1-9", "why": "fills no grid in this issue"}],
            "pages": [{"scan": "scan-a", "leaf": 26, "size": [800, 1000], "boxes": []}],
            "state": {"$id": 0}}
    raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
    h = "sha256:" + hashlib.sha256(raw).hexdigest()
    a = formats.artifact_path(store, "assembly", h)
    a.parent.mkdir(parents=True)
    a.write_bytes(gzip.compress(raw))
    rec = {"format": "assembly-record/1", "stage": "assembly", "version": "assembly/1",
           "settings": {"hands_off": reading.startswith("hands-off"), "linked_ends": False, "keys_next_issue": False},
           "inputs": {"issues": H, **{p: H for p in PAGES}}, "output": h, "made": "2026-11-25T22:02:27+00:00",
           "took": 16.2, "code": "xword-ocr 0.1.0"}
    f = tmp / "harvest" / "assembly" / "issue" / f"{date}.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({f"issue:{date}/{reading}": {"assembly": rec}}), encoding="utf-8")
    return f, store


def edit(f: Path, fn) -> None:
    d = json.loads(f.read_text(encoding="utf-8"))
    fn(next(iter(d.values()))["assembly"])
    f.write_text(json.dumps(d), encoding="utf-8")


def problems(f: Path, store: Path | None = None) -> list[str]:
    return [t for lv, t in formats.check_assembly(f, store) if lv == "problem"]


def test_what_the_writer_makes_passes(tmp_path):
    f, store = make(tmp_path)
    assert formats.check_assembly(f) == [] and formats.check_assembly(f, store) == []
    for path in (f, f.parent, f.parent.parent):  # a file, assembly/issue, or the harvest's assembly/ folder
        res = formats.check([path], store)
        assert (res["assemblies"], res["problems"], res["notes"], res["packets"]) == (1, 0, 0, 0)


def test_a_record_with_no_format_field_is_version_1(tmp_path):
    f, store = make(tmp_path)
    edit(f, lambda r: r.pop("format"))
    assert formats.check_assembly(f, store) == []
    edit(f, lambda r: r.update(format="assembly-record/2"))
    assert "newer than this check reads" in problems(f)[0]


def test_what_a_reader_would_break_on_is_a_problem(tmp_path):
    f, _ = make(tmp_path)
    edit(f, lambda r: (r.pop("took"), r["inputs"].update({"page:scan-a/0026": "abc"}), r["inputs"].pop("issues"),
                       r["settings"].update(hands_off=False)))
    got = problems(f)
    assert any("took is None" in t for t in got) and any("is not a sha256 hash" in t for t in got)
    assert any("inputs has no 'issues'" in t for t in got) and any("settings.hands_off is False" in t for t in got)


def test_a_unit_in_another_issues_file_and_an_unknown_reading(tmp_path):
    f, _ = make(tmp_path)
    f.rename(f.with_name("1977-11-01.json"))
    assert "is in the file of another issue" in problems(f.with_name("1977-11-01.json"))[0]
    g, _ = make(tmp_path / "b", reading="by-moonlight")
    assert [lv for lv, _ in formats.check_assembly(g)] == ["note"]


def test_the_artifact_is_read_when_the_store_is_given(tmp_path):
    f, store = make(tmp_path)
    assert problems(f, tmp_path / "elsewhere") and "is not in the store" in problems(f, tmp_path / "elsewhere")[0]
    edit(f, lambda r: r["inputs"].pop("page:scan-a/0063"))  # the artifact read a page the record doesn't name
    assert any("they should be the same pages" in t for t in problems(f, store))
    f2, store2 = make(tmp_path / "c")
    out = json.loads(f2.read_text(encoding="utf-8"))["issue:1977-09-01/hands-off"]["assembly"]["output"]
    a = formats.artifact_path(store2, "assembly", out)
    a.write_bytes(gzip.compress(gzip.decompress(a.read_bytes()).replace(b'"A Title"', b'"Another"')))
    assert any("don't have the hash the record names" in t for t in problems(f2, store2))


# -- the search for missing parts, recorded beside the assembly in the same unit (stage "search")

def add_search(f: Path, store: Path, puzzles=None) -> None:
    """A search record and artifact as xword-ocr's writer makes them, beside the unit's assembly."""
    d = json.loads(f.read_text(encoding="utf-8"))
    unit, stages = next(iter(d.items()))
    asm = stages["assembly"]["output"]
    place = {"scan": "scan-a", "leaf": 26, "box": [10.0, 20.0, 300.0, 400.0]}
    puzzles = puzzles if puzzles is not None else [{
        "grid": {**place, "size": [15, 15]},
        "expects": [{"part": "grid", "has": {**place, "size": [15, 15]}},
                    {"part": "across", "has": {"share": 1.0, "parts": [place]}},
                    {"part": "down", "has": {"share": 0.6, "parts": [place]}, "short": ["D1", "D2"],
                     "missing": "2 of 30 Down clues not found"},
                    {"part": "key", "missing": "no answer grid with its black squares in this issue or the next"}],
        "missing": ["down", "key"],
        "tries": [{"step": "issue", "part": "key", "how": "keysearch", "result": "found",
                   "best": {"scan": "scan-a", "leaf": 63, "differ": 0}},
                  {"step": "issue", "part": "down", "result": "nothing fits"},
                  {"step": "pointed", "part": "down", "result": "no list of the issue is headed as continued"}],
        "linked": [{"part": "key", "as": "answer grid", "step": "issue", **place, "leaf": 63, "differ": 0}],
        "still_missing": ["down"],
        "requests": [{"part": "down", "scan": "scan-a", "leaves": [25], "kind": "look",
                      "why": "its Down list lacks its start (D1, D2): the page before the list's first was read"}]}]
    body = {"format": "assembly-record/1", "pubid": "games", "date": unit[6:16], "variant": unit.split("/")[1],
            "assembly": asm, "next": None, "puzzles": puzzles, "state": {"$id": 0}}
    raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
    h = "sha256:" + hashlib.sha256(raw).hexdigest()
    a = formats.artifact_path(store, "search", h)
    a.parent.mkdir(parents=True, exist_ok=True)
    a.write_bytes(gzip.compress(raw))
    stages["search"] = {"format": "assembly-record/1", "stage": "search", "version": "search/1",
                        "settings": {"whole": 0.95}, "inputs": {"assembly": asm, "page:scan-a/0063": H}, "output": h,
                        "made": "2026-11-25T23:00:00+00:00", "took": 1.6, "code": "xword-ocr 0.1.0"}
    f.write_text(json.dumps(d), encoding="utf-8")


def test_a_search_beside_the_assembly_passes_and_a_record_without_one_still_does(tmp_path):
    f, store = make(tmp_path)
    assert formats.check_assembly(f, store) == []  # no search: assembly-record/1 as before
    add_search(f, store)
    assert formats.check_assembly(f, store) == [] and formats.check_assembly(f) == []


def test_a_search_made_from_another_assembly_is_stale_not_broken(tmp_path):
    f, store = make(tmp_path)
    add_search(f, store)
    d = json.loads(f.read_text(encoding="utf-8"))
    next(iter(d.values()))["search"]["inputs"]["assembly"] = H
    f.write_text(json.dumps(d), encoding="utf-8")
    got = formats.check_assembly(f)
    assert [lv for lv, _ in got] == ["note"] and "stale" in got[0][1]


def test_a_missing_part_with_nothing_tried_or_asked_for_is_a_problem(tmp_path):
    f, store = make(tmp_path)
    add_search(f, store, puzzles=[{
        "grid": {"scan": "scan-a", "leaf": 26, "box": [1.0, 2.0, 3.0, 4.0]},
        "expects": [{"part": "key", "missing": "no key"}, {"part": "across", "has": {"share": 1.0}}],
        "missing": ["key"], "tries": [], "linked": [{"part": "across", "as": "clue list", "step": "issue"}],
        "still_missing": ["key"], "requests": [{"part": "key", "scan": "scan-a", "leaves": [], "kind": "maybe", "why": "x"}]}])
    got = problems(f, store)
    assert any("nothing was tried" in t for t in got)
    assert any("a link is not" in t for t in got)  # linked a part that wasn't missing
    assert any("a request is not" in t for t in got)
    f2, store2 = make(tmp_path / "b")
    add_search(f2, store2)
    d = json.loads(f2.read_text(encoding="utf-8"))
    next(iter(d.values()))["search"]["output"] = "sha256:" + "cd" * 32
    f2.write_text(json.dumps(d), encoding="utf-8")
    assert "its artifact is not in the store" in problems(f2, store2)[0]
