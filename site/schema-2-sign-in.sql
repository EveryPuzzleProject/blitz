-- Sign in with Google or GitHub, keeping a guest's work. Run once in the SQL editor, after schema.sql.
--
-- A guest (anonymous sign-in) who signs in gets a new identity, or an existing account on another
-- device. Before leaving for Google or GitHub, the page asks for a claim ticket as the guest
-- (start_guest_claim); back, signed in, it hands the ticket in (finish_guest_claim) and the guest's
-- decisions, verdicts, reports and name move to the account. The account's own rows win where both
-- decided the same thing. Tickets are random, kept only in that browser, and expire after a day.

create table if not exists guest_claims (
  token text primary key,
  guest_id uuid not null references auth.users on delete cascade,
  created_at timestamptz not null default now()
);
alter table guest_claims enable row level security;  -- no policies: only the functions below touch it

create or replace function start_guest_claim() returns text
language plpgsql security definer set search_path = public as $$
declare
  t text := replace(gen_random_uuid()::text || gen_random_uuid()::text, '-', '');
begin
  if auth.uid() is null or not coalesce((auth.jwt() ->> 'is_anonymous')::boolean, false) then
    raise exception 'only a guest can start a claim';
  end if;
  delete from guest_claims where guest_id = auth.uid() or created_at < now() - interval '1 day';
  insert into guest_claims (token, guest_id) values (t, auth.uid());
  return t;
end $$;

create or replace function finish_guest_claim(t text) returns int
language plpgsql security definer set search_path = public as $$
declare
  me uuid := auth.uid();
  g uuid;
  n int := 0;
  c int;
begin
  if me is null then
    raise exception 'sign in first';
  end if;
  select guest_id into g from guest_claims where token = t and created_at > now() - interval '1 day';
  delete from guest_claims where token = t;
  if g is null or g = me then
    return 0;
  end if;
  update decisions d set user_id = me where d.user_id = g
    and not exists (select 1 from decisions e where e.user_id = me and e.xdid = d.xdid and e.item = d.item);
  get diagnostics c = row_count; n := n + c;
  update verdicts v set user_id = me where v.user_id = g
    and not exists (select 1 from verdicts w where w.user_id = me and w.xdid = v.xdid);
  get diagnostics c = row_count; n := n + c;
  update reports r set user_id = me where r.user_id = g
    and not exists (select 1 from reports s where s.user_id = me and s.xdid = r.xdid and s.target = r.target);
  get diagnostics c = row_count; n := n + c;
  insert into profiles (user_id, display_name, on_leaderboard)
    select me, display_name, on_leaderboard from profiles where user_id = g
    on conflict (user_id) do nothing;
  delete from decisions where user_id = g;
  delete from verdicts where user_id = g;
  delete from reports where user_id = g;
  delete from profiles where user_id = g;
  return n;
end $$;

revoke all on function start_guest_claim() from public, anon;
revoke all on function finish_guest_claim(text) from public, anon;
grant execute on function start_guest_claim() to authenticated;
grant execute on function finish_guest_claim(text) to authenticated;
