from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.auth.actors import get_actor
from app.exports.csv_export import to_csv
from app.main import app

OWNER = {"id": "org-1", "actor_name": "Owner", "actor_type": "user", "actor_role": "owner"}
REVIEWER = {"id": "org-1", "actor_name": "Sara", "actor_type": "user", "actor_role": "reviewer"}


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def as_actor(actor):
    app.dependency_overrides[get_actor] = lambda: actor


@pytest.fixture
def client():
    return TestClient(app)


def test_only_an_owner_can_invite(client, make_fake_supabase, fake_query):
    as_actor(REVIEWER)
    with patch("app.api.members.get_supabase", return_value=make_fake_supabase(memberships=fake_query())):
        response = client.post("/members", json={"email": "x@example.com", "role": "reviewer"})
    assert response.status_code == 403


def test_an_owner_invites_with_a_lowercase_email(client, make_fake_supabase, fake_query):
    as_actor(OWNER)
    table = fake_query(data=[])
    table._insert_data = [{"id": 5, "email": "ali@example.com", "role": "reviewer",
                           "display_name": None, "user_id": None, "created_at": "2026-10-01T00:00:00Z"}]
    fake = make_fake_supabase(memberships=table, audit_log=fake_query())
    with patch("app.api.members.get_supabase", return_value=fake):
        response = client.post("/members", json={"email": "  Ali@Example.com ", "role": "reviewer"})
    assert response.status_code == 200
    assert table.inserted["email"] == "ali@example.com"


def test_a_duplicate_invitation_is_a_conflict(client, make_fake_supabase, fake_query):
    as_actor(OWNER)
    fake = make_fake_supabase(memberships=fake_query(data=[{"id": 1}]))
    with patch("app.api.members.get_supabase", return_value=fake):
        response = client.post("/members", json={"email": "ali@example.com", "role": "viewer"})
    assert response.status_code == 409


def test_an_invalid_role_is_rejected(client):
    as_actor(OWNER)
    assert client.post("/members", json={"email": "a@b.co", "role": "superuser"}).status_code == 422


def test_the_last_owner_cannot_be_removed(client, make_fake_supabase, fake_query):
    as_actor(OWNER)
    memberships = fake_query(data=[{"id": 1, "role": "owner", "email": "owner@example.com"}])
    fake = make_fake_supabase(memberships=memberships, audit_log=fake_query())
    with patch("app.api.members.get_supabase", return_value=fake):
        response = client.delete("/members/1")
    assert response.status_code == 400


def test_removing_a_reviewer_is_audited(client, make_fake_supabase, fake_query):
    as_actor(OWNER)
    memberships = fake_query(data=[{"id": 2, "role": "reviewer", "email": "ali@example.com"}])
    audit = fake_query()
    fake = make_fake_supabase(memberships=memberships, audit_log=audit)
    with patch("app.api.members.get_supabase", return_value=fake):
        response = client.delete("/members/2")
    assert response.status_code == 200
    assert audit.inserted["action"] == "member.removed"


def test_only_an_owner_can_read_the_audit_log(client):
    as_actor(REVIEWER)
    assert client.get("/audit").status_code == 403
    assert client.get("/exports/audit.csv").status_code == 403


def test_a_reviewer_can_export_decisions(client, make_fake_supabase, fake_query):
    as_actor(REVIEWER)
    rows = [{"id": 1, "created_at": "2026-10-01", "agent_name": "bot", "event_type": "x", "status": "approved",
             "confidence": 0.9, "cost_usd": 0, "pii_redacted": False, "judge_verdict": None,
             "input_summary": "hello", "output_summary": "=HYPERLINK(\"http://evil\")"}]
    with patch("app.api.audit.get_supabase", return_value=make_fake_supabase(agent_events=fake_query(data=rows))):
        response = client.get("/exports/decisions.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    assert "'=HYPERLINK" in response.text


def test_csv_neutralises_formulas_and_quotes_commas():
    body = to_csv([{"a": "=2+2", "b": "one, two", "c": "say \"hi\"", "d": None}], ["a", "b", "c", "d"])
    lines = body.splitlines()
    assert lines[0] == "a,b,c,d"
    assert lines[1] == "'=2+2,\"one, two\",\"say \"\"hi\"\"\","


def test_csv_serialises_json_detail_cells():
    body = to_csv([{"detail": {"limit": 5}}], ["detail"])
    assert '"{""limit"": 5}"' in body


def test_a_failed_audit_write_never_blocks_the_action(make_fake_supabase, fake_query):
    from app.audit import record_audit

    class Broken(fake_query):
        def execute(self):
            raise RuntimeError("database unavailable")

    record_audit(make_fake_supabase(audit_log=Broken()), OWNER, "member.added")  # must not raise