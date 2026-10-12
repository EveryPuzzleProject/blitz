# Follow-ups

Work agreed on but not started. Take these on once Judge's gxd submission is done.
The lessons from Judge's last day, and the changes to make first, are in next-publication.md.
Newest at the bottom of each section; strike through or delete when done.

## Tools

0. **A harvest checkpoint: confirm the exceptions before review** (user, 2026-10-11). This one ties 6, 7 and 9
   together. Right after harvest, and before any puzzle goes to review, the harvest writes an exceptions list.
   A person, or an agent with a person checking its calls, works through it while the context is fresh,
   instead of these turning up at the end as gaps to hunt down. Each row shows its evidence side by side
   (crops plus links to the archive.org pages) and takes a one-click answer that goes into the fix file as a
   decision with a note:
   - a duplicate number: the same puzzle scanned twice (skip), a misprinted number (puzzle_number + note), or
     two puzzles;
   - a gap in the numbering: here's where we looked, so the puzzle is found on page N, or it's confirmed not
     in the scan;
   - a near-miss key: the right key but cut off or split (re-crop), or not this puzzle;
   - a key with no puzzle, or a puzzle with no key;
   - a grid read as a key or a key read as a grid; an odd shape; a continued clue list.
   The gap page (scratch gap_page.py, harvests/judge/gap-index.html) is the prototype. Harvest's status
   says "N exceptions open", and nothing is "ready for review" until they're settled.

1. **Detect odd-shaped grids** (agreed 2026-10-11). Telling "printed square" from "blank page"
   around a grid is mechanical: the grid reader should mark squares outside the shape as `_`
   (xd's "not part of the puzzle") and find a shape's ring of black squares, so shaped grids
   (Judge's heart and two faces, GAMES's many) come out of the pipeline reproducibly instead
   of typed by hand into the fix file. Today: judge1924-12-06 and judge1925-02-14 were mapped
   by hand from the scans (judge 7f889b3, 8e0a93a).
2. **Better continuation detection** (agreed 2026-10-11). `pipeline.list_continues` only flags
   a clue list as going on to another page when more than half its clues (and 10+) are missing.
   judge1929-02-02 had 21 of 64 missing and was only caught by a reviewer; it was then read with
   `continuations --only judge1929-02-02 --direction D`. Use better evidence: the missing clues
   are a run at the end of the list, the last printed number is far below the grid's last, the
   list ends at the foot of a column or page.
3. **Draw a box on the review page** (agreed 2026-10-11). On the proof page, a row with no crop
   (a byline, title, caption or clue the OCR never found) should let the reviewer draw where it
   is on the whole-page view. Save it as `regions` in the proof; `import-reviews` passes helpers'
   regions through as it does agents' (re-OCR'd into `region-ocr.json`), so the text is read
   rather than typed and the next reviewer sees the scan crop as proof. Motivated by the
   Tomordy byline on judge1926-01-30, which had no crop.

6. **Harvest discovery: examine every page the text search finds** (2026-10-11). In Judge's monthly years
   (2-3 puzzles an issue) the harvester missed puzzles whose pages archive.org's own text search finds
   ("crossword" hits both No. 320 and No. 321 in the November 1934 issue; we had only No. 320). About 17 of
   Judge's 23 missing numbers have their title in the page text. Also look for answer keys in the same issue
   ("Solutions of Puzzles in this Issue", unnumbered, Mar-Nov 1937) and by "Solution of Puzzle No. N" text,
   not only by grid shape in later issues: 38 of 71 missing keys were found that way. Judge was patched by hand
   with extra_pages; the general fix belongs in discovery. Search the page text for "puzzle" and "solution" as well as
   "crossword": the user found "puzzle" hits where "crossword" doesn't (OCR mangles stylized headings).

