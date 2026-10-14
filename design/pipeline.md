# The pipeline: stages, contributions and state

Draft, 2026-10-14, for review. Nothing here is built yet. It follows
`next-publication.md` (Judge, 2026-10-11) and the GAMES start (2026-10-13), and
keeps the algorithms and review tools we have; what changes is how their work
is stored, re-run and handed between people.

## Why

On 2026-10-13 a day went into GAMES's first steps, almost none of it on
puzzles. The pipeline has two re-entry points, and both are coarse:

- **harvest** reads scans and does everything after, for whole issues;
- **relink** re-derives every puzzle of a publication (keys, ids, fixes, the
  ledger, outputs) on every run: 5 to 60 minutes, whatever changed.

Neither records what its output was made from, so nothing knows what needs
re-running. Puzzle ids were derived again on every run, so a newly found grid
renamed puzzles under reviewed work. And all of the first half runs only on one
machine, so only one person can do it.

## Goals

1. **Each stage can be improved and retested alone**, without fear of regressions
   elsewhere (see *Regressions*). Improve layout analysis,
   run a dozen scans through it, compare the boxes with the last run. Nothing
   downstream re-runs unless its inputs changed.
2. **Any unit of work can be rejected at any stage** into an exception queue,
   with a note, and sent back to an earlier stage. Review tools can sit at any
   stage boundary; human review is possible everywhere, like a factory line.
3. **Contributions are independent.** Each kind of help needs only its own
   resource (see *Contributions*).
4. **Git is the record; SQLite is per session.** A session reads state from git,
   works, and writes it back as a pull request.
5. **Few tokens per puzzle.** Transcribing a puzzle should cost about 10% of
   handing Claude the page and asking for an xd (about 42% today). So every stage
   and tool is something Claude can use instead of reading the scan.
