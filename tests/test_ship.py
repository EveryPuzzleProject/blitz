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
