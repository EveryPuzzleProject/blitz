# Judge post-mortem

Judge magazine's crossword, 1924–1939, was the first full series taken through the tools,
from archive.org scans to a gxd merge request. This is the internal record of how it went:
what worked, what hurt and why, and what to change before the next series. The proposed
changes are in [next-publication.md](next-publication.md), and the backlog is in
[followups.md](followups.md). Written 2026-10-12, before the merge request went in.

## In one paragraph

531 puzzles (Nos. 1–415 in two numbered runs, plus specials and second puzzles) came out of
about 720 scanned pages from 458 archive.org items, in about 15 days (2026-09-28 to 10-12).
Every printed number was found, and every puzzle has an answer key except the last two, whose
keys would have run in issues we don't have. Agents did nearly all of the reading: 11,172 of the
ledger's 11,827 rows. The maintainer made 489 edits on 172 puzzles, and review-site helpers made
46. The pipeline and the agent reviews were good: grids and clues were almost always right by
the end. The problems were elsewhere:
- **Discovery.** 18 puzzles and about 70 answer keys were found only in the final gap hunt.
- **One letter.** The answer-key reader confused I and T (and D/O, S/E) all the way through.
- **The last day.** The final "30-minute touch-up" (2026-10-11) took the whole day, because the
  xd, the review packets, the site and the readiness check had drifted apart.

## Timeline

| Dates | Phase |
|---|---|
| 09-28 – 09-29 | Pipeline and first puzzles: masthead dating, review editor, task packets, first Fable batch; scope set (no cryptics, diagramless allowed) |
| 09-30 – 10-01 | Keys and rescues: partial keys extended (+42), 22 rejected grids rescued; batches 2–6 |
| 10-02 – 10-06 | Volunteer flow (blitz repo, first PR import); the catalog; Judge reprinted as 1925 "Cross Word Funnies"; missing numbers audited |
| 10-06 – 10-08 | Text-first review and the restricted `xword-reviewer` agent; batches 7–11; the continued-page reader; segmentation measured before merging |
| 10-07 – 10-09 | The public review site, then the proof page at /review/ |
| 10-09 | 298 reviews imported (6,146 corrections); judge repo takes over the fix file, ledger and state; `export-gxd` built; first gxd branch with 466 puzzles |
| 10-11 | Proofs on the site; gap hunt (18 puzzles, about 70 keys); the A fix (529 squares); the desync day |
| 10-12 | Agent review of the 21 new puzzles; payment notices and sourcing notes cleaned out; key-squares page for the last letter checks |

## What worked

- **Agents for the reading, people for the judgement calls.**
  - The text-first review: the agent reads `text.md`, then looks only at code-chosen crops of
    the scan. The restricted `xword-reviewer` agent brought the cost down to about 17k tokens
    and 0.15% of the weekly Fable allowance a puzzle, against 0.36% for a full-image review.
  - Fable agreed with itself on 91% of corrections. Haiku missed about two-thirds of the errors.
  - The API trials (Sonnet about $0.05 a puzzle, Opus $0.11) were dropped: the free Fable
    allowance does the work.
- **The tool-notes loop.** Reviewers report what the tools got wrong (1,599 notes); `blitz
  feedback` groups them, and each becomes a code fix or a line in `review-notes.md`. The I-letter
  fix it led to took letter accuracy from 90.9% to 99.6%.
- **Measuring before merging.**
  - Segmentation changes were scored against reviewed text before merging (exact clue matches
    went from 22,030 to 22,774 of 24,338).
  - Rebuilds were verified against a fixed judge commit, 0f808bb: no clue or black-square
    change slips through.
- **An append-only ledger with names on every row,** plus `epp scans restore`, which rebuilds
  every .xd exactly. Every change is attributable and reversible.
- **The importer's numbering check.** It refuses a grid fix that doesn't number into its clues.
  It caught real agent mistakes, including 1933-10-01b on the last day. Only 4 of 298 agent
  reviews touched a grid, and 2 of those were wrong.
- **The proof page** ("already a huge improvement"), Next puzzle as a queue, and the one-page
  key-squares checker on the last day. Narrow tasks with the evidence beside them go fast.
- **The user's scan research.** Many of the hardest finds came from reading the magazines:
  - No. 156 printed as 155;
  - keys under the next puzzle;
  - the Funnies reprints;
  - keys in double issues.

## What hurt, and why

### 1. Discovery came last instead of first

- **What was missed:** 18 puzzles were found only in the gap hunt, along with about 70 keys.
  Among them were monthly second puzzles, keys under a different puzzle's number, keys cut in
  pieces, and duplicate scans (No. 44, No. 310).
- **The cost:** each late find changed puzzles that had already been reviewed. A newly linked key
  meant nobody had checked its letters, and a new puzzle meant ids to pin and re-harvests that
  could degrade reviewed text.
- **Cause:** harvest dropped its exceptions on the floor (unmatched keys, gaps in the numbering,
  near-miss key shapes) instead of listing them for a decision.
- **Next time:** the harvest checkpoint (follow-up 0). Nothing goes to review until every
  exception is settled.

### 2. One OCR failure, everywhere: the answer-key letters

- **The failure:** I for T; D for O; S for E; the hand-lettered A read as Δ or left unread. These
  come with high OCR confidence, so the letter-confidence flags didn't catch them.
  - The first ten puzzles a person reviewed took 88 edits, 52 of them I-for-T, none flagged.
  - On the last day a word check found about 60 strong suspects, a dozen of them in puzzles
    already marked done.
