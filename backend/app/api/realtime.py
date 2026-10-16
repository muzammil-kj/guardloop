from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_org
from app.realtime.token import mint_realtime_token, RealtimeNotConfigured

router = APIRouter(prefix="/organizations/me", tags=["realtime"])


@router.post("/realtime-token")
async def get_realtime_token(org: dict = Depends(get_current_org)):
    """
    Exchanges a valid Guardloop API key for a short-lived Supabase Realtime
    token scoped to this organization, so the dashboard can receive live
    updates instead of polling.
    """
    try:
        token = mint_realtime_token(org["id"])
    except RealtimeNotConfigured:
        raise HTTPException(
            status_code=503,
            detail="Realtime is not configured on this server.",
        )
    return {"token": token, "organization_id": org["id"]}
