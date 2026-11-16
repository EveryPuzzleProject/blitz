-- The batch page's "Release to gxd" (since 2026-11-16; blitz design/ship.md, "The edition"; design/gxd-pull.md §6).
-- The owner presses it when a batch's shipped puzzles may be taken by gxd; pressing it again takes the release back.
-- One row per account per batch: released or not, a note, when. blitz ship (or blitz edition) takes each into the
-- publication's ledger as release:<batch> by "<who> (review site)", and only the owner's counts (the ship rule's
-- `owner` list in the publication's fixes/ship-rule.json): a helper's row does nothing. The page shows the button
-- only to a name on that list, and the import checks the name again.
-- Run once in the Supabase SQL editor. Safe to run again.

create table if not exists releases (
  batch text not null check (char_length(batch) <= 80),
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  who text not null default '' check (char_length(who) <= 40),   -- the name they gave on the proof page
  released boolean not null default true,                       -- false: the release taken back
  note text not null default '' check (char_length(note) <= 500),
  at timestamptz not null default now(),
  primary key (batch, user_id)
);

alter table releases enable row level security;
drop policy if exists "read releases" on releases;
create policy "read releases" on releases for select to anon, authenticated using (true);
drop policy if exists "own releases" on releases;
create policy "own releases" on releases for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
grant select on releases to anon, authenticated;
grant insert, update, delete on releases to authenticated;
