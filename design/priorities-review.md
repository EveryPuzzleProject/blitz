# Priorities review: where the text promises every puzzle

Recorded 2026-11-10. A survey of the Every Puzzle Project's public text for places that promise or imply that the project will collect every crossword, with a proposed replacement for each, or a note that it is fine as is.

The line the proposals draw: **the census aims at every publication; the collection aims at puzzles by priority.** Knowing that a puzzle ran is cheap and is a record in itself, so "every" is honest about publications. Transcription costs real work, so the collection says what it takes first and records what it can't find. The project name stays. "Every" about puzzles also stays where it describes a finished run ("every crossword in *Judge* from 1924 to 1939").

The policy itself is the new section "What we collect first" in blitz's README.

Versions read: blitz `main` at 33a0159; `everypuzzleproject.github.io` `origin/main` at 49a3bcb (the local checkout's `main` is behind and holds only a redirect); `census` `origin/main` at 1ea564b; the org profile README (`EveryPuzzleProject/.github`, `profile/README.md`) through the GitHub API. Line numbers are from those versions.

## everypuzzleproject.github.io (the home page and the blog): proposed, not edited

This is where the promise is loudest, because the headline says it.

**index.html:88**, the headline:

> Preserving every crossword ever printed

Proposed: **Accounting for every crossword ever printed.** "Accounting for" covers all three outcomes: transcribed, indexed, known only to have existed. It keeps the ambition and the rhythm. A second option, if a headline that names both halves is wanted: "Every crossword publication counted. The puzzles that matter most, preserved first."

**index.html:7 and :11**, the meta and Open Graph descriptions:

> Preserving every crossword ever printed. Most old puzzles survive only on paper, or as scans you can look at but not search. We count the publications, index the puzzles, and transcribe each one into an xd file linked to its scan, so it is archived for good in the xd Crossword Corpus.

Proposed: "Accounting for every crossword ever printed. Most old puzzles survive only on paper, or as scans you can look at but not search. We count the publications that printed them, index the puzzles we can find, and transcribe them into xd files linked to their scans, the rarest and most consequential first, so they are archived for good in the xd Crossword Corpus."

**index.html:10**, `og:title`:

> Every Puzzle Project: preserving every crossword ever printed

Proposed: "Every Puzzle Project: accounting for every crossword ever printed".

**index.html:16**, `og:image:alt`, and the image it describes, **img/social-card.png**, made by **img/social_card.py:5 and :104**:

> --words "Preserving every crossword ever printed"

Proposed: change the default words to the new headline, rerun the script, and update the alt text to match. Blitz's copy of the script (`tools/social_card.py:5`) names the same words in its usage example; change it in the same pass.

**index.html:89–94**, the lede:

> We count the publications, index every puzzle they ran, and transcribe each one into an xd file, linked to the scan it was read from, so that it can be searched, studied and preserved.

Proposed: "We count the publications, index the puzzles they ran, and transcribe them into xd files, each linked to the scan it was read from, so they can be searched, studied and preserved. We can't transcribe every puzzle, so we choose: the rarest copies and the puzzles that mattered come first, and a puzzle we know ran but can't find stays on the record."

**New block on the home page**, after "How a puzzle gets from a page to the corpus": a short "What we collect first" with the same five priorities as blitz's README. The home page is the front door (design/entry-points.md), so the policy belongs there more than in blitz; blitz's README carries it now because this branch can edit only blitz.

**index.html:101**, the Find step:

> The Crossword Census counts every publication known to have printed a crossword

Fine as is. This is the census's "every", and it is the right one.

**index.html:104–105**, the Index step: "records which puzzles exist, which we have a copy of, and which pages are still wanted." Fine as is. This is already the loss record; the proposed lede leans on it.

**index.html:152** and **blog/index.html:43**, the Collegian card: "we've indexed every one the university's open archive holds". Fine as is: a scoped, finished claim.

**publications.json:55**, the Globe: "Every Sunday since 1980 is indexed; the 1990s are missing entirely." Fine as is. It reads as a contradiction at a glance (indexed, yet missing), but it means the puzzles are known and the copies aren't, which is the distinction this review is about. Optional clarification: "Every Sunday since 1980 is indexed; no copies of the 1990s have been found."

**blog/judge.html:79** (dek), **:97** ("Now every one is an xd file"), **blog/index.html:51**, **blog/pelham.html:50** ("all 531 that *Judge* printed from 1924 to 1939"). Fine as is: a finished run, bounded by its years.

**blog/judge.html:544–546**: "The census lists every publication known to have printed a crossword." Fine as is.

**blog/judge.html:551**: "Help complete *Judge*. archive.org's scans stop in January 1939, but *Judge* ran until 1947." Fine as is. Finishing a run to its last issue is one of the priorities.

**blog/collegian.html:119**:

> An index is the first milestone. The goal is every one of these puzzles in xd

Fine as is; a bounded run. Optional clarification, which ties the post to the policy without retracting anything: after "came from", add "They come early in the queue: they are the start of a major constructor's career, in a paper no corpus has."

**blog/newyorkworld.html:172–173**: "'Nothing found' is not proof of absence". Fine as is, and the right tone for the rest.

**blog/games.html**: no completeness claims about the project. Fine as is.

**README.md** (the org site repo's own README): describes files only. Fine as is.

## EveryPuzzleProject/.github (the org profile on GitHub): proposed, not edited

**profile/README.md:3**:

> **Preserving every crossword ever printed.**

Proposed: the same headline as the home page.

**profile/README.md:8–9**:

> We count the publications, index every puzzle they ran, and transcribe each one into an xd file

Proposed: the same lede as the home page.

**profile/README.md:20–22**, "counts every publication known to have printed a crossword". Fine as is.

## census (the Crossword Census): proposed, not edited

The census is the one place where "every" is the honest goal, and its text is already careful ("a start, not a list"; "Nobody knows, and this page doesn't pretend to"). The proposals only make the loss record explicit.

**README.md:4–5**:

> The goal is every one of them, with what's known about each

Fine as is. Proposed addition after line 9 ("the census is what exists, the corpus is what we have"): "A publication whose puzzles are lost still gets an entry. The entry is the record that they existed."

**README.md:18–26** ("So the register below is a start, not a list"), **universe.md:3–6**, **universe.md:13–14** ("only distinct puzzles can ever be digitized once"). Fine as is.

**.github/ISSUE_TEMPLATE/report-publication.yml:9**: "Thanks for helping complete the census!" Fine as is: completeness is the census's aim.

**.github/ISSUE_TEMPLATE/report-puzzle.yml:2, :9**: "it helps map what exists"; "Every report helps." Fine as is. A sighting is the record a lost puzzle leaves.

**tools/render.py:243**, the census page's description: "A census of every publication that has printed crosswords". Fine as is.

**tools/render.py:41, :43, :47** and **README.md:53–68**: "every paper known to have printed a crossword", "every US newspaper by year", "can we list every US periodical by year?". Fine as is: research scopes, bounded by their sources.

## blitz (this repo): edited on this branch

**README.md**, new section "What we collect first", after "What this is, and isn't". The selection policy: the census aims at every publication; the collection takes puzzles by priority (decaying sole copies, a constructor's only surviving work, puzzles with consequences, first and last issues and editor changes, a sample of the rest); lost puzzles stay listed in their publication's repo. 150 words.

**design/entry-points.md:69–70**, the copy rules:

> The headline is "Preserving every crossword ever printed".

Edited: the rule now points at this review for the replacement headline, and a new rule says "every" belongs to the census, not the collection, and about puzzles only for a finished run. The headline itself is unchanged until the home page changes.

**README.md:14–19**, "We don't know how many puzzles were printed in newspapers, magazines, and books between 1913 and the present day". Fine as is; already honest.

**README.md:32–34**, "the goal is an accurate data archive of puzzles as they were printed". Fine as is.

**README.md:47**, "there are hundreds of puzzles to check"; **README.md:213**, "preserved for posterity". Fine as is.

**docs/index.html:7, :11, :90–93**, blitz's home page: describes the tool, promises no completeness. Fine as is. **docs/index.html:195**, "Every puzzle, one square each": the board of a run. Fine as is.

**docs/blog/*.html**: redirects to the org site since 2026-11-06. Nothing to edit; the posts are reviewed above under the org site.

**src/blitz/review.html:862** (the tour), "Thousands of old newspaper and magazine crosswords survive only as scanned pages"; **src/blitz/batch.html:217**, "every puzzle needs a person to check it". Fine as is.

**design/restructure.md:24** ("Facts about every publication"), **:15** ("100s of publications"). Fine as is. **design/restructure.md:47** plans a `missing` state, "known to exist, not found". That state is the collection's loss record, and the new README section relies on it. It isn't built yet: `judge/puzzles.tsv` today has only `restored` and `needs-person`. See follow-ups.

**design/judge-postmortem.md:13** ("Every printed number was found"), **design/followups.md:247** ("a completeness report"), **design/games-7779-next.md:6, :139**, **design/games-8082-plan.md:51**, **design/next-publication.md:150–152**, **design/pipeline.md:14, :183**: "every puzzle" and "completeness" here mean every puzzle of the run being processed. Fine as is: operational, not a promise about the universe.

**VOLUNTEER.md** and **MAINTAINING.md**: no completeness claims. Fine as is.

**CLAUDE.md:5**, "Every puzzle the project produces is an xd file that should be correct". Fine as is: a quality rule about what is produced.

## Not proposed

- The project name. It stays.
- A citation in the public text for the idea behind the policy. If one is wanted, the home page's "What we collect first" could thank Laura Braunstein, whose Crossword Con 2025 talk "Future-Proof Your Puzzle Archive" makes the case that an archive is about managing loss, with a link to the talk.

## Follow-ups found along the way

- The `missing` state in `puzzles.tsv` (design/restructure.md), so a puzzle known to have run but not found has a row and shows on its status page. The README's last sentence describes the policy; this would make every publication repo carry it out.
- blitz README's Publications table says *Judge* has "All 511 found puzzles reviewed"; the blog and the home page say 531.
- VOLUNTEER.md:3 says the person will "donate Claude usage"; the copy rules say "directing their Claude".
