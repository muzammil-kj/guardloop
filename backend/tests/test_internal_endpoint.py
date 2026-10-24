from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
SECRET = "cron-secret-for-tests"


def configured(secret=SECRET, gemini_key="gemini-key"):
    return patch(
        "app.api.internal.settings",
        SimpleNamespace(internal_cron_secret=secret, gemini_api_key=gemini_key),
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


# --- /internal/run-judge ------------------------------------------------------

JUDGE_STATS = {"reviewed": 4, "flagged": 1, "skipped": 0, "failed": 0,
               "retry_later": 0, "deferred": 0, "rate_limited": False}


def test_run_judge_is_503_when_no_cron_secret_is_configured():
    with configured(secret=""):
        response = client.post("/internal/run-judge", headers={"x-internal-secret": "x"})
    assert response.status_code == 503


def test_run_judge_rejects_a_missing_or_wrong_secret():
    with configured():
        assert client.post("/internal/run-judge").status_code == 401
        assert client.post(
            "/internal/run-judge", headers={"x-internal-secret": "wrong"}
        ).status_code == 401


def test_run_judge_is_503_when_the_judge_has_no_model_key():
    with configured(gemini_key=""):
        response = client.post("/internal/run-judge", headers={"x-internal-secret": SECRET})
    assert response.status_code == 503


def test_run_judge_reviews_across_all_orgs_within_its_budget():
    with configured(), patch("app.api.internal.get_supabase"), patch(
        "app.api.internal.review_pending", return_value=JUDGE_STATS
    ) as run:
        response = client.post("/internal/run-judge", headers={"x-internal-secret": SECRET})

    assert response.status_code == 200
    assert response.json() == JUDGE_STATS
    assert run.call_args.kwargs["organization_id"] is None
    assert run.call_args.kwargs["limit"] == 20
    assert run.call_args.kwargs["time_budget_seconds"] == 40
