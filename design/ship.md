# Shipping a batch: from reviewed puzzles to xd files to a gxd export

Built 2026-11-10 for GAMES 1977-79, the first v2 batch to ship. It is the last milestone of a
batch and lives in blitz (`src/blitz/ship.py`), since everything after the packet is blitz's.
It reads what the earlier milestones recorded and works nothing out about a puzzle itself.

```
uv run blitz ship games --proof ../xword-ocr/harvests/games-7779/proof/run15-restart --batch games-1977-79            # dry run
uv run blitz ship games --proof ... --batch games-1977-79 --write                                                     # write it
uv run blitz ship games --proof ... --batch games-1977-79 --publish                                                   # ship.json to the site
uv run blitz ship-export games --dest ../blitz-work/gxd-export-games-1977-79 --pages                                   # the gxd export, as files
uv run blitz ship collegian --proof <run's proof packets> --batch collegian-1976-81 --record                          # status only: the record, nothing shipped
```

## What it reads

| what | where | made by |
|---|---|---|
| the puzzle as reviewed | `<harvest>/proof/<run>/<pid>/puzzle.xd`, `review.json` (xd_fp, matches_xd), `ocr.json` (page, printed lines and their labels) | xword-ocr proof packets |
| reason codes and the ship check | `<harvest>/triage/<run>/triage.json` (`reasons[].code`, `ship.ok`, `ship.incomplete`) | xword-ocr triage |
| decisions | `<pub>/fixes/decisions.jsonl`: `proof:<pid>` (one per reviewer), `batch:<pid>`, `drop:<pid>`, `setaside:<pid>` | the batch and proof pages, agents |
| helpers' decisions | the review site (`blitz site-import`, or `--decisions FILE`) | the hosted proof page |

