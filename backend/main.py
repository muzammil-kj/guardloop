from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import date

from database import supabase
from models import IngestEvent, ResolveEscalation
from escalation_logic import should_escalate

app = FastAPI(title="Guardloop API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this to your Vercel domain once deployed
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/ingest")
async def ingest_event(event: IngestEvent):
    """
    Any agent (n8n, LangChain, custom script) calls this after it makes a
    decision. Guardloop decides whether that decision is safe to
    auto-approve, or needs a human in the loop.
    """
    escalate, reason = should_escalate(event.confidence, event.force_escalate)
    reason = event.escalate_reason or reason
    status = "escalated" if escalate else "approved"

    event_row = supabase.table("agent_events").insert({
        "agent_name": event.agent_name,
        "event_type": event.event_type,
        "input_summary": event.input_summary,
        "output_summary": event.output_summary,
        "confidence": event.confidence,
        "status": status,
        "cost_usd": event.cost_usd,
    }).execute()

    event_id = event_row.data[0]["id"]

    if escalate:
        supabase.table("escalations").insert({
            "event_id": event_id,
            "reason": reason,
            "status": "pending",
        }).execute()

    # Upsert daily cost rollup for this agent
    today = str(date.today())
    existing = supabase.table("agent_costs").select("*").eq(
        "agent_name", event.agent_name
    ).eq("date", today).execute()

    if existing.data:
        row = existing.data[0]
        supabase.table("agent_costs").update({
            "total_cost_usd": row["total_cost_usd"] + event.cost_usd,
            "event_count": row["event_count"] + 1,
        }).eq("id", row["id"]).execute()
    else:
        supabase.table("agent_costs").insert({
            "agent_name": event.agent_name,
            "date": today,
            "total_cost_usd": event.cost_usd,
            "event_count": 1,
        }).execute()

    return {"event_id": event_id, "status": status, "reason": reason}


@app.get("/events")
async def list_events(limit: int = 50):
    result = supabase.table("agent_events").select("*").order(
        "created_at", desc=True
    ).limit(limit).execute()
    return result.data


@app.get("/escalations")
async def list_escalations(status: str = "pending"):
    result = supabase.table("escalations").select(
        "*, agent_events(*)"
    ).eq("status", status).order("created_at", desc=True).execute()
    return result.data


@app.patch("/escalations/{escalation_id}/resolve")
async def resolve_escalation(escalation_id: int, resolution: ResolveEscalation):
    result = supabase.table("escalations").update({
        "status": resolution.status,
        "resolved_by": resolution.resolved_by,
        "resolution_note": resolution.resolution_note,
        "resolved_at": "now()",
    }).eq("id", escalation_id).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Escalation not found")

    return result.data[0]


@app.get("/costs")
async def list_costs():
    result = supabase.table("agent_costs").select("*").order(
        "date", desc=True
    ).execute()
    return result.data