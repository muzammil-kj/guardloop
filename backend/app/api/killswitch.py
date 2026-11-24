from fastapi import APIRouter, Depends

from app.audit import record_audit
from app.auth.actors import get_actor, require_role
from app.db.supabase_client import get_supabase
from app.models import KillSwitchInfo, KillSwitchUpdate

router = APIRouter(prefix="/agents", tags=["kill-switch"])


@router.get("/kill-switches", response_model=list[KillSwitchInfo])
async def list_switched_off_agents(actor: dict = Depends(get_actor)):
    rows = (
        get_supabase().table("agent_kill_switches")
        .select("agent_name,killed,reason")
        .eq("organization_id", actor["id"])
        .eq("killed", True)
        .execute().data
    )
    return [KillSwitchInfo(agent_name=row["agent_name"], killed=True, reason=row.get("reason")) for row in rows]


@router.put("/{agent_name}/kill-switch", response_model=KillSwitchInfo)
async def set_kill_switch(agent_name: str, payload: KillSwitchUpdate, actor: dict = Depends(get_actor)):
    """Switches an agent off (killed: true) or back on (killed: false). Owners only."""
    require_role(actor, "owner")
    supabase = get_supabase()
    reason = payload.reason.strip() if (payload.killed and payload.reason) else None

    supabase.table("agent_kill_switches").upsert({
        "organization_id": actor["id"],
        "agent_name": agent_name,
        "killed": payload.killed,
        "reason": reason,
        "updated_by": str(actor.get("actor_name") or "API key")[:200],
        "updated_at": "now()",
    }, on_conflict="organization_id,agent_name").execute()

    record_audit(
        supabase, actor,
        "agent.kill_switch_on" if payload.killed else "agent.kill_switch_off",
        "agent", agent_name, {"reason": reason},
    )
    return KillSwitchInfo(agent_name=agent_name, killed=payload.killed, reason=reason)