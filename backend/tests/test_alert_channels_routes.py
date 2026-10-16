from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.alerts.dispatcher import AlertDeliveryError
from app.auth.dependencies import get_current_org
from app.main import app

DISCORD_URL = "https://discord.com/api/webhooks/123456/abcdefSECRETtoken"
ORG = {"id": "org-1"}


@pytest.fixture
def client():
    app.dependency_overrides[get_current_org] = lambda: ORG
    yield TestClient(app)
    app.dependency_overrides.clear()


def channel_row(**overrides):
    row = {
        "id": 1,
        "organization_id": "org-1",
        "channel_type": "discord",
        "webhook_url": DISCORD_URL,
        "queue_depth_threshold": 10,
        "daily_budget_usd": 5.0,
        "enabled": True,
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    row.update(overrides)
    return row


def test_routes_require_an_api_key():
    unauth = TestClient(app)
    assert unauth.get("/alert-channels").status_code == 401
    assert unauth.post("/alert-channels", json={}).status_code == 401


def test_create_rejects_a_webhook_on_the_wrong_host(client):
    response = client.post("/alert-channels", json={
        "channel_type": "discord",
        "webhook_url": "https://evil.example.com/api/webhooks/1/abc",
    })
    assert response.status_code == 422


def test_create_rejects_an_unknown_channel_type(client):
    response = client.post("/alert-channels", json={
        "channel_type": "email",
        "webhook_url": DISCORD_URL,
    })
    assert response.status_code == 422


def test_create_rejects_nonsense_thresholds(client):
    response = client.post("/alert-channels", json={
        "channel_type": "discord",
        "webhook_url": DISCORD_URL,
        "queue_depth_threshold": 0,
        "daily_budget_usd": -3,
    })
    assert response.status_code == 422


def test_create_never_returns_the_full_webhook_url(client, make_fake_supabase, fake_query):
    fake = make_fake_supabase(alert_channels=fake_query())
    with patch("app.api.alert_channels.get_supabase", return_value=fake):
        response = client.post("/alert-channels", json={
            "channel_type": "discord",
            "webhook_url": DISCORD_URL,
            "queue_depth_threshold": 5,
            "daily_budget_usd": 2.5,
        })

    assert response.status_code == 200
    body = response.json()
    assert body["webhook_hint"] == "discord.com/...oken"
    assert "webhook_url" not in body
    assert "abcdefSECRET" not in response.text
    # The full URL is still what gets stored, scoped to the caller's org.
    assert fake.tables["alert_channels"].inserted["webhook_url"] == DISCORD_URL
    assert fake.tables["alert_channels"].inserted["organization_id"] == "org-1"


def test_list_masks_every_webhook(client, make_fake_supabase, fake_query):
    fake = make_fake_supabase(alert_channels=fake_query(data=[channel_row()]))
    with patch("app.api.alert_channels.get_supabase", return_value=fake):
        response = client.get("/alert-channels")

    assert response.status_code == 200
    assert "abcdefSECRET" not in response.text
    assert response.json()[0]["webhook_hint"] == "discord.com/...oken"


def test_test_send_returns_404_for_a_channel_not_in_your_org(
    client, make_fake_supabase, fake_query
):
    fake = make_fake_supabase(alert_channels=fake_query(data=[]))
    with patch("app.api.alert_channels.get_supabase", return_value=fake):
        response = client.post("/alert-channels/99/test")
    assert response.status_code == 404


def test_test_send_succeeds(client, make_fake_supabase, fake_query):
    fake = make_fake_supabase(alert_channels=fake_query(data=[channel_row()]))
    with patch("app.api.alert_channels.get_supabase", return_value=fake), patch(
        "app.api.alert_channels.send_alert"
    ) as send:
        response = client.post("/alert-channels/1/test")

    assert response.status_code == 200
    assert response.json() == {"status": "sent"}
    send.assert_called_once()


def test_test_send_reports_a_502_without_leaking_the_url(
    client, make_fake_supabase, fake_query
):
    fake = make_fake_supabase(alert_channels=fake_query(data=[channel_row()]))
    with patch("app.api.alert_channels.get_supabase", return_value=fake), patch(
        "app.api.alert_channels.send_alert",
        side_effect=AlertDeliveryError("The webhook returned HTTP 404."),
    ):
        response = client.post("/alert-channels/1/test")

    assert response.status_code == 502
    assert "abcdefSECRET" not in response.text


def test_delete_returns_404_for_a_channel_not_in_your_org(
    client, make_fake_supabase, fake_query
):
    fake = make_fake_supabase(alert_channels=fake_query(data=[]))
    with patch("app.api.alert_channels.get_supabase", return_value=fake):
        response = client.delete("/alert-channels/99")
    assert response.status_code == 404
