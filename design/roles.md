# Roles: who does what when several sessions work on one publication

Draft, 2026-11-01, written from the New York World FUN day (chain C1 OCR, the 1918–19
partner-paper intake). For discussion; nothing here is enforced yet. The aim is that a
brief for a new session starts from a role below instead of being written fresh, and that
the repeated procedures become skills.

The rule that makes roles necessary: **one writer per set of files, and every value says
where it came from.** When one session both runs the pipeline and changes its code, its
PR mixes run output with code, its "tests pass" is self-reported, and the only check on
its logic is whoever happens to read its progress notes. Roles separate those.

## The roles

### The person

Downloads and browses (Newspapers.com, archive.org), decides what a page is when search
can't find it (not-carried vs no-hit), answers flags on the proof page, merges PRs,
deploys the site, and makes the calls the tables record as decisions (what counts as the
same puzzle, which series is dated vs numbered, what gets published). Works in the status
page and the review site, not in chat.

### Point of contact (coordinator)

One session per working day. It is the only session the person talks to about the day's
work. It never reads pages, runs the pipeline or edits tables.

- Owns: the person's queue ("what you need to do next", always with crop vs full page per
  page), the routing table (which session holds which repo, branch and table), the working
  rules the person gives (memory: feedback files), and the files the person drops in
  `~/Downloads` (identifies each, names and files it; the person never renames).
- Must not: fix anything itself, transcribe, or decide what a puzzle is.
- Inputs: the person's messages and downloads; the other sessions' reports.
- Output: a few lines per event, the next download list, and the day's handoff memory.
- Hands off to: intake (new pages), the OCR operator (new crops, a diagnosis), chains
  (a new link), research (a question about sources).

### Intake (indexer)

One session per publication run. Reads page images only to index them, never to
transcribe; writes the publication's tables only through the record tool.

- Owns: `printings.tsv`, `searches.tsv`, `pages.tsv` in the scans repo, the queue on the
  status page, the intake runbook (`docs/INTAKE.md`).
- Rules: readers are cheap models, one page each, reporting JSON that the importer flattens;
  anything a reader could not read stays empty and becomes a flag, never a guess. no-hit
  (search) and not-carried (a person browsed) are different states. Matches are by first
  clue and grid shape and say so; "medium confidence" is a column, not a feeling.
- Inputs: new files in the scans repo; the person's browse verdicts; corrections.
- Output: a report with a table (per page: what it is, matched to what, offset), what was
  queued, what is still flagged; both repos pushed; no PR unless the person says.
- Hands off to: chains (a new page in a run), the OCR operator (a page ready to read).

### Chains (dating and identity)

Reasons across printings rather than per page: which copies are the same puzzle, which
puzzle follows which, where the chain breaks and what would close it. This is a different
judgement from intake and gets its own brief.

- Owns: `links.tsv`, `chains.tsv`, `chain_breaks.tsv`, `reruns.tsv`, `docs/CHAINS.md`, the
  Chains section of the status page.
- Rules: a link has an evidence kind (dated box, label, grid, printed number, series) and a
  verdict; tentative links are drawn paler and never promoted without new evidence; the
  person decides what counts as the same puzzle (reruns, reclued grids).
- Output: chains and breaks, and for each break the single page that would close it, as
  the next item on the person's list.

### Research (sourcing)

Which papers carried the feature, where scans exist, what the catalog knows. Writes to
the catalog and to `RESEARCH.md`, never to the tables.

### OCR operator

Runs the pipeline on a harvest and takes it as far as the allowed interventions go:
hints, the fix file, hand-drawn grids, the text step, packets, triage, the AI proof review,
publishing. Reports counts by failure kind.

- Owns: the harvest folder, the run registry, the publication's fix file, the batch on the
  review site, `docs/OCR-<run>.md`.
- Must not: change pipeline code during a run; type puzzle content. When a run exposes a
  bug, it records a **finding** (the failing case, the stage, the diagnosis, a crop) and
  stops at that puzzle; the fix is the developer's.
- Output: assembled / keyed / numbered / ready counts; the exceptions by kind; the
  person's to-do on the proof page; PRs on the publication repo (records) only.

### Pipeline developer

Changes xword-ocr and blitz code from findings, on its own branch, with tests.

- Inputs: findings from the operator (never a puzzle to fix by hand), design docs.
- Rules: new behaviour behind a switch; finished work keeps its version
  (design/regression-by-versions); views never compute. The PR says which findings it
  closes.
- Output: a PR, and a request to the tester. Does not re-run the publication's harvest
  itself; the operator does, once the tester passes it.

### Pipeline tester

A fresh session or agent, never the developer, that checks a PR against known work.

- Owns: the eval set (reviewed truth per publication), the regression report.
- Does: runs the eval on the PR branch, diffs per puzzle against the last accepted run,
  checks the principles that tests don't (a view that recomputes, a value with no source,
  a publication-specific rule upstream), and reads the developer's logic for errors of
  the kind "the key on the same page taken as the puzzle's own".
- Output: pass / fail with the per-puzzle diff, posted on the PR.

### Reviewer

The AI proof review (`xword-reviewer`): text first, suspects on the contact sheet, flags
as yes/no questions on the proof page. Already an agent type.

## How today mapped onto this

| Today | Role | What was mixed |
|---|---|---|
| this session | coordinator | also caught a logic error (No. 9 keyed to its own page's box): tester's job |
| fun-intake | intake, then chains inline ("Pittsburgh 16 weeks ahead") | dating judgements inside an intake report |
| fun-chains | chains | clean |
| fun-research, chronam, catalog | research | clean |
| ocr-the-early-world-fun | operator + developer + tester in one | gates, crop intake, key rule, Down matcher and the proof page all changed mid-run; "eval unchanged" self-reported |

## Encoding it

- **This file** is the source for briefs: a brief names the role, the publication, and the
  inputs; the role supplies the owns / must-not / output format.
- **Skills** for the procedures that were identical three times today: file the person's
  downloads (identify, name `<page>_fun` / `_key` / `_screenshot_*`, put in the scans repo);
  intake a batch (readers, import, continuity, rebuild, push, report table); run the
  regression (eval on a branch, per-puzzle diff); publish a batch (`--current-review`).
- **Agent definitions** (`.claude/agents/`) for the roles run as subagents inside a
  session: page reader, reviewer, tester.
- **Memory** for the rules the person gives (crop vs full page; the person never renames).
- **Hand-offs are files, not chat**: a finding is a record in the harvest; a queued page is
  a row in `searches.tsv`; a break is a row in `chain_breaks.tsv`. The coordinator relays
  that a file exists, not its contents.

Open questions: whether the operator and the developer can be one session when the fix is
in the fix file rather than code (today's hand-drawn grids were fine); whether the tester
is worth a session for small PRs or a skill the coordinator runs; and where this file
lives after the restructure (blitz is the umbrella, so here).