Helpers' Ready / Not ready are taken into the ledger first (`proof:<pid>` by `<helper> (review
site)`, the shape xword-ocr's `take_decisions` writes), so the ledger is the whole record.

## The ship rule

One function, `ship.standing()`. Its options are `ship.Rule`, read from the publication's
`fixes/ship-rule.json` and overridden on the command line.

1. The owner's own latest decision wins: the later of the batch page's Ship / Hold and their
   own proof page's Ready / Not ready. A proof record is the owner's when its `via` is neither
   `review site` nor `agent review` (their own tools), or when it was made on the review site
   under one of the names in the rule's `owner` list. It overrides a Not ready by anyone else,
   earlier or later; the reason then says so ("over a Not ready by ..., given after it").
2. Otherwise any Not ready that stands holds the puzzle for the owner: a person's, whatever
   version it was given on, or the AI proof reviewer's on the current version.
3. Otherwise one person's Ready ships it.
4. Otherwise it waits for a Ready.

A Ready counts only for the version of the puzzle it was given on (the packet's `xd_fp`, or one
of `xd_fp_same`). An AI reviewer's Not ready goes stale the same way (since 2026-11-11): once a
run has changed the puzzle's xd, what the AI asked about the earlier version no longer holds it,
its questions aren't asked, and the puzzle is held as `proof-stale` (not checked yet) until
someone reviews the new version. A person's Not ready does not go stale: it is a diagnosis, and
it stands across versions until the owner decides. One test decides both, `ship._stale()`, and
whose record it is comes from `ship.kind_of()` (the ledger's `via` and `by`). A stale decision
stays in `said`, marked `stale`, so the batch page shows it as given on an earlier version.

The version is the xd's fingerprint, nothing else. An AI Not ready on an xd the run left
unchanged still stands, even when a publication rule has since answered what it asked; the
reviewer's next round on that puzzle replaces it (each reviewer's latest record is the one
counted).

| option | default | what it does |
|---|---|---|
| `ai_ready` | `off` | `both`: with no person's Ready, the AI proof reviewer's Ready and a passing ship check together count as the one Ready. `either`: one of them is enough (xword-ocr docs/ship-gate.md's design). GAMES: `both`, the owner's decision of 2026-11-10. |
| `hold_codes` | `["clue-typed"]` | triage reason codes that hold a puzzle whoever said Ready. `clue-typed` (a clue the text step supplied with no OCR reading) doesn't exist in triage yet; when it does, such puzzles are held with no change here. |
| `owner` | `[]` | the owner's own accounts on the review site. Who the owner is isn't in the code: it is this list in the publication's `fixes/ship-rule.json` (GAMES: `oops6498`, confirmed by the owner 2026-11-10). The site's copy of the ship record shows such a decision as "the owner", a helper's as "a helper". |
| `ignore` | `[]` | review-site accounts whose decisions don't count (GAMES: `walkthrough test`, a scripted usability test that left a Ready and a Not ready on the live site). |

A puzzle the rule passes can still be held by the import, each with its own reason:

| reason | meaning |
|---|---|
| `edit-unrecorded` | an edit with no whole record of what it changed (The record of every edit, below) |
| `incomplete` | the ship check found missing or empty clues, an unsolved grid, a partial second clue set: no Ready makes it whole. One exception since 2026-11-12 (`ship.filled_by`): an unsolved grid, when the edits that ship with the Ready give every square the check named its letter (a key square the packet left unread, read by a reviewer: a reading fix with its record), and only when a person's decision ships the puzzle (rule `owner` or `people`): an AI's Ready never lifts it with its own letter, under any `ai_ready`. The reason it shipped says so. An empty or missing clue is never made whole by an edit. It needs the finding's `cells`, which records made before xword-ocr named them don't have (GAMES run15-restart), so it takes effect for a batch at its next triage run |
| `packet-stale` | the proof packet doesn't show its xd: rebuild the packet |
| `proof-stale` | all that was said (a Ready, or an AI's Not ready) was on an earlier version of the puzzle |
| `edits-differ` | two reviewers changed the same thing two ways |
| `edits-unapplied` | a proof-page edit the import doesn't apply: a line's label or keep (`line:B3`), a header's evidence line (`ev:title`), a fill-in blank, a rebus square; in a linked-ends puzzle, an edit that can't be applied safely (Linked ends, below) |
| `xd-exists` | `xd/` already has another file under its id |
| `candidate-undecided` | the packet records a candidate clue list and no reviewer who said Ready has decided it (next section but one). A question, not a breakage |
| `candidate-partial` | a candidate was taken into the puzzle (as the clues, or as a second set) and doesn't cover its slots |
| `mark-invalid` | a misprint mark (`typos`, `key_corrections`) that can't be taken: malformed, or naming words the row doesn't have (The record of every edit) |
| `misprint-edit` | a row marked as a misprint whose edit would ship it other than as printed |
| `proposal-waits` | a helper's or a guest's key correction, with their own edit to the square: a question for the owner |
| `mark-disputed` | an AI reviewer's misprint mark on a row a person edited, disagreeing with the edit: a question for the owner |

The rule's own reasons: `owner-hold`, `not-ready`, `no-ready`, `needs-work` (no Ready that
counts, and triage's disposition isn't ready), and each hold code. `needs-work` takes the place of
`proof-stale` as it does of `no-ready` (since 2026-11-12): a puzzle whose new version triage says
needs work is the pipeline's (broken, with the stage triage's blocking parts point to), whoever
reviewed an earlier version; before, it showed under "not checked yet", which asks a person to
proofread it. What was said stays in `said`, marked `stale`, and in the reason.

## What it writes (publication repo)

- `xd/<xdid>.xd`: the packet's `puzzle.xd` with the Ready reviewers' edits applied (clue text,
  key squares with the answers worked out again, the header fields). Its headers are the
  packet's. A misprint in a clue or a header stays as printed; a misprinted key letter is
  corrected, with a line under `Answer key corrected:` in its notes (the next section).
- `fixes/xdids.tsv`: ids pinned for puzzles that had none. A puzzle keeps the id
  `pipeline/ids.tsv` or `fixes/xdids.tsv` already gives its place on the page.
- `provenance.jsonl`, append-only, the last row for an xdid stands:
  `{xdid, pid, batch, run, packet, packet_xd, xd, shipped: {at, rule, ai_ready, by, why}, said:
  [{who, kind, answer, at, stale}], edits: {applied, from, records, packet}, corrections, notes,
  check, codes, sources: {grid, clues, key}, printed: [{label, text}]}`. `kind` is owner, helper,
  ai or check; `printed` is the kept printed lines with the text step's labels, which the
  export's Notes rule picks from; `edits`, `corrections` and `notes` are the next section.
- `gxd-exports.tsv`: judge's columns (`gxd_id xdid date number gxd_mr exported proof_url
  package_url scan_url ai_reviewed person_reviewed credit`), rebuilt from provenance.jsonl;
  `gxd_mr` and `exported` are filled by hand after a merge and kept.
- `pipeline/ship/<batch>.json`, the batch's ship record:
  `{batch, run, packets, rule, at, counts: {puzzles, shipped, shippable, held, out, held_by,
  ships_with, queues, reviewed, spot_check}, groups, spot, puzzles: [{pid, xdid, title, date,
  status, reason, rule, ships_with, why, said, check, queue, group, order, reviewed, spot_check,
  asks, also, broken}]}`. `status` is shipped (in `xd/` as it stands), shippable (passes, not
  written), held, or out (set aside, not a crossword). `ships_with` is the smallest `ai_ready`
  setting under which the rule passes the puzzle. Helpers' names are left out. The queue fields
  are the next section.

## The record of every edit

The owner's rule (2026-11-11): blitz is faithful to the original. Suggesting or making an edit is
fine; an edit with no record is not. Every change has a record of what it was, what it became,
who or what changed it and where to see it, and the record travels with the shipped xd (the
puzzle's `provenance.jsonl` row), not only in the ledger or on the proof page. There are three
cases, and where each is applied differs:

| case | what it is | the xd `blitz ship` writes | where it is recorded |
|---|---|---|---|
| 1. a reading fix | the scan or the OCR was bad: the reviewer makes our text match what was printed (a clue, a header, a key square) | applied | `edits.records`, class `reading` |
| 2. a misprint in a clue or a header | the scan is good and the original has a mistake | **as printed**: not applied | `corrections`, a proposal; `blitz ship-export` applies it and writes the editorial note into the exported xd |
| 3. a misprinted answer-key letter | the printed key has a wrong letter (the clue and the crossings call for another) | corrected, with an editorial note in the xd's notes | `edits.records`, class `key correction`, with the note; the row's `notes` |

The key is evidence for the answers rather than part of the puzzle, so its misprint is corrected
early and said (the project's standing rule for keys); a clue or a header is the puzzle itself,
so the publication's xd keeps what was printed and the correction is made where the puzzle
leaves for gxd.

A reviewer says a thing is a misprint in their review: a clue's or a header's in `typos`, `[{key,
printed, meant}]` (`clue:A71`; a header under the key the reviewer uses for its row, `ev:title`,
`ev:byline`, `ev:number`, or `meta:title`); a key letter's in `key_corrections`, `[{key:
"cell:r3c6", printed, corrected, edited, crop, text}]`, as xword-ocr's proof reviewer writes them
(xword-ocr docs/ship-gate.md). `edited: false` means the packet's grid already had the corrected
letter and the reviewer only records that the key prints otherwise. A `typos` entry with a
`cell:` key is taken as a key correction too. A `cell:` edit with neither is a reading fix.

`ship.edit_records()` makes the records, from the packet's `puzzle.xd`, that xd with the Ready
reviewers' edits applied, and those Ready records.

**`edits.records`**, one per value that ships changed: `{key, what, class, before, after, by, kind,
via, at, stage: "proof review", why, evidence: {proof, image, box}}`.

| edit | key | `before` | also recorded |
|---|---|---|---|
| a clue's text | `clue:A12` | the clue in the packet's xd | the clue's crop in the packet (`evidence.image`: the clue's own page image, `ocr.clues[..].image`, else the packet's `clue_image`; `box`) |
| a second-set clue | `clue:A12^Easy` | that line in the packet's xd; for a line a candidate's `second:<Key>` decision wrote, the candidate's own text (`written_by`) | |
| a key square | `cell:r3c4` | the letter in the packet's grid | `words`: each answer through it, before and after; `evidence.image`: the key's page |
| a header | `meta:title` (author, byline, puzzle_number, editor, feature) | the header in the packet's xd, "" when it had none | `header`: its name in the xd |
| a decision that isn't a value of the xd (a candidate clue list's) | `candidate:<id>` | "" | the clues it wrote, each as its own record with `decided_by` |

`by` is the reviewer as the ledger names them, `kind` owner / helper / ai / check, `why` their
comment on the row, `evidence.proof` the row on the proof page (`?p=<pid>&k=<key>`). An edit that
leaves the value as it was makes no record.

**Every applied edit has a class, and none is guessed:**

- `reading`: the reviewer commented on the row. The comment is the evidence that the page shows
  the new text; it is quoted in `why`, not parsed.
- `key correction`: a `typos` entry names the square (case 3).
- `decision`: not a value of the xd (a candidate list's decision, and the clues it wrote).
- `unclassed`: no comment on the row and no `typos` entry, so nothing says whether the reviewer
  fixed a reading or corrected the print. It is applied, and reported: `blitz ship` lists each one
  ("unclassed <pid> <key> by <reviewer>"), and the record says `unclassed`. Holding these instead
  would be one line; it is the owner's call.

**Case 2: `corrections`**, one per `typos` entry for a clue or a header: `{key, printed, meant, by,
kind, via, at, fits, says, evidence, edit}`. Nothing is applied. `fits` says what the export will
find: `printed` (the xd that ships has the printed word once: the export puts the word meant in
its place), `already` (it has the word meant and not the printed one: the text review had put it
right before any reviewer saw it, so the xd is not as printed there; the export writes the note
only), `unplaced` (neither, more than once, or the entry is incomplete: the export leaves it
alone and says so). `says` is the line the proof page draws ("A71 is printed 'cockail'; meant
'cocktail'.").

A reviewer names a misprint with no edit, and that is all the above. When ship meets both, an edit
and a `typos` entry for the same clue or header, what the edit says decides (words are matched
whole: "Tow" is not in "Towel"):

- the edit has the printed word: it is a reading fix and stands as it is. This is the reviewer's
  shape (xword-ocr proofreview): an earlier step had put the word right, so the reviewer puts the
  text back as printed and proposes the correction; or they fixed a reading elsewhere in a clue
  that also has a typo. The correction fits `printed`.
- the edit has the word meant, once, and not the printed word (an old-style edit toward the
  correction): the word meant goes back to the word printed, what is left of the edit is applied
  (its record is `unclassed`, with `beside`), and an edit that was the correction and nothing else
  leaves the clue untouched.
- the edit has neither: it is a reading fix like any other, and the correction comes out
  `unplaced`.

The reviewer's own text is kept on the correction as `edit`.

`blitz ship-export` applies them (`ship.corrected()`): each correction that fits becomes the word
meant in the exported xd, with the note `A71 is printed 'cockail'; corrected to 'cocktail'.` (a header: `The title is printed ...`), after the printed
lines the Notes rule takes. The export's `corrections.tsv` lists every correction and what was
done with it (`applied`, `noted`, `not applied`). The publication's xd is not touched.

**Case 3: a key correction.** The letter is corrected in the shipped xd: by the reviewer's own
`cell:` edit, or from their entry when they made none. The xd's notes get a block,
`Answer key corrected:`, one line each, naming the square, what the key printed and what it was
corrected to: the entry's own `text` ("The answer key printed 'C' at r3c6; corrected to 'D', which
the crossing clues require."), or, where it gives none, `The printed answer key gave 17 Across as RE (and so 2 Down as EMEERS), presumably
in error (E at row 3, column 4). It has been corrected to RB and EMBERS (B).`, the form of Judge's
notes. The record carries `misprint: {printed, meant}`, `note` and the entry's `crop` as
`evidence.image`; the lines are the row's `notes`,
which the gxd export adds to the puzzle's notes. When the packet's key already had the letter
meant (corrected before review), nothing changes and it is noted all the same (`stage: "before
review"`). A key correction that doesn't say what the key printed and what was meant, names no
square, or doesn't match the square doesn't ship. A `cell:` edit with a comment and no `typos`
entry is a reading fix; with neither it is `unclassed`, and listed.

