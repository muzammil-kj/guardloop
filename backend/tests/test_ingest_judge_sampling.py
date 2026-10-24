from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_org
from app.main import app

ORG = {"id": "org-1"}

APPROVED = {
    "agent_name": "support-bot",
    "event_type": "answer",
    "input_summary": "How do I reset my password?",
    "output_summary": "Use the Forgot password link.",
    "confidence": 0.95,
}


@pytest.fixture
def client():
    app.dependency_overrides[get_current_org] = lambda: ORG
    yield TestClient(app)
    app.dependency_overrides.clear()


def build_fake(make_fake_supabase, fake_query, judge_row=None, judge_settings_query=None):
    return make_fake_supabase(
        agent_policies=fake_query(data=[]),   # no policy: global default threshold
        agent_events=fake_query(),
        escalations=fake_query(),
        agent_costs=fake_query(data=[]),
        judge_settings=judge_settings_query
        or fake_query(data=[judge_row] if judge_row else []),
    )


def post(client, fake, payload=None, key="k"):
    with patch("app.ingestion.routes.get_supabase", return_value=fake), patch(
        "app.judge.sampling.settings", SimpleNamespace(gemini_api_key=key)
    ):
        return client.post("/ingest", json=payload or APPROVED)


JUDGE_ON = {"enabled": True, "sample_rate": 1.0}


def test_an_approved_event_is_queued_for_review_when_the_judge_is_on(
    client, make_fake_supabase, fake_query
):
    fake = build_fake(make_fake_supabase, fake_query, JUDGE_ON)
    response = post(client, fake)

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert fake.tables["agent_events"].inserted["judge_status"] == "pending"


def test_nothing_is_queued_when_the_org_has_not_enabled_the_judge(
    client, make_fake_supabase, fake_query
):
    fake = build_fake(make_fake_supabase, fake_query, {"enabled": False, "sample_rate": 1.0})
    post(client, fake)
    assert "judge_status" not in fake.tables["agent_events"].inserted


def test_nothing_is_queued_when_the_org_has_no_settings_at_all(
    client, make_fake_supabase, fake_query
):
    fake = build_fake(make_fake_supabase, fake_query, judge_row=None)
    post(client, fake)
    assert "judge_status" not in fake.tables["agent_events"].inserted


def test_escalated_events_are_not_queued_a_human_is_already_looking(
    client, make_fake_supabase, fake_query
):
    fake = build_fake(make_fake_supabase, fake_query, JUDGE_ON)
    response = post(client, fake, {**APPROVED, "confidence": 0.1})

    assert response.json()["status"] == "escalated"
    assert "judge_status" not in fake.tables["agent_events"].inserted


def test_events_with_nothing_to_review_are_not_queued(
    client, make_fake_supabase, fake_query
):
    fake = build_fake(make_fake_supabase, fake_query, JUDGE_ON)
    bare = {"agent_name": "support-bot", "event_type": "answer", "confidence": 0.95}
    post(client, fake, bare)
    assert "judge_status" not in fake.tables["agent_events"].inserted


def test_nothing_is_queued_without_a_model_key(client, make_fake_supabase, fake_query):
    fake = build_fake(make_fake_supabase, fake_query, JUDGE_ON)
    post(client, fake, key="")
    assert "judge_status" not in fake.tables["agent_events"].inserted


def test_a_broken_judge_never_breaks_ingestion(client, make_fake_supabase, fake_query):
    class Broken(fake_query):
        def execute(self):
            raise RuntimeError("relation judge_settings does not exist")

    fake = build_fake(make_fake_supabase, fake_query, judge_settings_query=Broken())
    response = post(client, fake)

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert "judge_status" not in fake.tables["agent_events"].inserted
