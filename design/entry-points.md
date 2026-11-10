# Entry points: where a visitor lands, and what each page is for

Recorded 2026-11-06, the day the project's web presence was rebuilt top-down.

## The problem

Until November 2026 blitz was the project's default entry point. blitz.xwordapp.com carried
the mission statement, the progress board, the blog and the volunteer pitch, under a tagline
("Bringing old crosswords back") that framed the project as replay rather than preservation.
everypuzzleproject.org, the domain the organisation is named for, was a redirect to it. A
visitor who found the project through its name arrived at a review tool and had to work out
what the project was from there; a visitor who found a blog post could not tell which site
they were on. The catalog and the publication status pages were separate repos with their own
looks, and nothing linked them into one chain.

## The chain

The project is a chain, and the sites follow it:

1. **Find.** The Crossword Census: every publication known to have printed a crossword, and
   a count of how many there are. https://everypuzzleproject.org/census/ (repo `census`).
2. **Index.** One repo per publication, each with a status page under the domain: which puzzles
   exist, which we have a copy of, which pages are still wanted. `/judge/`, `/bostonglobe/`,
   `/newyorkworld/`, `/bell/`, `/games/`, `/collegian/`.
3. **Transcribe and check.** Blitz: OCR built for the project drafts each puzzle from its scan;
   people and their Claude check it against the page. https://blitz.xwordapp.com (this repo).
4. **The corpus.** Checked puzzles join the xd Crossword Corpus
   (github.com/century-arcade/xdcorpus), browsed at crosswordreference.com.

## What each page is for

| Page | Purpose | Repo |
|---|---|---|
| everypuzzleproject.org | The front door: the mission, the chain, the publications board (one card per publication, live counts), ways to help, the newest posts. | `everypuzzleproject.github.io` |
| /census/ | The census: publications, counts, what is in the corpus, what is a lead. | `census` |
| /<publication>/ | The publication's status page: its puzzles, their states, the pages wanted. | `<publication>` |
| /blog/ | The project's writing: one HTML file per post, newest first in the index. Moved here from blitz on 2026-11-06. | `everypuzzleproject.github.io` |
| blitz.xwordapp.com | The review tool's page: what blitz is, the two ways in (the review site; directing your Claude), what is open for review now, contributors. | `blitz` |
| blitz.xwordapp.com/review/ | The review site: the proof page, Browse, the batch page. Where a person checks a puzzle. | `blitz` |
| blitz.xwordapp.com/view.html | One restored puzzle's record (metadata and the review's provenance). | `blitz` |

## The registry and the shared header

**`publications.json`** in the org site repo is the registry: one entry per publication with its
years, repo, status page, and which public TSV gives its counts and how to read it (column,
states, kinds). The home page's board is drawn from it. Blitz's home page reads the same
registry and shows a tile board for every publication whose repo has a blitz `puzzles.tsv`
(an `xdid` and a `state` a row); so a publication appears on blitz's page as soon as the blitz
tools sync it, with no list to edit in two places. Only metadata is ever shown: dates, counts,
states. Never clues or grids.

**The shared header** is the contract that makes the sites one family. Every page under the
domain, and blitz's home page, loads `https://everypuzzleproject.org/site.css` and starts with

```html
<header class="epp-header"><div class="wrap">
  <a href="https://everypuzzleproject.org/">Every Puzzle Project</a>
  <span class="epp-page">Page name</span>
  <nav>…optional links…</nav>
</div></header>
```

which reads "Every Puzzle Project · *Page name*" and links home. `site.css` also carries the
palette (the same one as blitz's `style.css`), `.wrap`, `h1`, `h2` and a dark scheme that follows
the system preference. The org site's README documents it.

## Copy rules

- Preservation and discoverability first: preserving, archiving, saving. Never "bringing back",
  never "playable". The headline is "Preserving every crossword ever printed".
- The headline is the goal; the text under it says how we work toward it. The census counts
  every publication that printed a crossword. The collection preserves whole runs, one at a
  time, finishes each series it starts, and lists the issues it can't find as missing, with
  the date. Which series come next is in blitz's README, "How we work toward it". Don't promise
  every puzzle in any other words; "every" about puzzles is for a finished run ("every crossword
  in *Judge* from 1924 to 1939"). The survey behind this rule: [priorities-review.md](priorities-review.md).
- The corpus is "the xd Crossword Corpus". Only the word "xd" is linked, to
  https://github.com/century-arcade/xdformat.
- Volunteers "contribute by directing their Claude"; the prompt lives in blitz's README under
  "How to help".
- Public pages show metadata only: dates, counts, states, titles, bylines. Never clues or grids.
- Blog posts have no byline (the project is the author) and no "I".
- Public-domain images only on anything shared as an image (social cards, post illustrations):
  Judge pages before 1931 are fine; nothing from GAMES, nothing from Newspapers.com.

## What landed on 2026-11-06

- The home page at everypuzzleproject.org (replacing the redirect): mission, chain, board,
  ways to help; `publications.json`; `site.css` with the header; the README.
- The org profile README on GitHub, rewritten to match.
- GAMES and Collegian status pages; the shared header on all six status pages.
- The catalog reframed as a census (131 publications; the Library of Congress denominator;
  "In the corpus" column) and its page at /catalog/; renamed to the Crossword Census
  (repo `census`, page at /census/) on 2026-11-07.
- Five blog posts: Judge, Pelham, Collegian, GAMES, New York World.
- The blog moved under the domain (/blog/); blitz's old post URLs redirect there (meta refresh
  plus canonical). Blitz's home page became the review tool's page, with the header, the two
  ways in and a registry-driven board; the old tagline is gone from the page, the Open Graph
  tags and both social cards (`tools/social_card.py` here, `img/social_card.py` in the org site).

## Deliberately left

- Seeding the census from the Editor & Publisher yearbooks and Syndicate Directory
  (`universe/ep-crossword-features.csv`): the next big source of papers that carried
  syndicated puzzles.
- The "gxd" wording in the census's research notes, people/ and bylines/README.md (the README
  and the table were cleaned; the rest still says gxd where it means the corpus).
- Retiring the images under blitz.xwordapp.com/blog/img/. External links may point at them, so
  the folder stays for a few weeks after the move; then it goes, and the blog image scripts in
  `tools/blog/` move to the org site repo with it.
