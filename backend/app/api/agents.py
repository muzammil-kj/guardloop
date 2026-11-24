from datetime import date

from fastapi import APIRouter, Depends

from app.audit import record_audit
from app.auth.actors import get_actor, require_role
from app.auth.dependencies import get_current_org
from app.config import settings
from app.db.supabase_client import get_supabase
from app.killswitch import is_killed
from app.models import AgentBudgetInfo, AgentBudgetUpdate, AgentPermission
from app.policies.budget import budget_status

router = APIRouter(prefix="/agents", tags=["agents"])


def _org_default_values(supabase, organization_id: str) -> tuple[float, list]:
    """A new per-agent row copies the organization's threshold and hard-gate list,
    so setting a budget never silently changes the agent's threshold."""
    rows = (
        supabase.table("agent_policies")
        .select("confidence_threshold,hard_escalate_event_types")
        .eq("organization_id", organization_id)
        .is_("agent_name", "null")
        .execute().data
    )
    if rows:
        return float(rows[0]["confidence_threshold"]), list(rows[0]["hard_escalate_event_types"] or [])
    return settings.default_confidence_threshold, []


@router.get("/overview")
async def agents_overview(actor: dict = Depends(get_actor)):
    """Every agent in this organization, with its budget, spend today and kill-switch state.
    Anyone signed in can read it. Changing budgets and switches needs the owner role."""
    supabase = get_supabase()
    org_id = actor["id"]

    events = (
        supabase.table("agent_events").select("agent_name")
        .eq("organization_id", org_id).order("created_at", desc=True).limit(1000)
        .execute().data
    )
    policies = (
        supabase.table("agent_policies").select("agent_name,daily_budget_usd")
        .eq("organization_id", org_id).execute().data
    )
    kill_rows = (
        supabase.table("agent_kill_switches").select("agent_name,killed,reason")
        .eq("organization_id", org_id).execute().data
    )
    cost_rows = (
        supabase.table("agent_costs").select("agent_name,total_cost_usd")
        .eq("organization_id", org_id).eq("date", str(date.today())).execute().data
    )

    org_cap = next((p.get("daily_budget_usd") for p in policies if p.get("agent_name") is None), None)
    agent_caps = {p["agent_name"]: p.get("daily_budget_usd") for p in policies if p.get("agent_name")}
    killed = {k["agent_name"]: (k.get("killed") is True, k.get("reason")) for k in kill_rows}
    spent: dict = {}
    for row in cost_rows:
        spent[row["agent_name"]] = spent.get(row["agent_name"], 0.0) + float(row["total_cost_usd"])

    names = {e["agent_name"] for e in events if e.get("agent_name")}
    names.update(agent_caps)
    names.update(killed)
    names.update(spent)

    overview = []
    for name in sorted(names):
        own_cap = agent_caps.get(name)
        if own_cap is not None:
            cap, source = float(own_cap), "agent"
        elif org_cap is not None:
            cap, source = float(org_cap), "organization"
        else:
            cap, source = None, None

        spent_today = round(spent.get(name, 0.0), 6)
        switched_off, reason = killed.get(name, (False, None))
        allowed = (not switched_off) and (cap is None or spent_today < cap)
        overview.append({
            "agent_name": name,
            "daily_budget_usd": cap,
            "budget_source": source,
            "spent_today_usd": spent_today,
            "remaining_usd": None if cap is None else round(max(cap - spent_today, 0.0), 6),
            "killed": switched_off,
            "kill_reason": reason,
            "allowed": allowed,
        })
    return overview


@router.get("/{agent_name}/permission", response_model=AgentPermission)
async def agent_permission(agent_name: str, org: dict = Depends(get_current_org)):
    """Call this BEFORE an agent acts. If allowed is false, the agent should stop.
    Guardloop can only stop an agent that asks first."""
    supabase = get_supabase()
    status = budget_status(supabase, org["id"], agent_name)
    killed, reason = is_killed(supabase, org["id"], agent_name)
    if killed:
        status = {**status, "allowed": False}
    return {**status, "killed": killed, "kill_reason": reason}


@router.put("/{agent_name}/budget", response_model=AgentBudgetInfo)
async def set_agent_budget(
    agent_name: str, payload: AgentBudgetUpdate, actor: dict = Depends(get_actor)
):
    """Sets a daily spend cap in USD for one agent. Send null to remove the cap. Owners only."""
    require_role(actor, "owner")
    supabase = get_supabase()
    existing = (
        supabase.table("agent_policies").select("id")
        .eq("organization_id", actor["id"])
        .eq("agent_name", agent_name)
        .execute().data
    )
    if existing:
        supabase.table("agent_policies").update({
            "daily_budget_usd": payload.daily_budget_usd,
            "updated_at": "now()",
        }).eq("id", existing[0]["id"]).execute()
    else:
        threshold, hard_gates = _org_default_values(supabase, actor["id"])
        supabase.table("agent_policies").insert({
            "organization_id": actor["id"],
            "agent_name": agent_name,
            "confidence_threshold": threshold,
            "hard_escalate_event_types": hard_gates,
            "daily_budget_usd": payload.daily_budget_usd,
        }).execute()

    record_audit(supabase, actor, "budget.set", "agent", agent_name,
                 {"daily_budget_usd": payload.daily_budget_usd})
    return AgentBudgetInfo(agent_name=agent_name, daily_budget_usd=payload.daily_budget_usd)