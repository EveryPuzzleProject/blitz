# Volunteer run: instructions for Claude

You're helping a person donate Claude usage to the Every Puzzle Project. Old
crossword puzzles were scanned and read by OCR. You will check some of those
readings against the scans and send the results back as a pull request. Work
through the steps below in order. Keep the person informed in short, friendly
lines; they're watching.

Repository: `EveryPuzzleProject/blitz`. Everything goes through one command,
`blitz`, run with `uv run blitz …` from the `blitz` folder. It uses `git` and
`gh` (the GitHub CLI). On Windows, Claude Code's Bash tool (Git Bash) works.

## 0. Settle the budget

The person may have told you how many puzzles to review. If they haven't, ask
once and suggest **8**. Each puzzle costs roughly 20–30 thousand tokens and a
few minutes. If they're unsure, suggest doing 4 first and checking how far
their usage meter moved.

Ask two more questions at the same time:
- Would they like their GitHub name listed on the project's contributors
  page? The default is no. Either way, their pull request is visible on
  GitHub.
- Which magazine: *Judge*, a 1920s humor magazine, or *GAMES*, the puzzle
  magazine, from 1977? The default is whichever is next in line.

Also tell them:
- They can stop you at any time. Every finished puzzle is already sent, so
  nothing is wasted.
- Hitting a usage limit partway through is fine for the same reason.
- If they'd like to watch the review as it happens, `uv run blitz watch`
  (step 4) opens a page showing where on each scan Claude is looking and what
  it changes.

If the person named a model for the reviews ("using Fable", "with Sonnet"),
run every review subagent on that model; some people have a separate
allowance for a particular model. Otherwise the subagents use this session's
model. Don't ask about models unprompted. Below, `<model>` is the model ID
the reviews run on (for example `claude-fable-5-1`).

## 1. Check the tools

- `gh auth status` must show them logged in. If `gh` is missing or logged
  out, help them install it (https://cli.github.com) and run `gh auth login`.
- `git --version` must work.
- `uv --version` must work. If it doesn't, install it
  (https://docs.astral.sh/uv/getting-started/installation/: one command).

Don't go further until all three work.

## 2. Get the repository

If there's no `blitz` folder here yet:

```
gh repo fork EveryPuzzleProject/blitz --clone --default-branch-only -- blitz
```

If they forked it before, this says the fork already exists (it may have an
older name, such as `puzzle-review`) and clones it into `blitz` anyway. Then:

```
cd blitz
git remote get-url upstream || git remote add upstream https://github.com/EveryPuzzleProject/blitz.git
uv run blitz doctor
```

`doctor` says what's missing, if anything. All later commands run inside
`blitz`. Puzzle files go in a work folder beside it, `../blitz-work`, never
inside the repository.

## 3. Claim the puzzles

```
uv run blitz start <budget> [judge|games] --model <model> [--list-me]
```

Leave out the magazine if they had no preference; add `--list-me` only if
they asked to be listed. This claims the next open puzzles with a draft pull
request (so nobody else takes them), downloads their scans to
`../blitz-work/<puzzle>/`, and writes each one's `text.md`. It prints the
pull request and the puzzles. A puzzle marked "expect a whole-puzzle problem"
is still yours to review: the reviewer escalates what it can't settle.

If it says every puzzle is taken, offer the other magazine, or thank the
person and stop. Tell the person what you claimed, e.g. "*Judge*, March 16 –
May 4, 1929: 8 puzzles".

## 4. Review them

Run review subagents, **4 puzzles to a subagent**, at most 3 subagents at a
time, with this prompt (fill in the folder, puzzles and model):

> Review the OCR of some scanned crossword puzzles, text first.
>
> Run every command from `<absolute path to the blitz folder>`. First run
> `uv run blitz instructions` and follow what it prints exactly. Then, for
> each puzzle in turn: read `../blitz-work/<puzzle>/text.md`, make its contact
> sheets with `uv run blitz sheets <puzzle> <targets>`, read the sheets, write
> `../blitz-work/<puzzle>/draft.json`, and run `uv run blitz finish <puzzle>`.
> Finish one puzzle before starting the next. Write no files other than the
> draft.json files.
>
> Puzzles: `<puzzle>`, `<puzzle>`, `<puzzle>`, `<puzzle>`
>
> When done, reply with one line per puzzle, in this form and nothing else:
> `<puzzle> | <title as printed> | <N> corrections | <N> misprints kept | <N> unsure | escalated or not | ready or not | "<the clue you found most charming, quoted exactly>"`

If the person wants to watch, run `uv run blitz watch` in the background
before starting the subagents: it opens a page in their browser that follows
the reviews live.

## 5. Send each review

As each puzzle finishes (it has a `review.json`):

```
uv run blitz submit <puzzle>
```

This commits the review, pushes it to the pull request, ticks it in the PR,
and makes the person a private copy of the puzzle to solve, as a souvenir (it
stays in the work folder and is never pushed). It prints the puzzle's record
link and the path of the private copy. If it says the review isn't
well-formed, run that puzzle's review once more; if it fails again, skip it
and say so.

Tell the person, in one line:

> ✓ *Judge*, March 16, 1929, "Cross Word Puzzle No. 231": 7 corrections, 1 printed misprint kept. Favorite clue: "…". Record: <link> · Try it yourself: <path>

`uv run blitz status` shows where every puzzle of the run stands.

## 6. Finish

When the last puzzle is sent, `submit` marks the pull request ready for
review. Then give the person a short wrap-up:
- the puzzles reviewed, with their record links and private copies (the
  copies are just for them: ask them not to share or post them),
- the PR link,
- the progress page: https://everypuzzleproject.github.io/blitz/

If the run stops early (they stop you, or a limit is hit), that's fine. Leave
the PR as a draft. The maintainer merges partial runs, and unreviewed puzzles
return to the pool after 48 hours. If they come back later and ask you to
continue, `uv run blitz status` shows what's left; review and submit those.
To give up the rest instead, `uv run blitz drop`.
