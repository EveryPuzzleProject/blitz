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
    # a linked-ends puzzle takes its own kinds (tests/test_ship_linked.py); a line's label or a header's evidence line still holds it
    linked = XD.replace("Date:", "Clues: linked ends\nDate:")
    assert refused({"clue:A1": "x", "line:B3": "y", "keep:B3": False, "num:r1c1": "3", "grid:r1c1": "_"}, linked) == []
    assert refused({"clue:A1": "x", "label:B3": "intro", "ev:title": "2"}, linked) == ["ev:title", "label:B3"]


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


# ---- candidate clue lists: decided on the proof page, applied by the import ----

from blitz.ship import apply_candidates

CAND = {"id": "D-alt1", "dir": "D", "slots": 3, "share": 1.0, "why": "1 lists fit Across and 2 Down, not two sets", "reads_as": "clues",
        "from": "assembly", "clues": {"D1": {"text": "Quatre"}, "D2": {"text": "Cinq"}, "D4": {"text": "Six, again"}}}


def test_removing_a_candidate_leaves_the_xd_as_it_is():
    for v in ("remove", "answers"):
        assert apply_candidates(XD, [CAND], {"candidate:D-alt1": v}) == (XD, ["candidate:D-alt1"], [])
    assert apply_candidates(XD, [CAND], {}) == (XD, [], [])
    assert refused({"candidate:D-alt1": "remove", "candidate:D-alt1x": "remove"}, XD) == ["candidate:D-alt1x"]
    assert refused({"candidate:D-alt1": "keep it"}, XD) == ["candidate:D-alt1"]


def test_a_candidate_taken_as_the_real_clues_replaces_the_list_and_says_so():
    out, done, partial = apply_candidates(XD, [CAND], {"candidate:D-alt1": "clues"})
    assert "D1. Quatre ~ AC\nD2. Cinq ~ BDF\nD4. Six, again ~ EG" in out and "A1. One ~ AB" in out and not partial
    assert "Clues: the Down clues are the list assembly recorded as a candidate" in out and "OCR review flags:\nA1: missing" in out
    assert out.count("\n\n\n") == XD.count("\n\n\n")  # still headers, grid, clues, notes
    short = {**CAND, "clues": {"D1": {"text": "Quatre"}}}
    out, done, partial = apply_candidates(XD, [short], {"candidate:D-alt1": "clues"})
    assert "D2. [missing] ~ BDF" in out and partial == ["the list chosen as the Down clues has no clue for D2 D4"]


def test_a_candidate_taken_as_a_second_set_becomes_its_metadata_lines():
    xd = XD.replace("A1 ^Easy: Uno\n", "")
    out, done, partial = apply_candidates(xd, [CAND], {"candidate:D-alt1": "second:easy"})
    assert "D1. Four ~ AC\nD1 ^Easy: Quatre\nD2. Five ~ BDF\nD2 ^Easy: Cinq\nD4. Six ~ EG\nD4 ^Easy: Six, again\n" in out
    assert partial == ["the ^Easy set has 3 of 6 clues"]  # one direction only: not a whole second set
    across = {**CAND, "id": "A-alt1", "dir": "A", "clues": {"A1": {"text": "Uno"}, "A3": {"text": "Dos"}, "A5": {"text": "Tres"}}}
    out, done, partial = apply_candidates(xd, [CAND, across], {"candidate:D-alt1": "second:Easy", "candidate:A-alt1": "second:Easy"})
    assert not partial and sorted(done) == ["candidate:A-alt1", "candidate:D-alt1"]
    assert "A1. One ~ AB\nA1 ^Easy: Uno\nA3. Two ~ CDE\nA3 ^Easy: Dos" in out and out.count("Clue sets: the ^Easy line") == 2
    # a reviewer's own fix to one of its clues is applied after, like any second set's
    assert "D2 ^Easy: Cinq!" in apply_edits(out, {"clue:D2^Easy": "Cinq!"})[0]


