# Formats: what each part of the project hands to the next

The project's parts meet at files. Each handoff has one document here that says what the files
hold, and a check that reads them (`blitz check-format`). The design this belongs to is
`design/v3-agent-forward.md`, "The handoffs, written down".

| Handoff | From, to | Document | Check |
|---|---|---|---|
| Page folder: `pages.tsv` and images | fetch to xword-ocr | xword-ocr `docs/sources.md` | not yet |
| **Assembly record**: one issue's parts linked into puzzles, with what it was made from and how long it took | xword-ocr's assembly to every step after it | [assembly-record.md](assembly-record.md) | `blitz check-format` |
| Issue census: every grid, key and clue list with its fate | xword-ocr to blitz | xword-ocr `docs/census.md` | not yet |
| **Proof packet**: one puzzle's folder | xword-ocr (and `blitz hand-packets`) to the proof page, review, ship | [proof-packet.md](proof-packet.md) | `blitz check-format` |
| Triage record, decisions ledger | inside blitz | `design/ship.md`; xword-ocr `docs/ship-gate.md` | not yet |
| **Ship record**: every puzzle of a batch with its status, its queue and its grade | blitz ship to the batch page and any reader | [ship-record.md](ship-record.md) for the grades, the digest and the stubs; `design/ship.md` for the rest | `blitz check-format` (the grade fields) |
| **Annotated xd**: the shipped transcription and its edition | blitz to any reader | [annotated-xd.md](annotated-xd.md); the design is `design/xd-fields.md` | `blitz check-format` |
| Provenance row (`provenance.jsonl`) | blitz to any reader | `design/ship.md`, "What it writes"; its `grade` in [ship-record.md](ship-record.md) | `blitz check-format` (its `grade`) |
| Edition and `shipped.tsv` | blitz to any reader | `design/ship.md`, "The edition" | not yet |

## Rules for a format

- **Version 1 is what was on disk when the document was written.** Nothing is rebuilt to fit a
  document; the document is written to fit the files.
- **The version is a field in the file**, `"format": "<name>/<n>"`. A file without one is
  version 1.
- **A new version is a new section of the same document**, saying what changed and from which
  commit of which writer. A reader says which versions it reads.
- **A change that only adds an optional field needs no new version.** A change to what a field
  means, a field removed, or a field newly required does.
- **The check reads files and nothing else**: no scan, no model, no stage code. It says
  "problem" where a reader would break or be misled, and "note" where a file is a valid older
  form.
- **Field names and coordinates are part of the format.** A view or a tool reads them as
  documented and never works out its own.
