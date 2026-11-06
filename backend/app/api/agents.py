
from fastapi import APIRouter, Depends

from app.audit import record_audit
from app.auth.dependencies import get_current_org
from app.config import settings
from app.db.supabase_client import get_supabase
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


@router.get("/{agent_name}/permission", response_model=AgentPermission)
async def agent_permission(agent_name: str, org: dict = Depends(get_current_org)):
    """Call this BEFORE an agent acts. If allowed is false, the agent should stop.
    Guardloop can only stop an agent that asks first."""
    return budget_status(get_supabase(), org["id"], agent_name)


@router.put("/{agent_name}/budget", response_model=AgentBudgetInfo)
async def set_agent_budget(
    agent_name: str, payload: AgentBudgetUpdate, org: dict = Depends(get_current_org)
):
    """Sets a daily spend cap in USD for one agent. Send null to remove the cap."""
    supabase = get_supabase()
    existing = (
        supabase.table("agent_policies").select("id")
        .eq("organization_id", org["id"])
        .eq("agent_name", agent_name)
        .execute().data
    )
    if existing:
        supabase.table("agent_policies").update({
            "daily_budget_usd": payload.daily_budget_usd,
            "updated_at": "now()",
        }).eq("id", existing[0]["id"]).execute()
    else:
        threshold, hard_gates = _org_default_values(supabase, org["id"])
        supabase.table("agent_policies").insert({
            "organization_id": org["id"],
            "agent_name": agent_name,
            "confidence_threshold": threshold,
            "hard_escalate_event_types": hard_gates,
            "daily_budget_usd": payload.daily_budget_usd,
        }).execute()

    record_audit(
        supabase, org, "budget.set", "agent", agent_name,
        {"daily_budget_usd": payload.daily_budget_usd}
    )

    return AgentBudgetInfo(
        agent_name=agent_name,
        daily_budget_usd=payload.daily_budget_usd
    )
