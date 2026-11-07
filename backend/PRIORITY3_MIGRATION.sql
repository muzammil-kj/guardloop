-- Priority 3 migration: judge calibration and agent versions.
-- Run in Supabase's SQL Editor BEFORE merging the Priority 3 pull request.
-- Safe to run more than once. Purely additive.

-- Where an escalation came from: the agent itself, the judge, or the budget pause.
alter table escalations
  add column if not exists source text not null default 'agent'
    check (source in ('agent', 'judge', 'budget'));

-- Tag each decision with the agent's version (prompt or model version, for example "prompt-v3").
alter table agent_events
  add column if not exists agent_version text
    check (agent_version is null or char_length(agent_version) between 1 and 64);

-- Backfill escalations created before this migration.
update escalations set source = 'judge'
  where source = 'agent' and reason like 'Judge disagreed%';
update escalations set source = 'budget'
  where source = 'agent' and reason like 'Agent %is paused:%';

create index if not exists escalations_source_status_idx
  on escalations (organization_id, source, status);
create index if not exists agent_events_version_idx
  on agent_events (organization_id, agent_name, agent_version);