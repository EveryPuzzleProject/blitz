-- The batch page's "Publish the edition" (since 2026-11-16; blitz design/ship.md, "The edition";
-- design/publishing-editions.md). The last step of a publication's process: the owner publishes a batch's edition
-- (its shipped puzzles' editions, edition/<xdid>.xd, listed as published in the publication's shipped.tsv);
-- "Take the edition back" undoes that. This is not the review site's own "publish" (blitz site-publish,
-- ship --publish), which puts packets and records on this site.
-- One row per account per batch: published or not, a note, when. blitz ship (or blitz edition) takes each into the
-- publication's ledger as publish-edition:<batch> by "<who> (review site)", and only the owner's counts (the ship
-- rule's `owner` list in the publication's fixes/ship-rule.json): a helper's row does nothing. The page shows the
-- button only to a name on that list, and the import checks the name again.
-- Run once in the Supabase SQL editor. Safe to run again.

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
drop policy if exists "own edition_publish" on edition_publish;
create policy "own edition_publish" on edition_publish for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
grant select on edition_publish to anon, authenticated;
grant insert, update, delete on edition_publish to authenticated;
