from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.auth.actors import get_actor
from app.judge.gemini import JudgeResult
from app.judge.reviewer import review_pending
from app.main import app
from tests.test_ingest_phase7 import OK_BUDGET, tables  # noqa: F401 reuse the ingest fakes

ACTOR = {"id": "org-1", "actor_name": "Sara", "actor_type": "user", "actor_role": "reviewer"}


@pytest.fixture(autouse=True)
def clear():
    yield
    app.dependency_overrides.clear()


def test_calibration_route_reads_only_judge_escalations(make_fake_supabase, fake_query):
    app.dependency_overrides[get_actor] = lambda: ACTOR
    rows = [{"status": "rejected", "agent_events": {"agent_name": "bot"}}]
    table = fake_query(data=rows)
    with patch("app.api.quality.get_supabase", return_value=make_fake_supabase(escalations=table)):
        response = TestClient(app).get("/quality/calibration")
    assert response.status_code == 200
    assert response.json()["flags_confirmed"] == 1


def test_versions_route_returns_a_list(make_fake_supabase, fake_query):
    app.dependency_overrides[get_actor] = lambda: ACTOR
    rows = [{"agent_name": "bot", "agent_version": "v1", "status": "approved",
             "judge_verdict": None, "created_at": "2026-10-01"}]
    with patch("app.api.quality.get_supabase",
               return_value=make_fake_supabase(agent_events=fake_query(data=rows))):
        response = TestClient(app).get("/quality/versions")
    assert response.status_code == 200
    assert response.json()[0]["agent_version"] == "v1"


def test_quality_routes_require_sign_in():
    unauth = TestClient(app)
    assert unauth.get("/quality/calibration").status_code == 401
    assert unauth.get("/quality/versions").status_code == 401


def test_a_judge_flag_is_tagged_as_coming_from_the_judge(make_fake_supabase, fake_query):
    escalations = fake_query(data=[])
    events = fake_query(data=[{"id": 7, "organization_id": "org-1", "input_summary": "x",
                               "output_summary": "y", "agent_name": "bot", "event_type": "answer"}])
    fake = make_fake_supabase(agent_events=events, escalations=escalations)
    result = review_pending(fake, organization_id="org-1", limit=5,
                            judge=lambda row: JudgeResult("disagree", 0.1, "wrong"))
    assert result["flagged"] == 1
    assert escalations.inserted["source"] == "judge"


def test_an_agent_version_is_stored_on_the_event(tables):  # noqa: F811
    from app.auth.dependencies import get_current_org
    app.dependency_overrides[get_current_org] = lambda: {"id": "org-1"}
    body = {"agent_name": "bot", "event_type": "answer", "confidence": 0.95,
            "input_summary": "hi", "agent_version": "  prompt-v3  "}
    with patch("app.ingestion.routes.get_supabase", return_value=tables), \
         patch("app.ingestion.service.budget_status", return_value=OK_BUDGET):
        response = TestClient(app).post("/ingest", json=body)
    assert response.status_code == 200
    assert tables.tables["agent_events"].inserted["agent_version"] == "prompt-v3"


def test_a_blank_version_is_stored_as_none(tables):  # noqa: F811
    from app.auth.dependencies import get_current_org
    app.dependency_overrides[get_current_org] = lambda: {"id": "org-1"}
    with patch("app.ingestion.routes.get_supabase", return_value=tables), \
         patch("app.ingestion.service.budget_status", return_value=OK_BUDGET):
        TestClient(app).post("/ingest", json={"agent_name": "bot", "event_type": "answer",
                                              "confidence": 0.95, "agent_version": "   "})
    assert tables.tables["agent_events"].inserted["agent_version"] is None


def test_an_overlong_version_is_rejected():
    from app.auth.dependencies import get_current_org
    app.dependency_overrides[get_current_org] = lambda: {"id": "org-1"}
    response = TestClient(app).post("/ingest", json={"agent_name": "bot", "event_type": "answer",
                                                     "agent_version": "x" * 65})
    assert response.status_code == 422