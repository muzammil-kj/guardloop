"""
Kill switch: an administrator can switch one agent off instantly.

While switched off, /ingest refuses the agent with 403, and /permission reports
it as not allowed. Switching it back on takes effect immediately.

Failure behaviour: if the lookup fails (for example, the migration hasn't been
run yet), the agent is treated as active and an error is logged. Otherwise a
missing table would stop every agent. A database outage stops ingest anyway.
"""
import logging

logger = logging.getLogger("guardloop.killswitch")


def is_killed(supabase, organization_id: str, agent_name: str) -> tuple[bool, str | None]:
    try:
        rows = (
            supabase.table("agent_kill_switches")
            .select("killed,reason")
            .eq("organization_id", organization_id)
            .eq("agent_name", agent_name)
            .execute().data
        )
    except Exception as exc:
        logger.error("Kill switch lookup failed; treating '%s' as active: %s",
                     agent_name, type(exc).__name__)
        return False, None
    if not rows:
        return False, None
    row = rows[0]
    if row.get("killed") is True:
        return True, row.get("reason")
    return False, None