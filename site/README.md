# The public review site

People without Claude can help: they open a link, sign in with their email, and check what an
agent's review changed in each puzzle, against the scan. It's the same page as `blitz watch`, in
helper mode (try it locally: `blitz watch` and open `/?helper`).

- **The page:** `docs/review/` on GitHub Pages (`blitz site-build` writes it).
- **Who did what:** Supabase (sign-in by emailed link; decisions, verdicts, reports; leaderboard).
- **The scans and packets:** a Cloudflare R2 bucket, public read (`blitz site-publish` fills it).

## Set up once

1. **Supabase.** Create a project (the free plan is fine).
   - SQL Editor: paste and run `site/schema.sql`.
   - Authentication > URL Configuration: set the Site URL to the review page's address
     (e.g. `https://blitz.xwordapp.com/review/`) and add it under Redirect URLs.
   - Authentication > Emails: Supabase's built-in mail sends only a few sign-in emails an hour.
     Before sharing the link widely, add your own SMTP (e.g. Resend's free tier) under SMTP Settings.
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
4. **Your machine.** Set these environment variables (never put them in a file in the repo):
   `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`,
   `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_PUBLIC_URL`.

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
