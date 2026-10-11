# Making the next publication go better

Lessons from Judge, 2026-10-11. The plan that morning was 30 minutes of touch-up on the review
site. It took the whole day, and almost none of that time went on the crosswords themselves.
This note says why and what to change before the next publication (GAMES, then the rest).
None of it should hold up Judge's gxd merge request.

## What went wrong

Every problem that day had the same shape: two parts of the system worked out the same fact
separately and got different answers, and nothing noticed until a person opened a page.

| What the user saw | The two answers that disagreed |
|---|---|
| 40 puzzles counted "restored" although nobody had checked their new answer keys | readiness guessed "someone saw this key" from packet files existing in `tasks*/`; building the proof queue made the files |
| The first import would have credited ~600 agent corrections and 84 "looks right" verdicts to the user | the importer took every `review.json` for a new review, including the queue's replayed ones |
| Each import re-added old verdicts and re-marked finished puzzles needs-work | verdicts were stamped with the import time instead of the proof's |
| No. 17 and 16 others showed "no answer key" although the xd had one | relink and task-packets each worked out which key a puzzle has; a typed key dropped its scan, and recovered keys were never saved |
| 13 more puzzles showed a black square as a letter, or clues under the wrong numbers | the page shows "OCR plus a list of changes" worked out separately from the xd |
| 1929-02-02 showed no key to the user although the site had it | the CDN served an older copy |
| ~50 misread key letters (I for T, D for O) in puzzles already marked done | key letters are checked only by eye, with no word check |

Underneath all of it, each puzzle lives in six forms: the OCR state on the dev machine, the fix
file and ledger in git, the working xd, the review packet, the copy on R2 behind a CDN, and
proofs in Supabase. Some facts are guessed rather than recorded. The rule "the review page is a
proxy for the xd" was a convention, not a check.

Running harvests on this machine and keeping the record in git aren't the cause. A server with
the same design would drift the same way.

## Changes, in order of payoff

### 1. The review page shows the xd itself

Today a packet is the raw OCR plus `review.json`, and `current_review` works out "everything fixed
so far" as a diff against the OCR. Instead, the packet carries:

- the xd as it stands (exactly the bytes in `judge/xd/`)
- for every field (each square, clue, header, note), where its value came from: OCR, a named
  reviewer's ledger entry, a hand fix, a typed key, an automatic repair
- for every field, the OCR's original reading
- scan crops of the grid, the clues and the key page

The page draws from the xd, so it can't show anything else. "Changed from the OCR" becomes a
property of each field rather than a separate list to keep in sync. The round-trip check
(xword-ocr `proof_mismatches`, blitz `site-publish` gate, 2026-10-11) stays as a backstop.

### 2. Record who saw what; don't guess it

- Every proof stores a fingerprint of the exact xd it was made against. The site knows it,
  because the packet carries it.
- Readiness and puzzles.tsv compare fingerprints: "your proof was of an older version: the
  key changed since" is an exact statement. No reading of file times in `tasks*/` folders.
- A puzzle is done when a person's proof's fingerprint matches the current xd and the person
  said Ready. That is the whole rule.

### 3. Decide each puzzle's key in one place, and save the decision

- Relink saves the key it chose, recovered keys included, in the state or the manifest. Packets,
  the export and readiness read that decision; none of them looks the key up again.
- A typed key always names its scan (fix file `solution` requires `solution_from` or a page
  link; relink refuses otherwise), so typed letters always show next to the printed key.

### 4. One command for the maintainer's loop, which stops on surprises

The loop is site-import, dry-run import, import, relink, volunteer-sync, verify, commit,
packets, check, publish. Today each step was run by hand, and the steps that can damage the
record (importing from the wrong folder, verdicts outside the batch) were easy to get wrong. One
command (`blitz sync <pub>`) should:

- run the dry import and show what it would add, by person: N edits, M verdicts
- refuse anything surprising (an import crediting someone with hundreds of corrections, verdicts
  for puzzles outside the batch, xd changes nobody's proof explains)
- run relink, sync, the clue/black-square verify against the last release, commit, packets,
  the round-trip check, publish
- end with a short report: what changed, the state counts, what to look at next

The maintainer reads one report instead of six command outputs.

### 5. The harvest checkpoint before any review (follow-up 0)

Much of the day's churn came from keys found late: 17 typed by hand, 49 linked after their
puzzles' review, the fragment matcher arriving mid-review. Settle every exception (missing
numbers, near-miss keys, duplicate scans) before the first puzzle goes to review, so a reviewed
puzzle doesn't get a new key underneath it.

### 6. Check key letters against words

A word check on every answer, before review and as a checkup grade: an entry that isn't a known
crossword answer but becomes one by changing an often-confused letter (I/T, D/O, S/E, C/G) gets
flagged on the page. On 2026-10-11 a rough version (gxd answers as the word list) found ~60 strong
suspects in Judge, a dozen of them in puzzles already marked done. The OCR's letter confidence
missed them.

### 7. The site's queue comes from the record

"What needs a person, in what order" should come from puzzles.tsv (the reason column), and
"Worst first" should use it, so the queue is right without a hand-run grading script. Today's
order was patched in by a scratch script setting checkup grades in Supabase.

### 8. Cache rules that can't serve stale puzzles

Version the packet URLs (the xd fingerprint in the path), or send `no-cache` on everything the
page reads. A reviewer must never proof an older copy than the one published.

## What to keep

- **Git as the record:** xd files, ledger, fix file. History, diffs and blame are what make the
  provenance believable, and it's how gxd works.
- **Harvest and OCR on the dev machine.** They need the GPU, the scan cache and the state file.
- **Supabase for proofs**, which are already rows with people and times.

## Later: a database for the working state

When several publications have outside volunteers, the import-commit loop becomes the
bottleneck. Then: the ledger becomes a Supabase table (each proof edit a row as it happens), the
page reads live state, and a sync job writes the ledger and xd to git for the record. Items 1-3
above are the groundwork. They make the page, the proofs and the record agree by construction,
which a database alone would not.

## Done means

A publication is ready for gxd when:

- every puzzle's latest person-proof fingerprint matches its current xd, and the proof said Ready
- every value in every xd shows on its review page with its source (the round-trip check passes
  for every puzzle)
- the harvest checkpoint's exceptions are all settled, each with a note
- the word check's flags are each confirmed or fixed
