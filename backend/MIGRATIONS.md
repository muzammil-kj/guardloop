# Database migrations, in order

Run each file once in Supabase's SQL Editor, in this order. Every file is safe to run twice.

| Order | File | What it adds |
|---|---|---|
| 0 | `MIGRATION_PHASE1.sql` | Only for the original MVP database. Skip for new projects. |
| 1 | `app/db/schema.sql` | Base tables for new projects. Skip if the tables already exist. |
| 2 | `PHASE2_MIGRATION.sql` | Per-agent and organization policies |
| 3 | `PHASE4_MIGRATION.sql` | Alerts, realtime, row-level security on every table |
| 4 | `PHASE5_MIGRATION.sql` | Judge columns and judge settings |
| 5 | `PHASE7_MIGRATION.sql` | Idempotency keys, budgets, PII tracking |
| 6 | `PHASE8_MIGRATION.sql` | Memberships, assignments, deadlines, audit log |
| 7 | `PRIORITY3_MIGRATION.sql` | Escalation sources, agent versions |
| 8 | `PHASE10_MIGRATION.sql` | Agent kill switch |

Phase 6 (CI and Docker) and Phase 9 (rate limiting) have no database changes.