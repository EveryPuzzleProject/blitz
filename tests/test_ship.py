"""The ship rule (blitz ship: src/blitz/ship.py standing()) and the import's edits.

Run with: uv run --with pytest pytest tests/test_ship.py"""

from blitz.ship import AGENT, SITE, Rule, apply_edits, refused, standing, to_gxd


def proof(by, answer, at, via="watch", xd="aaa", note=""):
    return {"id": "proof:p", "answer": answer, "by": by, "at": at, "via": via, "note": note,
            "proof": {"review": {"xd": xd, "edits": {}}}}


OWNER = proof("Reviewer 2", "ready", "2026-10-19T00:00:00Z")
HELPER = proof(f"pat ({SITE})", "ready", "2026-10-20T00:00:00Z", SITE)
HELPER_NO = proof(f"sam ({SITE})", "notready", "2026-10-21T00:00:00Z", SITE, note="D4 is wrong")
AI = proof("Claude (AI proof reviewer, m)", "ready", "2026-10-22T00:00:00Z", AGENT)
AI_NO = proof("Claude (AI proof reviewer, m)", "notready", "2026-10-22T00:00:00Z", AGENT)
CHECK = proof("the ship check (xword-ocr shipcheck)", "ready", "2026-10-27T00:00:00Z", AGENT)


def test_default_one_persons_ready_ships():
    assert standing({}, [HELPER])["status"] == "ship"
    assert standing({}, [HELPER])["rule"] == "people"
    assert standing({}, [OWNER])["rule"] == "owner"


def test_default_an_ai_ready_is_not_the_one_ready():
    r = standing({}, [AI, CHECK], check_ok=True)
    assert (r["status"], r["reason"]) == ("hold", "no-ready")


def test_ai_ready_option():
    both, either = Rule(ai_ready="both"), Rule(ai_ready="either")
    assert standing({}, [AI, CHECK], check_ok=True, rule=both)["rule"] == "ai"
    assert standing({}, [AI], check_ok=False, rule=both)["status"] == "hold"      # the reviewer alone isn't both
    assert standing({}, [CHECK], check_ok=True, rule=both)["status"] == "hold"    # nor the check alone
    assert standing({}, [AI], check_ok=False, rule=either)["status"] == "ship"
    assert standing({}, [CHECK], check_ok=True, rule=either)["status"] == "ship"
    assert standing({}, [AI_NO], check_ok=True, rule=either)["reason"] == "not-ready"  # an AI's Not ready still holds


def test_any_not_ready_holds_for_the_owner():
    assert standing({}, [HELPER, HELPER_NO])["reason"] == "not-ready"
    assert standing({}, [HELPER, AI_NO])["reason"] == "not-ready"
    assert "D4 is wrong" in standing({}, [HELPER, HELPER_NO])["why"]


def test_the_owners_decision_overrides():
    later = proof("Reviewer 2", "ready", "2026-10-23T00:00:00Z")
    assert standing({}, [HELPER_NO, AI_NO, later])["status"] == "ship"
    no = proof("Reviewer 2", "notready", "2026-10-23T00:00:00Z")
    assert standing({}, [HELPER, AI, no], check_ok=True, rule=Rule(ai_ready="either"))["reason"] == "owner-hold"
    # the batch page's Ship / Hold, when it is the later of the owner's two
    assert standing({"answer": "hold", "at": "2026-10-24T00:00:00Z", "by": "person"}, [later])["reason"] == "owner-hold"
    assert standing({"answer": "ship", "at": "2026-10-24T00:00:00Z", "by": "person"}, [HELPER_NO])["status"] == "ship"
    assert standing({"answer": "hold", "at": "2026-10-18T00:00:00Z", "by": "person"}, [later])["status"] == "ship"


def test_a_ready_on_an_earlier_version_does_not_count():
    r = standing({}, [HELPER], current=("bbb",))
    assert (r["status"], r["reason"]) == ("hold", "proof-stale")
    assert standing({}, [HELPER], current=("bbb", "aaa"))["status"] == "ship"
    assert standing({}, [OWNER], current=("bbb",))["reason"] == "proof-stale"


def test_an_ai_not_ready_on_the_current_version_holds():
    r = standing({}, [AI_NO, HELPER], current=("aaa",))
    assert (r["status"], r["reason"]) == ("hold", "not-ready")
    assert not any(x["stale"] for x in r["said"])
    assert standing({}, [AI_NO], current=())["reason"] == "not-ready"  # no version recorded for the packet: it stands


