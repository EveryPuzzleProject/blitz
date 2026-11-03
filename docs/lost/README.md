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

Twelve screenshots, fifteen rows in `exhibits.tsv` (the second pass, below, added six rows
and five shots). Tier A rows are the ones to lead with:

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

## Second pass (same day)

Six more rows, 17 shots in all. What changed:

- **A second newspaper.** `host-uclick-globe-2004`: boston.com's daily crossword, a uclick
  Flash player. 921 captures of the page; 5 per-day data files ever. Wayback now runs a
  Flash emulator (Ruffle) on the archived player, so the archive went to the trouble of
  making the player work, and it has nothing to show.
- **The Women's History Month page** (`purge-wapo-whm-2022`): captured, with its text
  ("Click Print at the top of the puzzle board") and a blank where the board was.
- **Saved, but invisible** (`saved-wapo-birnholz-2022-raw`): every 2022 Birnholz Sunday
  through June has a capture of its PuzzleMe player page with the whole puzzle inside, as
  a base64 blob. Replay shows "Access Denied", so to a visitor it looks lost. It is
  recoverable only by fetching the raw capture and decoding it, which is exactly what an
  app-aware downloader does on the live site. This is the sharpest exhibit of the lot and
  a recovery lead: see "Still open".
- **The Post Puzzler correction**: the Wayback URL listing shows 135 captured files under
  that prefix, through 2013 and beyond, not "about 20". `saved-wapo-puzzler-2012` is now
  tier A: same vendor, same URL scheme as the lost Daily and Sunday beside it; one
  directory got crawled and the others didn't.
- **No Dropbox `/u/` case exists** among the blogs that matter: Dropbox stopped issuing
  Public folders in late 2012, and the indie puzzle blogs started after that. They all used
  `/s/` share links, which die unpredictably (Cross Nerd dead, Fogarty alive). Closed.
- **The "last five Sundays" picker is not a purge.** `limit=5` on the Birnholz picker is
  in the 2018 capture; `limit=14` on the daily picker is in a 2020 one. Whatever happened
  to the archive happened on the vendor (PuzzleMe) side, not in the Post's page HTML.

## Still open

- **WaPo purge date.** Still not established. Alex recalls about February 2024. The Post's
  pages carry no notice and the pickers didn't change. Next test: CDX on
  `cdn1.amuselabs.com/wapo/crossword?id=ebirnholz_*` by year and see when the stream of
  captures stops, and whether the live player still serves a 2022 id. Evan Birnholz's own
  posts (devilcross.com, Bluesky) were not searched directly.
- **Recovery lead.** If the 2022 Sunday captures decode cleanly (`rawc` → base64 → JSON),
  the same may hold for the dailies (`tca220306`-style ids in the wp-picker captures) and
  for the WHM set, whose picker capture names three ids that 404 in replay but may exist
  as raw captures under a different timestamp. This is a scraping job, not a gallery job.
- **2016-2019 Birnholz Sundays**: the id scheme for those years is unknown, so nothing is
  verified either way. The biggest open question for "what is actually lost".
- **Newsday (brainsonly.com, 2004 captures exist) and the Onion AV Club
  (avclub.com/crossword/ has 200s from 2009)**: untried leads for more non-WaPo exhibits.
- **The 1998-2000 Sunday gap weeks** (08-13 to 08-27 and others): a precise list of which
  dates are missing would make the "files at stable URLs survive, except where the crawler
  didn't visit" point exact.

Method notes: WebFetch refuses web.archive.org; use `curl --compressed` (WaPo HTML comes
back gzipped). The CDX API rate-limits after roughly 30 requests in a few minutes and
returns "Temporarily Offline" pages at random; never claim "uncaptured" from an empty
result without a control query in the same minute, and never from a wildcard query.
The `archive.org/wayback/available` API returns empty for URLs CDX confirms, so don't use
it for absence. Blogger "dynamic views" blogs hide post bodies; fetch
`/feeds/posts/default` with the `id_` flag instead. `shoot.py` sometimes exits 0 without
writing a PNG on heavy pages; re-run it. The Wayback URL listing page
(`web.archive.org/web/*/<prefix>*`) shoots well with `live` and `--tall`.

## Files

- `exhibits.tsv`: one row per exhibit (label, mode, publication, URL, Wayback timestamp,
  data URL, data captured?, diagnosis, confidence). The screenshots are reproducible from it.
- `shots/<label>.png`: the screenshot, Wayback toolbar kept as provenance.
- `shoot.py`: `python docs/lost/shoot.py <label> <timestamp|live> <url> [--tall]` re-shoots
  one exhibit with headless Chrome.
