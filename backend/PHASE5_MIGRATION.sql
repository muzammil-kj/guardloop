-- Phase 5 migration: the LLM judge.
-- Run in your Supabase SQL Editor AFTER the Phase 4 migration.
-- Safe to run more than once.

-- ---------------------------------------------------------------------------
-- Judge results live on the event they review
-- ---------------------------------------------------------------------------
-- judge_status lifecycle:
--   none      never sampled (the default; also every existing row)
--   pending   sampled at ingest, waiting for a review pass
--   reviewing claimed by a running pass (guards against double review)
--   reviewed  judged; see judge_verdict
--   skipped   nothing to review (no input/output summary)
--   failed    the judge model errored 3 times; gave up

alter table agent_events
  add column if not exists judge_status text not null default 'none'
    check (judge_status in ('none', 'pending', 'reviewing', 'reviewed', 'skipped', 'failed')),
  add column if not exists judge_verdict text
    check (judge_verdict in ('agree', 'disagree', 'unsure')),
  add column if not exists judge_score float
    check (judge_score >= 0 and judge_score <= 1),
  add column if not exists judge_reason text,
  add column if not exists judge_reviewed_at timestamptz,
  add column if not exists judge_claimed_at timestamptz,
  add column if not exists judge_attempts int not null default 0;

-- Review passes only ever look for pending rows; keep that lookup cheap.
create index if not exists agent_events_judge_pending_idx
  on agent_events (created_at)
  where judge_status = 'pending';

-- ---------------------------------------------------------------------------
-- Per-organization judge settings (the judge is OFF until an org turns it on)
-- ---------------------------------------------------------------------------

create table if not exists judge_settings (
  organization_id uuid primary key references organizations(id) on delete cascade,
  enabled boolean not null default false,
  sample_rate float not null default 0.2
    check (sample_rate >= 0 and sample_rate <= 1),
  updated_at timestamptz not null default now()
);

-- Same hardening as every other table: RLS on, no policies, so the public
-- browser key can read nothing here. The backend's secret key bypasses RLS.
alter table judge_settings enable row level security;

grant select, insert, update, delete on judge_settings to service_role;
