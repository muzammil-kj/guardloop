from fastapi import APIRouter, Depends
from datetime import date

from app.db.supabase_client import get_supabase
from app.models import IngestEvent
from app.policies.evaluator import should_escalate
from app.judge.sampling import decide_judge_sampling
from app.auth.dependencies import get_current_org

router = APIRouter(tags=["ingestion"])


@router.post("/ingest")
async def ingest_event(event: IngestEvent, org: dict = Depends(get_current_org)):
    supabase = get_supabase()
    escalate, reason = should_escalate(
        supabase,
        org["id"],
        event.agent_name,
        event.event_type,
        event.confidence,
        event.force_escalate,
    )
    reason = event.escalate_reason or reason
    status = "escalated" if escalate else "approved"

    # Auto-approved events may be queued for a second opinion from the judge.
    # Escalated events aren't: a human is already looking at those.
    has_content = bool(
        (event.input_summary or "").strip() or (event.output_summary or "").strip()
    )
    judge_sampled = (
        not escalate
        and decide_judge_sampling(supabase, org["id"], has_content)
    )

    event_payload = {
        "organization_id": org["id"],
        "agent_name": event.agent_name,
        "event_type": event.event_type,
        "input_summary": event.input_summary,
        "output_summary": event.output_summary,
        "confidence": event.confidence,
        "status": status,
        "cost_usd": event.cost_usd,
    }
    if judge_sampled:
        event_payload["judge_status"] = "pending"

    event_row = supabase.table("agent_events").insert(event_payload).execute()

    event_id = event_row.data[0]["id"]

    if escalate:
        supabase.table("escalations").insert({
            "organization_id": org["id"],
            "event_id": event_id,
            "reason": reason,
            "status": "pending",
        }).execute()

    today = str(date.today())
    existing = (
        supabase.table("agent_costs")
        .select("*")
        .eq("organization_id", org["id"])
        .eq("agent_name", event.agent_name)
        .eq("date", today)
        .execute()
    )

    if existing.data:
        row = existing.data[0]
        supabase.table("agent_costs").update({
            "total_cost_usd": row["total_cost_usd"] + event.cost_usd,
            "event_count": row["event_count"] + 1,
        }).eq("id", row["id"]).execute()
    else:
        supabase.table("agent_costs").insert({
            "organization_id": org["id"],
            "agent_name": event.agent_name,
            "date": today,
            "total_cost_usd": event.cost_usd,
            "event_count": 1,
        }).execute()

    return {"event_id": event_id, "status": status, "reason": reason}
