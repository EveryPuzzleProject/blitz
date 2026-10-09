-- The proof page (/review/ since 2026-10-09): one row per helper per puzzle, holding their whole
-- review: the verdict on each part, their edits, their comments, a note and the decision.
-- Anyone can read submitted proofs, so the next reviewer sees earlier helpers' edits and comments
-- on their own screen; each helper writes only their own row.
-- Run once in the Supabase SQL editor. Safe to run again.

create table if not exists proofs (
  xdid text not null references puzzles on delete cascade,
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  who text not null default '' check (char_length(who) <= 40),        -- the name they gave on the page
  decision text not null check (decision in ('ready', 'notready')),
  review jsonb not null default '{}',   -- {edits: {key: value}, comments: [{key, text, why}], status: {part: {v, note}}, note}
  at timestamptz not null default now(),
  primary key (xdid, user_id)
);

alter table proofs enable row level security;
drop policy if exists "read proofs" on proofs;
create policy "read proofs" on proofs for select to anon, authenticated using (true);
drop policy if exists "own proofs" on proofs;
create policy "own proofs" on proofs for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
grant select on proofs to anon, authenticated;
grant insert, update, delete on proofs to authenticated;
