from fastapi import APIRouter, Depends

from app.db.supabase_client import get_supabase
from app.auth.actors import get_actor

router = APIRouter(tags=["events"])


@router.get("/events")
async def list_events(limit: int = 50, org: dict = Depends(get_actor)):
    supabase = get_supabase()
    result = (
        supabase.table("agent_events")
        .select("*")
        .eq("organization_id", org["id"])
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data