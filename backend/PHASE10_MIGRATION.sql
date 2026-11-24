-- Phase 10 (Part A) migration: agent kill switch.
-- Run in Supabase's SQL Editor BEFORE merging. Safe to run more than once.
-- Purely additive.

create table if not exists agent_kill_switches (
  id bigserial primary key,
  organization_id uuid not null references organizations(id) on delete cascade,
  agent_name text not null check (char_length(agent_name) between 1 and 200),
  killed boolean not null default false,
  reason text check (reason is null or char_length(reason) <= 300),
  updated_by text,
  updated_at timestamptz not null default now(),
  unique (organization_id, agent_name)
);

alter table agent_kill_switches enable row level security;
grant select, insert, update, delete on agent_kill_switches to service_role;
grant usage, select on sequence agent_kill_switches_id_seq to service_role;