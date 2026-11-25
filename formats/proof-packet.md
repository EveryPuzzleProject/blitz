# The proof packet, version 1

One folder per puzzle: the puzzle as it was read, the images that prove it, and the review that
came with it. It is what the pipeline hands to everything after: the proof page, the reviewers
(a person or an agent), `blitz ship`. Whoever writes a packet, a reader needs only this folder.

Version 1 is the packet as it stood on 2026-11-25, written from the files on disk (7,205 packets
in `xword-ocr/harvests` and `blitz-work`) and the code that reads them. The six current sets
pass the check with no problems: Collegian run2 (797), GAMES 1977-79 run15-restart (76), GAMES
1980-82 run1-handsoff (125), Judge tasks-final-1012 (531), Boston Globe run2 (33) and the
hand-read New York World (33). Packets of earlier runs differ in places; "Earlier packets" at
the end says how.

```
uv run blitz check-format <a packet, or a folder of packets> [--notes] [--lines]
```

## Who writes it

| Form | Writer | Told by |
|---|---|---|
| assembled | xword-ocr `proof-packets` (`proofpacket.py`), from an assembled puzzle and the text step | `puzzle.xd`, and `metadata` in `ocr.json` |
| hand | `blitz hand-packets` (`handread.py`), from an xd read by hand and its boxes file | `read_by` and `hand_read` in `ocr.json` |
| task | xword-ocr `task-packets` (`tasks.py`), the older harvest's (Judge) | no `puzzle.xd`, no `metadata` |

The task form is the oldest and the smallest. It is valid version 1; the check says so in a note.

## The folder

The folder's name is the puzzle's id on the review site (`games1977-09-01-L032`, or an xdid for
a hand-read packet).

| File | Holds | Needed |
|---|---|---|
| `ocr.json` | the reading every review starts from | always |
| `review.json` | what came with the reading: the text step's changes and doubts, and which version of the xd the packet shows | always |
| `puzzle.xd` | the xd file as it would ship with no reviewer's edit | assembled, hand |
| `checks.json` | what the checks found, each on its row of the proof page | optional |
| `page.jpg` | the page the grid is on, scaled down | always |
| `clue_page.jpg`, `continued_page.jpg` | the page with most of the clues, if another; a third page a clue list runs on to | when named |
| `answer_page.jpg` | the page the answer key is on | when the key was found |
| `grid.png`, `answers.png` | the grid and the key, straightened, 40 pixels a square | when a lattice was found (else the page shows the scan beside our grid) |
| `cover.jpg` | the issue's cover, small | optional |
| `meta-<id>.png`, `clues_<n>.png`, `pictures/`, `candidate_page*.jpg` | crops for the headers table; the task form's clue sheets; pictures a clue points to; pages only a candidate clue list is on | optional |
| `_src/` | the same pages at full resolution, by the same names, for crops | expected |
| `ai_review.json` | an AI proof reviewer's answer, when one ran | optional; not checked yet |

Every image `ocr.json` names must be in the folder.

## Coordinates

- A **box** is `[x0, y0, x1, y1]` in the pixels of the packet image it belongs to: `clue_image`
  (normally `page.jpg`) unless the clue or line names its own `image`.
- **`scales`** gives, for each packet image, its size as a share of the full-resolution page in
  `_src/`. Divide a box by its image's scale to crop from `_src/`.
- A **square** is `r<row>c<column>`, counted from 1.
- A **clue's id** is its standard label, `A12` or `D7`, also in a linked-ends puzzle (the
  printed pair is in the clue's `printed`).
- A **row key** names a row of the proof page: `clue:A12`, `cell:r3c4`, `line:B2` (the printed
  line with `n` 2), `meta:title`, `ev:title`. Reviews, checks and edit records all use them
  (`design/ship.md`).

## ocr.json

In every form:

| Field | Type | Holds |
|---|---|---|
| `xdid` | text | the packet's id (the folder's name) |
| `source` | text | where a person can see the grid's page; may be empty |
| `title`, `author`, `byline` | text | the headers as read; empty when none |
| `grid` | list of rows | the puzzle's shape: `.` a white square, `#` a black one, `_` outside the puzzle. All rows one length |
| `answers` | list of rows, or null | the key laid on the grid, the grid's size; null or empty when no key was found |
| `answers_low_confidence` | list of squares | key squares the reader was unsure of |
| `grid_asymmetric_squares` | list | squares that break the grid's symmetry, each alone or with the square opposite (`r1c5/r15c11`) |
| `clue_image` | text | the image the clues' boxes are on |
| `scales` | name to number | every page image in the packet, with its scale |
| `clues` | id to clue | each clue: `text`; `box` where it was read from; optional `flags`, `image` (when on another page), `printed` (a linked-ends pair) |

Also in the assembled and hand forms:

