-- Phase 4 migration: alert channels, alert debounce history, Realtime
-- support, and row-level-security hardening.
-- Run in your Supabase SQL Editor after the Phase 1 and Phase 2 migrations.
-- Safe to run more than once.

-- ---------------------------------------------------------------------------
-- Alerting tables
-- ---------------------------------------------------------------------------

create table if not exists alert_channels (
  id bigserial primary key,
  organization_id uuid not null references organizations(id) on delete cascade,
  channel_type text not null check (channel_type in ('discord', 'slack')),
  webhook_url text not null,
  queue_depth_threshold int not null default 10 check (queue_depth_threshold >= 1),
  daily_budget_usd numeric(10, 2) not null default 5.00 check (daily_budget_usd > 0),
  enabled boolean not null default true,
  created_at timestamptz not null default now()
);

create index if not exists alert_channels_org_idx on alert_channels (organization_id);

-- Debounce state is tracked PER CHANNEL, so a Discord alert never silences
-- the Slack one (or another team's channel) for the same rule.
create table if not exists alert_history (
  id bigserial primary key,
  channel_id bigint not null references alert_channels(id) on delete cascade,
  rule_type text not null check (rule_type in ('queue_depth', 'daily_budget')),
  last_triggered_at timestamptz not null default now(),
  unique (channel_id, rule_type)
);

grant select, insert, update, delete on alert_channels to service_role;
grant select, insert, update, delete on alert_history to service_role;
grant usage, select on sequence alert_channels_id_seq to service_role;
grant usage, select on sequence alert_history_id_seq to service_role;

-- ---------------------------------------------------------------------------
-- Row-level security hardening
-- ---------------------------------------------------------------------------
-- Phase 4 ships a PUBLIC Supabase key to the browser (for Realtime). Any table
-- without RLS could be readable with that key, so we enable RLS on EVERY
-- Guardloop table. With no policy, anon/authenticated are denied everything.
-- Your backend uses the secret/service_role key, which bypasses RLS, so the
-- API is unaffected.

alter table organizations enable row level security;
alter table api_keys enable row level security;
alter table agent_costs enable row level security;
alter table agent_policies enable row level security;
alter table alert_channels enable row level security;
alter table alert_history enable row level security;
alter table agent_events enable row level security;
alter table escalations enable row level security;

-- ---------------------------------------------------------------------------
-- Realtime: the ONLY thing the browser may read directly
-- ---------------------------------------------------------------------------
-- The backend mints a short-lived JWT carrying an organization_id claim after
-- normal API-key auth. These policies let a connection holding that token see
-- only its own organization's rows on these two tables.

grant select on agent_events to authenticated;
grant select on escalations to authenticated;

drop policy if exists "org reads own events via realtime" on agent_events;
create policy "org reads own events via realtime"
  on agent_events for select
  to authenticated
  using (organization_id::text = (select auth.jwt() ->> 'organization_id'));

drop policy if exists "org reads own escalations via realtime" on escalations;
create policy "org reads own escalations via realtime"
  on escalations for select
  to authenticated
  using (organization_id::text = (select auth.jwt() ->> 'organization_id'));

-- Tell Supabase to broadcast changes on these tables (idempotent).
do $$
begin
  if not exists (
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'agent_events'
  ) then
    alter publication supabase_realtime add table public.agent_events;
  end if;

  if not exists (
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'escalations'
  ) then
    alter publication supabase_realtime add table public.escalations;
  end if;
end $$;
