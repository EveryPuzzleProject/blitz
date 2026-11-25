# The annotated xd

The xd file a publication's repo holds for each shipped puzzle (`xd/<xdid>.xd`), and its
edition (`edition/<xdid>.xd`). It is what the whole process produces: the puzzle as printed,
with what EPP adds to it.

This is the reference for readers and for the check. The reasoning and the owner's decisions
are in `design/xd-fields.md` (EveryPuzzleProject/blitz#114, agreed 2026-11-25); where the two
differ, that design is right and this file is out of date.

```
uv run blitz check-format <an .xd file, or a folder of them> [--notes] [--lines]
```

## Two forms

| Form | Told by | Where it is |
|---|---|---|
| **field** | the file starts with `## Metadata` | the New York World's Nos. 1-33 (shipped 2026-11-25); everything new |
| **block** | parts set apart by two blank lines, no `## ` | Judge (531), GAMES (36), Collegian (69): shipped earlier, kept as shipped |

Shipped puzzles keep their form. A reader tells them apart by the first line; the manifest's
`form` column (`v1` block, `v2` field) says the same once blitz's `claude/manifest-feed-columns`
branch lands.

## The field form

Every statement in the file is one of four kinds, each with its own place. Nothing printed is
ever replaced: a correction sits beside the original.

| Kind | What | Where |
|---|---|---|
| 1 | the puzzle as printed | the grid, the clue lines, the headers `Title` `Author` `Editor` `Number` `Date` `Copyright` |
| 2 | the paper's other words | `## Printed` |
| 3 | EPP's own statements | named fields, below |
| 4 | provenance: who read it, how it was checked | not in the xd: `provenance.jsonl` and the ship record |

### Sections

`## Metadata` first, then `## Printed`, `## Grid`, `## Clues`, and where needed `## Design`,
`## Labels`, `## Notes`. Metadata, Grid and Clues are required. Sections are set apart by two
blank lines.

### ## Metadata

One `Name: value` per line.

| Header | Kind | Holds |
|---|---|---|
| `Title`, `Author`, `Editor`, `Number`, `Copyright` | 1 | as the paper printed them; left out when not printed |
| `Date` | 1 | `YYYY-MM-DD`. Required |
| `<Header>-Correction` | 3 | a printed header as meant, after the header it corrects: `Author-Correction:` |
| `Description` | 3 | what the grid alone doesn't show: the shape, a centre panel, an ornament |
| `Incomplete` | 3 | what is missing and why |
| `Numbering` | 3 | `as-printed` when the puzzle keeps the paper's own numbering (`## Labels`) |
| `Source`, `Solution-Source`, `Clue-Source` | citation | the scans the puzzle, its key and its clues were read from |
| `Notes` | | retired as a catch-all; a note in the check |

Working headers (`Assembly`, `Text-Review`, `Solution`, `Shipped`, `Proof`, `Provenance` and the
like) are provenance and are a problem in this form.

### ## Printed

The paper's words that are not the puzzle, verbatim, one per line as `label: text`. A label may
say which one in parentheses: `heading (left of grid): Can You`.

Labels in use: `heading`, `subheading`, `number`, `intro`, `intro heading`, `instructions`,
`credit`, `art credit`, `banner`, `tagline`, `note`, `panel`, `prize notice`, `centre`,
`centre block`, `solution heading`, `solution caption`, `solution intro`, `solution centre`,
and the text step's (`test-solver`, `kind`, `answers`, `section`, `furniture`, `other-puzzle`,
`other`). A label outside the list is a note, not a problem: the list grows with the
publications.

### ## Grid

One row per line, all one length. A letter is a square's answer, `#` a black square, `_`
outside the puzzle, `.` a square with no answer known. The letters are the printed key's, also
where the key is probably wrong.

### ## Clues

A clue is `<label>. <text> ~ <ANSWER>`, with `A12` or `D7` for the label (the paper's own
pair, `1-3`, under `Numbering: as-printed`). The ` ~ ` is always there, with nothing after it
when no answer is known. Fields follow their clue's line as `<label> ^Key: value`:

| Key | Holds |
|---|---|
| `^Printed:` | the clue's label as printed (`4-5`), where the paper numbered otherwise |
| `^Fits:` | the label that fits the grid, where `^Printed:` is a misprint. Never without `^Printed:` |
| `^Correction:` | the whole clue as meant, for a typesetting slip. Not period spelling or style |
| `^Answer-Correction:` | the answer as meant, where the printed key is probably wrong. The grid keeps the printed letters |
| `^Note:` | free text for a person; never the only place a fact lives |

### ## Design, ## Labels, ## Notes

`## Design`: square styles (a given square is `given: true`). `## Labels`: the printed labels
of a puzzle whose own numbering is kept. `## Notes`: a note `blitz ship` adds after the clues.
The check does not look inside these three yet.

## The block form

The shape `blitz ship` wrote before the field form: a header block, the grid, the clues, and
notes, set apart by two blank lines (`design/ship.md`).

- **Headers**: `Title`, `Author`, `Byline`, `Date`, `Number`, `Feature`, `Source`,
  `Solution-Source`, `Clue-Source`, and working headers (`Solution`, `Assembly`, `Text-Review`,
  Judge's `Provenance`).
- **Clues**: `A12. text ~ ANSWER`. A second clue set is a field on the clue,
  `A12 ^Easy: text` (GAMES).
- **Notes**: blocks under a head line: `Printed with puzzle:`, `Assembly flags:`,
  `OCR review flags:`, `Warnings:`, and those ship adds (`Answer key corrected:`,
  `Typed by hand:`).

The check holds the block form only to its structure: three parts or more, header lines, a
`Date`, a rectangular grid, clue lines with ` ~ `.

## The edition

A field-form transcription is its own edition: nothing is rewritten, since the corrections are
already fields. A block-form edition is the transcription with the corrections applied and
`Puzzle notes:` and `Misprints corrected:` blocks added (`design/ship.md`, "The edition").

## What the check found on 2026-11-25

Run on each publication's `origin/main`:

| Files | Result |
|---|---|
| Judge 531, GAMES 36, Collegian 69 (block) | no problems |
| New York World `xd/`, 33 (field) | no problems; 8 notes |
| New York World `edition/`, 33 | **57 problems** in the same files |

- **The World's editions on main are not valid field form.** The edition step appended a
  block-form `Puzzle notes:` passage after `## Clues`, where a reader takes each line for a
  clue. blitz's unmerged `claude/edition-field-form` branch stops doing that; the editions need
  making again once it lands, and before the edition is published.
- **Seven printed labels are spelt two ways**: `solution-caption` (4) and `solution-centre` (3)
  beside `solution caption` and `solution centre`.
- **One file has no clue lines** (`nyw1914-07-19`, No. 28: the paper printed none).

## Open

1. **The version marker.** `design/xd-fields.md` leaves it to be worked out. Today the first
   line tells the forms apart, which is enough for a reader but is not a version.
2. **The labels of `## Printed`** are a growing list, not a fixed one, and a label may carry a
   remark in parentheses (`intro (garbled)`, `heading (the reprint's own)`). Should the remark
   be the paper's place only, with judgements such as "garbled" moved to a `^Note:` or
   `Description:`?
3. **A grade.** `design/v3-agent-forward.md` asks whether a puzzle's grade is written in the
   xd. By the four kinds it is provenance (how the puzzle was checked) and stays out;
   `Incomplete:` already says what a reader of the puzzle needs.
