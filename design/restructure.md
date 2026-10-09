# Restructure plan: blitz, xword-ocr, and one repo per publication

Draft, 2026-10-09, for approval. Nothing here is done yet except step 0.

## The rule

**Code and how-to live in tool repos. Everything about one publication lives in
that publication's repos.** One test for any file: would it exist, unchanged, if
we were working on a different publication? If yes, it belongs to a tool repo.
If it names Judge, describes Judge, or is Judge's data, it belongs to `judge`
(public) or `judge-scans` (private).

This is what makes 100s of publications workable: adding a publication adds
repos, never folders or special cases inside the tools.

| Repo | What it is | Public? |
|---|---|---|
| `xword-ocr` | The library: page image in, grid / crops / clues / numbering / xd out. No publication state, no archive.org, no review. | yes, eventually (on PyPI) |
| `blitz` | The project and its one CLI: harvest, packets, review, the site, import, status, export. Generic docs (rules, volunteer guide, process notes). | yes |
| `<pub>` (e.g. `judge`) | The publication's record: what exists, what we have, its corrections, its puzzles, its status, its notes. | public by default |
| `<pub>-scans` | The publication's evidence and working files: page images, OCR caches, harvest state, raw review attempts. | private |
| `catalog` | Facts about every publication, one file each. | yes |
| Supabase + R2 | The review site's live data (puzzle list, proofs, verdicts; packet images). Generic: one database for all publications. | site |

`tools` (epp) folds into blitz (`blitz scans ...`) or is retired; see step 3.

## Where status lives

Today a puzzle's state is in four places that disagree: blitz `puzzles.tsv`,
judge `status.tsv` (copied from blitz in CI), the ledger, and Supabase.

After: **one table, `judge/puzzles.tsv`**, one row per *expected* puzzle,
including ones we haven't found (stubs). It is computed, never edited by hand:

```
blitz sync judge   =  harvest manifest  (what we found, where)
                    + corrections ledger (what was reviewed, verdicts)
                    + site decisions     (helpers' proofs, Not ready)
                    + gxd checkout       (what's in gxd, and whether it matches)
                    + judge/manual.tsv   (hand overlay: puzzles we know of but haven't found, notes)
                    -> judge/puzzles.tsv, and the same states pushed to Supabase
```

Columns, roughly: `xdid, date, number, state, reason, review_url, packet, in_gxd, updated`.
States in order: `missing` (known to exist, not found) -> `found` -> `in-review` ->
`reviewed` -> `exported` -> `in-gxd`, with `needs-person` + a reason
(`no-key`, `ruling`, `not-ready`, ...) beside any of them. `no-key` is not a
blocker: those export with a "help us find the answer key" note.

The judge status page (CI) renders `puzzles.tsv` directly. `blitz status` reads
every publication's `puzzles.tsv` for the cross-publication view ("what's out
there, what's in progress, what's reviewed").

## Where notes live

"Notes" is five different things today. Each gets one home:

| Kind | Example | Home |
|---|---|---|
| Facts and history | Judge went monthly in Aug 1932; numbering restarts in 1927 | `catalog/publications/judge.md` (facts), `judge/README.md` (the public story) |
| Reviewer guidance for this publication | "the $10 notice isn't part of the puzzle"; changing the grid | `judge/review-notes.md` (now blitz `publications/judge/NOTES.md` + the Judge part of `INSTRUCTIONS.md`). `blitz instructions judge` reads it from `../judge`. |
| Hand fixes to the harvest | page hints, a typed grid, extra pages | `judge/fixes.toml` (now `xword-ocr/fixes/judge.toml`) |
| Reviewers' notes on the tools | "D60 crop shows D59" | `judge/tool-notes.jsonl`: evidence for fixing the tools, kept with the publication it came from |
| How the tools evolved; lessons | "Reading the text first", the Judge 1929-39 run | `blitz/docs/process-notes.md` (moved from xword-ocr) |
| Missing data and calls to action | No. 95 not found; 73 answer keys missing | rows in `judge/puzzles.tsv` (state + reason), shown on the status page and crossref |

## What moves into `judge`

