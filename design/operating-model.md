# Operating model: the week, the managers, and the pipeline dev lane

Draft, 2026-11-10, for review. Builds on `roles.md` (2026-11-01), which defines the roles
inside one publication's working day and was never put into practice. This file adds what
that draft lacked: a layer above the publications, a way for pipeline changes to be asked
for and landed, and a weekly rhythm. Where the two disagree, this one is newer.

## Why

On 2026-11-10 a survey found seven series in flight, three batches waiting at the review
gate, and nothing from the v2 pipeline shipped. Work was being done; it was not being
finished, and nobody held the whole picture. The same day showed the costs of the current
way of working:

- every task session started cold and needed the publication's state explained again;
- four sessions changed `xword-ocr` and `blitz` in one day, each measured only on its own
  publication;
- merges went in on one session's own report that its tests passed;
- the V3 restructure stayed deferred because nothing connected it to the week's work.

## The layers

| Layer | Who | Holds | Talks to |
|---|---|---|---|
| Owner | Alex | decisions, merges, publishing, the quick human look | the project manager |
| Project manager | one long-running chat | the board across publications, the week, now-versus-V3 | the owner; managers; the dev lane |
| Batch manager | one per publication with a live batch | that publication's repo, run folder and batch | the project manager |
| Pipeline dev lane | developer, tester, reviewer (`roles.md`) | `xword-ocr` and `blitz` code | the project manager |
| Community | volunteers on the review site | answers to questions | the review site only |

The owner works with the project manager and in the web tools. The owner answers a
session directly only when it is stopped at a permission prompt.

## Batch manager

`roles.md` calls this the OCR operator. The change is that it is a standing owner of one
publication across weeks, not a session for one run.

- **Owns:** the publication's repo and its `-scans` twin, its fix file and ledger, its run
  folder (outside any checkout), its batch on the review site, and the publication's
  memory.
- **Runs the publication's week:** run or re-run what is invalidated, triage, make the ship
  record, prepare the Monday drop, prepare the Friday ship.
- **Must not:** change pipeline code; type puzzle content; merge; publish to the live site;
  send anything to gxd; change a rule the owner set. Each of those is a request upward.
- **When the pipeline fails a kind of puzzle:** files it with the dev lane (below) and
  carries on with the rest of the batch.
- **Picks up from:** this charter, the publication's memory, and its last report. A manager
  is a fresh session each time, so anything not in those three is lost.

### The manager's report

One file per report in the publication repo (`manager/YYYY-MM-DD.md`), same shape every
time, so the project manager's board is a roll-up:

1. Counts per queue (held on a question, not checked yet, broken in the pipeline, ready to
   ship, shipped), and the change since the last report.
2. What ran, and what it cost (model tokens, GPU hours) against what was projected.
3. Kinds of failure still open, ranked by puzzles, each with its issue link.
4. At most three decisions for the owner, each with a recommendation.

The queues are the ones the batch page shows (`ship.md`, "The queues"); the report quotes
the ship record and never counts for itself.

## Pipeline dev lane

`roles.md` defines the developer, the tester and the reviewer. This is how work reaches
them and how it lands.

- **Intake.** A kind of failure is a GitHub issue on `xword-ocr` or `blitz`: what goes
  wrong, at which milestone, how many puzzles in which publications, three example ids.
  Batch managers and the project manager file them; nobody fixes shared code without one.
- **Triage, Mondays.** The project manager ranks open issues by puzzles unblocked across
  all publications, and marks each **survives V3** or **throwaway**. V3's slices are issues
  in the same list. A slice is pulled in when it unblocks more than the patch it replaces,
  which is how the restructure gets built without a stop-the-world rebuild.
- **One writer per area.** Harvest and regions; parts and assembly; the text step and the
  reviewers; triage and ship; the views. Two sessions never change one area at once.
- **A regression set.** A small fixed sample per publication with reviewed truth (the
  tester's eval set). Every pipeline PR reports its effect on every publication's sample,
  not only the one that prompted it.
- **Review before merge.** A reviewer session that did not write the change reads the PR
  cold and reports to the owner. The owner merges.
- **Merge windows.** Pipeline changes merge on Tuesdays and Thursdays and never during a
  run, so a run records one code version.
- **Fixes apply forward.** A new check or evidence field applies to new runs; old output is
  not back-filled unless it is mechanical and cheap.

## The week

| Day | What happens | Who |
|---|---|---|
| Monday | **Drop**: one new packet goes up with its ask. Dev-lane triage. | managers publish (owner approves); project manager triages |
| Tuesday | Merge window. Review window opens. | owner merges reviewed PRs |
| Wednesday | **Owner's pass**: about 20 minutes on held-on-a-question and spot-checks. | owner, on the batch page |
| Thursday | Merge window. Runs for next Monday's drop start after it. | owner; managers |
| Friday | **Ship**: import decisions, make the ship record, publish status; the week's numbers; branch cleanup. | managers; project manager reports |

What the community is asked each week is the Monday drop's held-on-a-question queue.
Broken puzzles are shown with their reason but are not asked of volunteers until the site
gives them something to do other than retype (draw a box to re-read, request a better
scan).

## What only the owner does

Merging; publishing to the live site or its bucket; anything to gxd; changing a rule
(ship rule, publication rules, editorial rules); spending past the week's token budget;
starting a new publication.

## Standing decisions these roles rely on (2026-11-10)

- An AI reviewer's Ready with a passing ship check counts as the one Ready needed to ship.
  The owner's decision overrides either way.
- GAMES goes to gxd as one merge request for the whole series; milestones before then are
  shown on the EPP site.
- The batch page asks people for held-on-a-question first; an AI review alone never makes
  a puzzle "Reviewed".
- The scan is the proof. Run outputs are work in progress; back up model outputs, not
  rendered images.

## Open questions

1. May a PR that is green and has a reviewer's report merge without asking, inside a merge
   window? Today every merge is asked for.
2. What is in the regression set: how many puzzles per publication, and who keeps its truth
   current?
3. A weekly token budget per publication, so a manager knows when to stop and ask.
4. Whether one manager can hold two small publications (NY World and Bell).
5. Whether the manager's report belongs in the publication repo or on a status page on the
   EPP site, where it would also serve as the public milestone record.

## Starting state

- **Collegian**: first manager. Run2 is in progress (started 2026-11-10); its first report
  is the run2 result.
- **GAMES**: second manager. 1977-79 has 35 shipped; 1980-82 is the first Monday drop.
- **NY World, Globe, S&S, Bell**: no manager until one has a live batch.
- **Dev lane**: the first issues are the kinds left open by Collegian run2 (173 puzzles with
  a clue list never read), the reviewer recording whether a question is for a person or
  points at a stage, and the first V3 slice still outstanding (a `blitz batch` that owns run
  names and the registry).
