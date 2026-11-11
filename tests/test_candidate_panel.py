"""The proof page's candidate panel, as far as it can be tested without a browser.

The panel's rule for "is this candidate decided, and whose choice is it" is a pure block of proof.html
(between `// <candidate-rules>` and `// </candidate-rules>`). It is run here under node on the cases the
import is tested on (tests/test_ship.py), and its answers are compared with blitz ship.candidate_decisions
on the same reviews: the page and the import must say the same thing. Also checked from the source: the
page reads the packet's fields and never works a box out.

Run with: uv run --with pytest pytest tests/test_candidate_panel.py   (the node part is skipped without node)"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from blitz.ship import AGENT, CANDIDATE_VALUE, SITE, Rule, candidate_decisions

PAGE = (Path(__file__).resolve().parents[1] / "src" / "blitz" / "proof.html").read_text(encoding="utf-8")
RULES = re.search(r"// <candidate-rules>.*?\n(.*?)// </candidate-rules>", PAGE, re.S)[1]
KEY, FP = "candidate:D-alt1", "fp"


def page_says(rounds, cur=None, same=()):
    """candidateStanding and candidatesOpen for D-alt1, from the page's own code."""
    if not shutil.which("node"):
        pytest.skip("node isn't installed")
    js = RULES + f"""
const rounds = {json.dumps(rounds)}, cur = {json.dumps(cur)};
if (cur) rounds.push(cur);
console.log(JSON.stringify({{st: candidateStanding({json.dumps(KEY)}, rounds, cur ? rounds[rounds.length - 1] : null, {json.dumps(FP)}, {json.dumps(list(same))}),
  open: candidatesOpen(['D-alt1'], rounds, cur ? rounds[rounds.length - 1] : null, {json.dumps(FP)}, {json.dumps(list(same))})}}));
"""
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def record(who, answer, value, via=SITE, xd=FP, at="2026-11-11T00:00:00Z"):
    return {"id": "proof:p", "answer": answer, "by": f"{who} ({SITE})" if via == SITE else who, "at": at, "via": via,
            "proof": {"review": {"xd": xd, "edits": {KEY: value} if value else {}}}}


def round_of(rec):
    """A ledger record as the page holds that reviewer's round (loadProofs for a person, aiRound for the AI)."""
    rv = rec["proof"]["review"]
    return {"who": rec["by"], "person": rec["via"] != AGENT, "ai": rec["via"] == AGENT, "decision": rec["answer"],
            "xd": rv["xd"], "edits": rv["edits"]}


CASES = {
    "nobody chose": [],
    "a helper's Ready": [record("pat", "ready", "remove")],
    "a helper's Not ready": [record("pat", "notready", "remove")],
    "a Ready on an earlier version": [record("pat", "ready", "clues", xd="older")],
    "an AI's Ready": [record("Claude (AI proof reviewer, m)", "ready", "clues", via=AGENT)],
    "an AI's Ready and a helper's Not ready": [record("Claude (AI proof reviewer, m)", "ready", "clues", via=AGENT),
                                               record("pat", "notready", "second:Easy", at="2026-11-12T00:00:00Z")],
    "a value that isn't one of the four": [record("pat", "ready", "second")],
    "a Not ready, then another helper's Ready": [record("pat", "notready", "remove"), record("sam", "ready", "answers", at="2026-11-12T00:00:00Z")],
}


@pytest.mark.parametrize("name", CASES)
def test_the_page_and_the_import_agree_on_whether_a_candidate_is_decided(name):
    recs = CASES[name]
    want = candidate_decisions(recs, Rule(), (FP,)).get("D-alt1") or {"decision": ""}
    got = page_says([round_of(r) for r in recs])["st"]
    assert (got["value"] if got["counts"] else "") == want["decision"]
    pending = want.get("pending")
    assert (not got["counts"] and got["value"] or "") == (pending["decision"] if pending else "")
    if pending:
        assert got["why"] == pending["why"]


def test_a_ready_carries_the_choice_the_page_shows_or_the_page_says_it_does_not():
    """The cold review's case: a helper chose "remove" in a Not ready; the owner opens the page."""
    helper = round_of(record("pat", "notready", "remove"))
    seen = page_says([helper], cur={"who": "oops6498", "edits": {}, "decision": None})
    assert seen["st"] == {"value": "remove", "who": f"pat ({SITE})", "why": "in a review that said Not ready", "mine": False, "counts": False}
    # so a Ready now would leave it open, and the page names the choice that doesn't count
    assert seen["open"] == [{"id": "D-alt1", "pending": seen["st"]}]
    # once the owner makes it their own, their Ready carries it and nothing is open
    mine = page_says([helper], cur={"who": "oops6498", "edits": {KEY: "remove"}, "decision": "ready"})
    assert mine["st"] == {"value": "remove", "who": "You", "mine": True, "counts": True, "why": ""} and mine["open"] == []
    # their own choice in a Not ready is theirs, and is said not to count
    no = page_says([], cur={"who": "oops6498", "edits": {KEY: "remove"}, "decision": "notready"})
    assert (no["st"]["mine"], no["st"]["counts"], no["st"]["why"]) == (True, False, "you said Not ready")
    # another person's Ready on this version (or one the packet says is the same puzzle) counts without a choice of yours
    assert page_says([round_of(record("pat", "ready", "answers"))], cur={"who": "x", "edits": {}})["open"] == []
    assert page_says([round_of(record("pat", "ready", "answers", xd="older"))], cur={"who": "x", "edits": {}}, same=("older",))["open"] == []


def test_the_page_takes_the_same_four_values_as_the_import():
    page = re.search(r"const CAND_VALUE = /\^\((.*?)\)\$/;", RULES)[1]
    assert page == CANDIDATE_VALUE.pattern


def test_a_choice_is_always_written_into_the_reviewers_own_review():
    """Picking what an earlier reviewer picked must still be an edit of yours (setEdit drops an edit equal to the
    round before): otherwise the page would show it decided and your Ready would carry nothing."""
    panel = PAGE[PAGE.index("function candidatePanel(c)"):PAGE.index("\nfunction render()")]
    assert "cur.edits[key] = val" in panel and "setEdit(key" not in panel


def test_the_panel_draws_recorded_boxes_and_says_not_recorded():
    """Views never compute: the block and each clue's crop come from the packet's parts[].box and clues[k].box; a
    missing one is said, and nothing in the panel looks a box up anywhere else."""
    panel = PAGE[PAGE.index("function candidatePanel(c)"):PAGE.index("\nfunction render()")]
    assert "Where it is on the page" in panel and "not recorded" in panel and "line box: not recorded" in panel
    assert "strip(x.box, x.image)" in panel and "scanViewer(p.image, p.box)" in panel
    assert "ocr.clues[k].box" not in panel and "sourceFor(" not in panel and "contextStrip(" not in panel
    assert "c.from" in panel and "rev.built_from" in panel                      # the milestone and its version are named
