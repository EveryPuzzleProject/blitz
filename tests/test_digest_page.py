"""The batch digest and its step-through (src/blitz/batch.html, ?digest): the page draws blitz ship's record and
works nothing out, and a disagreement is recorded as the proof page records a Not ready.

The block between `// <digest>` and `// </digest>` is read from the source; `recordDisagree` (between
`// <digest-disagree>` and its end) is run under node against stand-ins for the site's database and a local server.

Run with: uv run --with pytest pytest tests/test_digest_page.py   (the node part is skipped without node)"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

BATCH = (Path(__file__).resolve().parents[1] / "src" / "blitz" / "batch.html").read_text(encoding="utf-8")
DIGEST = re.search(r"// <digest>.*?\n(.*?)// </digest>", BATCH, re.S)[1]
DISAGREE = re.search(r"// <digest-disagree>.*?\n(.*?)// </digest-disagree>", BATCH, re.S)[1]


def test_the_digest_draws_the_record_and_works_nothing_out():
    # no order of its own: the one sort is by the record's grade_order; no sample drawn, no hash, no grade decided here
    assert DIGEST.count(".sort(") == 1 and ".sort((a, b) => (a.grade_order ?? 1e9) - (b.grade_order ?? 1e9))" in DIGEST
    assert not re.search(r"Math\.random|crypto\.|sha1|\.grade\s*=[^=]", DIGEST)
    for field in ("SHIP.walk", "SHIP.sample", "SHIP.failures", "SHIP.grades.order", "c.grades", "x.doubts", "x.gaps", "x.diagnosis", "to_read"):
        assert field in DIGEST, field
    assert DIGEST.count("not recorded") >= 8                                          # what the record doesn't say is said, not guessed
    # the step-through's keys, and the way in from the batch's queues
    for key in ("'ArrowRight'", "'ArrowLeft'", "'x'", "'Escape'"):
        assert key in DIGEST
    assert "params.has('digest')" in BATCH and "digestUrl()" in BATCH.split("// </digest>")[1]


def node(js: str):
    if not shutil.which("node"):
        pytest.skip("node isn't installed")
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


STUBS = """
const sent = [], wrote = [];
let LIVE = {}, SB = null, have = [];
const myName = () => 'pat';
const table = name => ({
  select: () => ({eq: () => ({eq: async () => ({data: have, error: null})})}),
  upsert: async row => { wrote.push([name, row]); return {error: null}; }});
const mkSB = () => ({auth: {getSession: async () => ({data: {session: {user: {id: 'u1'}}}})}, from: table});
globalThis.fetch = async (url, opt) => { sent.push([url, JSON.parse(opt.body)]); return {ok: true, json: async () => ({})}; };
"""


def test_a_disagreement_is_a_not_ready_recorded_as_the_proof_page_records_one():
    r = node(STUBS + "const SITE = null, params = new URLSearchParams('save=/api/proof');\n" + DISAGREE + """
      recordDisagree('games1980-05-01-L026', {packet_xd: '451dfd396b58'}, '12-Down looks wrong')
        .then(x => console.log(JSON.stringify({x, sent, live: LIVE})));""")
    url, body = r["sent"][0]
    assert url == "/api/proof" and body["xdid"] == "games1980-05-01-L026" and body["decision"] == "notready" and body["who"] == "pat"
    assert body["review"]["xd"] == "451dfd396b58" and body["review"]["edits"] == {} and "12-Down looks wrong" in body["review"]["note"]
    assert r["x"]["answer"] == "notready" and r["live"]["games1980-05-01-L026"]["you"] == "notready"


def test_on_the_site_it_goes_to_proofs_and_never_writes_over_a_review_the_person_has():
    js = STUBS + "const SITE = {supabaseUrl: 'u', supabaseAnonKey: 'k'}, params = new URLSearchParams('');\nSB = mkSB();\n" + DISAGREE
    r = node(js + "recordDisagree('p1', {packet_xd: 'fp'}, '').then(() => console.log(JSON.stringify(wrote)));")
    assert [t for t, _ in r] == ["proofs", "verdicts"]
    assert (r[0][1]["xdid"], r[0][1]["user_id"], r[0][1]["decision"], r[0][1]["review"]["xd"]) == ("p1", "u1", "notready", "fp")
    assert r[1][1]["verdict"] == "needs-work"
    r = node(js + "have = [{decision: 'ready', at: '2026-11-20T00:00:00Z'}];\n"
             "recordDisagree('p1', {packet_xd: 'fp'}, '').then(() => console.log('\"recorded\"'), e => console.log(JSON.stringify({err: e.message, wrote})));")
    assert "already have a review" in r["err"] and r["wrote"] == []


def test_with_nowhere_to_record_it_says_so():
    r = node(STUBS + "const SITE = null, params = new URLSearchParams('');\n" + DISAGREE
             + "recordDisagree('p1', null, '').then(() => console.log('\"recorded\"'), e => console.log(JSON.stringify({err: e.message, sent})));")
    assert "nowhere to record" in r["err"] and r["sent"] == []
