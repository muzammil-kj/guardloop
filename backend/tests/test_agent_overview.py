from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.auth.actors import get_actor
from app.main import app

OWNER = {"id": "org-1", "actor_name": "Owner", "actor_type": "user", "actor_role": "owner"}
REVIEWER = {"id": "org-1", "actor_name": "Sara", "actor_type": "user", "actor_role": "reviewer"}


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def as_actor(actor):
    app.dependency_overrides[get_actor] = lambda: actor


def test_overview_combines_events_budgets_spend_and_switches(make_fake_supabase, fake_query):
    as_actor(REVIEWER)
    fake = make_fake_supabase(
        agent_events=fake_query(data=[{"agent_name": "email-bot"}, {"agent_name": "email-bot"},
                                      {"agent_name": "invoice-bot"}]),
        agent_policies=fake_query(data=[{"agent_name": None, "daily_budget_usd": 10.0},
                                        {"agent_name": "email-bot", "daily_budget_usd": 3.0}]),
        agent_kill_switches=fake_query(data=[{"agent_name": "invoice-bot", "killed": True, "reason": "loop"}]),
        agent_costs=fake_query(data=[{"agent_name": "email-bot", "total_cost_usd": 1.5}]),
    )
    with patch("app.api.agents.get_supabase", return_value=fake):
        rows = {r["agent_name"]: r for r in TestClient(app).get("/agents/overview").json()}

    assert set(rows) == {"email-bot", "invoice-bot"}
    assert rows["email-bot"]["daily_budget_usd"] == 3.0
    assert rows["email-bot"]["budget_source"] == "agent"
    assert rows["email-bot"]["spent_today_usd"] == 1.5
    assert rows["email-bot"]["remaining_usd"] == 1.5
    assert rows["email-bot"]["allowed"] is True
    assert rows["invoice-bot"]["budget_source"] == "organization"
    assert rows["invoice-bot"]["killed"] is True
    assert rows["invoice-bot"]["allowed"] is False


def test_an_agent_over_its_cap_is_not_allowed(make_fake_supabase, fake_query):
    as_actor(REVIEWER)
    fake = make_fake_supabase(
        agent_events=fake_query(data=[{"agent_name": "spendy"}]),
        agent_policies=fake_query(data=[{"agent_name": "spendy", "daily_budget_usd": 2.0}]),
        agent_kill_switches=fake_query(data=[]),
        agent_costs=fake_query(data=[{"agent_name": "spendy", "total_cost_usd": 2.5}]),
    )
    with patch("app.api.agents.get_supabase", return_value=fake):
        row = TestClient(app).get("/agents/overview").json()[0]
    assert row["allowed"] is False
    assert row["remaining_usd"] == 0.0


def test_an_agent_with_no_cap_anywhere_has_no_limit(make_fake_supabase, fake_query):
    as_actor(REVIEWER)
    fake = make_fake_supabase(
        agent_events=fake_query(data=[{"agent_name": "free-bot"}]),
        agent_policies=fake_query(data=[]),
        agent_kill_switches=fake_query(data=[]),
        agent_costs=fake_query(data=[]),
    )
    with patch("app.api.agents.get_supabase", return_value=fake):
        row = TestClient(app).get("/agents/overview").json()[0]
    assert row["daily_budget_usd"] is None
    assert row["budget_source"] is None
    assert row["allowed"] is True


def test_a_reviewer_can_read_the_overview(make_fake_supabase, fake_query):
    as_actor(REVIEWER)
    fake = make_fake_supabase(
        agent_events=fake_query(data=[]), agent_policies=fake_query(data=[]),
        agent_kill_switches=fake_query(data=[]), agent_costs=fake_query(data=[]),
    )
    with patch("app.api.agents.get_supabase", return_value=fake):
        assert TestClient(app).get("/agents/overview").status_code == 200


def test_a_reviewer_cannot_change_a_budget(make_fake_supabase, fake_query):
    as_actor(REVIEWER)
    fake = make_fake_supabase(agent_policies=fake_query(data=[{"id": 1}]))
    with patch("app.api.agents.get_supabase", return_value=fake):
        response = TestClient(app).put("/agents/bot/budget", json={"daily_budget_usd": 5})
    assert response.status_code == 403


def test_an_owner_signed_in_can_change_a_budget(make_fake_supabase, fake_query):
    as_actor(OWNER)
    table = fake_query(data=[{"id": 1}])
    fake = make_fake_supabase(agent_policies=table, audit_log=fake_query())
    with patch("app.api.agents.get_supabase", return_value=fake):
        response = TestClient(app).put("/agents/bot/budget", json={"daily_budget_usd": 5})
    assert response.status_code == 200
    assert table.updates[-1]["daily_budget_usd"] == 5