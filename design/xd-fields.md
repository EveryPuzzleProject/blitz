# The fields EPP adds to an xd: a proposal

Status: agreed by the owner, 2026-11-25 ("very good, very clever"), with the decisions at the end; the hand-read World Nos. 1-33 use it (shipped, newyorkworld #37). Not yet built: the gxd export and the edition step in this form. It comes out of the World's Nos. 1-33 (batch `nyw-1914-s1`, the
hand-read files in newyorkworld's `hand-read/`). There the owner found that the `Notes:` header had become a
catch-all, and asked for a formal definition of what EPP adds to an xd.

## Why

Read No. 21's `Notes:` today (nyw1914-05-10):

> A 19-wide diamond with a diamond-shaped hole in the centre (…shown as _), so the middle column holds two short
> words (53-54 TULLE above the hole, 55-56 ILIAD below). Number printed in the heading ("FUN'S CROSS-WORD PUZZLE
> No. 21"). Credit as printed in the intro: "Miss Elizabeth M. Rutzinger, who sent in…". Read by hand from the
> Milwaukee Sentinel's page (…png), solution from …png, by Claude, 2026-11-16.

That one header holds four kinds of thing:
- our description of the grid;
- text the paper printed (the intro);
- where a header came from;
- who transcribed the puzzle, how and when.

No reader can pull one of them out without parsing English.

Elsewhere the same kinds of fact are spread across three shapes:
- **Structured clue metadata** (`^Printed:`, `^Fits:`, `^Correction:`).
- **Prose in `^Note:`** ("misprint: the pair that fits the grid is 18-19").
- **Prose that blitz's edition step writes into Notes** ("A71 is printed 'cockail'; corrected to 'cocktail'.",
  `Answer key corrected:`).

Blitz's earlier ships also add working headers (`Assembly:`, `Text-Review:`, `Numbering-Rule:`, …), so the c1 copy
of No. 11 and the hand-read copy of No. 11 don't share a single header beyond `Date:` and `Number:`.

## The rule

**Every statement in the file is one of four kinds, and each kind has its own place:**

| kind | what it is | where it goes |
|---|---|---|
| 1. the puzzle as printed | the grid's letters, the clues, and headers the paper printed for this puzzle | the grid, clue lines, `Title:` `Author:` `Number:` `Date:` `Copyright:` |
| 2. other printed text | the paper's words that aren't the puzzle: heading, intro, credit, instructions, captions | `## Printed`, one labelled line each, verbatim |
| 3. EPP's editorial statements | what we think was meant, what's suspect, what's missing, our description | named fields (below), each with one meaning |
| 4. provenance | who read it, from which scan, how it was checked, when | `provenance.jsonl` and the ship record, not the xd (the xd keeps only the scan citations, `Source:` and `Solution-Source:`) |

The original text is never replaced. A correction sits beside what was printed, and a reader chooses which to show.
That's the owner's rule of 2026-11-25 for clue typos, and here it applies to everything.

## The fields (kinds 2 and 3)

**On a clue** (`<ref> ^Key: value`, the v4 clue-metadata form, after the clue line):

| key | value | meaning |
|---|---|---|
| `^Printed:` | the clue's label as printed (the World's `4-5`) | only where the paper numbered differently from the xd |
| `^Fits:` | the label that fits the grid | only where `^Printed:` is a misprint |
| `^Correction:` | the whole clue as meant | the printed clue has a typesetting slip (a dropped letter, a stray comma); never period spelling or style |
| `^Answer-Correction:` | the answer as meant | the printed answer (from the key) is probably wrong; the grid keeps the printed letters: ROAB for "A son of Lot" → `^Answer-Correction: MOAB`. Where what was meant can't be named (YAT, "A city in northern Africa"), a `^Note:` says so instead |
| `^Note:` | free text | an explanation for a person, never the only place a fact lives |

**On the puzzle** (headers):