**`edits.packet`** is what the packet had already changed before any reviewer saw it (the text
review's `corrections` in `review.json`): `{key, what, before, after, by, stage: "text review",
why}`, `before` being the reading the packet's `ocr.json` holds for that clue, printed line, key
square or header (`read: false` when it holds none). The xd's `Text-Review:` header says how many
there were; this is the list. These are not classed.

**On the proof page.** The packet's `puzzle.xd` shows neither the key notes ship adds nor the
corrections it holds back, so the ship record carries both per puzzle (`notes`, `corrections:
[{key, printed, meant, fits, says}]`) and "Notes in the xd file" draws them as two blocks that
say so: "Answer key corrected" (added when it ships) and "Corrections of the print, proposed"
(not applied here; the gxd export makes them).

**No record, no ship.** A puzzle is held as `edit-unrecorded` (the import's: broken) when
- an edit is to a clue or a square the packet's xd doesn't have, so nothing says what it
  replaced (before 2026-11-11 such an edit was dropped without a word);
- anything in the headers, the grid or the clues differs from the packet's xd with no edit
  behind it, or ships as something other than its edit;
- an edit sits beside a misprint entry that doesn't say what was printed and what was meant;
- a key correction has no whole record.

Puzzles shipped before this have rows with `edits: {applied, from}` alone. `blitz ship <pub>
--proof ... --backfill-records` lists the rows that would give them their records (the standing
row, its `edits` made again from the ledger and the packet, `backfilled: <date>`); with `--write`
it appends them and touches no xd. It can only do this for a puzzle whose xd in `xd/` is still
exactly what the ledger and the packet make.

Not recorded yet: a hand fix made upstream of the packet (the publication's `fixes.toml`, a typed
grid) reaches the xd inside the packet and is named in the xd's own headers and on the proof
page, not in `edits`.

**A person's own misprint mark (since 2026-11-13).** On the proof page a clue row and each row of
the headers table have "Printed this way, but wrong…", and the answer key has "A letter the printed
key got wrong…". They write the same `typos` and `key_corrections` into the person's review as the AI
reviewer's (the site keeps them in the review; `blitz site-import` and `from_site` carry them to the
ledger), so the three cases above apply unchanged: a clue's or a header's stays as printed and the
export corrects it; a key letter is corrected at ship with its note. The page accepts a mark only
when the printed words are in the row's text once, whole (what ship calls `fits: printed`); when
the reviewer had typed the correction, the page puts the printed words back (blitz ships what was
printed). Each mark shows on its row with what will happen to it ("Stays as printed here; corrected
to … at the gxd export").

**Whose marks take effect: the owner's rule, 2026-11-13, "Owner only for now".** A `typos` or
`key_corrections` entry takes effect when it is the owner's (an account in the rule's `owner` list, or
the owner's own tools) or the AI proof reviewer's (decided 2026-11-11): `ship.MARKS_COUNT`. Anyone
else's (a helper, a guest) is a **proposal**: kept in the ledger, carried as `proposals` (`{key,
printed, meant, what, says, status: "waiting for the owner", by, kind}`) on the ship record's row, the
as-shipped file and the provenance row, shown on the proof page and in the as-shipped view as
"Proposed: waiting for the owner", and never applied: `ship-export` reads only `corrections`, and a
key letter is not corrected in blitz. A helper who also changed the square to their proposed letter
holds the puzzle as `proposal-waits` (a question for the owner, at the square's row), since shipping
their edit would correct the letter on their word; on the page a helper's key mark leaves the square
alone. An account on the rule's `ignore` list counts for nothing, not even a proposal. (Later, not
built: an Accept button beside a proposal on the proof page, shown to the owner only, that writes the
proposal into the owner's own review as their mark; the batch page would list proposals per puzzle.)

**A marked row ships as printed** (the cold review, 2026-11-13, three passes). "The row check", below,
is: the edit to the row stands when it keeps the printed words once; when it has the words meant once
instead (and not the printed ones), those go back as printed; any other edit (the words meant typed
twice or in another case, the printed words gone) holds the puzzle as `misprint-edit`, since nothing
can tell which words are the misprint and the row would ship other than as printed. A mark says nothing
about the rest of an edit: that is classed on its own evidence (a comment on the row: a reading fix;
none: unclassed, listed for the owner). The whole rule, for a clue's or a header's mark; "own edit" is
an edit to the marked row by the marker, "another's edit" one by another reviewer whose Ready counts:

| who marked | mark | own edit on the row | another's edit on the row | no edit on the row |
|---|---|---|---|---|
| owner | valid | the row check; the correction is proposed for the export | the row check (the owner's mark governs the row, whoever edited it) | the correction is proposed for the export (`fits` printed, or already); the printed words and the words meant both absent: `mark-invalid` |
| AI reviewer | valid | the row check; the correction is proposed for the export | a person's edit is never changed, dropped or overridden by the AI's mark: where the edit keeps the printed words once, it ships as it is and the correction is proposed; otherwise held `mark-disputed`, a question for the owner showing the person's edit (with its comment) and the AI's mark (fourth pass, 2026-11-13) | as the owner's |
| owner, AI reviewer | malformed | `mark-invalid` | `mark-invalid` | `mark-invalid` |
| helper, guest | valid | the row check; a proposal waiting for the owner, never applied at the export | the other's edit ships as it is, with its own records; a proposal waiting for the owner | a proposal waiting for the owner; nothing changes (also when its words aren't in the row) |
| helper, guest | malformed | dropped, shown "not taken"; when it still names a clue or header and printed words: the edit stands only if it keeps them once, else `misprint-edit` | dropped, shown "not taken"; the other's edit ships as it is | dropped, shown "not taken"; nothing changes |
| ignored account | either | nothing (its Ready doesn't count, so its edits aren't applied) | nothing | nothing |

A key letter's mark (`key_corrections`, or a `typos` entry for a square): the owner's or the AI's is
corrected here with its note (case 3), or held `edit-unrecorded` when it doesn't match the square; a
malformed one is `mark-invalid`. A helper's or a guest's is a proposal; with their own edit of the square
to that letter it holds as `proposal-waits`; another person's edit of the square ships as it is.

**What a mark may hold** (fix B). Ship takes a mark only when its key names a clue, a header or (a key
letter) a square; its printed and meant (corrected) words are text of one line, with no tab or
control character, at most 200 characters, and differ; a key letter's are one letter each; and the
printed words (or, already corrected, the words meant) are in the row's text. Otherwise the puzzle is
held as `mark-invalid` (`ship.mark_problem`), and the mark reaches neither the xd nor `ship-export`.
`corrected()` checks the same before it applies anything, and `corrections.tsv` never carries a tab or
a line break. A clue's or a header's edit with a line break, a tab or another control character is
refused at import (`edits-unapplied`); a printed line's text may hold line breaks and nothing else of
the kind.

A dry run writes none of this. Three options write the record alone and ship nothing (status
only, for a batch that isn't shipping yet): `--record` (the publication repo's
`pipeline/ship/<batch>.json`), `--snapshot <folder>` (a `ship.json` there) and `--publish` (the
site's copy). Without `--write` a passing puzzle shows as ready to ship, never as shipped.

## The xd as it will ship

Each of those (and `--write`) also writes, for every puzzle the rule passes (ready to ship, or
shipped and unchanged), the exact xd text `--write` writes for it, made in the same run by the same
code, with the record of every edit behind it. One JSON file per puzzle beside the record:

| copy | where |
|---|---|
| the publication repo (`--record`, `--write`) | `pipeline/ship/<batch>/as-shipped/<pid>.json` |
| a snapshot (`--snapshot <folder>`) | `<folder>/as-shipped/<pid>.json` |
| the site (`--publish`) | `batch/<batch>/as-shipped/<pid>.json`, beside `ship.json` |

`{_about, pid, xdid, batch, run, at, status, xd, xd_fp, packet, packet_xd, decision: {rule, ai_ready,
why, said}, edits: {records, packet}, corrections, notes, printed}`: the shape of the puzzle's
provenance row, with the text. `at` is the record's; `xd_fp` is `fingerprint(xd)`, and the record's
row for the puzzle carries the same value as `as_shipped`, so a page can tell a file from another
making of the record. A helper is "a helper" and the owner's site account "the owner", as in the
record's public copy. A puzzle that no longer passes loses its file when the record is made again,
on the site too (`--publish` removes it: `ship.stale_as_shipped`). A file whose fingerprint isn't the
record's is drawn under a warning.

The batch page's "Ready to ship" and "Shipped" cards link to it (`?b=<batch>&ship=<pid>`): the text,
which decision ships it, every edit's record (each linking to its row on the proof page), the
misprints kept as printed with what the export will do, the text review's own changes. The proof
page draws the same file under "The xd as it will ship". Both draw only what the file says, and say
"not recorded" when the record points to a file that isn't there.

## Where the printed lines land

The record's row for each puzzle carries `printed` (`ship.printed_place`): where the packet's printed
lines land in its xd and what the import does with a keep, a discard or a text edit of one: `{head:
"Printed with puzzle:", lines: [the numbers of the packet's lines the block is made of, in its order]
(null when the xd's block isn't the packet's kept lines), edits: applied | held, fixed: [the lines a
header was read from], says}`. `applied`: a linked-ends puzzle, whose block the import writes again
from the kept lines in the packet's order (`apply_linked`). `held`: any other puzzle, which a Ready
carrying such an edit holds (`edits-unapplied`).

The proof page's "Notes in the xd file" draws that block with the review's own keeps, discards and
line edits, labelled "preview with this review's edits: not yet the shipped text", the packet's block
under it, and redraws it on each such edit. It works out nothing but which of the packet's lines are
kept (the page's `printedBlock`, which `tests/test_proof_edits.py` runs against `apply_linked` on real
packets). The record, not the packet, carries the place because it exists for every packet already
published (no packet is rebuilt for it), and because what the import does with the edit is ship's
to say. With no record of it, the page says so and shows the packet's notes. A kept printed line
over 300 characters is flagged on its row and in the preview.

A printed line's text may hold line breaks (a paragraph break: Shift+Enter, or "new line", on the
proof page). Each is a line of the block (`ship.block_lines`); an empty line is refused (the block
ends at one). A clue's or a header's text is one line of the xd, and the page refuses a break there,
saying so.

## Linked ends (the New York World's FUN, 1913-14)

Their xd is a different shape (xword-ocr `linkedends.py`): the header says `Clues: linked ends`,
each clue line is labelled by the numbers printed in its word's two end squares (`1-2. An insect.
~ BEE`; the slot's own label, `A4.`, where a number wasn't read), the across words' lines come
first and then the down words', a word printed in the grid has no line, the notes' `Numbering:`
section says which square has which number, and `_` is the template outside the puzzle. Since
2026-11-12 `blitz ship` applies a reviewer's edits to such an xd (`ship.apply_linked`), each with
its record under the same three cases. The proof page keys a clue by its word's standard label,
and so do the records (`clue:A6`, with the printed pair in `pair`).

| edit | what the import does | record (`what`) |
|---|---|---|
| `clue:A6` | the text of that word's line; the line keeps its pair | `clue`, with `pair` |
| `cell:r4c8` = a letter | the key's square; the answers of the words through it follow | `key square`, with `words` |
| `grid:r3c10` (`.`, `_`, `#`; the page writes `cell:r3c10` beside it) | the square's kind: `_` takes it out of the puzzle, `.` with a letter puts it in | `grid square`, under the `grid:` key, the `cell:` edit named in `with` |
| `num:r3c5` (a number, a letter, or empty) | the Numbering section is written again; a line whose word's end it touches takes the pair the ends then give, or its slot's own label when an end has no number | `square number`, with `pairs` (the lines relabelled) |
| `line:B4` | the line's text in the xd's `Printed with puzzle:` block, and in the row's `printed` (which the export's Notes rule reads) | `printed line` |
| `keep:B3` | the line joins or leaves that block and `printed` | `printed line kept`, class `decision`, with the line's text |
| `meta:title` and the other headers | as in any xd | `header` |