def test_an_ai_not_ready_on_an_earlier_version_goes_stale_as_a_ready_does():
    r = standing({}, [AI_NO], current=("bbb",))
    assert (r["status"], r["reason"]) == ("hold", "proof-stale")
    assert "Not ready was on an earlier version" in r["why"]
    assert [(x["answer"], x["stale"]) for x in r["said"]] == [("notready", True)]  # still shown, as stale


def test_a_persons_not_ready_on_an_earlier_version_still_holds():
    for no in (HELPER_NO, proof("Reviewer 2", "notready", "2026-10-23T00:00:00Z", note="the key is wrong")):
        r = standing({}, [no, proof(f"pat ({SITE})", "ready", "2026-10-20T00:00:00Z", SITE, xd="bbb")], current=("bbb",))
        assert r["status"] == "hold" and r["reason"] in ("not-ready", "owner-hold")
        assert not any(x["stale"] for x in r["said"])


def test_a_stale_ai_not_ready_and_a_current_ready_ships():
    ready = proof(f"pat ({SITE})", "ready", "2026-10-25T00:00:00Z", SITE, xd="bbb")
    r = standing({}, [AI_NO, ready], current=("bbb",))
    assert (r["status"], r["rule"], r["apply"]) == ("ship", "people", [ready])
    ai, check = ({**x, "proof": {"review": {"xd": "bbb", "edits": {}}}} for x in (AI, CHECK))
    r = standing({}, [AI_NO, {**ai, "by": "Claude (AI proof reviewer, m2)"}, check], check_ok=True, current=("bbb",), rule=Rule(ai_ready="both"))
    assert (r["status"], r["rule"]) == ("ship", "ai")
    # the owner's Ready no longer says it is over a Not ready that doesn't stand
    mine = proof("Reviewer 2", "ready", "2026-10-26T00:00:00Z", xd="bbb")
    assert "over a Not ready" not in standing({}, [AI_NO, mine], current=("bbb",))["why"]
    assert "over a Not ready" in standing({}, [AI_NO, mine], current=("aaa", "bbb"))["why"]


def test_hold_codes_hold_whoever_said_ready():
    r = standing({}, [OWNER, HELPER], codes={"clue-typed", "unsure"})
    assert (r["status"], r["reason"]) == ("hold", "clue-typed")
    assert standing({}, [OWNER], codes={"clue-typed"}, rule=Rule(hold_codes=()))["status"] == "ship"


def test_ignored_reviewers_do_not_count():
    test = proof(f"walkthrough test ({SITE})", "ready", "2026-10-21T00:00:00Z", SITE)
    assert standing({}, [test])["status"] == "ship"
    assert standing({}, [test], rule=Rule(ignore=("walkthrough test",)))["reason"] == "no-ready"


def test_the_owners_review_site_account_is_the_owner():
    mine = Rule(owner=("pat",))
    assert standing({}, [HELPER, AI_NO])["reason"] == "not-ready"                 # a helper's Ready doesn't override
    r = standing({}, [HELPER, AI_NO], rule=mine)                                  # the owner's does
    assert (r["status"], r["rule"]) == ("ship", "owner")
    no = proof(f"pat ({SITE})", "notready", "2026-10-25T00:00:00Z", SITE)
    assert standing({}, [AI, CHECK, no], check_ok=True, rule=Rule(owner=("pat",), ai_ready="both"))["reason"] == "owner-hold"
    assert standing({}, [HELPER_NO, HELPER], rule=mine)["status"] == "ship"       # as in their own tools: over a helper's Not ready too


XD = """Title: T
Author: A
Date: 1978-03-01
Source: https://archive.org/details/item/page/n30/mode/2up
Text-Review: AI reviewer: 1 change(s)


AB#
CDE
#FG


A1. One ~ AB
A3. Two ~ CDE
A5. Three ~ FG

D1. Four ~ AC
D2. Five ~ BDF
D4. Six ~ EG
A1 ^Easy: Uno


OCR review flags:
A1: missing
"""


def test_apply_edits_round_trip_and_answers():
    assert apply_edits(XD, {})[0] == XD
    out, done = apply_edits(XD, {"cell:r2c2": "x", "clue:A3": "Deux", "clue:A1^Easy": "Un", "meta:title": "New"})
    assert sorted(done) == ["cell:r2c2", "clue:A1^Easy", "clue:A3", "meta:title"]
    assert "A3. Deux ~ CXE" in out and "D2. Five ~ BXF" in out and "A1 ^Easy: Un" in out
    assert out.startswith("Title: New\nAuthor: A") and out.endswith("OCR review flags:\nA1: missing\n")


