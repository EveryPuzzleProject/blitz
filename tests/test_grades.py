"""Every puzzle exits with a grade (blitz ship: grade_of, Rule.ship_grades, digest; design/v3-agent-forward.md), and the
check of the grade fields (formats/ship-record.md).

Run with: uv run --with pytest pytest tests/test_grades.py"""

import json

import pytest

from blitz import formats
from blitz.ship import AGENT, GRADES, SAMPLE_N, SHIPS, SITE, Rule, as_shipped, counts, digest, plan, record, rule_of, standing, write
from blitz.work import Stop
from test_ship import AI, AI_NO, CHECK, HELPER, HELPER_NO, OK, OWNER, P, _ai_no, _batch, proof

ALL = Rule(ai_ready="both", ship_grades=SHIPS)
# triage's record of a puzzle, as xword-ocr writes it: reasons (class, severity, items), blocking parts (kind), the ship check
FLAGGED = {"decision": "ready", "ship": {"ok": False, "findings": [{"code": "triage-doubt", "detail": "unsure"}]},
           "reasons": [{"code": "unsure", "class": "defect", "severity": "proof", "detail": "2: D4: looks cut short", "items": ["D4", "L3"]},
                       {"code": "gxd-confirmed", "class": "info", "severity": "", "detail": "40 of 70 pairs"}]}
GAPPY = {"decision": "not ready", "ship": {"ok": False, "findings": [{"code": "grid-unsolved", "detail": "2 square(s) unsolved", "cells": ["r1c1", "r1c2"]}],
                                           "incomplete": ["2 square(s) unsolved"]},
         "reasons": [{"code": "key-missing", "class": "defect", "severity": "stage", "detail": ""}],
         "blocking": [{"code": "key-missing", "part": "the answer key", "restart": "assembly", "kind": "missing-part", "part_id": "key", "detail": ""}]}
MIXED = {"decision": "not ready", "ship": {"ok": False},
         "blocking": [{"code": "verdict-wrong-text", "part": "text linked from another puzzle", "restart": "assembly", "kind": "mixed", "detail": "from the verdict"}]}
CRYPTIC = {"decision": "ready", "ship": {"ok": True}, "reasons": [{"code": "cryptic-no-key", "class": "gap", "severity": "", "detail": ""}]}


def _run(tmp_path, said, triage, rule=ALL):
    repo, proofs = _batch(tmp_path, said, triage)
    p = plan(repo, proofs, rule, "b")
    return repo, p, {r["pid"][-2:]: r for r in p["rows"]}


def _mixed_batch(tmp_path, rule=ALL):
    said = {P + "41": [_ai_no(P + "41", ("clue:D4", "Cut off?", "check the crop"), ("grid", "Is r2c2 a D?", "look"))],
            P + "42": [AI], P + "46": [HELPER_NO],
            P + "47": [{"id": f"setaside:{P}47", "answer": "set-aside", "note": "a cryptic", "by": "person", "at": "2026-10-20T00:00:00Z"}],
            P + "48": [{"id": f"drop:{P}48", "answer": "not-a-crossword", "note": "a maze", "by": "triage", "at": "2026-10-20T00:00:00Z"}]}
    triage = {P + "40": OK, P + "41": FLAGGED, P + "42": FLAGGED, P + "43": FLAGGED, P + "44": GAPPY, P + "45": MIXED, P + "46": OK,
              P + "47": OK, P + "48": OK, P + "49": CRYPTIC}
    return _run(tmp_path, said, triage, rule)


