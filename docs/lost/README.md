# Lost puzzles: a gallery of what the web archive didn't keep

Assets for making the preservation case to stakeholders: screenshots of Wayback Machine
captures where the *page* a crossword lived on survived but the *puzzle* did not, with a
one-line diagnosis each. Format-agnostic: a blog post, a one-pager, a pitch deck or an
article can all be built from `exhibits.tsv` and `shots/`.

The argument in one sentence: a web crawler saves HTML; a crossword is data that an app
fetched separately, so "archive.org has it" usually means the shell, not the puzzle, and
the only puzzles that survive are the ones someone saved as files on purpose.

## Failure modes

| code | mode | what the capture looks like |
|---|---|---|
| applet | 1998-2012: Java applet / plugin on the page, grid fetched from a separate file | an empty box, a "Java not available" notice, or a bare "click to start" where the grid was |
| host | 2010-2020: third-party game host in an iframe or JS player (Arkadium, uclick, PuzzleMe) | a spinner, a blank player, or an error; the player's data calls were never crawled |
| purge | the publisher deleted its own archive (Washington Post, early 2024) | the page is gone live; Wayback has the shell of the page but the player inside it is empty |
| blog | indie blogs whose puzzles were .puz/.pdf files on Dropbox, Drive, a lapsed host | the post and its download link are archived; the link is dead and was never captured |
| saved | the contrast: data that survived because it was a plain file, or a scraper got it | a .puz that still downloads from web.archive.org; the xd corpus; xword-dl |

## What the first pass found (2026-11-03)

Twelve screenshots, fifteen rows in `exhibits.tsv`. Tier A rows are the ones to lead with:

- **The one-image argument** is `host-wapo-sunday-html5-2017`: the archived Arkadium player
  rendered its own config as raw JSON, so the capture literally prints the URL of the puzzle
  it wanted (`.../penny-dell/sunday-crossword/puzzle_YYMMDD.xml`), and that URL has zero
  captures.
- **Scale**: `games.washingtonpost.com/games/daily-crossword/` was archived 1,192 times
  (2012-2026). Of the ~1,000+ daily `.jpz` files it loaded, 5 were ever captured.
- **Three generations, one shape**: the 2000 Across Lite applet, the 2013 Flash player and
  the 2015-17 HTML5 player all left the page and lost the puzzle. The technology changed; the
  failure didn't.
- **Blogs**: the Cross Nerd's nine Dropbox links (2013) are dead and uncaptured. Neville
  Fogarty's 2012 Dropbox link is uncaptured but still serves the file. Same capture shape,
  opposite outcome; the archive can't tell you which is which.

Things that cut against the simple story, and belong in the piece as honesty:

- WaPo's 1998-2000 Sunday `.puz` files *were* captured, 138 of them, because they sat at
  plain dated URLs a crawler could follow. The loss there is the gap weeks and the
  "current puzzle" servlet URL. Files at stable URLs survive; app calls don't.
- The Post Puzzler's 2012-13 XML was mostly captured by accident, same vendor as the lost
  Daily and Sunday.
- The Boston Globe's 2019-20 pages server-rendered the whole grid into the HTML (cells
  carry the answer letters), so those captures hold the puzzle. Not an exhibit of loss;
  possibly a "saved" exhibit after a closer look.
- Most of the "data not captured" claims rest on empty CDX queries made while the CDX
  service was flaky (429s and "Temporarily Offline" on 2026-11-03). Each worker ran a
  control query where it could; the confidence column says where it couldn't.

## Still open

- **WaPo purge date.** Not established. Alex recalls about February 2024. CDX shows the
  landing page's last 200 capture at 2023-04-29 and 403s (bot-blocking, not deletion)
  after; `/crossword-puzzles/daily/` still had 200s in Mar 2024 and Jan 2025. Next: view
  the late-2023 and early-2024 captures of the daily page for the archive/date picker;
  check Evan Birnholz's blog and r/crossword for the announcement.
- **Women's History Month 2022**: the landing tile and its URL are confirmed; the page's
  own capture, its PuzzleMe iframe (cdn3.amuselabs.com), and the live response are not.
- **Individual Birnholz Sunday pages (2016-2019)** with the amuselabs iframe: not done.
- **Non-WaPo applet era**: Boston Globe (boston.com), LA Times/TMS, Newsday, uclick:
  queries timed out or returned nothing. Needs one-at-a-time CDX queries, 5-10 s apart.
- **A dead Dropbox `/u/` Public-folder case** (died 2017): none verified yet. Candidates:
  Matt Gaffney 2010-11 contest pages, Ben Tausig's Ink Well.
- **Shots for the `saved` rows**: a CDX listing page or the Wayback calendar for the
  `csserve.cgi?f=...` captures would make the contrast visual.

Method notes for the next pass: WebFetch refuses web.archive.org; use curl. The CDX API
rate-limits after roughly 30 requests in a few minutes. Never claim "uncaptured" from an
empty result without a control query in the same minute. Avoid domain-wide wildcards.
`shoot.py` sometimes exits 0 without writing a PNG on heavy pages; re-run it.

## Files

- `exhibits.tsv`: one row per exhibit (label, mode, publication, URL, Wayback timestamp,
  data URL, data captured?, diagnosis, confidence). The screenshots are reproducible from it.
- `shots/<label>.png`: the screenshot, Wayback toolbar kept as provenance.
- `shoot.py`: `python docs/lost/shoot.py <label> <timestamp|live> <url> [--tall]` re-shoots
  one exhibit with headless Chrome.
