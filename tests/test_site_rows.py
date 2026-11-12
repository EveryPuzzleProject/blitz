"""The review pages read the site's whole list, and ?p= never opens another puzzle.

The site's database gives at most 1,000 rows to one request and says nothing when it stops there. On
2026-11-11 the Collegian batch took the site to 1,433 open puzzles; the proof page asked once, so its
list ended at the 1,000th (judge1927-04-16), and `?p=nyw1914-03-08-L000` opened the first puzzle on
the list (a Collegian one) with no word. The batch page's way in lost the same 433 puzzles.

The pages' rule is a pure block of each (between `// <site-rows>` and `// </site-rows>`), run here
under node against a stand-in for the database that keeps the same cap. Also checked from the source:
no page or command reads a site table with a single request.

Run with: uv run --with pytest pytest tests/test_site_rows.py   (the node part is skipped without node)"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "blitz"
PROOF = (SRC / "proof.html").read_text(encoding="utf-8")
BATCH = (SRC / "batch.html").read_text(encoding="utf-8")
block = lambda page: re.search(r"// <site-rows>.*?\n(.*?)// </site-rows>", page, re.S)[1]

# the database: n puzzles in id order, at most 1,000 to a request whatever limit asks for
DB = """
const CAP = 1000, asked = [];
const db = n => async q => {
  asked.push(q);
  const u = new URLSearchParams(q.split('?')[1]), at = +u.get('offset') || 0;
  if (failAt !== null && at >= failAt) return null;
  const rows = Array.from({length: n}, (_, i) => ({xdid: 'p' + String(i).padStart(5, '0')}));
  return rows.slice(at, at + Math.min(+u.get('limit') || CAP, CAP));
};
let failAt = null;
"""


def node(js: str):
    if not shutil.which("node"):
        pytest.skip("node isn't installed")
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@pytest.mark.parametrize("page", [PROOF, BATCH], ids=["proof.html", "batch.html"])
@pytest.mark.parametrize("n", [0, 86, 999, 1000, 1001, 1433, 2000, 3210])
def test_a_page_reads_every_row_whatever_the_count(page, n):
    got = node(block(page) + DB + f"""
allRows(db({n}), 'puzzles?select=xdid&order=xdid').then(rows =>
  console.log(JSON.stringify({{n: rows.length, distinct: new Set(rows.map(r => r.xdid)).size, last: (rows[rows.length - 1] || {{}}).xdid, asked: asked.length}})));""")
    assert got["n"] == got["distinct"] == n
    assert got.get("last") == (f"p{n - 1:05d}" if n else None)
    assert got["asked"] == n // 1000 + 1


@pytest.mark.parametrize("page", [PROOF, BATCH], ids=["proof.html", "batch.html"])
def test_a_list_that_stops_part_way_is_an_error_not_a_shorter_list(page):
    got = node(block(page) + DB + """
failAt = 1000;
allRows(db(1433), 'puzzles?select=xdid&order=xdid').then(rows => console.log(JSON.stringify({rows: rows.length})),
                                                         e => console.log(JSON.stringify({error: String(e.message)})));""")
    assert "error" in got and "puzzles" in got["error"]


def test_p_opens_the_puzzle_it_names_or_none():
    """The 1,433 of 2026-11-12: a puzzle past the 1,000th opens; an id that isn't there opens nothing
    (the page then says so: noPuzzle), never the first puzzle; with no ?p=, the first not dropped."""
    got = node(block(PROOF) + DB + """
allRows(db(1433), 'puzzles?select=xdid&order=xdid').then(all => {
  const dropped = p => p.xdid === 'p00000';
  console.log(JSON.stringify({late: choosePuzzle(all, 'p01432', dropped), dropped: choosePuzzle(all, 'p00000', dropped),
    missing: choosePuzzle(all, 'nyw1914-03-08-L000', dropped), none: choosePuzzle(all, null, dropped), empty: choosePuzzle([], null, dropped)}));
});""")
    assert got == {"late": {"xdid": "p01432"}, "dropped": {"xdid": "p00000"}, "missing": None, "none": {"xdid": "p00001"}, "empty": None}


def test_the_proof_page_says_so_when_p_names_no_open_puzzle():
    assert "const here = choosePuzzle(all, want, isDropped);" in PROOF
    assert re.search(r"if \(!here\) return noPuzzle\('No open puzzle ' \+ want", PROOF)
    assert "if (await pickPuzzle() === false) return;" in PROOF  # and nothing else is loaded in its place


def test_no_site_table_is_read_with_a_single_request():
    """Every read of a whole table goes through the paging: allRows on the pages (the key-squares page
    has its own, `pages`), _rest_all in the commands. A read of one puzzle's rows (.eq('xdid', ...)) is
    not a list."""
    for name, page in (("proof.html", PROOF), ("batch.html", BATCH)):
        direct = [m for m in re.findall(r"fetch\(`\$\{SITE\.supabaseUrl\}/rest/v1/([^`]*)`", page) if m not in ("${q}", "${x}")]
        assert not direct, f"{name} reads {direct} without paging"
    whole = [ln.strip() for ln in PROOF.splitlines() if re.search(r"sb\.from\('\w+'\)\.select\(", ln) and ".eq('xdid'" not in ln]
    assert not whole, f"proof.html reads a whole table through supabase-js: {whole}"
    squares = (SRC / "squares.html").read_text(encoding="utf-8")
    assert ".range(a, a + 999)" in squares
    assert all("pages(" in ln for ln in squares.splitlines() if "sb.from(" in ln and ".select(" in ln)
    for name in ("site.py", "cli.py", "sitebatch.py", "ship.py", "sync.py"):
        gets = re.findall(r'_rest\("GET"[^\n]*', (SRC / name).read_text(encoding="utf-8"))
        assert all("{path}" in g for g in gets), f"{name} reads with one request: {gets}"