def test_each_grade_from_the_records(tmp_path):
    _, p, by = _mixed_batch(tmp_path)
    assert {k: r["grade"] for k, r in by.items()} == {
        "40": "clean", "41": "doubts", "42": "reviewed", "43": "doubts", "44": "incomplete", "45": "held", "46": "held",
        "47": "deferred", "48": "not-a-crossword", "49": "incomplete"}
    # reviewed: the AI reviewer's Ready settled what the checks flagged, and nothing stays open
    assert by["42"]["settled"]["kind"] == "ai" and by["42"]["flags"] == 1 and not by["42"]["doubts"]
    # doubts with an AI's Not ready: its own questions, each with its row on the proof page
    assert [(d["row"], d["code"]) for d in by["41"]["doubts"]] == [("clue:D4", "ai-question"), ("grid", "ai-question")]
    assert "check the crop" in by["41"]["doubts"][0]["text"]
    # doubts nobody reviewed: what the checks flagged, at the rows triage names
    assert by["43"]["doubts"] == [{"row": "clue:D4", "rows": ["clue:D4", "line:B3"], "text": "D4: looks cut short", "code": "unsure", "from": "triage"}]
    # incomplete: the gaps are named, with the stage each points to
    assert [(g["code"], g["stage"], g["row"]) for g in by["44"]["gaps"]] == [("grid-unsolved", "key reading", "grid"), ("key-missing", "assembly", "grid")]
    assert [g["code"] for g in by["49"]["gaps"]] == ["cryptic-no-key"]              # a gap triage records, though the ship check passes
    # held: a diagnosis names the stage (the structure), or the person whose word holds it
    assert by["45"]["diagnosis"] == {"stage": "assembly", "what": "text linked from another puzzle", "code": "verdict-wrong-text", "detail": ""}
    assert (by["46"]["diagnosis"]["code"], by["46"]["diagnosis"]["stage"]) == ("not-ready", "proof review")
    c = counts(p["rows"])
    assert sum(c["grades"].values()) == c["puzzles"] == 10 and set(c["grades"]) == set(GRADES)


def test_off_by_default_the_rule_decides_as_before(tmp_path):
    _, on, _ = _mixed_batch(tmp_path / "on")
    _, off, by = _mixed_batch(tmp_path / "off", Rule(ai_ready="both"))
    assert Rule().ship_grades == () and standing({}, [], check_ok=True, grade="clean")["status"] == "hold"
    assert [r["status"] for r in off["rows"]].count("shippable") == 0                 # nobody's Ready counts here: nothing ships
    assert {r["pid"]: r["grade"] for r in off["rows"]} == {r["pid"]: r["grade"] for r in on["rows"]}  # the grade doesn't depend on the option
    assert (by["40"]["reason"], by["41"]["reason"], by["44"]["reason"]) == ("no-ready", "not-ready", "needs-work")
    assert record(off)["rule"]["ship_grades"] == [] and record(off)["grades"]["ships"] == []


def test_shipping_by_grade(tmp_path):
    _, p, by = _mixed_batch(tmp_path)
    assert {k: r["status"] for k, r in by.items()} == {"40": "shippable", "41": "shippable", "42": "shippable", "43": "shippable", "44": "shippable",
                                                       "45": "held", "46": "held", "47": "out", "48": "out", "49": "shippable"}
    assert all(by[k]["rule"] == "grade" for k in ("40", "41", "43", "44"))
    assert "ships by its grade" in by["41"]["why"] and "open questions" in by["41"]["why"]
    assert "ships incomplete, by its grade: 2 square(s) unsolved" in by["44"]["why"]
    assert counts(p["rows"])["grade_ships"] == {"clean": 1, "reviewed": 1, "doubts": 2, "incomplete": 2, "held": 0, "deferred": 0, "not-a-crossword": 0}
    # only the grades the rule lists
    _, _, some = _mixed_batch(tmp_path / "some", Rule(ai_ready="both", ship_grades=("clean", "reviewed")))
    assert {k for k, r in some.items() if r["status"] == "shippable"} == {"40", "42"}
    assert some["44"]["grade"] == "incomplete" and some["44"]["status"] == "held"   # graded all the same


def test_every_protection_of_a_persons_word_stays():
    g = dict(check_ok=True, grade="doubts", rule=ALL)
    assert standing({}, [HELPER_NO], **g)["reason"] == "not-ready"                   # a person's Not ready holds
    assert standing({}, [HELPER_NO, AI_NO], **g)["reason"] == "not-ready"
    no = proof("Reviewer 2", "notready", "2026-10-23T00:00:00Z")
    assert standing({}, [no, AI], **g)["reason"] == "owner-hold"                     # the owner's decision overrides
    assert standing({"answer": "hold", "at": "2026-10-24T00:00:00Z", "by": "person"}, [], **g)["reason"] == "owner-hold"
    assert standing({}, [HELPER_NO, proof("Reviewer 2", "ready", "2026-10-23T00:00:00Z")], **g)["rule"] == "owner"
    assert standing({}, [AI_NO], **g)["rule"] == "grade"                             # an AI's Not ready stays open, and it ships
    assert standing({}, [AI_NO, HELPER], **g)["rule"] == "people"                    # a person's Ready is still what ships it
    assert standing({}, [], codes={"clue-typed"}, **g)["reason"] == "clue-typed"     # a hold code holds
    assert standing({}, [], codes={"clue-by-sequence"}, **g)["status"] == "hold"     # needs a person's Ready, whatever the grade
    assert standing({}, [OWNER], current=("bbb",), **g)["reason"] == "proof-stale"   # the owner's Ready on an older version: look again
    assert standing({}, [], check_ok=True, grade="held", rule=ALL)["status"] == "hold"
    assert standing({}, [AI, CHECK], check_ok=True, grade="incomplete", rule=Rule(ship_grades=("clean",)))["status"] == "hold"


