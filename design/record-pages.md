# Puzzle record pages

A public page for every puzzle the project transcribed from print: what was printed, what
we transcribed, and how it was checked. It is the one page The Cross Reference links to
from a puzzle the project transcribed ("See it as printed →"), so it has to be the complete
destination. Built 2026-11-12 (`blitz records`, src/blitz/records.py); the design was
agreed with the maintainer from a preview of nine Judge pages.

## Decisions

- **URL:** `https://everypuzzleproject.org/<pub>/<xdid without the pub prefix>/`, e.g.
  `judge1924-11-01` → `/judge/1924-11-01/`, `judge1924-11-15b` → `/judge/1924-11-15b/`.
  A permalink: crossref and shared links depend on it.
- **The link contract with crossref** is the `record_url` column of `<pub>/gxd-exports.tsv`,
  keyed by `gxd_id`. Crossref must not build the URL itself: gxd ids are numbers
  (`judge-001`), not our dates. `ship.write_exports` writes the column.
- **Hosting:** everypuzzleproject.org, the project's front door (blitz.xwordapp.com is only
  the review tool). The pages are written into the publication repo's Pages build
  (`site/`, `.github/workflows/pages.yml`), beside its status page; the generator lives
  here so every publication shares it.
- **Images** are not on GitHub Pages (about 1 MB of scans a puzzle). They are linked from the
  puzzle's review package on R2 (`package_url`: page.jpg, clue_page.jpg, answers.png). The
  build fetches only each scan's first 64 KB, for its size. r2.dev is rate-limited: give the
  bucket a custom domain and pass it as `--images-base` before the pages are promoted.
  Showing page images is fine, copyrighted publications included (one page in the context
  of the larger project).
- **og:image** is a 1200×630 crop of the printed grid (`og.jpg`, written beside the page).
- **Emphasis, top to bottom:** what was printed (the page, the clue page, the answer key);
  what we transcribed (grid and clues as printed, misprints kept, with the clue page beside
  it: pointing at a clue lights the box the OCR recorded for it, from the packet's
  ocr.json); what was done (found, read by OCR, each reviewer's confirmations and
  corrections with their reasons, hand fixes). The review page and the OCR packet are
  linked low on the page, not led with.
- **Names:** AI reviewers by model; the maintainer as "the project's maintainer" (including
  the review-site account); volunteers unnamed until they opt in.
- **Notes:** the xd's "Printed with puzzle" and "Misprints, kept as printed" paragraphs are
  shown (misprints are also marked on their clue); "OCR review flags" and "Warnings" are
  pipeline bookkeeping, told by the history instead.
- **The grid is drawn black on white** in both themes, like the printed page.

## Not done yet

- R2 custom domain (the maintainer's Cloudflare step), then `--images-base`.
- GAMES and the Globe: same generator once their repos have gxd-exports.tsv rows with
  package_url; check their packages have the same files.
- Stub pages for puzzles known but not found ("help us find it"), linked from the status page.
- Clue boxes come from the packet's OCR boxes; boxes a reviewer redrew
  (judge-scans/region-ocr.json) aren't in the package, so a redrawn clue shows the OCR's box.

## Sketch: a friendlier front for the status pages (not built)

The status pages (everypuzzleproject.org/judge/) open on a long table. A visitor arriving
from a record page or crossref wants the story first:

1. **The story.** Two or three sentences: what Judge was, when its crosswords ran
   (1924–1930s), the first one ("Try this on your cerebellum!"), and what the project did.
   A picture of the first puzzle's printed page (from its record page).
2. **Progress.** One bar: 531 found, N checked, M in the archive, K still being looked
   for, with each number linking to the filtered list.
3. **The run as a calendar.** One small square per issue, a row per year, coloured by
   state; a transcribed puzzle's square is a thumbnail-on-hover link to its record page,
   a missing one links to "help us find it". It shows the run's shape at a glance: the
   weekly years, the monthly years, the gaps.
4. **Highlights.** A few record pages worth a look (the cover puzzle, the JUDGE/HA HA grid,
   Pelham's puzzles), picked by hand in a small TSV.
5. **The full table** behind a "Every puzzle" heading, as now, each id linking to its
   record page (done: tools/render.py links them).
