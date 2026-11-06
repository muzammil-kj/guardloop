from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from app.auth.actors import get_actor, require_role
from app.db.supabase_client import get_supabase
from app.exports.csv_export import to_csv

router = APIRouter(tags=["audit"])

DECISION_COLUMNS = [
    "id", "created_at", "agent_name", "event_type", "status", "confidence",
    "cost_usd", "pii_redacted", "judge_verdict", "input_summary", "output_summary",
]
AUDIT_COLUMNS = [
    "id", "created_at", "actor_name", "actor_type", "action",
    "target_type", "target_id", "detail",
]


def _csv_response(body: str, filename: str) -> Response:
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/audit")
async def list_audit(limit: int = Query(default=100, ge=1, le=500), actor: dict = Depends(get_actor)):
    require_role(actor, "owner")
    return (
        get_supabase().table("audit_log").select("*")
        .eq("organization_id", actor["id"])
        .order("created_at", desc=True).limit(limit)
        .execute().data
    )


@router.get("/exports/audit.csv")
async def export_audit(actor: dict = Depends(get_actor)):
    require_role(actor, "owner")
    rows = (
        get_supabase().table("audit_log").select("*")
        .eq("organization_id", actor["id"])
        .order("created_at", desc=True).limit(10000)
        .execute().data
    )
    return _csv_response(to_csv(rows, AUDIT_COLUMNS), "guardloop-audit.csv")


@router.get("/exports/decisions.csv")
async def export_decisions(
    limit: int = Query(default=5000, ge=1, le=10000), actor: dict = Depends(get_actor)
):
    rows = (
        get_supabase().table("agent_events").select(",".join(DECISION_COLUMNS))
        .eq("organization_id", actor["id"])
        .order("created_at", desc=True).limit(limit)
        .execute().data
    )
    return _csv_response(to_csv(rows, DECISION_COLUMNS), "guardloop-decisions.csv")