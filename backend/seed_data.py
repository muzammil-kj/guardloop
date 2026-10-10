
"""
Seeds realistic demo events across 3 simulated agents.

Run from the backend directory:
    python seed_data.py
"""

import random
from datetime import datetime, timedelta, timezone

from app.db.supabase_client import get_supabase

supabase = get_supabase()

DEMO_ORG_ID = "00000000-0000-0000-0000-000000000001"
DEMO_ORG_NAME = "Guardloop Demo Organization"
CONFIDENCE_THRESHOLD = 0.75

AGENTS = [
    "email-triage-agent",
    "support-chat-agent",
    "data-entry-agent",
]

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


def ensure_demo_organization():
    existing = (
        supabase.table("organizations")
        .select("id")
        .eq("id", DEMO_ORG_ID)
        .execute()
    )

    if existing.data:
        print("Demo organization already exists.")
        return

    supabase.table("organizations").insert({
        "id": DEMO_ORG_ID,
        "name": DEMO_ORG_NAME,
    }).execute()

    print("Created demo organization.")


def random_timestamp_within_last_days(days: int) -> str:
    delta = timedelta(
        days=random.randint(0, days),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )
    timestamp = datetime.now(timezone.utc) - delta
    return timestamp.isoformat()


def seed():
    ensure_demo_organization()

    # Avoid accidentally inserting another full batch.
    existing = (
        supabase.table("agent_events")
        .select("id")
        .eq("organization_id", DEMO_ORG_ID)
        .limit(1)
        .execute()
    )

    if existing.data:
        print(
            "Demo events already exist. No new events were inserted. "
            "If you want to reseed, inspect the existing demo data first."
        )
        return

    inserted = 0
    escalations_inserted = 0

    for agent in AGENTS:
        for _ in range(12):
            input_summary, output_summary, base_confidence = random.choice(
                EVENT_SAMPLES[agent]
            )

            confidence = round(
                min(
                    0.99,
                    max(
                        0.30,
                        base_confidence + random.uniform(-0.1, 0.05),
                    ),
                ),
                2,
            )

            status = (
                "escalated"
                if confidence < CONFIDENCE_THRESHOLD
                else "approved"
            )
            cost = round(random.uniform(0.0005, 0.01), 6)

            event = (
                supabase.table("agent_events")
                .insert({
                    "organization_id": DEMO_ORG_ID,
                    "agent_name": agent,
                    "event_type": "classification",
                    "input_summary": input_summary,
                    "output_summary": output_summary,
                    "confidence": confidence,
                    "status": status,
                    "cost_usd": cost,
                    "created_at": random_timestamp_within_last_days(6),
                })
                .execute()
            )

            if status == "escalated":
                supabase.table("escalations").insert({
                    "organization_id": DEMO_ORG_ID,
                    "event_id": event.data[0]["id"],
                    "reason": (
                        f"Confidence {confidence} below threshold "
                        f"{CONFIDENCE_THRESHOLD}."
                    ),
                    "status": "pending",
                }).execute()

                escalations_inserted += 1

            inserted += 1

    print(
        f"Seeded {inserted} events and {escalations_inserted} pending "
        f"escalations for {DEMO_ORG_NAME}."
    )


if __name__ == "__main__":
    seed()
