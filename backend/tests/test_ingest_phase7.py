from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_org
from app.ingestion.idempotency import IdempotencyConflict
from app.main import app

ORG = {"id": "org-1"}
OK_BUDGET = {"agent_name": "support-bot", "allowed": True, "daily_budget_usd": None,
             "spent_today_usd": 0.0, "remaining_usd": None}
BASE = {
    "agent_name": "support-bot",
    "event_type": "answer",
    "input_summary": "How do I reset my password?",
    "output_summary": "Use the Forgot password link.",
    "confidence": 0.95,
}


@pytest.fixture
def client():
    app.dependency_overrides[get_current_org] = lambda: ORG
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture
def tables(make_fake_supabase, fake_query):
    return make_fake_supabase(
        agent_policies=fake_query(data=[]),
        agent_events=fake_query(),
        escalations=fake_query(),
        agent_costs=fake_query(data=[]),
        judge_settings=fake_query(data=[]),
        ingest_idempotency=fake_query(data=[]),
    )


def post(client, fake, payload=None, headers=None):
    with patch("app.ingestion.routes.get_supabase", return_value=fake):
        return client.post("/ingest", json=payload or BASE, headers=headers or {})


# --- PII redaction ----------------------------------------------------------

def test_personal_data_is_masked_before_it_is_stored(client, tables):
    payload = {**BASE, "input_summary": "Email jane@example.com about card 4111 1111 1111 1111"}
    response = post(client, tables, payload)

    stored = tables.tables["agent_events"].inserted
    assert "jane@example.com" not in stored["input_summary"]
    assert "[EMAIL]" in stored["input_summary"] and "[CARD]" in stored["input_summary"]
    assert stored["pii_redacted"] is True
    assert response.json()["pii_redacted"] is True


def test_personal_data_in_an_escalation_reason_is_masked(client, tables):
    payload = {**BASE, "force_escalate": True,
               "escalate_reason": "Customer jane@example.com asked for a refund"}
    post(client, tables, payload)
    assert "jane@example.com" not in tables.tables["escalations"].inserted["reason"]


def test_clean_text_is_not_marked_as_redacted(client, tables):
    response = post(client, tables)
    assert response.json()["pii_redacted"] is False
    assert tables.tables["agent_events"].inserted["pii_redacted"] is False


# --- spend caps -------------------------------------------------------------

def test_an_agent_over_budget_is_blocked_with_429(client, tables):
    over = {"agent_name": "support-bot", "allowed": False, "daily_budget_usd": 5.0,
            "spent_today_usd": 6.0, "remaining_usd": 0.0}
    with patch("app.ingestion.service.budget_status", return_value=over):
        response = post(client, tables)

    assert response.status_code == 429
    body = response.json()
    assert body["status"] == "blocked"
    assert "Stop acting" in body["reason"]


def test_a_blocked_event_is_recorded_for_audit_but_costs_nothing(client, tables):
    over = {"agent_name": "support-bot", "allowed": False, "daily_budget_usd": 5.0,
            "spent_today_usd": 6.0, "remaining_usd": 0.0}
    payload = {**BASE, "cost_usd": 0.5}
    with patch("app.ingestion.service.budget_status", return_value=over):
        post(client, tables, payload)

    recorded = tables.tables["agent_events"].inserted
    assert recorded["status"] == "blocked"
    assert recorded["cost_usd"] == 0.0
    assert tables.tables["agent_costs"].inserted is None
    assert tables.tables["escalations"].inserted is None


def test_an_agent_under_budget_is_processed_normally(client, tables):
    with patch("app.ingestion.service.budget_status", return_value=OK_BUDGET):
        response = post(client, tables)
    assert response.status_code == 200
    assert response.json()["status"] == "approved"


# --- idempotency ------------------------------------------------------------

def test_a_repeated_key_returns_the_stored_response_without_a_new_event(client, tables):
    stored = {"event_id": 7, "status": "approved", "reason": None, "pii_redacted": False}
    with patch("app.ingestion.routes.claim", return_value=(False, stored)):
        response = post(client, tables, headers={"Idempotency-Key": "exec-1"})

    assert response.status_code == 200
    assert response.json() == stored
    assert response.headers["idempotent-replayed"] == "true"
    assert tables.tables["agent_events"].inserted is None


def test_a_repeated_blocked_key_stays_blocked(client, tables):
    stored = {"event_id": 8, "status": "blocked", "reason": "over budget", "pii_redacted": False}
    with patch("app.ingestion.routes.claim", return_value=(False, stored)):
        response = post(client, tables, headers={"Idempotency-Key": "exec-2"})
    assert response.status_code == 429


def test_a_new_key_is_stored_against_the_event(client, tables):
    with patch("app.ingestion.routes.claim", return_value=(True, None)), \
         patch("app.ingestion.routes.complete") as complete, \
         patch("app.ingestion.routes.process_event",
               return_value={"event_id": 9, "status": "approved", "reason": None, "pii_redacted": False}):
        post(client, tables, headers={"Idempotency-Key": "exec-3"})
    args = complete.call_args.args
    assert args[2] == "exec-3" and args[3] == 9


def test_a_failed_attempt_releases_its_key_so_a_retry_can_succeed(client, tables):
    with patch("app.ingestion.routes.claim", return_value=(True, None)), \
         patch("app.ingestion.routes.release") as release, \
         patch("app.ingestion.routes.process_event", side_effect=RuntimeError("db down")):
        response = post(client, tables, headers={"Idempotency-Key": "exec-4"})
    assert response.status_code == 500
    release.assert_called_once()


def test_a_key_still_in_progress_returns_409(client, tables):
    with patch("app.ingestion.routes.claim", side_effect=IdempotencyConflict("busy")):
        response = post(client, tables, headers={"Idempotency-Key": "exec-5"})
    assert response.status_code == 409


def test_an_empty_key_is_rejected(client, tables):
    response = post(client, tables, headers={"Idempotency-Key": "   "})
    assert response.status_code == 400


def test_an_overlong_key_is_rejected(client, tables):
    response = post(client, tables, headers={"Idempotency-Key": "x" * 300})
    assert response.status_code == 400


def test_without_a_key_nothing_idempotent_happens(client, tables):
    with patch("app.ingestion.routes.claim") as claim:
        post(client, tables)
    claim.assert_not_called()