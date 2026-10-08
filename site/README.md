# The public review site

People without Claude can help: they open a link and check what an agent's review changed in each
puzzle, against the scan. No sign-up: their first click makes them a guest (kept in their browser),
so their work hangs together; they can add a name for the leaderboard, and sign in with Google or
GitHub to keep their progress on any device (their guest work moves to the account). It's the same page as `blitz watch`, in
helper mode (try it locally: `blitz watch` and open `/?helper`).

- **The page:** `docs/review/` on GitHub Pages (`blitz site-build` writes it).
- **Who did what:** Supabase (guest sign-in; decisions, verdicts, reports; leaderboard).
- **The scans and packets:** a Cloudflare R2 bucket, public read (`blitz site-publish` fills it).

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

## Welcome tour, year filter, reactions

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

How several helpers' decisions combine: a change is rejected if anyone rejected it (all their
notes kept, with names); a puzzle "needs work" if anyone said so; every report is kept.
`by` in the file shows each helper's own decisions.
