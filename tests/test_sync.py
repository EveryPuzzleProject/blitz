from blitz.sync import dry_run_credits, surprises

DRY = """12 reviews: 0 new corrections appended to x
HELPERS judge1930-01-04 clue:A3: helpers differ, left out
DRY RUN: nothing was written to ../judge/fixes. It would append:
  corrections.jsonl: 37 lines
       32  Alex DeJarnatt: looks-right puzzle
        2  Alex DeJarnatt: needs-work puzzle
        1  a helper (review site): correct clue
        2  a helper (review site): correct other
  tool-notes.jsonl: 3 lines
        3  review site: note tool
"""


def test_the_dry_run_report_is_read_by_log_and_name():
    c = dry_run_credits(DRY)
    assert c["corrections.jsonl"][("Alex DeJarnatt", "looks-right", "puzzle")] == 32
    assert c["corrections.jsonl"][("a helper (review site)", "correct", "other")] == 2
    assert c["tool-notes.jsonl"][("review site", "note", "tool")] == 3


def test_surprises_stop_the_sync():
    assert surprises(dry_run_credits(DRY), DRY, "review site", 150) == []
    # too much credited to one name: the wrong folder?
    assert "more than 30" in surprises(dry_run_credits(DRY), DRY, "review site", 30)[0]
    # the folder's own review.json files credited: replayed packets, not new reviews
    replayed = DRY.replace("a helper (review site): correct clue", "review site: correct clue")
    assert any("from the folder's own review.json" in s for s in surprises(dry_run_credits(replayed), replayed, "review site", 150))
    assert any("rejected" in s for s in surprises(dry_run_credits(DRY), DRY + "REJECTED judge1930-01-04: bad grid\n", "review site", 150))
