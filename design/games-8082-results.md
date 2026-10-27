# GAMES 1980–82: results of the hands-off v2 run

The run planned in [games-8082-plan.md](games-8082-plan.md), written as it goes (started
2026-10-21). One orchestration session (Claude Opus 5.5), no code changes beyond the run
registry. Branch `claude/games-8082-run` in xword-ocr, blitz and games.

## Setup

- **Run registry:** a file per batch. `games/pipeline/triage/runs-games-8082.json` holds
  1980–82's runs; `runs.json` stays GAMES 1977–79's. `batchpage.run_notes(repo, out_dir)` picks
  the batch's file by its harvest folder (`runs-<harvest>.json`), else `runs.json`
  (xword-ocr, with a test). The current run is `run1-handsoff`.
- **Fable meter at the start:** weekly Fable 0%, weekly all models 22% (2026-10-21 19:20 EDT).

## Wall clock, by step

| step | start | took | notes |
|---|---|---|---|
| setup (read the brief, worktrees, registry) | 18:58 | ~20 min | |
| key letters re-read (`reread-letters`) | 19:04 | 18 min | compute only: 377 answer grids re-read; the relink after it: 84 puzzles, 71 with a matched key; 40 page records rewritten in games `pipeline/` |
| re-assembly, hands off, and the open requests (`requests`, listing only) | 19:22 | 12 min | compute only, from the stored OCR; 9 requests in the ledger, none open for 1980–82, so the request loop had nothing to fetch |
| text-step packets (`text_trial.py run1-handsoff --all`) | 19:36 | 7 min | assembles every issue again; 125 puzzles in 13 batches of 10 (the box review had 106; 2026-10-15's hands-off assembly found 124) |
| waiting for the go-ahead on the text step | 19:44 | 58 min | **ask**: 125 puzzles, about 0.98M Fable tokens, about 9% of the weekly Fable limit. The maintainer did a sanity pass on the watch's Assembled tab first (human touch 1), then said go |
| text step, batch 1 of 13 (`xword-text`, model set to Fable) | 20:43 | 4 min | 10 puzzles: 436 input, 92.8k cache writes, 1.15M cache reads, 20.2k output; $2.46 at API rates. Weekly Fable meter 0% → 2% |
| text step, batches 2–13 (12 agents at once) | 20:48 | 7 min | all 125 answered |
| proof packets (`proof-packets`) | 20:57 | 2 min | compute only |
| triage (`triage --gxd-db --record-drops`) | 20:59 | 31 s | 68 Needs work, 52 Ready for review, 5 dropped as not a crossword (recorded by triage) |
| batch page | 21:00 | 5 min | stalled: the watch started from the worktree couldn't find triage's folders (relative to the main checkout); restarted from the main checkout |
| remedy case file (`remedy cases`) | 21:00 | 9 min | assembles every issue again; 68 cases, 200 KB |
| remedy agent, 1980 (12 puzzles, Sonnet) | 21:10 | 6 min | 0 fixed, 1 waiting (a request for 1980-03 leaf 52), 11 for you; 3 looks (+1 viewed); 1 grow (1980-05 L046, still not ready) |
| remedy agent, 1981 (21 puzzles, Sonnet) | 21:17 | 4 min | brief adds the cryptic-key kind from 1980. 0 fixed, 21 for you (each flagged; 10 cryptics also a key gap); 2 looks; 1 unneeded request (1981-01 L048, leaf 47 already harvested; noted on its flag) |
| remedy agent, 1982 (35 puzzles, Sonnet) | 21:22 | 76 min | brief adds the kinds from 1980–81: cryptic headings, fold pages, not-a-crossword. 7 restarted from parts (lists inside the person's box but misread: the second Across column, the strip under the grid, a quiz taken instead) now wait for the text step; 28 for you; 5 looks. Slow: each restart re-assembles its issue |
| request loop for the remedy's page request (1980-03 leaf 52) | 22:37 | 13 min | **stalled**: "11 requests, 0 open", nothing fetched; the request isn't counted as open for this harvest, so 1980-03 L054 still waits. 13 minutes of re-assembly for nothing |
| waiting for the go-ahead on the text step for 8 restarted puzzles | 22:51 | 3 min | **ask**: about 100k Fable tokens, about 1% of the weekly limit. Go-ahead (human touch 3) |
| text step on the 8 restarted (Fable) | 22:55 | 3 min | 432 input, 67k cache writes, 751k cache reads, 14k output; $1.73 |
| proof packets (8) and triage again | 22:58 | 1 min | **62 Needs work, 58 Ready for review, 5 not a crossword** |
| the maintainer's pass on the batch page | 23:00 | | decided with the maintainer: no assembly review (the failures are kinds for v3); only kind decisions (Not a crossword) |
| publish dry run: proofs (`site-publish --dry-run`, the 62 Needs work skipped) | next day | <1 min | would publish 63: 58 ready + 5 drops |
| publish dry run: batch snapshot (`site-publish-batch --dry-run`) | next day | 38 min | 131 cards (125 + 1977–79's 6 drops), 1,031 files; slow: every thumbnail and page fetched through the live watch |

## Cost per puzzle, by role

(filled in from the transcripts at the end)

Prices (first-party API, per million tokens): Fable 5.1 $10 input, $12.50 cache write,
$0.25 cache read, $50 output; Opus 5.5 $4, $5, $0.20, $20.

**The text step's estimate was low.** The plan's 7.8k tokens a puzzle (1977–79) counted
output and cache writes. Batch 1 ran about 11.3k a puzzle on that measure (113k for 10, plus
115k cache reads a puzzle), and moved the weekly Fable meter 2 points for 10 puzzles, where
1977–79 took 6 for 81. The meter rounds, so it's a rough guide: 125 puzzles project to about
13–25% of the weekly Fable limit rather than 9%.

**The whole text step** (13 `xword-text` agents on Fable 5.1, 125 puzzles, 11 minutes wall clock
run 12 at once): 8.4k input, 1.18M cache writes, 16.9M cache reads, 323k output; **$35.27** at
API rates, **$0.28 a puzzle**, 12.1k tokens a puzzle (input + cache writes + output). The weekly
Fable meter went 0% → 13%; the 5-hour limit (all models) reached 76%.

| role | input | cache writes | cache reads | output | API $ | per puzzle |
|---|---|---|---|---|---|---|
| text step (Fable 5.1) | 8,366 | 1,184,513 | 16,883,841 | 323,235 | 35.27 | 0.28 |
| text step again, 8 restarted (Fable 5.1) | 432 | 67,016 | 750,882 | 14,051 | 1.73 | 0.01 |
| remedy agent (Sonnet 5.5, 3 passes, 68 puzzles), scan looks included | 158 | 1,060,464 | 7,203,227 | 2,586 | 4.12 | 0.03 |
| orchestration (this session, Opus 5.5, to 22:37) | 306 | 535,321 | 26,797,891 | 63,220 | 9.30 | 0.07 |
| **total so far** | | | | | **48.69** | **0.39** |

Scan looks are inside the remedy agent's numbers: 10 looks (3 + 2 + 5) for 68 puzzles, about
8% of the batch. The orchestration figure includes reading the text step's 13 reports and the
remedy reports; the 1982 remedy pass's cache writes (870k) are most of the remedy cost, from 49
tool calls over 35 puzzles.

## Hands-off quality

(against the maintainer's 1980–82 box review in the games ledger)

**After triage** (run1-handsoff, 125 puzzles): **68 Needs work, 52 Ready for review, 5 not a
crossword** (dropped by triage on the text step's word: 1980-03 L028, 1980-05 L024, 1980-11
L105, 1982-05 L048, 1982-12 L039). 1977–79 reached 10 Needs work of 76 only after fifteen runs;
this is the first pass on untuned puzzles.

What holds the 68 back (puzzles per blocking reason; a puzzle can have several):

| reason | puzzles | restart from |
|---|---|---|
| `header-typed` (the text step typed a title or byline no stage read) | 42 | assembly |
| `verdict-missing` (the verdict says a part is missing) | 26 | assembly |
| `request-page` (a page never fetched: mostly cryptic keys in the Answer Drawer) | 25 | harvest |
| `clues-unread` | 19 | parts |
| `key-missing` | 17 | key matching |
| `request-list` (a clue list belongs to another puzzle) | 17 | parts |
| `verdict-wrong-text` | 6 | assembly |
| `key-unread` | 4 | key reading |
| `list-missing-D` | 3 | parts |

Triage did catch the typed headers: no value the model wrote reaches review unmarked. Not every
non-crossword was dropped: the Answer Drawer coupon and page (1981-03 L075, 1982-11 L114), the
contest example grid (1981-11 L033), Phone Numbers and Cross-Fact, and Cross Sets reach Needs
work instead.

**After the remedy agent** (68 Needs work): **0 fixed outright, 7 restarted and waiting for the
text step, 1 waiting for a page request, 60 for the maintainer** with a diagnosis each (the
batch page's "For you": 61, counting one restarted puzzle with a separate key flag). In 1977–79
the remedy agent fixed 9 of 22; there most failures were parts the proof page could settle, here
most are assembly's linking, which no remedy action reaches (see the v3 list).

**After the restarted puzzles' text step** (8 puzzles, then proof packets and triage again):
**62 Needs work, 58 Ready for review, 5 not a crossword.** The remedy's restarts brought 6
puzzles to ready; 1982-03 L036 (key in the next issue) and 1982-09 L045 (an ad's Down list
never read) still need work.

gxd cross-check: 4,370 of 9,125 clue/answer pairs seen in gxd (48%); 16 key near misses, 25
blank mismatches.

## Human touches

1. **Go-ahead for the text step**, after a sanity pass over the assembled puzzles on the watch's
   Assembled tab (hands off). Planned stop; the pass was the maintainer's choice, prompted by
   having no packet view to check before spending Fable.

2. **A proof-page readability fix, slipped in** (the maintainer's request, outside the
   no-code rule): the blue outlines around reviewer-changed key squares can be hidden, like
   the orange low-confidence ones, because they hide the scan when the grid sits a little off
   it. Done in its own session, blitz branch `claude/proof-corrected-toggle` (394c2a9), not
   part of this run's code. PR EveryPuzzleProject/blitz#46.
3. **Go-ahead for the text step on the 8 restarted puzzles** (planned stop for Fable).

## Orchestration decisions

- **The remedy agent ran a year at a time, one after another**, not in parallel: a restart
  rewrites the harvest's shared state, and two at once could overwrite each other.
- **Cryptic keys as a kind, not per puzzle.** The 1980 pass looked at two Answer Drawer pages
  (1980-03 leaf 80, 1980-09 leaf 76): a cryptic's answers are printed as explanations in text,
  with no grid. It then recorded the same `gap` for two other issues' cryptics without looking.
  For 1981 and 1982 the brief states the kind (from those two looks) and allows the gap for
  cryptics only, so the looks go to other failures. Triage's `cryptic-no-key` already treats
  this as a gap; the text step's request for the key page is what blocks.

## Stalls

## New failure kinds (for the v3 list)

From the text step's reports (125 puzzles). Each is a kind, with examples:

- **Assembly takes a neighbouring block as a clue list.** A quiz or word list printed beside
  the grid becomes the crossword's Across or Down list (1982-07 L032, L036; 1982-05 L034,
  L036; 1982-09 L045; 1982-10 L030; 1982-12 L066; 1982-05 L048). Common in 1982's denser
  layouts.
- **Cryptic pages: the main cryptic's heading goes to the warm-up.** On every page that prints
  a 5x5 or 7x7 warm-up beside the 15x15 cryptic, the "Cryptic Crossword / by ..." lines link to
  the warm-up, and the 15x15 has none (1980-03, 1980-05, 1980-11, 1981-01, 1981-03, 1981-05,
  1981-07, 1981-11, 1982-01, 1982-09, 1982-11). The warm-up's own two-line title ("Warm-Up
  Puzzle / for New Solvers") is never read whole.
- **Cryptic keys are never asked for.** Assembly doesn't expect a grid key for a cryptic, so it
  raises no request for the Answer Drawer page; every cryptic and warm-up reached the text
  step with no key. This is why the request loop found nothing to fetch.
- **The text step writes values no stage read.** Titles and bylines given as "values" when the
  line was cut or linked elsewhere (about 20 puzzles, flagged unsure), a cross-reference clue
  worded by the model (1982-03 L036 A37), and **solved answers for unkeyed cryptic warm-ups**
  as findings (1980-05 L042, 1980-07 L048, 1980-09 L046, 1981-01 L044, 1981-03 L050). That's
  transcription, or solving, by another name; triage and the proof page have to show these as
  the model's, and the instructions should forbid solving.
- **Non-crosswords read as grids:** Answer Drawer pages and ads (1980-11 L105 chess board,
  1981-03 L075 coupon, 1982-11 L114), word-path and Latin-square puzzles (1980-05 L024, 1982-05
  L048), a contest's example grid (1981-11 L033, also linked as 1981-09 L048's key), a number
  grid (1982-11 L044 Phone Numbers, 1982-01 L032 Cross-Fact), a Link Acrostic (1982-12 L039).
- **The key reader has no digits or symbols.** Digit-theme keys (1981-09 L046 Double Play: 27
  squares), rebus squares ($ in 1981-07 L026, POINT in 1980-07 L046).
- **Unnumbered theme entries** shift every later clue number (1981-03 L034, 1981-11 L058).
- **Two-player puzzles:** Matchwit prints an "A" and a "B" list for one grid (1982-09 L064).
- **Clue lines read as page lines.** Clues printed under the grid, or at a column's foot, come
  through as L-lines and their slots go empty; the text step put many back by number (every
  Ornery, and 1980-05 L028, 1982-01 L038, 1982-09 L050).
- **Spell-check rewrote a correct word** (1981-03 L048, "taction").
- **The batch page mixes batches.** Its "Not a crossword" group counts every drop in the
  publication's ledger, so 1980–82's page shows 131 puzzles: 125 plus 1977–79's 6 drops. And
  until the run registry is on the games checkout's main, it says "Not the current run
  (run15-restart)". v3: one batch's records per page, the registry owned by the orchestrator.
- **The remedy agent can't fix linking.** Its tools restart a stage for one puzzle (grow a box,
  re-read parts, request a page). Most 1980–82 failures are assembly linking a read part to the
  wrong puzzle (the cryptic heading to the warm-up, a fold page's heading and Hard clues not
  joined to the 25x25, a neighbouring quiz as a clue list), so the agent can only flag them. A
  remedy needs a "relink this part to that puzzle" action, recorded as a decision assembly obeys.
- **A remedy's page request isn't seen as open.** The remedy agent requested 1980-03 leaf 52
  (`grow` refused it as unharvested), but `requests --run` counted 0 open and fetched nothing.
  The request and the harvest disagree on whether the page is in the harvest.
- **A key gap doesn't clear the text step's key request.** After `gap --part key` on a cryptic,
  triage still blocks on the text step's `request-page` for the Answer Drawer (1981: cleared on
  1 of 10).
- **The maintainer couldn't tell whether the Assembled tab is the run.** It assembles live
  (hands off or with the boxes, by a link at the top), while the run's proof packets keep
  assembly's record from when they were built. They agreed where checked (1980-01: the same 4
  keys), but nothing on the page says so. v3: the view draws the run's assembly record, with
  its fingerprint, and says when the live reading differs. Example: 1980-01 "Definitions?"
  showed no title on the Assembled tab in its boxes mode (the 2026-10-15 box review's
  boxes), while the run's hands-off assembly has the title, byline and the key from the other
  uploader's scan (leaf 63). The two modes look alike and nothing says which one the run used.
