"""blitz ship on puzzles read by hand (design/hand-read.md): the xd in ## sections is read and edited as the
blank-line form and shipped in its own sections; the World's own form (pairs, Labels) takes a clue edit on the run
the proof page showed it on, written back under its pair; the record ship reads is the one hand-packets wrote."""

import json
from dataclasses import replace

from blitz import handread
from blitz.ship import AGENT, SITE, Rule, plan, sectioned, unsection, write
from test_handread import MODERN, PAIRS, _make
from test_ship import proof

M, P = "nyw1914-01-04", "nyw1914-04-19"


def _packets(tmp_path):
    src, pages = _make(tmp_path, M, MODERN, [
        {"pair": "1-2", "text": "A pet.", "page": "puzzle", "box": [5, 100, 90, 120], "ref": "A1"},
        {"pair": "1-3", "text": "A taxi.", "page": "puzzle", "box": [5, 120, 90, 140], "ref": "D1"}])
    (src / f"{P}.xd").write_text(PAIRS, encoding="utf-8")
    (src / f"{P}.boxes.json").write_text((src / f"{M}.boxes.json").read_text(encoding="utf-8").replace(M, P), encoding="utf-8")
    root = tmp_path / "hand" / "nyw-1914-s1"
    handread.build_all(src, pages, root)
    return root


def _said(root, pid, edits, comments=()):
    r = proof(f"pat ({SITE})", "ready", "2026-11-17T00:00:00Z", SITE)
    r["id"] = f"proof:{pid}"
    r["proof"]["review"].update(xd=json.loads((root / pid / "review.json").read_text(encoding="utf-8"))["xd_fp"], edits=edits,
                                comments=[{"key": k, "text": t, "why": True} for k, t in comments])
    return r


def _repo(tmp_path, recs):
    repo = tmp_path / "nyw"
    (repo / "fixes").mkdir(parents=True, exist_ok=True)
    (repo / "fixes" / "decisions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")
    return repo


def _row(p, pid):
    return next(r for r in p["rows"] if r["pid"] == pid)


def test_the_section_form_reads_as_the_blank_line_form_and_back(tmp_path):
    root = _packets(tmp_path)
    for pid, xd in ((M, MODERN), (P, PAIRS)):
        ocr = json.loads((root / pid / "ocr.json").read_text(encoding="utf-8"))
        plain, restore = unsection(xd, ocr)
        assert sectioned(xd) and not sectioned(plain) and restore(plain) == xd
    plain, _ = unsection(MODERN)
    assert plain.split("\n\n\n")[1] == "_CAT\n_A__\n_B__" and "D1 ^Printed: 1-3" in plain
    # the World's own form: a clue on a run is read under the run's label, the diagonal stays under its pair
    plain, restore = unsection(PAIRS, json.loads((root / P / "ocr.json").read_text(encoding="utf-8")))
    assert "A1. A pet. ~ CAT" in plain and "D2. A pull. ~ TOW" in plain and "1-4. Diagonal. ~ C_W" in plain
    # a block ship adds after the clues (a corrected key letter's note) is a Notes section at the end
    assert restore(plain.rstrip("\n") + "\n\n\nAnswer key corrected:\nX.\n").endswith("r3c3\n\n\n## Notes\nAnswer key corrected:\nX.\n")


