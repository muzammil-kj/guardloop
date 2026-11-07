from fastapi import APIRouter, Depends, Query

from app.auth.actors import get_actor
from app.db.supabase_client import get_supabase
from app.judge.calibration import summarize_calibration
from app.judge.versions import summarize_versions

router = APIRouter(prefix="/quality", tags=["quality"])


@router.get("/calibration")
async def judge_calibration(actor: dict = Depends(get_actor)):
    """How often the judge's flags were confirmed by humans, overall and per agent."""
    rows = (
        get_supabase().table("escalations")
        .select("status, agent_events(agent_name)")
        .eq("organization_id", actor["id"])
        .eq("source", "judge")
        .in_("status", ["approved", "rejected"])
        .order("resolved_at", desc=True)
        .limit(2000)
        .execute().data
    )
    return summarize_calibration(rows)


@router.get("/versions")
async def agent_versions(limit: int = Query(default=5000, ge=1, le=20000), actor: dict = Depends(get_actor)):
    """Decision quality per agent version, oldest first, so a deploy's effect is visible."""
    rows = (
        get_supabase().table("agent_events")
        .select("agent_name, agent_version, status, judge_verdict, created_at")
        .eq("organization_id", actor["id"])
        .order("created_at", desc=True)
        .limit(limit)
        .execute().data
    )
    return summarize_versions(rows)