- **A key taken from the other scan shows twice wrong.** The puzzle's card doesn't draw the key's
  page (it draws only the grid's scan), and the chosen scan's own partial reading of the same
  key stays under "Keys with no puzzle" as pieces (1980-01 "Definitions?": its 21x21 key read on
  games-15-1980-january leaf 63 as 14x21, 7x15 and 7x21 fragments, the 14x21 listed as a
  key-like orphan). An orphan whose page gave another puzzle its key from the other scan should
  say so and leave the orphan list.
- **Not a crossword is per grid, but the card shows several leaves.** A card's id names one
  grid, and the drop applies to it alone; the other leaves are pages it took parts from. The
  maintainer couldn't tell from the card what a click would take out. The card should say
  "this grid (leaf N)" on the button, and mark the borrowed pages as borrowed.
- **The batch snapshot takes 38 minutes** (1,031 files fetched one by one from the live watch,
  thumbnails rendered on demand), and it includes another batch's drops.
- **Relative paths in milestone records.** triage.json names its text-step and proof folders
  relative to the checkout the command ran in, so a viewer started elsewhere (a worktree)
  fails with a TypeError instead of "not recorded".
- **Sheets too downscaled to read** for 25x25 puzzles (1980-05 L046's sheet-2 is 10,210 px
  tall, mostly repeats of one crop).

- **The key re-read is slow and silent.** `reread-letters` over 481 answer grids prints nothing
  until it ends (well over 10 minutes). A long compute-only step should report progress, and,
  as a milestone, re-read only the grids whose reader version changed.
- **Assembly runs three times over the same inputs.** The relink after the key re-read, then
  `requests` (12 min), then the packet build each assemble every issue again from the same
  stored OCR. Assembly needs a recorded output that later steps reuse.
- **No request raised for 1980–82.** Hands-off assembly asked for no pages (keys on the other
  uploader's scan, covers): either nothing is missing, or the requests aren't raised for this
  harvest. Checked against triage below.
- **No view of the text-step packets before the text step.** The maintainer wanted a sanity
  pass over the 125 packets before spending Fable. The batch page only exists after triage,
  and the text trial's index needs answers; the closest page is the watch's Assembled tab
  (hands off), which assembles each issue again live as it loads. v3: the packet milestone
  gets its own list view (thumbnail, checks, text.md, sheets), the gate before a model runs.
