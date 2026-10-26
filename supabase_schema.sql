-- Iron Log — run this once in your Supabase project: SQL Editor → New query → Run.
-- One row per user holding the whole app state as JSON. Row Level Security
-- means each signed-in user can only ever read/write their own row, so the
-- public anon key is safe to use in the app.

create table if not exists public.workout_state (
  user_id    uuid primary key references auth.users (id) on delete cascade,
  state      jsonb not null,
  updated_at timestamptz not null default now()
);

alter table public.workout_state enable row level security;

drop policy if exists "own workout state" on public.workout_state;
create policy "own workout state" on public.workout_state
  for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);
