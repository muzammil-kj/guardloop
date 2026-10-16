from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
SECRET = "cron-secret-for-tests"


def configured(secret=SECRET):
    return patch(
        "app.api.internal.settings", SimpleNamespace(internal_cron_secret=secret)
    )


def test_returns_503_when_no_secret_is_configured():
    with configured(""):
        response = client.post(
            "/internal/run-checks", headers={"x-internal-secret": "anything"}
        )
    assert response.status_code == 503


def test_missing_secret_header_returns_401():
    with configured():
        response = client.post("/internal/run-checks")
    assert response.status_code == 401


def test_wrong_secret_returns_401():
    with configured():
        response = client.post(
            "/internal/run-checks", headers={"x-internal-secret": "wrong"}
        )
    assert response.status_code == 401


def test_correct_secret_checks_every_enabled_channel(make_fake_supabase, fake_query):
    channels = [{"id": 1}, {"id": 2}, {"id": 3}]
    fake = make_fake_supabase(alert_channels=fake_query(data=channels))

    with configured(), patch("app.api.internal.get_supabase", return_value=fake), patch(
        "app.api.internal.run_checks_for_channel"
    ) as run:
        response = client.post(
            "/internal/run-checks", headers={"x-internal-secret": SECRET}
        )

    assert response.status_code == 200
    assert response.json() == {"channels_checked": 3, "channels_failed": 0}
    assert run.call_count == 3


def test_one_failing_channel_does_not_stop_the_others(make_fake_supabase, fake_query):
    channels = [{"id": 1}, {"id": 2}, {"id": 3}]
    fake = make_fake_supabase(alert_channels=fake_query(data=channels))

    def flaky(supabase, channel):
        if channel["id"] == 2:
            raise RuntimeError("webhook exploded")

    with configured(), patch("app.api.internal.get_supabase", return_value=fake), patch(
        "app.api.internal.run_checks_for_channel", side_effect=flaky
    ):
        response = client.post(
            "/internal/run-checks", headers={"x-internal-secret": SECRET}
        )

    assert response.status_code == 200
    assert response.json() == {"channels_checked": 2, "channels_failed": 1}
