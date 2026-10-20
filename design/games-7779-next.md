# GAMES 1977–79: where it stands and what's next

Written 2026-10-17; updated 2026-10-18 with the triage plan (agent-driven, by kinds of failure)
and the exceptions queue (a diagnosis per stage, not line edits). The goal is unchanged: every
puzzle from hands-off assembly to an xd file in the games repo, nearly hands off, with tokens
spent only where they buy the most. The baseline to beat is an agent reading every puzzle.

## Next round: start here (written 2026-10-20)

The sections below "Where it stands" record how the plan was made (2026-10-17/18). This
section is the current state and the agenda. Start a fresh session with this section as
its brief; the long sessions that built this round are out of context.

### State on 2026-10-20

- **The v2 pipeline on main** (xword-ocr, blitz, games):
  - assembly only links text, and `headers.propose` guesses the headers;
  - the text step's findings are records;
  - a second clue set is carried as `^Easy` clue metadata, plus a Feature header;
  - triage puts each puzzle in one of three states: **Needs work**, **Ready for review**,
    **Reviewed** (memory: review-dispositions);
  - the restart loop and agent remedies ("check these, fix what you can, flag the rest");
  - crowd decisions reach the import under the ship rule: one Ready and no Not ready ships;
    any Not ready comes to the maintainer;
  - the batch page, local and hosted.
- **Runs** (games `pipeline/triage/runs.json`):
  - **run14-feature is current**, and it's what's published on the site: 76 open puzzles and
    6 dropped.
  - **run15-restart** is a trial carrying the restart loop and dispositions: 10 Needs work, 64
    Ready for review. It becomes current once the PRs below merge.
- **Decisions:** 2 Ready, both the maintainer's (1977-09-01 L026 and L032). Nothing imported;
  `games/xd` has no GAMES 1977-79 puzzles yet.
- **The review site:** `/review/` opens a batch landing page. GAMES 1977-79 is there with its
  batch page and proof pages. The old v1 pages are gone.

### Agenda, in order

1. **Merge the stranded work:** EveryPuzzleProject/xword-ocr#35, EveryPuzzleProject/blitz#37,
   EveryPuzzleProject/games#13. These are commits pushed after their PRs (xword-ocr#34,
   blitz#36, games#12) had been merged: key squares recorded, Not a crossword from the batch
   card and proof page, the Easy-only view.
2. **Make run15-restart current and republish** its proofs (`blitz site-publish`) and the batch
   snapshot (`blitz site-publish-batch`, taken from a running watch). Keep the drops marked.
3. **Work the 10 Needs work** on the local batch page: run the remedy agent, then the harvest for
   the pages it requested. Whatever is left is for the maintainer, with each diagnosis on its
   card.
4. **Review the Ready ones:** the maintainer, and volunteers if invited. Run `blitz site-import`
   to bring site decisions into the ledger.
5. **Decide the Notes rule** (a batch page tool), and how Feature reaches the gxd export
   (`Category:` is the candidate; mention it to Saul).
6. **Import** the shipped puzzles into `games/xd` (`import-batch`, ids assigned last), then
   open a games PR.
7. **gxd export:** `^Easy` lines kept, Notes by the rule, Feature mapped, gaps labelled.
8. **Fill in the blog post's part 3 numbers** (blitz `claude/v2-pipeline-blog`).

Then **v3, before the rest of GAMES** (design/restructure.md: harvest standalone, blitz
orchestrates, the viewer without the code, the internal control room and the public review
site). GAMES 1980-82 is the first v3 batch, run as a pure orchestration session: it gives the
per-puzzle cost baseline against the 10% target.

### Known defects (not blocking 1977-79)

- **1979-09-01 L064:** about 40 Hard clues never read; a request is raised.
- **Every Ornery puzzle:** a page number ("38") stuck to an Easy clue. The reading should drop
  page numbers from clue lines.
- **Region boxes that start at the grid** can cut off a title or byline above it. If this
  recurs, pad the regions upward.
- **The key reader** read a column of a hand-lettered key's black squares as letters (three
  run15 puzzles). It's recorded and shown now, but the reader itself isn't fixed.
- **Hands-off runs ignore earlier box decisions** from the harvest tool. In v3 the
  orchestrator applies every standing decision to every run.

### How to run it locally

```
uv run xword-ocr watch --out harvests/games-7779 --start 1977-01-01 --end 1979-12-31
```

Run it from `~/Projects/xword-ocr`, with xword-ocr, blitz and games pulled. The batch page is
at http://127.0.0.1:8765/batch/. It uses `../games/fixes/fixes.toml` for the ledger and run
registry, and the blitz checkout beside xword-ocr for the proof page.

**When several sessions run at once:** merge a session's PRs only when it reports done. A
session that keeps pushing to a branch after its PR is merged strands those commits (that's
what item 1 recovers).

## Where it stands

- **81 puzzles** (the 75 from the box review plus 6 extras) went through assembly, the text
  step and proof packets. They are live on the review site, https://blitz.xwordapp.com/review/
  (batch `games-1977-79`, provisional ids such as `games1977-09-01-L026`):
  - packets: `xword-ocr/harvests/games-7779/proof/run4`;
  - text step answers: `harvests/games-7779/textstep/run4-7779`.
