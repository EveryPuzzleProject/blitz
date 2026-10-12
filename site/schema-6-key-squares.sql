-- The key-squares page (/review/squares/, since 2026-10-12): one card per doubtful answer-key square
-- (the OCR was unsure of it, or the word check), and each helper's answer: keep the letter, or the
-- letter it should be. Narrow checks like this are the main way people help: seconds per card,
-- with the printed key beside it.
--
-- `blitz site-publish` writes the cards (service key; `blitz key-squares` makes them); helpers write
-- only their own answers; `blitz site-import` reads both back for xword-ocr import-reviews.
-- `page` leaves room for more pages of the same shape later (grid rulings, misprints) and for
-- cards that come from a "flag a mistake" link on the live puzzle (design/flag-a-mistake.md).
-- Run once in the Supabase SQL editor. Safe to run again.

create table if not exists flags (
  xdid text not null check (char_length(xdid) <= 60),
  page text not null default 'key-squares',
  sq text not null check (sq ~ '^r[0-9]+c[0-9]+$'),   -- the square, r3c12
  pub text not null,
  source text not null,             -- what raised it: ocr (the OCR was unsure), words (the word check), ocr+words
  card jsonb not null,              -- what the card shows: the letter, why, a suggestion, the answers and clues
                                    -- through the square, the key image and where to crop it, the scan's link
  open boolean not null default true,   -- false: settled (a person's answer imported) or the key changed
  batch text not null default '',
  added_at timestamptz not null default now(),
  primary key (xdid, page, sq)
);

create table if not exists flag_checks (
  xdid text not null,
  page text not null default 'key-squares',
  sq text not null,
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  who text not null default '' check (char_length(who) <= 40),   -- the name they gave on the page
  was text not null check (char_length(was) <= 12),              -- the letter on the card when they answered
  value text not null check (value ~ '^[A-Za-z0-9]{1,12}$'),     -- the letter it should be (= was: keep)
  at timestamptz not null default now(),
  primary key (xdid, page, sq, user_id),
  foreign key (xdid, page, sq) references flags   -- cards are closed, never deleted, so answers stay
);

alter table flags enable row level security;
drop policy if exists "read flags" on flags;
create policy "read flags" on flags for select to anon, authenticated using (true);
grant select on flags to anon, authenticated;

-- Anyone can read the answers (the page shows who already looked at a card); each helper writes
-- only their own, and only on an open card.
alter table flag_checks enable row level security;
drop policy if exists "read flag checks" on flag_checks;
create policy "read flag checks" on flag_checks for select to anon, authenticated using (true);
drop policy if exists "own flag checks" on flag_checks;
drop policy if exists "answer open cards" on flag_checks;
create policy "answer open cards" on flag_checks for insert to authenticated
  with check (user_id = auth.uid()
              and exists (select 1 from flags f where f.xdid = flag_checks.xdid and f.page = flag_checks.page
                          and f.sq = flag_checks.sq and f.open));
drop policy if exists "change answers on open cards" on flag_checks;
create policy "change answers on open cards" on flag_checks for update to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid()
              and exists (select 1 from flags f where f.xdid = flag_checks.xdid and f.page = flag_checks.page
                          and f.sq = flag_checks.sq and f.open));
drop policy if exists "take back own answers" on flag_checks;
create policy "take back own answers" on flag_checks for delete to authenticated using (user_id = auth.uid());
grant select on flag_checks to anon, authenticated;
grant insert, update, delete on flag_checks to authenticated;
