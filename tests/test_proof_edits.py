"""The proof page's own rules for what a reviewer types (between `// <edit-rules>` and `// </edit-rules>` in
src/blitz/proof.html), run under node, and checked against what blitz ship does with the same values:

- an edit box's text: a printed line keeps its line breaks (each a line of the xd's "Printed with puzzle:" block),
  a clue or a header can't hold one;
- the notes' preview: the block with one review's keeps, discards and text edits, by the place the ship record
  recorded (printed_place), is exactly the block apply_linked writes;
- a person's "printed this way, but wrong": accepted when the printed words are in the text once (ship's `fits:
  printed`), and the text put back as printed when the reviewer had typed the correction.

Run with: uv run --with pytest --extra site pytest tests/test_proof_edits.py   (skipped without node)"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from blitz.ship import apply_linked, printed_place
from test_ship_linked import LEDGER, NO7, NO12, packet

PROOF = (Path(__file__).resolve().parents[1] / "src" / "blitz" / "proof.html").read_text(encoding="utf-8")
RULES = re.search(r"// <edit-rules>.*?\n(.*?)// </edit-rules>", PROOF, re.S)[1]
node = pytest.mark.skipif(not shutil.which("node"), reason="node not installed")


def run(js: str):
    out = subprocess.run(["node", "-e", RULES + "\nconsole.log(JSON.stringify((() => {" + js + "})()));"],
                         capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(out.stdout)


@node
def test_a_printed_line_keeps_its_breaks_and_a_clue_or_header_cannot_hold_one():
    r = run("""return [cleanText('First para.\\n  Second para. \\n', true), cleanText('a\\n\\n\\nb', true), cleanText('Cross-Word\\nPuzzle', false),
                       MULTILINE('line:B4'), MULTILINE('clue:A6'), MULTILINE('meta:title'), ONE_LINE_SAYS('clue:A6'), ONE_LINE_SAYS('meta:title')]""")
    assert r[0] == {"value": "First para.\nSecond para.", "said": ""}
    assert r[1] == {"value": "a\nb", "said": "an empty line taken out"}                     # ship refuses an empty line in the block
    assert r[2] == {"value": "Cross-Word Puzzle", "said": "joined into one line"}
    assert r[3:6] == [True, False, False]
    assert "clue is one line" in r[6] and "title is one line" in r[7]


@node
def test_the_notes_preview_is_the_block_ship_writes_with_the_same_edits():
    for pid, edits in ((NO7, LEDGER[NO7]["proof"]["review"]["edits"]),
                       (NO12, {"keep:B22": False, "keep:B26": False, "line:B5": "(Copyright, 1914,\nby the Du Pay Syndicate.)"})):
        xd, ocr, review = packet(pid)
        place = printed_place(xd, ocr, review)
        pv = run(f"return printedBlock({json.dumps(ocr['lines'])}, {json.dumps(place)}, {json.dumps(edits)}, {json.dumps(review.get('corrections') or {})})")
        text, _, cant = apply_linked(xd, {k: v for k, v in edits.items() if k.startswith(("keep:", "line:"))}, ocr, review)
        assert cant == []
        block = text.split("Printed with puzzle:\n")[1].split("\n\n")[0].split("\n") if "Printed with puzzle:\n" in text else []
        assert pv["out"] == block and pv["touched"] and pv["placed"] and pv["applied"]
    assert len(pv["out"]) < len(place["lines"])                                              # No. 12: two lines fewer, B5 in two


@node
def test_a_misprint_mark_is_the_printed_words_once_and_puts_a_typed_correction_back():
    r = run("""return [misprintCheck('Cross-Word Puzzle No. 5', 'No. 5', 'No. 7'), misprintCheck('Cross-Word Puzzle No. 7', 'No. 5', 'No. 7'),
                       misprintCheck('No. 5 and No. 5', 'No. 5', 'No. 7'), misprintCheck('Towel', 'Tow', 'Toe'), misprintCheck('x', 'x', 'x')]""")
    assert r[0] == {"ok": True, "printed": "No. 5", "meant": "No. 7"}
    assert r[1]["ok"] and r[1]["back"] == "Cross-Word Puzzle No. 5"                          # blitz ships what was printed
    assert not r[2]["ok"] and "more than once" in r[2]["msg"]
    assert not r[3]["ok"]                                                                     # whole words, as ship matches them
    assert not r[4]["ok"]


@node
def test_a_declined_mark_says_only_that_it_was_declined():
    """Seen in the browser, 2026-11-13: a guest's mark the owner declined still read "corrected to 'untie' at the gxd
    export" beside "Declined by the owner: not taken" (and a key letter "corrected: M"). Ship never takes a declined mark,
    so the row says nothing else about it."""
    said = "Stays as printed here; corrected to “untie” at the gxd export, with a note."
    assert run(f"return [markFateText(true, true, {said!r}), markFateText(true, false, {said!r}), markFateText(false, false, {said!r}),"
               " markVerb(true, true), markVerb(true, false), markVerb(false, false)]") == [
        "", said, "Proposed: waiting for the owner, who decides whether it is corrected. Nothing is changed until then.",
        "proposed, then declined", "corrected", "proposed"]