def test_an_ai_never_overrides_a_person_and_its_not_ready_edits_are_not_applied(tmp_path):
    ai = _ai_no(P + "41", ("clue:A1", "The crop reads otherwise.", "fix it"))
    ai["proof"]["review"]["edits"] = {"clue:A1": "An AI's reading"}
    _, p, by = _run(tmp_path, {P + "41": [ai]}, {P + "41": FLAGGED})
    x = p["passing"][P + "41"]
    assert by["41"]["status"] == "shippable" and x["edits"] == [] and "An AI's reading" not in x["text"]
    assert x["text"] == (tmp_path / "h" / "proof" / "run1" / (P + "41") / "puzzle.xd").read_text(encoding="utf-8")


def test_the_grade_goes_to_the_record_and_provenance_and_never_into_the_xd(tmp_path):
    repo, p, _ = _mixed_batch(tmp_path)
    res = write(repo, p, "2026-11-25")
    assert len(res["written"]) == 6
    prov = {r["pid"][-2:]: r for r in map(json.loads, (repo / "provenance.jsonl").read_text(encoding="utf-8").splitlines())}
    assert prov["41"]["grade"]["grade"] == "doubts" and [d["row"] for d in prov["41"]["grade"]["doubts"]] == ["clue:D4", "grid"]
    assert prov["44"]["grade"]["gaps"][0]["what"] == "2 square(s) unsolved" and prov["40"]["grade"]["grade"] == "clean"
    assert prov["41"]["shipped"]["rule"] == "grade" and "no person's review" in prov["41"]["review"]
    for f in (repo / "xd").glob("*.xd"):
        text = f.read_text(encoding="utf-8").lower()
        assert "grade" not in text and "doubt" not in text                            # provenance, not the puzzle (design/xd-fields.md)
    rec = json.loads((repo / "pipeline" / "ship" / "b.json").read_text(encoding="utf-8"))
    assert rec["format"] == "ship-record/1" and rec["grades"] == {"order": list(GRADES), "ships": list(SHIPS)}
    assert formats.check([repo / "pipeline" / "ship" / "b.json", repo / "provenance.jsonl"])["problems"] == 0
    doc = json.loads((repo / "pipeline" / "ship" / "b" / "as-shipped" / f"{P}41.json").read_text(encoding="utf-8"))
    assert doc["grade"]["grade"] == "doubts" and len(doc["grade"]["doubts"]) == 2


def test_a_persons_ready_settles_what_was_flagged(tmp_path):
    _, _, by = _run(tmp_path, {P + "50": [HELPER], P + "51": [HELPER]}, {P + "50": FLAGGED, P + "51": MIXED}, Rule())
    assert (by["50"]["grade"], by["50"]["settled"]["kind"], by["50"]["status"]) == ("reviewed", "helper", "shippable")
    assert by["51"]["grade"] == "clean" and by["51"]["status"] == "shippable"       # their word ships it, whatever triage asked of the pipeline


def test_a_helpers_name_stays_out_of_the_sites_copy(tmp_path):
    _, p, _ = _run(tmp_path, {P + "50": [HELPER], P + "46": [HELPER_NO]}, {P + "50": FLAGGED, P + "46": OK})
    pub = {r["pid"][-2:]: r for r in record(p)["puzzles"]}
    mine = ("grade_why", "settled", "doubts", "gaps", "diagnosis")
    assert pub["50"]["settled"]["by"] == "a helper" and "pat" not in json.dumps([pub["50"][k] for k in mine])
    assert pub["46"]["grade"] == "held" and "sam (" not in json.dumps(pub["46"]) and "a helper" in pub["46"]["diagnosis"]["what"]
    assert "pat" not in json.dumps(as_shipped(p, record(p))[P + "50"]["grade"])


