from unittest.mock import patch

from app.alerts.dispatcher import AlertDeliveryError
from app.alerts.sla import check_overdue


def test_overdue_reviews_alert_each_channel_once(make_fake_supabase, fake_query):
    escalations = fake_query(data=[{"id": 1, "reason": "Refund request", "organization_id": "org-1"},
                                   {"id": 2, "reason": "Angry customer", "organization_id": "org-1"}])
    channels = fake_query(data=[{"channel_type": "discord", "webhook_url": "https://discord.com/api/webhooks/1/a"}])
    fake = make_fake_supabase(escalations=escalations, alert_channels=channels)
    with patch("app.alerts.sla.send_alert") as send:
        count = check_overdue(fake)
    assert count == 2
    send.assert_called_once()
    assert "2 escalations are past" in send.call_args.args[2]
    assert "Refund request" in send.call_args.args[2]
    assert escalations.updates[-1]["sla_alerted_at"]


def test_nothing_overdue_means_nothing_sent(make_fake_supabase, fake_query):
    fake = make_fake_supabase(escalations=fake_query(data=[]))
    with patch("app.alerts.sla.send_alert") as send:
        assert check_overdue(fake) == 0
    send.assert_not_called()


def test_one_failing_channel_does_not_stop_the_rest(make_fake_supabase, fake_query):
    escalations = fake_query(data=[{"id": 1, "reason": "x", "organization_id": "org-1"}])
    channels = fake_query(data=[{"channel_type": "discord", "webhook_url": "a"},
                                {"channel_type": "slack", "webhook_url": "b"}])
    fake = make_fake_supabase(escalations=escalations, alert_channels=channels)
    with patch("app.alerts.sla.send_alert", side_effect=[AlertDeliveryError("down"), None]) as send:
        check_overdue(fake)
    assert send.call_count == 2


def test_an_org_without_channels_is_still_marked_overdue(make_fake_supabase, fake_query):
    escalations = fake_query(data=[{"id": 1, "reason": "x", "organization_id": "org-1"}])
    fake = make_fake_supabase(escalations=escalations, alert_channels=fake_query(data=[]))
    with patch("app.alerts.sla.send_alert") as send:
        check_overdue(fake)
    send.assert_not_called()
    assert escalations.updates[-1]["sla_alerted_at"]