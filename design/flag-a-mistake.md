# Flag a mistake on the live puzzle (design, not built)

Step 4 of the workflow in judge-postmortem.md: anyone looking at a published puzzle can say
"this is wrong", and the flag comes back as a card in the same narrow review tool, so the fix
is one click with its source recorded in the ledger.

## What exists to build on (2026-10-12)

- `flags`: one row per card (xdid, page, sq), with what the card shows in `card` and what raised
  it in `source` (`ocr`, `words`). Cards are closed, never deleted.
- `flag_checks`: each helper's answer to a card, which `site-import` and `import-reviews` turn into
  ledger entries credited "<names> (key-squares page)".
- The key-squares page shows open cards, earlier answers, and puts unseen puzzles first.

## The path

1. **On the live record** (crossref's puzzle page, or the review site's read-only puzzle view):
   a "Flag a mistake" link on each square of the answer grid and each clue. It opens a small
   form: what's wrong ("this letter should be ___", "this clue reads ___ on the scan"), an
   optional note, and a name. No account: the same guest sign-in as the review site.
2. **It writes a card.** A new `source = 'live'` row in `flags`, written through a Postgres
   function (`security definer`, rate-limited per guest, length-checked) since helpers can't
   write `flags` directly. The card carries everything the key-squares page needs (letter,
   answers and clues through the square, the crop geometry), so the function builds it from a
   per-puzzle JSON the publish step already uploads (the same fields `blitz key-squares` writes,
   for every square). The flagger's suggestion becomes the card's `suggest`, and their note a
   `why` line ("Flagged on the live site by Sam: the scan has an O").
   - A key-square flag lands on `page = 'key-squares'`. A clue flag needs its own page shape
     (the clue crop, our text, an edit box): `page = 'clues'`, the next narrow page to build.
   - If the square already has an open card, the flag adds a `why` line instead of a second card.
3. **The flagger is not the checker.** A live flag doesn't count as an answer: someone else
   checks the card against the scan. The flagger's suggestion is credited in the ledger record
   (`"flagged_by": "Sam (live site)"`), so the provenance shows both who spotted it and who
   confirmed it.
4. **Import** as today: the checker's answer becomes a `cell:` confirm or correction; a correction
   that came from a live flag also gets a note in the puzzle's provenance ("r3c4 corrected after a
   reader's flag, 2026-11-02"), shown on the review page.
5. **Republish.** The fixed xd goes out with the next export, and the card closes when the
   flag list is rebuilt.

## Open questions

- Where the live record lives for readers (crossref vs. the review site) decides where the link
  goes; the card side doesn't change.
- Spam: rate limits and a maintainer's "close card" in `blitz site-status` may be enough at
  first, since nothing reaches the ledger without a second person's check.
- A flag on a puzzle whose xd changed since the reader saw it: the card stores the xd
  fingerprint it was made against (the `xd` field cards already have), and the page says so.
