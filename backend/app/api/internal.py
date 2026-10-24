import logging
import secrets

from fastapi import APIRouter, Header, HTTPException

from app.alerts.checker import run_checks_for_channel
from app.config import settings
from app.db.supabase_client import get_supabase
from app.judge.reviewer import review_pending

logger = logging.getLogger("guardloop.alerts")

router = APIRouter(prefix="/internal", tags=["internal"])

# One cron pass reviews at most this many events, within this many seconds,
# so a request never outlives the cron service's own timeout.
JUDGE_PASS_LIMIT = 20
JUDGE_PASS_TIME_BUDGET_SECONDS = 40


def _authorize(x_internal_secret: str | None) -> None:
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


@router.post("/run-checks")
async def run_checks(x_internal_secret: str | None = Header(default=None)):
    """
    Called by an external scheduler (a free cron service) every few minutes.
    An in-process scheduler would silently stop whenever Render's free tier
    puts the service to sleep; an external ping also wakes it back up.
    """
    _authorize(x_internal_secret)

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


@router.post("/run-judge")
def run_judge(x_internal_secret: str | None = Header(default=None)):
    """Scheduled judge pass across every organization. Plain `def` because it
    makes slow model calls; FastAPI runs it in a thread pool."""
    _authorize(x_internal_secret)

    if not settings.gemini_api_key:
        raise HTTPException(
            status_code=503,
            detail="The judge is not configured (GEMINI_API_KEY is unset).",
        )

    return review_pending(
        get_supabase(),
        organization_id=None,
        limit=JUDGE_PASS_LIMIT,
        time_budget_seconds=JUDGE_PASS_TIME_BUDGET_SECONDS,
    )
