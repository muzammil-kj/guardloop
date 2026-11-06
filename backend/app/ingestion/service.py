from datetime import date, datetime, timezone

from app.judge.sampling import decide_judge_sampling
from app.models import IngestEvent
from app.policies.budget import budget_status
from app.policies.evaluator import should_escalate
from app.privacy.redaction import redact


def _today() -> str:
    return str(date.today())


def _record_cost(supabase, organization_id: str, agent_name: str, cost_usd: float) -> None:
    existing = (
        supabase.table("agent_costs").select("*")
        .eq("organization_id", organization_id)
        .eq("agent_name", agent_name)
        .eq("date", _today())
        .execute()
    )
    if existing.data:
        row = existing.data[0]
        supabase.table("agent_costs").update({
            "total_cost_usd": float(row["total_cost_usd"]) + cost_usd,
            "event_count": row["event_count"] + 1,
        }).eq("id", row["id"]).execute()
    else:
        supabase.table("agent_costs").insert({
            "organization_id": organization_id,
            "agent_name": agent_name,
            "date": _today(),
            "total_cost_usd": cost_usd,
            "event_count": 1,
        }).execute()


def _insert_event(supabase, organization_id, event, input_text, output_text,
                  status, pii_redacted, cost_usd, judge_pending) -> int:
    payload = {
        "organization_id": organization_id,
        "agent_name": event.agent_name,
        "event_type": event.event_type,
        "input_summary": input_text,
        "output_summary": output_text,
        "confidence": event.confidence,
        "status": status,
        "cost_usd": cost_usd,
        "pii_redacted": pii_redacted,
    }
    if judge_pending:
        payload["judge_status"] = "pending"
    return supabase.table("agent_events").insert(payload).execute().data[0]["id"]


def _pause_notice(supabase, organization_id, agent_name, event_id, budget) -> None:
    """One pending review per agent per day, so a runaway loop can't flood the queue."""
    start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    blocks_today = (
        supabase.table("agent_events").select("id")
        .eq("organization_id", organization_id)
        .eq("agent_name", agent_name)
        .eq("status", "blocked")
        .gte("created_at", start_of_day)
        .execute().data
    )
    if len(blocks_today) != 1:
        return  # not the first block today: a notice already exists
    supabase.table("escalations").insert({
        "organization_id": organization_id,
        "event_id": event_id,
        "source": "budget",
        "reason": (
            f"Agent '{agent_name}' is paused: daily budget of ${budget['daily_budget_usd']:.2f} "
            f"reached (spent ${budget['spent_today_usd']:.2f}). It stays paused until the budget "
            "resets or is raised."
        ),
        "status": "pending",
    }).execute()


def process_event(supabase, org: dict, event: IngestEvent) -> dict:
    """The full ingest decision. Returns the response body; the route picks the status code."""
    organization_id = org["id"]

    # 1. Mask personal data first, so storage, escalations and the judge only ever see masked text.
    input_redaction = redact(event.input_summary)
    output_redaction = redact(event.output_summary)
    input_text = input_redaction.text if event.input_summary else None
    output_text = output_redaction.text if event.output_summary else None
    pii_redacted = input_redaction.changed or output_redaction.changed

    # 2. Spend cap. A blocked event is still recorded (audit trail), but costs nothing and is not escalated.
    budget = budget_status(supabase, organization_id, event.agent_name)
    if not budget["allowed"]:
        event_id = _insert_event(supabase, organization_id, event, input_text, output_text,
                                 "blocked", pii_redacted, 0.0, judge_pending=False)
        _pause_notice(supabase, organization_id, event.agent_name, event_id, budget)
        return {
            "event_id": event_id,
            "status": "blocked",
            "reason": (
                f"Daily budget of ${budget['daily_budget_usd']:.2f} reached for this agent "
                f"(spent ${budget['spent_today_usd']:.2f} today). Stop acting until it resets."
            ),
            "pii_redacted": pii_redacted,
        }

    # 3. Human-in-the-loop decision.
    escalate, auto_reason = should_escalate(
        supabase, organization_id, event.agent_name, event.event_type,
        event.confidence, event.force_escalate,
    )
    raw_reason = event.escalate_reason or auto_reason
    reason = None
    if raw_reason:
        reason_redaction = redact(raw_reason)
        reason = reason_redaction.text
        pii_redacted = pii_redacted or reason_redaction.changed
    status = "escalated" if escalate else "approved"

    # 4. Judge sampling (approved events with content only).
    has_content = bool((input_text or "").strip() or (output_text or "").strip())
    judge_pending = status == "approved" and decide_judge_sampling(
        supabase, organization_id, has_content
    )

    event_id = _insert_event(supabase, organization_id, event, input_text, output_text,
                             status, pii_redacted, event.cost_usd, judge_pending)

    if escalate:
        supabase.table("escalations").insert({
            "organization_id": organization_id,
            "event_id": event_id,
            "reason": reason,
            "status": "pending",
        }).execute()

    _record_cost(supabase, organization_id, event.agent_name, event.cost_usd)

    return {"event_id": event_id, "status": status, "reason": reason, "pii_redacted": pii_redacted}