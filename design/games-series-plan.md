# GAMES 1977–89: the whole series to gxd (plan, 2026-10-27)

The maintainer asked for one driver to take GAMES from where it stands to a gxd import, on
the existing process and the existing review tools, with the takeaways feeding v3. This is the
analysis and the plan, for approval before anything runs.

## Where it stands

**What the series is.** archive.org has 68 issues for 1983–89 (monthly in 1983–86, with
two uploaders most months; six a year in 1987–88, eight in 1989) on top of the 34 for
1977–82. The 2026-09 v1 harvest counted 425 crosswords in 1977–89 (keys found for about
90%). v2 finds about 60% more than v1 on the same pages (206 against 126 for 1977–82:
cryptics, warm-ups, unkeyed and continued puzzles), so the series is roughly **700 puzzles**,
about **480 of them not yet on v2**.

| batch | state | puzzles | ready for review | needs work | set aside / dropped | in games/xd | in gxd |
|---|---|---|---|---|---|---|---|
| 1977–79 (`harvests/games-7779`, run15-restart) | published for review 2026-10-21 | 81 | 62 | 7 | 3 / 6 | 0 | 0 |
| 1980–82 (`harvests/games-8082`, run1-handsoff) | run complete, not published | 125 | 58 | 62 | 0 / 5 | 0 | 0 |
| 1983–89 | v1 only; pages cached | ~480 (v2 estimate) | | | | 0 | 0 |

- **The review gate isn't moving.** In six days on the site, 1977–79 drew eight decisions,
  all "needs work" from one helper; the ledger has four Ready, none the maintainer's. The
  ship rule (one Ready, no Not ready) means nothing ships until someone reviews, and no
  one is. The maintainer has said twice they'd rather not read 700 puzzles.
- **Two experiments already answer what to do instead** (2026-10-21, not landed):
  - an AI proof review of the 62 ready puzzles (games branch `claude/ai-proof-review-7779`):
    42 Ready, 20 held with yes/no flags, about 0.9M input tokens a puzzle on Opus;
  - a **no-model ship check** (scratchpad `shipcheck.py`): complete, no recorded doubt,
    no clue slips → 29 of the 62 ship with no model at all; it catches 17 of the 20 the AI
    held. The maintainer leaned toward this one.
- **1980–82's hands-off result:** 58 ready / 62 needs work on untuned puzzles. The remedy
  agent fixed none of the 68 outright: most failures are assembly linking a read part to the
  wrong puzzle (the cryptic heading to the warm-up beside it; a quiz as a clue list; a fold
  page not joined to its 25x25), and no remedy action reaches linking. Its results doc is
  uncommitted in blitz worktree `games-8082`; its remedy decisions and relinked records
  (148 files) are **uncommitted in the games main checkout**.
- **Measured cost, 1980–82** (API-equivalent, per puzzle): text step on Fable $0.28 (12k
  billable tokens, 135k cache reads); remedy agent $0.03; orchestration $0.07; **$0.39** in
  all, before any review. The text step on 125 puzzles moved the weekly Fable meter 13 points.
- **Export to gxd exists for v1 only.** `export-gxd` reads the v1 `manifest.json`,
  `puzzles.tsv` states and `games-scans/sources.tsv`. The v2 import (`import-batch`) writes
  `games/xd/` from the ledger's shipped puzzles, but nothing yet writes puzzles.tsv rows,
  sources.tsv rows or receipts from v2 records, and gxd has no `games` publication. So even
  a reviewed v2 puzzle can't reach gxd today.
- **Pages are already here.** The IA cache holds 4,400 page images for 1983–89 and
  games-scans has 874 rows for those years, from v1. A v2 harvest of 1983–89 is mostly
  compute (OCR, regions, parts), not downloads.

## The diagnosis

GAMES was chosen as v2's test because it is hard, and it is: several puzzles a page, four
puzzle kinds a reviewer must tell apart, features and sub-series, two clue sets, keys that are
prose. Most of what 1980–82 surfaced is **GAMES-shaped** (cryptic pages, Ornery fold pages,
quizzes beside grids) and won't recur in a newspaper with one puzzle a page. The maintainer's
worry is right: tuning assembly to every GAMES layout is over-fitting.

But the thing actually blocking the series is not assembly. It's that **the process ends at a
human gate nobody staffs**, and that **the export path was never joined to v2**. Those two are
publication-independent, and fixing them is what every later publication needs anyway.

So the plan does three things, in this order, and avoids a fourth:

1. **Replace the human gate with a machine gate plus an AI reviewer, people for exceptions.**
2. **Join v2 to the gxd export, with the source archive.**
3. **Run 1983–89 as hands-off batches, measuring, with only generic tool fixes.**
4. Not: build v3, and not: tune assembly to GAMES's layouts beyond two generic rules.

