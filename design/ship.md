# Shipping a batch: from reviewed puzzles to xd files to a gxd export

Built 2026-11-10 for GAMES 1977-79, the first v2 batch to ship. It is the last milestone of a
batch and lives in blitz (`src/blitz/ship.py`), since everything after the packet is blitz's.
It reads what the earlier milestones recorded and works nothing out about a puzzle itself.

```
uv run blitz ship games --proof ../xword-ocr/harvests/games-7779/proof/run15-restart --batch games-1977-79            # dry run
uv run blitz ship games --proof ... --batch games-1977-79 --write                                                     # write it
uv run blitz ship games --proof ... --batch games-1977-79 --publish                                                   # ship.json to the site
uv run blitz ship-export games --dest ../blitz-work/gxd-export-games-1977-79 --pages                                   # the gxd export, as files
uv run blitz ship collegian --proof <run's proof packets> --batch collegian-1976-81 --record                          # status only: the record, nothing shipped
```

## What it reads

| what | where | made by |
|---|---|---|
| the puzzle as reviewed | `<harvest>/proof/<run>/<pid>/puzzle.xd`, `review.json` (xd_fp, matches_xd), `ocr.json` (page, printed lines and their labels) | xword-ocr proof packets |
| reason codes and the ship check | `<harvest>/triage/<run>/triage.json` (`reasons[].code`, `ship.ok`, `ship.incomplete`) | xword-ocr triage |
| decisions | `<pub>/fixes/decisions.jsonl`: `proof:<pid>` (one per reviewer), `batch:<pid>`, `drop:<pid>`, `setaside:<pid>` | the batch and proof pages, agents |
| helpers' decisions | the review site (`blitz site-import`, or `--decisions FILE`) | the hosted proof page |