def _candidates(tmp_path, said, cands=(CAND,)):
    held = {"decision": "ready", "ship": {"ok": False, "findings": [{"code": "candidate-undecided"}]}}
    repo, proofs = _batch(tmp_path, said, {pid: held for pid in said})
    for pid in said:
        f = proofs / pid / "ocr.json"
        f.write_text(json.dumps({**json.loads(f.read_text(encoding="utf-8")), "candidates": list(cands)}), encoding="utf-8")
    return repo, proofs


def _decides(by, value, answer="ready", at="2026-11-11T00:00:00Z", via=SITE):
    r = proof(by, answer, at, via, xd="fp")
    r["proof"]["review"]["edits"] = {"candidate:D-alt1": value}
    return r


def test_an_undecided_candidate_holds_the_puzzle_on_a_question_at_its_row(tmp_path):
    ask = ("meta:note", "The notes hold an 'another list' block of a neighbour's clues. Drop the block?", "drop it")
    said = {P + "31": [_ai_no(P + "31", ask)],            # the AI asked about the notes: its question stays where it put it
            P + "32": [HELPER],                           # a person's Ready that decided nothing
            P + "33": [AI, CHECK]}                        # nobody asked: the pipeline's own question
    repo, proofs = _candidates(tmp_path, said)
    p = plan(repo, proofs, Rule(ai_ready="both"), "b")
    by = {r["pid"][-2:]: r for r in p["rows"]}
    assert [(r["queue"], r["reason"]) for r in (by["31"], by["32"])] == [("question", "not-ready"), ("question", "candidate-undecided")]
    # no guessing from a question's wording: the AI's stays on the notes, and the candidate gets the pipeline's own
    assert [(a["row"], a["group"], a["kind"]) for a in by["31"]["asks"]] == [("meta:note", "notes", "ai"), ("candidate:D-alt1", "candidate", "pipeline")]
    (a,) = by["32"]["asks"]
    assert (a["who"], a["row"], a["group"]) == ("assembly", "candidate:D-alt1", "candidate") and "3 of 3 slots" in a["text"]
    assert by["33"]["queue"] == "unchecked"               # the check doesn't pass while a candidate is undecided
    assert by["32"]["candidates"] == [{"id": "D-alt1", "dir": "D", "clues": 3, "slots": 3, "reads_as": "clues", "decision": ""}]
    assert {"key": "candidate", "label": "a candidate clue list", "puzzles": 2, "asks": 2} in p["groups"]
    assert not p["passing"]
    assert record(p)["puzzles"][0]["candidates"][0]["decision"] == ""