A key correction's note names the words by their pairs ("The printed answer key gave 5-6 as ...");
a proposed correction of a clue's print says "The clue for 5-6 is printed ...".

**What isn't applied holds the puzzle** (`edits-unapplied`, broken, stage import), with the reason
in words; nothing is applied in part (a printed line's text may hold line breaks, each a line of the
block, since 2026-11-13). The import places no clue and decides no number: those are
assembly's.

- A shape fix (`grid:`) is applied only when the grid keeps the same words: every word of the
  packet's grid still there under its label, longer or shorter. One that makes or removes a word,
  or shifts the words' numbering, means the clues have to be placed again.
- A shape fix or a number that leaves a printed number on a square outside the puzzle (the end of
  a word moved): the reviewer says where the number is printed (`num:`), or assembly runs again.
- A `num:` edit that changes which words are printed in the grid (and so have no clue); a number
  past 61, which the Numbering section has no symbol for.
- A clue, square or number edit when the xd's clue lines can't be put on its grid's words (not as
  many lines as words, or a line whose label names another word than its place in the list).
- A `clue:` edit whose row on the proof page isn't the line it would land on. The page keys a row
  by its word (`ocr.json` `clues`: `A12`, with the pair it was read with in `printed`); the import
  puts the edit on that word's line in the xd. When the row's pair (its own label when it has none)
  isn't that line's label, or the packet records no such row, the edit is refused: the page and the
  xd disagree, and the packet has to be rebuilt (No. 9 of c14: the page's A12 is the clue read as
  12-14, the xd's line for A12 is `7-8.`). For the same reason a linked-ends packet whose
  `review.json` has no `matches_xd` is held `packet-stale`, not taken as agreeing.
- A follow-on edit the import makes from a review's `typos` / `key_corrections` (a key letter
  corrected from its entry alone, a misprint taken back out of an edit) that can't be applied: held
  `edits-unapplied`, with no note and no record of a change that wasn't made. The export likewise
  says `applied` in `corrections.tsv` only for a correction it did apply.
