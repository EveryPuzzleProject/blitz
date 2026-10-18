-- Puzzles dropped as not crosswords (since 2026-10-18). A drop only marks a puzzle: site-publish puts
-- it on the site with puzzles.dropped set (who dropped it and why, from the publication's ledger,
-- drop:<pid>), the review page leaves it out of its lists, and Browse shows it under "Dropped" with a
-- Restore button. A restore is a helper's decision, one row per helper per puzzle in `restores`: the
-- puzzle is open again on the site at once, and site-import carries it to the ledger (a person's
-- keep on drop:<pid>), so the next proof-packets puts it back in the batch.
-- Run once in the Supabase SQL editor. Safe to run again.

alter table puzzles add column if not exists dropped jsonb;  -- {"by": "triage", "note": "triage: the text step's request: ..."}

create table if not exists restores (
  xdid text not null references puzzles on delete cascade,
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  who text not null default '' check (char_length(who) <= 40),   -- the name they gave on the page
  note text not null default '' check (char_length(note) <= 500),
  at timestamptz not null default now(),
  primary key (xdid, user_id)
);

alter table restores enable row level security;
drop policy if exists "read restores" on restores;
create policy "read restores" on restores for select to anon, authenticated using (true);
drop policy if exists "own restores" on restores;
create policy "own restores" on restores for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
grant select on restores to anon, authenticated;
grant insert, update, delete on restores to authenticated;