def test_hand_packets_writes_the_ship_check_ship_reads(tmp_path):
    root = _packets(tmp_path)
    t = {r["pid"]: r for r in json.loads((root / "triage.json").read_text(encoding="utf-8"))["puzzles"]}
    assert set(t) == {M, P} and t[M]["decision"] == "ready"
    assert [f["code"] for f in t[M]["ship"]["findings"]] == ["no-author"] and t[M]["ship"]["incomplete"] == []
    off = next(f for f in t[P]["ship"]["findings"] if f["code"] == "clue-off-grid")
    assert off["items"] == ["1-4"] and t[P]["ship"]["incomplete"] == []  # said, not holding
    unsolved = handread.ship_check(MODERN.replace("_CAT\n", "_C??\n"))
    assert unsolved["incomplete"] == ["2 square(s) unsolved"] and unsolved["findings"][-1]["cells"] == ["r1c3", "r1c4"]
    # a run with no clue line is said (FUN left some words unclued), not held; one all givens wants none
    allgiven = MODERN.replace(".G..\n", ".GGG\n").replace("A1. A pet. ~ CAT\nA1 ^Printed: 1-2\n", "")
    assert "clue-missing" not in {f["code"] for f in handread.ship_check(allgiven)["findings"]}
    gone = handread.ship_check(MODERN.replace("D1. A taxi. ~ CAB\nD1 ^Printed: 1-3\nD1 ^Note: misprint: the pair that fits is 1-4\n", ""))
    assert gone["findings"][-1]["items"] == ["D1"] and gone["incomplete"] == []


def test_a_ready_with_edits_ships_the_hand_read_xd_in_its_own_sections(tmp_path):
    root = _packets(tmp_path)
    repo = _repo(tmp_path, [
        _said(root, M, {"clue:A1": "A small pet.", "cell:r3c2": "T", "clue:D1^Note": "the pair that fits is 1-4"},
              comments=[("clue:A1", "the crop reads 'A small pet.'"), ("cell:r3c2", "the key prints T")]),
        _said(root, P, {"clue:A1": "A house pet."}, comments=[("clue:A1", "the crop reads 'A house pet.'")])])
    p = plan(repo, root, Rule())
    assert (_row(p, M)["status"], _row(p, P)["status"]) == ("shippable", "shippable"), (_row(p, M)["why"], _row(p, P)["why"])
    assert (_row(p, M)["xdid"], _row(p, P)["xdid"]) == (M, P)                     # named by its xdid already: no new pin
    assert p["pins"] == []
    m = p["passing"][M]["text"]
    assert m == (MODERN.replace("A1. A pet. ~ CAT", "A1. A small pet. ~ CAT").replace("_B__\n\n\n## Clues", "_T__\n\n\n## Clues")
                 .replace("D1. A taxi. ~ CAB", "D1. A taxi. ~ CAT").replace("D1 ^Note: misprint: the pair", "D1 ^Note: the pair"))
    assert p["passing"][P]["text"] == PAIRS.replace("1-2. A pet. ~ CAT", "1-2. A house pet. ~ CAT")  # under its pair, as printed
    recs = {r["key"]: r for r in p["passing"][M]["edit_records"]}
    assert recs["clue:A1"]["before"] == "A pet." and recs["cell:r3c2"]["words"] == {"D1": ["CAB", "CAT"]}
    write(repo, p)
    assert (repo / "xd" / f"{M}.xd").read_text(encoding="utf-8") == m
    assert _row(plan(repo, root, Rule()), M)["status"] == "shipped"


def test_what_the_import_cant_apply_to_a_hand_read_puzzle_holds_it(tmp_path):
    root = _packets(tmp_path)
    repo = _repo(tmp_path, [_said(root, P, {"cell:r1c2": "U"}), _said(root, M, {})])
    (repo / "xd").mkdir()
    (repo / "xd" / f"{M}.xd").write_text("Title: shipped from the OCR\n", encoding="utf-8")
    p = plan(repo, root, Rule())
    # a key square in a puzzle with a clue no run names (the diagonal's answer can't follow it)
    assert _row(p, P)["reason"] == "edits-unapplied" and "1-4" in _row(p, P)["why"]
    # xd/ already has another file under its id (the OCR batch shipped it): the owner replaces it, not the import
    assert _row(p, M)["reason"] == "xd-exists"


U = "nyw1914-01-11"
UNSOLVED = MODERN.replace("_CAT\n_A__\n_B__", "_???\n_?__\n_?__").replace("~ CAT", "~ ???").replace("~ CAB", "~ ???")


