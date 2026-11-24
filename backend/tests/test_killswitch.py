from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.actors import get_actor
from app.auth.dependencies import get_current_org
from app.killswitch import is_killed
from app.main import app

OWNER = {"id": "org-1", "actor_name": "Owner", "actor_type": "user", "actor_role": "owner"}
REVIEWER = {"id": "org-1", "actor_name": "Sara", "actor_type": "user", "actor_role": "reviewer"}
OK_BUDGET = {"agent_name": "bot", "allowed": True, "daily_budget_usd": None,
             "spent_today_usd": 0.0, "remaining_usd": None}


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_a_switched_off_agent_is_reported_killed(make_fake_supabase, fake_query):
    fake = make_fake_supabase(agent_kill_switches=fake_query(data=[{"killed": True, "reason": "bad prompt"}]))
    assert is_killed(fake, "org-1", "bot") == (True, "bad prompt")


def test_an_agent_with_no_row_is_active(make_fake_supabase, fake_query):
    fake = make_fake_supabase(agent_kill_switches=fake_query(data=[]))
    assert is_killed(fake, "org-1", "bot") == (False, None)


def test_only_a_real_true_counts_as_switched_off(make_fake_supabase, fake_query):
    fake = make_fake_supabase(agent_kill_switches=fake_query(data=[{"killed": "yes", "reason": None}]))
    assert is_killed(fake, "org-1", "bot") == (False, None)


def test_a_missing_table_fails_open_instead_of_blocking_everyone(make_fake_supabase):
    fake = make_fake_supabase()  # no agent_kill_switches table: migration not run yet
    assert is_killed(fake, "org-1", "bot") == (False, None)


def test_a_reviewer_cannot_switch_an_agent_off():
    app.dependency_overrides[get_actor] = lambda: REVIEWER
    response = TestClient(app).put("/agents/bot/kill-switch", json={"killed": True, "reason": "x"})
    assert response.status_code == 403


def test_switching_off_is_saved_and_audited(make_fake_supabase, fake_query):
    app.dependency_overrides[get_actor] = lambda: OWNER
    table = fake_query()
    audit = fake_query()
    fake = make_fake_supabase(agent_kill_switches=table, audit_log=audit)
    with patch("app.api.killswitch.get_supabase", return_value=fake):
        response = TestClient(app).put("/agents/bot/kill-switch",
                                       json={"killed": True, "reason": "runaway loop"})
    assert response.status_code == 200
    assert response.json() == {"agent_name": "bot", "killed": True, "reason": "runaway loop"}
    assert table.upserted["killed"] is True
    assert table.upsert_kwargs["on_conflict"] == "organization_id,agent_name"
    assert audit.inserted["action"] == "agent.kill_switch_on"


def test_switching_back_on_clears_the_reason_and_is_audited(make_fake_supabase, fake_query):
    app.dependency_overrides[get_actor] = lambda: OWNER
    table = fake_query()
    audit = fake_query()
    fake = make_fake_supabase(agent_kill_switches=table, audit_log=audit)
    with patch("app.api.killswitch.get_supabase", return_value=fake):
        response = TestClient(app).put("/agents/bot/kill-switch",
                                       json={"killed": False, "reason": "left over"})
    assert response.status_code == 200
    assert table.upserted["reason"] is None
    assert audit.inserted["action"] == "agent.kill_switch_off"


def test_an_overlong_reason_is_rejected():
    app.dependency_overrides[get_actor] = lambda: OWNER
    response = TestClient(app).put("/agents/bot/kill-switch", json={"killed": True, "reason": "x" * 301})
    assert response.status_code == 422


def test_ingest_refuses_a_switched_off_agent_and_records_nothing(make_fake_supabase, fake_query):
    app.dependency_overrides[get_current_org] = lambda: {"id": "org-1"}
    fake = make_fake_supabase(agent_kill_switches=fake_query(data=[{"killed": True, "reason": "stop"}]))
    process = MagicMock()
    with patch("app.ingestion.routes.get_supabase", return_value=fake), \
         patch("app.ingestion.routes.process_event", process):
        response = TestClient(app).post("/ingest", json={"agent_name": "bot", "event_type": "answer"})
    assert response.status_code == 403
    assert "switched off" in response.json()["detail"]
    process.assert_not_called()


def test_permission_reports_a_switched_off_agent_as_not_allowed(make_fake_supabase, fake_query):
    app.dependency_overrides[get_current_org] = lambda: {"id": "org-1"}
    fake = make_fake_supabase(agent_kill_switches=fake_query(data=[{"killed": True, "reason": "stop"}]))
    with patch("app.api.agents.get_supabase", return_value=fake), \
         patch("app.api.agents.budget_status", return_value=OK_BUDGET):
        response = TestClient(app).get("/agents/bot/permission")
    body = response.json()
    assert body["allowed"] is False
    assert body["killed"] is True
    assert body["kill_reason"] == "stop"


def test_permission_for_an_active_agent_is_unchanged(make_fake_supabase, fake_query):
    app.dependency_overrides[get_current_org] = lambda: {"id": "org-1"}
    fake = make_fake_supabase(agent_kill_switches=fake_query(data=[]))
    with patch("app.api.agents.get_supabase", return_value=fake), \
         patch("app.api.agents.budget_status", return_value=OK_BUDGET):
        body = TestClient(app).get("/agents/bot/permission").json()
    assert body["allowed"] is True
    assert body["killed"] is False