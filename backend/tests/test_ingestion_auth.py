from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_ingest_without_auth_header_returns_401():
    response = client.post("/ingest", json={
        "agent_name": "test-agent",
        "event_type": "classification",
        "confidence": 0.9,
    })
    assert response.status_code == 401
    assert "Authorization" in response.json()["detail"]


def test_ingest_with_malformed_header_returns_401():
    response = client.post(
        "/ingest",
        json={"agent_name": "test-agent", "event_type": "classification"},
        headers={"Authorization": "NotBearer something"},
    )
    assert response.status_code == 401


def test_ingest_with_unknown_key_returns_401():
    """
    No live Supabase connection needed: we mock the lookup to simulate a
    key that doesn't exist (or was revoked), and confirm the request is
    still correctly rejected.
    """
    mock_result = MagicMock()
    mock_result.data = []

    with patch("app.auth.dependencies.get_supabase") as mock_get_supabase:
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result
        mock_get_supabase.return_value = mock_supabase

        response = client.post(
            "/ingest",
            json={"agent_name": "test-agent", "event_type": "classification"},
            headers={"Authorization": "Bearer gl_live_fake_invalid_key"},
        )

    assert response.status_code == 401
    assert "Invalid or revoked" in response.json()["detail"]