def test_refused_edits():
    assert refused({"clue:A1": "x", "line:B3": "y", "ev:title": "2", "cell:r1c1": "AB"}, XD) == ["cell:r1c1", "ev:title", "line:B3"]
    assert refused({"clue:A1": "x"}, XD.replace("Date:", "Clues: linked ends\nDate:")) == ["clue:A1"]


def test_to_gxd_is_the_puzzle_only():
    out = to_gxd(XD.replace("Author: A", "Author: Mr.Bill  Smith,"), ["Printed “hint”"])
    assert out.startswith("Title: T\nAuthor: Bill Smith\nDate: 1978-03-01\n\n\nAB#")
    assert "Source" not in out and "OCR review flags" not in out and "A1 ^Easy: Uno" in out
    assert out.endswith('Printed "hint"\n')


# ---- the queues: what the batch page asks of people (ship.queues, in the batch's ship record) ----

import json

from blitz import ship as shipmod
from blitz.ship import QUEUES, counts, plan, record, spot, write


def _ai_no(pid, *comments):
    r = proof("Claude (AI proof reviewer, m)", "notready", "2026-10-22T00:00:00Z", AGENT, xd="fp", note="n")
    r["id"] = f"proof:{pid}"
    r["proof"]["review"]["comments"] = [{"key": k, "text": f"Flag for the maintainer: {t} Suggest: {sg}"} for k, t, sg in comments]
    return r


def _batch(tmp_path, said, triage):
    """A publication repo and a run's packets: {pid: [ledger records]}, {pid: triage's row without its pid}."""
    repo, proofs = tmp_path / "games", tmp_path / "h" / "proof" / "run1"
    (repo / "fixes").mkdir(parents=True)
    recs = []
    for i, pid in enumerate(triage):
        d = proofs / pid
        d.mkdir(parents=True)
        (d / "puzzle.xd").write_text(XD, encoding="utf-8")
        (d / "review.json").write_text(json.dumps({"xd_fp": "fp", "matches_xd": True}), encoding="utf-8")
        (d / "ocr.json").write_text(json.dumps({"stages": {"pages": {"page.jpg": ["item", 30 + i]}}}), encoding="utf-8")
        for r in said.get(pid, []):
            r = json.loads(json.dumps(r))
            if r["id"] == "proof:p":
                r["id"] = f"proof:{pid}"
                r["proof"]["review"]["xd"] = "fp"
            recs.append(r)
    (repo / "fixes" / "decisions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")
    t = tmp_path / "h" / "triage" / "run1"
    t.mkdir(parents=True)
    (t / "triage.json").write_text(json.dumps({"puzzles": [{"pid": pid, **row} for pid, row in triage.items()]}), encoding="utf-8")
    return repo, proofs


OK = {"decision": "ready", "ship": {"ok": True}}
DOUBT = {"decision": "ready", "ship": {"ok": False, "findings": [{"code": "triage-doubt"}]}}
P = "games1978-03-01-L0"


def _fixture(tmp_path):
    said = {
        P + "30": [AI, CHECK],                                                     # the AI's Ready and the check: ships
        P + "31": [_ai_no(P + "31", ("ev:title", "Is it untitled?", "confirm"), ("clue:A1", "Cut off?", "check"))],
        P + "32": [_ai_no(P + "32", ("ev:title", "Is it untitled?", "confirm"))],
        P + "33": [_ai_no(P + "33", ("grid:r2c2", "Is this square D?", "look"))],
        P + "34": [AI],                                                            # the AI alone, the check doesn't pass
        P + "36": [HELPER],                                                        # a person's Ready
        P + "37": [{"id": f"setaside:{P}37", "answer": "set-aside", "note": "a cryptic", "by": "person", "at": "2026-10-20T00:00:00Z"}],
        P + "38": [{"id": f"drop:{P}38", "answer": "not-a-crossword", "note": "a maze", "by": "triage", "at": "2026-10-20T00:00:00Z"}],
        P + "39": [AI, CHECK],                                                     # passes the rule, but incomplete
    }
    triage = {P + "30": OK, P + "31": DOUBT, P + "32": DOUBT, P + "33": DOUBT, P + "34": DOUBT,
              P + "35": {"decision": "not ready", "ship": {"ok": False},
                         "blocking": [{"code": "key-missing", "part": "the key", "restart": "assembly", "detail": ""}]},
              P + "36": DOUBT, P + "37": OK, P + "38": OK,
              P + "39": {"decision": "ready", "ship": {"ok": True, "findings": [{"code": "grid-unsolved"}], "incomplete": ["2 square(s) unsolved"]}}}
    repo, proofs = _batch(tmp_path, said, triage)
    return repo, plan(repo, proofs, Rule(ai_ready="both"), "b")


