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

## Shipping

`blitz ship <pub> --proof <the hand-packets folder> --batch <name>` ships a hand-read batch as any other:
the same ship rule, helpers' decisions from the site, the record of every edit, `xd/<xdid>.xd`. What differs:

- **The ship check is recorded by hand-packets.** A hand-read batch has no harvest, so `hand-packets`
  writes `triage.json` in the packets' folder (ship reads it there when the harvest has none): every
  puzzle ready for review, and `handread.ship_check` of its xd, in xword-ocr's shape. It holds a puzzle
  on an unsolved grid (`?` squares: No. 3 has no key; a reviewer's letters for every square fill it), a
  clue naming no run, or an answer that isn't the grid's letters. A run with no clue line, or a clue line
  with no text, is what FUN printed (the reader's `worldxd.py check` passes it too): a finding the
  reviewer sees, not a hold. In the World's own form, each clue no run can name is said (`clue-off-grid`).
- **The xd's own sections.** ship reads the hand-read xd through `ship.unsection`: its Metadata, Grid and
  Clues as the blank-line form the rest of ship reads, and back into the file's sections when it ships,
  every other line (Design, Labels, `^Printed:`) as it was. `_` is outside the puzzle, so a changed key
  square changes the answers of the right words. A note ship adds after the clues (a corrected key
  letter's) goes in a `## Notes` section at the end.
- **The World's own form.** A clue the proof page showed on a run (`ocr.json` clues, `printed`: its pair)
  is edited as that run's clue and written back under its pair. A key square changed in a puzzle with
  clues no run can name holds it (`edits-unapplied`): their answers can't follow the square. So does an
  edit of such a clue (a printed line's text, `line:B<n>`), as for any puzzle that isn't linked-ends.
- **Ids.** A hand-read packet is named by its xdid, and ships under it: nothing is pinned. Where `xd/`
  already has that file from another source (Nos. 11 and 12, shipped from the OCR batch as
  `nyw1914-03-01` and `-03-08`), the puzzle is held as `xd-exists`: which version stands is the owner's call.

Not done: `ship-export` (the gxd export) reads the blank-line form; a hand-read xd in `xd/` isn't
exported until it reads sections too.