```
judge/
  README.md            the public story + how to help (exists)
  CONTRIBUTING.md      what Judge needs now (harvest / review / find), and how to send it
  puzzles.tsv          the status table (replaces blitz publications/judge/puzzles.tsv and status.tsv)
  manual.tsv           hand overlay (exists)
  series.tsv           (exists)
  funnies.tsv          (exists)
  review-notes.md      reviewer guidance (from blitz publications/judge/NOTES.md + INSTRUCTIONS.md's Judge part)
  fixes/               (done 2026-10-09, judge 223800a)
    fixes.toml         hand fixes (was xword-ocr/fixes/judge.toml)
    corrections.jsonl  the ledger, append-only
    corrections.rejected.jsonl
    tool-notes.jsonl
  provenance.jsonl     per xdid: grid / clue / solution scan URLs, how it was made, who reviewed, review link
  xd/YYYY/*.xd         the export: puzzle-only, what goes to gxd (replaces blitz publications/judge/xd/)
  reviews/<xdid>.json  the final review of each puzzle (doubts, sic, notes), for the record
  site/                the status page (exists)
  releases             packet tarballs for volunteers (now on blitz's releases)
```

`provenance.jsonl` is shaped so it could become gxd's receipts later (Saul is
open to that), and it's the one file crossref overlays to show "transcribed from
a scan" with links to the scan and the review.

The working .xd files (with OCR headers) stay derived: `relink` rebuilds them,
they aren't committed anywhere.

Visibility: public by default; make a repo private if a source calls for it or
if it draws objections.

## The volunteer pipeline, end to end

The goal: volunteers harvest, run the first-pass OCR and the AI review; the
results reach the review site for less technical helpers; their proofs come back.

| Step | Who | How |
|---|---|---|
| Harvest a source, first-pass OCR, build packets | a harvester (collaborator on the publication repo) | `blitz harvest` / `blitz packets` (after step 2); packets attached to a release of the publication repo |
| AI review | anyone, with their agent | fork the publication repo, `blitz start`, PR the reviews (step 1c) |
| Merge, import into the ledger | maintainer, later CI | `blitz check` on the PR; import on merge |
| Publish to the review site | maintainer (`blitz site-publish`) | **later, decide:** a CI job on merge, with the site keys as org secrets |
| Helpers' proofs back into the ledger | maintainer | `site-import` + import |

Harvesting is a trusted role (it uploads packets), reviewing is open to anyone.
The test of the whole chain: someone other than the maintainer harvests a batch
of Boston Globe puzzles, reviews it with their agent, and it reaches the site.

## What stays in `judge-scans` (and becomes the harvest folder)

Today `xword-ocr/harvests/judge/` is the working folder and `epp scans backup`
copies parts of it into `judge-scans`. After, **the harvest works directly in the
`judge-scans` checkout**: page images, caches, `region-ocr.json`, `manifest.json`,
`state.pkl` (git-ignored, uploaded as a release), and batches under `work/`
(git-ignored scratch: packets, drafts, the 30+ `tasks-*` folders today). Backing
up becomes a commit, not a copy. Raw review attempts (every batch's
`review.json`) stay here, private: the ledger and `judge/reviews/` have what
matters.

## What moves into `blitz`, and what's left in `xword-ocr`

| Module (xword-ocr today) | Goes to |
|---|---|
| `grid`, `ocr`, `letters`, `layout`, `clues`, `textfix`, `numbering`, `xd`, `puzfile`, `lint`, `pipeline`, `look` | stay: the library (~4.3k lines; they import only each other) |
| `harvest` (1.7k lines), `sources/ia`, `fixes` | blitz `harvest/`: `blitz harvest`, `relink`, `continuations`, `second-look`, `reread-letters`, `stale` |
| `tasks` (packets, `import_reviews`) | blitz: `blitz packets`, `blitz import` |
| `corrections`, `prcheck`, `findings`, `volunteer` | blitz: the ledger, PR check/import, OCR findings, `blitz sync` |
| `browse` (harvest index, queue, triage pages) | blitz, later folded into `blitz status` / the site |
| `review.py` (the old per-puzzle HTML page, `context_crop`) | crops to the library; the page retires |

blitz then depends on xword-ocr (the library) with its OCR extra; volunteers who
only review install blitz without the heavy OCR dependencies.

**Risk: `state.pkl`.** It pickles `harvest.Page`, `Puzzle`, `ManifestRow` and
`_ManualSolution`. Moving `harvest.py` breaks loading old state. Plan: a small
unpickler that maps `xword_ocr.harvest.*` to the new module, tested by loading
today's state and relinking all 511 Judge puzzles byte-identically. (Later,
replace pickle with JSON so state survives refactors.)