## 1. The ship gate (publication-independent)

A puzzle's disposition after triage becomes one of:

| disposition | how decided | tokens | who sees it |
|---|---|---|---|
| **Ships** | the no-model check: every slot clued, grid solved (or key confirmed not printed), numbering consistent with the grid, no text-step `unsure`, no recorded defect, no clue slip (unbalanced quotes, "a. plane", number read into text), second clue set present when promised; plus the gxd cross-check (seen pairs confirm, near misses hold) | 0 | nobody; it's in the import plan with "shipped by rule: <checks passed>" as its source |
| **AI review** | anything Ready for review that the check holds: one subagent per puzzle on proof sheets, asked for Ready / Not ready with yes/no flags, recorded as a helper's decision (xword-ocr `claude/ai-proof-review` makes that the rule) | ~0.9M input (Opus) today; target under 100k by sending only the flagged crops | nobody unless Not ready |
| **For you** | AI Not ready, Needs work after remedies, kind decisions the policy doesn't cover | | the batch page, "For you", each with a diagnosis and a proof link |
| **Policy** | kind classification at triage: cryptic (reviewed, kept, not exported), number cross (set aside), RightAngles / word paths / acrostics / contest example grids / Answer Drawer pages (not a crossword) | 0 | the batch page's Set aside and Not a crossword groups, reason shown |

This changes the ship rule for GAMES: **a rule-shipped puzzle and an AI Ready both count as the
one Ready**; the maintainer's own decision still overrides. It is a decision for the
maintainer (see "Decisions" below). Everything is visible on the batch and proof pages with
its source, as the no-hidden-data rule requires; the import writes `Shipped: by rule
(checks ...)` or `Proof: ready by Claude (AI proof reviewer, <model>)` into the xd's
provenance headers, which the export strips.

What this takes: promote `shipcheck.py` into `triage.py` as a disposition with its checks
as reason codes; a `ships` group on the batch page; the AI reviewer as a documented agent
(`xword-ocr proof-review <run> --pids ...`, proof sheets built by code, not in a scratchpad);
`import-batch` reading the new rule. About one session.

## 2. The export path (publication-independent)

`import-batch` → `games/xd/<xdid>.xd` already works for shipped puzzles. What's missing, each
a small piece of `export-gxd` or the games sync:

- **puzzles.tsv from the v2 ledger**: one row per v2 puzzle (provisional ids until assigned),
  state from the disposition (`shipped`, `ai-reviewed`, `needs-person` + reason, `set-aside`,
  `not-a-crossword`), so the export's state filter and the status page work for v2.
- **The pages behind each puzzle into games-scans**: a proof packet records `built_from`
  (grid page, clue pages, key page, cover). `export-gxd --source` copies those pages from
  the harvest and writes their `sources.tsv` rows (path, archive.org URL, sha256, captured,
  used_by), the same shape v1 used. The archive is every page the exported puzzles were read
  from, named `<item>/page/n<leaf>.jpg`, built with gxd's `make-source-archive.py` and put
  in `s3://gxd-sources/src/`, sha256 in the MR.
- **The export's filter reads v2's states**, and takes `games/xd/` as its input instead of
  the v1 manifest; `Feature:` maps to a gxd header (`Category:` proposed, to clear with
  Saul); `^Easy` clue lines kept; the Notes rule (printed instructions and theme text in,
  sourcing out) applied by label.
- **gxd side**: a `games` row in `publications.tsv` and `pubregex.tsv`, `receipts.tsv`
  rows, xdlint clean (the Ornery 25x25s and unkeyed cryptics will warn; cryptics aren't
  exported), `games/gxd-exports.tsv` for crossref's credit line.

About one session to build, then an MR per batch (1977–82 first).

## 3. 1983–89, as hands-off batches

Three batches by density, each the 1980–82 recipe (`design/games-8082-plan.md`), no code
changes inside a run:

| batch | issues | puzzles (v1 count → v2 estimate) | note |
|---|---|---|---|
| 1983–84 | 24 (two uploaders most months) | 84 → ~140 | pick a main uploader per issue (prefer one series) |
| 1985–86 | 24 | 104 → ~170 | densest years |
| 1987–89 | 20 | 111 → ~170 | one uploader from 1987 |

Per batch: v2 harvest from the cache (compute; ~1–2 h wall clock, run in the background);
text step (Fable: about 15% of the weekly meter per 125 puzzles, so one batch a week, or
Opus for the clean packets and Fable only for packets with unsure lines; measure both on the
first batch); proof packets; triage with the ship gate; remedy agent; AI review of what's
held; the maintainer's "For you"; import-batch; export.

**Tool fixes allowed between batches**, only for kinds that recur across publications or
block a third of a batch, each its own PR and a compute-only re-run:

