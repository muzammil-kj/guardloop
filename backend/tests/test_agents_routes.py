from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_org
from app.main import app
from tests.test_budget import queued

ORG = {"id": "org-1"}


@pytest.fixture
def client():
    app.dependency_overrides[get_current_org] = lambda: ORG
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_permission_route_reports_blocked(client):
    status = {"agent_name": "bot", "allowed": False, "daily_budget_usd": 5.0,
              "spent_today_usd": 6.0, "remaining_usd": 0.0}
    with patch("app.api.agents.get_supabase"), \
         patch("app.api.agents.budget_status", return_value=status):
        response = client.get("/agents/bot/permission")
    assert response.status_code == 200
    assert response.json()["allowed"] is False


def test_setting_a_budget_on_an_existing_agent_updates_it(client, make_fake_supabase, fake_query):
    table = fake_query(data=[{"id": 3}])
    fake = make_fake_supabase(agent_policies=table)
    with patch("app.api.agents.get_supabase", return_value=fake):
        response = client.put("/agents/bot/budget", json={"daily_budget_usd": 4})
    assert response.status_code == 200
    assert table.updates[-1]["daily_budget_usd"] == 4


def test_a_new_agent_budget_inherits_the_organization_threshold(client, make_fake_supabase, fake_query):
    """Regression guard: a budget-only row must not reset the threshold to 0.75."""
    table = queued(fake_query, [
        [],                                                                                  # no agent row yet
        [{"confidence_threshold": 0.85, "hard_escalate_event_types": ["job_application"]}],  # org default
    ])
    fake = make_fake_supabase(agent_policies=table)
    with patch("app.api.agents.get_supabase", return_value=fake):
        response = client.put("/agents/bot/budget", json={"daily_budget_usd": 2})
    assert response.status_code == 200
    assert table.inserted["confidence_threshold"] == 0.85
    assert table.inserted["hard_escalate_event_types"] == ["job_application"]
    assert table.inserted["daily_budget_usd"] == 2


def test_budget_must_be_positive(client):
    assert client.put("/agents/bot/budget", json={"daily_budget_usd": 0}).status_code == 422


def test_removing_a_budget_is_allowed(client, make_fake_supabase, fake_query):
    table = fake_query(data=[{"id": 3}])
    fake = make_fake_supabase(agent_policies=table)
    with patch("app.api.agents.get_supabase", return_value=fake):
        response = client.put("/agents/bot/budget", json={"daily_budget_usd": None})
    assert response.status_code == 200
    assert table.updates[-1]["daily_budget_usd"] is None


def test_agent_routes_require_an_api_key():
    unauth = TestClient(app)
    assert unauth.get("/agents/bot/permission").status_code == 401
    assert unauth.put("/agents/bot/budget", json={"daily_budget_usd": 1}).status_code == 401