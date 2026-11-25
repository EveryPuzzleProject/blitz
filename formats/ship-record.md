# The ship record's grades, version 1

Every puzzle of a batch leaves the run with a grade, which says how far to trust it
(`design/v3-agent-forward.md`, "Every puzzle exits with a grade"). `blitz ship` works the grade
out and writes it in three places: the batch's ship record, the puzzle's provenance row, and
its as-shipped file. It is never written into the xd: by `design/xd-fields.md` a grade is
provenance, and whether a short form of it belongs in the xd is still open with the owner.

This document covers the grade fields, the batch digest's fields and the stubs of deferred
puzzles. The ship record's older fields (`status`, `reason`, `queue`, `asks`, `broken`, the
edition) are in `design/ship.md`, "What it writes" and "The queues", and are not checked here.

Version 1 is the record as `blitz ship` first wrote it with grades (branch
`claude/silly-williamson-05f530`, 2026-11-25). The writer is `ship.grade_of`, `ship.digest` and
`ship.record`.

```
uv run blitz check-format <snapshot>/ship.json <pub>/pipeline/ship/<batch>.json <pub>/provenance.jsonl [--notes] [--lines]
```

## Where it is

| File | Holds |
|---|---|
| `<pub>/pipeline/ship/<batch>.json` | the batch's ship record (`blitz ship --record` or `--write`) |
| `<snapshot>/ship.json`; on the site `batch/<batch>/ship.json` | the copy the batch page draws (`--snapshot`, `--publish`): review-site account names left out |
| `<pub>/provenance.jsonl` | one row per shipped puzzle; `grade` on each row written since the grades |
| `as-shipped/<pid>.json` beside either record | the xd as it ships, with the same `grade` object as the provenance row |

A record with a `format` field says `"format": "ship-record/1"`. A record with no puzzle
graded is from before the grades: valid, and the check says so as a note.

## The grades

| Grade | Means | From |
|---|---|---|
| `clean` | the ship check passed and nothing was flagged | triage's `ship.ok`, and no flag (below) |
| `reviewed` | flags were raised, and a review settled them | an AI proof reviewer's Ready on this version of the puzzle, or the Ready of the person whose word ships it |
| `doubts` | flags stay open | an AI reviewer's Not ready (its comments are the doubts), or flags no review has looked at, or a candidate clue list nobody decided |
| `incomplete` | a part was never found or never read; the gaps are named | the ship check's `incomplete`; triage's blocking parts of kind `missing-part` or `ocr-broken`; triage's reasons of class `gap` |
| `held` | the structure does not hold, or a protection of the ship rule holds it | a blocking part of any other kind (`mixed`, `other`, or none recorded); or the rule would hold the puzzle with every grade on: a person's Not ready, the owner's hold, an edit with no record, a packet that doesn't show its xd |
| `deferred` | known, not transcribed | a person's set-aside (`setaside:<pid>`), or the publication's scope rule |
| `not-a-crossword` | dropped | `drop:<pid>` |

- A **flag** is one of triage's reasons of class `defect` and severity `proof`, or a finding of
  the ship check that isn't incompleteness. The ship check's own Ready settles none.
- A person's Ready that ships a puzzle settles its flags and what triage asked of the pipeline
  (its blocking parts): the owner's decision overrides. What the ship check finds missing
  stays a gap unless their edits fill it.
- The order of precedence is `held`, `incomplete`, `doubts`, `reviewed`, `clean`. An incomplete
  puzzle can also list open doubts.
- `held` is exactly the puzzles the ship rule would hold with every grade on. So a grade in
  `clean`, `reviewed`, `doubts` or `incomplete` is one the rule ships when the batch opts in.
- Nothing is read from the scan. A grade is worked out from `triage.json`, the ledger and the
  packet's `ocr.json` (`candidates`).

## Shipping by grade

`fixes/ship-rule.json` takes `ship_grades`, a list of any of `clean`, `reviewed`, `doubts`,
`incomplete`, for the publication or for one batch (`"batches": {"<batch>": {...}}`). It is
empty by default, and then nothing ships by its grade. `design/ship.md`, "Shipping by grade",
has the rule. The record's `rule.ship_grades` and `grades.ships` say what the record was made
with.

## In the record

