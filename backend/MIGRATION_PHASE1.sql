-- Phase 1 migration: run this in your EXISTING Supabase project's SQL Editor.
-- Adds organizations + api_keys, scopes all existing tables by organization_id,
-- and backfills your current seeded demo data into a "Demo Organization"
-- so nothing is lost or orphaned.

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

-- Fixed, known UUID so seed_data.py can target it directly
insert into organizations (id, name)
values ('00000000-0000-0000-0000-000000000001', 'Demo Organization');

alter table agent_events add column organization_id uuid references organizations(id);
alter table escalations add column organization_id uuid references organizations(id);
alter table agent_costs add column organization_id uuid references organizations(id);

update agent_events set organization_id = '00000000-0000-0000-0000-000000000001' where organization_id is null;
update escalations set organization_id = '00000000-0000-0000-0000-000000000001' where organization_id is null;
update agent_costs set organization_id = '00000000-0000-0000-0000-000000000001' where organization_id is null;

alter table agent_events alter column organization_id set not null;
alter table escalations alter column organization_id set not null;
alter table agent_costs alter column organization_id set not null;

-- The old unique constraint didn't account for org; replace it
alter table agent_costs drop constraint if exists agent_costs_agent_name_date_key;
alter table agent_costs add constraint agent_costs_org_agent_date_key unique(organization_id, agent_name, date);

grant select, insert, update, delete on organizations to service_role;
grant select, insert, update, delete on api_keys to service_role;
grant usage, select on sequence api_keys_id_seq to service_role;
