from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.alerts.checker import run_checks_for_channel

NOW = datetime.now(timezone.utc)


def channel(**overrides):
    base = {
        "id": 7,
        "organization_id": "org-1",
        "channel_type": "discord",
        "webhook_url": "https://discord.com/api/webhooks/1/abc",
        "queue_depth_threshold": 10,
        "daily_budget_usd": 5.0,
        "enabled": True,
    }
    base.update(overrides)
    return base


def build(make_fake_supabase, fake_query, depth=0, history=None, costs=None):
    history_query = fake_query(data=history or [])
    fake = make_fake_supabase(
        escalations=fake_query(count=depth),
        agent_costs=fake_query(data=costs or []),
        alert_history=history_query,
    )
    return fake, history_query


def ago(**kwargs):
    return (NOW - timedelta(**kwargs)).isoformat()


# --- Queue depth -----------------------------------------------------------

def test_no_alert_when_queue_is_below_threshold(make_fake_supabase, fake_query):
    fake, _ = build(make_fake_supabase, fake_query, depth=9)
    with patch("app.alerts.checker.send_alert") as send:
        run_checks_for_channel(fake, channel())
    send.assert_not_called()


def test_alert_fires_when_queue_reaches_threshold(make_fake_supabase, fake_query):
    fake, history = build(make_fake_supabase, fake_query, depth=10)
    with patch("app.alerts.checker.send_alert") as send:
        run_checks_for_channel(fake, channel())

    send.assert_called_once()
    assert "10 escalations" in send.call_args.args[2]
    # The trigger is recorded per channel so it can be debounced.
    assert history.upserted["channel_id"] == 7
    assert history.upserted["rule_type"] == "queue_depth"
    assert history.upsert_kwargs["on_conflict"] == "channel_id,rule_type"


def test_alert_is_suppressed_inside_the_debounce_window(make_fake_supabase, fake_query):
    recent = [{"last_triggered_at": ago(minutes=20)}]
    fake, history = build(make_fake_supabase, fake_query, depth=50, history=recent)
    with patch("app.alerts.checker.send_alert") as send:
        run_checks_for_channel(fake, channel())
    send.assert_not_called()
    assert history.upserted is None


def test_alert_fires_again_after_the_debounce_window(make_fake_supabase, fake_query):
    old = [{"last_triggered_at": ago(hours=2)}]
    fake, _ = build(make_fake_supabase, fake_query, depth=50, history=old)
    with patch("app.alerts.checker.send_alert") as send:
        run_checks_for_channel(fake, channel())
    send.assert_called_once()


def test_z_suffixed_timestamps_are_parsed(make_fake_supabase, fake_query):
    recent = [{"last_triggered_at": ago(minutes=5).replace("+00:00", "Z")}]
    fake, _ = build(make_fake_supabase, fake_query, depth=50, history=recent)
    with patch("app.alerts.checker.send_alert") as send:
        run_checks_for_channel(fake, channel())
    send.assert_not_called()


# --- Daily budget ----------------------------------------------------------

def test_budget_alert_fires_when_spend_reaches_budget(make_fake_supabase, fake_query):
    costs = [{"total_cost_usd": 3.0}, {"total_cost_usd": 2.5}]
    fake, _ = build(make_fake_supabase, fake_query, costs=costs)
    with patch("app.alerts.checker.send_alert") as send:
        run_checks_for_channel(fake, channel(daily_budget_usd=5.0))

    send.assert_called_once()
    assert "$5.50" in send.call_args.args[2]


def test_no_budget_alert_when_under_budget(make_fake_supabase, fake_query):
    fake, _ = build(make_fake_supabase, fake_query, costs=[{"total_cost_usd": 1.0}])
    with patch("app.alerts.checker.send_alert") as send:
        run_checks_for_channel(fake, channel(daily_budget_usd=5.0))
    send.assert_not_called()


def test_numeric_strings_from_the_database_are_handled(make_fake_supabase, fake_query):
    fake, _ = build(
        make_fake_supabase, fake_query, costs=[{"total_cost_usd": "7.250000"}]
    )
    with patch("app.alerts.checker.send_alert") as send:
        run_checks_for_channel(fake, channel(daily_budget_usd="5.00"))
    send.assert_called_once()


# --- Channel behaviour -----------------------------------------------------

def test_disabled_channel_is_skipped_entirely(make_fake_supabase, fake_query):
    fake, _ = build(make_fake_supabase, fake_query, depth=999)
    with patch("app.alerts.checker.send_alert") as send:
        run_checks_for_channel(fake, channel(enabled=False))
    send.assert_not_called()


def test_a_failed_send_is_not_recorded_so_it_retries_next_run(
    make_fake_supabase, fake_query
):
    fake, history = build(make_fake_supabase, fake_query, depth=50)
    with patch("app.alerts.checker.send_alert", side_effect=RuntimeError("down")):
        try:
            run_checks_for_channel(fake, channel())
        except RuntimeError:
            pass
    assert history.upserted is None


def test_the_message_uses_correct_grammar_for_one_escalation(make_fake_supabase, fake_query):
    fake, _ = build(make_fake_supabase, fake_query, depth=1)
    with patch("app.alerts.checker.send_alert") as send:
        run_checks_for_channel(fake, channel(queue_depth_threshold=1))

    message = send.call_args.args[2]
    assert "1 escalation is waiting" in message
    assert "escalations" not in message
