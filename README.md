# Every Puzzle Project: puzzle review

**Have Claude usage left before your weekly reset? Donate it to bringing old
crosswords back.**

Thousands of crosswords from the 1920s on survive only as magazine scans.
We've read them with OCR, but OCR makes mistakes: an `rn` read as `m`, a
black square missed, a clue's last word dropped at a line break. Claude is
good at catching those by comparing the reading against the scan. That takes
about 80k tokens a puzzle, which adds up across a few hundred puzzles.

## How to help

You need [Claude Code](https://claude.com/claude-code) and a GitHub account.
In an empty folder, start Claude Code and paste:

> Help the Every Puzzle Project restore old crosswords. Follow
> https://github.com/EveryPuzzleProject/puzzle-review/blob/main/VOLUNTEER.md
> and review **3** puzzles.

Change the 3 to whatever you like. Claude will:

1. Set up the GitHub CLI if you don't have it, and fork this repository.
2. Claim the next few puzzles nobody is working on, by opening a draft pull
   request.
3. Review them, a few at a time. As each one finishes it's pushed to your
   pull request, and you get a link to **solve the puzzle you just
   restored**. It may be the first time anyone has solved it in nearly a
   hundred years.

**You stay in control of what you spend.** About 80k tokens a puzzle, mostly
reading images. Stop Claude whenever you like: every finished puzzle has
already been sent. Running into your usage limit is fine for the same reason.
The strongest model you have does the best job, but any recent Claude helps.

## What happens next

A maintainer merges your pull request and folds the corrections into the
project's puzzle files, which are bound for the public
[gxd crossword archive](https://github.com/century-arcade/xd). Restored
puzzles and progress: https://everypuzzleproject.github.io/puzzle-review/

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
