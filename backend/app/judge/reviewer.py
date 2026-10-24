import logging
import time
from datetime import datetime, timedelta, timezone

from app.judge.gemini import JudgeError, JudgeRateLimited, judge_event

logger = logging.getLogger("guardloop.judge")

MAX_ATTEMPTS = 3
STALE_CLAIM_AFTER = timedelta(minutes=10)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _has_content(row: dict) -> bool:
    return bool(
        (row.get("input_summary") or "").strip()
        or (row.get("output_summary") or "").strip()
    )


def _release_stale_claims(supabase, organization_id: str | None) -> None:
    """A pass that died mid-review leaves events stuck in 'reviewing'.
    Put any claim older than STALE_CLAIM_AFTER back in the queue."""
    cutoff = (datetime.now(timezone.utc) - STALE_CLAIM_AFTER).isoformat()
    query = (
        supabase.table("agent_events")
        .update({"judge_status": "pending", "judge_claimed_at": None})
        .eq("judge_status", "reviewing")
        .lt("judge_claimed_at", cutoff)
    )
    if organization_id:
        query = query.eq("organization_id", organization_id)
    query.execute()


def _claim(supabase, event_id: int) -> bool:
    """Atomically move pending -> reviewing. If another pass got there first,
    the filter matches nothing and we get no row back."""
    result = (
        supabase.table("agent_events")
        .update({"judge_status": "reviewing", "judge_claimed_at": _now_iso()})
        .eq("id", event_id)
        .eq("judge_status", "pending")
        .execute()
    )
    return bool(result.data)


def _flag_for_humans(supabase, row: dict, reason: str) -> None:
    # An auto-approved event has no escalation row, so any existing one means
    # an earlier pass already flagged it. Checking keeps this idempotent.
    existing = (
        supabase.table("escalations").select("id").eq("event_id", row["id"]).execute()
    )
    if existing.data:
        return
    supabase.table("escalations").insert({
        "organization_id": row["organization_id"],
        "event_id": row["id"],
        "reason": f"Judge disagreed with this auto-approved decision: {reason}",
        "status": "pending",
    }).execute()


def review_pending(
    supabase,
    *,
    organization_id: str | None = None,
    limit: int = 5,
    time_budget_seconds: float = 25.0,
    judge=judge_event,
) -> dict:
    """
    Reviews up to `limit` sampled events (one organization, or all of them
    when organization_id is None). Returns counts of what happened.
    Plain `def`, not async: it makes slow network calls, and FastAPI runs
    plain handlers in a thread pool instead of blocking the event loop.
    """
    stats = {
        "reviewed": 0,
        "flagged": 0,
        "skipped": 0,
        "failed": 0,
        "retry_later": 0,
        "deferred": 0,
        "rate_limited": False,
        "last_error": None,  # newest model error this pass, so the UI can show why
    }

    _release_stale_claims(supabase, organization_id)

    query = supabase.table("agent_events").select("*").eq("judge_status", "pending")
    if organization_id:
        query = query.eq("organization_id", organization_id)
    rows = query.order("created_at").limit(limit).execute().data

    started = time.monotonic()
    for index, row in enumerate(rows):
        if time.monotonic() - started >= time_budget_seconds:
            stats["deferred"] += len(rows) - index
            break

        if not _claim(supabase, row["id"]):
            continue  # another pass took it

        attempts = (row.get("judge_attempts") or 0) + 1

        if not _has_content(row):
            supabase.table("agent_events").update({
                "judge_status": "skipped",
                "judge_reason": "No input or output summary to review.",
            }).eq("id", row["id"]).execute()
            stats["skipped"] += 1
            continue

        try:
            result = judge(row)
        except JudgeRateLimited:
            # Not this event's fault: put it back untouched and stop the batch.
            supabase.table("agent_events").update({
                "judge_status": "pending",
                "judge_claimed_at": None,
            }).eq("id", row["id"]).execute()
            stats["rate_limited"] = True
            stats["deferred"] += len(rows) - index
            break
        except Exception as exc:
            message = str(exc) if isinstance(exc, JudgeError) else type(exc).__name__
            logger.warning("Judge failed on event %s: %s", row["id"], message)
            stats["last_error"] = message
            exhausted = attempts >= MAX_ATTEMPTS
            supabase.table("agent_events").update({
                "judge_status": "failed" if exhausted else "pending",
                "judge_claimed_at": None,
                "judge_attempts": attempts,
                "judge_reason": f"Review attempt failed: {message}",
            }).eq("id", row["id"]).execute()
            stats["failed" if exhausted else "retry_later"] += 1
            continue

        # Flag first, then record the verdict: if recording fails the event
        # is retried, and _flag_for_humans won't create a second escalation.
        if result.verdict == "disagree":
            _flag_for_humans(supabase, row, result.reason)
            stats["flagged"] += 1

        supabase.table("agent_events").update({
            "judge_status": "reviewed",
            "judge_verdict": result.verdict,
            "judge_score": result.score,
            "judge_reason": result.reason,
            "judge_reviewed_at": _now_iso(),
            "judge_claimed_at": None,
            "judge_attempts": attempts,
        }).eq("id", row["id"]).execute()
        stats["reviewed"] += 1

    return stats
