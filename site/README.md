# The public review site

People without Claude can help: they open a link and check a puzzle, as it now stands after the
agent's review, against the scan. No sign-up: submitting a review makes them a guest (kept in their
browser).

- **The page:** `docs/review/` on GitHub Pages (`blitz site-build` writes it from `src/blitz/proof.html`).
- **Who did what:** Supabase (guest sign-in; proofs, verdicts).
- **The scans and packets:** a Cloudflare R2 bucket, public read (`blitz site-publish` fills it).

## The review page (since 2026-10-09)

The page proofs the finished puzzle rather than listing the agent's changes. Part by part (title and
byline, answer key, Across, Down; the blank grid only when there's no answer key), each printed line sits
above our text, each answer's scanned squares above our letters. Reviewers' edits show as tracked
changes and their notes as comments, with layers to hide them; a helper edits in place and can comment.
Each part ends with "looks good" (with my N edits) or "there's a problem I couldn't fix", and the page
ends with a summary and one decision, Ready or Not ready.

On Submit it writes the whole review to `proofs` (run `site/schema-5-proofs.sql` once), which anyone can
read, so the next helper sees earlier helpers' edits and comments; and a row in `verdicts` for the progress
counts and the importer: `looks-right` only when Ready with no edits, otherwise `needs-work` (edits aren't
applied on import yet). `site-import` puts each puzzle's proofs under `proofs`.

### Not brought forward from the old page

The earlier change-by-change page is kept at `/review-old/` (`docs/review-old/`, built from
`src/blitz/review.html`, which is also `blitz watch`). These parts of it aren't in the new page yet:

- **Sign-in and accounts:** Google / GitHub / Discord sign-in, "keep my progress" (a guest's work moving to
  an account, `schema-2-sign-in.sql`), and the name shown with it. The new page has a free-text name
  that's saved with each review, but no profile.
- **Leaderboard:** the `profiles` table and `leaderboard` view are untouched, but nothing on the new page
  shows or fills them. (Its verdicts still count towards `puzzle_progress`.)
- **Welcome tour.**
- **Puzzle list sidebar** with year and grade filters, sorts (most in need, fewest checks first), checkup
  grade dots and per-puzzle progress; the new page has a picker and Next puzzle (in date order).
- **Checkup panel** (the grade and warnings above the tabs).
- **Per-change accept/reject** (`decisions`): helpers now fix the line instead. The importer's
  rejected-change path still reads `decisions`, so it simply gets none from the new page.
- **Reactions** (`schema-3-reactions.sql`).
- **Reports** (pointing at a clue on the scan): replaced by comments and edits on the line.

## Set up once

1. **Supabase.** Create a project (the free plan is fine).
   - SQL Editor: paste and run `site/schema.sql`.
   - Authentication > Sign In / Providers: turn on **Allow anonymous sign-ins**. That's what lets
     helpers start without signing up.
   - SQL Editor: also run `site/schema-2-sign-in.sql` (lets a guest's work follow them when they sign in).
   - Authentication > URL Configuration: Site URL `https://blitz.xwordapp.com/review/`; Redirect
     URLs `https://blitz.xwordapp.com/**` (and `http://localhost:8780/**` for testing locally).
   - Sign in with Google and GitHub (no email sending needed). Both ask for a callback URL:
     `https://<project>.supabase.co/auth/v1/callback`.
     - GitHub: Settings > Developer settings > OAuth Apps > New OAuth App (homepage
       `https://blitz.xwordapp.com`, callback as above); copy the Client ID and a new client secret
       into Supabase > Authentication > Sign In / Providers > GitHub, and enable it.
     - Google: Google Cloud Console > APIs & Services > OAuth consent screen (External; app name,
       support email), then Credentials > Create credentials > OAuth client ID (Web application;
       authorized redirect URI: the callback above); copy the Client ID and secret into Supabase >
       Providers > Google, and enable it.
   - Project Settings > API: note the Project URL, the `anon` key (public) and the `service_role`
     key (secret).
2. **Cloudflare R2.** Create a bucket (e.g. `blitz-scans`).
   - Settings > Public access: turn on the r2.dev address, or connect a custom domain (needs the
     domain's DNS on Cloudflare, e.g. `scans.xwordapp.com`).
   - Settings > CORS policy: allow `GET` from the review page's origin, e.g.
     `[{"AllowedOrigins": ["https://blitz.xwordapp.com"], "AllowedMethods": ["GET"]}]`.
   - R2 > Manage API tokens: create one with Object Read & Write on that bucket; note the Access
     Key ID, the Secret Access Key and your Account ID.
3. **The page.** Run `uv run blitz site-build`, then fill in `docs/review/config.js` (Project URL,
   anon key, the bucket's public URL), commit and push. For a custom address, add a CNAME record
   `blitz` → `everypuzzleproject.github.io` and set the custom domain in the repository's
   Settings > Pages.
4. **Your machine.** Put these in `~/.blitz-site.env`, one `KEY=value` per line (or set them as
   environment variables; never in a file in the repo):
   `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`,
   `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_PUBLIC_URL`.

## Welcome tour, year filter, reactions (old page, /review-old/)

- **Welcome tour.** The first thing a helper sees: what the project is, then how to pick a puzzle, read the
  scan, check each change, look at the result, pass judgement and leave a note. Its "Show this every time"
  box is on by default; unticking it stops the automatic tour (kept in that browser), and the **? Tour**
  button in the header brings it back.
- **Year filter.** A menu at the top of the puzzle list narrows it to one year (kept in the browser).
- **Reactions.** A ☺＋ button between the verdict buttons and the note lets a helper add an emoji to a puzzle,
  like Slack or Discord; each emoji shows how many people used it. Run `site/schema-3-reactions.sql` once in the
  Supabase SQL editor to switch it on; until then the site just hides the button. (In a local `blitz watch
  ?helper` preview, reactions are kept in the browser and only count you.)

## Each batch

```
uv run --extra site blitz site-publish ../blitz-work --batch judge-1931-32
```

uploads the reviewed puzzles (packet files only: the OCR, the review, the page and grid images)
and lists them on the page. Share the link. To bring back what helpers decided:

```
uv run blitz site-import -o ../blitz-work/site-decisions.json
```

then, in xword-ocr, `import-reviews <folder> --pubid judge --by "..." --decisions <that file>`, and
`uv run blitz site-close <puzzles...>` to take imported puzzles off the page.

`uv run --extra site blitz site-status` shows how many puzzles have been checked by how many helpers, and lists
the ones where helpers disagree (someone said needs work, or two helpers differ on a change). Each puzzle in
`site-import`'s file also carries `eyes` (how many checked it), `agreement` (`agreed`, `disputed`, `single` or
`none`) and `conflicts` (the changes helpers differ on); `site-import --agreed` writes only the puzzles that two or
more helpers agree on. The page opens the puzzle with the fewest checks first, so second opinions come for free.

How several helpers' decisions combine: a change is rejected if anyone rejected it (all their
notes kept, with names); a puzzle "needs work" if anyone said so; every report is kept.
`by` in the file shows each helper's own decisions.
