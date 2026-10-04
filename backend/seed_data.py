"""
Generates ~40 realistic fake events across 3 simulated agents, so the
dashboard has something meaningful to show the moment it's deployed,
without needing a live agent connected yet.

Run with: python seed_data.py
"""
import random
from datetime import datetime, timedelta
from database import supabase

AGENTS = ["email-triage-agent", "support-chat-agent", "data-entry-agent"]

EVENT_SAMPLES = {
    "email-triage-agent": [
        ("Incoming email: 'Can we schedule a call tomorrow?'", "Classified as: meeting_request, priority: normal", 0.94),
        ("Incoming email: 'URGENT - system down'", "Classified as: urgent, escalated to on-call", 0.88),
        ("Incoming email: 'Please review my application'", "Classified as: job_application, routed to HR", 0.91),
        ("Incoming email: ambiguous subject, mixed signals", "Classified as: general_query", 0.61),
        ("Incoming email: promotional content", "Classified as: spam, archived", 0.97),
    ],
    "support-chat-agent": [
        ("User: 'How do I reset my password?'", "Answered from knowledge base, cited source article", 0.93),
        ("User: 'My payment failed twice, I'm frustrated'", "Flagged as complaint, escalated to human agent", 0.82),
        ("User: 'What's your refund policy for annual plans?'", "Answered from knowledge base", 0.58),
        ("User: 'Is my data secure?'", "Answered from knowledge base, cited security page", 0.90),
    ],
    "data-entry-agent": [
        ("New lead record: missing company field", "Flagged for manual review, field left blank", 0.70),
        ("New lead record: complete and well-formed", "Auto-approved and inserted", 0.96),
        ("New lead record: duplicate suspected", "Escalated for duplicate review", 0.55),
        ("New lead record: country field unrecognized value", "Escalated, unrecognized format", 0.62),
    ],
}


def random_timestamp_within_last_days(days: int) -> str:
    delta = timedelta(
        days=random.randint(0, days),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )
    ts = datetime.utcnow() - delta
    return ts.isoformat()


def seed():
    inserted = 0
    for agent in AGENTS:
        samples = EVENT_SAMPLES[agent]
        for _ in range(12):  # ~12 per agent, ~36 total, close to the ~40 target
            input_summary, output_summary, base_confidence = random.choice(samples)
            confidence = round(min(0.99, max(0.30, base_confidence + random.uniform(-0.1, 0.05))), 2)
            status = "escalated" if confidence < 0.75 else "approved"
            cost = round(random.uniform(0.0005, 0.01), 6)

            event = supabase.table("agent_events").insert({
                "agent_name": agent,
                "event_type": "classification",
                "input_summary": input_summary,
                "output_summary": output_summary,
                "confidence": confidence,
                "status": status,
                "cost_usd": cost,
                "created_at": random_timestamp_within_last_days(6),
            }).execute()

            if status == "escalated":
                supabase.table("escalations").insert({
                    "event_id": event.data[0]["id"],
                    "reason": f"Confidence {confidence} below threshold 0.75.",
                    "status": "pending",
                }).execute()

            inserted += 1

    print(f"Seeded {inserted} events across {len(AGENTS)} agents.")


if __name__ == "__main__":
    seed()