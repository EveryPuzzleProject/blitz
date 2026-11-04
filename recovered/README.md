# Washington Post crosswords recovered from the Wayback Machine

Made by [`tools/wayback_puzzleme.py`](../tools/wayback_puzzleme.py). The Post's online crossword
archive is gone, and Wayback *replay* of the PuzzleMe (Amuse Labs) player pages shows "Access
Denied". But the **raw** capture (`web.archive.org/web/<ts>id_/<url>`) still holds the whole puzzle
as a `window.rawc` blob. The script lists captures with CDX (paced, 6 s apart, an empty answer only
trusted after a control query), fetches the raw page, decodes `rawc` with gxd-downloader's Amuse
adapter and converter (used as a library; set `GXD_DOWNLOADER` to its checkout), and writes:

- `manifest.tsv`: id, set, Wayback timestamp, title, author, date, status
- `xd/<set>/<date>_<id>.xd` and `.json` (the decoded payload as served), 2.3 MB for the 21 puzzles
- `cdx/<set>-<year>.tsv`: every capture CDX lists for that set and year (all statuses)
- `raw/`: the fetched pages (6 MB, not committed; rebuilt by `fetch`)

## Found

**Sundays (`wapo-eb`, Evan Birnholz), 2022: 21 of 26 recovered** as `.xd` (21 x 21 grids, clues,
answers). Three spot-checked (2022-01-02, 03-13, 06-26): 21 x 21, 144 to 152 clues, no
conversion warnings. Some captures are dated later than the puzzle (03-20 was captured 03-27,
06-19 on 07-12, 06-26 on 07-19). 2022-03-13 "Clockwork" is by guest constructors Sally Hoelscher
and Mary Lou Guizzo.

Not recovered:
- **2022-03-27**: no capture of `ebirnholz_220327` in CDX.
- **2022-05-22, 05-29, 06-05, 06-12**: captured, but the page's `rawc` is scrambled with a key
  the gxd-downloader `unscramble` search doesn't find (it assumes a 7-digit key of digits 2 to 20).
  The raw pages are in `raw/` (rebuildable); this is a decoder question, not a missing capture.
- `ebirnholz_201227` was captured in Nov 2022 as a picker page with no `rawc`.

**Women's History Month 2022 (`wapo-whm`): none of the puzzles recovered.** The set was three
puzzles: **Golden Girls** (1 Mar), **Mom Genes** (9 Mar), **Credit Report** (16 Mar),
ids `6f50a0b5`, `8fc402eb`, `b86ade92`. Wayback has the *picker* pages for the set
(`cdn1.amuselabs.com/wapo/wp-picker?...set=wapo-whm`, captured 2022-03-05 and 2022-03-19), which
give the titles and dates (now in the manifest as `not-captured`) but no puzzle data. CDX shows no
capture of `crossword?id=<id>&set=wapo-whm` under any host or query I tried (`cdn1` prefix `/wapo/`
and `/pmm/`, `cdn2`, `cdn3`). The set's landing page on washingtonpost.com was captured only as
403/301/302. A domain-wide CDX scan for the ids timed out (504); a retry later could still turn
something up.

## Captures by set and year (CDX, all statuses; `ids200` = distinct puzzle ids with a 200 capture)

| set | 2020 | 2021 | 2022 | 2023 | 2024 |
|---|---|---|---|---|---|
| wapo-eb (Sundays) | 10 | 39 | 27 (26 ids) | 0 | 0 |
| wapo-daily | 1 (a PDF-print URL) | 2 (1 id: `tca210125`) | 0 | 22 (1 id with a 200: `tca230720`; the rest are `test=1` 302s) | 27 (all non-200) |
| wapo-whm | 0 | 0 | 0 (player pages; 4 picker captures) | 0 | 0 |

- Sundays: captures run 2020-10-31 to 2022-07-19 (first to last in CDX), with nothing in 2023 or 2024.
  2020 and 2021 are listed but **not downloaded**; Alex already has the Sundays from Birnholz.
- Dailies (`tca<YYMMDD>`): effectively not captured (a handful of captures, mostly redirects), so
  there is nothing to recover and no downloads were attempted.
- Not looked for: the 2016 to 2019 id scheme.

Searches in this directory only trust CDX when a control query that must hit also succeeds; the
CDX API returned "Temporarily Offline" and 504s at random.
