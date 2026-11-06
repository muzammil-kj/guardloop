import logging
from datetime import datetime, timezone

from app.alerts.dispatcher import send_alert

logger = logging.getLogger("guardloop.sla")


def check_overdue(supabase) -> int:
    """Alerts each organization's channels once for every escalation past its deadline."""
    now = datetime.now(timezone.utc).isoformat()
    overdue = (
        supabase.table("escalations")
        .select("id,reason,organization_id")
        .eq("status", "pending")
        .is_("sla_alerted_at", "null")
        .lt("due_at", now)
        .execute().data
    )
    if not overdue:
        return 0

    by_org: dict = {}
    for item in overdue:
        by_org.setdefault(item["organization_id"], []).append(item)

    for organization_id, items in by_org.items():
        channels = (
            supabase.table("alert_channels").select("*")
            .eq("organization_id", organization_id).eq("enabled", True)
            .execute().data
        )
        noun = "escalation is" if len(items) == 1 else "escalations are"
        message = (
            f"Guardloop SLA alert: {len(items)} {noun} past the review deadline. "
            f"Oldest: {items[0]['reason'][:160]}"
        )
        for channel in channels:
            try:
                send_alert(channel["channel_type"], channel["webhook_url"], message)
            except Exception as exc:
                logger.warning("SLA alert to channel %s failed: %s", channel.get("id"), type(exc).__name__)

        # Mark as alerted even if no channel exists, so the queue shows it as overdue
        # without re-alerting every five minutes.
        supabase.table("escalations").update({"sla_alerted_at": now}).in_(
            "id", [item["id"] for item in items]
        ).execute()

    return len(overdue)