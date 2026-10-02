# Volunteer run: instructions for Claude

You're helping a person donate Claude usage to the Every Puzzle Project. Old
crossword puzzles were scanned and read by OCR. You will check some of those
readings against the scans and send the results back as a pull request. Work
through the steps below in order. Keep the person informed in short, friendly
lines; they're watching.

Repository: `EveryPuzzleProject/puzzle-review`. Everything below uses `gh`
(the GitHub CLI), `git` and `tar` in a bash shell. On Windows, Claude Code's
Bash tool (Git Bash) works.

## 0. Settle the budget

The person may have told you how many puzzles to review. If they haven't, ask
once and suggest **3**. Each puzzle costs roughly 70–100 thousand tokens,
almost all of it reading images, and takes a few minutes. If they're unsure,
suggest doing 1 first and checking how far their usage meter moved.

Also tell them:
- They can stop you at any time. Every finished puzzle is already sent, so
  nothing is wasted.
- Hitting a usage limit partway through is fine for the same reason.

Review at most 3 puzzles at once. More doesn't save tokens, it just spends
them faster.

## 1. Check the tools

- `gh auth status` must show them logged in. If `gh` is missing or logged
  out, help them install it (https://cli.github.com) and run `gh auth login`.
  Don't go further until it works.
- `git --version` and `tar --version` must work.
- Note their GitHub username: `gh api user --jq .login`. Below it's `<user>`.
- Note your own model ID (for example `claude-sonnet-5-5`). Below it's `<model>`.

## 2. Get the repository

If there's no `puzzle-review` folder here yet:

```
gh repo fork EveryPuzzleProject/puzzle-review --clone --default-branch-only
```

Then, whether the folder is new or not:

```
cd puzzle-review
git fetch upstream
```

The fork may be an old one from an earlier run. That's fine: your branch
starts from `upstream/main` in step 4, not from the fork's `main`.

All later commands run inside `puzzle-review`. Puzzle images go in a work
folder beside it, `../puzzle-review-work`, never inside the repository.

## 3. Pick the puzzles

```
tools/pick.sh <budget>
```

It prints the open puzzles to review, oldest first, one per line:
`<pub> <xdid> <release tag>`, e.g. `judge judge1929-03-16 judge-1929-1930`.
A puzzle is open when its scans are released, nobody has reviewed it, and
nobody has claimed it in the last 48 hours. If it prints nothing, every
available puzzle is taken: thank the person and stop.

Tell the person what you picked, e.g. "*Judge*, March 16 – April 6, 1929:
3 puzzles".

## 4. Claim them with a draft pull request

```
git checkout -b review-<user>-<yyyymmdd-hhmm> upstream/main
```

For each puzzle, download and unpack its packet, then copy its `ocr.json` into
the repository:

```
gh release download <release tag> --repo EveryPuzzleProject/puzzle-review --pattern "<xdid>.tar.gz" --dir ../puzzle-review-work
tar -xzf ../puzzle-review-work/<xdid>.tar.gz -C ../puzzle-review-work
mkdir -p publications/<pub>/reviews/<xdid>
cp ../puzzle-review-work/<xdid>/ocr.json publications/<pub>/reviews/<xdid>/ocr.json
```

Commit with the message `Claim <xdids, space-separated>`, then
`git push -u origin HEAD`. Git may warn that CRLF will be replaced by LF.
That's expected; ignore it.

Write the PR body to `../puzzle-review-work/pr-body.md`:

```
Reviewing with <model>.

- [ ] judge1929-03-16
- [ ] judge1929-03-23
```

and open a draft pull request:

```
gh pr create --draft --repo EveryPuzzleProject/puzzle-review --title "Review <xdids, space-separated>" --body-file ../puzzle-review-work/pr-body.md
```

This is the claim, so do it before reviewing.

## 5. Review each puzzle

Run one subagent per puzzle, at most 3 at a time, with this prompt (fill in
the paths and model):

> Review the OCR of one scanned crossword puzzle.
>
> Puzzle folder: `<absolute path to ../puzzle-review-work/<xdid>>`
> Instructions: `<absolute path to publications/<pub>/INSTRUCTIONS.md>`
>
> Read the instructions file first and follow it exactly. Use the Read tool on
> every image in the puzzle folder (it displays images). Compare against
> ocr.json and write review.json into the puzzle folder in the format the
> instructions give, adding one more key: "model": "<model>". Only read files
> in that folder plus the instructions file; create no files other than
> review.json.
>
> Your final reply must be exactly one line, in this form and nothing else:
> `<title as printed> | <N> corrections (<N> grid, <N> clue, <N> other) | <N> misprints kept | <N> unsure | ready or not ready | "<the clue you found most charming, quoted exactly>"`

As each puzzle finishes:
1. Read `review.json` and make sure it's well-formed JSON. If it isn't, run
   that puzzle once more; if it fails again, skip it and say so.
2. Copy it to `publications/<pub>/reviews/<xdid>/review.json`.
3. Commit with the message `Review <xdid>`, push, tick its box in the PR
   body file, and update the PR:
   `gh pr edit <number> --repo EveryPuzzleProject/puzzle-review --body-file ../puzzle-review-work/pr-body.md`
4. Tell the person, in one line, with a link to solve it:

   > ✓ *Judge*, March 16, 1929, "Cross Word Puzzle No. 231": 7 corrections, 1 printed misprint kept. Favorite clue: "…". Solve it: <link>

   The link is
   `https://everypuzzleproject.github.io/puzzle-review/solve.html?p=<pub>/<xdid>&from=<user>:<branch>`.

Only add files under `publications/<pub>/reviews/`. A check runs on the pull
request and flags any review that isn't well-formed.

## 6. Finish

When every claimed puzzle is done (or skipped), mark the PR ready with
`gh pr ready <number> --repo EveryPuzzleProject/puzzle-review`. Then give the
person a short wrap-up:
- the puzzles reviewed, with their solve links,
- the PR link,
- the progress page: https://everypuzzleproject.github.io/puzzle-review/

If the run stops early (they stop you, or a limit is hit), that's fine. Leave
the PR as a draft. The maintainer merges partial runs, and unreviewed puzzles
return to the pool after 48 hours. If they come back later and ask you to
continue, pick up the unticked puzzles in the same PR.
