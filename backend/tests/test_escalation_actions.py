from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.auth.actors import get_actor
from app.main import app

REVIEWER = {"id": "org-1", "actor_name": "Sara Ali", "actor_type": "user", "actor_role": "reviewer"}
VIEWER = {"id": "org-1", "actor_name": "Tom", "actor_type": "user", "actor_role": "viewer"}
SERVICE = {"id": "org-1", "actor_name": "API key", "actor_type": "api_key", "actor_role": "owner"}


def as_actor(actor):
    app.dependency_overrides[get_actor] = lambda: actor


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


def test_a_reviewer_is_recorded_by_name_not_the_body(client, make_fake_supabase, fake_query):
    as_actor(REVIEWER)
    table = fake_query(data=[{"id": 4, "status": "approved"}])
    audit = fake_query()
    fake = make_fake_supabase(escalations=table, audit_log=audit)
    with patch("app.api.escalations.get_supabase", return_value=fake):
        response = client.patch("/escalations/4/resolve",
                                json={"status": "approved", "resolved_by": "demo@guardloop.ai"})
    assert response.status_code == 200
    assert table.updates[-1]["resolved_by"] == "Sara Ali"
    assert audit.inserted["actor_name"] == "Sara Ali"
    assert audit.inserted["action"] == "escalation.approved"

def test_a_service_key_still_records_the_name_it_sends(client, make_fake_supabase, fake_query):
    as_actor(SERVICE)
    table = fake_query(data=[{"id": 4}])
    fake = make_fake_supabase(escalations=table, audit_log=fake_query())
    with patch("app.api.escalations.get_supabase", return_value=fake):
        client.patch("/escalations/4/resolve", json={"status": "rejected", "resolved_by": "ops-bot"})
    assert table.updates[-1]["resolved_by"] == "ops-bot"


def test_a_viewer_cannot_resolve(client, make_fake_supabase, fake_query):
    as_actor(VIEWER)
    fake = make_fake_supabase(escalations=fake_query(data=[{"id": 4}]))
    with patch("app.api.escalations.get_supabase", return_value=fake):
        response = client.patch("/escalations/4/resolve", json={"status": "approved", "resolved_by": "x"})
    assert response.status_code == 403


def test_assigning_to_a_non_member_is_refused(client, make_fake_supabase, fake_query):
    as_actor(REVIEWER)
    fake = make_fake_supabase(memberships=fake_query(data=[]), escalations=fake_query(data=[{"id": 4}]))
    with patch("app.api.escalations.get_supabase", return_value=fake):
        response = client.patch("/escalations/4/assign", json={"assignee_email": "stranger@example.com"})
    assert response.status_code == 400


def test_assigning_to_a_member_is_saved_in_lowercase(client, make_fake_supabase, fake_query):
    as_actor(REVIEWER)
    table = fake_query(data=[{"id": 4, "assigned_to": "ali@example.com"}])
    fake = make_fake_supabase(memberships=fake_query(data=[{"id": 2}]), escalations=table, audit_log=fake_query())
    with patch("app.api.escalations.get_supabase", return_value=fake):
        response = client.patch("/escalations/4/assign", json={"assignee_email": "Ali@Example.com"})
    assert response.status_code == 200
    assert table.updates[-1] == {"assigned_to": "ali@example.com"}


def test_unassigning_clears_the_owner(client, make_fake_supabase, fake_query):
    as_actor(REVIEWER)
    table = fake_query(data=[{"id": 4}])
    fake = make_fake_supabase(escalations=table, audit_log=fake_query())
    with patch("app.api.escalations.get_supabase", return_value=fake):
        client.patch("/escalations/4/assign", json={"assignee_email": None})
    assert table.updates[-1] == {"assigned_to": None}


def test_the_dashboard_can_read_escalations_as_a_viewer(client, make_fake_supabase, fake_query):
    as_actor(VIEWER)
    fake = make_fake_supabase(escalations=fake_query(data=[{"id": 1}]))
    with patch("app.api.escalations.get_supabase", return_value=fake):
        assert client.get("/escalations?status=pending").status_code == 200


def test_settings_stay_api_key_only(client):
    """A reviewer's session must not be able to change policies."""
    as_actor(REVIEWER)
    response = TestClient(app).put("/policies/default",
                                   json={"confidence_threshold": 0.1, "hard_escalate_event_types": []})
    assert response.status_code == 401