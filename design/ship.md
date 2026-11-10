# Shipping a batch: from reviewed puzzles to xd files to a gxd export

Built 2026-11-10 for GAMES 1977-79, the first v2 batch to ship. It is the last milestone of a
batch and lives in blitz (`src/blitz/ship.py`), since everything after the packet is blitz's.
It reads what the earlier milestones recorded and works nothing out about a puzzle itself.

```
uv run blitz ship games --proof ../xword-ocr/harvests/games-7779/proof/run15-restart --batch games-1977-79            # dry run
uv run blitz ship games --proof ... --batch games-1977-79 --write                                                     # write it
uv run blitz ship games --proof ... --batch games-1977-79 --publish                                                   # ship.json to the site
uv run blitz ship-export games --dest ../blitz-work/gxd-export-games-1977-79 --pages                                   # the gxd export, as files
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
  ships_with}, puzzles: [{pid, xdid, title, date, status, reason, rule, ships_with, why, said,
  check}]}`. `status` is shipped (in `xd/` as it stands), shippable (passes, not written),
  held, or out (set aside, not a crossword). `ships_with` is the smallest `ai_ready` setting
  under which the rule passes the puzzle. Helpers' names are left out.

## Where a person sees it

The batch page (`/review/batch/?b=<batch>`) reads `ship.json` beside the batch's `batch.json`
(`blitz ship --publish` puts it there; `--snapshot <folder>` for a local copy). It shows a
Shipping row (Shipped, Ready to ship, Held, and the holds by reason, each a filter) and a line on
every card: shipped as which id, or held and why. The page draws the record; it never applies
the rule.

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
