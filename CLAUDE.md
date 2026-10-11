# blitz: notes for Claude

## The goal: a correct xd file, with its proof visible

Every puzzle the project produces is an xd file that should be correct, and the evidence
for it is the OCR, the reviewers' changes and comments, and the original scans. The review
page (src/blitz/proof.html, live at blitz.xwordapp.com/review/) is meant to be read as a
proxy for the xd file: everything in the xd must be visible there, with its proof.

- **No hidden data.** If a value is in the xd, the page must show it: title, author,
  byline, every clue, every answer, black squares, and the puzzle's notes. A value added
  along the way is fine, but the page must say where it came from (which reviewer, a hand
  fix, a typed grid, a pipeline repair).
- **When there's no straightened image** (a grid typed by hand), show the scanned page
  beside our grid rather than nothing.
- **Decisions are notes**, shown on the page and kept in the xd (e.g. "two grids stacked
  here to keep the printed numbering").

Publishing reviewed puzzles to the site: build their packets with xword-ocr's
`task-packets --current-review`, then `blitz site-publish`.

## Where things are

- How the repos fit together and what's next: design/restructure.md.
- The maintainer's loop: MAINTAINING.md. Volunteers: VOLUNTEER.md, HAND.md.
- Each publication's data lives in its own repo beside this one (../judge, ../games).
