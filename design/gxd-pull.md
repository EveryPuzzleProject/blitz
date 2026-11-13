# gxd pulls from EPP: reversing the export

Status: proposal, 2026-11-13. Nothing here is built. The owner's direction of 2026-11-13: instead
of EPP pushing to gxd, EPP advertises what it has, and gxd downloads and imports it the way it
does every other outlet, with its own import code and its own editorial. Nothing from the v2
pipeline has gone to gxd yet (GAMES 1977-79: 35 shipped; Collegian: 69; New York World 1914: 2),
so changing direction now is cheap. Revised the same day, after the owner settled the editorial
boundary (next section).

## What EPP produces: a transcription and an edition

Decided by the owner, 2026-11-13: EPP publishes two layers of every puzzle, and gxd imports the
second.

- **The transcription**: the puzzle as printed, what the proof page verifies against the scan.
  Reading fixes and answer-key letter corrections (with their note) are applied here, as now
  (`blitz ship` writes it to `xd/`).
- **The edition**: a final EPP step applies the recorded misprint corrections (from AI reviewers'
  and people's marks, under the ship rule, less any the owner declined) and the Notes choice, and
  writes a note in the xd for each change. It is derived by rule from the transcription plus the
  marks, never hand-edited, and made again whenever a mark is added or declined. EPP advertises the
  edition; the transcription is its evidence and is published beside it.

**The boundary** (agreed): anything that changes what the puzzle says is EPP's (clue and header
misprint corrections, key-letter corrections, which printed lines are notes); anything mechanical
about form is gxd's house style (which headers it keeps, author tidying, quote characters and
similar). Whether the two projects share one set of editorial guidelines is still open.

This revises the owner's 2026-11-11 wording, that a clue misprint is corrected "as far downstream
as possible... as part of GXD's editorial": the correction now happens at the end of EPP, in the
edition, not in gxd. The record-keeping is unchanged: the transcription stays as printed, every
correction is a record in `provenance.jsonl` naming who proposed it, and the note says what was
printed.

## The facts

### How gxd takes in a source today

- **Two steps, strictly separated** (gxd-downloader `README.md`, `DESIGN.md` §3.1). *Fetch*
  keeps the bytes as served in an immutable session archive (`downloads/<year>/<ts>-www.zip`:
  files under `<pubid>/`, `MANIFEST.tsv` with sha256, source_url, fetched_at; a `NOTES.md`; a
  register row). *Import* (`gxd-downloader import --gxd <checkout>`, `gxd_downloader/importer.py`)
  converts every archive gxd's `source-archives.tsv` doesn't list yet: `.xd` on its shelf, a
  `receipts.tsv` row, the archive's register row, `tricky-xdids.txt`. Two cursors: the store's
  ledger (fetched) and `source-archives.tsv` (imported).
- **A new source provides** a row in `outlets.tsv` (`id adapter params days since tz
  available_after refetch homepage auth enabled notes`), usually on an existing adapter, a
  converter per *format* (chosen by content), and a fixture (`tests/fixtures/<pubid>/raw.*` +
  `expected.xd`). gxd needs its `publications.tsv` / `pubregex.tsv` rows.
- **Ids.** The importer works the xdid out from the source file's name (pubid, then date or
  number), with `overrides.tsv` to pin one (gxd `CONTRIBUTING.md`, "How the importer works out an
  xdid"). For EPP the rule is already written down as [proposed]: puzzles made outside gxd "get
  their xdid from the tool that made them" ("Changing an xdid").
- **Change.** A re-fetch that converts the same is left alone; one that converts differently
  updates the `.xd` in place (`importer.py`, docstring), the old text kept in git. gxd calls that a
  revision or a corrected mistaken copy ("Versions of a puzzle"). `refetch` says how long an outlet
  is looked at again.
- **Review.** Intake checks run on every converted puzzle (`checks.py`, 2026-11-13); a converter
  can mark a puzzle `needs_review`, which holds it out of the nightly commit onto a `review/<xdid>`
  merge request that never merges itself. `GXD_PUBLISH` is `off` (preview), `mr` (branch on the
  fork, MR into rabidrat/gxd), `automerge` or `push`.
- **Receipts** are append-only, one row per item that became a puzzle: `CaptureTime ReceivedTime
  ExternalSource InternalSource SourceFilename xdid`. An item may be "a package of several files (a
  packet of page images and OCR text)", its folder ending in `/` ("Receipts"). `ExternalSource`
  may be as specific as the file itself. Judge's 531 rows: `https://github.com/EveryPuzzleProject/judge`,
  `judge-scans-2026-10-12.zip`, a page image.
