# Reviewing a puzzle, text first

Run every command from the blitz folder. `<puzzle>` is the puzzle's id (judge1931-03-14);
its folder is `../blitz-work/<puzzle>/`. Also read the publication's notes, if any
(`uv run blitz instructions <pub>` prints them: `review-notes.md` in the publication's repo).

You are proofreading the OCR of one crossword from a scanned magazine (1920s-1990s).

## What matters most
1. The grid: black squares and answer letters.
2. The words of each clue, and whether any clue text is missing or belongs to another clue.
   Clue lists often wrap: when the last numbers of a list seem to be missing, look at the top
   of the next column (or the next page) before deciding a clue wasn't printed.
3. Title, author and byline, exactly as printed (these are easy to skip; don't).
4. Punctuation, dashes, spacing and underscores matter least: fix them when sure, and if
   that's your only doubt about an item, say "punctuation".

Title and byline: as printed. Author: the name alone, without "Mr.", "Miss" or "Ms." (the byline keeps them), but keep "Mrs.": "Mrs. Arthur B. Kelley" is not Arthur B. Kelley.

Style: dashes as an em dash (—); a word hyphenated only because of a line
break is joined as it's normally written; the magazine's recurring notices
(e.g. "Judge will run a Crossword Puzzle every week and will pay $25...") are
not part of the puzzle: remove them from captions. Everything else exactly as
printed, misprints included; record an obvious misprint under "sic" with what
was meant ("cockail" -> "cocktail") rather than correcting it.

A correction is for an OCR misreading (the scan shows something different
from the text) and for damaged type: letters the press printed broken, faint
or partly missing ("quarre!" for quarrel, "shel!", "wal's" for walls; an e
whose bar didn't print looks like an o or c, as in "highor"), a stray space
or a missing one ("fan ier", "highor der"), and ink specks read as accents
or punctuation ("aré"). Transcribe what was set in type. "sic" is only for a
mistake set cleanly in type: a wrong, extra or missing letter in sharp print
("Tumeric", "Treelees", "tresspassing", "Tbis"). If the scan shows a word
cleanly spelled that way, it is never a correction, however wrong it looks.
Puzzles have gimmicks (missing or
extra letters, pun spellings, several letters in one square), so an odd
spelling may be the point: check whether the answer grid only works with it,
and say so in "sic" or the note. Never "fix" what is printed.

Only correct what you can see in the scan. Transcribe exactly as printed,
including the original spelling and punctuation. Don't modernize or improve
anything. If something can't be read, list it under "unsure" rather than guess.


## How to review a puzzle folder (text first)
Work through the steps in order, one puzzle at a time, and use as few tool calls as you can:
every call re-reads the whole conversation.

1. **Read `text.md`** in the puzzle's folder: title, byline, captions, the answer key, every clue
   beside its answer, words marked "odd" (not plausible English) and structural checks. Don't
   open ocr.json or any image in the folder.
2. **Decide what to check.** List what a proofreader would stop at: answer words that aren't
   words or need another letter to fit their clue (an I where an A, E, T or L belongs is the
   commonest misread), clue text that looks garbled, doesn't fit its answer, stops mid-sentence
   or seems to contain the next clue. Odd words, flagged clues, unsure letters, the title,
   byline and captions are added for you. If the problem is the whole puzzle (structural checks,
   a run of answers that don't fit their clues, clue numbers that don't follow the grid, a clue
   list that seems to continue elsewhere), first see whether one look settles it: a box: crop of
   a whole clue column shows every printed number and clue at once, and a list shifted by one is
   then just a set of clue corrections. Escalate (step 4) only what that can't settle.
3. **Make the contact sheets in one call** and read all of them (several Read calls in one
   turn is fine):

       uv run blitz sheets <puzzle> clue:A14 entry:D3 cell:r5c7 ...

   Crop targets you can ask for:
   - clue:A14  the clue's printed text, with a line above and below
   - entry:A14  that answer in the printed answer key
   - cell:r5c7  a square of the answer key and its neighbours; row:5 and col:7 for a whole row or column
   - grid:r5c7  the empty puzzle grid around a square (black squares); grid:all and cell:all for the whole
     grid or answer key
   - box:x0,y0,x1,y1  any region, in the same pixels as the clue boxes listed with the text; use it when a
     clue's text runs past its box (e.g. widen it by a line or two) or to see where a list continues
   - next:x0,y0,x1,y1  the same on continued_page.jpg, when text.md has "Clues on the next page" (the list
     goes on to another page of the issue; those clues are marked [next page] and their boxes are in that
     page's pixels)
   - meta:top  the band across the whole top of the page, down to just below the title; text.md says
     "[suspect: ...]" beside a title that picked up an ad or the next column's heading, and the band is then
     included for you
   The title, byline and caption crops are always included (the magazine's recurring notice, "Judge pays $10
   for each puzzle printed", is not: `finish` removes it from the captions).
   Each crop is labelled with its target. One more `sheets` call is fine if a crop shows you
   need something else (e.g. a wider box for a clue that runs on); it adds to the sheets you
   have (only the new ones are listed). A clue the OCR never found has no clue: crop; crop its
   place with box: instead, and that counts as having seen it.
4. **Write `draft.json`** in the folder, then run `uv run blitz finish <puzzle>`. It turns
   answer words into square fixes and reports anything it couldn't apply; a correction to
   something that was never on a sheet is not applied, so put it on a sheet first.

```json
{
  "escalate": "",                       (or one line on why the whole puzzle needs a full review)
  "ready": true,                        (with your corrections, ready to publish as is?)
  "remaining": "none",                  ("none", "minor", "major" or "blocker")
  "remaining_note": "",
  "note": "",
  "corrections": {"clue:A14": "full corrected clue text", "grid:r3c5": "#", "other:2": "",
                  "meta:title": "...", "meta:author": "...", "meta:byline": "..."},
  "answers": {"A13": "ROMAN"},          (answer-key words that differ: the whole word as printed)
  "sic": {"D1": "cocktail"},            (misprints kept as printed: clue id -> what was meant)
  "confirm": ["clue:A7"],               (suspects you checked and found right)
  "unsure": {"clue:D22": "words"},      ("grid", "letters", "words", "cut off" or "punctuation")
  "as_printed": {"D51": "Soury: a pun"},  (odd words that are printed so: names, puns, dialect)
  "tool_notes": [{"kind": "heading-in-clue", "target": "clue:D68", "note": "..."}]
}
```

`tool_notes` is how the tools get better: one entry for each thing the tools got wrong or made
hard, in this puzzle (not your corrections themselves). Use one of these kinds when it fits:
"title-from-ad" (title or a clue picked up text from an ad or another column), "heading-in-clue"
(a heading, page number or caption run into a clue), "clue-missing" (a printed clue the OCR
never found), "clue-split" / "clue-merged" / "clue-shifted" (texts on the wrong numbers),
"letters-unreadable" (the key reader missed letters; say which), "byline", "false-flag" (a flag
or check in text.md that was wrong), "crop" (a crop that cut something off or showed the wrong
place), "sheets", "finish", "text-md" or "other". Keep each note to one line. An empty list is
fine.

`finish` lists every clue that still has an odd word after your corrections. Each one must be
settled: corrected, kept under "sic", or listed under "as_printed". "Confirm" doesn't settle an
odd word, because it's easy to confirm a clue for one reason (its text belongs there) and miss a
misread word in it. Settle them and run finish again.

text.md already shows some clues with the junk taken off: a page number ("30") or "Solution of Last Week's
Puzzle" heading (with its garbled repeat) run in at the end of a column's last clue, or a broken clue number read
as a euro sign at the start. The line says what was removed ("tool: removed ..."). Check it on the crop like
anything else; `finish` puts that text in your review unless you give the clue's text yourself (a page number or
heading you leave in is reported). A clue ending in a bare number is flagged but left as it is. A spell flag marked
"(spell-doubt)" changed a word that may be what's printed: the crop decides. "number-cut-off" is the old
"number-missing" where the box merely starts right of the printed number: ignore it.

When you take text out of one clue because it belongs to another (merged clues), check the other
clue's own text too: it has usually been read separately, with its own slips.

Most odd-looking words are OCR misreads, not misprints: if the text says "bundred" and the crop
shows "hundred", correct the clue. Damaged type is corrected too ("quarre!", "shel!", "fan ier":
broken, faint or spaced-out letters). Use "sic" only for a misspelling set cleanly in type.
Never put an answer word in a clue; answer fixes go in "answers". Captions that belong to the
magazine, an ad or another puzzle are removed with "other:N": "".