| Field | Holds |
|---|---|
| `format` | `"ship-record/1"` |
| `grades` | `{order: [the seven grades, as above], ships: [the grades this batch ships by]}` |
| `counts.grades` | `{grade: how many puzzles}`; they add up to `counts.puzzles` |
| `counts.grade_ships` | `{grade: how many of them ship}` (`status` shipped or shippable) |
| `sample` | the owner's reading sample: `{per_grade, of: [grades], from, by, pool: {grade: how many ship}, picked: {grade: [pid]}}` |
| `walk` | the pids of the puzzles that ship, in the order the batch page steps through them |
| `failures` | the kinds of failure, ranked by puzzles: `[{code, kind, stage, means, puzzles, pids}]` |
| `scope` | only when the publication has a scope rule: `{rule: {kind: import or defer}, recorded_by: {kind: what records it}, stubs: how many}` |

**The sample.** Up to `per_grade` (10) puzzles that ship from each grade of `of` (clean,
reviewed, doubts): the ones with the smallest sha1 of `<batch>:<pid>`. That is random with
respect to the puzzles and the same each time the record is made, so the reading list does not
move. The page marks these rows and draws no sample of its own.

**The failures.** `kind` is `held` (a held puzzle's diagnosis), `gap` (a gap of any puzzle) or
`doubt` (an open doubt of any puzzle). `code` is the record's own: a triage reason code, a ship
check finding, a hold reason, `ai-question` or `candidate-undecided`. `means` is triage's own
words for its code (its record's `groups`), or blitz's for the others; `stage` is the stage a
gap or a hold points to, `""` when none is recorded. A puzzle counts once for each kind it has.

## In a puzzle's row

| Field | Holds |
|---|---|
| `grade` | one of the seven |
| `grade_why` | one line, in words |
| `flags` | how many flags the checks raised |
| `settled` | `{by, kind, at}` of the review that settled them, or `null` |
| `doubts` | the open ones: `[{row, rows?, text, code, from}]` |
| `gaps` | `[{what, code, stage, detail, row}]` |
| `diagnosis` | a held puzzle's: `{stage, what, code, detail}`; `null` otherwise |
| `grade_order` | the row's place in the digest: by grade, then id. 0 to n-1 |
| `to_read` | `true` when the row is in `sample.picked` |
| `stub` | a deferred puzzle's: `{pid, issue, scan, leaf, size, kind, kind_from, why}` |

- `row` is the proof page's key for the row, so the link is `?p=<pid>&k=<row>`: `clue:A12`,
  `line:B3`, `cell:r3c4`, `ev:title`, `meta:note`, `candidate:<id>`, `grid`, or `""` when the
  record names no row. `rows` lists every row a reason names, when more than one.
- A doubt's `from` is `triage`, `ship check`, `assembly`, or the AI reviewer as the ledger
  names it. Its `code` is the reason or finding code, `ai-question` for an AI reviewer's own
  question, `candidate-undecided` for a candidate list.
- A stub's `kind` is `cryptic`, `variety`, `crossword`, or `""` when no milestone recorded
  one, and `kind_from` names what recorded it (`triage: cryptic-no-key`). Its thumbnail is the
  batch snapshot's (`batch.json`), not a field here.
- In the public copy a helper is "a helper" and the owner's site account "the owner", as in
  the rest of the record.

## In the provenance row and the as-shipped file

`grade: {grade, why, flags, settled, doubts, gaps}`, the same values as the row's, with
`grade_why` as `why`. A puzzle that shipped is never `held`, `deferred` or `not-a-crossword`.

## What the check reads

`blitz check-format` on a ship record: each grade is one of the seven; doubts, gaps, the
diagnosis and the stub have their fields, and each `row` is a proof-page key; a `doubts` puzzle
lists a doubt, an `incomplete` one names a gap, a `held` one has a diagnosis, a `reviewed` one
says who settled it; nothing that ships is graded `held`, `deferred` or `not-a-crossword`; the
counts agree with the rows; `grade_order` is each row's own place; `walk` is exactly what
ships, in that order, each with an `as_shipped` fingerprint; the sample's puzzles ship at the
grade they are listed under and are the rows marked `to_read`; `failures` is ranked. On
`provenance.jsonl`: each row's `grade`, where it has one. It reads the files and nothing else.
