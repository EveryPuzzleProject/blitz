# Whole-page test (2026-10-12)

For the "Why not skip the OCR?" paragraph in docs/blog/judge.html. One Claude Fable agent per puzzle got
only the puzzle page and the answer-key page (full archive.org leaves from xword-ocr's cache), read each
image once with no cropping or processing, and wrote an xd. Each run took about 78k tokens and 3 minutes.

    python tools/blog/wholepage/compare.py tools/blog/wholepage/judge1928-04-07.whole-page.xd ../judge/xd/judge1928-04-07.xd

| Puzzle | Squares wrong | Clues exact |
|---|---|---|
| judge1928-04-07 (No. 46, 17x17) | 0 of 289 | 110 of 112 (the other two differ by a period) |
| judge1927-04-30 (New X Word No. 1, 15x15) | 1 of 225: 19A, the key prints YEY; the agent wrote YET | 70 of 74 (punctuation and spacing) |