- a **relink decision** ("this part belongs to that puzzle") the remedy agent and the
  batch page can record and assembly obeys: the one action 1980–82's 60 "for you" needed;
- **two generic linking rules**: a heading links to the largest grid under it, not the
  nearest small one (the cryptic/warm-up page); a block whose numbering doesn't fit the grid
  isn't its clue list (the quiz-as-list failure);
- **kind classification** at triage with per-kind policy (above);
- a request raised for a cryptic's answer page even though no grid key is expected
  (so the request loop has something to fetch).

Not done for GAMES: Ornery fold-page joining, two-player lists, digit keys, barred grids.
Those are set aside with a reason and counted; they go on the v3 list.

## 4. What would cut the token cost most

The maintainer's question: with a person out of the loop, what tools would most reduce the
driver's own spend? Where a puzzle's tokens go today (1980–82, API-equivalent):

| step | per puzzle | what it's spent on |
|---|---|---|
| text step (Fable) | $0.28; 12k billable + 135k cache reads | 9 KB instructions and ~50k harness overhead per agent, a 460 KB sheet image, 2.6k output; most corrections are mechanical (a number read into the text, a column break, a blank) |
| AI proof review (Opus) | ~$0.35; 0.9M input | the whole puzzle's crops read again, to confirm what's mostly right |
| orchestration (Opus) | $0.07; 215k cache reads | waiting on 13-minute request loops and 38-minute snapshots; reading 13 agent reports; this analysis alone cost 190k tokens of reading docs before a single command |
| remedy (Sonnet) | $0.03 | diagnoses it can't act on |

In order of leverage:

1. **Verify in code, review by exception.** The key gives the answer; crossings check the
   grid; numbering checks the lists; gxd's clue database (48% of pairs already seen) and a
   word list confirm most clue/answer pairs. A puzzle that passes every check ships with no
   model. The model sees only what failed, as one crop and one question, on a cheap model.
   This turns the 0.9M-token review into maybe 20k, and makes half the batch free.
2. **Make the recurring text-step corrections code.** Its findings are records now; the
   kinds that recur (number into text, column-break shuffle at the list's end, dropped
   blanks and ellipses, stars after a title) are reading fixes. Each one moved to code
   removes an output token from every later puzzle, and a packet with nothing flagged can
   skip the model or go to a cheaper one.
3. **A relink action and kind policies**, so remedies fix instead of flag, and set-asides
   are automatic. Every "for you" is a human touch and a round of my context.
4. **Milestones that are recorded once.** Assembly ran three times over the same inputs in
   1980–82; the batch snapshot fetched 1,031 files through a live server. Wall clock here is
   orchestration tokens: every wait is a turn.
5. **One status command** (`blitz batch status <batch>`: runs, dispositions, what's
   blocked, what's next) in place of reading five design docs and a registry to find out
   where a batch stands. The handoff cost between sessions is the largest hidden spend in
   this project.
6. **Restrict what the text-step agent carries**: a subagent with only Read and Write still
   loads the full tool schemas; a leaner harness (or the API in batch mode for volunteers
   who have credits) would halve the fixed cost per agent.

A frontier model reading every page is about 61k tokens a puzzle (the 2026-10-15 baseline).
Today's pipeline is at about 12k for the text step plus review; with items 1–2 the clean
half of a batch costs nothing and the rest a few thousand, which is the 10% target.

## Decisions for the maintainer

1. **The ship rule for GAMES**: rule-shipped and AI-Ready puzzles ship; you see only Not ready,
   Needs work and policy exceptions, on the batch page. (Yes / keep waiting for the site.)
2. **The text-step model for 1983–89**: Fable for all (about three weekly meters over three
   weeks), or Opus for clean packets with Fable for flagged ones, decided after the first
   batch's comparison.
3. **gxd**: pubid `games` and shelf `games/`; `Feature:` as `Category:`; cryptics kept in
   games/xd but not exported. To raise with Saul before the first MR.
4. **1990–99**: out of scope for now (scans thin, 50 issues); say if you want them queued.

## Order of work

1. Land what exists: the 1980–82 results doc and ledger records (PRs from the games-8082
   worktrees), the AI proof review branches, the ship-check prototype as a triage
   disposition. Make 1980–82 current and published.
2. Build the ship gate and the AI reviewer command; run them on 1977–79 and 1980–82; the
   maintainer's "For you" pass.
3. Build the export path; export 1977–82; the first gxd MR with its source archive.
4. 1983–84, then 1985–86, then 1987–89, each with its results section appended to this
   document and its new failure kinds on the v3 list.
5. After GAMES: the next publication should be a single-puzzle periodical, to measure the
   per-puzzle cost of the common case GAMES can't measure.
