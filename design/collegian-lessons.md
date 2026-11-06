# What the Collegian harvest built, and where each piece belongs

Written 2026-11-05 from the Daily Collegian run (Mike Shenk's crosswords, Penn State, 1976-81): 920
archive issues settled by a person, 874 puzzle pages located, crop boxes drawn. The tools are prototypes in
`tools/collegian/` (PR #62). This note says where each should end up under the v3 plan in
`restructure.md` (harvest / xword-ocr / blitz views), so a round of UX or a refactor doesn't lose them.

Data: `collegian-scans` (private: records, ephemera) and `collegian` (public index, generated).

## Where each piece goes

| Now | Goes to | Before it moves |
|---|---|---|
| `scan.py` `issues` / `scan` / `prior`: the issue list from the archive's IIIF collection, each page's OCR scored for a crossword's look (Across/Down heads, numbered clue lines, an "answers" line), the page chosen, an era prior for pages the OCR misses | **harvest**, as a source: the same job `sources/ia` does for archive.org (rank pages by the archive's own OCR text), for a Chronicling-America-style IIIF archive with ALTO OCR | make it a source adapter; the era prior becomes a per-publication hint |
| `grids.py`: the grid on each puzzle page (corners, size, black/white cells) from xword-ocr's `detect_grids` | already xword-ocr's detector; the step is **harvest/blitz glue** that records it as a milestone (`grids.jsonl`, with the xword-ocr commit) | keep the record format; it is what the answer-key match will read |
| `scan.py` `boxes` and `clue_box`: a puzzle's box from its detected grid, plus the OCR's clue lines where read, plus typical margins per layout where not | **xword-ocr** (a function beside `layout.find_panel`; that one needs printed rules, newspaper boxes often have none) | developer session with tests; the labelled boxes below are its test set |
| `answers.py`: each puzzle's answer key. Candidate pages from text (pointers, key headings, classifieds, the puzzle's rows read in the OCR, where neighbours' keys were); `detect_grids` on the page and on tiles; a match by 5x5 region hashes; the paper's habit (same issue / next) learned from the neighbours; `/answers` (`answers_view.py`) for the rest | the matcher and the tiling: **xword-ocr** (beside `match_solutions`); candidate pages: **harvest**; `/answers`: **blitz**, as a view | the findings in `collegian-scans/findings.md`; the region-hash index needs tests on another publication's keys |
| The detector's failures (`findings.md` in `collegian-scans`) | **xword-ocr**, as findings with test cases | see below |
| `review.py`: contact sheet (settle which page), confirm sheet (OCR finds, crop labels), second look, `/boxes` (drag a box) | **blitz**, as views | read milestone files only (see "Views never compute") |
| The labelled data: 874 page decisions, ~700 crop labels, 44 hand-placed boxes | xword-ocr's `eval/`: reviewed ground truth for page finding and box finding | agree the format with the tester role |
| `scan.py publish`: the public index generated from the working records | blitz (`blitz export`-style), or the publication repo's tools | |

## Findings for xword-ocr (stage: grid detection, 61e6e0b)

- `detect_grids` finds the main grid on 851 of 874 puzzle pages at first pass; a retry at higher
  resolution fixes 26 of 106 implausible ones. 20 pages still have no grid although the puzzle is plain to
  the eye (1979-09 to 1981-05, mostly two-page spreads, puzzle flush against the right page edge and the scan
  border). Cropping the corner, native resolution, and white or black padding around the page did not help
  (recovered 6 of the 26, then 3 of 81). List in `collegian-scans/findings.md`.
- Grids cut off by the scan (15x14, 15x13 on 1978 p4) and shaded squares ("Morals", 1976-09-15) read as
  asymmetric. They are real features of the pages: the grid result should say "truncated" / "has shading"
  and not look like a failure.
- 36 puzzle pages carry a second small grid with letters: the previous puzzle's answers on the same page
  (1976-78). `detect_grids` already returns them (`has_letters`).

## Views never compute: what `review.py` must change before it moves

- It imports `scan.py` (manifest, fetch, OCR cache) and computes in the view: the second-look flag, the box
  queue, "has a box", the era guess shown on the contact sheet. Each of those should be a recorded
  milestone value, with the view only drawing it and naming its source.
- Hand decisions are already the right shape: `decisions.jsonl`, `box_fixes.jsonl`, `crop_flags.jsonl`
  (last line per date wins, each with who and when). Keep them as the contract.

## View patterns worth keeping (found by use, not by design)

- **Every item is a history entry** (`#date`, `history.state` holding the trail), so the mouse's back and
  forward buttons are prev/next, redoing a batch works, and a reload keeps your place.
- **Say what happened.** A save shows "Saved 1981-03-17: page 1" and, at the end of a view, a "Nothing more
  to see here" panel. A silent no-op looked like a bug.
- **Never draw the next item's boxes over the previous item's image.** Dim the old image, hide the boxes, say
  "Loading...", draw only after the image has loaded; preload the next few images; scroll to where the puzzle
  probably is, not to the top.
- **Ignore every mouse button but the left while drawing**; swallow thumb buttons mid-drag.
- **Prefetch**, and put the suspect page first.
- **Mark what is wrong, not only what is right**: "bad crop" on the confirm sheet gave a labelled test set
  as a by-product of the review.

## Process lessons

- Look in xword-ocr first (README, module docstrings) before building image analysis. This run spent a long
  stretch on a hand-built grid finder before looking; `detect_grids` found the grid on almost every page in
  0.2 s. (Memory: check-xword-ocr-first.)
- OCR text alone finds a puzzle's page on under half the issues (the byline is a graphic and the grid is
  not text); a position prior by era plus a person's one click per issue settled the rest quickly. Use the
  person where judgement is cheap and the OCR is weak.
- A person's observation of the page found real exceptions no scan would have: the 1978-01-20 reprint stub
  (grid, no clues), the June 1981 help-wanted ad, a themed "Nazism" puzzle. They are recorded in
  `exceptions.tsv` and shown on the review page.

## Order

1. This note, and the findings filed for xword-ocr.
2. xword-ocr developer session: the detector findings and the box function, tested on the labelled boxes.
3. harvest: the archive source adapter.
4. blitz: move the views, reading milestones only.
5. Build the Collegian `pages.tsv` folder (`docs/sources.md` in xword-ocr: page images + `crop_of` crops with
   the archive URL on each) and run the pipeline on it.
