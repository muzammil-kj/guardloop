from unittest.mock import patch, MagicMock
import pytest

from guardloop_sdk import GuardloopClient, GuardloopError


def make_response(status_code=200, json_data=None, text=""):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.ok = 200 <= status_code < 300
    mock_resp.json.return_value = json_data or {}
    mock_resp.text = text
    return mock_resp


def test_report_returns_approved_result():
    client = GuardloopClient(api_key="gl_live_test123", base_url="https://api.example.com")

    with patch("guardloop_sdk.client.requests.post") as mock_post:
        mock_post.return_value = make_response(
            200, {"event_id": 42, "status": "approved", "reason": None}
        )
        result = client.report(agent_name="test-agent", event_type="classification", confidence=0.95)

    assert result.event_id == 42
    assert result.approved is True
    assert result.escalated is False


def test_report_returns_escalated_result():
    client = GuardloopClient(api_key="gl_live_test123", base_url="https://api.example.com")

    with patch("guardloop_sdk.client.requests.post") as mock_post:
        mock_post.return_value = make_response(
            200, {"event_id": 43, "status": "escalated", "reason": "Confidence too low."}
        )
        result = client.report(agent_name="test-agent", event_type="classification", confidence=0.3)

    assert result.escalated is True
    assert result.reason == "Confidence too low."


def test_invalid_api_key_raises_guardloop_error():
    client = GuardloopClient(api_key="gl_live_bad", base_url="https://api.example.com")

    with patch("guardloop_sdk.client.requests.post") as mock_post:
        mock_post.return_value = make_response(401, text="Unauthorized")
        with pytest.raises(GuardloopError):
            client.report(agent_name="test-agent", event_type="classification")


def test_empty_api_key_raises_value_error():
    with pytest.raises(ValueError):
        GuardloopClient(api_key="")


def test_network_error_raises_guardloop_error():
    import requests as requests_module

    client = GuardloopClient(api_key="gl_live_test123", base_url="https://api.example.com")

    with patch(
        "guardloop_sdk.client.requests.post",
        side_effect=requests_module.ConnectionError("boom"),
    ):
        with pytest.raises(GuardloopError):
            client.report(agent_name="test-agent", event_type="classification")


def test_server_error_raises_guardloop_error():
    client = GuardloopClient(api_key="gl_live_test123", base_url="https://api.example.com")

    with patch("guardloop_sdk.client.requests.post") as mock_post:
        mock_post.return_value = make_response(500, text="Internal Server Error")
        with pytest.raises(GuardloopError):
            client.report(agent_name="test-agent", event_type="classification")