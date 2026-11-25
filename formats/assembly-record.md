# The assembly record, version 1

One issue's parts linked into puzzles, written once and read by every step after: the proof
packet build, the census, the text step packets, the remedy case file, the watch page's
Assembled views. Assembling is the slow part of each of those (5 to 20 seconds an issue on
GAMES 1977-79), so it is recorded per issue with what it was made from, and made again only
when one of those things changes.

Version 1 is the record as xword-ocr first wrote it (branch `claude/assembly-record`,
2026-11-25). The writer is `watch.Watch._assemble` with `stages.assembly_put`; how to use it is
in xword-ocr `docs/stages.md`, "Assembly: one record per issue".

```
uv run blitz check-format <harvest>/assembly [--artifacts <xword-ocr>/.cache/artifacts] [--notes] [--lines]
```

## Where it is

| File | Holds |
|---|---|
| `<harvest>/assembly/issue/<date>.json` | the issue's records, one per reading: small, durable, readable |
| `<store>/assembly/<ab>/<hash>.json.gz` | the artifact a record names: what assembly made, gzipped JSON, named by the sha256 of its uncompressed bytes (`<ab>` is the hash's first two characters) |

The records are in the harvest folder, not the publication's repo, because an issue is
assembled from one harvest's pages: two harvests of a publication each have their own. The
store is the one the page stages use (xword-ocr `.cache/artifacts`).

## The unit

`issue:<date>/<reading>`, for example `issue:1977-09-01/hands-off`. The readings:

| Reading | The pages are read with |
|---|---|
| `hands-off` | the harvest's own regions, nothing a person did (pages a restart names are read with their recorded boxes) |
| `reviewed` | a person's boxes, marks and verdicts |
| `hands-off-without-drops` | as `hands-off`, the grids standing dropped or set aside left out, so their parts go to the puzzles they were printed for. Written only for an issue that has such a grid; a run's census and text step packets are built from it |

## The record file

An object of units, each with one stage, `assembly`:

```json
{
 "issue:1977-09-01/hands-off": {
  "assembly": {
   "format": "assembly-record/1",
   "stage": "assembly",
   "version": "assembly/1",
   "settings": {"hands_off": true, "scope": "both", "linked_ends": false, "keys_next_issue": false},
   "inputs": {"issues": "sha256:…", "page:<scan>/0026": "sha256:…", "page:<scan>/0063": "sha256:…"},
   "output": "sha256:…",
   "made": "2026-11-25T22:02:27+00:00",
   "took": 16.2,
   "code": "xword-ocr 0.1.0"
  }
 }
}
```

| Field | Holds |
|---|---|
| `format` | `assembly-record/1` |
| `stage` | `assembly` |
| `version` | the assembly code's version when the record was made (`assembly/<n>`, bumped by hand in xword-ocr `stages.py` when what assembly makes changes) |
| `settings` | the reading and the switches assembly reads: `hands_off`; `scope` (hands-off only: `regions`, `page` or `both`); `linked_ends` and `keys_next_issue` (the fix file's); `keep_partial` when the fix file sets it |
| `inputs` | what the record was made from, each as a name and a sha256 hash (below) |
| `output` | the artifact's hash |
| `made` | when, UTC |
| `took` | seconds the issue took to assemble. Estimates before a long run are made from these |
| `code` | the writer's package version |

### Inputs

| Name | Covers |
|---|---|
| `page:<scan>/<leaf, 4 digits>` | one page that was read: its analysis in the harvest snapshot, its OCR artifact, its image, its entry in the region view (the harvest's regions; a person's boxes, marks and grid fixes from the ledger), and whether a restart names it. The parts are in the artifact's `pages_read` |
| `issues` | the issue's date, the next issue's, and each issue's pages in order |
| `given_keys` | the key pairings the source made (a folder's `answers` column), when it made any |
| `left_out` | the grids left out of this issue (place, black squares, puzzle id), for `hands-off-without-drops` |

The pages are this issue's, the next issue's (for its answer grids: a key printed an issue
later), another issue's that the source pairs a key with, and a page read whole for a list
headed "(con't.)".

**A record is current** when its `version`, `settings` and every input are what they would be
now, and no input has appeared or gone. Otherwise it is stale: the next caller that needs the
issue assembles it again, that issue only. A view never does: it draws the stale record and
says what changed. So a decision or fix touching one issue's pages makes that issue's records
stale, and the issue before it when those pages hold its keys, and no other.

## The artifact

```json
{"format": "assembly-record/1", "pubid": "games", "date": "1977-09-01", "variant": "hands-off",
 "next": "1977-11-01", "pages_read": [...], "puzzles": [...], "loose": [...], "pages": [...],
 "state": {...}}
```

| Field | Holds |
|---|---|
| `format` | `assembly-record/1` |
| `pubid`, `date`, `variant` | the publication, the issue, the reading (the unit's) |
| `next` | the next issue's date, or null for the last |
| `pages_read` | one entry per `page:` input: `scan`, `leaf`, `role` (`issue`, `next issue`, `another issue`, `continued list`), and the hashes its input covers: `analysis`, `ocr`, `image`, `view` (each a sha256 or null), `restarted`. `extract` is the page's extract record at the time, to trace back by; it is not part of the input (the snapshot's analysis is what assembly read, and can be an earlier reading) |
| `puzzles` | each grid taken as a crossword, as plain JSON (below) |
| `loose` | each part no puzzle took: `kind` (`grid`, `clues`, `answer grid`), `label`, `scan`, `leaf`, `box`, `why`; a grid's `title`; an answer grid's `key_like` (it looks like a crossword's key) |
| `pages` | the issue's pages as they were read: `scan`, `leaf`, `size`, `boxes` (each `box`, `is`, and the `parts` found in it: `kind`, `box`, `label`, …); `continued` on a page read only for a continued list |
| `state` | the same result with the objects the xd is built from (each puzzle's grid, its key's answer grid, its clue lines; every part read), in xword-ocr's `statefile` encoding. For xword-ocr's own callers; any other reader uses the fields above |

A puzzle:

| Field | Holds |
|---|---|
| `grid` | `label`, `size` (rows, columns), `scan`, `leaf`, `box`, `in_box` (which of the page's boxes) |
| `title`, `title_from`, `number` | the heading assembly linked and where from. Headers are proposed later, by the headers step |
| `clues` | `A` and `D`: a list of sets (the first is the clues; a second is a second clue set or a candidate), each with `share` (how much of the grid's slots it fills) and `parts` (`label`, `scan`, `leaf`, `box`, `rects`) |
| `key` | null, or the answer grid matched: `label`, `scan`, `leaf`, `box`, `differ` (black squares that differ), `issue` (`this`, `next`, `other`), `crop` |
| `cryptic` | most clues end with an enumeration: no grid key expected |
| `flags` | what assembly wasn't sure of, in words |
| `heads`, `notes` | the headings and text printed with it, each with `role`, `label`, `scan`, `leaf`, `box` |
| `clue_sets`, `candidates`, `scan` | when present: two printed clue sets; lists that fit and are neither; what is wrong with the scan of its page |

## Coordinates

A `box` is `[x0, y0, x1, y1]` in the pixels of the full-resolution page image (`scan`, `leaf`),
as the harvest read it. This is not the proof packet's frame, whose boxes are in the pixels of
the packet's scaled images.

## What the check reads

`blitz check-format <harvest>/assembly` reads the record files: each unit's name against its
file, the record's fields and their types, the reading against `settings.hands_off`, every
input a sha256. With `--artifacts <store>` it also reads each record's artifact: that it is in
the store under the hash the record names and its bytes have that hash, its fields, that
`pages_read` names the same pages as the record's inputs, and the shape of each puzzle, loose
part and page. It reads no scan and assembles nothing, so it cannot say whether a record is
current: `xword-ocr assembly status` does.
