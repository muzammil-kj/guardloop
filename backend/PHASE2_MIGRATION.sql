-- Phase 2 migration: configurable per-agent, per-organization policies.
-- Run this in your Supabase SQL Editor (after Phase 1's migration).

create table agent_policies (
  id bigserial primary key,
  organization_id uuid not null references organizations(id) on delete cascade,
  agent_name text,  -- NULL means this row is the organization's default policy
  confidence_threshold float not null default 0.75,
  hard_escalate_event_types text[] not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Partial unique indexes: at most one policy per (org, agent), and at most
-- one default (agent_name null) row per org. A plain UNIQUE constraint
-- wouldn't work here since Postgres treats NULLs as distinct from each other.
create unique index agent_policies_org_agent_key
  on agent_policies (organization_id, agent_name)
  where agent_name is not null;

create unique index agent_policies_org_default_key
  on agent_policies (organization_id)
  where agent_name is null;

grant select, insert, update, delete on agent_policies to service_role;
grant usage, select on sequence agent_policies_id_seq to service_role;