- A new square with no letter; a letter for a square outside the puzzle; a rebus square.
- `line:` or `keep:` when the xd's block isn't the packet's kept lines (`ocr.json` `lines`, as the
  text review corrected them); `keep:` on a line a header was read from (`ocr.json` `evidence`);
  `line:` on such a line unless its new text still shows the xd's header (its Number, say): the
  page derives a header from its line, the import doesn't, so the header is given with it (`meta:`).
  Such a line isn't a kept line, so it isn't in the xd: the edit changes nothing that ships, and is
  still listed as applied with its `printed line` record (`kept: false`).
- `label:`, `ev:`, `candidate:`, a fill-in blank: as for any puzzle.

`line:` and `keep:` are applied to linked-ends puzzles only. Any other puzzle is still held on
them (GAMES 1977-79 has three such), though nothing in how they are applied is particular to
linked ends: lifting that is a change to `refused()` and a look at those three.

blitz doesn't depend on xword-ocr, so the Numbering section's reader and writer are in `ship.py`
as well as in xword-ocr `numbering.py`, whose format it is; `tests/test_ship_linked.py` reads
four real packets of batch `nyw-1914-c1` through both the reader and the writer. Not done:
`blitz ship-export` for a linked-ends xd (`to_gxd` keeps neither the `Clues` header nor the
Numbering section), and what gxd's Title and Author say for these puzzles, which is the owner's.

