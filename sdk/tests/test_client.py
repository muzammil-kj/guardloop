from unittest.mock import MagicMock, patch

import pytest
import requests

from guardloop_sdk import GuardloopClient, GuardloopError

BASE = "https://api.example.com"


def response(status=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status
    resp.ok = 200 <= status < 300
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


def client():
    return GuardloopClient(api_key="gl_live_test123", base_url=BASE)


def test_report_returns_an_approved_result():
    with patch("guardloop_sdk.client.requests.request",
               return_value=response(200, {"event_id": 42, "status": "approved", "reason": None})):
        result = client().report(agent_name="bot", event_type="classification", confidence=0.95)
    assert result.approved and not result.escalated and not result.blocked


def test_report_returns_an_escalated_result():
    with patch("guardloop_sdk.client.requests.request",
               return_value=response(200, {"event_id": 43, "status": "escalated", "reason": "Low confidence."})):
        result = client().report(agent_name="bot", event_type="classification", confidence=0.3)
    assert result.escalated and result.reason == "Low confidence."


def test_invalid_api_key_raises():
    with patch("guardloop_sdk.client.requests.request", return_value=response(401)):
        with pytest.raises(GuardloopError):
            client().report(agent_name="bot", event_type="classification")


def test_empty_api_key_raises_value_error():
    with pytest.raises(ValueError):
        GuardloopClient(api_key="")


def test_network_failure_raises_without_leaking_details():
    boom = requests.ConnectionError("secret-internal-host unreachable")
    with patch("guardloop_sdk.client.requests.request", side_effect=boom):
        with pytest.raises(GuardloopError) as exc:
            client().report(agent_name="bot", event_type="classification")
    assert "secret-internal-host" not in str(exc.value)


def test_server_error_raises():
    with patch("guardloop_sdk.client.requests.request", return_value=response(500)):
        with pytest.raises(GuardloopError):
            client().report(agent_name="bot", event_type="classification")


def test_idempotency_key_is_sent_as_a_header():
    with patch("guardloop_sdk.client.requests.request",
               return_value=response(200, {"event_id": 1, "status": "approved"})) as request:
        client().report(agent_name="bot", event_type="x", idempotency_key="exec-99")
    assert request.call_args.kwargs["headers"]["Idempotency-Key"] == "exec-99"


def test_no_idempotency_header_when_no_key_given():
    with patch("guardloop_sdk.client.requests.request",
               return_value=response(200, {"event_id": 1, "status": "approved"})) as request:
        client().report(agent_name="bot", event_type="x")
    assert "Idempotency-Key" not in request.call_args.kwargs["headers"]


def test_a_budget_block_is_a_result_not_an_exception():
    body = {"event_id": 5, "status": "blocked", "reason": "Daily budget reached."}
    with patch("guardloop_sdk.client.requests.request", return_value=response(429, body)):
        result = client().report(agent_name="bot", event_type="x")
    assert result.blocked is True
    assert result.reason == "Daily budget reached."


def test_a_conflict_raises_with_a_retry_hint():
    with patch("guardloop_sdk.client.requests.request", return_value=response(409)):
        with pytest.raises(GuardloopError) as exc:
            client().report(agent_name="bot", event_type="x", idempotency_key="k")
    assert "retry" in str(exc.value).lower()


def test_can_act_returns_the_permission():
    body = {"agent_name": "bot", "allowed": False, "daily_budget_usd": 5.0,
            "spent_today_usd": 6.0, "remaining_usd": 0.0}
    with patch("guardloop_sdk.client.requests.request", return_value=response(200, body)):
        permission = client().can_act("bot")
    assert permission.allowed is False
    assert permission.spent_today_usd == 6.0


def test_can_act_encodes_the_agent_name_in_the_url():
    with patch("guardloop_sdk.client.requests.request",
               return_value=response(200, {"agent_name": "a b/c", "allowed": True,
                                           "spent_today_usd": 0.0})) as request:
        client().can_act("a b/c")
    assert "/agents/a%20b%2Fc/permission" in request.call_args.args[1]


def test_can_act_raises_on_bad_key():
    with patch("guardloop_sdk.client.requests.request", return_value=response(401)):
        with pytest.raises(GuardloopError):
            client().can_act("bot")