from fastapi import APIRouter, Depends, HTTPException

from app.db.supabase_client import get_supabase
from app.auth.dependencies import get_current_org
from app.models import PolicyUpdate, PolicyInfo

router = APIRouter(prefix="/policies", tags=["policies"])


@router.get("", response_model=list[PolicyInfo])
async def list_policies(org: dict = Depends(get_current_org)):
    """Returns every configured policy for this org, including the default
    (agent_name: null) row if one has been set."""
    supabase = get_supabase()
    result = (
        supabase.table("agent_policies")
        .select("*")
        .eq("organization_id", org["id"])
        .execute()
    )
    return result.data


@router.put("/default", response_model=PolicyInfo)
async def set_default_policy(payload: PolicyUpdate, org: dict = Depends(get_current_org)):
    """Sets or updates this organization's default policy, applied to any
    agent that doesn't have its own specific override."""
    supabase = get_supabase()
    existing = (
        supabase.table("agent_policies")
        .select("id")
        .eq("organization_id", org["id"])
        .is_("agent_name", "null")
        .execute()
    )

    row = {
        "organization_id": org["id"],
        "agent_name": None,
        "confidence_threshold": payload.confidence_threshold,
        "hard_escalate_event_types": payload.hard_escalate_event_types,
        "updated_at": "now()",
    }

    if existing.data:
        result = (
            supabase.table("agent_policies")
            .update(row)
            .eq("id", existing.data[0]["id"])
            .execute()
        )
    else:
        result = supabase.table("agent_policies").insert(row).execute()

    return result.data[0]


@router.put("/{agent_name}", response_model=PolicyInfo)
async def set_agent_policy(
    agent_name: str, payload: PolicyUpdate, org: dict = Depends(get_current_org)
):
    """Sets or updates a policy specific to one agent, overriding the org
    default for that agent only."""
    supabase = get_supabase()
    existing = (
        supabase.table("agent_policies")
        .select("id")
        .eq("organization_id", org["id"])
        .eq("agent_name", agent_name)
        .execute()
    )

    row = {
        "organization_id": org["id"],
        "agent_name": agent_name,
        "confidence_threshold": payload.confidence_threshold,
        "hard_escalate_event_types": payload.hard_escalate_event_types,
        "updated_at": "now()",
    }

    if existing.data:
        result = (
            supabase.table("agent_policies")
            .update(row)
            .eq("id", existing.data[0]["id"])
            .execute()
        )
    else:
        result = supabase.table("agent_policies").insert(row).execute()

    return result.data[0]


@router.delete("/{agent_name}")
async def delete_agent_policy(agent_name: str, org: dict = Depends(get_current_org)):
    """Removes a per-agent override, causing that agent to fall back to the
    org default (or the global default, if no org default is set either)."""
    supabase = get_supabase()
    result = (
        supabase.table("agent_policies")
        .delete()
        .eq("organization_id", org["id"])
        .eq("agent_name", agent_name)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="No policy found for this agent.")
    return {"status": "deleted"}