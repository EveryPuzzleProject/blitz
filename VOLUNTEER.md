# Volunteer run: instructions for Claude

You're helping a person donate Claude usage to the Every Puzzle Project. Old
crossword puzzles were scanned and read by OCR. You will check some of those
readings against the scans and send the results back as a pull request. Work
through the steps below in order. Keep the person informed in short, friendly
lines; they're watching.

Repository: `EveryPuzzleProject/puzzle-review`. Everything below uses the
GitHub CLI (`gh`) and `git`.

## 0. Settle the budget

The person may have told you how many puzzles to review. If they haven't, ask
once and suggest **3**. Each puzzle costs roughly 70–90 thousand tokens, almost
all of it reading images. If they're unsure, suggest doing 1 first and checking
how far their usage meter moved.

Also tell them:
- They can stop you at any time. Every finished puzzle is already sent, so
  nothing is wasted.
- Hitting a usage limit partway through is fine for the same reason.

Default to reviewing at most 3 puzzles at once. More doesn't save tokens, it
just spends them faster.

## 1. Check the tools

- `gh auth status` must show them logged in. If `gh` is missing or logged
  out, help them install it (https://cli.github.com) and run `gh auth login`.
  Don't go further until it works.
- `git --version` and `tar --version` must work. `tar` handles `.tar.gz` on
  Windows 10+, macOS and Linux.

## 2. Get the repository

If there's no `puzzle-review` folder here yet:

```
gh repo fork EveryPuzzleProject/puzzle-review --clone --default-branch-only
```

If it exists, bring it up to date:

```
cd puzzle-review
git checkout main
git pull --ff-only upstream main
```

All later commands run inside `puzzle-review`. Puzzle images go in a work
folder beside it, `../puzzle-review-work`, never inside the repository.

## 3. Pick the puzzles

Each publication has a `publications/<pub>/puzzles.tsv` that lists every puzzle
(`xdid`) and its `packet` column:
- a release tag such as `judge-1929-1930` means the packet is ready for review,
- `done` means it was reviewed before this project started,
- `later` means it isn't available yet.

A puzzle is **open** when all of these hold:
1. Its packet is a release tag.
2. `publications/<pub>/reviews/<xdid>/review.json` doesn't exist on
   upstream `main`.
3. It isn't claimed. Run:
   ```
   gh pr list --repo EveryPuzzleProject/puzzle-review --state open --json number,updatedAt,body --limit 200
   ```
   Any xdid that appears in the body of an open PR updated in the last 48
   hours is claimed.

Take the first open puzzles in file order, oldest first, up to the budget. Go
through publications in the order listed in the README. Tell the person what
you picked, e.g. "Judge, March 16 – April 6, 1929: 3 puzzles".

## 4. Claim them with a draft pull request

```
git checkout -b review-<github-username>-<yyyymmdd-hhmm>
```

For each puzzle, download and unpack its packet, then copy its `ocr.json` into
the repository:

```
gh release download <packet tag> --repo EveryPuzzleProject/puzzle-review --pattern "<xdid>.tar.gz" --dir ../puzzle-review-work
tar -xzf ../puzzle-review-work/<xdid>.tar.gz -C ../puzzle-review-work
mkdir -p publications/<pub>/reviews/<xdid>
cp ../puzzle-review-work/<xdid>/ocr.json publications/<pub>/reviews/<xdid>/ocr.json
```

Commit ("Claim <n> <pub> puzzles"), push (`git push -u origin HEAD`), and open a
draft pull request:

```
gh pr create --draft --repo EveryPuzzleProject/puzzle-review --title "<Pub> review: <first date> – <last date>" --body-file <file>
```

The body is a checklist, one line per puzzle, plus the model you're running as:

```
Reviewing with Claude <model name>.

- [ ] judge1929-03-16
- [ ] judge1929-03-23
```

This is the claim, so do it before reviewing.

## 5. Review each puzzle

Run one subagent per puzzle, at most 3 at a time, with this prompt:

> Review the OCR of one scanned crossword puzzle.
>
> Puzzle folder: `<absolute path to ../puzzle-review-work/<xdid>>`
> Instructions: `<absolute path to publications/<pub>/INSTRUCTIONS.md>`
>
> Read the instructions file first and follow it exactly. Use the Read tool on
> every image in the puzzle folder (it displays images). Compare against
> ocr.json and write review.json into the puzzle folder in the format the
> instructions give, adding one more key, "model", with the name of the Claude
> model you are. Only read files in that folder plus the instructions file;
> create no files other than review.json. Reply with one line: counts of
> corrections by kind, confirmations, unsure, whether it's ready to go, and the
> clue you found most charming, quoted exactly.

As each puzzle finishes:
1. Check that `review.json` parses as JSON. If it doesn't, run that puzzle once
   more; if it fails again, skip it and say so.
2. Copy it to `publications/<pub>/reviews/<xdid>/review.json`.
3. Commit ("Review <xdid>"), push, and tick its box in the PR body
   (`gh pr edit <number> --repo EveryPuzzleProject/puzzle-review --body-file <file>`).
4. Tell the person, in one line, with a link to solve it:

   > ✓ *Judge*, March 16, 1929, "Cross Word Puzzle No. 231": 7 misreads fixed, 1 printed misprint kept. Favorite clue: "…". Solve it: <link>

   The link is
   `https://everypuzzleproject.github.io/puzzle-review/solve.html?p=<pub>/<xdid>&from=<github-username>:<branch>`.

Don't push anything except files under `publications/<pub>/reviews/`.

## 6. Finish

When every claimed puzzle is done (or skipped), mark the PR ready with
`gh pr ready <number> --repo EveryPuzzleProject/puzzle-review`. Then give the
person a short wrap-up:
- puzzles reviewed, and the solve links again,
- the PR link,
- the progress page: https://everypuzzleproject.github.io/puzzle-review/

If the run stops early (they stop you, or a limit is hit), that's fine. Leave
the PR as a draft; the maintainer merges partial runs and the unreviewed
puzzles return to the pool after 48 hours. If they come back later and ask you
to continue, pick up the unticked puzzles in the same PR.