- **Edits** ("Editing puzzles already in the corpus"): commit the puzzles as published first, the
  fixes in a second commit. A publisher's clue typo is corrected **in git only** (the commit says
  what was printed); an answer or grid letter the publisher got wrong is corrected **with a note**.
  Stubs (`<xdid>.xd.stub`, no receipts row) are [proposed].

### What is gxd-specific in blitz today

All of it is in `src/blitz/ship.py` from line 2266 on, plus its callers:

| piece | where | fate |
|---|---|---|
| `ship-export` command, `export()`: shelves, receipts rows, `source-pages.tsv`, `publications.tsv` row, `held-back.tsv`, `COMMANDS.md` | `ship.py` 2519-2619, `cli.py` 648 | leaves (gxd's import does this) |
| `to_gxd()`'s house style: header whitelist `KEEP`, `normalize_author`, curly quotes flattened (`FLATTEN`), `Feature` dropped or renamed | `ship.py` 2428-2468 | leaves (to the gxd converter) |
| The Notes rule: `NOTE_LABELS`, `notes_labels()`, the ledger's `notes-rule:<pubid>` and its batch-page control | `ship.py` 2430, 2471; `batch.html` | stays, in the edition step |
| `corrected()`: applies a clue or header misprint and writes "X is printed 'a'; corrected to 'b'." | `ship.py` 2027 | stays, as the edition step, taken out of `ship-export` |
| `NOT_EXPORTED` (cryptic with no key) and the "key-declined" hold | `ship.py` 2431, in `export()` | become a status in the manifest |
| `gxd-exports.tsv` (`gxd_id`, `gxd_mr`, `exported` filled by hand; `proof_url`, `record_url`, credit) | `write_exports()` 2266; read by `records.py` 574 and crossref's `pipeline/fetch_epp.py` | replaced by the manifest and gxd's receipts |

What stays in blitz: `blitz ship` and everything it writes (`xd/`, `provenance.jsonl`, the ship
record, `as-shipped/<pid>.json`); key-letter corrections made at ship with their note (case 3 of
`design/ship.md`, "The record of every edit"); misprint marks with their records; printed-line
labels and keeps; the edition step (`corrected()` and the Notes rule); the record pages.
`squares.py` reading a gxd checkout as a word list is a read, not an export, and stays.

### Typography today

Three normalizations exist, in different places, and nothing says which side owns them:

- **Quotes**: blitz's `FLATTEN` (`ship.py` 2429) makes curly quotes straight at export, because
  gxd's lint wants plain quotes (xdlint XD208); xword-ocr's old `export.py` 44 has the same table.
- **Fill-in blanks**: xword-ocr's text step keeps a blank as printed (`——`) and tags it, saying
  "The export turns blanks into `___`" (`textstep.py` 84-87); the AI proof reviewer keeps `___`
  where it already is (`proofreview.py` 76). No code in blitz's export makes that conversion
  (`ship.py` has no `___`), so the promise is unkept.
- **Dashes**: the 2026-10-17 ASCII rule (blanks `___`, punctuation dashes `--`, quotes straight;
  `design/games-7779-next.md` 248-251 puts it in the export) is written down, but as far as the
  code shows only the quotes are applied.

### What EPP already publishes, and what a machine still lacks

All four publication repos are public (`gh repo list`: judge, games, collegian, newyorkworld
PUBLIC; every `-scans` twin PRIVATE). On their default branches today:

| repo | `xd/` | `provenance.jsonl` rows | ship record | `as-shipped/` | `gxd-exports.tsv` |
|---|---|---|---|---|---|
| judge | 531 | none (shipped by the older path) | none | none | yes, with gxd ids (`judge-001`) and `gxd_mr` |
| games | 37 | 35 | `pipeline/ship/games-1977-79.json` | none | yes, no `record_url` |
| collegian | 69 | 69 | `pipeline/ship/collegian-1976-81.json` | none | yes, no `record_url` |
| newyorkworld | 2 | 2 | `pipeline/ship/nyw-1914-c1.json` | none | yes, with `record_url` |

A provenance row already holds most of what gxd's editorial needs: the xd's fingerprint (`xd`,
12 hex), `printed` (kept lines with labels), `notes` (key letters corrected), `corrections`
(proposed misprints), `sources` (scan URLs per role), `said` (who reviewed). The review package on
R2 (`package_url`) holds public page crops for every puzzle, GAMES and Collegian included.

Missing for a pull: **one index per publication** saying which puzzles are available now, with
a full-length fingerprint and a status (available, withdrawn, held); a **release mark** (shipped
is not the same as "gxd may take it", see Cadence); the **as-shipped files** are not on any
default branch; Judge has **no provenance rows**; and nothing says **which commit** a set of files
is, so a fetch could catch a repo mid-push.

## The design

Each decision gives options and a recommendation. **(O)** is the owner's; **(O+S)** also needs Saul.

### 1. Where the advertisement lives (O)

- (a) The repos as they are: gxd reads `xd/` and `provenance.jsonl`. No index; withdrawals invisible.
- (b) **A manifest per publication repo**, written by `blitz ship`, beside the files it lists.
- (c) A feed on everypuzzleproject.org (one JSON for all publications).
- (d) The bucket (R2 or `s3://epp-blitz`).

**Recommend (b)**: `<pub>/shipped.tsv`, one row per puzzle EPP has ever advertised: `xdid, date,
number, status, why, transcription, transcription_sha256, edition, edition_sha256, shipped_at,
batch, release, record_url, proof_url` (the two file columns are paths in the repo).

**Where each file lives.** `xd/<xdid>.xd` stays the transcription, as today; the edition goes in
`edition/<xdid>.xd`. Keeping `xd/` costs nothing: its readers (`records.py` 583-597 for the record
pages, `sync.py` 140, the provenance row's `xd` fingerprint, the proof page's checks against the
scan) all mean the transcription. The other way round (`xd/` as the edition, `transcription/` beside
it) would suit someone browsing GitHub, but would change what every reader and fingerprint means;
outside readers go through the manifest anyway. The edition is written by `blitz ship` (`--write`;
`--record` for the `as-shipped/` copies) and by a small `blitz edition <pub>` run when a mark is
added or declined after shipping. Both update the manifest row. The batch page's and proof page's
"xd as it will ship" views draw the edition, with its notes, from that file.

**The files already shipped**: the 69 Collegian, 35 GAMES and 2 World files in `xd/` are
transcriptions already and stay as they are; their editions are made the first time the step runs,
with no re-ship. Judge's 531 came by the older path and are already in gxd: the manifest lists them
as editions, with no transcription column.

The fetch reads it
from a **pinned commit** (raw.githubusercontent.com at a sha, or a shallow clone), and that sha goes
in the archive's `NOTES.md`, so what gxd took is reproducible. Everything it points to is already
public; GitHub is where crossref already reads from. (c) can be built later from the manifests for
people; (d) adds a second copy to keep in step. **Public versus restricted**: the xd text of GAMES
and the Collegian is already public in their repos under the owner's fair-use stance, and their page
crops are public on R2, so nothing in the pull needs credentials. Full-resolution scans stay in the
private `-scans` repos and are not part of the pull.

### 2. Identity and change (O+S)

- **Ids.** EPP's xdid is the key in the manifest; gxd's id is gxd's. They match for the World,
  GAMES and the Collegian (date-based, letter suffixes); Judge differs (`judge1924-11-01` vs
  `judge-001`). **Recommend**: the converter gives the id from the manifest's `date` and `number`
  by a per-publication rule in the `outlets.tsv` row (`id=number` for Judge, date otherwise), with
  `overrides.tsv` for the odd pin. No file-name parsing, no id kept on the EPP side.
- **New or changed.** The manifest's `edition_sha256` against the sha256 in the last archive gxd imported
  for that puzzle (not against gxd's file, which differs by design once gxd's editorial has run).
  Same: nothing. Different: the importer's existing update-in-place, held for review if it touches
  the grid or answers.
- **A mark after release.** A misprint mark added, or one the owner declines, after gxd has the
  puzzle changes the edition and its fingerprint; gxd's next pull sees a changed puzzle and
  re-imports it like any revision. A change to the transcription that leaves the edition the same
  never reaches gxd.
- **Re-ships overwrite.** Because the converter applies gxd's editorial every time, a re-import is
  deterministic. That only holds if **nobody hand-edits an EPP puzzle in gxd**: a fix goes back to
  EPP (a mark on the proof page), which re-ships it. That is a rule Saul has to agree to.
- **Withdrawals.** A puzzle stays in the manifest with `status=withdrawn` and `why` (set aside as
  not a crossword; a key correction the owner later declined; a re-dating). gxd never deletes on its
  own: a withdrawal opens a review MR. A re-dating is gxd's "Changing an xdid" with a receipts row.

### 3. Where each editorial step happens (agreed 2026-11-13; typography open)

| step | today | proposed |
|---|---|---|
| Reading fixes; key-letter misprints (corrected, noted) | `blitz ship`, in `xd/` | unchanged: the transcription |
| Clue / header misprints | `corrected()` at export, with a note | EPP's edition step: applied where mechanical (the printed word present once), with a note; a mark it can't place holds the puzzle's edition, shown on the batch page |
| Which printed lines go in Notes | blitz ledger `notes-rule:<pubid>`, default intro + instructions | EPP's edition step: the same rule and batch-page control |
| Header whitelist, author tidy, quotes | blitz `to_gxd` | gxd's `epp` converter (house style) |
| Blitz-only headers (`Source`, `Solution`, `Assembly`, `Text-Review`, `Rights`, `Numbering-Rule`, `Clues`) and blocks (`Typed by hand:`) | dropped by `to_gxd` | kept in both EPP files; gxd's converter drops them as house style |
| Fill-in blanks, dashes | promised, not done | whichever side owns typography (an owner's decision) |
| Unsolved puzzles | none shipped yet | gxd's own convention (every white square X, listed as tricky) |
| Stubs | `puzzles.tsv` `missing` rows | out of scope until gxd settles stubs ([proposed]) |
| Cryptic with no key | `NOT_EXPORTED` | a manifest status (`kind=cryptic-no-key`); the registry decides |

gxd's own rule for a publisher's clue typo is to fix it in git only, with no note (`CONTRIBUTING.md`,
"Editing puzzles already in the corpus"). EPP's edition carries a note for each correction; whether
gxd keeps those notes or strips them is house style, and Saul's to say.

### 4. The linked-ends xd (O+S)

gxd already holds the World in this shape: Saul's `nyworld/1913/nyw1913-12-21.xd` labels clues by
end pairs (`2-3. What bargain hunters enjoy. ~ SALES`) with `_` outside the diamond. EPP's
`nyw1914-03-01` differs in three ways: a `Clues: linked ends` header, a `Numbering:` notes section
mapping squares to numbers, and the slot's own label (`A4.`) where an end number wasn't read.
**Recommend**: the converter drops the `Clues:` header and the Numbering section to match gxd's
existing files, and holds for review any puzzle with a slot label (pairs couldn't all be read).
Whether xdformat should carry the numbering map is Saul's and xdformat's question, not a blocker.

### 5. Provenance and credit (O+S)

- **Receipts**: one row per puzzle, `ExternalSource` = the puzzle's **record page URL**
  (`https://everypuzzleproject.org/nyw/1914-03-01/`), `InternalSource` = the session archive,
  `SourceFilename` = the package folder `<pub>/<xdid>/` holding the xd as served, its provenance
  row, and the R2 page crops. CONTRIBUTING already allows a specific address and a package item.
- **Crossref** then gets its credit link from gxd's receipts (EPP's ExternalSource prefix marks the
  credit, the URL is the link), and `gxd-exports.tsv` and crossref's `fetch_epp.py` retire. EPP's
  record pages still want the crossref link back, which needs the gxd id: crossref can publish
  its own `epp.csv` mapping, which `records.py` reads instead of `gxd-exports.tsv`.

### 6. Cadence and gating (O)

- (a) Shipped means pullable; gxd pulls on a schedule.
- (b) **A release mark per batch**: the owner presses "Release to gxd" on the batch page (a ledger
  row `release:<batch>`, recorded with who and when); `blitz ship` writes `release` into the manifest
  and only released rows are `available`.
- (c) gxd decides alone by date range in its registry.

**Recommend (b)**. It keeps "GAMES as one merge request": the GAMES batches are released together
when the series is ready, and gxd pulls once. The gxd side runs the EPP row on demand (no nightly),
with `GXD_PUBLISH=mr` and never `automerge`. Also open: whether gxd takes a puzzle whose only Ready
is an AI's (the Collegian's 69 have `person_reviewed` empty in `gxd-exports.tsv`).

### 7. What is deleted or frozen in blitz, in slices

Freeze `ship-export` now (no linked-ends support, no new features). Then:

1. **Edition and manifest** (blitz, small): take `corrected()` and the Notes rule out of
   `ship-export` into the edition step; `blitz ship` writes `edition/` and `shipped.tsv` for every
   publication (Judge's from its `xd/` and `gxd-exports.tsv`, release = already in gxd); the "xd as
   it will ship" views draw the edition. Release mark on the batch page. Nothing in gxd changes.
2. **Converter and adapter** (gxd-downloader, one MR): an `epp` adapter reading the manifest at a
   commit, an `epp` converter holding only house style (`to_gxd`'s headers, author tidy, quotes). Its parity test: convert
   Judge's 531 EPP files and diff against gxd's `judge/` (the crosshare branch measured 732 of 739
   identical the same way). No MR to gxd.
3. **First pull: the New York World, 2 puzzles.** Public domain (no rights question), gxd already
   has the `nyw` pubid, its shelf and Saul's own two 1913 files to compare against, the ids match,
   and it is the shape ship-export was about to need special code for. A branch on the fork and one
   MR, with the owner's go-ahead.
4. **Credit**: receipts-based crossref link; `records.py` reads crossref's mapping. Then delete
   `export()`, `to_gxd`, `normalize_author`, `KEEP` and `FLATTEN` (unless typography lands on EPP's
   side), `NOT_EXPORTED`, `COMMANDS`, `write_exports` and `gxd-exports.tsv`, and the `ship-export`
   command. `corrected()` and the Notes rule stay, in the edition step.
5. **Collegian, then GAMES** once the series is released, each as one pull and one MR.

## Decisions for the owner first

1. Is the advertisement a manifest per publication repo, read at a pinned commit (§1)?
2. Is "available to gxd" a release mark per batch on the batch page, not just "shipped" (§6)?
3. What is still open on the editorial side:
   - **Who owns typography** (blanks to `___`, dashes to `--`, quotes straight): EPP's edition,
     as critical work that makes the edition useful on its own, or gxd's house style. Today it is
     promised in one place and done, for quotes only, in another.
   - **One shared set of editorial guidelines** for both projects, starting from the Collegian's
     `editorial.md` and gxd's `CONTRIBUTING.md`, or two sets that agree.
   - **Where the edition lives**: `edition/<xdid>.xd` beside `xd/` as proposed, or `xd/` becomes
     the edition.
4. Is the World the first pull, with ship-export frozen from now (§7)?

## Open questions for Saul

- No hand edits to EPP puzzles in gxd: fixes go back to EPP and come in as re-imports. Acceptable?
- EPP's edition carries a note for each clue or header misprint it corrected. Does gxd keep those
  notes, or strip them as its own rule (typo fixes in git only) would?
- Receipts `ExternalSource` per puzzle (the record page) and a package folder as `SourceFilename`
  (holding the edition, the transcription and the page crops).
- Linked-ends files: drop `Clues:` and `Numbering:` to match his 1913 files, or does xdformat want
  the numbering map?
- Puzzles whose only Ready is an AI reviewer's (the Collegian): in, held, or marked?
- Withdrawals: always a review MR, never automatic?

## What I could not determine from the repos

- Whether crossref reads gxd's `receipts.tsv` today, and whether the crossref repo is public (it
  decides how `records.py` gets the gxd id back).
- Why `games/xd/` has 37 files but 35 provenance rows.
- Whether the as-shipped files are published to R2 for every batch (ship.md says `--publish` does;
  none is on a default branch).
- Whether gxd's xdlint accepts a slot label (`A4.`) in a pair-labelled clue list.
- How gxd counts a puzzle reached through EPP's repo whose underlying page is also in a gxd source
  archive already (Judge's `judge-scans-*.zip`): one receipts row or two.
