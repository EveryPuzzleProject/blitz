# The batch page's ask, by queue: screenshots of 2026-11-10

What the batch page (`/review/batch/?b=<batch>`) asks of people, after the rework that draws each
puzzle's queue from `blitz ship`'s record (format: [design/ship.md](../ship.md), "The queues").
Taken from the page running locally (`tools/review_dev.py`) over the two live batches' snapshots
and a ship record made for each as a dry run. Nothing here was published.

## Counts

| queue | GAMES 1977-79 | Collegian 1976-81 |
|---|---|---|
| Held on a question | 22 | 238 |
| Not checked yet | 2 | 64 |
| Broken in the pipeline | 13 | 495 |
| Ready to ship | 0 | 0 |
| Shipped | 35 (spot-check 3) | 0 |
| Set aside | 3 | 0 |
| Not a crossword | 7 (1 in the record, 6 from the snapshot's drops) | 0 |
| **all** | **82** | **797** |
| reviewed by a person | 24 | 0 |

Shared-question groups (by the puzzle's largest group; they add up to the queue):

- GAMES: the notes 10, the byline 2, one puzzle's own 10.
- Collegian: the title 185, the byline 25, the notes 3, one puzzle's own 25.

Broken, by the stage the first broken part points to:

- GAMES: parts 4, import 4, assembly 3, key reading 1, the proof packet 1.
- Collegian: assembly 215, parts 166, key reading 114.

Of the puzzles held on a question, the ship check also found some incomplete (unsolved squares, clues
with no text), which an answer won't mend; their cards say so: GAMES 1, Collegian 50.

## The pictures

- [00-landing.jpg](00-landing.jpg): the site's way in, one card per batch; the third card is a copy of
  GAMES with no ship record, to show "not recorded".
- `games-1` to `games-9`, `collegian-1` to `collegian-5`: the default view and each filter.
- `*-card-*`: one card of each kind.
- [collegian-proof-page-at-the-question.jpg](collegian-proof-page-at-the-question.jpg): where "Answer it" lands, the proof
  page at the question's row with the walk bar.
- [no-record-batch.jpg](no-record-batch.jpg): a batch with no record.

## To see it again

```
uv run python tools/review_dev.py --data ../blitz-work/batch-ask-dev --port 8797
```

then <http://localhost:8797/review/batch/>. The folder holds copies of the two batches' `batch.json`,
links to their pictures in `blitz-work/site-batch/`, and the two `ship.json` made with:

```
uv run blitz ship games --repo ../games --proof ../xword-ocr/harvests/games-7779/proof/run15-restart --batch games-1977-79 --no-site --snapshot ../blitz-work/batch-ask-dev/files/batch/games-1977-79
uv run blitz ship collegian --proof ../blitz-work/collegian-run1-backup/proof/run1 --batch collegian-1976-81 --no-site --snapshot ../blitz-work/batch-ask-dev/files/batch/collegian-1976-81
```
