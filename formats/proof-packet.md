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
| `ai_review.json` | an AI proof reviewer's answer, when one ran, and a second opinion's beside it | optional |

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
| `clues` | id to clue | each clue: `text`; `box` where it was read from; optional `flags`, `image` (when on another page), `printed` (a linked-ends pair), `read_from` (below) |

Also in the assembled and hand forms:

| Field | Type | Holds |
|---|---|---|
| `puzzle_number`, `editor`, `feature`, `issue_date` | text | more headers; empty when none |
| `lines` | list | every printed line that is not a clue: `n` (the line is row `B<n>`), `text`, `box`; `keep` (whether it is in the xd's printed block), `label` (what the line is) and `by` (who or what said so); optional `image`, `clues` (the clues assembly read from it, below; a line that was nothing else has `label` `clues`, not kept) |
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
printed), `supplied` (clues whose text is the text step's alone, below), `asks`, `pictures`,
`mismatches`, `hand_read`.

### A clue the reading filed elsewhere: ocr.json's read_from

Assembly gives back to its slot a clue the OCR read but the list put somewhere else (xword-ocr
`claims.py`), by the number printed before it: a line read as a printed line near the puzzle
(`how` `line`: the column's last rows under the grid), a line the list gave another number
(`moved`, only when it is printed in its slot's place in the column), or two clues read as one
line (`split`). `read_from` is `{how, from, text}`: `from` the clue it came out of (`D54`) or
`printed line`; `text` the reading it came out of. The clue's `box` is that reading's box, and
its `flags` say the same in words (`read as a printed line: ...`, `read under D54: ...`, `read
run into D50: ...`). Such a clue is the OCR's reading, not typed: the text step checks it on its
crop like any doubted line.

### supplied: what the text step gave where the OCR read nothing

`supplied` maps a clue's row (`clue:D12`) to:

| Field | Holds |
|---|---|
| `kind` | `supplied` (printed clue text, typed by the text step), `replaced` (the reading was another clue's), `picture` (a drawing described: not printed text), `no-clue-printed` (an entry printed with no clue: no text), `withdrawn` (the reading here is another clue's, or only part of this one's with the rest on no crop, says the text step: written missing) |
| `says` | the row's badge, in words: typed by which stage, from which crop, read twice or not |
| `sourced` | whether a source crop is recorded |
| `by` | the stage that gave it (`the text step`) |
| `from`, `lines` | the source crop's label and the printed lines within it |
| `box`, `image` | the source crop on one of the packet's page images, in that image's pixels; `page` instead when the page isn't in the packet |
| `readings`, `agree` | a typed clue read a second time from the same crop by another agent that had not seen the first reading: `[{text, by}, {text, by, unsure?}]`, the text step's first; `agree` whether the two are the same (letters and digits, a fill-in blank however long) and the second raised no doubt (`unsure`) |
| `written` | `false`: the text step typed it and named no source crop, so it was not written. The clue stays missing; the row says so, with no text |
| `reading`, `why`, `wrong`, `of` | a `withdrawn` row's: the OCR's reading that was not written, the text step's reason, `another-clue` or `cut-off`, and the clue the reading is (when named). Always `written: false` |

A typed clue is written only with its source crop (2026-11-26); `check-format` notes a packet made
before that, whose unsourced typed clues were written. What holds is the source, not the
agreement (the owner, 2026-11-26): a typed clue with a recorded crop is triage's
`clue-model-read`, never a hold; readings that differ, or a doubt from the second reader, are
`clue-reading-differs`, a doubt on the row and in the grade's `doubts`. `clue-typed` is only a
typed clue with no recorded source; it holds (games' `hold_codes`).

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

## ai_review.json

Optional: the AI proof reviewer's record (xword-ocr `proofreview.py`), a copy of the ledger's
`proof:<pid>` record that the proof page draws as the AI's round. The ledger stays the source of
truth.

| Field | Holds |
|---|---|
| `record`, `ledger` | the record's id and the ledger it is in |
| `by`, `model_id` | "Claude (AI proof reviewer, <model>)", and the model |
| `answer` | `ready` or `notready` |
| `at`, `xd_fp` | when, and the version of the puzzle it was made on |
| `review` | `{edits, comments, status, note, xd, typos?, key_corrections?, second_opinion?}`, keyed as the proof page keys its rows |
| `second` | a second opinion's record, the same fields, when one was made |

**Flags.** Each flag is a comment whose text begins "Flag for the maintainer:". Since v3 slice 5
(2026-11-25) a flag carries `kind`, one of a closed set; it is optional, so a record from before
it stays valid, and a flag with no kind is read as before: an AI's Not ready holds the puzzle.

| `kind` | The reviewer says | At ship (`blitz ship`, `grade_of`) |
|---|---|---|
| `structure` | the puzzle is put together wrong: another puzzle's grid or answer key, clues for another grid, two puzzles mixed, misnumbered all through | `held`, diagnosis `ai-structure`, stage assembly |
| `missing` | a part is not there or was never read: a clue, a list, the key (a grid of dots), a line cut off | `incomplete`, a gap `ai-missing` |
| `grid-reading` | a doubt about one square of the key | `doubts` |
| `clue-reading` | a doubt about a clue's or a printed line's reading | `doubts` |
| `header` | a doubt about a header's value | `doubts` |
| `misprint` | the print may be wrong, or on purpose (typo or wordplay) | `doubts` |
| `convention` | the reading is right; the question is how the xd holds it (a symbol in a square, an unclued entry) | `doubts` |
| `extra` | something that isn't this puzzle's and can go (another puzzle's list in the notes) | `doubts` |

**The second opinion.** A first review that is Not ready, with every flag of a kind and none
`structure`, goes to a second reviewer on a different model (the first on Opus, the second on
Sonnet; never Fable), which reads the same input (`input.md` and crops) without the first's
answer. Its record sits in the ledger beside the first's, by its own reviewer, and its `review`
carries `second_opinion`:

| Field | Holds |
|---|---|
| `of`, `of_at`, `of_answer` | the first review's reviewer, its record's time, its answer |
| `of_flags` | the first's flags: `[{key, kind}]` |
| `settles` | the first's flags this review's own edits settle the same way, when it is Ready: `[{key, kind, edit: {key: value}}]` (the square the first proposed changing to O, edited to O) |

How the two make a grade, first match wins:

1. Either names a `structure` problem: `held`.
2. Either names a `missing` part: `incomplete`, the flag as a gap.
3. The second is Ready and settles every flag of the first's: `reviewed`, settled by both; its
   edits are the ones applied.
4. Otherwise `doubts`: the first's flags it did not settle stay open, each marked `second: also`
   (the second flagged the same row) or `second: nothing` (it didn't), and the second's own
   flags are added. A second's Ready that settles only some of them is a disagreement, and a
   disagreement stays a doubt (`design/v3-agent-forward.md`).

An AI's Not ready whose flags are all of a kind other than `structure` doesn't stop a puzzle
shipping by its grade (`ship_grades`); it still stops an AI's Ready shipping it (`ai_ready`), and
with `ship_grades` off it holds as before.

The check: the fields; a `kind` outside the set is a problem, a record whose flags have no kind a
note; a second opinion must name the first's reviewer, be on another model, and make every edit
its `settles` names.

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
`findings` or `blanks`; a `checks.json` made for another version; an `ai_review.json` whose flags have no kind.

The check does not yet look inside `candidates`, `stages`, `findings` or `requests`, and it
does not open the images.

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
