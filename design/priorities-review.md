# Priorities review: how the text works toward every crossword

Recorded 2026-11-10. A survey of the Every Puzzle Project's public text for places that promise or imply that the project will collect every crossword, with a proposed change for each, or a note that it is fine as is.

The headline stays: "Preserving every crossword ever printed". It is the goal. The fix is the text under it, which says how the project works toward it, at two levels:

- **The census** counts every publication that ever printed a crossword. A first and a last issue establish a run; sampled years give the counts.
- **The collection** preserves puzzles one whole run at a time. It finishes each series it starts and lists the issues it can't find as missing, with the date, so the record shows they ran. Whole runs because the corpus is worth most for comparison across a run (editor eras, constructor careers, reuse between publications, the 2016 plagiarism case), and none of that works on a sample.

Which series come next, in order: series nearly complete (the last 1% first); series whose only copies are decaying; a constructor's otherwise lost work; runs that mattered; series we can do (scans exist, pages OCR cleanly, rights clear enough to hold); series someone asked for. In practice, what we can do orders the queue. The full text is blitz's README, "How we work toward it".

Versions read: blitz `main` at 33a0159; `everypuzzleproject.github.io` `origin/main` at 49a3bcb (the local checkout's `main` is behind and holds only a redirect); `census` `origin/main` at 1ea564b; the org profile README (`EveryPuzzleProject/.github`, `profile/README.md`) through the GitHub API. Line numbers are from those versions.

## The proposed lede

For the home page (`index.html:89–94`) and the org profile (`profile/README.md:6–13`), replacing the current lede:

> The first crossword appeared in 1913. Since then countless newspapers, magazines and books have printed them, and most survive only on paper, or as page scans you can look at but not search. We count every publication that ever printed a crossword. We preserve their puzzles one whole run at a time, each transcribed into an xd file linked to the scan it was read from. We finish each series we start, and list the issues we can't find, so the record shows they ran. Runs we've nearly finished come first, then the ones most at risk. The finished puzzles join the xd Crossword Corpus, a research archive of crosswords from 1913 to today.

## everypuzzleproject.github.io (the home page and the blog): proposed, not edited

**index.html:88**, the headline, "Preserving every crossword ever printed". Unchanged.

**index.html:89–94**, the lede:

> We count the publications, index every puzzle they ran, and transcribe each one into an xd file, linked to the scan it was read from, so that it can be searched, studied and preserved.

Proposed: the lede above.

**index.html:7 and :11**, the meta and Open Graph descriptions:

> Preserving every crossword ever printed. Most old puzzles survive only on paper, or as scans you can look at but not search. We count the publications, index the puzzles, and transcribe each one into an xd file linked to its scan, so it is archived for good in the xd Crossword Corpus.

Proposed: "Preserving every crossword ever printed. Most old puzzles survive only on paper, or as scans you can look at but not search. We count every publication that printed them, and preserve their puzzles one whole run at a time, each an xd file linked to its scan, archived for good in the xd Crossword Corpus."

**index.html:10** (`og:title`), **index.html:16** (`og:image:alt`), **img/social-card.png** and **img/social_card.py:5, :104**: the headline. Unchanged; the social card stays as it is.

**New block on the home page**, after "How a puzzle gets from a page to the corpus": "How we work toward it", the same text as blitz's README section. The home page is the front door (design/entry-points.md), so the policy belongs there as well as in blitz.

**index.html:101**, the Find step, "The Crossword Census counts every publication known to have printed a crossword". Fine as is: this is the census's "every".

**index.html:104–105**, the Index step, "records which puzzles exist, which we have a copy of, and which pages are still wanted". Fine as is. This is the record of the gaps.

**index.html:152** and **blog/index.html:43**, the Collegian card, "we've indexed every one the university's open archive holds". Fine as is: a scoped, finished claim.

**publications.json:55**, the Globe, "Every Sunday since 1980 is indexed; the 1990s are missing entirely." Fine as is: the puzzles are known, the copies aren't. Optional clarification: "Every Sunday since 1980 is indexed; no copies of the 1990s have been found."

**blog/judge.html:79** (dek), **:97** ("Now every one is an xd file"), **blog/index.html:51**, **blog/pelham.html:50** ("all 531 that *Judge* printed from 1924 to 1939"). Fine as is: a finished run, bounded by its years.

**blog/judge.html:544–546**, "The census lists every publication known to have printed a crossword." Fine as is.

**blog/judge.html:551**, "Help complete *Judge*. archive.org's scans stop in January 1939, but *Judge* ran until 1947." Fine as is: finishing a series is the policy.

**blog/collegian.html:119**, "The goal is every one of these puzzles in xd". Fine as is: a whole run, which is the policy.

**blog/newyorkworld.html:172–173**, "'Nothing found' is not proof of absence". Fine as is.

**blog/games.html**: no completeness claims about the project. Fine as is.

**README.md** (the org site repo's own README): describes files only. Fine as is.

## EveryPuzzleProject/.github (the org profile on GitHub): proposed, not edited

**profile/README.md:3**, "**Preserving every crossword ever printed.**" Unchanged.

**profile/README.md:6–13**, the lede ("We count the publications, index every puzzle they ran, and transcribe each one into an xd file…"). Proposed: the lede above.

**profile/README.md:20–22**, "counts every publication known to have printed a crossword". Fine as is.

## census (the Crossword Census): proposed, not edited

The census is where "every" is literal, and its text is already careful ("a start, not a list"; "Nobody knows, and this page doesn't pretend to").

**README.md:4–5**, "The goal is every one of them, with what's known about each". Fine as is. Proposed addition after line 9 ("the census is what exists, the corpus is what we have"): "A publication whose puzzles are lost still gets an entry. The entry is the record that they existed."

**README.md:18–26** ("So the register below is a start, not a list"), **universe.md:3–6**, **universe.md:14** ("only distinct puzzles can ever be digitized once"). Fine as is.

**.github/ISSUE_TEMPLATE/report-publication.yml:9**, "Thanks for helping complete the census!" Fine as is.

**.github/ISSUE_TEMPLATE/report-puzzle.yml:2, :9**, "it helps map what exists"; "Every report helps." Fine as is.

**tools/render.py:243**, the census page's description, "A census of every publication that has printed crosswords". Fine as is.

**tools/render.py:41, :43, :47** and **README.md:53–68**: "every paper known to have printed a crossword", "every US newspaper by year", "can we list every US periodical by year?". Fine as is: research scopes, bounded by their sources.

## blitz (this repo): edited on this branch

**README.md**, new section "How we work toward it", after "What this is, and isn't": the census's methods, whole runs and why, missing issues listed with the date, the order of series, and feasibility as what orders the queue in practice. Under 200 words.

**design/entry-points.md:69–76**, the copy rules. The headline rule is unchanged; a new rule says the text under the headline says how we work toward it, at both levels, and that "every" about puzzles is for a finished run.

**README.md:14–19**, "We don't know how many puzzles were printed in newspapers, magazines, and books between 1913 and the present day". Fine as is.

**README.md:32–34**, "the goal is an accurate data archive of puzzles as they were printed". Fine as is.

**README.md** "hundreds of puzzles to check" and "preserved for posterity". Fine as is.

**docs/index.html:7, :11, :90–93**, blitz's home page: describes the tool, promises no completeness. Fine as is. **docs/index.html:195**, "Every puzzle, one square each": the board of a run. Fine as is.

**docs/blog/*.html**: redirects to the org site since 2026-11-06. Nothing to edit; the posts are reviewed above.

**src/blitz/review.html:862** (the tour) and **src/blitz/batch.html:217**. Fine as is.

**tools/social_card.py:5**: names the headline in its usage example. Unchanged.

**design/restructure.md:24** ("Facts about every publication"), **:15** ("100s of publications"). Fine as is. **design/restructure.md:47** plans a `missing` state, "known to exist, not found". That state is how a publication repo lists the issues it can't find, which the new README section promises. It isn't built yet: `judge/puzzles.tsv` today has only `restored` and `needs-person`. See follow-ups.

**design/judge-postmortem.md:13**, **design/followups.md:247**, **design/games-7779-next.md:6, :139**, **design/games-8082-plan.md:51**, **design/next-publication.md:150–152**, **design/pipeline.md:14, :183**: "every puzzle" and "completeness" here mean every puzzle of the run being processed. Fine as is, and in line with the whole-run policy.

**VOLUNTEER.md**, **MAINTAINING.md**, **CLAUDE.md:5**: no completeness claims. Fine as is.

## Not proposed

- The project name and the headline. Both stay.
- A citation for the thinking behind the text. If one is wanted, the home page block could thank Laura Braunstein, whose Crossword Con 2025 talk "Future-Proof Your Puzzle Archive" makes the case that an archive is about managing loss, with a link to the talk.

## Follow-ups found along the way

- The `missing` state in `puzzles.tsv` (design/restructure.md), so an issue known to have run but not found has a row and shows on its status page.
- blitz README's Publications table says *Judge* has "All 511 found puzzles reviewed"; the blog and the home page say 531.
- VOLUNTEER.md:3 says the person will "donate Claude usage"; the copy rules say "directing their Claude".
