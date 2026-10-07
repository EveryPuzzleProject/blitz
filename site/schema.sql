-- The public review site's database (Supabase). Run once in the project's SQL editor.
--
-- Helpers sign in (email link) and check puzzles an agent has reviewed: accept or reject each
-- change, a verdict per puzzle, and reports of problems the review missed. Everything a helper
-- writes is theirs alone (row-level security); what everyone may see is the list of puzzles, how
-- many people have checked each, and a leaderboard of those who opted in.
--
-- `blitz site-publish` adds puzzles (with the service key); `blitz site-import` reads everything
-- back for import upstream (xword-ocr import-reviews --decisions).

create table if not exists puzzles (
  xdid text primary key,
  pub text not null,
  batch text not null default '',
  title text not null default '',
  base_url text not null,                      -- where the packet's files are (R2)
  files jsonb not null default '{}',           -- which files it has: {"page.jpg": true, "_src/page.jpg": true, ...}
  review_status text not null default 'ready', -- what the agent review concluded: ready, needs a person, escalated
  open boolean not null default true,          -- false: taken off the site (e.g. imported)
  added_at timestamptz not null default now()
);

create table if not exists profiles (
  user_id uuid primary key default auth.uid() references auth.users on delete cascade,
  display_name text not null default '' check (char_length(display_name) <= 40),
  on_leaderboard boolean not null default false,
  created_at timestamptz not null default now()
);

create table if not exists decisions (           -- accept / reject one change of the agent's review
  xdid text not null references puzzles on delete cascade,
  item text not null check (char_length(item) <= 40),        -- as the importer names it: clue:A14, cell:r3c5, sic:D1
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  decision text not null check (decision in ('accept', 'reject')),
  note text not null default '' check (char_length(note) <= 500),
  at timestamptz not null default now(),
  primary key (xdid, item, user_id)
);

create table if not exists verdicts (            -- the helper's verdict on the whole puzzle
  xdid text not null references puzzles on delete cascade,
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  verdict text not null check (verdict in ('looks-right', 'needs-work')),
  note text not null default '' check (char_length(note) <= 500),
  at timestamptz not null default now(),
  primary key (xdid, user_id)
);

create table if not exists reports (             -- a problem the review missed, pointed at on the scan
  xdid text not null references puzzles on delete cascade,
  target text not null check (char_length(target) <= 40),    -- clue:A14
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  text text not null default '' check (char_length(text) <= 500),
  at timestamptz not null default now(),
  primary key (xdid, target, user_id)
);

alter table puzzles enable row level security;
alter table profiles enable row level security;
alter table decisions enable row level security;
alter table verdicts enable row level security;
alter table reports enable row level security;

-- Anyone may see the open puzzles; only the service key (publish/import) changes them.
drop policy if exists "open puzzles" on puzzles;
create policy "open puzzles" on puzzles for select using (open);

-- A helper sees and changes only their own rows.
drop policy if exists "own profile" on profiles;
create policy "own profile" on profiles for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
drop policy if exists "own decisions" on decisions;
create policy "own decisions" on decisions for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
drop policy if exists "own verdicts" on verdicts;
create policy "own verdicts" on verdicts for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
drop policy if exists "own reports" on reports;
create policy "own reports" on reports for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

-- What everyone may see of other people's work: counts, never who decided what.
-- (Views run with their owner's rights, so they can count rows the viewer can't read.)
create or replace view puzzle_progress as
  select xdid, count(*)::int as eyes from verdicts group by xdid;
create or replace view leaderboard as
  select p.display_name, count(distinct v.xdid)::int as puzzles, max(v.at) as latest
  from verdicts v join profiles p on p.user_id = v.user_id
  where p.on_leaderboard and p.display_name <> ''
  group by p.user_id, p.display_name
  order by puzzles desc;
grant select on puzzle_progress, leaderboard to anon, authenticated;
