-- Guardloop full schema, Phase 1 (organizations + API keys + multi-tenancy)
-- Use this ONLY for a brand-new Supabase project.
-- If you already have a live Guardloop database from the MVP, run
-- MIGRATION_PHASE1.sql instead — do not run this on top of existing data.

create table organizations (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  created_at timestamptz not null default now()
);

create table api_keys (
  id bigserial primary key,
  organization_id uuid not null references organizations(id) on delete cascade,
  key_hash text not null unique,
  key_prefix text not null,
  label text,
  revoked boolean not null default false,
  last_used_at timestamptz,
  created_at timestamptz not null default now()
);

create table agent_events (
  id bigserial primary key,
  organization_id uuid not null references organizations(id) on delete cascade,
  agent_name text not null,
  event_type text not null,
  input_summary text,
  output_summary text,
  confidence float,
  status text not null default 'approved',
  cost_usd numeric(10, 6) default 0,
  created_at timestamptz not null default now()
);

create table escalations (
  id bigserial primary key,
  organization_id uuid not null references organizations(id) on delete cascade,
  event_id bigint references agent_events(id) on delete cascade,
  reason text not null,
  status text not null default 'pending',
  resolved_by text,
  resolution_note text,
  resolved_at timestamptz,
  created_at timestamptz not null default now()
);

create table agent_costs (
  id bigserial primary key,
  organization_id uuid not null references organizations(id) on delete cascade,
  agent_name text not null,
  date date not null default current_date,
  total_cost_usd numeric(10, 6) not null default 0,
  event_count int not null default 0,
  unique(organization_id, agent_name, date)
);

grant select, insert, update, delete on organizations to service_role;
grant select, insert, update, delete on api_keys to service_role;
grant select, insert, update, delete on agent_events to service_role;
grant select, insert, update, delete on escalations to service_role;
grant select, insert, update, delete on agent_costs to service_role;

grant usage, select on sequence api_keys_id_seq to service_role;
grant usage, select on sequence agent_events_id_seq to service_role;
grant usage, select on sequence escalations_id_seq to service_role;
grant usage, select on sequence agent_costs_id_seq to service_role;