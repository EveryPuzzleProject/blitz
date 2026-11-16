# Publishing the edition: the last step of every publication

Status: decided points and slice 1 built (2026-11-16, blitz branch `claude/gxd-pull-slice1`, after a cold review);
the owner's open decisions are listed near the end. This note was `design/gxd-pull.md` ("gxd pulls from EPP", 2026-11-13); the owner reframed it on
2026-11-16:

> every puzzle project [is] an independent project, meaning the last step in its process is publishing the digital
> edition that is prepared. That then makes it available to GXD or anyone else who's downstream of every puzzle
> project... publishing doesn't necessarily mean publishing publicly. That's kind of a TBD question... I think we need
> to decouple GXD and every puzzle project.

So each publication's process ends with **publishing its edition**. Nothing in EPP's process, files or pages is named for
a downstream reader or knows about one; gxd is one such reader, and everything about it is in the last section, "gxd as
one downstream reader". "Publish the edition" is not the review site's "publish" (`blitz site-publish`,
`site-publish-batch`, `ship --publish`, which put packets and records on blitz.xwordapp.com): this note always says
"publish the edition" in full.

## Two layers: the transcription and the edition

Decided by the owner, 2026-11-13: EPP makes two layers of every puzzle, and publishes the second.

- **The transcription**: the puzzle as printed, what the proof page verifies against the scan. Reading fixes and
  answer-key letter corrections (with their note) are applied here (`blitz ship` writes it to `xd/`).
- **The edition**: a final step applies the recorded misprint corrections (from AI reviewers' and people's marks,
  under the ship rule, less any the owner declined) and the Notes choice, and writes a note in the xd for each change.
  It is derived by rule from the transcription plus the marks, never hand-edited, and made again whenever a mark is
  added or declined. The edition is what a publication publishes; the transcription is its evidence, beside it.

**The boundary** (agreed 2026-11-13): anything that changes what the puzzle says is EPP's (clue and header misprint
corrections, key-letter corrections, which printed lines are notes); anything mechanical about form is a downstream
reader's house style (which headers it keeps, author tidying, quote characters and similar). Who owns typography is
open (below). The record-keeping: the transcription stays as printed, every correction is a record in
`provenance.jsonl` naming who proposed it, and the note says what was printed. (This revises the owner's 2026-11-11
wording that a clue misprint is corrected "as far downstream as possible": it is corrected at the end of EPP, in the
edition.)

## What a publication publishes

In each publication repo:

| file | what it is |
|---|---|
| `edition/<xdid>.xd` | the edition (none while it is held) |
| `shipped.tsv` | the manifest: one row per puzzle the publication has ever listed, with its status |
| `xd/<xdid>.xd` | the transcription, the edition's evidence |
| `provenance.jsonl`, `pipeline/edition.json`, `pipeline/ship/` | who decided what, what each edition was made from, the ship records |