- **The text step** is the Fable agent `xword-text`. For each puzzle it:
  - reads the lines printed near the puzzle (L1, L2, …);
  - says which line each xd header comes from;
  - labels the other lines and corrects their text;
  - tags fill-in blanks, kept as printed;
  - writes a one-sentence verdict, only when something is notable.

  Headers come from the lines by fixed rules (`xword_ocr/headers.py`, mirrored in
  `src/blitz/proof.html`). The full run cost about 7.8k tokens per puzzle, 6% of the weekly
  Fable limit for the 81.
- **The proof page** shows:
  - the xd's headers in a fixed order, each with its evidence: crop, then OCR text, then the
    value, naming the rule when one changed the text;
  - the other printed lines, each with Keep / Discard and a label;
  - the text step's verdict and a linked list of what it did;
  - a navigation rail of edits and doubts;
  - FITB pills for fill-in blanks.
- **Assembly only links** (xword-ocr #18, 2026-10-18). Every heading and text block near a
  puzzle reaches the packet whole, read column by column. `headers.propose` makes the first
  guess at Title, Byline and Number, and the text step checks it. First guesses, measured on
  the 81 against run4's reviewed values: titles 54 → 62, bylines 75 → 77, numbers 79 → 80.
  The header diff is a private artifact: https://claude.ai/artifact/Ej1vFoGHQWTXSpoicbUiTu
- **run4's reviewed headers have errors.** On pages a warmup shares with an Anglaise cryptic,
  run4 swapped the two puzzles' titles and bylines, and the text step didn't catch it. Don't
  treat run4 as ground truth there.
- **In progress:** re-running the text step on the puzzles whose printed lines changed under
  #18 (run6, about 64 of 81), then republishing the batch.
- **Merged:** xword-ocr #15–#18; blitz #10–#14; games #4–#6. `games/editorial.md` holds
  GAMES's conventions (blanks, picture clues, headings).
- **Nothing is in `games/xd/` yet.** No puzzle has been reviewed on the site.

## The plan: send agents after kinds of failure, not puzzles

The model is how 1979-07-01 L042 got fixed:
1. One broken puzzle was traced back through the stages to its cause, using the watch page's
   data.
2. The fix went into the tool.
3. The batch was re-run as compute only and the result was diffed.

No agent read the other 80. Cost should grow with the number of **failure kinds** in a batch
(maybe 5–10), not the number of puzzles. A person diagnoses only the one-offs, and records a
diagnosis, not a correction.

### 1. Triage in code (zero tokens)

After the text step, give every puzzle a decision: *ship as is*, *glance*, *needs attention*
or *not a crossword*. Back each decision with **reason codes** taken from what the pipeline
already records:
- how well the clues fill the grid;
- whether a key matched, and how many key letters were unread;
- list and page requests;
- the text step's unsure items and verdict;
- headers with no evidence line, or with a value typed by hand;
- printed lines that changed between runs.

Example codes: `title-from-pointer`, `clues-missing-A`, `key-unread>3`,
`header-line-swapped?`.

Keep **accepted gaps**, which ship labelled as missing, apart from **defects**. Accepted gaps
include a cryptic with no printed key, no printed title, and the second "Easy" clue set.

A first hand-made pass gave 21 ship / 23 glance / 33 needs a person / 4 not a crossword. That
pass predates #18, and its "needs a person" count is inflated: warmup cryptics were counted as
missing keys, and a few misread key squares were counted as a full review.

### 2. Free cross-checks (zero tokens)

These catch what the pipeline is confidently wrong about, like the swapped headers above:
- **gxd's clue database.** A clue and answer pair seen before is strong confirmation. A near
  miss (same answer, a clue one or two letters off) points at an OCR error.
- **Bylines against the catalog's known constructors** (`catalog/people/`).
- **Crossings against the key**, and header consistency across the issue (two puzzles on one
  page shouldn't share a byline unless printed so).

### 3. Agent investigates groups

Group the flagged puzzles by reason code. Per group, an agent takes one or two examples and
traces the failure back through the stages with the watch page's data (`/api/parts`,
`/api/assembly`, the boxes view), then does one of two things:
- **fixes the tool:** add a test, re-run the batch as compute only, diff headers, lines and
  clues against the last run, and check the evaluation set (`evalset.py`) for regressions
  (Judge too, for overfitting); or
- **sends the puzzle back with feedback** through the requests ledger: read the page again,
  this list continues on the next page, this region box splits the puzzle.

This step needs:
- a short runbook for the agent: how to trace a puzzle, where each stage's data is, what a
  good diff looks like;
- the text step's requests routed into the games ledger (`textstep.route`; 85 are waiting).

### 4. Cheap single questions, then an audit

- For a flagged puzzle that fits no group, ask one small yes/no question with one crop, on a
  cheap model ("Is the line in this crop the title?"). This is not a review of the puzzle.
- Per batch, an agent checks a fixed small sample of *ship as is* puzzles against the scans,
  to measure the error rate and catch systemic mistakes.

### 5. The exceptions queue: diagnose a stage, restart from it

What's left for a person is a short queue, and an item in it is a **diagnosis**, not a line
edit. Each item shows the puzzle's chain with evidence:
1. the page with its region boxes;
2. the parts in the boxes;
3. what assembly linked;
4. the printed lines;
5. the headers, the clues and the key.

It asks one question, **where did it go wrong?** Each answer names a stage and a restart:

| Diagnosis | The person | Restarts from |
|---|---|---|
| Region box wrong (cut off, split, two puzzles in one) | adjusts the box (the watch page does this now) | parts → assembly → text step |
| Wrong text linked (a title went to the neighbour) | points at the line that belongs | assembly → headers |
| A header from the wrong line | picks the right line as evidence | headers (no tokens) |
| OCR misread a region | asks for a re-read (higher resolution, second OCR) | the page's OCR → onward |
| Clue list continues elsewhere, or a page is missing | requests the page | harvest → onward |
| Key misread | flags the squares (the key-squares page) | key reading |
| Not a crossword | drops it | — |
| Printed that way (misprint; a rebus with digits in the grid) | writes a note | nothing: ships as printed, noted |

How a diagnosis is handled:
- It goes into `decisions.jsonl` with who made it and why, and shows on the review page (no
  hidden data).
- It marks that stage and everything after it stale, and the pipeline re-runs from there. The
  stage fingerprints from pipeline v2 should make this mostly bookkeeping. The text step
  re-runs only for puzzles whose printed lines changed.
- A diagnosis that recurs becomes a reason code for step 1 and a group for step 3. The
  person's diagnoses are the training signal for the automatic loop.
- Retyping text stays the last resort, for true one-offs.

**Exists already:** the watch page's box and grid fixes, the requests ledger and its settle
step, the relink button, the stage fingerprints. **Missing:** the diagnosis picker tied to a
stage, and invalidation that reaches through to the text step and the proof packets.

### 6. Batch review page

The batch page becomes the home of steps 1–5. It shows:
- the triage counts;
- the groups, with what the agent found and fixed;
- the exceptions queue;
- *ship* / *hold* / *drop* per puzzle, saved where the import reads them (the games ledger or
  the site's database).

Prototype, from before the plan: https://claude.ai/artifact/WpFkspcnz9HXNSzNLAZtyN. It links
each "not sure" item into the proof page (`?k=clue:A68`).

### 7. Then: Notes, import, export, feedback

- **Settle the Notes rule** before the first export: which line labels go in gxd's Notes
  (instructions, test-solver, intro, credit, kind). Show its effect across the batch first.
- **Import.** Shipped puzzles become xd files in `games/xd`, ids assigned last, including
  edits from the proof page (`site-import`; keys `clue:*`, `line:Bn`, `ev:<field>`,
  `keep:Bn`, `label:Bn`, `meta:<field>`, `fitb:<clue>`). Picture-clue drawings
  (`pictures/<clue>.png`) travel with the puzzle, unused until xd can carry images.
- **gxd export.** The export rewrites typography:
  - tagged fill-in blanks become `___`;
  - other long dashes become `--`;
  - curly quotes become straight.

  Notes follow the rule above. Gaps are labelled, never guessed. Mind gxd's standard (clean
  data): *ship* stays conservative.
- **Feedback loop.** Problems found later (gxd contributors, crossref's "report a problem")
  come back as diagnoses on the puzzle in the pipeline, the same as step 5, never as hand
  edits.

### After GAMES 1977–79: 1980–82

GAMES 1980–82 is harvested (`harvests/games-8082`) and was measured on 2026-10-15: hands-off
assembly found 105 of 106 reviewed puzzles. It hasn't been through the text step. It is the
first batch to run the whole loop above as intended, and a fair test of the triage rules on
puzzles they weren't tuned on.

## Open tool issues

- **The text step's requests** aren't routed to the games ledger (`textstep.route`). Step 3
  needs this.
- **Headers:**
  - The "PENCILWISE" section banner is taken as a title.
  - A title printed on two lines ("Warmup Puzzle" / "for New Solvers") is read as two
    headings, so the first guess takes one of them.
  - A title and byline read as one line, followed by a clue-list label ("Hard Clues"), get the
    label glued on. The text step fixes it; the reading should too.
- **Text and regions:**
  - An intro split across two harvest region boxes reads as two blocks, each column by column
    on its own.
  - Text on a clue list's page links by distance, so a neighbouring puzzle's intro can come
    along as notes. The text step labels it "other-puzzle"; tighter linking would save tokens.
- **The key reader** forces digits into letters on purpose (0→O, 2→Z, 5→S). That's wrong only
  for a rebus key like 1979-07-01 L042 ("4-Warned Is 4-Armed"). A diagnosis "printed that way"
  covers it for now.
- **Clue reading:**
  - A long-dash blank that ends a line ("Walking ——") isn't put back by the reading.
  - Long clue lines' crops sometimes stop mid-clue, losing ": 2 wds." tails.
- **The giant "World's Most Ornery" puzzles** print a second (Easy) clue set that isn't
  captured.
