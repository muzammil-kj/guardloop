from fastapi import APIRouter, Depends, HTTPException

from app.alerts.dispatcher import AlertDeliveryError, mask_webhook_url, send_alert
from app.auth.dependencies import get_current_org
from app.db.supabase_client import get_supabase
from app.models import AlertChannelCreate, AlertChannelInfo

router = APIRouter(prefix="/alert-channels", tags=["alert-channels"])


def _to_info(row: dict) -> AlertChannelInfo:
    return AlertChannelInfo(
        id=row["id"],
        channel_type=row["channel_type"],
        webhook_hint=mask_webhook_url(row["webhook_url"]),
        queue_depth_threshold=row["queue_depth_threshold"],
        daily_budget_usd=float(row["daily_budget_usd"]),
        enabled=row["enabled"],
        created_at=row["created_at"],
    )


@router.get("", response_model=list[AlertChannelInfo])
async def list_channels(org: dict = Depends(get_current_org)):
    supabase = get_supabase()
    result = (
        supabase.table("alert_channels")
        .select("*")
        .eq("organization_id", org["id"])
        .order("created_at", desc=True)
        .execute()
    )
    return [_to_info(row) for row in result.data]


@router.post("", response_model=AlertChannelInfo)
async def create_channel(
    payload: AlertChannelCreate, org: dict = Depends(get_current_org)
):
    supabase = get_supabase()
    result = (
        supabase.table("alert_channels")
        .insert({
            "organization_id": org["id"],
            "channel_type": payload.channel_type,
            "webhook_url": payload.webhook_url,
            "queue_depth_threshold": payload.queue_depth_threshold,
            "daily_budget_usd": payload.daily_budget_usd,
            "enabled": True,
        })
        .execute()
    )
    return _to_info(result.data[0])


@router.post("/{channel_id}/test")
async def send_test_alert(channel_id: int, org: dict = Depends(get_current_org)):
    """Sends a test message so a team can confirm the webhook works now."""
    supabase = get_supabase()
    result = (
        supabase.table("alert_channels")
        .select("*")
        .eq("id", channel_id)
        .eq("organization_id", org["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Alert channel not found.")

    channel = result.data[0]
    try:
        send_alert(
            channel["channel_type"],
            channel["webhook_url"],
            "Guardloop test alert: this channel is connected and working.",
        )
    except AlertDeliveryError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return {"status": "sent"}


@router.delete("/{channel_id}")
async def delete_channel(channel_id: int, org: dict = Depends(get_current_org)):
    supabase = get_supabase()
    result = (
        supabase.table("alert_channels")
        .delete()
        .eq("id", channel_id)
        .eq("organization_id", org["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Alert channel not found.")
    return {"status": "deleted"}
