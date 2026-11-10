# Do the batch page's question links land on the question? (2026-11-10)

Made by `tools/check_question_links.py` against the real packets on a local server (`tools/review_dev.py`), with
the proof page of branch `claude/batch-ask-questions`. Two columns of each kind:

- **published again**: the packets with their `puzzle.xd` (and, for GAMES, the `ai_review.json` and
  `checks.json` that `xword-ocr proof-review attach` and `proof-checks` add): what a person sees once the
  packets are published again.
- **as live today**: the packets as the site has them now (no `puzzle.xd`; GAMES also without `ai_review.json`
  and `checks.json`), with the new proof page.

Columns: **row**, the row the question points at is on the page; **shown at top**, the question is in the box at
the top; **shown at row**, the question is also at its row (a callout, or the reviewer's comment); **lands**, for a
puzzle's first question (the "Answer it" link), the page is scrolled to that row, or stays at the box when
the row isn't on the page.

Before this change, on the live page: the question was shown nowhere for GAMES (0 of 58: its packets carry no
AI review), and only as the AI's comment at the row for Collegian; a notes question had no row in either batch.

The two GAMES questions with no row even after publishing again are real: `games1978-07-01-L030` asks about
`clue:A60`, which the grid doesn't have (the reviewer meant 60 Down), and `games1978-05-01-L026` asks about the
answer key of a puzzle whose packet has none. The box at the top says so.

## GAMES 1977-79: all 22 puzzles held on a question

Totals for games-1977-79:

- published again: 56 of 58 questions have their row on the page; 58 of 58 are shown at the top; 56 of 56 rows show the question at the row; 22 of 22 first links land where they should.
- as live today: 46 of 58 questions have their row on the page; 58 of 58 are shown at the top; 46 of 46 rows show the question at the row; 22 of 22 first links land where they should.

### games-1977-79: 22 puzzles, 58 questions

| puzzle | group | question about | published again: row | as live today: row | published again: shown at top | as live today: shown at top | published again: shown at row | as live today: shown at row | published again: lands | as live today: lands |
|---|---|---|---|---|---|---|---|---|---|---|
| games1978-09-01-L028 | notes | meta:note | yes | NO | yes | yes | yes | no row | yes | yes |
| games1978-09-01-L032 | notes | meta:note | yes | NO | yes | yes | yes | no row | yes | yes |
| games1978-07-01-L026 | notes | meta:note | yes | NO | yes | yes | yes | no row | yes | yes |
|  |  | ev:byline | yes | yes | yes | yes | yes | yes |  |  |
| games1979-03-01-L030 | notes | ev:byline | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | meta:note | yes | NO | yes | yes | yes | no row |  |  |
| games1979-05-01-L028 | notes | meta:note | yes | NO | yes | yes | yes | no row | yes | yes |
|  |  | ev:byline | yes | yes | yes | yes | yes | yes |  |  |
| games1979-07-01-L026 | notes | meta:note | yes | NO | yes | yes | yes | no row | yes | yes |
|  |  | ev:byline | yes | yes | yes | yes | yes | yes |  |  |
| games1979-03-01-L030b | notes | line:B3 | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | meta:note | yes | NO | yes | yes | yes | no row |  |  |
| games1979-05-01-L028b | notes | line:B3 | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | meta:note | yes | NO | yes | yes | yes | no row |  |  |
| games1979-07-01-L026b | notes | line:B2 | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | meta:note | yes | NO | yes | yes | yes | no row |  |  |
| games1978-09-01-L028b | notes | clue:A11 | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | clue:D6 | yes | yes | yes | yes | yes | yes |  |  |
|  |  | clue:D25 | yes | yes | yes | yes | yes | yes |  |  |
|  |  | line:B4 | yes | yes | yes | yes | yes | yes |  |  |
|  |  | clue:A24 | yes | yes | yes | yes | yes | yes |  |  |
|  |  | meta:note | yes | NO | yes | yes | yes | no row |  |  |
| games1978-03-01-L050 | byline | ev:byline | yes | yes | yes | yes | yes | yes | yes | yes |
| games1978-03-01-L032b | byline | clue:D55 | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | ev:byline | yes | yes | yes | yes | yes | yes |  |  |
| games1977-09-01-L032b | own | clue:D49 | yes | yes | yes | yes | yes | yes | yes | yes |
| games1978-07-01-L028b | own | clue:D51 | yes | yes | yes | yes | yes | yes | yes | yes |
| games1978-11-01-L032 | own | cell:r13c15 | yes | yes | yes | yes | yes | yes | yes | yes |
| games1979-07-01-L042 | own | grid | yes | yes | yes | yes | yes | yes | yes | yes |
| games1978-07-01-L030 | own | clue:D109 | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | clue:A60 | NO | NO | yes | yes | no row | no row |  |  |
| games1978-09-01-L042 | own | clue:D82^Easy | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | clue:A34^Easy | yes | yes | yes | yes | yes | yes |  |  |
| games1978-05-01-L026 | own | clue:A25 | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | line:B3 | yes | yes | yes | yes | yes | yes |  |  |
|  |  | grid | NO | NO | yes | yes | no row | no row |  |  |
| games1978-05-01-L040 | own | clue:A36^Easy | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | clue:A85 | yes | yes | yes | yes | yes | yes |  |  |
|  |  | line:B5 | yes | yes | yes | yes | yes | yes |  |  |
| games1978-07-01-L040 | own | clue:D68 | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | clue:D121 | yes | yes | yes | yes | yes | yes |  |  |
|  |  | clue:A11^Easy | yes | yes | yes | yes | yes | yes |  |  |
|  |  | line:B5 | yes | yes | yes | yes | yes | yes |  |  |
|  |  | clue:A29^Easy | yes | yes | yes | yes | yes | yes |  |  |
|  |  | clue:A35^Easy | yes | yes | yes | yes | yes | yes |  |  |
|  |  | clue:D155^Easy | yes | yes | yes | yes | yes | yes |  |  |
| games1979-03-01-L040b | own | clue:A49^Alt | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | clue:A50^Alt | yes | yes | yes | yes | yes | yes |  |  |
|  |  | clue:A56^Alt | yes | yes | yes | yes | yes | yes |  |  |
|  |  | clue:A61^Alt | yes | yes | yes | yes | yes | yes |  |  |
|  |  | clue:A166^Alt | yes | yes | yes | yes | yes | yes |  |  |
|  |  | clue:D97 | yes | yes | yes | yes | yes | yes |  |  |
|  |  | clue:D171 | yes | yes | yes | yes | yes | yes |  |  |
|  |  | cell:r20c8 | yes | yes | yes | yes | yes | yes |  |  |
|  |  | cell:r25c8 | yes | yes | yes | yes | yes | yes |  |  |
|  |  | cell:r25c24 | yes | yes | yes | yes | yes | yes |  |  |
|  |  | cell:r12c12 | yes | yes | yes | yes | yes | yes |  |  |
|  |  | clue:D1^Alt | yes | yes | yes | yes | yes | yes |  |  |

## Collegian 1976-81: a sample of 30 of the 238, spread over the four groups

Totals for collegian-1976-81:

- published again: 65 of 65 questions have their row on the page; 65 of 65 are shown at the top; 65 of 65 rows show the question at the row; 30 of 30 first links land where they should.
- as live today: 61 of 65 questions have their row on the page; 65 of 65 are shown at the top; 61 of 61 rows show the question at the row; 30 of 30 first links land where they should.

### collegian-1976-81: 30 puzzles, 65 questions

| puzzle | group | question about | published again: row | as live today: row | published again: shown at top | as live today: shown at top | published again: shown at row | as live today: shown at row | published again: lands | as live today: lands |
|---|---|---|---|---|---|---|---|---|---|---|
| collegian1976-10-27-L001 | title | ev:title | yes | yes | yes | yes | yes | yes | yes | yes |
| collegian1979-01-04-L003 | title | ev:title | yes | yes | yes | yes | yes | yes | yes | yes |
| collegian1978-09-29-L001 | title | ev:byline | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | ev:title | yes | yes | yes | yes | yes | yes |  |  |
| collegian1980-04-01-L003 | title | ev:byline | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | ev:title | yes | yes | yes | yes | yes | yes |  |  |
| collegian1978-11-06-L001 | title | ev:title | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | clue:A56 | yes | yes | yes | yes | yes | yes |  |  |
| collegian1981-01-28-L003 | title | clue:A66 | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | ev:title | yes | yes | yes | yes | yes | yes |  |  |
| collegian1978-10-04-L001 | title | clue:D6 | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | clue:D6 | yes | yes | yes | yes | yes | yes |  |  |
|  |  | ev:title | yes | yes | yes | yes | yes | yes |  |  |
| collegian1980-12-18-L003 | title | clue:D10 | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | ev:title | yes | yes | yes | yes | yes | yes |  |  |
|  |  | clue:A61 | yes | yes | yes | yes | yes | yes |  |  |
| collegian1981-01-26-L003 | title | ev:byline | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | clue:A45 | yes | yes | yes | yes | yes | yes |  |  |
|  |  | ev:title | yes | yes | yes | yes | yes | yes |  |  |
|  |  | clue:D26 | yes | yes | yes | yes | yes | yes |  |  |
| collegian1979-02-13-L001 | byline | ev:byline | yes | yes | yes | yes | yes | yes | yes | yes |
| collegian1977-02-09-L001 | byline | clue:D40 | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | ev:byline | yes | yes | yes | yes | yes | yes |  |  |
| collegian1979-03-23-L003 | byline | ev:byline | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | clue:A20 | yes | yes | yes | yes | yes | yes |  |  |
| collegian1977-02-02-L001 | byline | clue:A16 | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | ev:byline | yes | yes | yes | yes | yes | yes |  |  |
|  |  | clue:A48 | yes | yes | yes | yes | yes | yes |  |  |
| collegian1979-02-09-L003 | byline | cell:r5c11 | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | ev:byline | yes | yes | yes | yes | yes | yes |  |  |
|  |  | clue:D50 | yes | yes | yes | yes | yes | yes |  |  |
| collegian1979-04-20-L001 | byline | ev:byline | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | clue:A43 | yes | yes | yes | yes | yes | yes |  |  |
|  |  | clue:D18 | yes | yes | yes | yes | yes | yes |  |  |
| collegian1979-07-25-L001 | byline | ev:byline | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | grid | yes | yes | yes | yes | yes | yes |  |  |
|  |  | clue:A43 | yes | yes | yes | yes | yes | yes |  |  |
| collegian1977-05-11-L001 | byline | grid | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | clue:A1 | yes | yes | yes | yes | yes | yes |  |  |
|  |  | meta:note | yes | NO | yes | yes | yes | no row |  |  |
|  |  | ev:byline | yes | yes | yes | yes | yes | yes |  |  |
| collegian1980-04-25-L003 | byline | clue:A37 | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | clue:D17 | yes | yes | yes | yes | yes | yes |  |  |
|  |  | ev:byline | yes | yes | yes | yes | yes | yes |  |  |
|  |  | clue:D17 | yes | yes | yes | yes | yes | yes |  |  |
| collegian1979-03-09-L003 | notes | notes | yes | NO | yes | yes | yes | no row | yes | yes |
| collegian1979-03-12-L003 | notes | notes | yes | NO | yes | yes | yes | no row | yes | yes |
| collegian1979-03-13-L003 | notes | notes | yes | NO | yes | yes | yes | no row | yes | yes |
| collegian1976-09-24-L003 | own | clue:D8 | yes | yes | yes | yes | yes | yes | yes | yes |
| collegian1976-11-04-L001 | own | clue:A77 | yes | yes | yes | yes | yes | yes | yes | yes |
| collegian1979-01-29-L001 | own | clue:A36 | yes | yes | yes | yes | yes | yes | yes | yes |
| collegian1981-03-25-L003 | own | clue:D36 | yes | yes | yes | yes | yes | yes | yes | yes |
| collegian1976-10-22-L001 | own | clue:D7 | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | clue:A48 | yes | yes | yes | yes | yes | yes |  |  |
| collegian1977-01-27-L001 | own | clue:A18 | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | clue:D14 | yes | yes | yes | yes | yes | yes |  |  |
| collegian1979-10-15-L003 | own | cell:r2c2 | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | clue:A15 | yes | yes | yes | yes | yes | yes |  |  |
| collegian1979-03-14-L003 | own | clue:D44 | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | clue:D46 | yes | yes | yes | yes | yes | yes |  |  |
|  |  | grid | yes | yes | yes | yes | yes | yes |  |  |
| collegian1976-10-28-L001 | own | clue:A69 | yes | yes | yes | yes | yes | yes | yes | yes |
|  |  | clue:D21 | yes | yes | yes | yes | yes | yes |  |  |
|  |  | clue:A26 | yes | yes | yes | yes | yes | yes |  |  |
|  |  | clue:D63 | yes | yes | yes | yes | yes | yes |  |  |