| header | meaning |
|---|---|
| `<Header>-Correction:` | a printed header as meant, beside it (agreed name): `Author: Elizabeth M. Rutzinger` with `Author-Correction: Elizabeth M. Butzinger` |
| `Description:` | our description of what the grid alone doesn't show: the shape, a centre panel, a printed ornament |
| `Incomplete:` | what's missing and why: "no printed answer key found", "the inner star is left out; see Description" |
| `Notes:` | retired as a catch-all. If kept, it holds only what the old gxd form expects (see the open questions) |

**On the grid:**
- `## Design`: square styles. Givens are `given: true`; decoration that separates words is a block.
- `## Labels`: the printed labels, for a puzzle whose own numbering is kept (the metas, Nos. 18 and 27).

**`## Printed`**: the paper's other words, one per line as `label: text`. The labels are blitz's printed-line labels
(`heading`, `intro`, `credit`, `instructions`, `solution caption`, …). It replaces quoting the intro inside Notes,
and it's where a downstream reader's Notes rule picks from.

## What changes

1. **Answer-key misprints are recorded beside the print, not over it.** Today `design/ship.md` corrects a misprinted
   key letter in the transcription, with a note. Under this rule the grid keeps the printed letter and each clue it
   spoils gets `^Answer-Correction:`. The owner, 2026-11-25: "flag the probable mistake but leave it in". Also:
   correcting the key "is often necessary just so that the review tool makes sense… That doesn't mean… that we would
   overwrite it in the XD file, just that we would include the corrected version". So the review tool may show the
   corrected key, and the xd still holds both. RABIT, for "A wooden drinking vessel", is archaic but right, so it gets
   no flag.
2. **The edition step stops rewriting text.** Corrections are already in the file as fields, so the edition no
   longer changes clue text or writes prose notes. Choosing the printed or the corrected text becomes a reader's
   house style (the `publishing-editions.md` boundary moves one step down). This also answers that note's open
   decision 2, what a published edition contains: kinds 1-3, and no working headers.
3. **Provenance leaves the xd.** "Read by hand by Claude", `Assembly:`, `Text-Review:` and the OCR review flags go
   to `provenance.jsonl` and the ship record, which already hold most of it.
4. **The hand-read World files move to this form.**
   - Their Notes split into `Description:`, `## Printed` and provenance.
   - Each `^Note: misprint…` reduces to `^Printed:` + `^Fits:`.
   - The answer-key misprints the first reading noted get `^Answer-Correction:`.
5. **No. 13** (nyw1914-03-15): its inner star leaves the grid. The star's clues and its shape go to `Description:`
   as text, and the file gets `Incomplete:`. The owner's call: hard or impossible to represent for now.

## A worked example: No. 4, A14 (nyw1914-01-11)

```
## Metadata
Date: 1914-01-11
Copyright: New York World
Description: A 13-wide diamond with a black cross in the centre.
Source: Milwaukee Sentinel, 1914-01-11, p. …
Solution-Source: Milwaukee Sentinel, 1914-01-18, p. 83

## Printed
heading: …
instructions: …

## Clues
A14. A son of Lot. ~ ROAB
A14 ^Printed: 15-16
A14 ^Answer-Correction: MOAB
```

## Decided (the owner, 2026-11-25)

1. **Names.** `^Correction:` (a clue's text), `^Answer-Correction:` (its answer) and `<Header>-Correction:`
   (a header's, e.g. `Author-Correction:`): the same "X-Correction" pattern throughout.
2. **gxd gets a minimal edition in the old form.** "When we're exporting to GXD, going back to the old version is fine…
   at some point we'll adopt the V4 version. We're just not there yet." The gxd edition is the blank-line form and
   "could be fairly minimal. It'll link back to EPP": it needn't carry every EPP field. The full file, with every
   field, is EPP's own.
3. **Not registered in xdformat.** These are EPP's extensions, published on the EPP site, not proposed for the spec.
   (xdformat #47, the World's printed numbering, is a separate proposal.)
4. **Shipped puzzles keep their shape.** Judge, GAMES and the World's c1 batch stay as shipped. Files of both
   shapes will coexist, which calls for a version marker (v1, v2) to be worked out.
