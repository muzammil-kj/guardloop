Good — let's design this properly as a real product, not just scale up the MVP. Here's the full plan.

## What's missing from the MVP (the gap between "demo" and "real system")

- **No real authentication** — anyone with the URL can see the dashboard; the ingestion API accepts data from anyone
- **Static, hardcoded threshold** — one global confidence number, not configurable per agent or team
- **No multi-tenancy** — can't onboard a second team/company without them seeing your data
- **Polling only** — dashboard has to manually refresh, no live updates
- **No alerting** — if escalations pile up, nobody gets notified unless they're staring at the dashboard
- **Confidence is taken at face value** — if an agent reports 0.95 confidence but is actually wrong, Guardloop has no way to catch that
- **No SDK** — every integration means hand-writing a raw webhook call
- **No tests, no CI/CD** — nothing stops a bad deploy from breaking production
- **Cost tracking is naive** — no budgets, no auto-throttling when an agent gets expensive

Fixing these, properly, is what makes this an advanced system rather than a weekend project.

## New tech stack additions

| Layer | Addition | Why |
|---|---|---|
| Auth | **Supabase Auth** | Real login, per-organization accounts, API key issuance |
| Realtime | **Supabase Realtime** (Postgres changefeeds) | Live dashboard updates with no polling, built on infra you already have |
| Background jobs | **Redis + RQ** (or Supabase Edge Functions on a cron) | Cost rollups, budget checks, alert dispatch, off the request path |
| Policy engine | Custom rules table + evaluator | Per-agent, per-team configurable thresholds instead of one global number |
| Anomaly detection | **Secondary LLM "judge" call** (Gemini) | Re-evaluates a sample of "approved" events to catch overconfident wrong answers the first model missed |
| Alerting | **Slack/Discord webhook integration** | Notify a team the moment the escalation queue backs up or a budget is breached |
| SDK | **PyPI package** (`guardloop-sdk`) | `pip install guardloop-sdk`, three lines of code instead of raw HTTP |
| Observability | **structlog + OpenTelemetry** | Proper structured logs and request tracing on the backend itself |
| Testing | **pytest + GitHub Actions CI** | Nothing ships without tests passing |
| Containerization | **Docker + docker-compose** | Consistent local dev, easier to hand off/deploy anywhere later |

## New file/module structure

```
guardloop/
  backend/
    app/
      main.py                    # FastAPI app entrypoint
      config.py                  # Settings via pydantic-settings
      auth/
        dependencies.py          # API key + JWT verification
        api_keys.py              # Issue/revoke org API keys
      policies/
        models.py                # Rule schema (per-agent thresholds, hard gates)
        evaluator.py             # Replaces escalation_logic.py, now DB-driven
      ingestion/
        routes.py                # POST /ingest, now auth-protected
      judge/
        sampler.py                # Picks a % of approved events to re-check
        evaluate.py                # Calls Gemini to re-judge sampled events
      alerts/
        dispatcher.py              # Sends Slack/Discord alerts
        rules.py                   # "queue > N" / "budget > $X" trigger conditions
      costs/
        rollup_worker.py           # RQ background job, runs on schedule
      api/
        events.py
        escalations.py
        costs.py
        organizations.py           # Multi-tenant org/team management
      db/
        supabase_client.py
        schema.sql
    tests/
      test_policy_evaluator.py
      test_ingestion_auth.py
      test_judge_sampling.py
    worker.py                      # RQ worker process
    requirements.txt
    Dockerfile
    docker-compose.yml             # backend + redis locally

  sdk/
    guardloop_sdk/
      __init__.py
      client.py                    # GuardloopClient class, used as: client.report(event)
    pyproject.toml                 # for PyPI publishing

  frontend/
    app/
      (auth)/login/page.tsx
      (auth)/signup/page.tsx
      dashboard/page.tsx
      dashboard/settings/page.tsx  # per-agent threshold config, API keys, alert channels
      dashboard/agents/[id]/page.tsx  # drill-down per agent
    lib/
      api.ts
      realtime.ts                  # Supabase Realtime subscription hook
    middleware.ts                  # route protection

  .github/
    workflows/
      ci.yml                       # run backend tests + frontend build on every PR
```