- **Cause:** keys were checked only by eye. No step asked "is this answer a word?"
- **Next time:** a word check on every answer (gxd's answers make a good list), from the first
  harvest, as a checkup grade.

### 3. The desync day (2026-10-11)

Every problem that day was two parts of the system working out the same fact separately and
getting different answers:
- readiness guessed "seen" from packet files;
- the importer read replayed packets as new reviews;
- verdicts were stamped with the import time;
- relink and the packet builder each worked out which key a puzzle has;
- the CDN served a stale copy.

Each puzzle exists in six forms: the OCR state, the fix file and ledger, the working xd, the
review packet, the R2 copy, and the proofs in Supabase. The full analysis and the fixes are in
next-publication.md. The round-trip check and the publish gate (the page must show the xd, built
from committed data) now catch this class of problem.

### 4. Re-harvests degraded reviewed work

`harvest --only` re-reads pages. In one run No. 311 was re-read as a key and disappeared, and
four reviewed clues got worse. The workaround (back up the state, restore the old readings,
verify) works but is manual. Next time: a re-harvest keeps readings that were already reviewed
(follow-up 8).

### 5. Notes and provenance were mixed up

Sourcing, OCR caveats and layout decisions went into the puzzle's `note`, which would have gone
into gxd's Notes. The rule now:
- gxd Notes hold only corrected print misprints;
- everything else goes in `provenance`, which shows on the review page and stays out of gxd.

Bylines and printed lines also carried Judge's payment notices, which aren't part of the puzzle.
Both cost the maintainer most of the last day's clicks, all mechanical.

### 6. Shapes and odd layouts were typed by hand

These were typed or patched by hand:
- the two face-shaped grids and the heart;
- 15 Down lists continued on the next page;
- No. 171's Down list (typed, and invisible on the review page until a hand patch);
- circled squares;
- printed numbering that differs from the grid.

Each was a judgement call that ended up in the fix file. See follow-ups 1, 2, 10 and 12.

## What it cost

- **Agent review:** about 0.15–0.36% of the weekly Fable allowance a puzzle, depending on the
  method. The 5-hour limit stopped work once, for about 80 minutes. No API spend after the
  trials.
- **Maintainer time:** most of it went on tooling, and on the last two days on proofing and
  cleanup the tools should have done. Of the last 11 puzzles proofed by hand, 2 needed a letter
  fixed. The rest of the proofing time went on payment notices and notes.
- **Machine:** the 2.8 GB packet folders, and a 15-process pool that used 19 GB and crashed the
  machine once (keep pools small).

## Rules settled during Judge (carry them forward)

- **No hidden data.** Everything in the xd shows on the review page with its source. Decisions
  are provenance, visible on the page.
- **Misprints:**
  - Clue misprints stay as printed, with `sic`.
  - Misprinted answer-key letters are corrected, with a note in the form "The solution grid that
    ran on <date> printed 1 Down as TAHG. It has been corrected to TANG."
- **gxd export:**
  - The .xd is puzzle-only.
  - Number always; keep Byline; normalize Author/Editor/Date.
  - Unsolved puzzles are fine.
  - Payment notices and printed solicitations are not part of the puzzle.
- **Sourcing:** provenance goes in receipts or our own layer; source archives go straight to S3.
- **Ids:** pinned in `fixes/xdids.tsv`. In gxd, the second puzzle on a date gets suffix `a` and
  the third `b`. Our working ids use `b` for the second, so the export must map them (still open,
  see below).
- **No publication-specific rules upstream.** Prefer general, reviewer-driven mechanisms.
- **Budget:** use the free Fable allowance.
- **Rights:** fair use for research; repos public by default.

## For the next series, in order

1. **Harvest checkpoint first** (follow-up 0). Every gap, near-miss key, duplicate scan and
   misnumbering is settled, with evidence and links, before review starts.
2. **Word check on answers from day one,** with a key-squares page (like the 2026-10-12 one) as
   the standard way a person checks keys: crops, keep or change, done.
3. **The review page shows the xd itself;** proofs carry an xd fingerprint; each puzzle's key is
   decided once and saved. (next-publication.md, items 1–3.)
4. **One `blitz sync <pub>` command** that imports, rebuilds, verifies, publishes and stops on
   surprises. (next-publication.md, item 4.)
5. **Notes and provenance separate from the start,** and the review instructions say so.
6. **Publication rules learned from confirmed data,** not hand-coded: where keys run, how
   numbering works, recurring printed text. (Follow-ups 7, 11.)
7. **People do the narrow checks:** key squares, grid rulings, misprint rulings. Agents read
   everything else. Budget the person's time per series from Judge: proofing a whole puzzle took
   about 2 minutes once the page was good, and a key square takes seconds.

## Still open for Judge

- **1933-10-01b (No. 297):** the agent's grid fix was refused at import and needs a person.
- **The key-squares page:** 88 squares across 39 puzzles, plus 28 clean keys to confirm.
- **Five notes to rule on:** keep in Notes or move to provenance (the wildcard square, the blank
  clue, the clue with no entry, No. 371's instructions and its answer).
- **Same-date suffixes in the export:** `export-gxd` writes our ids as they are
  (`judge1924-11-15b.xd`), but gxd names the second puzzle on a date `...a`. Map them in the export.
- **The merge request:** rebuild the gxd branch, a new scans archive, receipts, MR.md.