def test_a_persons_decision_releases_the_hold_and_the_import_applies_it(tmp_path):
    said = {P + "31": [_ai_no(P + "31", ("meta:note", "Drop the 'another list' block?", "drop it")),
                       _decides("Reviewer 2", "remove", via="watch")],                     # the owner: not this puzzle's
            P + "32": [_decides(f"pat ({SITE})", "clues")],                                  # a helper: these are the real clues
            P + "33": [_decides(f"pat ({SITE})", "second:Easy")],                            # a second set, one direction only
            P + "34": [_decides(f"pat ({SITE})", "remove", answer="notready")]}              # decided, but said Not ready
    repo, proofs = _candidates(tmp_path, said)
    p = plan(repo, proofs, Rule(ai_ready="both"), "b")
    by = {r["pid"][-2:]: r for r in p["rows"]}
    assert (by["31"]["status"], by["32"]["status"]) == ("shippable", "shippable")
    assert p["passing"][P + "31"]["text"] == XD and p["passing"][P + "31"]["edits"] == ["candidate:D-alt1"]
    assert "D1. Quatre ~ AC" in p["passing"][P + "32"]["text"]
    assert (by["33"]["reason"], by["33"]["queue"]) == ("candidate-partial", "broken") and "^Easy set has 4 of 6" in by["33"]["why"]
    assert (by["34"]["reason"], by["34"]["queue"]) == ("not-ready", "question")
    assert by["31"]["candidates"][0]["decision"] == "remove" and by["31"]["candidates"][0]["kind"] == "owner"
    # chosen in a Not ready: it doesn't count, the record says so, and the question is still asked
    c34 = by["34"]["candidates"][0]
    assert c34["decision"] == "" and c34["pending"] == {"decision": "remove", "kind": "helper", "at": "2026-11-11",
                                                         "why": "in a review that said Not ready"}
    assert [a["row"] for a in by["34"]["asks"] if a["kind"] == "pipeline"] == ["candidate:D-alt1"]
    assert "doesn't count yet" in by["34"]["asks"][-1]["text"]
    write(repo, p, "2026-11-11")
    prov = [json.loads(x) for x in (repo / "provenance.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {r["pid"][-2:]: r["edits"]["applied"] for r in prov} == {"31": ["candidate:D-alt1"], "32": ["candidate:D-alt1"]}


def test_candidate_pages_go_up_with_the_packet(tmp_path):
    from blitz.site import candidate_pages
    (tmp_path / "ocr.json").write_text(json.dumps({"scales": {"page.jpg": 0.2, "candidate_page.jpg": 0.2, "candidate_page-2.jpg": 0.2}}))
    assert sorted(candidate_pages(tmp_path)) == ["_src/candidate_page-2.jpg", "_src/candidate_page.jpg", "candidate_page-2.jpg", "candidate_page.jpg"]
    assert candidate_pages(tmp_path / "none") == []


def test_the_record_and_the_import_agree_on_whether_a_candidate_is_decided(tmp_path):
    """The cold review's case: a helper picks "remove" and says Not ready, then the owner says Ready without
    choosing. The choice doesn't count, the puzzle is held on the candidate, and the record says whose choice
    is pending and why. When the owner's Ready carries the choice, it ships."""
    from blitz.ship import candidate_decisions

    helper_no = _decides(f"pat ({SITE})", "remove", answer="notready", at="2026-11-11T00:00:00Z")
    owner = proof("Reviewer 2", "ready", "2026-11-12T00:00:00Z", xd="fp")
    repo, proofs = _candidates(tmp_path, {P + "31": [helper_no, owner],
                                          P + "32": [helper_no, _decides("Reviewer 2", "remove", at="2026-11-12T00:00:00Z", via="watch")]})
    p = plan(repo, proofs, Rule(ai_ready="both"), "b")
    by = {r["pid"][-2:]: r for r in p["rows"]}
    assert (by["31"]["reason"], by["31"]["queue"]) == ("candidate-undecided", "question")
    assert by["31"]["candidates"][0]["decision"] == "" and by["31"]["candidates"][0]["pending"]["kind"] == "helper"
    assert "A helper chose" in by["31"]["asks"][-1]["text"] and "pat" not in json.dumps(record(p))
    assert by["32"]["status"] == "shippable" and by["32"]["candidates"][0] == {
        "id": "D-alt1", "dir": "D", "clues": 3, "slots": 3, "reads_as": "clues", "decision": "remove", "kind": "owner", "at": "2026-11-12"}
    # a Ready on an earlier version doesn't count either
    old = _decides(f"pat ({SITE})", "remove")
    old["proof"]["review"]["xd"] = "an earlier version"
    assert candidate_decisions([old], Rule(), ("fp",))["D-alt1"]["pending"]["why"] == "in a Ready on an earlier version of the puzzle"
    assert candidate_decisions([old], Rule(), ())["D-alt1"]["decision"] == "remove"       # no version known: as standing() has it
    # an ignored account's choice, and a value that isn't one of the four
    assert candidate_decisions([_decides(f"pat ({SITE})", "remove")], Rule(ignore=("pat",)), ("fp",)) == {}
    assert candidate_decisions([_decides(f"pat ({SITE})", "second")], Rule(), ("fp",)) == {}


def test_an_ai_never_decides_a_candidate(tmp_path):
    """An AI reviewer's Ready that carries a candidate:<id> edit is not the decision: not under ai_ready either
    (where its Ready alone ships a puzzle), not with the owner's Ship on the batch page."""
    ai = _decides("Claude (AI proof reviewer, m)", "clues", at="2026-10-22T00:00:00Z", via=AGENT)
    ship_it = {"id": "batch:p", "answer": "ship", "by": "person", "at": "2026-11-12T00:00:00Z", "note": ""}
    said = {P + "31": [ai], P + "32": [ai, {**ship_it, "id": f"batch:{P}32"}]}
    repo, proofs = _candidates(tmp_path, said)
    for opt in ("either", "both"):
        p = plan(repo, proofs, Rule(ai_ready=opt), "b")
        by = {r["pid"][-2:]: r for r in p["rows"]}
        assert not p["passing"]
        assert (by["32"]["reason"], by["32"]["queue"]) == ("candidate-undecided", "question")
        assert all(c["decision"] == "" and "pending" not in c for r in by.values() for c in r["candidates"])
    assert (by["31"]["reason"]) == "no-ready"                                             # both: the check doesn't pass
    p = plan(repo, proofs, Rule(ai_ready="either"), "b")
    assert {r["pid"][-2:]: r["reason"] for r in p["rows"]} == {"31": "candidate-undecided", "32": "candidate-undecided"}


INCOMPLETE = {"decision": "ready", "ship": {"ok": False, "findings": [{"code": "clue-empty"}, {"code": "triage-doubt"}],
                                            "incomplete": ["clues with no text: A2 D19"]}}


def test_a_not_ready_on_a_puzzle_no_answer_makes_whole_waits_on_the_pipeline(tmp_path):
    """A question on a puzzle the ship check finds incomplete: answering it ships nothing, and the packet will be made
    again. It is the pipeline's, with the question kept on the card; the same question on a whole puzzle is asked."""
    said = {P + "31": [_ai_no(P + "31", ("ev:title", "Is it untitled?", "confirm"))],
            P + "32": [_ai_no(P + "32", ("ev:title", "Is it untitled?", "confirm"))]}
    repo, proofs = _batch(tmp_path, said, {P + "31": INCOMPLETE, P + "32": DOUBT})
    p = plan(repo, proofs, Rule(ai_ready="both"), "b")
    by = {r["pid"][-2:]: r for r in p["rows"]}
    assert (by["31"]["queue"], by["31"]["reason"], by["32"]["queue"], by["32"]["reason"]) == ("broken", "question-incomplete", "question", "not-ready")
    assert by["31"]["broken"] == [{"what": "clues with no text: A2 D19", "stage": "parts", "code": "incomplete", "detail": ""}]
    assert by["31"]["asks"] == [] and [(a["row"], a["text"]) for a in by["31"]["asked"]] == [("ev:title", "Is it untitled?")]
    assert by["31"]["why"].startswith("waiting on the pipeline: said Not ready by") and "no answer mends: clues with no text: A2 D19" in by["31"]["why"]
    assert p["groups"] == [{"key": "title", "label": "the title", "puzzles": 1, "asks": 1}]   # only the question that is asked
    rec = record(p)
    assert rec["counts"]["held_by"] == {"question-incomplete": 1, "not-ready": 1}
    assert next(r for r in rec["puzzles"] if r["pid"] == P + "31")["asked"][0]["text"] == "Is it untitled?"


def test_the_proofreads_a_ready_ships_are_walked_before_the_ones_it_cannot(tmp_path):
    repo, proofs = _batch(tmp_path, {}, {P + "31": INCOMPLETE, P + "32": DOUBT, P + "33": DOUBT})
    p = plan(repo, proofs, Rule(ai_ready="both"), "b")
    by = {r["pid"][-2:]: r for r in p["rows"]}
    assert {r["queue"] for r in p["rows"]} == {"unchecked"}
    assert [r["pid"][-2:] for r in sorted(p["rows"], key=lambda r: r["order"])] == ["32", "33", "31"]
    assert by["31"]["also"] == ["clues with no text: A2 D19"] and by["32"]["also"] == []   # the card says a Ready won't ship it yet