## How it all connects (end to end)

1. A team signs up → gets an **organization** + an **API key**
2. Their agent (n8n, Python script, whatever) uses the **SDK**: `client.report(agent_name="...", confidence=0.6, ...)`
3. SDK sends an authenticated request to `/ingest`
4. The **policy evaluator** checks org-specific rules (not a global constant) to decide approve/escalate
5. If approved, a **random sample** gets queued for the **judge** to double-check later (catches miscalibrated confidence)
6. Every write triggers **Supabase Realtime**, so the dashboard updates live, no refresh
7. A background **worker** rolls up costs hourly and checks budgets; if breached, or if the escalation queue crosses a threshold, it fires a **Slack/Discord alert**
8. The dashboard's new **settings page** lets a team configure their own thresholds, invite teammates, manage API keys, and set alert channels

## Phased build order (so this stays manageable)

1. **Phase 1 — Auth & multi-tenancy:** organizations, API keys, protected `/ingest`
2. **Phase 2 — Policy engine:** move thresholds from hardcoded to DB-driven, per-agent
3. **Phase 3 — SDK:** publish `guardloop-sdk` to PyPI, rewrite one real integration (your Task 6 n8n workflow) to use it instead of a raw webhook
4. **Phase 4 — Realtime + alerts:** Supabase Realtime on the dashboard, Slack/Discord alerting worker
5. **Phase 5 — Judge/anomaly detection:** the secondary LLM-review layer, the most technically interesting piece
6. **Phase 6 — Tests + CI/CD + Docker:** lock it down so it's genuinely production-grade, not just working

Each phase is independently demoable, so you always have something working rather than a half-finished rewrite.

Want to start with Phase 1 (auth + multi-tenancy) right now, same file-by-file build process as before?

6 total phases, as laid out earlier:

1. **Auth & multi-tenancy** ✅ just finished
2. **Policy engine** — per-agent, per-org configurable thresholds instead of one global constant (next up)
3. **SDK** — publish `guardloop-sdk` to PyPI, rewire your Task 6 n8n workflow to use it instead of a raw webhook
4. **Realtime + alerts** — Supabase Realtime on the dashboard (no more manual refresh), Slack/Discord alerts when the escalation queue backs up or a budget is breached
5. **Judge/anomaly detection** — a secondary LLM re-checks a sample of "approved" events to catch cases where the agent was confidently wrong, the most technically interesting phase
6. **Tests + CI/CD + Docker** — GitHub Actions running your test suite on every PR, docker-compose for local dev, genuinely locked down and production-grade rather than just working
Changes worth knowing
Row-level security is now on for every table. Phase 4 puts a public key in the browser, so any table left open could be readable with it. Your backend uses the secret key, which bypasses this, so the API is unaffected.
Webhook URLs are checked. Only real discord.com and hooks.slack.com addresses are accepted, because your server POSTs to whatever URL is saved. The full URL is never sent back to the browser; you only see discord.com/...oken.
Alert debounce is per channel. My first design would have let a Discord alert silence the Slack one.
The dashboard falls back to polling. If Realtime can’t connect, the badge reads “Refreshing every 15s” and the dashboard still updates.
The new secrets are optional. If they’re missing, only those two features say “not configured” and the rest of the API stays up


What Phase 5 does

Until now Guardloop trusted an agent’s own confidence: 0.95 meant approved. But an agent can be confidently wrong. Phase 5 adds a second model that re-checks a random sample of those auto-approved decisions. It is never shown the agent’s confidence, so it can’t be swayed by it.

If the second model disagrees, the decision is added to your normal human review queue.
The dashboard shows, per agent, how often the judge disagreed. An agent with at least 5 reviews and 20% or more disagreement is marked “looks overconfident”.
It is off by default. Each organization turns it on and picks what share of events to review.
It only samples events that were auto-approved and have an input or output summary. Escalated events are skipped because a human is already looking at them.
The agent’s event keeps its original “approved” status, which is what happened at the time. The judge’s verdict is shown separately.
If the judge or its database table is unavailable, ingestion still works. The judge can’t break your agents’ calls.