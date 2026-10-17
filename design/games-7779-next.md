# GAMES 1977–79: where it stands and what's next

Written 2026-10-17, at the end of the session that put GAMES 1977–79 through the v2 pipeline.
The goal is unchanged: every puzzle from hands-off assembly to an xd file in the games repo,
nearly hands off, with tokens spent only where they buy the most.

## Where it stands

- **81 puzzles** (the 75 from the box review plus 6 extras) went through assembly, the text
  step and proof packets, and are live on the review site:
  https://blitz.xwordapp.com/review/ (batch `games-1977-79`, provisional ids such as
  `games1977-09-01-L026`). Packets: `xword-ocr/harvests/games-7779/proof/run4`; text step
  answers: `harvests/games-7779/textstep/run4-7779`.
- **The text step** (Fable agent `xword-text`) now reads the lines printed near the puzzle
  (L1, L2, …), says which line each xd header comes from, labels the other lines, corrects
  their text, tags fill-in blanks (kept as printed), and writes a one-sentence verdict only when
  something is notable. Headers come from the lines by fixed rules (`xword_ocr/headers.py`,
  mirrored in `src/blitz/proof.html`). Cost of the full re-run: about 630k tokens, the weekly
  Fable meter 9% → 15%; about 7.8k tokens per puzzle.
- **The proof page** shows the xd's headers in a fixed order with their evidence (crop → OCR
  text → value, the rule named when it changed the text), the other printed lines with Keep /
  Discard and a label, the text step's verdict, a linked list of what it did, a navigation rail
  of edits and doubts, and FITB pills for fill-in blanks.
- **Merged:** xword-ocr #15–#17; blitz #10–#13; games #4–#6. `games/editorial.md` holds GAMES's
  conventions (blanks, picture clues, headings).
- **Nothing is in `games/xd/` yet.** No puzzle has been reviewed on the site.

## Next steps, in order

1. **Triage each puzzle.** After the text step, give every puzzle a decision: *ship as is*,
   *glance*, *needs a person*, *not a crossword*, with reasons in plain words, from what the
   pipeline already records (missing clues, list/page requests, key letters the verdict calls
   misread, unread key, typed header values, unsure items). Separate **accepted gaps**, which
   ship labelled as missing (a cryptic with no printed key, no printed title, the second
   "Easy" clue set), from **defects**, which need a person. A first pass gave 21 ship /
   23 glance / 33 needs a person / 4 not a crossword; "needs a person" is still inflated
   (warmup cryptics counted as missing keys; key misreads that are a few squares for the
   key-squares page, not a full review).
2. **Batch review page.** Prototype: https://claude.ai/artifact/WpFkspcnz9HXNSzNLAZtyN. One row
   per puzzle, worst first: grid, title, decision, reasons, verdict, the "not sure" items each
   linked into the proof page (`?k=clue:A68`), and Ship / Hold / Drop with "ship all ship-as-is".
   Make it real: choices saved where the import reads them (the games ledger or the site's
   database), on the live site.
3. **Settle the Notes rule** before the first export: which line labels go in gxd's Notes
   (instructions, test-solver, intro, credit, kind). Show its effect across the batch first.
4. **Import.** Shipped puzzles become xd files in `games/xd`, ids assigned last, including
   edits from the proof page (`site-import`; keys `clue:*`, `line:Bn`, `ev:<field>`, `keep:Bn`,
   `label:Bn`, `meta:<field>`, `fitb:<clue>`). Picture-clue drawings (`pictures/<clue>.png`)
   travel with the puzzle, unused until xd can carry images.
5. **gxd export.** Tagged fill-in blanks → `___`, other long dashes → `--`, curly quotes →
   straight; Notes by the rule from step 3; gaps labelled, never guessed. Mind gxd's standard
   (clean data): "ship" should stay conservative.
6. **Feedback loop.** Problems found later (gxd contributors, crossref's "report a problem")
   come back as flags on the puzzle in the pipeline, not as hand edits.

A follow-up session with a full brief for steps 1–5 was proposed in the Claude desktop app
("GAMES 1977-79: triage, batch review page, xd + gxd export").

## Open tool issues

- The text step's 85 requests (crops, missing pages, "is this a crossword?") aren't routed to
  the games ledger yet (`textstep.route`).
- Two cryptics sharing a page both get the warmup's heading; the 15x15's own heading isn't read.
- A long-dash blank that ends a line ("Walking ——") isn't put back by the reading.
- Long clue lines' crops sometimes stop mid-clue, losing ": 2 wds." tails.
- A title and byline read as one line, followed by a clue-list label ("Hard Clues"), get the
  label glued on; the text step fixes it, the reading should too.
- The giant "World's Most Ornery" puzzles print a second (Easy) clue set that isn't captured.
