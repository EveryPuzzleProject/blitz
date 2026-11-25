# Formats: what each part of the project hands to the next

The project's parts meet at files. Each handoff has one document here that says what the files
hold, and a check that reads them (`blitz check-format`). The design this belongs to is
`design/v3-agent-forward.md`, "The handoffs, written down".

| Handoff | From, to | Document | Check |
|---|---|---|---|
| Page folder: `pages.tsv` and images | fetch to xword-ocr | xword-ocr `docs/sources.md` | not yet |
| Issue census: every grid, key and clue list with its fate | xword-ocr to blitz | xword-ocr `docs/census.md` | not yet |
| **Proof packet**: one puzzle's folder | xword-ocr (and `blitz hand-packets`) to the proof page, review, ship | [proof-packet.md](proof-packet.md) | `blitz check-format` |
| Triage record, decisions ledger, ship record | inside blitz | `design/ship.md`; xword-ocr `docs/ship-gate.md` | not yet |
| Annotated xd and its provenance row | blitz to any reader | not yet written (`design/ship.md`, `design/hand-read.md`) | not yet |
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
