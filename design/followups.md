# Follow-ups

Work agreed on but not started. Take these on once Judge's gxd submission is done.
Newest at the bottom of each section; strike through or delete when done.

## Tools

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

## Review site

4. **Republish the ~300 newer Judge puzzles with `--current-review`**, so the page shows each
   one as it stands now (later fixes, notes, sources), not the original agent review.

## Elsewhere

5. **crossref: treat `_` as "no square"** (xd's not-part-of-the-puzzle), for the shaped Judge
   grids; gxd's 1913 Wynne diamond already uses it.
