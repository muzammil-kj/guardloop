from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import get_current_org
from app.config import settings
from app.db.supabase_client import get_supabase
from app.judge.reviewer import review_pending
from app.judge.sampling import get_judge_settings
from app.judge.summary import summarize
from app.models import JudgeSettingsInfo, JudgeSettingsUpdate

router = APIRouter(prefix="/judge", tags=["judge"])

# How many recent reviews feed the per-agent statistics.
SUMMARY_WINDOW = 500

# A manual "review now" is capped so one click can't run up a large bill.
MANUAL_RUN_LIMIT = 5
MANUAL_RUN_TIME_BUDGET_SECONDS = 25


def _info(config: dict) -> JudgeSettingsInfo:
    return JudgeSettingsInfo(
        enabled=config["enabled"],
        sample_rate=config["sample_rate"],
        judge_configured=bool(settings.gemini_api_key),
    )


@router.get("/settings", response_model=JudgeSettingsInfo)
def read_settings(org: dict = Depends(get_current_org)):
    return _info(get_judge_settings(get_supabase(), org["id"]))


@router.put("/settings", response_model=JudgeSettingsInfo)
def update_settings(payload: JudgeSettingsUpdate, org: dict = Depends(get_current_org)):
    get_supabase().table("judge_settings").upsert(
        {
            "organization_id": org["id"],
            "enabled": payload.enabled,
            "sample_rate": payload.sample_rate,
        },
        on_conflict="organization_id",
    ).execute()
    return _info({"enabled": payload.enabled, "sample_rate": payload.sample_rate})


@router.get("/summary")
def read_summary(org: dict = Depends(get_current_org)):
    supabase = get_supabase()

    reviewed = (
        supabase.table("agent_events")
        .select("agent_name, confidence, judge_verdict")
        .eq("organization_id", org["id"])
        .eq("judge_status", "reviewed")
        .order("judge_reviewed_at", desc=True)
        .limit(SUMMARY_WINDOW)
        .execute()
    )
    pending = (
        supabase.table("agent_events")
        .select("id", count="exact")
        .eq("organization_id", org["id"])
        .eq("judge_status", "pending")
        .execute()
    )

    config = get_judge_settings(supabase, org["id"])
    return {
        "enabled": config["enabled"],
        "sample_rate": config["sample_rate"],
        "judge_configured": bool(settings.gemini_api_key),
        "pending": pending.count or 0,
        **summarize(reviewed.data),
    }


@router.get("/reviews")
def read_reviews(
    limit: int = Query(default=10, ge=1, le=50),
    org: dict = Depends(get_current_org),
):
    result = (
        get_supabase()
        .table("agent_events")
        .select(
            "id, agent_name, event_type, input_summary, output_summary, confidence, "
            "judge_verdict, judge_score, judge_reason, judge_reviewed_at"
        )
        .eq("organization_id", org["id"])
        .eq("judge_status", "reviewed")
        .order("judge_reviewed_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data


@router.post("/run")
def run_now(org: dict = Depends(get_current_org)):
    """Reviews this organization's waiting events immediately, so a demo or a
    first-time setup doesn't have to wait for the scheduled pass."""
    if not settings.gemini_api_key:
        raise HTTPException(
            status_code=503,
            detail="The judge is not configured on this server (GEMINI_API_KEY is unset).",
        )
    return review_pending(
        get_supabase(),
        organization_id=org["id"],
        limit=MANUAL_RUN_LIMIT,
        time_budget_seconds=MANUAL_RUN_TIME_BUDGET_SECONDS,
    )