7. **Near misses become candidates, not drops** (user, 2026-10-11). The answer-key matcher is yes/no:
   a key one column short (1931-04-04, 1931-05-02, 1936-04-01, Oct 1933's two), in two pieces (No. 316),
   or off by a square is silently dropped. Keep these as ranked candidates (what fits, what's off), show
   them side by side with the puzzle for a one-click "yes / no / yes but cut off" (as on the Judge gap
   page), and on "yes" widen the crop to the full grid and OCR the rest. The same for puzzle pages:
   surface "probably a crossword here" pages rather than dropping them below a score.
8. **Re-harvest must keep existing page readings** (2026-10-11). `harvest --only` re-OCR'd pages it already
   had: a puzzle grid was re-read as an answer key (No. 311 vanished) and four reviewed clues degraded
   where reviewers had confirmed, not corrected, the OCR. It should reuse cached analyses for known pages
   and analyze only new ones (Judge was repaired by restoring the earlier readings).

9. **Check the series: duplicates and order, not only gaps** (user, 2026-10-11). Numbering gaps become
   "missing" rows, but two puzzles with the same number weren't flagged: Judge printed No. 156 as "No. 155"
   (1930-05-17, a week after the real 155, with 156 missing between them), and No. 44 appears twice
   (1925-10-10, 1925-10-17b). Report duplicate numbers, numbers out of date order, and a duplicate beside a
   gap (a likely misprint) in the harvest's status and as a warning on the puzzle in review. Also catch the same
   page scanned twice: No. 44 (1925-10-10) reappears as leaf 40 of the 1925-10-17 item, and No. 310 twice in
   1934-06, each time one copy filled in by a reader. Same number plus near-identical clues means a duplicate
   scan, not a second puzzle.

11. **Learn each publication's layout from what's confirmed** (user, 2026-10-11). Where the puzzle sits in
   an issue, where its key runs, and whether a second puzzle is on the facing page are all regular, and the
   data already shows it. Judge's confirmed puzzles sit at leaf 31 (10-90%: 31-34 weekly, 31-38 monthly).
   Keys are in the next issue for 290 of 292 weekly puzzles and 177 of 191 monthly ones; the other 14
   monthly keys are in the same issue, a few pages from the puzzle. Fit these as statistics per publication
   (data, not hand-written rules: see no-publication-specific-cruft) and use them to:
   - rank the pages to examine first, so a gap hunt starts at "leaf 30-32 of this issue, then the
     facing page";
   - put an expectation on each exception in the checkpoint (item 0): "No. 297 expected near leaf 31 of
     1933-10; its key near leaf 31 of 1933-11";
   - flag a placement that breaks the pattern (a key two issues later, a puzzle at leaf 8) as an exception.
   The model updates as reviewers confirm pages, and a change in the pattern (weekly to monthly, a
   same-issue key) is a finding to show, not noise.

12. **Keep printed clue numbers when they differ from standard numbering** (user, 2026-10-11). gxd's 1913
   Wynne puzzle (gxd/nyworld/1913/nyw1913-12-21.xd) carries a `Numbering:` block after its clues: a copy of
   the grid with each numbered square's label, letters standing in for two-digit numbers (`a=10 x=34`).
   It isn't in doc/xd-format.md, and neither xdlint nor crossref reads it; it's the only use in gxd.
   Judge has two puzzles where the printed grid numbers a square that starts no entry, so the printed clue
   numbers run one high (judge1928-09-01, judge1929-03-02). We renumbered them to standard and explained
   it in the note. judge1937-05-01 prints a clue 60 Across with no 60 Across in the grid. To do: agree with
   Saul on a spec'd form (the Numbering block, or a per-clue `^Printed: 29` metadata line, which xd 3.0
   already allows), then keep the printed numbers for these three, and have crossref show them.

## Review site

4. **Republish the ~300 newer Judge puzzles with `--current-review`**, so the page shows each
   one as it stands now (later fixes, notes, sources), not the original agent review.

10. **Circled (and shaded) squares** (user, 2026-10-11). xd marks them with lowercase letters in the grid
   plus a `Special: circle` (or `shaded`) header; xdlint checks the value. Judge's unnumbered "Dirty Work at
   the Crosswords" (Dec 1936, our No. 371) has circled squares. Needs: a way to mark a square circled in the
   review UI (shown on the page, with its source, like everything else), import into the ledger, and the
   pipeline (numbering, lint, packets, export-gxd) keeping lowercase cells as letters.
   **Built 2026-10-11** (blitz branch claude/nice-poincare-b3a6f1, xword-ocr branch circled-squares): ledger
   item `special:r3c5` = "circle" / "shaded" / "" (plain), fix-file `special_cells`; the proof page's answer
   key (or blank grid when there's no key) has "Click a square to: fix it / ◯ circle it / ▒ shade it", draws
   the marks everywhere, and lists every marked square with who marked it. Left: No. 371 itself, once its
   harvest is in (mark its circles on the review page, or `special_cells` in its fix entry).

13. **Proof page nits from reviewing all of Judge** (user, 2026-10-11):
   - Changing a letter in the grid should let you say why right there, at the square, instead of
     scrolling down to the first clue that uses it.
   - Marking something in the header as not important: the "why" prompts don't fit. Offer a
     "not important" choice (or similar).
   - Make the notes field easy to clear or delete. The user cleared it a lot, because notes were full
     of sourcing and OCR details that don't belong in a puzzle's note (they belong in headers like
     Solution-Source, or in the change labels). Also stop writing such notes into fix-file `note`s.
   - Hide the circle and shading tools behind something like "show circle/shading controls".
   - Make answers findable with the browser's find (Ctrl+F). Today they're only drawn into the grid
     and the clue rows' images. Print each entry's answer in small text under its row (or beside the
     grid), so searching for TANG lands on the clue it belongs to.

14. **A grid change that reinterprets the page goes back for reprocessing** (user, 2026-10-12).
   When a reviewer finds a grid problem that changes how the rest of the page reads (a smudged
   white square the OCR made black, as in judge1933-10-01b r3c5), they need a way to say so,
   explain it, and send the puzzle back. Today they can't: the proof page can't renumber the
   clues, and the importer refuses a grid fix that leaves clues without squares. So a
   reviewer's correct fix gets dropped. Shape:
   - **On the page:** toggling a square black or white offers "This changes the numbering: send
     back for reprocessing", with a required why ("the scan shows an O; the key has an O").
     The rest of the proof is set aside, not imported half-applied.
   - **On import:** the grid squares go into the ledger as `grid:` records with the reviewer's
     reason. The puzzle is marked "reprocess", not refused.
   - **Reprocessing:** relink applies the squares (fix-file `grid_cells` already re-aligns the
     OCR's clue text to the corrected numbering), the round-trip check runs, and the puzzle gets a
     fresh packet and goes back in the queue. The reviewer's note shows on the new page, so the
     next reviewer sees why the grid changed.
   - **Agents too:** an agent's grid fix that the importer refuses today (No. 297) takes the same
     path.

15. **Retire "sic" for clues; a special review for close calls** (user, 2026-10-12).
   **The decision (after the Judge sic audit):** "sic" was something of a fool's errand for
   clues. Of Judge's 239 sic items, 54 were OCR slips or damaged type that should simply have been
   fixed, 15 were wordplay that should never have been marked, and 13 were misnumbered clues that
   belonged in a note. The rest were trivial printer's typos where the mark added nothing. From now
   on, for clues: **fix it or don't.** Fix typography (bad kerning, a smudged period read as a
   comma, a letter eaten by the scan). Leave odd or wrong text as printed, unannotated
   (`as_printed`). For borderline cases, ask Claude, then a person. Answer keys keep their rule:
   a clearly wrong printed letter is corrected, with a note. To do: drop "sic" from
   publications/REVIEW.md and INSTRUCTIONS.md, the draft.json schema and `blitz finish`'s
   "settled" check; the importer and export keep reading old sic records.
   **Background:**
   While drafting the Judge blog post, many clue texts kept as "sic" turned out to be possibly real,
   uncorrected errors (OCR or transcription, not the printer). The opposite also happened: a
   deliberate pun was "corrected" away. "A bull's enemy. (Financy that!)" became "Fancy that!",
   but it's almost certainly a pun on finance. A Judge audit is running separately. For every
   series:
   - **Sic items** (kept as printed): each gets a second look against the scan. Is it really
     printed that way, and is it really a misprint and not wordplay? If the scan shows the right
     text, it's an error to fix.
   - **Corrections that turn an odd word into a common one:** each gets a second look for
     wordplay (puns, dialect, deliberate misspellings like Judge's "gnumber", "Efternoon",
     "Driv-It-Ur-Self"). If the print has it, restore it as printed.
   - **Close calls** (a reviewer's "unsure", or two reviewers who disagree): double-checked by
     a second reviewer or a person.
   - **The tool:** a narrow page like the key-squares checker. Each card shows the crop of the
     printed clue, the text as printed, the text we have, and why it was changed or kept, with
     the choices "as printed (wordplay)", "misprint, kept with sic", "OCR error, fix" and
     "typo in print, corrected with a note".

16. **One card format for every narrow check; scripts used twice become commands** (2026-10-12).
   On Judge's last day the same shape was built three times as one-off pages in a scratch
   folder: key squares, the sic audit, and the queue ordering. Two rules:
   - **Cards:** blitz branch `claude/key-squares` (the key-squares page, `flags` / `flag_checks`
     tables) keys a card by square and limits an answer to letters. Generalize it to
     `{xdid, page, item, now, suggest, why, crop, rows}`, where `item` is any ledger key
     (`clue:A14`, `cell:r3c5`, `meta:byline`), the value is free text, and `rows` are the ledger
     rows applied on Accept. Then an audit, an agent or the live site's "flag a mistake" just
     writes cards, and the same page and import handle them. The Judge sic audit
     (judge branch `claude/sic-audit`, `audits/*.rows.jsonl`) is the second user.
   - **Scripts:** a scratch script used a second time moves into a repo as a command with a test.
     First in line: `verify_xd.py` (`xword-ocr verify --against <commit>`: no clue or black-square
     changes slip through), `restore_old_pages.py` (`xword-ocr restore-readings <backup>`), the
     answer word check (part of the checkup and the key-squares flags), and ordering the review
     queue from puzzles.tsv (`blitz site-queue`).

## Elsewhere

5. **crossref: treat `_` as "no square"** (xd's not-part-of-the-puzzle), for the shaped Judge
   grids; gxd's 1913 Wynne diamond already uses it.
