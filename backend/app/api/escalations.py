from fastapi import APIRouter, Depends, HTTPException

from app.db.supabase_client import get_supabase
from app.auth.dependencies import get_current_org
from app.models import ResolveEscalation

router = APIRouter(tags=["escalations"])


@router.get("/escalations")
async def list_escalations(status: str = "pending", org: dict = Depends(get_current_org)):
    supabase = get_supabase()
    result = (
        supabase.table("escalations")
        .select("*, agent_events(*)")
        .eq("organization_id", org["id"])
        .eq("status", status)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@router.patch("/escalations/{escalation_id}/resolve")
async def resolve_escalation(
    escalation_id: int,
    resolution: ResolveEscalation,
    org: dict = Depends(get_current_org),
):
    supabase = get_supabase()
    result = (
        supabase.table("escalations")
        .update({
            "status": resolution.status,
            "resolved_by": resolution.resolved_by,
            "resolution_note": resolution.resolution_note,
            "resolved_at": "now()",
        })
        .eq("id", escalation_id)
        .eq("organization_id", org["id"])
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Escalation not found")

    return result.data[0]