`xd/` stays the transcription: its readers (`records.py` for the record pages, `sync.py`, provenance's `xd`
fingerprint, the proof page's checks against the scan) all mean the transcription. The editions of puzzles shipped
before the step existed (Collegian 69, GAMES 35, World 2) are made the first time it runs, with no re-ship. Judge came
by the older path: its `xd/` files are transcriptions, and its manifest lists them with no edition (below).

**The manifest is the contract** with any downstream reader: which puzzles exist, which are published, where each file
is and its sha256, and why one is held or withdrawn. Its exact format is in `design/ship.md`, "The edition". A reader
reads it at a pinned commit (raw files at a sha, or a shallow clone) and records the sha, so what it took is
reproducible. Nothing in the manifest names a reader.

## Publishing the edition: the owner's mark per batch

Decided (owner, 2026-11-16, from the 2026-11-13 options): a batch's edition is published by the owner's
**"Publish the edition"** on the batch page, recorded with who and when (the ledger's `publish-edition:<batch>`),
and taken back by **"Take the edition back"**. Shipped is not the same as published: `blitz ship` writes the mark
into the manifest, and only rows of a published batch, with their edition made, are `published`. Publishing a series
together (GAMES's batches) is one mark per batch, pressed when the series is ready.

## Identity and change

- **Ids.** The publication's xdid is the manifest's key. A reader that keeps its own ids works them out from the
  manifest's `date` and `number`; nothing on EPP's side keeps a reader's id.
- **Changed.** A reader compares `edition_sha256` with the sha256 of what it took last: same, nothing to do;
  different, a revision.
- **A mark after publishing.** A misprint mark added, or one the owner declines, after the edition is published
  changes the edition and its sha256; the row stays published, and a reader sees a revision. A change to the
  transcription that leaves the edition the same changes only `transcription_sha256`.
- **Fixes go back to the publication.** A reader that finds a mistake reports it to EPP (a mark on the proof page),
  and the next edition carries it; hand-editing a published edition downstream makes re-reading it lose the edit.
- **Withdrawals.** A puzzle stays in the manifest with `status=withdrawn` and `why` (no longer in `xd/`: set aside as
  not a crossword, re-dated). Taking a batch's edition back puts its rows back to `held: not-published`; what a reader
  does with that is the reader's to say.

## Visibility: an open decision

"Publishing doesn't necessarily mean publishing publicly" (the owner, 2026-11-16: TBD). Today every publication repo is
public (`gh repo list`: judge, games, collegian, newyorkworld PUBLIC; the `-scans` twins private), so a published edition
in one is publicly readable, as the transcription already is. Nothing in slice 1 depends on that: the manifest and
`edition/` are files in the publication repo, the page crops a reader might want are on R2, and no step checks who can
read them. If a publication's editions were to be restricted:

- **Where they live**: the manifest and `edition/` would move out of the public repo, to a private repo (as the `-scans`
  twins are) or a private bucket, with the transcription and provenance kept where they are or moved with them; `blitz
  edition` would take where to write them as a setting per publication.
- **What a reader needs**: credentials for that place (a deploy key or token for a private repo, a bucket key), and the
  manifest's paths would be relative to that place rather than to the public repo.
- **What a public page may show**: the batch page, the as-shipped view and the record pages show the edition's text
  today; for a restricted publication they would show the status and the fingerprint only.

## What the repos held on 2026-11-13, and what was missing

All four publication repos are public (`gh repo list`: judge, games, collegian, newyorkworld
PUBLIC; every `-scans` twin PRIVATE). On their default branches today:

| repo | `xd/` | `provenance.jsonl` rows | ship record | `as-shipped/` | `gxd-exports.tsv` |
|---|---|---|---|---|---|
| judge | 531 | none (shipped by the older path) | none | none | yes, with gxd ids (`judge-001`) and `gxd_mr` |
| games | 37 | 35 | `pipeline/ship/games-1977-79.json` | none | yes, no `record_url` |
| collegian | 69 | 69 | `pipeline/ship/collegian-1976-81.json` | none | yes, no `record_url` |
| newyorkworld | 2 | 2 | `pipeline/ship/nyw-1914-c1.json` | none | yes, with `record_url` |

A provenance row already holds most of what a reader's editorial needs: the xd's fingerprint (`xd`,
12 hex), `printed` (kept lines with labels), `notes` (key letters corrected), `corrections`
(proposed misprints), `sources` (scan URLs per role), `said` (who reviewed). The review package on
R2 (`package_url`) holds public page crops for every puzzle, GAMES and Collegian included.

Missing then, for any reader: **one index per publication** saying which puzzles are published, with
a full-length fingerprint and a status (published, withdrawn, held: now `shipped.tsv`); a **mark that publishes the
edition** (shipped is not the same as published: now the owner's mark); the **as-shipped files** are not on any
default branch; Judge has **no provenance rows**; and nothing says **which commit** a set of files
is, so a fetch could catch a repo mid-push.


## As built: slice 1 (2026-11-16)

The edition step, the manifest and the mark that publishes the edition are in blitz (`src/blitz/edition.py`;
`blitz edition <pub>`; run by `blitz ship --write` and `--record`), documented in `design/ship.md`, "The edition", which
holds the manifest's exact format. Nothing on gxd's side changed. A cold review (blitz-work
`reviews/2026-11-16-gxd-pull-slice1-review.md`) led to fixes A to G, folded in below. Decided in building it:

- **Names.** The mark: "Publish the edition" / "Take the edition back" on the batch page; the ledger's
  `publish-edition:<batch>` (answers `publish`, `unpublish`); the review site's tables `edition_publish` and
  `edition_publishers` (`site/schema-8-edition-publish.sql`, not run yet); the ship record's `edition_published` and
  `editions_published`. The manifest: column `published` (the date the batch's edition was published), statuses
  `published`, `held`, `withdrawn`.
- **Who can publish.** Only the owner, by account id: the site's table takes a row only from an account in
  `edition_publishers`, the button shows only to such an account, and `blitz ship` counts a row only when its account
  is in the publication's ship rule `owner_ids`. A name typed on the proof page never counts (the review showed a guest
  typing the owner's name could publish). `blitz ship` takes in only rows for the batch it ships.
- **The repo holds everything the step used.** `blitz ship` (`--record` as well as `--write`) appends the site's
  records its plan used to the ledger before it makes the editions, the manifest and the record; `blitz edition` reads
  the repo alone and makes the same files again. A mark or a decline given on the site reaches the edition at the next
  `blitz ship --record` or `--write` for its batch.
- **The manifest's format** is the 2026-11-13 proposal's columns in that order (`release` renamed `published`), sha256
  of each file's text with LF line ends, rows in xdid order, `why` starting with a code for a held row.
- **record_url** is written only for a page recorded as published (`pipeline/record-pages.tsv` in the publication repo,
  which nothing writes yet), never made from the URL pattern: the World's older list (`gxd-exports.tsv`) names record
  pages that return 404. Judge's one-off manifest copies its live pages' URLs.
- **Judge** (`blitz edition judge --older-path`, refused for a repo with provenance rows): its `xd/` files are
  transcriptions (they carry `Source:`, `Provenance:` and OCR flags), so each row lists the transcription and no
  edition, `held`, with `why` "older-path: ... its edition went out by the older path, not through this manifest". A
  reader has nothing to take from it until Judge's editions are made by the step (which needs provenance rows for it).
- **A file in `xd/` with no provenance row** (GAMES's `games1977-09-01`) is listed, `held: no-provenance`.
- **The edition's own code list** (`edition.CODES`), not the frozen gxd export's `NOT_EXPORTED`: a cryptic with no key
  is published, with `cryptic-no-key` in `why`, pending the owner.
- **Taking the edition back** puts the batch's rows back to `held: not-published`; `withdrawn` is for a puzzle no
  longer in `xd/`, whose row keeps its last values and whose edition file is removed.
- **A mark whose words meant are already in its row** gets its note alone only when a record shows the swap (the
  packet's text-review change, or an edit record, on that row); otherwise the edition is held (`mark-unplaced`). The
  project manager's default pending the owner (`NOTED_NEEDS_EVIDENCE`).
- **Run once**: what each edition was made from is in `pipeline/edition.json`; who marked a correction isn't hashed;
  the version is a fingerprint of the code that makes the text; an edition whose record of marks doesn't describe its
  transcription is held (`marks-stale`), and a change of source is reported, not silent.

## Decisions for the owner

1. **Visibility** (above): are a publication's published editions public, and could one publication's be restricted?
   Related: **the publication repos are public, so committing `edition/` and `shipped.tsv` there is itself publishing**
   them, whatever a row's status says. Held and not-yet-published editions sit beside the published ones, and anyone
   can read them. Either that is fine (status is advice to readers, and these puzzles' transcriptions are public
   already), or unpublished editions stay out of the commit (the step writes them somewhere private, or the commit
   leaves out rows that aren't published), or editions live in a private place until published.
2. **What a published edition contains.** As built, the edition is the transcription plus the step's changes, so it
   keeps every blitz working header and block (`Source:`, `Assembly:`, `Text-Review:`, `Text step, unsure:`, `OCR
   review flags:` and the rest), which made sense while gxd's converter was to drop them. If the edition is the
   publication's finished file, it would hold the puzzle's own headers, the grid, the clues, `Puzzle notes:`,
   `Misprints corrected:`, `Answer key corrected:`, `Typed by hand:` and, for linked ends, `Numbering:`, with the
   transcription in `xd/` as the evidence. Not changed in this slice.
3. **The default Notes rule** (intro and instructions) picks lines that only make sense in the paper: the World's
   "SOLUTION NEXT WEEK.", the Collegian's eight "Answers in tomorrow's (Collegian) classifieds", and GAMES's "Fold this
   page! You are approaching" beside its real theme text. Set a Notes rule per publication on the batch page, or give
   such lines their own label in the text step, before any edition is published. Not changed in this slice.
4. **"Already applied" marks**: note only with a record of the swap, otherwise held (as built), or the note whenever
   the row reads the words meant.
5. **A cryptic with no key**: published with its code (as built), or held.
6. **A key correction the owner declines after publishing**: the edition is held (`key-declined`, as built) until a
   re-ship, or the row is withdrawn.
7. **Who owns typography** (blanks to `___`, dashes to `--`, quotes straight): the edition, as part of what the puzzle
   says in a usable form, or each reader's house style. Today it is promised in one place and done, for quotes only, in
   the frozen gxd export.
8. **One shared set of editorial guidelines** for EPP and its readers, starting from the Collegian's `editorial.md`, or
   EPP's own, with each reader's alongside.
9. **The puzzle's kind in the manifest** (a cryptic, a puzzle with no key), for readers that treat kinds differently.

## gxd as one downstream reader

Everything in this section is about gxd (the corpus kept with Saul Pwanson), the first reader expected to take EPP's
editions. Nothing in it is part of a publication's process. It was the 2026-11-13 note's main subject: instead of EPP
pushing to gxd (`blitz ship-export`, now frozen), gxd downloads and imports what EPP publishes, the way it does every
other outlet, with its own import code and its own editorial. Nothing from the v2 pipeline has gone to gxd yet.

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


### What in blitz is still gxd-specific

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


### Where each editorial step happens for gxd (agreed 2026-11-13; typography open)

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
gxd keeps those notes or strips them is house style (see "Decided by the owner" below).


### The linked-ends xd in gxd

gxd already holds the World in this shape: Saul's `nyworld/1913/nyw1913-12-21.xd` labels clues by
end pairs (`2-3. What bargain hunters enjoy. ~ SALES`) with `_` outside the diamond. EPP's
`nyw1914-03-01` differs in three ways: a `Clues: linked ends` header, a `Numbering:` notes section
mapping squares to numbers, and the slot's own label (`A4.`) where an end number wasn't read.
**Recommend**: the converter drops the `Clues:` header and the Numbering section to match gxd's
existing files, and holds for review any puzzle with a slot label (pairs couldn't all be read).
Whether xdformat should carry the numbering map is Saul's and xdformat's question, not a blocker.


### Provenance and credit in gxd

- **Receipts**: one row per puzzle, `ExternalSource` = the puzzle's **record page URL**
  (`https://everypuzzleproject.org/nyw/1914-03-01/`), `InternalSource` = the session archive,
  `SourceFilename` = the package folder `<pub>/<xdid>/` holding the xd as served, its provenance
  row, and the R2 page crops. CONTRIBUTING already allows a specific address and a package item.
- **Crossref** then gets its credit link from gxd's receipts (EPP's ExternalSource prefix marks the
  credit, the URL is the link), and `gxd-exports.tsv` and crossref's `fetch_epp.py` retire. EPP's
  record pages still want the crossref link back, which needs the gxd id: crossref can publish
  its own `epp.csv` mapping, which `records.py` reads instead of `gxd-exports.tsv`.


### gxd's side of publishing

The owner's mark publishes a batch's edition for every reader alike. On gxd's side: the EPP row runs on demand (no
nightly), with `GXD_PUBLISH=mr` and never `automerge`; a manifest row turning from published to held or withdrawn opens a
review MR there, never an automatic delete; gxd's id comes from the manifest's `date` and `number` by a rule in its
`outlets.tsv` row (`id=number` for Judge, whose gxd ids are `judge-001`; the date otherwise), with `overrides.tsv` for
the odd pin; a changed `edition_sha256` goes through the importer's update-in-place, held for review if it touches the
grid or answers. Whether gxd takes a puzzle whose only Ready is an AI's (the Collegian's 69) is gxd's to say.

### Slices: what is deleted or frozen in blitz

Freeze `ship-export` now (no linked-ends support, no new features). Then:

1. **Edition and manifest** (blitz, built 2026-11-16: "As built: slice 1" above): `corrected()` and the Notes
   rule moved into the edition step; `edition/` and `shipped.tsv` for every publication; the "xd as it will ship"
   views draw the edition; "Publish the edition" on the batch page. Nothing in gxd changed.
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
5. **Collegian, then GAMES** once each series' edition is published, each as one pull and one MR.


### Decided by the owner (2026-11-16)

These were the open questions for Saul. The owner is now primary on gxd and answered them:

- **Errors vs editorial changes.** An error found in an EPP puzzle in gxd (a wrong letter, a misread
  clue) is fixed in EPP and comes back into gxd as a re-import: errors go upstream. An editorial change
  that is gxd's own convention (a header, house style) may be made on gxd's side and is not upstreamed:
  EPP and gxd may have different editorial conventions.
- **Receipts stay simple.** `ExternalSource` is the EPP project URL, as elsewhere (Judge's 531 rows point
  at `https://github.com/EveryPuzzleProject/judge`), not a per-puzzle record page. The detailed URLs (record
  page, proof page, page crops, transcription) go in the source archive (its `MANIFEST.tsv` / package
  folder), not in receipts. This changes "Provenance and credit in gxd" above: crossref's per-puzzle credit
  link can't come from `ExternalSource` alone.
- **AI-Ready puzzles may ship**, into gxd too. What's needed is a process for working backwards when a
  problem is found after the fact: correct it in EPP, re-publish the edition, and gxd's re-import picks it
  up (the update-in-place path, held for review when it touches the grid or answers). To be written.
- **Notes stay in EPP; gxd's xd files get none.** EPP produces two flavors of note:
  - *editorial notes*: EPP's decision to correct what was printed (an obviously wrong letter in the answer
    key, a typo in a clue). These are what make EPP's files critical digital editions.
  - *reviewer notes*: the process (corrected x, y and z for an OCR smudge; made a guess).

  The line between them is fuzzy: a reconstructed passage where part of the page is unreadable could be
  either. So for now all of these notes stay in EPP (its edition, transcription, `provenance.jsonl` and
  records), open to anyone who wants to check them, and none appear in the xd files gxd takes in. gxd's
  converter strips them. gxd's own rule (a publisher's typo fixed in git only, no note) applies to EPP
  puzzles as to any other source. A sidecar file that travels with the xd is a possible later step,
  not part of this.

Still open:

- Linked-ends files: drop `Clues:` and `Numbering:` to match the 1913 files (the recommendation), or carry
  the numbering map in xdformat.
- Withdrawals: always a review MR in gxd, never an automatic delete (the recommendation).


### What I could not determine from the repos

- Whether crossref reads gxd's `receipts.tsv` today, and whether the crossref repo is public (it
  decides how `records.py` gets the gxd id back).
- Why `games/xd/` has 37 files but 35 provenance rows.
- Whether the as-shipped files are published to R2 for every batch (ship.md says `--publish` does;
  none is on a default branch).
- Whether gxd's xdlint accepts a slot label (`A4.`) in a pair-labelled clue list.
- How gxd counts a puzzle reached through EPP's repo whose underlying page is also in a gxd source
  archive already (Judge's `judge-scans-*.zip`): one receipts row or two.
