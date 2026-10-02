# Every Puzzle Project: puzzle review

**Have Claude usage left before your weekly reset? Spend it restoring
crosswords that haven't been solved in nearly a hundred years.**

## The goal

Crosswords have been printed since 1913, but most from before the 1940s
survive only as pictures: page scans of old magazines and newspapers. You
can look at them, but you can't search them, count them, or compare them.

The Every Puzzle Project is turning those scans into
[xd](https://github.com/century-arcade/xd), a plain-text crossword format
with the grid, every clue and answer, the title, the author and the date. In
xd, a 1929 puzzle sits in the same open archive as modern ones and can be
searched and analyzed with them. You can ask which words were crossword
staples a century ago, how cluing changed, or who the forgotten constructors
were. Many of them were readers who mailed puzzles in. Analysis of the xd
archive has already turned up a major crossword plagiarism case.

## What's done, and what's left

**Done, by machine.** We found the puzzles in scanned magazines, cut out
each grid, clue list and answer key, and read them all with OCR. The answer
keys were often printed weeks later in another issue. Every puzzle now has a
first-draft transcription.

**Left: checking it against the scan.** OCR is close but not right. It
reads `rn` as `m`, misses a black square, drops a clue's last word at a line
break, or picks up a stray caption from the next column. One error is enough
to ruin a crossword, and there are hundreds of puzzles to check. This is
the step your Claude does.

For each puzzle, your Claude:
- looks at the scan crops of the grid, every clue and the answer key,
- compares them, square by square and clue by clue, with the OCR's reading,
- writes down each correction, and keeps the printed misprints as printed
  (we restore what was published, not what was meant),
- says whether the puzzle is ready or what a person still needs to look at.

The result is one small JSON file per puzzle. A person spot-checks before
anything goes into the archive.

## How to help

You need [Claude Code](https://claude.com/claude-code) and a GitHub account.
In an empty folder, start Claude Code and paste:

> Help the Every Puzzle Project restore old crosswords. Follow
> https://github.com/EveryPuzzleProject/puzzle-review/blob/main/VOLUNTEER.md
> and review **3** puzzles.

Change the 3 to whatever you like. Claude will:

1. Set up the GitHub CLI if you don't have it, and fork this repository.
2. Claim the next puzzles nobody is working on, by opening a draft pull
   request.
3. Download each puzzle's scan crops (about 3 MB) and review them, a few at
   a time.
4. Push each review to your pull request as it finishes, and give you a
   link to **solve the puzzle you just restored**.

**What it costs.** About 80k tokens a puzzle, nearly all of it Claude
reading images. If you're not sure how that compares to your plan, do 1 and
watch how far your usage meter moves. The strongest model you have does the
best job, but any recent Claude helps.

**You can stop any time.** Every finished puzzle has already been sent, so
stopping Claude, or running into your usage limit, wastes nothing. Puzzles
you claimed but didn't finish go back to the pool after 48 hours.

**What it touches.** A folder on your machine with this repository and the
puzzle images, a fork in your GitHub account, and one pull request here.
Nothing else.

## What you get

- A link to solve each puzzle you restored, right in your browser: the grid
  and clues as printed in 1929 or 1930, with a check button.
- Your name on the [contributors list](https://everypuzzleproject.github.io/puzzle-review/)
  once your pull request is merged.
- Knowing these puzzles are searchable again.

## Publications

Volunteers work through these in order:

| Publication | Years | Notes |
|---|---|---|
| [*Judge*](publications/judge/) | 1924–1939 | A humor magazine with a weekly crossword from 1924. 1929–30 open now. |

## Layout

- `VOLUNTEER.md`: the procedure Claude follows.
- `publications/<pub>/INSTRUCTIONS.md`: how to review that publication's puzzles.
- `publications/<pub>/puzzles.tsv`: every puzzle and where its packet is.
- `publications/<pub>/reviews/<puzzle>/`: the OCR reading (`ocr.json`) and the review (`review.json`).
- Puzzle packets (scan crops) are release assets, not in the repository.
- `docs/`: the website, including the solver.