def test_the_option_is_per_batch_in_ship_rule_json(tmp_path):
    (tmp_path / "fixes").mkdir()
    f = tmp_path / "fixes" / "ship-rule.json"
    f.write_text(json.dumps({"ai_ready": "both", "batches": {"games-1980-82": {"ship_grades": ["clean", "reviewed", "doubts", "incomplete"]}}}), encoding="utf-8")
    assert rule_of(tmp_path, "games-1977-79").ship_grades == () and rule_of(tmp_path, "games-1980-82").ship_grades == SHIPS
    assert rule_of(tmp_path, "games-1980-82", ship_grades=[]).ship_grades == ()       # the command line's off
    f.write_text(json.dumps({"ship_grades": ["clean", "held"]}), encoding="utf-8")
    with pytest.raises(Stop):
        rule_of(tmp_path)


def test_the_digest_sample_walk_and_failures(tmp_path):
    clean = sorted(f"games19{i}-03-01-L030" for i in range(50, 75))                  # 25 clean puzzles, one an issue
    triage = {pid: OK for pid in clean} | {P + "90": FLAGGED, P + "91": GAPPY, P + "92": GAPPY, P + "93": MIXED}
    repo, p, by = _run(tmp_path, {}, triage)
    d = p["digest"]
    assert d["sample"]["per_grade"] == SAMPLE_N and d["sample"]["pool"] == {"clean": 25, "reviewed": 0, "doubts": 1}
    assert len(d["sample"]["picked"]["clean"]) == 10 and d["sample"]["picked"]["doubts"] == [P + "90"]
    assert {r["pid"] for r in p["rows"] if r.get("to_read")} == {pid for pids in d["sample"]["picked"].values() for pid in pids}
    assert digest(p["rows"], "b")["sample"]["picked"] == d["sample"]["picked"]        # the same each time the record is made
    assert digest(p["rows"], "another")["sample"]["picked"]["clean"] != d["sample"]["picked"]["clean"]
    # the walk: what ships, by grade then id; a held puzzle is not in it
    assert d["walk"][:25] == clean and d["walk"][25:] == [P + "90", P + "91", P + "92"]
    assert [r["grade_order"] for r in sorted(p["rows"], key=lambda r: r["grade_order"])] == list(range(29))
    # the kinds of failure, ranked by puzzles
    top = d["failures"][0]
    assert (top["puzzles"], top["kind"], top["pids"]) == (2, "gap", [P + "91", P + "92"])
    assert {(f["kind"], f["code"]) for f in d["failures"]} == {("gap", "grid-unsolved"), ("gap", "key-missing"), ("doubt", "unsure"), ("held", "verdict-wrong-text")}
    rec = record(p)
    assert rec["walk"] == d["walk"] and rec["sample"] == d["sample"] and rec["failures"] == d["failures"]


def test_the_check_of_the_grade_fields(tmp_path):
    repo, p, _ = _mixed_batch(tmp_path)
    f = tmp_path / "ship.json"

    def problems(change):
        rec = json.loads(json.dumps(record(p)))
        change(rec, {r["pid"][-2:]: r for r in rec["puzzles"]})
        f.write_text(json.dumps(rec), encoding="utf-8")
        return [t for _, lv, t in formats.check([f])["lines"] if lv == "problem"]

    assert problems(lambda rec, by: None) == []
    assert any("not one of" in t for t in problems(lambda rec, by: by["40"].update(grade="fine")))
    assert any("held, with no diagnosis" in t for t in problems(lambda rec, by: by["45"].update(diagnosis=None)))
    assert any("lists none" in t for t in problems(lambda rec, by: by["43"].update(doubts=[])))
    assert any("not a proof-page row key" in t for t in problems(lambda rec, by: by["43"]["doubts"][0].update(row="clue:title")))
    assert any("which never ships" in t for t in problems(lambda rec, by: by["45"].update(status="shippable")))
    assert any("counts.grades.clean" in t for t in problems(lambda rec, by: rec["counts"]["grades"].update(clean=9)))
    assert any("to_read and sample.picked" in t for t in problems(lambda rec, by: by["40"].update(to_read=False)))
    assert any("walk is not exactly" in t for t in problems(lambda rec, by: rec["walk"].pop()))
    # a record from before the grades is a valid older form: a note
    rec = record(p)
    for r in rec["puzzles"]:
        for k in ("grade", "grade_why", "flags", "settled", "doubts", "gaps", "diagnosis", "grade_order", "to_read"):
            r.pop(k)
    f.write_text(json.dumps(rec), encoding="utf-8")
    res = formats.check([f])
    assert res["problems"] == 0 and res["notes"] == 1


