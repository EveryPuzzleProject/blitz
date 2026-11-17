# Puzzles read by hand, through the review site (2026-11-17)

Some puzzles never get an OCR draft worth reviewing: the New York World's FUN crosswords Nos. 1-33
(1913-14) were read from the scans by hand instead (Alex's rule for that batch: use what the OCR
gets, don't extend it for the early puzzles' odd designs; newyorkworld `hand-read/README.md`). Each
has an xd and a boxes file that ties every clue and printed line to its box on the page. This is how
such a puzzle goes through the normal review loop.

## The hand-read xd is the starting version

`blitz hand-packets <hand-read dir> --pages <page images> --dest <folder>` writes a proof packet per
puzzle, in the shape `site-publish` and the proof page already take:

| packet file | from |
|---|---|
| `puzzle.xd` | the hand-read xd, byte for byte (its `xd_fp` in review.json) |
| `ocr.json` | the reading every review starts from: the grid's shape, the letters, each clue's text and printed pair (`^Printed:`), its box on the page, every printed line with its box, the xd's headers as `metadata` (shown in the headers table as "read by hand"); `read_by: "read by hand"` names whose reading it is |
| `review.json` | no corrections; the reader's doubts file as a note, each `^Note:` on its clue, each given on its square |
| `page.jpg`, `answer_page.jpg`, `_src/` | the puzzle and solution pages, whole (boxes are in their pixels; scale 1) |
| `grid.png`, `answers.png` | the grid and the key straightened from the lattice the reader recorded (corners TL TR BR BL) |

Nothing is read from the scan here: crops are cut where the boxes file says, every value comes from the
xd. The proof page draws the base round as "Read by hand as …" instead of "OCR read …".

Packets are named by the xdid (`nyw1914-03-08`), not the harvest's pid (`nyw1914-03-08-L000`), so they
never share a name with an OCR batch's packet on the site, in R2 or in the ledger (the retired
`nyw-1914-c1` batch used `-L000`/`-L001` pids for the same Sundays, some for different puzzles).

## The forms

- **Modern numbering with the printed pair** (`A6. … ~ RECEIPT`, `A6 ^Printed: 4-5`, `A6 ^Note: …`):
  the proof page numbers the grid as usual and shows each clue's printed pair as its label. Givens
  (`## Design`, `G { given: true }`) are comments on their squares; the Design section itself shows
  under "Notes in the xd file".
- **The World's own form, as a meta** (`Numbering: as-printed`, `## Labels`, `1-3. …`; Nos. 13, 18, 27):
  the printed numbers go on the blank grid (`square_numbers` from Labels), and each clue whose two end
  squares bound an across or down run is shown on that run. A clue no run can name (No. 18's diagonals,
  No. 13's inner star, No. 27's words run on from FUN) is a printed line of its own, with its crop,
  pair and answer, so it is seen and checked, but the proof page can't put it on the grid.

## What is not done yet: the import and ship

Helpers' work comes back the usual way (`blitz sync` / `site-import`, then xword-ocr `import-reviews`
into the publication's `fixes/`, keyed by the xdid). `blitz ship` already applies reviewers' edits to
the packet's own `puzzle.xd`, which here is the hand-read file, so the hand-read xd stays the version
the edits apply against. Two gaps before a hand-read batch can ship:

1. `ship.apply_edits` reads gxd's blank-line form (headers, grid, clues split by two blank lines); the
   hand-read files use `## Metadata` / `## Grid` / `## Clues` sections, `^Printed:` metadata and Design.
   It needs that form, including writing an edited clue back under its pair label for the three metas.
2. `ship` reads a harvest's triage record for each puzzle; a hand-read batch has none. Its ship check
   for these would be `worldxd.py check` (newyorkworld), recorded the same way.

Until then the batch can be reviewed (Ready / Not ready, edits, comments, all kept on the site and in
the ledger), and nothing ships.