## The queues: what the batch asks of people

Every puzzle of the batch is in exactly one queue, and the record says which. This lives in the
ship record, not in the batch snapshot, because it is the ship rule's answer: the snapshot is
the watch's picture of the pipeline (triage's disposition, the boxes, the thumbnails), and what a
batch still needs from a person depends on the decisions in the ledger and on the site, the
rule's options and the import's own holds, which only `blitz ship` puts together. The batch page
draws these fields and works none of them out.

| `queue` | from | who it is for |
|---|---|---|
| `question` | held as `not-ready`, `owner-hold`, `edits-differ`, `candidate-undecided`, `proposal-waits` or `mark-disputed` | a person: answer on the proof page, and it can ship. The page's default list and its walk. |
| `unchecked` | held as `no-ready` or `proof-stale` | a person: nobody's Ready counts for it yet, so it wants a whole proofread. No question to lead with. |
| `broken` | every other hold: `needs-work`, `incomplete`, `sent-back`, `awaits-replace`, `edits-unapplied`, `packet-stale`, `no-packet`, `xd-exists`, a hold code | agents (as kinds of failure) and the maintainer (a diagnosis of the stage). Shown with its reason; no proofreading ask. |
| `shippable` | passes, not written | nobody: `--write` ships it |
| `shipped` | in `xd/` | nobody; a sample goes to the maintainer (`spot_check`) |
| `set-aside`, `not-a-crossword` | the ledger's `setaside:` / `drop:` | nobody |

Per puzzle:

- `asks` (a `question` puzzle): `[{who, kind, at, row, text, suggest, group}]`, one per comment of
  each Not ready that stands (a Not ready with no comments gives one ask with its note). `who` is
  the reviewer as the ledger names them (a helper: "a helper"), `kind` owner / helper / ai /
  import, `row` the proof page's key for what the question is about, so the link is
  `?p=<pid>&k=<row>` (`ev:title`, `clue:A12`, `cell:r3c4`, `line:B2`, `grid`; "" for the puzzle as
  a whole). `text` is the comment without the reviewer's "Flag for the maintainer:", `suggest`
  what follows its "Suggest:".
- `group` on an ask: the shared question it belongs to, by the header it is about (`ev:title` and
  `meta:title` are `title`; author is `byline`; note is `notes`); "" for a clue, a square or a
  printed line, which is that puzzle's own question. `group` on the puzzle: the largest group
  among its asks. The record's `groups` lists them largest first: `[{key, label, puzzles, asks}]`
  (`puzzles` counts by the puzzle's own `group`, so the groups and the ungrouped add up to the
  queue; `asks` counts every puzzle with a question in the group).
- `also` (a `question` puzzle): what the ship check found incomplete. An answer doesn't mend it,
  so the card says so beside the question.
- `broken` (a `broken` puzzle): `[{what, stage, code, detail}]`. For `needs-work` these are
  triage's blocking parts and the stage each restarts from. For `incomplete`, the ship check's
  lines, with the stage its finding points to (`grid-unsolved`: key reading; `clue-empty`: parts;
  `clue-missing`, `clue-extra`, `second-set-missing`: assembly). For the import's own holds:
  `packet-stale` and `no-packet` point to the proof packet, `edits-unapplied` and `xd-exists` to
  the import, `clue-typed` to the text step. A stage that nothing recorded is "".
- `order`: the puzzle's place in the batch's walk, so the page never sorts by its own idea.
  Questions first: the shared groups, largest first; inside a group the puzzles with nothing but
  shared questions, then the fewest questions; then the puzzles with only their own questions.
  After them the other queues in the table's order, by id.
- `reviewed`: a person (the owner or a helper) has said Ready or Not ready on it. An AI's review
  or the ship check never sets it. This is what "Reviewed" means on the page: a fact about a
  puzzle, shown on its card and as one count, not a queue.
- `spot_check`: in the maintainer's spot-check sample. The sample is fixed by the id alone
  (`sha1(pid) mod 10 == 0`, about one in ten), taken from the puzzles shipped on someone else's
  word than the owner's (`rule` is not `owner`). A puzzle is in it or out of it for good; the
  record's `spot` says how it was drawn.

`counts.queues` has every queue's count; they add up to `counts.puzzles`.

### A question that isn't a person's to answer: `sent-back`

A person who opens a question and finds it is the pipeline's (a block linked from a neighbour, a line
that has to be read again) says so with the proof page's existing send-back: a Not ready whose review
carries `sendback: {kind, part, note}` (the kinds and parts are xword-ocr problems.py's, which the
packet's `review.json` lists). It reaches the ledger like any helper's decision (`proof:<pid>`, by
`<helper> (review site)`), so there is no second ledger. A standing Not ready with a send-back makes
the hold `sent-back` instead of `not-ready`: the puzzle leaves `question` for `broken`, with what the
person said and the stage it points to (a part's stage: the clue lists and the grid are parts, the key
and the title assembly; else the kind's: missing or misread is parts, mixed is assembly; "" for
something else). The owner's later Ready still overrides, as it does any Not ready.

### A Not ready that waits on the pipeline: `awaits-replace`

**Whose fixes: the owner's rule, 2026-11-12, "Owner only for now".** Only the owner's fixes to a grid
restart a puzzle: records made in the owner's own tools, or on the review site under an account in
the rule's `owner` list. A helper's or a guest's stay in the ledger, show in the packet as not used,
and restart nothing; their Not ready is a question for the owner as any other is. An account on the
rule's `ignore` list never counts. (Later, not built: a button for the owner to accept a helper's fix.)