Helpers' Ready / Not ready are taken into the ledger first (`proof:<pid>` by `<helper> (review
site)`, the shape xword-ocr's `take_decisions` writes), so the ledger is the whole record.

## The ship rule

One function, `ship.standing()`. Its options are `ship.Rule`, read from the publication's
`fixes/ship-rule.json` and overridden on the command line.

1. The owner's own latest decision wins: the later of the batch page's Ship / Hold and their
   own proof page's Ready / Not ready. A proof record is the owner's when its `via` is neither
   `review site` nor `agent review` (their own tools), or when it was made on the review site
   under one of the names in the rule's `owner` list. It overrides a Not ready by anyone else,
   earlier or later; the reason then says so ("over a Not ready by ..., given after it").
2. Otherwise any Not ready, a person's or the AI proof reviewer's, holds the puzzle for the
   owner.
3. Otherwise one person's Ready ships it.
4. Otherwise it waits for a Ready.

A Ready counts only for the version of the puzzle it was given on (the packet's `xd_fp`, or one
of `xd_fp_same`).

| option | default | what it does |
|---|---|---|
| `ai_ready` | `off` | `both`: with no person's Ready, the AI proof reviewer's Ready and a passing ship check together count as the one Ready. `either`: one of them is enough (xword-ocr docs/ship-gate.md's design). GAMES: `both`, the owner's decision of 2026-11-10. |
| `hold_codes` | `["clue-typed"]` | triage reason codes that hold a puzzle whoever said Ready. `clue-typed` (a clue the text step supplied with no OCR reading) doesn't exist in triage yet; when it does, such puzzles are held with no change here. |
| `owner` | `[]` | the owner's own accounts on the review site. Who the owner is isn't in the code: it is this list in the publication's `fixes/ship-rule.json` (GAMES: `oops6498`, confirmed by the owner 2026-11-10). The site's copy of the ship record shows such a decision as "the owner", a helper's as "a helper". |
| `ignore` | `[]` | review-site accounts whose decisions don't count (GAMES: `walkthrough test`, a scripted usability test that left a Ready and a Not ready on the live site). |

A puzzle the rule passes can still be held by the import, each with its own reason:

| reason | meaning |
|---|---|
| `incomplete` | the ship check found missing or empty clues, an unsolved grid, a partial second clue set: no Ready makes it whole |
| `packet-stale` | the proof packet doesn't show its xd: rebuild the packet |
| `proof-stale` | the only Ready was on an earlier version of the puzzle |
| `edits-differ` | two reviewers changed the same thing two ways |
| `edits-unapplied` | a proof-page edit the import doesn't apply: a line's label or keep (`line:B3`), a header's evidence line (`ev:title`), a fill-in blank, a rebus square, anything in a linked-ends puzzle |
| `xd-exists` | `xd/` already has another file under its id |

The rule's own reasons: `owner-hold`, `not-ready`, `no-ready`, `needs-work` (no Ready, and
triage's disposition isn't ready), and each hold code.

## What it writes (publication repo)

- `xd/<xdid>.xd`: the packet's `puzzle.xd` with the Ready reviewers' edits applied (clue text,
  key squares with the answers worked out again, the header fields). Its headers are the
  packet's; nothing about shipping is added to the file.
- `fixes/xdids.tsv`: ids pinned for puzzles that had none. A puzzle keeps the id
  `pipeline/ids.tsv` or `fixes/xdids.tsv` already gives its place on the page.
- `provenance.jsonl`, append-only, the last row for an xdid stands:
  `{xdid, pid, batch, run, packet, packet_xd, xd, shipped: {at, rule, ai_ready, by, why}, said:
  [{who, kind, answer, at, stale}], edits: {applied, from}, check, codes, sources: {grid, clues,
  key}, printed: [{label, text}]}`. `kind` is owner, helper, ai or check; `printed` is the kept
  printed lines with the text step's labels, which the export's Notes rule picks from.
- `gxd-exports.tsv`: judge's columns (`gxd_id xdid date number gxd_mr exported proof_url
  package_url scan_url ai_reviewed person_reviewed credit`), rebuilt from provenance.jsonl;
  `gxd_mr` and `exported` are filled by hand after a merge and kept.
- `pipeline/ship/<batch>.json`, the batch's ship record:
  `{batch, run, packets, rule, at, counts: {puzzles, shipped, shippable, held, out, held_by,
  ships_with, queues, reviewed, spot_check}, groups, spot, puzzles: [{pid, xdid, title, date,
  status, reason, rule, ships_with, why, said, check, queue, group, order, reviewed, spot_check,
  asks, also, broken}]}`. `status` is shipped (in `xd/` as it stands), shippable (passes, not
  written), held, or out (set aside, not a crossword). `ships_with` is the smallest `ai_ready`
  setting under which the rule passes the puzzle. Helpers' names are left out. The queue fields
  are the next section.

A dry run writes none of this. Three options write the record alone and ship nothing (status
only, for a batch that isn't shipping yet): `--record` (the publication repo's
`pipeline/ship/<batch>.json`), `--snapshot <folder>` (a `ship.json` there) and `--publish` (the
site's copy). Without `--write` a passing puzzle shows as ready to ship, never as shipped.

## The queues: what the batch asks of people

Every puzzle of the batch is in exactly one queue, and the record says which. This lives in the
ship record, not in the batch snapshot, because it is the ship rule's answer: the snapshot is
the watch's picture of the pipeline (triage's disposition, the boxes, the thumbnails), and what a
batch still needs from a person depends on the decisions in the ledger and on the site, the
rule's options and the import's own holds, which only `blitz ship` puts together. The batch page
draws these fields and works none of them out.

| `queue` | from | who it is for |
|---|---|---|
| `question` | held as `not-ready`, `owner-hold` or `edits-differ` | a person: answer on the proof page, and it can ship. The page's default list and its walk. |
| `unchecked` | held as `no-ready` or `proof-stale` | a person: nobody's Ready counts for it yet, so it wants a whole proofread. No question to lead with. |
| `broken` | every other hold: `needs-work`, `incomplete`, `edits-unapplied`, `packet-stale`, `no-packet`, `xd-exists`, a hold code | agents (as kinds of failure) and the maintainer (a diagnosis of the stage). Shown with its reason; no proofreading ask. |
| `shippable` | passes, not written | nobody: `--write` ships it |
| `shipped` | in `xd/` | nobody; a sample goes to the maintainer (`spot_check`) |
| `set-aside`, `not-a-crossword` | the ledger's `setaside:` / `drop:` | nobody |

Per puzzle:

- `asks` (a `question` puzzle): `[{who, kind, at, row, text, suggest, group}]`, one per comment of
  each Not ready that stands (a Not ready with no comments gives one ask with its note). `who` is
  the reviewer as the ledger names them (a helper: "a helper"), `kind` owner / helper / ai /
  import, `row` the proof page's key for what the question is about, so the link is
  `?p=<pid>&k=<row>` (`ev:title`, `clue:A12`, `cell:r3c4`, `line:B2`, `grid`; "" for the puzzle as
  a whole). `text` is the comment without the reviewer's "Flag for the maintainer:", `suggest`
  what follows its "Suggest:".
- `group` on an ask: the shared question it belongs to, by the header it is about (`ev:title` and
  `meta:title` are `title`; author is `byline`; note is `notes`); "" for a clue, a square or a
  printed line, which is that puzzle's own question. `group` on the puzzle: the largest group
  among its asks. The record's `groups` lists them largest first: `[{key, label, puzzles, asks}]`
  (`puzzles` counts by the puzzle's own `group`, so the groups and the ungrouped add up to the
  queue; `asks` counts every puzzle with a question in the group).
- `also` (a `question` puzzle): what the ship check found incomplete. An answer doesn't mend it,
  so the card says so beside the question.
- `broken` (a `broken` puzzle): `[{what, stage, code, detail}]`. For `needs-work` these are
  triage's blocking parts and the stage each restarts from. For `incomplete`, the ship check's
  lines, with the stage its finding points to (`grid-unsolved`: key reading; `clue-empty`: parts;
  `clue-missing`, `clue-extra`, `second-set-missing`: assembly). For the import's own holds:
  `packet-stale` and `no-packet` point to the proof packet, `edits-unapplied` and `xd-exists` to
  the import, `clue-typed` to the text step. A stage that nothing recorded is "".
- `order`: the puzzle's place in the batch's walk, so the page never sorts by its own idea.
  Questions first: the shared groups, largest first; inside a group the puzzles with nothing but
  shared questions, then the fewest questions; then the puzzles with only their own questions.
  After them the other queues in the table's order, by id.
- `reviewed`: a person (the owner or a helper) has said Ready or Not ready on it. An AI's review
  or the ship check never sets it. This is what "Reviewed" means on the page: a fact about a
  puzzle, shown on its card and as one count, not a queue.
- `spot_check`: in the maintainer's spot-check sample. The sample is fixed by the id alone
  (`sha1(pid) mod 10 == 0`, about one in ten), taken from the puzzles shipped on someone else's
  word than the owner's (`rule` is not `owner`). A puzzle is in it or out of it for good; the
  record's `spot` says how it was drawn.

`counts.queues` has every queue's count; they add up to `counts.puzzles`.

## Where a person sees it

The batch page (`/review/batch/?b=<batch>`) reads `ship.json` beside the batch's `batch.json`
(`blitz ship --publish` puts it there; `--snapshot <folder>` for a local copy). The page is the
record's queues:

- One chip per queue, with counts that add up to the batch. It opens on **Held on a question**,
  in the record's order, a heading per shared question; the main button walks that list on the
  proof page, opening at the first question's row. Each card leads with its questions: who asked,
  the row (a link to `?p=<pid>&k=<row>`), the text, what was suggested.
- **Not checked yet** has a Proofread button and its own walk. **Broken in the pipeline** shows
  what is broken and the stage it points to (a filter per stage), and asks nobody to proofread.
- **Shipped** cards say the id and why it shipped. **Spot-check** is the recorded sample, for the
  maintainer, with its own walk.
- A puzzle the snapshot lists and the record doesn't (one triage dropped before the record's
  list was made) shows under Not a crossword when the snapshot recorded the drop, and says the
  snapshot is its source; any other shows as Not recorded.
- A batch with no record, or one from before the queues, says "not recorded": every puzzle is
  listed with triage's word, and no walk is offered.

Answers given on the site after the record was made show on the cards (the live tally); a puzzle
changes queue only when `blitz ship` makes the record again. The page draws the record; it never
applies the rule. To work on the page, `tools/review_dev.py --data <folder>` serves it over a
copy of the snapshots and reloads on every edit.

## Status and milestones on the EPP site

Nothing is published by `--write`. Two things carry a batch's status outward, both made from
the same plan:

- `<pub>/pipeline/ship/<batch>.json` in the publication's repo (public): `counts` (puzzles,
  shipped, shippable, held, out, held_by) and every puzzle's status. This is the input for a
  status page or a milestone note ("35 of 76 shipped"); `gxd-exports.tsv` lists the shipped
  puzzles with their proof pages.
- `ship.json` on the review site, which the batch page draws. To publish it, from a blitz
  checkout that has this code, with the publication's checkout beside it holding the shipped
  `xd/` (otherwise shipped puzzles show as "ready to ship"):

  ```
  uv run blitz ship games --proof ../xword-ocr/harvests/games-7779/proof/run15-restart --batch games-1977-79 --publish
  ```

  It needs the site's R2 settings (`R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`,
  `R2_BUCKET`) and writes one object, `batch/games-1977-79/ship.json`.

## The gxd export

`blitz ship-export <pub> --dest <folder>` writes files only: `<shelf>/<YYYY>/<gxd id>.xd`,
`receipts.tsv`, `publications.tsv`, `source-pages.tsv` (every page the puzzles were read from),
`source/` with `--pages`, `held-back.tsv`, and `COMMANDS.md`, the commands that would make
the merge request. Nothing is pushed. gxd branches go to the fork only, with the owner's
go-ahead.

An exported file is the puzzle only: Title, Author (tidied), Editor, Date, Number, Byline,
Rebus, Special; the grid; the clues with their `^Easy` lines; and the printed lines the Notes
rule takes (the ledger's `notes-rule:<pubid>`, else intro and instructions). Sources, OCR flags
and everything else stay in provenance.jsonl. `Feature` is left out until `--feature-as` says
which gxd header it becomes. A puzzle carrying `cryptic-no-key` stays in `xd/` and isn't
exported.

## Not done yet

- xword-ocr still has its own copy of the rule (`batchpage.standing`, where an AI's Ready
  always counts) and its own `import-batch`; the local watch's batch page shows that one. They
  should go, or read `pipeline/ship/<batch>.json`.
- `puzzles.tsv` and the publication's status page (`games/tools/render.py`) don't read the ship
  record yet; the EPP home page has no milestone line fed from it.
- A cryptic that has a key grid carries no code saying it's a cryptic, so the export can't hold
  it back.
- Pages v2 read that the scans repo never backed up have no capture date for the receipts.
