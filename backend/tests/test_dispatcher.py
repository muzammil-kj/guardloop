from unittest.mock import MagicMock, patch

import pytest
import requests

from app.alerts.dispatcher import (
    AlertDeliveryError,
    mask_webhook_url,
    send_alert,
    send_discord_alert,
    send_slack_alert,
    validate_webhook_url,
)

DISCORD_URL = "https://discord.com/api/webhooks/123456/abcdefSECRETtoken"
SLACK_URL = "https://hooks.slack.com/services/T000/B000/XXXXsecret"


def ok_response():
    resp = MagicMock()
    resp.ok = True
    resp.status_code = 204
    return resp


# --- URL validation (SSRF protection) --------------------------------------

def test_valid_discord_and_slack_urls_pass():
    validate_webhook_url("discord", DISCORD_URL)
    validate_webhook_url("slack", SLACK_URL)


@pytest.mark.parametrize(
    "channel_type,url",
    [
        ("discord", "http://discord.com/api/webhooks/1/abc"),            # not https
        ("discord", "https://evil.example.com/api/webhooks/1/abc"),      # wrong host
        ("discord", "https://discord.com@evil.example.com/api/webhooks/1/a"),  # userinfo trick
        ("discord", "https://localhost/api/webhooks/1/abc"),             # internal host
        ("discord", "https://169.254.169.254/api/webhooks/1/abc"),       # cloud metadata
        ("discord", "https://discord.com/somewhere/else"),               # wrong path
        ("slack", DISCORD_URL),                                          # provider mismatch
        ("discord", SLACK_URL),                                          # provider mismatch
    ],
)
def test_unsafe_or_mismatched_urls_are_rejected(channel_type, url):
    with pytest.raises(ValueError):
        validate_webhook_url(channel_type, url)


def test_unknown_channel_type_is_rejected():
    with pytest.raises(ValueError):
        validate_webhook_url("carrier-pigeon", DISCORD_URL)


# --- Masking ---------------------------------------------------------------

def test_mask_hides_the_secret_part_of_the_url():
    hint = mask_webhook_url(DISCORD_URL)
    assert hint == "discord.com/...oken"
    assert "abcdefSECRET" not in hint
    assert "123456" not in hint


# --- Delivery --------------------------------------------------------------

def test_discord_posts_content_field_without_following_redirects():
    with patch("app.alerts.dispatcher.requests.post", return_value=ok_response()) as post:
        send_discord_alert(DISCORD_URL, "hello")
    _, kwargs = post.call_args
    assert kwargs["json"] == {"content": "hello"}
    assert kwargs["allow_redirects"] is False


def test_slack_posts_text_field():
    with patch("app.alerts.dispatcher.requests.post", return_value=ok_response()) as post:
        send_slack_alert(SLACK_URL, "hello")
    assert post.call_args.kwargs["json"] == {"text": "hello"}


def test_send_alert_routes_by_channel_type():
    with patch("app.alerts.dispatcher.requests.post", return_value=ok_response()) as post:
        send_alert("discord", DISCORD_URL, "hi")
        send_alert("slack", SLACK_URL, "hi")
    assert post.call_count == 2


def test_send_alert_rejects_unknown_channel_type():
    with pytest.raises(ValueError):
        send_alert("carrier-pigeon", DISCORD_URL, "hi")


def test_non_2xx_response_raises_delivery_error():
    bad = MagicMock()
    bad.ok = False
    bad.status_code = 404
    with patch("app.alerts.dispatcher.requests.post", return_value=bad):
        with pytest.raises(AlertDeliveryError) as exc:
            send_discord_alert(DISCORD_URL, "hi")
    assert "404" in str(exc.value)


def test_network_error_raises_delivery_error_without_leaking_the_url():
    boom = requests.ConnectionError(f"connection to {DISCORD_URL} failed")
    with patch("app.alerts.dispatcher.requests.post", side_effect=boom):
        with pytest.raises(AlertDeliveryError) as exc:
            send_discord_alert(DISCORD_URL, "hi")
    assert "abcdefSECRET" not in str(exc.value)
