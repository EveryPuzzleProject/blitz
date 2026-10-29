# Maintaining a publication

How a maintainer (a collaborator on the publication's repo) runs the whole loop:
open puzzles for review, review them, check and merge, import. It is the
volunteer flow ([VOLUNTEER.md](VOLUNTEER.md)) plus the maintainer's steps, with
your own branch in the publication's repo instead of a fork. GAMES is the
example; Judge is the same with `judge` for `games`.

Tested end to end on 2026-10-09 with games1977-09-01
([games#1](https://github.com/EveryPuzzleProject/games/pull/1)).

## Once: the checkouts

Everything works from sibling folders:

```
Projects/
  blitz/          the tools (this repo)
  xword-ocr/      OCR, harvest, packets, import (step 2 of design/restructure.md moves these into blitz)
  games/          the publication's repo: fixes/ (ledger), puzzles.tsv, xd/, reviews/, review-notes.md
  games-scans/    private: page images and harvest state (restored with epp)
  tools/          epp (scans backup/restore)
  blitz-work/     scratch: one folder per puzzle you're reviewing (made by blitz start)
```

Clone `games` from `EveryPuzzleProject/games` (not a fork): then `blitz start`
pushes branches to the repo itself. xword-ocr's harvest for GAMES lives in
`xword-ocr/harvests/games` (`epp scans restore games` rebuilds it on a new machine).

## 1. Open puzzles for review

A puzzle can be claimed once its packet is a release asset of the publication's
repo and its row in `puzzles.tsv` names that release.

```
cd xword-ocr
uv run xword-ocr task-packets --out harvests/games --dest harvests/games/tasks-<name> <xdid...>   # or --next 40
```

Then `.tar.gz` each puzzle folder (`tar czf <xdid>.tar.gz <xdid>` in the
`--dest` folder), and attach them to a new release of the publication's repo:

```
gh release create games-<name> -R EveryPuzzleProject/games --title "GAMES <name> packets" --notes "..." harvests/games/tasks-<name>/*.tar.gz
```

Set the `packet` column of those rows in `games/puzzles.tsv` to the release tag
and run `uv run xword-ocr volunteer-sync --out harvests/games`: their state
becomes `open`. Commit and push `games`.

## 2. Review (as a volunteer would)

```
cd blitz
uv run blitz start 3 games --model claude-fable-5-1
```

This claims the next 3 open puzzles with a draft PR to `EveryPuzzleProject/games`
(a branch in the repo), downloads their packets into `../blitz-work/<xdid>/`, and
writes each `text.md`. It leaves `../games` on that branch.

Review each one, either:

- **With Claude**: in a Claude Code session in `xword-ocr` (which has the
  `xword-reviewer` agent), ask for the review, e.g.:

  > Review games1977-09-01 with the xword-reviewer agent on Fable. Repository root to run
  > commands from: C:/Users/adeja/Projects/blitz. Instructions: `uv run blitz instructions games`.
  > Puzzle folder: C:/Users/adeja/Projects/blitz-work/games1977-09-01. Don't run blitz submit.

  The agent reads `text.md`, makes contact sheets (`blitz sheets`), writes
  `draft.json` and runs `blitz finish`, which writes `review.json`. One puzzle took
  about 75 seconds and 28k tokens.
- **By hand**: `blitz start ... --hand` instead, and use the editor it opens ([HAND.md](HAND.md)).

Optionally watch with `uv run blitz watch`. Then send each review:

```
uv run blitz submit games1977-09-01
```

That commits `reviews/<xdid>/review.json` to the branch, ticks the puzzle in the
PR, and marks the PR ready after the last one. CI on the PR runs blitz's
`tools/check_reviews.py`. When you're done: `git -C ../games checkout main`.

## 3. Check and merge

```
cd xword-ocr
uv run xword-ocr pr-check <N> --out harvests/games
```

It fetches the PR's reviews and their scans into `harvests/games/prcheck/pr-<N>/`
and writes `index.html` there. Open it through the `pr-check` preview server
(`http://localhost:8769/games/prcheck/pr-<N>/index.html`). Reject any bad change,
give each puzzle Looks right / Needs work, and download the decisions into that
folder. Then merge the PR on GitHub (or `gh pr merge <N> -R EveryPuzzleProject/games --merge --delete-branch`).

## 4. Import

```
git -C ../games pull
uv run xword-ocr pr-import <N> --out harvests/games --decisions harvests/games/prcheck/pr-<N>/decisions.json
uv run xword-ocr relink --out harvests/games              # about 10 minutes for GAMES
uv run xword-ocr volunteer-sync --out harvests/games      # puzzles.tsv and xd/ in ../games
git -C ../games add -A && git -C ../games commit -m "Import PR <N>" && git -C ../games push
epp scans backup games --publish                          # from ../tools
```

`pr-import` appends the review's changes to `games/fixes/corrections.jsonl` (the
ledger: append-only, the newest change to an item wins), less what you rejected
(to `corrections.rejected.jsonl`), and the reviewer's tool notes to
`tool-notes.jsonl`. Import each PR once. `relink` rebuilds every puzzle from the
OCR plus the ledger; `volunteer-sync` writes each puzzle's state into
`puzzles.tsv` (restored, or needs-person with a reason) and the reviewed
puzzles' `.xd` into `xd/`.

## 5. The review site (optional)

To let helpers proof the reviewed puzzles at blitz.xwordapp.com/review/:

```
cd blitz
uv run --extra site blitz site-publish <folder of reviewed packets> --batch <name>
```

To bring their proofs back, one command does the whole loop and stops on surprises:

```
uv run --extra site blitz sync games ../xword-ocr/harvests/games/<folder of the packets on the site>
```

Without `--go` it fetches what helpers decided, dry-runs the import and reports what it would
add to the ledger, by who it credits. It stops if one name would get more than 150 lines, if the
folder's own review.json files would be credited (a current-review folder adds none), or if a
review is rejected. With `--go` it imports, relinks, signs off each ready proof of the current
version (`xword-ocr signoff`: `fixes/signoffs.jsonl` records the xd it produced), runs
volunteer-sync, and checks that only this batch's puzzles' xd files changed. `--commit` commits
the publication's repo. Pushing, rebuilding packets for the changed puzzles and site-publish are
printed as next steps. A sign-off lapses when the puzzle's xd changes later, so readiness always
means "a person said this exact version is ready".

### Working on the site's pages

To change the proof page or the batch page (`src/blitz/proof.html`, `batch.html`) and see each edit
in seconds, run the site locally over a copy of real data:

```
uv run python tools/review_dev.py --data <folder> [--port 8795]
```

Each packet's `checks.json` (what the checks found: the ship check's findings, triage's doubts, the
text step's notes, gxd's key near misses, keyed by the page's rows) is written by xword-ocr's
`triage --proof`, or `proof-checks --out <harvest> --run <run> [--dest <copy>]` for packets copied
here; the proof page opens with it, and `site-publish` uploads it with the packet.

It serves the pages as the site does (the volunteer's view, no `site-build`), reloads the open tab
whenever either file is saved, and stands in for Supabase: Ready, Not ready, edits and comments are
kept in `<folder>/db/`, never on the real site. `<folder>` holds `packets/` (proof packets, copied
once from a harvest's `proof/<run>/`, with its `dropped.json`) and `files/batch/` (a batch snapshot:
`batches.json` and `<name>/`, from `site-publish-batch --dry-run` or the published copy). Open
`http://localhost:8795/review/batch/`. When the pages are right, `blitz site-build` and commit
`docs/review/` as usual.

### Key squares

The quickest way for people to help: one doubtful answer-key letter at a time, at
blitz.xwordapp.com/review/squares/ (see site/README.md). For a folder of current-review packets:

```
uv run blitz key-squares <folder> --pub games            # the flag list: OCR-unsure letters and the word check
uv run --extra site blitz site-publish <folder> --squares-only
```

Bring the answers back with the rest of the site's work, and read the dry run before the real one:

```
uv run --extra site blitz site-import -o ../blitz-work/site-decisions.json
cd ../xword-ocr
uv run xword-ocr import-reviews <folder> --pubid games --by "..." --decisions ../blitz-work/site-decisions.json --dry-run
```

The dry run ends with what it would append, by who it credits: key-square answers show as
`<names> (key-squares page): confirm cell` / `correct cell` / `confirm check`. Then run it without
`--dry-run`, relink and sync as in step 4, rebuild the packets, and run `blitz key-squares` and
`site-publish --squares-only` again: settled cards drop off the page.

## Large batches without PRs

For tens or hundreds of puzzles at once, the maintainer can skip claims and PRs:
`task-packets` into a batch folder, run several `xword-reviewer` agents on it,
then `import-reviews`. See "Importing a large reviewed set" in xword-ocr's
`docs/review-runbook.md` (that's how Judge's 298 went in on 2026-10-09). The
PR flow above is the one volunteers use, and the one to keep exercised.
