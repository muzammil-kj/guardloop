from fastapi import APIRouter, Depends, HTTPException

from app.audit import record_audit
from app.auth.actors import get_actor, require_role
from app.db.supabase_client import get_supabase
from app.models import AssignEscalation, ResolveEscalation

router = APIRouter(tags=["escalations"])


@router.get("/escalations")
async def list_escalations(status: str = "pending", actor: dict = Depends(get_actor)):
    result = (
        get_supabase().table("escalations")
        .select("*, agent_events(*)")
        .eq("organization_id", actor["id"])
        .eq("status", status)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@router.patch("/escalations/{escalation_id}/resolve")
async def resolve_escalation(
    escalation_id: int, resolution: ResolveEscalation, actor: dict = Depends(get_actor)
):
    """Signed-in reviewers are recorded by their name. The body's resolved_by is only
    used for service API keys, which have no user identity."""
    require_role(actor, "reviewer")
    supabase = get_supabase()
    resolved_by = actor["actor_name"] if actor["actor_type"] == "user" else resolution.resolved_by

    result = (
        supabase.table("escalations")
        .update({
            "status": resolution.status,
            "resolved_by": resolved_by,
            "resolution_note": resolution.resolution_note,
            "resolved_at": "now()",
        })
        .eq("id", escalation_id)
        .eq("organization_id", actor["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Escalation not found")

    record_audit(
        supabase, {**actor, "actor_name": resolved_by}, "escalation.resolved",
        "escalation", escalation_id,
        {"status": resolution.status, "note": resolution.resolution_note},
    )
    return result.data[0]


@router.patch("/escalations/{escalation_id}/assign")
async def assign_escalation(
    escalation_id: int, payload: AssignEscalation, actor: dict = Depends(get_actor)
):
    """Assigns a review to a member of this organization. Send null to unassign."""
    require_role(actor, "reviewer")
    supabase = get_supabase()

    assignee = None
    if payload.assignee_email:
        assignee = payload.assignee_email.strip().lower()
        members = (
            supabase.table("memberships").select("id")
            .eq("organization_id", actor["id"]).eq("email", assignee)
            .execute().data
        )
        if not members:
            raise HTTPException(status_code=400, detail="That person is not a member of this organization.")

    result = (
        supabase.table("escalations")
        .update({"assigned_to": assignee})
        .eq("id", escalation_id)
        .eq("organization_id", actor["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Escalation not found")

    record_audit(supabase, actor, "escalation.assigned", "escalation", escalation_id, {"assigned_to": assignee})
    return result.data[0]
