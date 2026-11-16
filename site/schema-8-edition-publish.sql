-- The batch page's "Publish the edition" (since 2026-11-16; blitz design/ship.md, "The edition";
-- design/publishing-editions.md). The last step of a publication's process: the owner publishes a batch's edition
-- (its shipped puzzles' editions, edition/<xdid>.xd, listed as published in the publication's shipped.tsv);
-- "Take the edition back" undoes that. This is not the review site's own "publish" (blitz site-publish,
-- ship --publish), which puts packets and records on this site.
-- Publishing the edition is the owner's alone, and goes by account id, never by the name typed on the proof page
-- (anyone can type a name). Two places say who the owner is, both by Supabase user_id:
--   edition_publishers (below): the accounts this table takes a row from (its policy refuses anyone else's), and the
--     accounts the batch page shows the button to;
--   each publication's fixes/ship-rule.json `owner_ids`: the accounts blitz ship counts a row from.
-- One row per account per batch: published or not, a note, when. blitz ship takes each into the publication's ledger
-- as publish-edition:<batch>, with the account id, and only for that publication's batch.
-- Run once in the Supabase SQL editor. Safe to run again. Then the owner's account id, once (blitz design/ship.md,
-- "Publishing the edition: one-time setup"). The site signs people in anonymously, so the id belongs to one browser:
-- submit a review once in the browser you will publish from, take its user_id (the proofs row you just made, or
-- Authentication -> Users), and add it here and to `owner_ids` in each publication's fixes/ship-rule.json:
--   insert into edition_publishers (user_id) values ('<the owner''s user_id>') on conflict do nothing;
-- Repeat if that browser's site data is cleared. (A provider sign-in, one id everywhere, is a follow-up.)

create table if not exists edition_publishers (
  user_id uuid primary key references auth.users on delete cascade
);
alter table edition_publishers enable row level security;
drop policy if exists "own publisher row" on edition_publishers;
create policy "own publisher row" on edition_publishers for select to authenticated using (user_id = auth.uid());
grant select on edition_publishers to authenticated;  -- no insert grant: rows are added in the SQL editor only

create table if not exists edition_publish (
  batch text not null check (char_length(batch) <= 80),
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  who text not null default '' check (char_length(who) <= 40),   -- the name they gave on the proof page
  published boolean not null default true,                      -- false: the edition taken back
  note text not null default '' check (char_length(note) <= 500),
  at timestamptz not null default now(),
  primary key (batch, user_id)
);

alter table edition_publish enable row level security;
drop policy if exists "read edition_publish" on edition_publish;
create policy "read edition_publish" on edition_publish for select to anon, authenticated using (true);
-- Rows are added and changed only by a listed account, and never deleted (taking the edition back is a row with
-- published false): a delete before blitz ship takes the row in would make a publish vanish, and an account
-- removed from edition_publishers could still delete its old rows.
drop policy if exists "own edition_publish" on edition_publish;
drop policy if exists "publisher inserts" on edition_publish;
drop policy if exists "publisher updates" on edition_publish;
create policy "publisher inserts" on edition_publish for insert to authenticated
  with check (user_id = auth.uid() and exists (select 1 from edition_publishers p where p.user_id = auth.uid()));
create policy "publisher updates" on edition_publish for update to authenticated
  using (user_id = auth.uid() and exists (select 1 from edition_publishers p where p.user_id = auth.uid()))
  with check (user_id = auth.uid() and exists (select 1 from edition_publishers p where p.user_id = auth.uid()));
grant select on edition_publish to anon, authenticated;
revoke delete on edition_publish from anon, authenticated;
grant insert, update on edition_publish to authenticated;