On a linked-ends puzzle (the New York World's) the owner mends the grid on the proof page: a square
that isn't one, a square's printed number, a key letter. The import applies only a Ready's edits, and
the words and the clues' places follow from the grid, so the owner's Not ready carrying such edits
(`grid:`, `num:`, `cell:`) is a diagnosis for the stage that places the clues, which reads them from
the ledger (xword-ocr `linkedends.hint`; `xword-ocr remedy replace` reads the puzzle again). Until the
packet says it was made from that decision (`ocr.json` `reviewer_fixes.decisions`: who and when, as the
stage recorded them), the hold is `awaits-replace` and the puzzle is in `broken`, pointing to
assembly, with how many fixes of each kind wait and the reviewer's note. What was said stays on the
row as `asked` (the shape of `asks`), so the card shows it under "Waiting on the pipeline: nothing to
answer here yet". Nothing is read out of the note's words. Once the packet records the decision, it
goes by triage: ready for review, and the Not ready is a question again (`owner-hold` or `not-ready`),
the reviewer's to look at; needs work, and the hold is `needs-work` (triage's blocking parts and their
stages), still in `broken`, with `asked` kept.

With no puzzle held on a question, the batch page opens on `unchecked` and its Start walks those.

**What the pipeline read in is shown and recorded.** A re-placed packet's own values include the
owner's squares, key letters and numbers, so no Ready's edit carries them. The packet says which
(`ocr.json` `reviewer_fixes.squares`: `{key, value, was, by, at}`, xword-ocr's record of what the
reading was made from). The proof page draws them and works nothing out: the blank grid lists every
one under "Read in from the owner's fixes on the proof page", with what the stage had there, where
the key disagrees (`key_disagrees`), where the owner's accounts disagreed, and whose fixes were not
used; a square or key letter the owner changed is outlined as a change by "the owner (read in by the
pipeline)" after the OCR's value. At ship each becomes an edit record in provenance
(`read_in_records`, stage `re-place`, before the Readys' own): a square's kind and a printed number
as class `reading`, a key letter as `unclassed` (nothing says whether the key was misread or
misprinted), a number with `before_recorded: false` (what stood there was not recorded). One the
owner gave that the stage already had is no change and no record.

**A clue placed by sequence** (triage's `clue-by-sequence`, xword-ocr) needs a person's Ready under
any `ai_ready` (`PERSON_CODES`); it is a doubt on the clue's row, not a hold on a person's Ready.

### Proofreads a Ready ships come first

An AI's question on a puzzle the ship check finds incomplete stays a question (it was tried as a
hold of its own and dropped on the cold review of 2026-11-12: for 9 of the Collegian's 18 the
question is that a clue is not printed in the paper, which only a person can decide).

`also` is kept on an `unchecked` puzzle too (what the ship check finds incomplete: a Ready wouldn't
ship it yet), the card says so, and `order` puts the unchecked puzzles a Ready ships before those.

## Candidate clue lists

A clue list that fits the grid and is neither its clues nor a recognised second set is a
*candidate* (xword-ocr docs/ship-gate.md, "Candidate clue lists"): assembly records it, the proof
packet carries it (`ocr.json` `candidates`), and it is never in the xd until a person says what it
is. Before 2026-11-10 it was a block of text in the xd's notes ("Another list that fits the
grid"), which the ship check flagged and nobody could act on.

On the proof page it is a panel at the top of its direction's clues: what it is and which
milestone recorded it, how well it fits and why it wasn't taken as a second set, the block it was
read from cut from its page (opens the page with the block outlined), and its clues one by one,
each with the crop of the OCR lines it was read from, beside the puzzle's own clue at that number.
A box the packet doesn't have shows as "not recorded". Four buttons decide it; each is the edit
`candidate:<id>` in the reviewer's review, so it is saved, imported and credited like any edit
(the `proofs` table, then `proof:<pid>` in the ledger):

| button | edit value | what the import does |
|---|---|---|
| Not this puzzle's: remove it | `remove` | nothing to the xd (the list was never in it); the hold is released |
| A second clue set for this grid… (asks the set's name in place) | `second:<Key>` | each of its clues becomes the `D1 ^Key:` line under its clue; a note in the xd says so. Held as `candidate-partial` unless the set covers every clue of the puzzle |
| These are the real clues | `clues` | each of its clues replaces the clue at its number (as the OCR read it); a note says so. Held as `candidate-partial` if it lacks a number |
| The printed answers, not clues | `answers` | nothing to the xd; recorded as answers. Filling the key from them isn't built |

`ship.apply_candidates` does this before the other edits, so a reviewer's fix to one of the new
lines (`clue:D1^Easy`) lands on it.

**When a candidate is decided.** One function answers it, `ship.candidate_decisions`, for the
import, the record, the batch card and (by the same rule, in its own code) the proof page:

- a choice is a `candidate:<id>` edit with one of the four values, made by a person: the owner or
  a helper, not an account in the rule's `ignore` list. An AI reviewer's or the ship check's record
  never decides, under any `ai_ready` setting and with the owner's Ship on the batch page: an AI
  asks, a person decides;
- a choice **counts** when its review said Ready on the puzzle's current version. That is exactly
  when the import takes that review's edits. A choice made in a Not ready, or in a Ready on an
  earlier version, doesn't count.

The ship rule itself is unchanged: the puzzle ships when the rule passes it *and* every candidate
has a choice that counts. Otherwise it is held `candidate-undecided`, a question. While one is
undecided the ship check fails too, so an AI's Ready never ships it.

The proof page says which it is. A choice that counts shows as decided, with whose it is. A choice
that doesn't shows as "Not decided yet", with whose it is and why, and a button to make it your
own. Picking a value always writes it into your own review, even when it repeats someone else's,
so a Ready given on a page that shows your choice carries it. Saying Ready with a candidate you
haven't chosen for, and nobody's choice counting, asks first: it names any choice the page shows
that doesn't count, and offers to make it yours. (`tests/test_candidate_panel.py` runs the page's
rule under node against `candidate_decisions` on the same reviews.) xword-ocr's
`triage.candidate_decisions` is the same test less the `ignore` list.

In the record each such puzzle has `candidates: [{id, dir, clues, slots, reads_as, decision, kind,
at}]`: `decision` is the choice that counts, "" while there is none; then `pending: {decision,
kind, at, why}` is the latest choice that doesn't count, if any, which the card shows as such. Each
undecided candidate gets the pipeline's own question at its row (`candidate:<id>`, group
`candidate`, asked by "assembly"), saying so when a choice is pending. A reviewer's question stays
on the row the reviewer gave it: one about the notes' "another list" block (asked before candidates
had a place) stays on the notes, beside the pipeline's question. Nothing is re-pointed by its
wording.