## How contributions come in (decided 2026-10-09)

Two entry points:

- **The review site** is the main way in for most helpers: no clone, no PR,
  no AI tool needed. Proofs come back through `site-import`.
- **Pull requests to the publication repo**, for developers and their AI
  agents. Work on Judge happens in `judge`; there is no inbox in blitz. The org
  README points people to blitz and xword-ocr (the tools) and to each
  publication repo (the work). Each publication repo's `CONTRIBUTING.md` says
  what that publication needs right now.

What a PR to a publication repo can carry, by stage:

| Stage | A contribution | Lands as |
|---|---|---|
| Find | a puzzle we didn't know about, a sighting, a better source | a row in `manual.tsv` (and `catalog` for publication-level facts) |
| Harvest | run `blitz harvest` over a source, tune page hints | `fixes.toml` changes, `manifest.json`; packets as a release |
| Review | an agent's or a person's review of puzzles | `reviews/<xdid>.json` (+ the packet's `ocr.json`) |
| Fix | a correction to a reviewed puzzle | a review file, like any other review |

On merge: a CI check (`blitz check`) has already validated the PR (the
numbering holds, the reviews match their packets); then `blitz import judge`
appends to the ledger and `blitz sync judge` refreshes `puzzles.tsv`. The import
can run in CI (it needs no scans); relink and export need the harvest state, so
they run on a maintainer's machine for now.

**Harvest by volunteers.** Anyone working on a publication works from its
repos. Where the scans come from doesn't change the workflow: archive.org pages,
or clippings shared among a research team with newspapers.com subscriptions
(fair-use research and note-taking). The only thing a source decides is whether
that publication's repos are public (the default) or private (a small team);
either can change later.

Claiming work (so two people don't review the same puzzles) moves with it: a
draft PR or an issue in the publication repo, not in blitz. The existing
"donate your Claude allowance" flow (`blitz start`) keeps working, but points at
the publication repo instead of `blitz/publications/`.

## Order

0. ~~Review code out of xword-ocr~~ (done 2026-10-09).
1a. ~~Judge's fixes and ledger into `judge/fixes/`~~ (done 2026-10-09). xword-ocr finds
   `../<pub>/fixes/fixes.toml` when the record repo is beside it; GAMES still uses
   `xword-ocr/fixes/games.toml` until `games` exists.
1b. ~~Judge's `puzzles.tsv`, `xd/`, `reviews/` and notes (`review-notes.md`) into `judge`~~
   (done 2026-10-09, judge 05f672c, blitz 8f5706a). volunteer-sync writes there; the status
   page builds from it; `blitz instructions judge` and the site's pages read it. Judge's
   PR flow is paused (Judge left `publications/ORDER`) until step 1c.
1c. **Next:** rebuild the volunteer PR flow (`blitz start`, `hand.sh`, `pick.sh`, the PR check,
   `pr-check`/`pr-import`) against publication repos, and create `games` the same way.
1. **The record repos.** Move fixes/ledger/notes/xd/puzzles.tsv into `judge`;
   create `games` the same way. Tools find a publication's repos as siblings
   (`../judge`, `../judge-scans`) through a registry in blitz
   (`publications.tsv`: pubid, record repo, scans repo). `blitz sync` replaces
   `volunteer-sync` and the judge CI copy step. Still using xword-ocr's commands,
   only with new paths. blitz's `publications/` folder empties out; `blitz start`
   and review PRs point at the publication repo; each publication repo gets a
   `CONTRIBUTING.md`.
2. **The code move.** Workflow modules into blitz, with the pickle shim; xword-ocr
   becomes the library. Check: relink rebuilds every .xd identically; packets
   identical; both test suites pass.
3. **Harvest folder = scans checkout.** Retire `epp scans backup/restore`; move
   `globe-wayback` into blitz or leave it in `tools` (it's Boston Globe discovery).
4. **`blitz status`, export, provenance.** The cross-publication view; puzzle-only
   xd into `judge/xd/`; `provenance.jsonl`; re-export on change.
5. **Library polish.** API, docs, examples, PyPI, make xword-ocr public.
6. **The org landing page** (`EveryPuzzleProject/.github`, `profile/README.md`):
   what's where, and the ways to help (review site; tools; publication repos).
   After step 2, so it describes the layout once. A first `bostonglobe` harvest
   by a volunteer is the test that the contributor path works end to end.

Each step leaves everything working and is merged before the next starts.
