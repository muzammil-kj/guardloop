from fastapi import APIRouter, Depends

from app.db.supabase_client import get_supabase
from app.auth.actors import get_actor

router = APIRouter(tags=["costs"])


@router.get("/costs")
async def list_costs(org: dict = Depends(get_actor)):
    supabase = get_supabase()
    result = (
        supabase.table("agent_costs")
        .select("*")
        .eq("organization_id", org["id"])
        .order("date", desc=True)
        .execute()
    )
    return result.data