# Crossword OCR review task

Each folder here is one crossword from a scanned magazine (1920s-1990s). A
pipeline read it with OCR; your job is to check that reading against the scan
and record corrections. Work only from the files in the folder.

## Files
- `ocr.json`: what the OCR read: title, author, byline, captions (text found
  near the grid), the grid (`#` = black square), the answer grid letters (`.` =
  unreadable), low-confidence answer squares, and every clue with any flags.
- `page.jpg`: the whole scanned page, for context. `clue_page.jpg`: the page the
  clues are printed on, when it isn't the grid's page. Each clue in ocr.json has a
  `box` [x0, y0, x1, y1] in pixels of the image named by `clue_image`.
- `grid.png`: the puzzle grid, straightened.
- `answers.png`: the printed answer grid, straightened (if the answers were found).
- `clues_*.png`: each clue's scan crop, labelled with its clue id (A1, D5...): the
  clue's detected region is outlined in orange, with a line of context above and
  below. If the clue's text continues outside the outline, it's still part of the clue.

## What to check (in this order)
1. Answer grid: compare `answers` in ocr.json with answers.png square by
   square. If `grid_asymmetric_squares` lists pairs, the grid isn't symmetric
   there: nearly always a misread black square, so check those first (some
   themed grids really are asymmetric; say so in the note). Rows are numbered from 1 at the top, columns from 1 at the left.
2. Clues: compare each clue's text with its crop. Common OCR faults: misread
   letters (rn/m, l/I, e/c), text belonging to the previous or next clue,
   leftover clue numbers, lost words at line breaks.
3. Captions: text in `captions` that belongs to another puzzle, an answer page,
   or an ad is not part of this puzzle.
4. Title and byline: as printed. Author: the name alone, without "Mr.", "Miss" or "Ms."
   (the byline keeps them), but keep "Mrs.": "Mrs. Arthur B. Kelley" is not Arthur B. Kelley.

Use the answers as a cross-check: each clue's answer must fit its clue.

## What matters most
1. The grid: black squares and answer letters.
2. The words of each clue, and whether any clue text is missing or belongs to another clue.
   Clue lists often wrap: when the last numbers of a list seem to be missing, look at the top
   of the next column (or the next page) before deciding a clue wasn't printed.
3. Title, author and byline, exactly as printed (these are easy to skip; don't).
4. Punctuation, dashes, spacing and underscores matter least: fix them when sure, and if
   that's your only doubt about an item, say "punctuation".

## Output: write `review.json` in the puzzle's folder
```json
{
  "ready": true or false,               (with your corrections applied, is the puzzle ready to
                                        publish as is: grid, answers, every clue, title and byline?)
  "remaining": "none", "minor", "major" or "blocker",
                                       (what's left after your corrections: "minor" = small doubts
                                        that don't matter much; "major" = a person must look; "blocker"
                                        = can't be published as is, e.g. no answers, a clue missing
                                        from the page, an answer key that isn't this puzzle's)
  "remaining_note": "one line on what's left, if anything",
  "note": "anything else a person should know (a meta, shaded squares, an oddity of this puzzle)",
  "corrections": {
    "cell:r3c5": "E",                  (answer-grid letter; "#" for a black square)
    "grid:r3c5": "#",                  (puzzle-grid square: "#" black, "." white; for
                                        squares the OCR got wrong, e.g. cross-hatched)
    "special:r3c5": "circle",          (a square printed with a circle in it; "shaded" for a shaded
                                        square; "" if a square shown as marked isn't. Look at grid:all)
    "clue:A14": "full corrected clue text",
    "clue:A26": "",                    ("" = this clue number doesn't exist; if you fix the
                                        grid, key clues by the corrected grid's numbering)
    "other:2": "",                     (captions are numbered from 1; "" removes one; a number past the last adds one)
    "meta:title": "corrected title",
    "meta:author": "the name alone",   (also "meta:byline", "meta:puzzle_number")
  },
  "as_printed": {"D51": "Soury: a pun"}, (odd words printed so on purpose: names, puns, dialect, a
                                        gimmick; or a close call for a person to decide)
  "regions": {"clue:A64": [x0, y0, x1, y1]},  (only if a clue's "box" misses part of its printed
                                        text: the corrected box, in pixels of the clue image)
  "confirm": ["clue:A7", "cell:r2c3"],   (flagged or low-confidence items you checked and found correct)
  "unsure": {"clue:D22": "words"}       (items you could not read with confidence, and what kind of
                                        doubt: "grid", "letters", "words", "cut off", or "punctuation")
}
```
Style: dashes as an em dash (—); a word hyphenated only because of a line
break is joined as it's normally written; the magazine's recurring notices
(e.g. "Judge will run a Crossword Puzzle every week and will pay $25...") are
not part of the puzzle: remove them from captions.

Here the text is faithful to the page: you make it match what was printed.
Three cases, and only the first is a change to a clue's text:

1. **A reading fix.** A correction is for an OCR misreading (the scan shows
   something different from the text) and for damaged type: letters the press
   printed broken, faint or partly missing ("quarre!" for quarrel, "shel!",
   "wal's" for walls; an e whose bar didn't print looks like an o or c, as in
   "highor"), a stray space or a missing one ("fan ier", "highor der"), and
   ink specks read as accents or punctuation ("aré"). Say what the scan shows.
2. **A printer's typo in a clue or a header is not corrected here.** A wrong,
   extra or missing letter set cleanly in type ("cockail" for cocktail,
   "Tumeric", "tresspassing", "Tbis") stays as printed. Say so in `note`
   ("D1 is printed 'cockail'; 'cocktail' was meant"): that is a proposal. The
   corpus's text is the puzzle as the publisher meant it (its rule,
   EDITORIAL.md: obvious mistakes are corrected to what was meant), so the
   correction is made when the puzzle is exported to the corpus, with a note
   saying what was printed. If the text already has the word meant and the
   scan shows the typo, put the text back as printed and say the same.
3. **A misprinted letter in the answer key is corrected here, and noted**
   (the paragraph on the answer key, below).

What the publisher did on purpose stays. Puzzles have gimmicks (missing or
extra letters, pun spellings, several letters in one square, dialect), so an
odd spelling may be the point: check whether the answer grid only works with
it, keep it, and list it under "as_printed" with why ("Soury: a pun"). When
you can't tell a typo from wordplay, keep it as printed under "as_printed",
say it's a close call, and a person decides.

The answer key is evidence for the answers rather than part of the
puzzle. When a letter in the printed key is plainly a misprint (the clue and the crossing words
both call for another letter, and anyone solving the puzzle would agree: TANG, not TAHG), correct
the square to the right letter and say so in the note, in this form: "The solution grid that
ran on September 8, 1928 printed 1 Down as TAHG. It has been corrected to TANG." If the puzzle's
gimmick needs the odd letter, keep it.

Only correct what you can see in the scan. Keep the original spelling and
punctuation where they are what the publisher meant; don't modernize or
improve anything. If something can't be read, list it under "unsure" rather
than guess.
