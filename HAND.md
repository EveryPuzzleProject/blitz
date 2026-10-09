# Review puzzles by hand

You don't need Claude to help. You can check a puzzle's OCR against the scan
yourself, in an editor that runs in your browser, and send the result as a
pull request. Hand reviews go through the same checks as Claude's and count
the same toward restoring each magazine.

## What you need

- A GitHub account, and the [GitHub CLI](https://cli.github.com) logged in
  (`gh auth login`).
- `git` ([Git for Windows](https://git-scm.com/download/win) on Windows) and
  [`uv`](https://docs.astral.sh/uv/getting-started/installation/), which runs
  the `blitz` command.
- A web browser.

## Once: get the repository

```
gh repo clone EveryPuzzleProject/blitz
cd blitz
```

That's the tools. Each magazine has its own repository, where reviews go:
`blitz start` forks it into a folder beside `blitz` the first time.

## Each time

**1. Claim puzzles.** From the `blitz` folder:

```
uv run blitz start 1 games --hand
```

The number is how many puzzles to take; the last word is the magazine,
`games` (*GAMES*, from 1977) or `judge` (*Judge*, the 1920s humor
magazine), or leave it out for whichever is next. This opens a draft pull
request with your name on those puzzles, so nobody else takes them,
downloads their scans to `../blitz-work`, and opens the first puzzle's
editor. It prints the path of each editor (`edit.html`), so you can open the
others yourself.

**2. Review in the editor.** The scan is on the right; click any clue or
square to see it there.

- **Title and byline:** as printed. The title is the puzzle's own name; a
  printed number goes in Number.
- **Answer grid:** compare it square by square with the printed key. Flip
  between **Printed key** and **Your letters** to spot differences. Click a
  square and type the right letter (`#` makes it black, `.` marks it
  unreadable).
- **Clues:** each clue's text sits under its scan crop. Fix what the OCR
  misread. Keep misprints and odd spellings exactly as printed, and mark them
  with **Misprint** (say what was meant) instead of correcting them. Mark
  anything you can't read with **Unsure**.
- **Finish:** say whether it's ready to publish, and anything left over.

The editor saves as you go, in your browser, so you can close it and come
back. The full rules are in `publications/INSTRUCTIONS.md`, and what's particular to
the magazine in its repository's `review-notes.md` (`uv run blitz instructions <magazine>` prints both).

**3. Save and send.** Press **Save review**. It goes to your Downloads folder
as `<puzzle>.review.json`. Then:

```
uv run blitz submit games1977-09-01b
```

That checks the file, adds it to your pull request and ticks the puzzle off.
After the last one, your pull request is marked ready and a maintainer takes
it from there.

## If you stop partway

Finished puzzles are already sent. Puzzles you claimed but didn't finish go
back to the pool after 48 hours. To carry on later, open the same `edit.html`
again (your work is still there) and submit when you're done.
