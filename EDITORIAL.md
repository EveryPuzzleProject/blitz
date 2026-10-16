# Editorial conventions: transcribing puzzles from print

How the Every Puzzle Project turns a printed puzzle (a magazine or newspaper
page, a book, a scan of either) into an `.xd` file: what is corrected, what is
kept as printed, and how each decision is recorded.

This covers only the step from print to `.xd`. What a finished `.xd` contains
and how its headers are used, whatever the source, is gxd's
`EDITORIAL.md` (in the gxd repo). Puzzles exported from here follow both.

The operational version, written for reviewers and their agents, is
[publications/REVIEW.md](publications/REVIEW.md). A publication's own quirks
are in its repo's `review-notes.md`. Where this document and REVIEW.md
disagree, the difference is noted below and is being settled.

## The text: as printed

- **Transcribe what was set in type.** Keep the original spelling,
  punctuation and dated usage. Don't modernize or improve anything.
- **Fix accidents of type and transfer**, without comment:
  - OCR misreadings: the scan shows something different from the text.
  - Damaged type: letters printed broken, faint or partly missing ("quarre!"
    for quarrel; an e whose bar didn't print, read as o or c), a stray or
    missing space ("fan ier"), ink specks read as accents or punctuation.
  - A word hyphenated only because of a line break is joined.
- **Wordplay stays.** Puns, dialect and deliberate misspellings are the point
  ("A bull's enemy. (Financy that!)" is a pun on finance; Judge's "gnumber").
  When a correction would turn an odd word into a common one, look at the scan
  again first. If the answer grid only works with the odd spelling, it is
  certainly deliberate.
- **Misprints in clues stay as printed.** A mistake set cleanly in type
  ("Tumeric", "tresspassing") is not corrected.
  - Annotation is changing: REVIEW.md still asks reviewers to record an obvious
    misprint under "sic" with what was meant. After the 2026-10-12 audit (of
    239 Judge "sic" items, 54 were OCR or damaged type, 15 were wordplay, 13
    were misnumbered clues), the decision was to drop "sic" for clues and leave
    the text as printed, unannotated. See `design/followups.md`, item 15.
- **Unreadable text** is marked as unsure, never guessed. An unreadable
  answer square is `.`.
- **Style**: dashes as an em dash (—).

## Headings

- **Title**: the puzzle's own name as printed. Read the whole heading block,
  including large type beside the grid, not just the line above it.
  - A series label ("Crossword Puzzle #2") is not the title when a name is
    printed. Its number goes in Number.
  - A subtitle or tagline goes in the puzzle's note.
  - When no name is printed, the series heading is the title.
- **Byline**: exactly as printed, honorifics included ("Submitted by W. T.
  Litson, Jr., Oceanside, L. I.").
- **Author**: the name alone, without "Mr.", "Miss" or "Ms.", but keep "Mrs.":
  "Mrs. Arthur B. Kelley" is not Arthur B. Kelley.
- **Not part of the puzzle**: the magazine's recurring notices (prize and
  payment offers such as "Judge will run a Crossword Puzzle every week and will
  pay $25..."), advertisements, page furniture. Leave them out.

## The grid and its numbers

- **A printed number on a square that starts no word.** The clues go under
  their own entries with standard numbering, and the note says how the printed
  numbers ran.
- **A printed clue with no entry, or an entry with no printed clue**, is
  recorded in the note.
- **Marks printed in squares** (hatching, pictures, dots) become blocks or
  rebus cells as the puzzle needs, and the note explains how they were read.
- **A deliberately asymmetric grid** is kept as printed.
- **Two grids printed as one puzzle** (Judge No. 6's two faces) are combined
  as the puzzle needs, and the note says how.

## The answer key

The answer key is evidence for the answers; it is not part of the puzzle text.
It usually ran in a later issue.

- **A misprinted key letter is corrected** when the clue and the crossing
  words both call for another letter and anyone solving the puzzle would agree.
  The note says so, in this form: "The solution grid that ran on September 8,
  1928 printed 1 Down as TAHG. It has been corrected to TANG." If the puzzle's
  gimmick needs the odd letter, keep it.
- **A printed solution that doesn't fit its clues**: the grid follows the
  clues and crossings, and the note records what was printed.
- **No key found**: the answer squares are `.`, and the puzzle still goes to
  gxd. The missing key is listed as a gap to fill.

## Where decisions are recorded

- **In the puzzle's note** (and so in the `.xd`): text printed with the
  puzzle (instructions, theme or meta explanations, subtitles) and every change
  to what was printed (key corrections, renumbering, how marked squares were
  read).
- **In the publication's record, not the `.xd`**: where the key ran, who found
  it, OCR caveats, transcription decisions that don't change the text. These
  show on the review page beside the puzzle and go to gxd as provenance, not as
  notes.
- **Nothing hidden.** Every value in the `.xd` is visible on the review page
  with its source ("reviewer added this", "hand fix in the fix file").

## Reprints

A puzzle reprinted elsewhere (Judge's puzzles as "Cross Word Funnies" in 1925
newspapers) is the same puzzle, not a new one. Record each reprint against
the original with how it relates: an identical reprint, a revised reprint
(clues or grid changed), or a partial reprint (part of the puzzle). Note any
reading that differs from the original. A reprint can also supply text the
original's scan is missing.