def test_every_puzzle_is_in_one_queue_and_the_counts_add_up(tmp_path):
    repo, p = _fixture(tmp_path)
    by = {r["pid"][-2:]: r for r in p["rows"]}
    assert {k: r["queue"] for k, r in by.items()} == {
        "30": "shippable", "31": "question", "32": "question", "33": "question", "34": "unchecked", "35": "broken",
        "36": "shippable", "37": "set-aside", "38": "not-a-crossword", "39": "broken"}
    c = counts(p["rows"])
    assert sum(c["queues"].values()) == c["puzzles"] == len(p["rows"]) and set(c["queues"]) == set(QUEUES)
    rec = record(p)
    assert sorted(r["order"] for r in rec["puzzles"]) == list(range(len(p["rows"])))    # one place each in the walk
    assert all(r["queue"] in QUEUES for r in rec["puzzles"])


def test_questions_carry_who_asked_the_row_and_the_group(tmp_path):
    repo, p = _fixture(tmp_path)
    by = {r["pid"][-2:]: r for r in p["rows"]}
    a = by["31"]["asks"]
    assert [(x["row"], x["group"], x["text"], x["suggest"]) for x in a] == [
        ("ev:title", "title", "Is it untitled?", "confirm"), ("clue:A1", "", "Cut off?", "check")]
    assert a[0]["who"].startswith("Claude") and a[0]["kind"] == "ai"
    assert by["33"]["asks"][0]["row"] == "cell:r2c2"                                   # the proof page's key for a square
    assert p["groups"] == [{"key": "title", "label": "the title", "puzzles": 2, "asks": 2}]
    # the walk: the shared question first, the puzzle with nothing else to ask before the one with more; then one puzzle's own
    walk = [r["pid"][-2:] for r in sorted(p["rows"], key=lambda r: r["order"]) if r["queue"] == "question"]
    assert walk == ["32", "31", "33"] and (by["32"]["group"], by["33"]["group"]) == ("title", "")
    assert not by["34"]["asks"] and not by["35"]["asks"]


def test_broken_puzzles_name_the_stage_they_point_to(tmp_path):
    repo, p = _fixture(tmp_path)
    by = {r["pid"][-2:]: r for r in p["rows"]}
    assert by["35"]["broken"] == [{"what": "the key", "stage": "assembly", "code": "key-missing", "detail": ""}]
    assert by["39"]["broken"] == [{"what": "2 square(s) unsolved", "stage": "key reading", "code": "incomplete", "detail": ""}]
    assert not by["31"]["broken"]


def test_an_ai_review_alone_is_not_reviewed(tmp_path):
    repo, p = _fixture(tmp_path)
    by = {r["pid"][-2:]: r for r in p["rows"]}
    assert not by["30"]["reviewed"] and not by["31"]["reviewed"] and not by["34"]["reviewed"]   # the AI, the check
    assert by["36"]["reviewed"]                                                                # a person
    assert counts(p["rows"])["reviewed"] == 1


def test_a_stale_ai_not_ready_leaves_the_question_queue_and_its_asks_are_not_asked(tmp_path):
    def earlier(r):  # the record as an earlier run's packet would have left it
        r = json.loads(json.dumps(r))
        r["proof"]["review"]["xd"] = "run1"
        return r
    person = {**HELPER_NO, "id": f"proof:{P}42", "proof": {"review": {"xd": "run1", "edits": {}, "comments": [{"key": "clue:D4", "text": "D4 is wrong"}]}}}
    said = {P + "40": [earlier(_ai_no(P + "40", ("ev:title", "Is it untitled?", "confirm")))],          # only the earlier run's AI question
            P + "41": [_ai_no(P + "41", ("ev:title", "Is it untitled?", "confirm"))],                   # asked on this version
            P + "42": [earlier(_ai_no(P + "42", ("ev:title", "Is it untitled?", "confirm"))), person],  # and a person's, on the earlier one
            P + "43": [earlier(_ai_no(P + "43", ("ev:title", "Is it untitled?", "confirm"))), AI, CHECK]}
    repo, proofs = _batch(tmp_path, said, {P + "40": OK, P + "41": OK, P + "42": OK, P + "43": OK})
    rows = {r["pid"][-2:]: r for r in plan(repo, proofs, Rule(ai_ready="both"), "b")["rows"]}
    assert [(k, r["queue"], r["reason"]) for k, r in sorted(rows.items())] == [
        ("40", "unchecked", "proof-stale"), ("41", "question", "not-ready"), ("42", "question", "not-ready"), ("43", "shippable", "")]
    assert rows["40"]["asks"] == [] and [a["row"] for a in rows["41"]["asks"]] == ["ev:title"]
    assert [(a["kind"], a["row"]) for a in rows["42"]["asks"]] == [("helper", "clue:D4")]  # the person's question only


