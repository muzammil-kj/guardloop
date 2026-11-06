from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_org
from app.ingestion.service import _pause_notice
from app.main import app

OVER = {"agent_name": "bot", "allowed": False, "daily_budget_usd": 5.0, "spent_today_usd": 6.0, "remaining_usd": 0.0}


def test_the_first_block_of_the_day_creates_one_review(make_fake_supabase, fake_query):
    blocks = fake_query(data=[{"id": 1}])
    escalations = fake_query()
    fake = make_fake_supabase(agent_events=blocks, escalations=escalations)
    _pause_notice(fake, "org-1", "bot", 1, OVER)
    assert escalations.inserted["status"] == "pending"
    assert escalations.inserted["source"] == "budget"
    assert "'bot' is paused" in escalations.inserted["reason"]
    assert "$5.00" in escalations.inserted["reason"]


def test_later_blocks_the_same_day_do_not_flood_the_queue(make_fake_supabase, fake_query):
    blocks = fake_query(data=[{"id": 1}, {"id": 2}, {"id": 3}])
    escalations = fake_query()
    fake = make_fake_supabase(agent_events=blocks, escalations=escalations)
    _pause_notice(fake, "org-1", "bot", 3, OVER)
    assert escalations.inserted is None


def test_a_blocked_request_end_to_end_queues_a_review(make_fake_supabase, fake_query):
    app.dependency_overrides[get_current_org] = lambda: {"id": "org-1"}
    try:
        escalations = fake_query()
        fake = make_fake_supabase(
            agent_policies=fake_query(data=[]),
            agent_events=fake_query(data=[{"id": 1}]),
            escalations=escalations,
            agent_costs=fake_query(data=[]),
            judge_settings=fake_query(data=[]),
        )
        with patch("app.ingestion.routes.get_supabase", return_value=fake), \
             patch("app.ingestion.service.budget_status", return_value=OVER):
            response = TestClient(app).post("/ingest", json={
                "agent_name": "bot", "event_type": "answer", "confidence": 0.9})
        assert response.status_code == 429
        assert escalations.inserted is not None
    finally:
        app.dependency_overrides.clear()