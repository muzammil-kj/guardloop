-- Phase 8 migration: reviewer accounts, escalation owners and deadlines, audit log.
-- Run in Supabase's SQL Editor BEFORE merging the Phase 8 pull request.
-- Safe to run more than once. Purely additive.

alter table organizations
  add column if not exists sla_hours int not null default 4 check (sla_hours between 1 and 720);

alter table escalations
  add column if not exists assigned_to text,
  add column if not exists due_at timestamptz,
  add column if not exists sla_alerted_at timestamptz;

-- Every new escalation gets a deadline automatically: created_at + the organization's SLA.
create or replace function set_escalation_due_at() returns trigger
language plpgsql as $$
begin
  if new.due_at is null then
    select new.created_at + make_interval(hours => o.sla_hours)
      into new.due_at
      from organizations o
      where o.id = new.organization_id;
  end if;
  return new;
end $$;

drop trigger if exists escalations_set_due_at on escalations;
create trigger escalations_set_due_at
  before insert on escalations
  for each row execute function set_escalation_due_at();

-- Give existing pending escalations a deadline too.
update escalations e
  set due_at = e.created_at + make_interval(hours => o.sla_hours)
  from organizations o
  where o.id = e.organization_id and e.due_at is null;

create index if not exists escalations_overdue_idx
  on escalations (status, due_at)
  where sla_alerted_at is null;

create table if not exists memberships (
  id bigserial primary key,
  organization_id uuid not null references organizations(id) on delete cascade,
  email text not null,
  user_id uuid,
  display_name text,
  role text not null check (role in ('owner', 'reviewer', 'viewer')),
  created_at timestamptz not null default now(),
  unique (organization_id, email)
);

create table if not exists audit_log (
  id bigserial primary key,
  organization_id uuid not null references organizations(id) on delete cascade,
  actor_name text not null,
  actor_type text not null check (actor_type in ('user', 'api_key')),
  action text not null,
  target_type text,
  target_id text,
  detail jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists audit_log_org_time_idx on audit_log (organization_id, created_at desc);

alter table memberships enable row level security;
alter table audit_log enable row level security;

grant select, insert, update, delete on memberships to service_role;
grant select, insert, update, delete on audit_log to service_role;
grant usage, select on sequence memberships_id_seq to service_role;
grant usage, select on sequence audit_log_id_seq to service_role;