6. **Techniques, not silos.** A publication can need machinery others don't
   (old newsprint is not GAMES), but it is built as a named technique ("old
   newspaper layout") that any publication can switch on and try, never as
   "Boston Globe OCR".

## Stages

| # | Stage | Unit | Makes | Typical exceptions |
|---|---|---|---|---|
| 1 | Source | issue | page images, the source's page text | issue missing, page unreadable |
| 2 | Page OCR | page | text lines with boxes | page needs a better scan |
| 3 | Layout | page | regions: grid, clue block, heading, answer grid, other | grid missed or cut wrong |
| 4 | Extraction | region | grid squares, clue lines, key letters, heading fields | unreadable region |
| 5 | Assembly | issue (or a run of issues) | puzzles: which regions, which key; ids minted; **packet born** | missing part, key with no puzzle, number missing |
| 6 | Validation | puzzle | numbering, clue counts, symmetry, key agrees with grid, word check | structure doesn't hold |
| 7 | AI review | puzzle | edits and comments, appended to the packet | flags a mis-crop: back to 3 |
| 8 | Human review | puzzle | edits, comments, sign-off (on the review site) | Not ready |
| 9 | Package | puzzle | the final xd and packet, in git | |
| 10 | Export | batch | gxd files, receipts, merge request; **xdids assigned here** | |

Page OCR comes before layout because layout reads the text (numbered clue lines,
type size, captions). Assembly is its own stage because much of it can't be done
one puzzle at a time: a key printed weeks later, the same puzzle in two scans,
a numbered series with a gap.

How today's commands map: `harvest` is 1 to 5; `relink` is 5, 6 and applying
the fix file and ledger; `task-packets` is part of 5 and 9; `blitz start` is 7;
the review site is 8; `blitz sync` is 8 into 9; `export-gxd` is 10.

## Artifacts and fingerprints

Every stage writes its output as a JSON artifact with a header:

```json
{"stage": "layout", "version": "layout/7", "settings": {"heading_blocks": true},
 "inputs": {"image": "sha256:…", "ocr": "sha256:…"}, "made": "2026-10-14T…"}
```

- **version** is the stage's own version, bumped when its behaviour changes
  (not the whole package's).
- **inputs** are the hashes of what it read (including a page's hint from the
  fix file). A stage re-runs for a unit when an input hash differs from what's
  recorded. When only its version or settings differ (the code changed), the
  last output stands until someone upgrades that stage for the publication on
  purpose (see *Regressions*).
- **Compare runs:** any stage can run on a subset into a scratch run, and a diff
  command shows what changed (the viewer draws old and new boxes together).
- No pickles. The per-page analysis and key-search caches become these
  artifacts.

## Regressions: versions and an evaluation set

We can't re-run every past publication on every change to OCR or layout, and
we shouldn't need to.

- **Finished work keeps the version that made it.** A code change never alters
  existing outputs by itself; a publication moves to a new stage version only
  when someone runs that stage for it on purpose, and that run ends with a diff.
  (Today `relink` re-derives everything with whatever code is current, which is
  why every change felt like a risk to Judge.)
- **Measure against reviewed truth.** Each stage and technique has a small fixed
  evaluation set (20–30 pages each from Judge, GAMES, later a newspaper or two),
  scored against the reviewed xd files: regions found, squares and clues right.
  It runs in minutes on every change and says *better or worse*, not merely
  *different*.
- **New behaviour sits behind a switch** (a technique), off for publications
  that don't use it, so it can't regress them.
- A full re-run is a deliberate upgrade of one publication, sample first.

## Where state lives

| What | Where | Why |
|---|---|---|
| Page images, page text, OCR, layout and extraction artifacts | the publication's scans store: `<pub>-scans` releases or R2/S3, by hash | too big for git; content-addressed, so shared between sessions |
| Packets (one file per puzzle), exception states, decisions, publication hints, the id registry and aliases | the publication's repo (`judge`, `games`) | the record: reviewable, mergeable, one file per unit so merges are trivial |
| Pipeline index: units, stage status, fingerprints, queues | SQLite, per session | rebuilt from git at the start of a session, written back to git at the end; never the durable copy |
| Live review | Supabase + R2 (the review site) | web-only reviewers; folded back into packets by `blitz sync` |

A session: pull, hydrate SQLite from the repo (fetch artifacts as needed), run
stages for the units claimed, write packets, states and artifact hashes back,
open a pull request.

## Ids

- A puzzle's id is **minted once, at assembly**, and never worked out again:
  `<pub>-<issue>-<n>`, e.g. `games-1977-09-01-3`, `n` the next unused number in
  the issue. Its location (scan, leaf, printed page, position) is data stored
  with it, not part of the name. Gaps don't matter; a late find gets the next
  number. One contributor works on an issue at a time, so numbers can't collide.
- **xdids exist only in the export**, with gxd's same-date suffix rule.
- **Old names stay valid** through an alias table (old xdid → id): Supabase
  rows, links like `?p=judge1931-10-03`, the ledger and fix-file entries keep
  working; nothing is re-uploaded. Judge's and GAMES's `xdids.tsv` files seed it.

## Packets

- Born at assembly, one per puzzle, in the publication's repo. It references its
  regions and their artifacts, carries the validation results, and accumulates
  every review: each edit records what it changed (`was` → `value`), who, when,
  and the version of the puzzle it was made against.
- **Rebasing:** when an upstream stage improves after review, edits are replayed
  onto the new reading. An edit whose `was` no longer matches is flagged, not
  applied silently. Sign-offs lapse when the puzzle changes (as now).
- What's on the review site is exactly the version in git (fingerprints, as
  since 2026-10-13).

## Exceptions and queues

Every unit has a state: its stage, and `ok`, `waiting` or `exception` with a
reason and notes. Any stage, tool or person can raise one and send the unit back
to an earlier stage ("the clue list goes on to leaf 41: re-run layout with it").
A queue is a query over these states, and a review tool is a page over a queue:

- layout and assembly: the issue viewer (`xword-ocr viewer`), with click and
  draw hints;
- key letters: the key-squares page;
- proofs: the review site.

This replaces the checkpoint report, readiness guessing and most of
`puzzles.tsv`'s hand-kept columns.

### The board

A kanban board for the maintainer (a requirement), drawn from those states:

- **Columns are stages** (source, OCR, layout, extraction, assembly, validation,
  AI review, human review, packaged, exported); **cards are units**: issues
  until assembly, puzzles after. Filter by publication, batch, or "mine".
- **Exceptions stand out:** a card in `exception` or `waiting` is marked in its
  column with its reason ("key with no puzzle", "clue list continues on leaf
  41", "Not ready: 2 squares"), and a filter shows only those.
- **One click to the right review tool:** a layout or assembly card opens the
  issue viewer at that page; a key card the key-squares page; a review card the
  proof page; anything else the packet. Resolving it there moves the card.
- It reads the same states as everything else, so it can't disagree with them:
  served locally from the session's SQLite, and from the repo's states for a
  read-only view on the site.

## Contributions

| Phase | Contribution | Needs | Does not need |
|---|---|---|---|
| 1: find and assemble | where puzzles are (sources) | knowledge | anything installed |
| | scans (archive.org, a private stash, hand clips) | access to the source | a GPU, a model |
| | compute: run stages 1 to 6 for claimed issues | a decent machine, the tools | access, a model budget |
| | completeness: check assembled issues in the viewer | time, a browser | a GPU, a model |
| 2: review | model credits: run AI review on claimed puzzles | a Claude subscription, a checkout | scans, a GPU |
| | human review | a browser (the review site) | git, tools, a model |

Each stops where it likes and contributes what it did: a compute run commits the
issues it finished. Phase 2 needs nothing from phase 1 but the packets (with
their crops). The inbox for hand-clipped pages (newspapers.com, papers' own
archives) is deferred until we start on those.

## Publications and techniques

- A sophisticated contributor (likely with Claude) can **start a publication**:
  a starter command makes its repo, a hints file and empty state; they add
  hints and run the stages on a few issues to see how it goes.
- Everything specific to a publication is in its **hints**: where to look, which
  techniques to use, its quirks (`[ocr] sure_swaps`, `[ocr] heading_blocks`).
- New machinery is a **technique** with a name and a switch, documented with
  what it's for and which publications use it, so the next publication can try
  it and compare (goal 1 makes that cheap).

## Legible to Claude

Claude should drive the tools, not read the page:

- every stage has a short "show me" command: a compact text summary of one unit
  and its doubts, not a dump;
- packets are text first (as `text.md` is now): the model looks at an image
  only where a tool flags doubt, and gets a crop, not the page;
- every tool's output says what to do next;
- tokens are measured per puzzle and per stage, against the 10% goal.

## Migration (keeps the code)

0. Merge the 2026-10-13 branches (done or in progress).
1. **Page artifacts:** OCR, layout and extraction outputs as fingerprinted JSON
   in the scans store, written by the current code. Retire the pickles. Build
   the evaluation set and a run-diff command.
2. **Session SQLite:** hydrate from git and the artifacts; write back. Stage
   commands run on a subset and skip what's current.
3. **Assembly as a stage per issue:** mint ids, write packets; add the alias
   table (repo and Supabase).
4. **Exception states and queues** replace the checkpoint report; the viewer
   reads and writes them; **the board** shows them.
5. **Incremental downstream:** validation, packaging and site publishing touch
   only puzzles whose inputs changed.
6. **GAMES 1977–79 end to end** on the new path. Judge stays on the current path
   until the new one reproduces its xd files byte for byte.

## Decisions (were open questions)

Settled 2026-10-14.

- **Ids for newspapers with several editions or sections a day:** `<issue>` is
  whatever key the source stage gives the unit, not necessarily a date. A
  newspaper's Sunday magazine is `bg-1925-03-01-mag`, its daily page
  `bg-1925-03-01`; the format doesn't change.
- **Artifact store:** R2, content-addressed (`<pub>/<stage>/<sha256>.json`),
  with a local cache in front of it. We already run R2 for the review site;
  release assets have count limits and no addressing by hash.
- **Stage versions:** a constant in each stage module, bumped by hand when its
  behaviour changes. A version derived from the code would change on every
  harmless refactor and force re-runs. The evaluation set catches a bump that
  was missed.
- **AI review and the review site on the same puzzle:** AI review sets the
  puzzle's state to `in-review` (with who and since when) when it claims it;
  the site shows that and holds off saving edits until it clears. Claims
  expire after a day.
- **Tokens per puzzle:** each AI review records its usage (model, input,
  output and cache tokens) in its packet entry; a `tokens` report sums them per
  stage and per puzzle against the 10% goal.

## Notes for the build

- Today grids are found from pixels first and a page is OCR'd only if it has a
  grid. OCR before layout means OCR on every page; measure the cost on a sample
  (GAMES 1977) before running a whole publication.
- The evaluation set is built with the page artifacts (step 1), so every later
  step can show it didn't make things worse.
- The first test run is a year or two of GAMES, 1977–78 first.
