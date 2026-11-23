from unittest.mock import MagicMock, patch

import pytest

from guardloop_sdk import GuardloopClient, GuardloopError


def response(status, body=None, headers=None):
    resp = MagicMock()
    resp.status_code = status
    resp.ok = 200 <= status < 300
    resp.json.return_value = body or {}
    resp.headers = headers or {}
    return resp


def client():
    return GuardloopClient(api_key="gl_live_test123", base_url="https://api.example.com")


def test_a_rate_limit_raises_with_the_retry_time():
    with patch("guardloop_sdk.client.requests.request",
               return_value=response(429, {"detail": "Rate limit exceeded"}, {"Retry-After": "7"})):
        with pytest.raises(GuardloopError) as exc:
            client().report(agent_name="bot", event_type="x")
    assert "7 seconds" in str(exc.value)


def test_a_budget_block_is_still_returned_as_a_result():
    body = {"event_id": 3, "status": "blocked", "reason": "Daily budget reached."}
    with patch("guardloop_sdk.client.requests.request", return_value=response(429, body)):
        result = client().report(agent_name="bot", event_type="x")
    assert result.blocked is True