## The question on the proof page

The batch page's "Answer it" opens `/review/?p=<pid>&k=<row>`. The proof page reads the puzzle's
batch from the site's puzzles table and that batch's `ship.json`, and when the record holds the puzzle
on a question it draws, from the record:

- a box at the top: each question with who asked, its text and what was suggested, and a button to
  its row; the incompleteness an answer won't mend; how to answer (fix the row or comment on it, then
  Ready or Not ready), and "It's a pipeline question: send it back", which opens the send-back form
  with the question as its note;
- the question again at its row, unless a reviewer's comment there already says it (the AI's round,
  from the packet's `ai_review.json`).

The ship record is the source, not `ai_review.json`: the record is what put the puzzle in the question
queue, it carries a person's and the import's questions as well as the AI's, and it exists for packets
published before the AI review did. A row the packet doesn't have (a clue number that isn't in the
grid, an answer key the packet doesn't show, the xd's notes when the packet went up without its xd) is
said so in the box, and the page stays there instead of landing somewhere else. In a walk, Next opens
the next puzzle at its own first question.

The xd's notes: `blitz site-publish` now uploads the packet's `puzzle.xd`, and the proof page shows
everything the xd carries after its clues, block by block as written, read-only, under "Notes in the
xd file" (`meta:note` and `notes` land there; comments on the notes are made there). Each block's
first line is its own heading and names what it is (Assembly flags,
OCR review flags, Text step, Printed with puzzle). This is not the header table's Notes row that the
2026-10-17 redesign left out: which printed lines go into the gxd export's notes is still the
run-wide Notes rule. It shows what the xd holds now, so nothing in it is hidden. A packet published
without its xd says "not recorded" there.

`tools/check_question_links.py` checks every question link of a ship record against real packets on
the dev server (does the row exist, is the question shown at the top and at the row, does the page land
there); design/batch-ask/link-check.md is its table of 2026-11-10.

## Where a person sees it

The batch page (`/review/batch/?b=<batch>`) reads `ship.json` beside the batch's `batch.json`
(`blitz ship --publish` puts it there; `--snapshot <folder>` for a local copy). The page is the
record's queues:

- One chip per queue, with counts that add up to the batch. It opens on **Held on a question**,
  in the record's order, a heading per shared question; the main button walks that list on the
  proof page, opening at the first question's row. Each card leads with its questions: who asked,
  the row (a link to `?p=<pid>&k=<row>`), the text, what was suggested.
- **Not checked yet** has a Proofread button and its own walk. **Broken in the pipeline** shows
  what is broken and the stage it points to (a filter per stage), and asks nobody to proofread.
- **Shipped** cards say the id and why it shipped. **Spot-check** is the recorded sample, for the
  maintainer, with its own walk.
- A puzzle the snapshot lists and the record doesn't (one triage dropped before the record's
  list was made) shows under Not a crossword when the snapshot recorded the drop, and says the
  snapshot is its source; any other shows as Not recorded.
- A batch with no record, or one from before the queues, says "not recorded": every puzzle is
  listed with triage's word, and no walk is offered.

Answers given on the site after the record was made show on the cards (the live tally); a puzzle
changes queue only when `blitz ship` makes the record again. The page draws the record; it never
applies the rule. To work on the page, `tools/review_dev.py --data <folder>` serves it over a
copy of the snapshots and reloads on every edit.

## Status and milestones on the EPP site

Nothing is published by `--write`. Two things carry a batch's status outward, both made from
the same plan:

- `<pub>/pipeline/ship/<batch>.json` in the publication's repo (public): `counts` (puzzles,
  shipped, shippable, held, out, held_by) and every puzzle's status. This is the input for a
  status page or a milestone note ("35 of 76 shipped"); `gxd-exports.tsv` lists the shipped
  puzzles with their proof pages.
- `ship.json` on the review site, which the batch page draws. To publish it, from a blitz
  checkout that has this code, with the publication's checkout beside it holding the shipped
  `xd/` (otherwise shipped puzzles show as "ready to ship"):

  ```
  uv run blitz ship games --proof ../xword-ocr/harvests/games-7779/proof/run15-restart --batch games-1977-79 --publish
  ```

  It needs the site's R2 settings (`R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`,
  `R2_BUCKET`) and writes one object, `batch/games-1977-79/ship.json`.

## The gxd export

`blitz ship-export <pub> --dest <folder>` writes files only: `<shelf>/<YYYY>/<gxd id>.xd`,
`receipts.tsv`, `publications.tsv`, `source-pages.tsv` (every page the puzzles were read from),
`source/` with `--pages`, `held-back.tsv`, and `COMMANDS.md`, the commands that would make
the merge request. Nothing is pushed. gxd branches go to the fork only, with the owner's
go-ahead.

An exported file is the puzzle only: Title, Author (tidied), Editor, Date, Number, Byline,
Rebus, Special; the grid; the clues with their `^Easy` lines; and the printed lines the Notes
rule takes (the ledger's `notes-rule:<pubid>`, else intro and instructions), then the row's
`notes` (key letters corrected) and a note for each correction of the print the export makes
(`corrections.tsv` lists them). Sources, OCR flags
and everything else stay in provenance.jsonl. `Feature` is left out until `--feature-as` says
which gxd header it becomes. A puzzle carrying `cryptic-no-key` stays in `xd/` and isn't
exported.

## Not done yet

- xword-ocr still has its own copy of the rule (`batchpage.standing`, where an AI's Ready
  always counts) and its own `import-batch`; the local watch's batch page shows that one. They
  should go, or read `pipeline/ship/<batch>.json`.
- `puzzles.tsv` and the publication's status page (`games/tools/render.py`) don't read the ship
  record yet; the EPP home page has no milestone line fed from it.
- A cryptic that has a key grid carries no code saying it's a cryptic, so the export can't hold
  it back.
- Pages v2 read that the scans repo never backed up have no capture date for the receipts.
