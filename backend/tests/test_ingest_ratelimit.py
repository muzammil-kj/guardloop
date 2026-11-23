from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app import ratelimit
from app.auth.dependencies import get_current_org
from app.main import app
from app.ratelimit import RateLimiter
from tests.test_ratelimit import FakeClock

BODY = {"agent_name": "bot", "event_type": "answer", "confidence": 0.9}
PROCESSED = {"event_id": 1, "status": "approved", "reason": None, "pii_redacted": False}


@pytest.fixture
def client():
    app.dependency_overrides[get_current_org] = lambda: {"id": "org-rl"}
    yield TestClient(app)
    app.dependency_overrides.clear()


def post(client):
    with patch("app.ingestion.routes.get_supabase", return_value=MagicMock()), \
         patch("app.ingestion.routes.process_event", return_value=PROCESSED):
        return client.post("/ingest", json=BODY)


def test_requests_over_the_organization_limit_get_429_with_retry_after(client):
    with patch.object(ratelimit, "ENABLED", True), \
         patch.object(ratelimit, "ORG_PER_MINUTE", 2), \
         patch.object(ratelimit, "AGENT_PER_MINUTE", 100), \
         patch.object(ratelimit, "limiter", RateLimiter(clock=FakeClock())):
        statuses = [post(client).status_code for _ in range(3)]
        third = post(client)
    assert statuses == [200, 200, 429]
    assert third.status_code == 429
    assert "Retry-After" in third.headers
    assert "organization" in third.json()["detail"]


def test_a_rate_limit_is_not_reported_as_a_budget_block(client):
    with patch.object(ratelimit, "ENABLED", True), \
         patch.object(ratelimit, "ORG_PER_MINUTE", 1), \
         patch.object(ratelimit, "AGENT_PER_MINUTE", 100), \
         patch.object(ratelimit, "limiter", RateLimiter(clock=FakeClock())):
        post(client)
        response = post(client)
    assert "status" not in response.json()  # budget blocks carry status "blocked"; rate limits do not


def test_a_refused_request_does_not_create_an_event(client):
    fake_process = MagicMock(return_value=PROCESSED)
    with patch.object(ratelimit, "ENABLED", True), \
         patch.object(ratelimit, "ORG_PER_MINUTE", 1), \
         patch.object(ratelimit, "AGENT_PER_MINUTE", 100), \
         patch.object(ratelimit, "limiter", RateLimiter(clock=FakeClock())), \
         patch("app.ingestion.routes.get_supabase", return_value=MagicMock()), \
         patch("app.ingestion.routes.process_event", fake_process):
        client.post("/ingest", json=BODY)
        client.post("/ingest", json=BODY)
    assert fake_process.call_count == 1