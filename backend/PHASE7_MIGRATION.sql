-- Phase 7 migration: idempotent ingest, daily spend caps, PII redaction tracking.
-- Run in Supabase's SQL Editor BEFORE merging the Phase 7 pull request.
-- Safe to run more than once. Purely additive: existing data is untouched.

alter table agent_policies
  add column if not exists daily_budget_usd numeric(10, 2)
    check (daily_budget_usd is null or daily_budget_usd > 0);

alter table agent_events
  add column if not exists pii_redacted boolean not null default false;

create table if not exists ingest_idempotency (
  id bigserial primary key,
  organization_id uuid not null references organizations(id) on delete cascade,
  idempotency_key text not null check (char_length(idempotency_key) between 1 and 255),
  event_id bigint references agent_events(id) on delete set null,
  response jsonb,
  claimed_at timestamptz not null default now(),
  unique (organization_id, idempotency_key)
);

alter table ingest_idempotency enable row level security;
grant select, insert, update, delete on ingest_idempotency to service_role;
grant usage, select on sequence ingest_idempotency_id_seq to service_role;
