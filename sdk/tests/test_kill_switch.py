from unittest.mock import MagicMock, patch

import pytest

from guardloop_sdk import GuardloopClient, GuardloopError


def response(status, body=None):
    resp = MagicMock()
    resp.status_code = status
    resp.ok = 200 <= status < 300
    resp.json.return_value = body or {}
    resp.headers = {}
    return resp


def client():
    return GuardloopClient(api_key="gl_live_test123", base_url="https://api.example.com")


def test_a_switched_off_agent_raises_a_clear_error():
    with patch("guardloop_sdk.client.requests.request", return_value=response(403)):
        with pytest.raises(GuardloopError) as exc:
            client().report(agent_name="bot", event_type="x")
    assert "switched off" in str(exc.value)


def test_can_act_reports_a_switched_off_agent_as_not_allowed():
    body = {"agent_name": "bot", "allowed": False, "killed": True, "kill_reason": "stop",
            "daily_budget_usd": None, "spent_today_usd": 0.0, "remaining_usd": None}
    with patch("guardloop_sdk.client.requests.request", return_value=response(200, body)):
        assert client().can_act("bot").allowed is False