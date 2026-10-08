-- Emoji reactions to a puzzle (the little ☺＋ button next to a helper's verdict). Run once in the
-- Supabase SQL editor, after schema.sql. Until it has been run the site simply hides reactions.
--
-- A helper's own rows are theirs alone (row-level security); what everyone may see is how many
-- people reacted with each emoji to each puzzle, never who.

create table if not exists reactions (
  xdid text not null references puzzles on delete cascade,
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  emoji text not null check (char_length(emoji) between 1 and 16),
  at timestamptz not null default now(),
  primary key (xdid, user_id, emoji)
);

alter table reactions enable row level security;
drop policy if exists "own reactions" on reactions;
create policy "own reactions" on reactions for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

create or replace view puzzle_reactions as
  select xdid, emoji, count(*)::int as n from reactions group by xdid, emoji;
grant select on puzzle_reactions to anon, authenticated;
