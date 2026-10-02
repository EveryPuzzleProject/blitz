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
    "clue:A14": "full corrected clue text",
    "clue:A26": "",                    ("" = this clue number doesn't exist; if you fix the
                                        grid, key clues by the corrected grid's numbering)
    "other:2": "",                     (captions are numbered from 1; "" removes one; a number past the last adds one)
    "meta:title": "corrected title"
  },
  "sic": {"D1": "cocktail"},            (a misprint you kept as printed: clue id -> what was meant;
                                        for a misprinted answer use the answer's clue id)
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
not part of the puzzle: remove them from captions. Everything else exactly as
printed, misprints included; record an obvious misprint under "sic" with what
was meant ("cockail" -> "cocktail") rather than correcting it.

A correction is only for an OCR misreading: the scan shows something
different from the text. If the scan shows a word spelled that way, it is
never a correction, however wrong it looks. Puzzles have gimmicks (missing or
extra letters, pun spellings, several letters in one square), so an odd
spelling may be the point: check whether the answer grid only works with it,
and say so in "sic" or the note. Never "fix" what is printed.

Only correct what you can see in the scan. Transcribe exactly as printed,
including the original spelling and punctuation. Don't modernize or improve
anything. If something can't be read, list it under "unsure" rather than guess.

## About *GAMES*
- *GAMES* (1977 on) printed several puzzles on a page, each in its own ruled
  panel with a title and byline: crosswords next to word games, quizzes and
  logic puzzles. Only this puzzle's text belongs to it. Remove captions from
  the neighbouring panels, and check that every clue is this puzzle's (its
  number fits this grid and its answer fits the answer grid).
- Titles are set in large type above or beside the grid, and the OCR often
  misses them (`title` is empty) or takes the introduction for the title.
  Set `meta:title` to the printed title. Stars after a title (★, ★★, ★★★,
  read by OCR as `*`) are the magazine's difficulty rating, not part of the
  title: leave them out and give the rating in the note ("difficulty ★★").
  An introduction ("For solvers who enjoy crosswords on the challenging
  side...") is a caption, not the title.
- Byline as printed ("by Merl H. Reagle"); the author is the name alone. Some
  early puzzles are signed with initials only ("J.L."): keep them as printed.
- "Answer Drawer, page 61", "Pencilwise continues on page 65" and similar
  page pointers are not part of the puzzle: remove them from captions.
- Answers are printed at the back of the same issue (the "Answer Drawer"),
  many grids side by side. `answers.png` is this puzzle's grid cut from that
  page, sometimes from another scan of the same issue. If it doesn't fit this
  puzzle's grid and clues, it's the wrong key: say so ("blocker").
- Some scans are of copies a reader solved: pencilled letters in the grid,
  ticks or crossings-out next to clues. Ignore all handwriting. Only what was
  printed counts, in both the grid and the clues.
- Clues are numbered without a period ("12 Rolling stone"), and the Down list
  often continues in short columns under the grid. Abbreviation hints are
  part of the clue: keep ": 2 wds.", ": Abbr.", ": Fr." exactly as printed.
- In illustrated crosswords some clues are pictures. A picture clue becomes
  `[picture]`, followed by any letters or words printed in or under the
  picture, exactly as printed (`[picture] S`). In the note, say in a few
  plain words what each picture shows ("A17: a mermaid; A26: a fried egg").
- Not every grid here is a crossword. If this one is a cryptic (clues that
  end in the answer's length, "(7)"), a word search, a logic puzzle or another
  kind of puzzle, set "ready": false, "remaining": "blocker" and start the
  note with "not a crossword:" and what it is. Don't review it further.
