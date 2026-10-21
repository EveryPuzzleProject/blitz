# GAMES 1980–82: a hands-off run on v2 (plan, 2026-10-21)

**Purpose.** Run GAMES 1980–82 through the v2 pipeline as hands-off as possible, as a test of
what v2 can do on puzzles it was never tuned on, and to take the per-puzzle cost baseline
against the 10% token target. It's a measurement as much as a batch: record what happens, and
don't fix the tools along the way unless something blocks the run. Findings go on the v3 list
(design/restructure.md, xword-ocr memory "v3 lessons from v2").

Start a fresh session with this document as its brief. The goals and rules are in xword-ocr's
and blitz's CLAUDE.md ("The pipeline: runs quietly in the background", "The north star").

## Starting point

- **Harvest:** `xword-ocr/harvests/games-8082` (manifest, state, keys) was harvested on
  2026-10-15, before most of v2: assembly that only links text, the text step's findings as
  records, `^Easy` clue sets, Feature, dispositions, restart and remedies. Measured then,
  hands-off assembly found 105 of the 106 puzzles in the maintainer's box review, plus 19
  extras.
- **Reviewed reference:** the games ledger (`fixes/decisions.jsonl`) holds about 500 records
  for 1980–82 from the maintainer's box review on 2026-10-14/15. A hands-off run ignores them
  by design; use them to score the run, not as input.
- **Run registry:** `games/pipeline/triage/runs.json` is written for GAMES 1977-79 only (one
  `current`). Give 1980–82 its own registry first: a file per batch, or batch-keyed entries,
  so the batch page, publish and import pick the right run per batch. That's the one piece of
  setup code to expect.

## Before the run: remove known friction (the maintainer)

- Exempt `xword-ocr/harvests/` from the edit hook in the Claude Code settings. Each text-step
  run in 1977–79 needed the user's OK to copy answers back past the hook.
- Pull all three checkouts (xword-ocr, blitz, games) to main.
- Fable budget: the text step ran at about 7.8k tokens per puzzle in 1977–79. For about 110
  puzzles, expect roughly 0.85M Fable tokens. Check the weekly meter before starting.

## The run, in order

Each step is a command or an agent pass; stop only where marked **(ask)**.

1. **Re-assemble with current code**, compute only, from the 2026-10-15 harvest. **No
   re-harvest:** the pages, OCR, region boxes and answer grids found are reused; only the stages
   after OCR run again. Two things first:
   - **Re-read the answer keys' letters** with the key-reader fix of 2026-10-18 (letters on a
     key's edge row or against a heavy border; xword-ocr#27). 1977-79 needed the same step
     (run10, all answer grids re-read). It's compute only, from the stored page images.
   - Assembly reads parts from the stored OCR, so the clue-reading fixes (blanks, two-page lists,
     columns) apply without new OCR.

   Then run the request loop for pages assembly asks for, including keys on the other uploader's
   scan and issue covers (`xword-ocr requests --out harvests/games-8082 --run`; **ask** if it would
   take over ~10 minutes). Those are the only downloads.
2. **Text-step packets** for every puzzle (`scripts/text_trial.py <run> --all` with
   XWORD_HARVEST=games-8082, XWORD_START=1980-01-01, XWORD_END=1982-12-31). Register the run.
3. **The text step (ask):** report the count and Fable estimate, then run the `xword-text`
   batches and report the meter after the first. Agents write into the run folder (once the
   hook is exempted).
4. **Proof packets and triage**, with the gxd clue cross-check. Use the dispositions: Needs work,
   Ready for review, Reviewed.
5. **Remedy agent:** "check the Needs work puzzles, fix what you can, flag the rest". It
   restarts from the right stage; it never transcribes. Scan looks stay within the budget (one
   or two per kind of failure, never more than ~10% of the batch). Fetch any pages it requests.
6. **The maintainer's pass:** what's left under "For you" on the local batch page, plus kind
   decisions such as Set aside for number crosses and Not a crossword for RightAngles. Count
   every human touch.
7. **Publish for review (ask):** proofs and batch snapshot (`site-publish`,
   `site-publish-batch`), drops and set-asides included, as batch `games-1980-82`.

## What to measure (the point of the run)

Write the measurements to `design/games-8082-results.md` as you go:

- **Cost per puzzle, by role,** from the session transcripts and sub-agents' records: the text
  step, the remedy agent, scan looks, and orchestration. Report the categories separately
  (output, cache writes, cache reads, input) plus the API-dollar equivalent, against the 10%
  target. Run it as a **pure orchestration session**: no code changes beyond the run registry,
  so the numbers measure the pipeline, not tool-building.
- **Hands-off quality:** puzzles found against the box-review reference; the dispositions
  after triage and after remedies; and how many Needs work the remedy agent fixed, versus
  flagged for the maintainer.
- **Human touches:** each decision the maintainer made, and why.
- **Wall-clock time per step,** and every point where the run stalled or needed a person.
- **New failure kinds** that didn't appear in 1977–79. Each one goes to the v3 list.

## Rules for the session

- No new features. A tool problem that doesn't block the run is a finding, not a fix. If
  something blocks, make the smallest fix, as its own PR, and say so in the results.
- Work in your own worktrees. Never write into the user's checkouts, except the harvest folder
  the pipeline writes to.
- A watch server writes decisions into the games checkout it points at, so point it at the
  user's real games checkout. A throwaway copy loses them (that's how two Readys and three
  set-asides were stranded in 1977–79).
- Open PRs only when the work is done, and stop pushing to a branch once its PR is open or
  merged.
- Report progress as pages to open (the local batch page, the published batch), not chat
  lists.

## Known traps from 1977–79

- **Puzzle kinds aren't classified upstream.** Cryptics, number crosses and RightAngles reach
  review as exceptions. Current policy: number cross is set aside; RightAngles is not a
  crossword; cryptics are reviewed, and set aside only by choice.
- **Two clue sets** (Hard and Easy) become `^Easy` clue metadata. Check that the flag fires
  only on real second sets.
- **Region boxes that start at the grid** can cut off a title or byline. That's a review ask
  now, not a blocker.
- **The key reader** can read a column of a hand-lettered key's black squares as letters. It's
  recorded as a check, not a blocker.
- **Page numbers** got stuck to clue lines (the "38" on an Easy clue).
- **The site build:** `docs/review` must be rebuilt after any page change (a test catches a
  stale build).
