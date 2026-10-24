from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_org
from app.main import app

ORG = {"id": "org-1"}


def key(value="k"):
    return patch("app.api.judge.settings", SimpleNamespace(gemini_api_key=value))


@pytest.fixture
def client():
    app.dependency_overrides[get_current_org] = lambda: ORG
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_every_judge_route_requires_an_api_key():
    unauth = TestClient(app)
    assert unauth.get("/judge/settings").status_code == 401
    assert unauth.put("/judge/settings", json={"enabled": True, "sample_rate": 0.5}).status_code == 401
    assert unauth.get("/judge/summary").status_code == 401
    assert unauth.get("/judge/reviews").status_code == 401
    assert unauth.post("/judge/run").status_code == 401


# --- settings ---------------------------------------------------------------

def test_settings_default_to_off_and_report_whether_a_key_is_configured(
    client, make_fake_supabase, fake_query
):
    fake = make_fake_supabase(judge_settings=fake_query(data=[]))
    with patch("app.api.judge.get_supabase", return_value=fake), key("k"):
        body = client.get("/judge/settings").json()
    assert body == {"enabled": False, "sample_rate": 0.2, "judge_configured": True}

    with patch("app.api.judge.get_supabase", return_value=fake), key(""):
        assert client.get("/judge/settings").json()["judge_configured"] is False


@pytest.mark.parametrize("rate", [1.5, -0.1])
def test_sample_rate_outside_zero_to_one_is_rejected(client, rate):
    response = client.put("/judge/settings", json={"enabled": True, "sample_rate": rate})
    assert response.status_code == 422


def test_saving_settings_upserts_for_the_callers_org_only(
    client, make_fake_supabase, fake_query
):
    table = fake_query()
    fake = make_fake_supabase(judge_settings=table)
    with patch("app.api.judge.get_supabase", return_value=fake), key():
        response = client.put("/judge/settings", json={"enabled": True, "sample_rate": 0.5})

    assert response.status_code == 200
    assert response.json()["enabled"] is True
    assert table.upserted == {"organization_id": "org-1", "enabled": True, "sample_rate": 0.5}
    assert table.upsert_kwargs["on_conflict"] == "organization_id"


# --- summary and reviews ----------------------------------------------------

def test_summary_combines_stats_pending_count_and_settings(
    client, make_fake_supabase, fake_query
):
    reviewed = [
        {"agent_name": "a", "confidence": 0.9, "judge_verdict": "agree"},
        {"agent_name": "a", "confidence": 0.95, "judge_verdict": "disagree"},
    ]
    fake = make_fake_supabase(
        agent_events=fake_query(data=reviewed, count=3),
        judge_settings=fake_query(data=[{"enabled": True, "sample_rate": 0.4}]),
    )
    with patch("app.api.judge.get_supabase", return_value=fake), key():
        body = client.get("/judge/summary").json()

    assert body["enabled"] is True
    assert body["sample_rate"] == 0.4
    assert body["judge_configured"] is True
    assert body["pending"] == 3
    assert body["totals"]["reviewed"] == 2
    assert body["agents"][0]["disagreement_rate"] == 0.5


def test_reviews_are_returned_for_the_org(client, make_fake_supabase, fake_query):
    rows = [{"id": 1, "agent_name": "a", "judge_verdict": "agree"}]
    fake = make_fake_supabase(agent_events=fake_query(data=rows))
    with patch("app.api.judge.get_supabase", return_value=fake):
        response = client.get("/judge/reviews?limit=5")
    assert response.status_code == 200
    assert response.json() == rows


def test_reviews_limit_is_bounded(client):
    assert client.get("/judge/reviews?limit=0").status_code == 422
    assert client.get("/judge/reviews?limit=500").status_code == 422


# --- manual run -------------------------------------------------------------

def test_manual_run_is_503_when_no_model_key_is_configured(client):
    with key(""):
        response = client.post("/judge/run")
    assert response.status_code == 503


def test_manual_run_reviews_only_the_callers_org_with_a_small_cap(client):
    stats = {"reviewed": 2, "flagged": 1, "skipped": 0, "failed": 0,
             "retry_later": 0, "deferred": 0, "rate_limited": False}
    with key(), patch("app.api.judge.get_supabase"), patch(
        "app.api.judge.review_pending", return_value=stats
    ) as run:
        response = client.post("/judge/run")

    assert response.status_code == 200
    assert response.json() == stats
    assert run.call_args.kwargs["organization_id"] == "org-1"
    assert run.call_args.kwargs["limit"] == 5