def _unsolved(tmp_path):
    src, pages = _make(tmp_path, U, UNSOLVED, [
        {"pair": "1-2", "text": "A pet.", "page": "puzzle", "box": [5, 100, 90, 120], "ref": "A1"}])
    root = tmp_path / "hand" / "nyw-1914-s1"
    handread.build_all(src, pages, root)
    gap = json.loads((root / "triage.json").read_text(encoding="utf-8"))["puzzles"][0]["ship"]["incomplete"]
    assert gap == ["5 square(s) unsolved"]
    return root, gap


def _partial(root, by, via, missing, note="no printed key found"):
    r = _said(root, U, {})
    r["by"], r["via"] = by, via
    r["proof"]["review"]["partial"] = {"missing": missing, "note": note}
    return r


def test_a_persons_ready_to_ship_as_it_stands_ships_the_gaps_it_names(tmp_path):
    root, gap = _unsolved(tmp_path)
    repo = _repo(tmp_path, [_partial(root, f"pat ({SITE})", SITE, gap)])
    p = plan(repo, root, Rule())
    row = _row(p, U)
    assert row["status"] == "shippable", row["why"]
    assert "shipped as it stands" in row["why"] and "no printed key found" in row["why"]
    assert row["partial"] == {"missing": gap, "note": "no printed key found"}
    assert p["passing"][U]["text"] == UNSOLVED                      # the unknown squares ship as unknown
    write(repo, p)
    prov = json.loads((repo / "provenance.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert prov["partial"]["missing"] == gap and prov["partial"]["by"] == f"pat ({SITE})"


def test_only_a_person_and_only_the_gaps_named(tmp_path):
    root, gap = _unsolved(tmp_path)
    # a plain Ready: held as before
    assert _row(plan(_repo(tmp_path, [_said(root, U, {})]), root, Rule()), U)["reason"] == "incomplete"
    # an AI's Ready to ship as it stands never waives a gap (the owner's rule, 2026-11-23)
    ai = _partial(root, "Claude (AI proof reviewer, m)", AGENT, gap)
    assert _row(plan(_repo(tmp_path, [ai]), root, Rule(ai_ready="either")), U)["reason"] == "incomplete"
    # a person's that named another gap (the check found more since): held
    other = _partial(root, f"pat ({SITE})", SITE, ["2 square(s) unsolved"])
    assert _row(plan(_repo(tmp_path, [other]), root, Rule()), U)["reason"] == "incomplete"


def test_a_batch_ships_on_an_ai_ready_from_the_double_read_and_says_so(tmp_path):
    from blitz.ship import rule_of
    root = _packets(tmp_path)
    note = "read twice, blind; every difference settled on the scan (second-read/VERDICTS.md)"
    recs = handread.ai_ready_records(root, "Claude (double read)", note, hold={P}, at="2026-11-25T00:00:00Z")
    assert [r["id"] for r in recs] == [f"proof:{M}"] and recs[0]["via"] == AGENT
    repo = _repo(tmp_path, recs)
    # the publication's rule is off; the batch's own entry takes the AI's Ready, and may replace an earlier ship of M
    (repo / "fixes" / "ship-rule.json").write_text(json.dumps({"ai_ready": "off", "batches": {
        "nyw-1914-s1": {"ai_ready": "ai", "replace": [M]}}}), encoding="utf-8")
    assert rule_of(repo).ai_ready == "off" and rule_of(repo, "other").replace == ()
    rule = rule_of(repo, "nyw-1914-s1")
    assert (rule.ai_ready, rule.replace) == ("ai", (M,))
    # M was shipped before from the OCR batch: the hand-read reading takes its place, and says so
    (repo / "xd").mkdir()
    (repo / "xd" / f"{M}.xd").write_text("Title: from the OCR\n", encoding="utf-8")
    (repo / "provenance.jsonl").write_text(json.dumps({"xdid": M, "pid": M + "-L000", "batch": "nyw-1914-c1"}) + "\n", encoding="utf-8")
    p = plan(repo, root, rule, "nyw-1914-s1")
    m, held = _row(p, M), _row(p, P)
    assert m["status"] == "shippable" and "replaces xd/" in m["why"] and f"{M}-L000" in m["why"]
    assert m["review"] == f"read by hand; {note}; an AI's Ready; no person's review; by the AI proof reviewer's Ready"
    assert held["reason"] == "no-ready"                          # held for a person: no AI Ready was written for it
    write(repo, p)
    row = json.loads((repo / "provenance.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert row["review"] == m["review"] and row["replaces"]["pid"] == f"{M}-L000" and row["replaces"]["batch"] == "nyw-1914-c1"
    assert (repo / "xd" / f"{M}.xd").read_text(encoding="utf-8") == MODERN
    # a plain AI Ready under the publication's own rule (off) ships nothing
    assert _row(plan(repo, root, rule_of(repo), "nyw-1914-s1"), P)["reason"] == "no-ready"


def test_a_keep_on_a_printed_line_ships_when_the_xd_has_a_printed_section(tmp_path):
    xd = MODERN.replace("## Grid", "## Printed\ncredit: By someone.\n\n\n## Grid")
    src, pages = _make(tmp_path, M, xd, [{"pair": "1-2", "text": "A pet.", "page": "puzzle", "box": [5, 100, 90, 120], "ref": "A1"}])
    root = tmp_path / "hand" / "nyw-1914-s1"
    handread.build_all(src, pages, root)
    keep = _said(root, M, {"keep:B1": False})
    p = plan(_repo(tmp_path, [keep]), root, Rule())
    assert _row(p, M)["status"] == "shippable", _row(p, M)["why"]
    assert p["passing"][M]["text"] == xd                       # ## Printed keeps every printed line; the keep is the edition's
    fix = _said(root, M, {"line:B1": "By some one."})
    assert _row(plan(_repo(tmp_path, [fix]), root, Rule()), M)["reason"] == "edits-unapplied"


def test_owner_stale_lapse_lets_an_ai_ready_on_the_current_version_ship(tmp_path):
    from blitz.ship import standing
    old = proof("oops6498 (review site)", "ready", "2026-11-20T00:00:00Z", SITE, xd="old")
    ai = proof("Claude (double read)", "ready", "2026-11-25T00:00:00Z", AGENT, xd="new")
    ai["note"] = "read twice, blind"
    rule = Rule(ai_ready="ai", owner=("oops6498",))
    assert standing({}, [old, ai], current=("new",), rule=rule)["reason"] == "proof-stale"     # the default: look again
    st = standing({}, [old, ai], current=("new",), rule=replace(rule, owner_stale="lapse"))
    assert st["status"] == "ship" and st["rule"] == "ai" and "earlier version" in st["why"] and st["lapsed"]["at"].startswith("2026-11-20")
    # a Not ready, the owner's or a helper's, still holds on any version
    no = proof("oops6498 (review site)", "notready", "2026-11-20T00:00:00Z", SITE, xd="old")
    assert standing({}, [no, ai], current=("new",), rule=replace(rule, owner_stale="lapse"))["status"] == "hold"
    helper_no = proof(f"pat ({SITE})", "notready", "2026-11-21T00:00:00Z", SITE, xd="old")
    assert standing({}, [old, helper_no, ai], current=("new",), rule=replace(rule, owner_stale="lapse"))["reason"] == "not-ready"


def test_a_field_form_transcription_is_its_own_edition():
    from blitz.edition import make
    xd = MODERN.replace("## Grid", "## Printed\nintro: Fill in the squares.\n\n\n## Grid")
    ed = make(xd, printed=[{"label": "intro", "text": "Fill in the squares."}])
    assert ed["text"] == xd and ed["held"] == [] and ed["notes"] == []       # no Puzzle notes block: ## Printed has it
    marked = make(xd, marks=[{"key": "clue:A1", "printed": "pet", "meant": "pat", "by": "x"}])
    assert marked["text"] is None and marked["held"][0]["code"] == "mark-unplaced"  # a site mark has no place in it yet
