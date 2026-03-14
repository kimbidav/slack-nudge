-- Run this in your Supabase SQL editor to create the tables

create table if not exists users (
  id uuid primary key default gen_random_uuid(),
  email text unique not null,
  slack_user_id text not null,
  display_name text not null default '',
  schedule_hour int not null default 15,  -- UTC hour (15 = 8am PT)
  active boolean not null default true,
  created_at timestamptz not null default now()
);

create table if not exists nudge_runs (
  id uuid primary key default gen_random_uuid(),
  user_email text not null references users(email),
  ran_at timestamptz not null default now(),
  submissions_checked int not null default 0,
  nudges_needed int not null default 0,
  nudges_sent int not null default 0,
  details jsonb default '{}'::jsonb
);

-- Public read/write policies (internal tool, no auth needed)
alter table users enable row level security;
alter table nudge_runs enable row level security;

create policy "Public access" on users for all using (true) with check (true);
create policy "Public access" on nudge_runs for all using (true) with check (true);
