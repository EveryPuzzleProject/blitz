# v3: agents drive the import, people review backwards

Draft, 2026-11-25, for review. Nothing here is built. It comes from a conversation with the
owner that day and replaces no earlier document: `restructure.md` (the v3 section),
`pipeline.md`, `ship.md` and `operating-model.md` still describe what exists. Where this
disagrees with them, this is the newer intent, and "Decisions and open questions" at the end
lists what the owner has and has not settled.

## Why

Holding imports on a person's review does not scale. As of the last reports:

- Collegian: 69 shipped of 797; 310 broken in the pipeline, 263 not checked, 155 on a question.
- GAMES 1980-82: 58 ready for review of 125 after a hands-off run; 62 need work; never published.
- GAMES 1977-79: 35 shipped of 76 after fifteen runs.

The proof pages waiting for a person are not the main queue. The main queue is puzzles the
pipeline could not finish and that no agent has an action to repair, plus a rule that sends
every doubt to the owner.

What works and stays: the tools that download and harvest scans, the document analysis and
OCR, the proof page (the OCR's crop beside its text), the record of every edit, and the small
tools where a person's glance is worth a lot (finding grids on a contact sheet, drawing a box).

## The idea

1. **Agents push forward to a result.** A lead session is pointed at a publication or a body of
   images. Annotated xd files come out, each with the provenance needed to check any reading or
   editorial decision. No step waits for a person.
2. **People walk backwards.** The owner looks at a batch in bulk, or at the puzzles once they
   are in gxd and on crossref, where a wrong word or a clue that doesn't fit stands out. From
   any doubt there is a link back through the evidence: the proof page at the row, then the
   stage views behind it.
3. **Agents work from the pipeline's outputs.** Text first, then crops of what is flagged. An
   agent does not read a page image to produce a puzzle.
4. **People can still step in where it pays.** The contact sheet, the box tool and the proof
   page stay, as optional help, never as a gate.

The crowd-review model (a queue of proof pages for volunteers) stops being the way puzzles
ship. The review site stays as the place evidence is read and corrections are made.

## The components, and the line between them

| Component | Owns | Never has |
|---|---|---|
| **fetch** (its own repo, last to move) | source adapters (archive.org, a folder of images, IIIF archives), the inventory of scans, scan choice, page download. Out: a page folder. | OCR, puzzles |
| **xword-ocr**, the library | image in, puzzle data out: page OCR, grids, regions, parts, key finding and reading, assembly's linking. Deterministic. Out: a reading packet per puzzle and a census per issue. | a model call, a ledger, a batch, a web page |
| **blitz**, the orchestrator | the batch and the run, milestones and their invalidation, every model step (text step, review, second opinion, repair, last-resort read), triage, the ship rule, the edition, publishing, the views | how OCR works |
| **`<pub>`, `<pub>-scans`** | the publication's record and its evidence (unchanged from `restructure.md`) | code |

The test for a module: if it calls a model, reads or writes the ledger, knows what a batch is,
or serves a page, it is blitz's. If it turns pixels or OCR boxes into puzzle data, it is
xword-ocr's.

**Where the code is today.** xword-ocr is about 31,000 lines and blitz about 8,300. By module,
roughly: 10k is the image library, 4.5k harvest and sources, 9k orchestration after the reading
(text step, triage, ship check, proof packets, proof review, remedy, restart, batch page), 5k
views. blitz does not import xword-ocr: it shells out to it in one place (`sync.py`) and
otherwise reads packet folders, so the boundary already exists as files.

**The hard part.** `harvest.py` (2,900 lines) does both fetching and linking, thirteen modules
import it, views call its private functions, and proof packets get their assembled puzzle
through a method on the watch server (`watch.Watch._assemble`). That knot moves last.

**No packet is reset by a move.** A packet is identified by its xd's fingerprint, not by the
code that made it. Moving a module changes no bytes; a published packet is never rebuilt
because code moved. Each move is checked by rebuilding a fixed set of real packets byte for
byte.

## Units

| Phase | Unit | Why |
|---|---|---|
| Reading: page OCR, regions, parts | page | read once and cached; a page never needs its neighbours |
| Assembling and accounting | issue | clues and keys cross pages, sometimes into the next issue |
| Everything after: text step, review, repair, ship | puzzle | |

## The handoffs, written down

Each handoff gets one document in blitz `formats/`, a version field in the file it describes,
and a validator (`blitz check-format <path>`). Today's shapes become version 1 as they are.

| Handoff | From, to | Today |
|---|---|---|
| Page folder: `pages.tsv` and images | fetch to xword-ocr | documented (xword-ocr `docs/sources.md`) |
| Issue census: every grid, key and clue list with its fate | xword-ocr to blitz | documented (xword-ocr `docs/census.md`) |
| Reading packet: `ocr.json`, crops, boxes, page images | xword-ocr to blitz | two module docstrings, one in each repo; no version |
| Triage record, decisions ledger, ship record | inside blitz | prose in `ship.md` and xword-ocr `docs/ship-gate.md` |
| Annotated xd and its provenance row | blitz to any reader | spread over `ship.md` and `hand-read.md`; the `^Printed` / `^Fits` proposal is on an xdformat branch |
| Edition and `shipped.tsv` | blitz to any reader | `ship.md`, "The edition" |

The annotated xd is the one that most needs writing: which sections and headers a transcription
may carry (`## Printed`, `^Printed:`, `^Fits:`, `Typed by hand:`, `Answer key corrected:`, the
Design and Numbering sections), which of them reach the edition, and what the provenance row
says for each value that was not simply read.

## A run

One lead session per batch. It holds a brief: the publication, the scope rule, a token budget
and a time budget. It runs compute itself and hands model steps to worker agents.

| # | Step | Unit | Model | Exists |
|---|---|---|---|---|
| 1 | Fetch and read pages | page | none | yes |
| 2 | Assemble; write the census | issue | none | yes, but not recorded for reuse |
| 3 | Classify each grid's kind; defer what is out of scope | puzzle | small | partly (the text step drops non-crosswords) |
| 4 | Text step | puzzle | yes | yes |
| 5 | Triage and the ship check | puzzle | none | yes |
| 6 | Review of flagged items, from crops | puzzle | yes | yes (`proofreview`) |
| 7 | Second opinion where the first said Not ready | puzzle | yes | no |
| 8 | Repair: a stage action, then back to the step it invalidates | puzzle | yes | partly (`remedy`: grow a box, re-read parts, request a page) |
| 9 | Last resort: an agent reads the part no stage delivered | part | yes | no (done by hand for the World, Nos. 1-33) |
| 10 | Grade, ship, make and publish the edition, publish the review pages, write the batch report | puzzle | none | ship and edition yes; grade and report no |

Steps 6 to 9 loop at most a fixed number of rounds per puzzle. A puzzle that is still not
whole after them exits with what it has.

## Every puzzle exits with a grade

Today a puzzle either ships or waits for a person. In v3 every puzzle leaves the run, and its
grade says how far to trust it. The grade is in the provenance row and the ship record, and on
the proof page and the batch page.

| Grade | Means | Ships |
|---|---|---|
| `clean` | the ship check passed; nothing was flagged | yes |
| `reviewed` | flags were raised and an AI review settled each from its crop | yes |
| `doubts` | one or more flags stayed open after the second opinion; each is listed with its row and crop | yes |
| `incomplete` | a part was never found (a key, a clue, a clue list); the gaps are named | yes, as it stands |
| `held` | the structure does not hold (the clues don't fit the grid, no grid); a diagnosis names the stage | no |
| `deferred` | its kind is out of scope for now | no: a stub |
| `not-a-crossword` | | no |

Nothing in the ship rule that protects a person's word changes: a person's Not ready still
holds a puzzle, the owner's decision overrides, an AI never overrides a person, and every edit
still needs its record.

## The second opinion

An AI reviewer's Not ready goes to a second reviewer that has not seen the first's answer, on
the same crops, and on a different model.

- Both say the same fix: it is applied, with both named in the record.
- They disagree, or both are unsure: the flag stays open, and the puzzle's grade is `doubts`.
- Neither result is a question for the owner.

## Repair actions

On GAMES 1980-82 the remedy agent fixed none of 68 puzzles outright, because most failures
were assembly linking a part to the wrong puzzle and it has no action for that. Each action
below is a decision in the ledger that its stage obeys on the next run, the same decision a
person's click in a stage view would write.

| Action | Stage that obeys it | Exists |
|---|---|---|
| Grow or redraw a box | regions, parts | yes (grow) |
| Re-read a part | parts | yes |
| Request a page | fetch | yes, with a bug (the request is not seen as open) |
| Link this part to that puzzle; unlink it | assembly | no |
| This key belongs to that puzzle | assembly | no |
| Look for a grid on this page, of this size or block pattern | regions | no |
| This grid is this kind | census, scope | partly (drop, set aside) |

## The last resort: an agent reads a crop

When no stage delivers a part and no repair brings it, an agent may read it from the scan.
This relaxes "never transcribe from the scan" in a bounded way, and CLAUDE.md changes only
when this slice lands.

- Only the missing part: a clue column, a key, a heading. Never a whole page.
- Read twice, blind, by separate agents; the two readings are compared and differences are
  listed as doubts.
- Every such value is marked "read by agent" on the proof page, in the xd and in provenance,
  as `Typed by hand:` is today, and it is a reason code in triage.
- It is the last step, after repair, so it never hides a stage that should be fixed. The batch
  report counts how many parts needed it, per kind of failure: that count is the pipeline's
  to-do list.

## Accounting per issue

The census (xword-ocr `docs/census.md`) already gives every grid, answer key and clue list on
an issue one fate. v3 makes it the issue's closing statement.

- **A line per issue in the batch report**: grids, keys and clue lists found; puzzles made;
  orphan keys, loose lists and unclaimed grids left over.
- **Leftovers become repair work.** An orphan key means a grid was missed: a repair agent gets
  the key's size and block pattern and the issue's pages to search.
- **An independent count where the issue prints one.** A contents page or an answer section
  names the issue's puzzles. Reading it gives a number to check the census against.
- **Leftovers never block the issue.** It ships with "2 pieces unaccounted for" shown on its
  status page, and the pieces stay listed with their crops.

## Scope: kinds that are not a priority

Cryptics and crossword-like puzzles should cost almost nothing and still not be lost.

- **Every grid gets a kind at the census**: crossword, cryptic, variety, not a puzzle.
- **The publication states its scope once**, in its repo: for example `crossword: import`,
  `cryptic: defer`, `variety: defer`.
- **A deferred puzzle gets a stub and nothing else**: id, issue, page, kind, thumbnail. No
  model step runs on it after classification. It never counts as broken, and its parts are
  freed for the crosswords beside it (as a dropped grid's are today).
- **Stubs are listed as "known, not transcribed"** on the status page. A later batch picks
  them up by kind.

Today's per-puzzle set-aside (`setaside:<pid>`) stays, for the single case no rule covers.

## Wall clock

An agent has no sense of time, and today the shortest path to fixing one puzzle is often to
re-run the batch. On GAMES 1980-82 assembly ran three times over the same inputs in one
evening, each remedy restart re-assembled its whole issue, and the batch snapshot took 38
minutes fetching 1,031 files one at a time.

- **Assembly's output is recorded per issue and reused** by every later step. This is the
  largest single saving.
- **Every command takes ids.** The form that runs over a whole batch is an explicit flag.
- **Every milestone records how long each unit took.** A command that would re-run many units
  says first how many and about how long ("412 puzzles, about 3 hours").
- **The patch is the shortest command**: fix this puzzle from this stage, and only its chain
  re-runs.
- **A time budget in every brief**, beside the token budget. Past it, the agent records why,
  or runs the step in the background and carries on with other work.
- **The run log is automatic**: wall clock and tokens by step, as `games-8082-results.md`
  kept by hand.

## How a person works

- **The batch digest**: one page per run, puzzles sorted by grade with a thumbnail each, the
  issue accounting, the kinds of failure ranked by puzzles, and what the run cost. It is the
  owner's bulk look and the public record of the run.
- **From downstream back to the evidence**: a puzzle's page on crossref or the EPP site links
  to its proof page; a flag there (`flag-a-mistake.md`) reopens the puzzle at that row.
- **A correction is a decision**, recorded as now. Where it names a stage, the run picks it up
  and re-runs that puzzle's chain.
- **Budgets replace go-aheads.** The lead has a token ceiling for the batch and does not stop
  to ask inside it.
- **The lead publishes without asking**: review pages and editions (the owner, 2026-11-25).
  This replaces `operating-model.md`'s owner-only publishing for now. Nothing reads the
  editions yet, not even gxd; the owner expects to bring back a person's sign-off once
  something does.

### Batch review of every step

Any step that decides something can be scanned in bulk, with its evidence, after the fact.
These are checks the owner can make at any time, never gates the run waits at.

| Step | What is scanned | Evidence on each card |
|---|---|---|
| Kind and scope (3) | every grid deferred, dropped or called not a crossword, grouped by kind | the grid's crop and its page, the kind, who or what decided |
| Census (2) | every grid turned down, orphan key and loose clue list | the crop, its fate, the issue's line |
| Assembly (2) | every puzzle as assembled: grid, lists and key side by side | thumbnails of each part with the page it came from |
| Reading (4 to 9) | grids in bulk, or clue sheets in bulk | the crop beside what was read |
| Ship (10) | every xd that shipped, stepped through in order, sorted by grade | the xd beside its proof: grade, open doubts, edits |

- One view pattern for all of them: a sheet of cards, keys for next and previous, one key to
  disagree. Collegian's contact and confirm sheets are the model (`collegian-lessons.md`,
  "View patterns worth keeping").
- A disagreement is a decision in the ledger. The run picks it up and re-runs that puzzle's
  chain, as for any correction.
- Each view reads what its milestone recorded, so each step has to record its decisions with
  the crop they were made from. A step that cannot be scanned is not finished.
- These sheets are also where volunteers could help later, and assembly may turn out to be
  the step that needs people most.

### Backwards from a mistake, in the open

Anyone can walk the chain, with no account: a puzzle on crossref, its EPP record page, the
proof page, the assembly view, the page and its regions, the scan. As much of this as rights
allow is public. In practice it will mostly be the owner.

## What does not change

- The ship rule's protections, the three-case edit rule, the transcription and the edition.
- Views never compute; a milestone is run once and re-run only when invalidated.
- The reviewer rules for helpers, guests and the owner in `ship.md` stay as built. They are
  not extended.

## Slices, in order

Each leaves everything working and is merged before the next starts.

1. **Formats.** `formats/` for the six handoffs, version fields, the validator, and a fixed set
   of real packets as the byte-for-byte test. No code moves.
2. **Assembly recorded per issue**, with the census, reused downstream; per-unit timings and
   the estimate before a long run; per-puzzle invalidation.
3. **blitz owns the batch and the run.** A `blitz batch` that calls xword-ocr at stage
   boundaries. The modules that only read packets move: ship check, triage, proof review,
   batch page, import. Then the text step and proof packets.
4. **Grades and the batch digest**; the scope rule and stubs.
5. **The second opinion.**
6. **Repair actions for assembly** (link, unlink, key-of, look for a grid).
7. **The last-resort read.**
8. **Views into the viewer** with no stage code (`restructure.md`); **fetch into its own
   repo**.

Slices 4 and 5 need no code move and could run before 3 if the first run should come sooner.

## The first run, and its measure

GAMES 1980-82: 125 puzzles, a measured baseline (62 need work, $0.39 a puzzle, 3 human
touches) and nothing published. The measure is how many puzzles exit at each grade with no
person involved, what it cost in tokens and hours, and, from a sample the owner reads, how
many shipped puzzles have an error the grade did not warn of.

## Decisions and open questions

Agreed in outline by the owner, 2026-11-25: agents drive and people review backwards; a puzzle
with open doubts ships with them noted; a second AI opinion in place of "for you"; repair
actions; a marked last-resort agent read; budgets in place of go-ahead stops; xword-ocr slims
to image tools and blitz orchestrates; the formats are written down; the puzzle is the unit
after assembly; incremental work by default; fetch may be its own repo; issue accounting that
does not block; out-of-scope kinds deferred, not dropped.

Answered the same day:

- **Incomplete puzzles ship with the `incomplete` grade**, with no person's Ready. The rule of
  2026-11-23 (`ship.md`: a person's "Ready to ship as it stands") no longer stands for v3
  runs.
- **Every step's decisions can be reviewed in bulk** ("Batch review of every step").
- **The lead publishes review pages and editions without asking**, for now.
- **The second opinion comes from a different model than the first reviewer's**: they make
  different mistakes, so their agreement means more.
- **After the first run the owner reads 10 shipped puzzles from each grade** (clean, reviewed,
  doubts), a random sample the ship step-through marks, to learn whether the grades can be
  trusted.
- **Volunteers are out of scope.** The site is open and anyone can walk backwards from a
  mistake; the batch sheets may become volunteer work later.

Open:

1. **Where the grade and the open doubts are written.** Not settled and not urgent: it can
   change later. The owner leans towards a short final grade or summary in the xd file, with
   the detail in provenance.