def test_shipped_puzzles_are_never_in_the_walk(tmp_path, monkeypatch):
    repo, p = _fixture(tmp_path)
    monkeypatch.setattr(shipmod, "spot", lambda pid: pid[-2:] in ("30", "36", "31"))
    write(repo, p, "2026-11-10")
    rec = json.loads((repo / "pipeline" / "ship" / "b.json").read_text(encoding="utf-8"))
    by = {r["pid"][-2:]: r for r in rec["puzzles"]}
    shipped = [r for r in rec["puzzles"] if r["queue"] == "shipped"]
    assert {r["pid"][-2:] for r in shipped} == {"30", "36"} and rec["counts"]["queues"]["shipped"] == 2
    assert all(not r["asks"] and not r["broken"] for r in shipped)
    walk = [r for r in rec["puzzles"] if r["queue"] in ("question", "unchecked")]
    assert not {r["pid"] for r in walk} & {r["pid"] for r in shipped}
    assert max(r["order"] for r in walk) < min(r["order"] for r in shipped)
    # the spot-check sample: shipped puzzles only, fixed by the id
    assert [r["pid"][-2:] for r in rec["puzzles"] if r["spot_check"]] == ["30", "36"] and rec["counts"]["spot_check"] == 2
    assert not by["31"]["spot_check"]
    assert sum(rec["counts"]["queues"].values()) == rec["counts"]["puzzles"]


def test_the_spot_check_sample_is_fixed_by_the_id():
    ids = [f"games1978-03-01-L{i:03d}" for i in range(400)]
    assert [spot(i) for i in ids] == [spot(i) for i in ids]
    assert 20 <= sum(spot(i) for i in ids) <= 60                                       # about one in ten


def test_a_send_back_from_the_proof_page_moves_a_question_to_broken(tmp_path):
    """A person on the proof page says the question is the pipeline's (a Not ready with a sendback): the
    puzzle leaves the question queue for broken, with what they said and the stage it points to."""
    back = proof(f"sam ({SITE})", "notready", "2026-11-10T00:00:00Z", SITE)
    back["proof"]["review"]["sendback"] = {"kind": "mixed", "part": "", "note": "the notes hold a neighbour's clues"}
    said = {P + "31": [_ai_no(P + "31", ("meta:note", "Drop the block?", "drop it")), back],
            P + "32": [_ai_no(P + "32", ("meta:note", "Drop the block?", "drop it"))]}
    repo, proofs = _batch(tmp_path, said, {P + "31": DOUBT, P + "32": DOUBT})
    p = plan(repo, proofs, Rule(ai_ready="both"), "b")
    by = {r["pid"][-2:]: r for r in p["rows"]}
    assert (by["31"]["queue"], by["31"]["reason"], by["32"]["queue"]) == ("broken", "sent-back", "question")
    assert by["31"]["broken"] == [{"what": "sent back from the proof page: parts of two puzzles are mixed together", "stage": "assembly",
                                   "code": "sent-back", "detail": "the notes hold a neighbour's clues"}]
    assert not by["31"]["asks"] and by["31"]["reviewed"]
    pub = {r["pid"][-2:]: r for r in record(p)["puzzles"]}
    assert "sam" not in json.dumps(pub["31"])                                          # a helper's name stays out of the site's copy
    assert counts(p["rows"])["queues"]["broken"] == 1 and counts(p["rows"])["held_by"]["sent-back"] == 1


def test_the_xd_goes_up_with_the_packet():
    from blitz.site import FILES
    assert "puzzle.xd" in FILES                                                        # the proof page draws the xd's notes from it
