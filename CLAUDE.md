# blitz: notes for Claude

## The goal: a correct xd file, with its proof visible

Every puzzle the project produces is an xd file that should be correct, and the evidence
for it is the OCR, the reviewers' changes and comments, and the original scans. The review
page (src/blitz/proof.html, live at blitz.xwordapp.com/review/) is meant to be read as a
proxy for the xd file: everything in the xd must be visible there, with its proof.

- **No hidden data.** If a value is in the xd, the page must show it: title, author,
  byline, every clue, every answer, black squares, and the puzzle's notes. A value added
  along the way is fine, but the page must say where it came from (which reviewer, a hand
  fix, a typed grid, a pipeline repair).
- **When there's no straightened image** (a grid typed by hand), show the scanned page
  beside our grid rather than nothing.
- **Decisions are notes**, shown on the page and kept in the xd (e.g. "two grids stacked
  here to keep the printed numbering").

Publishing reviewed puzzles to the site: build their packets with xword-ocr's
`task-packets --current-review`, then `blitz site-publish`.

## The pipeline: runs quietly in the background

Agents run the pipeline and fix its problems cheaply, from what the milestones recorded:
signals, diffs, a crop or two. They never read a puzzle again from the source image. When an
agent can't fix something, a person goes straight to the right stage with the right tool, and
walks back through the stages to the cause:

| Symptom | Start at | Walk back to |
|---|---|---|
| A few odd answers or clues | the proof page: what the OCR read, beside the crop | the reading of that clue or key square |
| Title or metadata missing or wrong | the proof page: the header and its evidence | assembly (what was linked), then parts (what was found in the box) |
| Clues or key missing | assembly and layout: the boxes on the page | regions, then harvest (the page was never found: locate it) |

- **Milestones.** The pipeline is a series of named milestones: harvest, page OCR, regions,
  parts, assembly, text step, headers, proof packet, triage. Each writes a durable output in
  a documented format, which agents read and the visual tools render. Read a milestone's
  output; don't recompute a stage to inspect it.
- **Run once; re-run only when invalidated.** Each milestone records what it was made from
  (code version, upstream outputs, decisions) and is reused until one of those changes. A
  person's diagnosis invalidates its stage and the stages after it. A tool that recomputes
  everything every time is a bug to fix, not a cost to live with. (GAMES 1977-79, 2026-10-17:
  every packet build re-assembled all 81 puzzles, about 5 minutes, when only assembly's code
  had changed.)
- **Every milestone has a view, and the views form a chain.** Each view links to the stages
  before and after it for the same puzzle and the same place on the page: proof page,
  assembly, parts and boxes, page and regions, harvest. An exception opens at the stage its
  symptom points to.
- **People work in those views**, never in chat or a terminal (the north star, below).
- **Iterate on views fast.** Design in the lowest-friction loop: an auto-reloading local
  server over existing milestone output, where an edit shows in seconds. Don't rebuild
  packets or republish to see a design change; publish when the design is settled.

## The north star: people work in our web tools, not in chat or a terminal

The project builds powerful visual tools and repeatable processes, so that a person spends
their time on judgement, not on reading puzzles. Every session, and every brief written for
another session or agent, keeps to these rules:

- **The person's interface is our web tools**: the review site (blitz.xwordapp.com/review/:
  the proof page, Browse, the batch page) and the watch page (`xword-ocr watch`). Whatever a
  person should look at shows there, with what they need to judge it at a glance: a thumbnail
  or a crop of the scan, the reason, and a link into the proof page at the right row
  (`?p=<id>&k=<row>`).
- **Whatever a person should do is a button there** that records a decision with its source
  (decisions.jsonl, the games ledger, the site's database). Never offer a chat list, a bare
  archive.org link or a command line as the way to see or act. Chat says where to look ("4
  drops, under Dropped on Browse"), not what's there.
- **A slice is done when its result is visible and actionable in those tools.** If the page
  for it doesn't exist yet, the slice builds the smallest version of it, or extends the
  closest existing page. "Backend now, page later" leaves chat to fill the gap.
- **Repeatable, not one-off.** Results come from the pipeline into files and the site, the
  same way next time, never assembled by hand for one conversation.
- **Fix the process, not the puzzle.** Agents go after kinds of failure, not puzzles; a
  person's input is a diagnosis of which stage went wrong, which restarts the pipeline from
  there (blitz design/games-7779-next.md), not a correction typed into one puzzle.

## Where things are

- How the repos fit together and what's next: design/restructure.md.
- The maintainer's loop: MAINTAINING.md. Volunteers: VOLUNTEER.md, HAND.md.
- Each publication's data lives in its own repo beside this one (../judge, ../games).