# ---- the scope rule and the stubs of deferred puzzles (ship.scope_of, recorded_kind) ----

def test_a_kind_the_scope_defers_leaves_the_batch_as_a_stub(tmp_path):
    from blitz.ship import recorded_kind, scope_of

    triage = {P + "40": OK, P + "49": CRYPTIC, P + "44": GAPPY}
    repo, proofs = _batch(tmp_path, {}, triage)
    assert scope_of(repo) == {} and recorded_kind(CRYPTIC) == ("cryptic", "triage: cryptic-no-key") and recorded_kind(OK) == ("", "")
    before = {r["pid"][-2:]: r for r in plan(repo, proofs, ALL, "b")["rows"]}
    assert before["49"]["grade"] == "incomplete" and "stub" not in before["49"]      # no rule: every kind is imported, as before
    (repo / "fixes" / "scope.json").write_text(json.dumps({"crossword": "import", "cryptic": "defer", "variety": "defer"}), encoding="utf-8")
    p = plan(repo, proofs, ALL, "b")
    by = {r["pid"][-2:]: r for r in p["rows"]}
    assert (by["49"]["status"], by["49"]["reason"], by["49"]["grade"], by["49"]["queue"]) == ("out", "deferred", "deferred", "deferred")
    assert by["49"]["stub"] == {"pid": P + "49", "issue": "1978-03-01", "scan": "item", "leaf": "31", "size": "3x3", "kind": "cryptic",
                                "kind_from": "triage: cryptic-no-key", "why": by["49"]["why"]}
    assert by["40"]["status"] == by["44"]["status"] == "shippable"                  # a puzzle with no recorded kind is imported
    rec = record(p)
    assert rec["scope"]["rule"]["cryptic"] == "defer" and rec["scope"]["stubs"] == 1 and rec["counts"]["queues"]["deferred"] == 1
    assert sum(rec["counts"]["queues"].values()) == rec["counts"]["puzzles"] and P + "49" not in rec["walk"]
    f = tmp_path / "ship.json"
    f.write_text(json.dumps(rec), encoding="utf-8")
    assert formats.check([f])["problems"] == 0
    # one batch's own scope, as ship-rule.json has it; and a bad rule stops
    (repo / "fixes" / "scope.json").write_text(json.dumps({"cryptic": "defer", "batches": {"b": {"cryptic": "import"}}}), encoding="utf-8")
    assert scope_of(repo, "b") == {"cryptic": "import"} and scope_of(repo, "c") == {"cryptic": "defer"}
    (repo / "fixes" / "scope.json").write_text(json.dumps({"acrostic": "defer"}), encoding="utf-8")
    with pytest.raises(Stop):
        scope_of(repo)


def test_a_set_aside_puzzle_has_a_stub_and_a_shipped_one_is_never_deferred(tmp_path):
    aside = {"id": f"setaside:{P}47", "answer": "set-aside", "note": "a diagramless", "by": "person", "at": "2026-10-20T00:00:00Z"}
    repo, proofs = _batch(tmp_path, {P + "47": [aside], P + "49": [HELPER]}, {P + "47": OK, P + "49": CRYPTIC})
    p = plan(repo, proofs, Rule(), "b")
    by = {r["pid"][-2:]: r for r in p["rows"]}
    assert by["47"]["stub"]["kind"] == "" and "a diagramless" in by["47"]["stub"]["why"]   # no milestone recorded its kind: said so
    write(repo, p, "2026-11-25")                                                       # the cryptic ships on a person's Ready
    (repo / "fixes" / "scope.json").write_text(json.dumps({"cryptic": "defer"}), encoding="utf-8")
    again = {r["pid"][-2:]: r for r in plan(repo, proofs, Rule(), "b")["rows"]}
    assert again["49"]["status"] == "shipped" and "stub" not in again["49"]          # a rule written later takes nothing back
