from fastapi import APIRouter, Depends

from app.db.supabase_client import get_supabase
from app.auth.dependencies import get_current_org

router = APIRouter(tags=["events"])


@router.get("/events")
async def list_events(limit: int = 50, org: dict = Depends(get_current_org)):
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