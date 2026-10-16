import logging
import secrets

from fastapi import APIRouter, Header, HTTPException

from app.alerts.checker import run_checks_for_channel
from app.config import settings
from app.db.supabase_client import get_supabase

logger = logging.getLogger("guardloop.alerts")

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/run-checks")
async def run_checks(x_internal_secret: str | None = Header(default=None)):
    """
    Called by an external scheduler (a free cron service) every few minutes.
    An in-process scheduler would silently stop whenever Render's free tier
    puts the service to sleep; an external ping also wakes it back up.
    """
    configured = settings.internal_cron_secret
    if not configured:
        raise HTTPException(
            status_code=503,
            detail="Internal checks are not configured (INTERNAL_CRON_SECRET is unset).",
        )

    # Constant-time comparison so response timing can't leak the secret.
    if not x_internal_secret or not secrets.compare_digest(
        x_internal_secret.encode(), configured.encode()
    ):
        raise HTTPException(status_code=401, detail="Invalid internal secret.")

    supabase = get_supabase()
    channels = (
        supabase.table("alert_channels").select("*").eq("enabled", True).execute()
    )

    checked = 0
    failed = 0
    for channel in channels.data:
        # One broken webhook must not stop alerts for everyone else.
        try:
            run_checks_for_channel(supabase, channel)
            checked += 1
        except Exception as exc:
            failed += 1
            logger.warning(
                "Alert check failed for channel %s: %s", channel.get("id"), exc
            )

    return {"channels_checked": checked, "channels_failed": failed}
