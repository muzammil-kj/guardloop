from datetime import date


def _today() -> str:
    return str(date.today())


def spent_today(supabase, organization_id: str, agent_name: str) -> float:
    rows = (
        supabase.table("agent_costs").select("total_cost_usd")
        .eq("organization_id", organization_id)
        .eq("agent_name", agent_name)
        .eq("date", _today())
        .execute().data
    )
    return round(sum(float(row["total_cost_usd"]) for row in rows), 6)


def effective_daily_budget(supabase, organization_id: str, agent_name: str) -> float | None:
    """The agent's own cap, else the organization's default cap, else None (no cap)."""
    agent_rows = (
        supabase.table("agent_policies").select("daily_budget_usd")
        .eq("organization_id", organization_id)
        .eq("agent_name", agent_name)
        .execute().data
    )
    if agent_rows and agent_rows[0].get("daily_budget_usd") is not None:
        return float(agent_rows[0]["daily_budget_usd"])

    org_rows = (
        supabase.table("agent_policies").select("daily_budget_usd")
        .eq("organization_id", organization_id)
        .is_("agent_name", "null")
        .execute().data
    )
    if org_rows and org_rows[0].get("daily_budget_usd") is not None:
        return float(org_rows[0]["daily_budget_usd"])
    return None


def budget_status(supabase, organization_id: str, agent_name: str) -> dict:
    cap = effective_daily_budget(supabase, organization_id, agent_name)
    spent = spent_today(supabase, organization_id, agent_name)
    allowed = cap is None or spent < cap
    remaining = None if cap is None else round(max(cap - spent, 0.0), 6)
    return {
        "agent_name": agent_name,
        "allowed": allowed,
        "daily_budget_usd": cap,
        "spent_today_usd": spent,
        "remaining_usd": remaining,
    }