| Field | Type | Holds |
|---|---|---|
| `puzzle_number`, `editor`, `feature`, `issue_date` | text | more headers; empty when none |
| `lines` | list | every printed line that is not a clue: `n` (the line is row `B<n>`), `text`, `box`; `keep` (whether it is in the xd's printed block), `label` (what the line is) and `by` (who or what said so); optional `image` |
| `evidence` | header to line number | which printed line each header was read from (null: none) |
| `metadata` | list | the rows of the proof page's headers table: `id`, `name`, `value`; optional `field`, `source`, `says`, `rule`, `image`, `line` |

Optional, each written only when there is something to say:

| Field | Form | Holds |
|---|---|---|
| `answer_page` | assembled | `scan`, `leaf`, `image`, `scale`, and `key_outline`: where on that page the key was matched |
| `stages` | assembled | where the puzzle is in the stages before: `date`, `pages` (each packet image's scan and leaf), `regions` (the boxes its parts were read from) |
| `cover`, `cover_from` | assembled | the cover image and its scan, leaf and page |
| `candidates` | assembled | assembly's candidate clue lists: lists that fit the grid and are not in the xd |
| `clue_sets` | assembled | a second clue set's heading: `key`, `heading`, `box`, `image` |
| `key_differ` | assembled | where the key's black squares differ from the grid's |
| `read_by`, `hand_read` | hand | whose reading it is; the boxes file and page images it came from |
| `square_numbers`, `numbering` | hand | the numbers printed in the grid, by square, and how they were worked out |
| `epp_fields` | hand | the xd's own extra headers, as `name` and `value` |
| `captions`, `meta_boxes`, `continued_page` | task | picture captions; the title's and byline's boxes; the page a clue list runs on to |
| `format` | any | `proof-packet/1`. Absent means version 1 |

## review.json

In every form:

| Field | Type | Holds |
|---|---|---|
| `ready` | true or false | whether the round that came with the packet called it ready |
| `model` | text | the round's name on the proof page ("AI reviewer", "read by hand") |
| `corrections` | row key to text | what that round changed from the reading: the new text of each row |
| `confirm` | list | rows it checked and left as read |
| `sic` | row key to text | rows printed wrong and kept as printed |
| `unsure` | row key to text | what it was unsure of, in words |
| `note` | text | its summary |
| `tool_notes` | list | notes on the tools and the source of each change: `kind`, `target`, `note` |
| `matches_xd` | true or false | whether `ocr.json` with `corrections` applied gives `puzzle.xd` |

Also in the assembled and hand forms:

| Field | Type | Holds |
|---|---|---|
| `xd_fp` | 12 hex digits | the version of the puzzle this packet shows (below) |
| `xd_fp_same` | list | other fingerprints of the same puzzle: a Ready given on any of them still counts |
| `reviewer`, `reviewer_line`, `model_id` | text | who the round was, as the page says it; the model it ran on |
| `verdict` | text | the text step's verdict on the whole puzzle |
| `requests`, `findings`, `blanks` | list, list, map | pages or parts the text step asked for; what it found (`kind`, `target`, `read`, `suggest`, `why`, `status`); fill-in blanks put back from the image |

Optional: `built_from` (the commits of the code and the publication's repo), `send_back` (the
kinds and parts the page offers for sending a puzzle back), `gaps` (parts confirmed not
printed), `supplied` (clues whose text is the text step's alone), `asks`, `pictures`,
`mismatches`, `hand_read`.

## The version: xd_fp

`xd_fp` is the first 12 hex digits of the SHA-1 of `puzzle.xd`'s text (UTF-8, LF line ends)
with its process headers left out: `Source`, `Solution-Source`, `Clue-Source`, `Assembly`,
`Text-Review`, `Proof-Packet`, `Shipped`, `Proof`, `Proof-Edits`, `Numbering-Rule`. Those say
how the puzzle was made, not what it is, so changing one does not undo anyone's Ready.

A Ready counts only for the version it was given on (`design/ship.md`). So a packet whose
`puzzle.xd` does not have the fingerprint `review.json` gives is a problem: the page would show
one puzzle and ship another.

A packet's identity is this fingerprint, not the code that built it. Moving or renaming the
code that writes packets changes no packet.

## checks.json

Optional. `xd_fp` (the version it was made for), `decision` (triage's disposition), `ship`
(`ok`, `findings`, `incomplete`, `xd_fp`: the ship check, xword-ocr `docs/ship-gate.md`),
`items` (each with a row `key`, `what` was found and `from` which check), and, in the assembled
form, `pid` and `from` (where triage and the review were read).

## What the check says

A **problem** is something a reader would break on or be misled by: a missing or unreadable
`ocr.json` or `review.json`; a required field missing or of the wrong type; a grid whose rows
differ in length or hold other characters; a key of another size than the grid; a box that is
not four numbers; an image named and not in the folder; a `puzzle.xd` that is not the version
`review.json` gives; a `format` the check does not know.

A **note** is a valid packet that differs from what today's writers write: the task form; no
`grid.png`, `answers.png` or `_src/`; a review without `reviewer`, `verdict`, `requests`,
`findings` or `blanks`; a `checks.json` made for another version.

The check does not yet look inside `candidates`, `stages`, `findings`, `requests` or
`ai_review.json`, and it does not open the images.

## Earlier packets

Run over everything on disk, the check finds problems only in superseded folders:

- Earlier GAMES 1977-79 runs lack fields the packet gained as the runs went on (`editor`,
  `feature`, `metadata`).
- Judge's and GAMES's working folders (`tasks`, `tasks-batch*`, `import-ready`, `volunteer`,
  `prcheck`) hold a reviewer's `review.json` in an older shape (`unsure` as a list, no
  `matches_xd`), and some name images that are no longer beside them.
- Two Judge packets (`judge1925-02-14` in tasks-batch7, `judge1924-12-06` in tasks-batch8)
  carry a 9x9 key against a larger grid. Judge's final set has no such packet.
- `tests/data/linked` holds five packets cut down to what the ship tests read; they are test
  data, not whole packets.

None of these is rebuilt. They are listed so that a problem in a current batch is not mistaken
for one of them.
