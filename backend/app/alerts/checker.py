from datetime import datetime, timedelta, timezone

from app.alerts.dispatcher import send_alert

DEBOUNCE_WINDOW = timedelta(hours=1)


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _recently_triggered(supabase, channel_id: int, rule_type: str) -> bool:
    result = (
        supabase.table("alert_history")
        .select("last_triggered_at")
        .eq("channel_id", channel_id)
        .eq("rule_type", rule_type)
        .execute()
    )
    if not result.data:
        return False
    last = _parse_timestamp(result.data[0]["last_triggered_at"])
    return datetime.now(timezone.utc) - last < DEBOUNCE_WINDOW


def _record_trigger(supabase, channel_id: int, rule_type: str) -> None:
    supabase.table("alert_history").upsert(
        {
            "channel_id": channel_id,
            "rule_type": rule_type,
            "last_triggered_at": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="channel_id,rule_type",
    ).execute()


def check_queue_depth(supabase, channel: dict) -> None:
    rule_type = "queue_depth"

    pending = (
        supabase.table("escalations")
        .select("*", count="exact")
        .eq("organization_id", channel["organization_id"])
        .eq("status", "pending")
        .execute()
    )
    depth = pending.count or 0
    threshold = channel["queue_depth_threshold"]

    if depth >= threshold and not _recently_triggered(supabase, channel["id"], rule_type):
        send_alert(
            channel["channel_type"],
            channel["webhook_url"],
            f"Guardloop alert: {depth} "
            f"{'escalation is' if depth == 1 else 'escalations are'} "
            f"waiting for human review (your threshold is {threshold}).",
        )
        _record_trigger(supabase, channel["id"], rule_type)


def check_daily_budget(supabase, channel: dict) -> None:
    rule_type = "daily_budget"
    today = datetime.now(timezone.utc).date().isoformat()

    costs = (
        supabase.table("agent_costs")
        .select("total_cost_usd")
        .eq("organization_id", channel["organization_id"])
        .eq("date", today)
        .execute()
    )
    spent = sum(float(row["total_cost_usd"]) for row in costs.data)
    budget = float(channel["daily_budget_usd"])

    if spent >= budget and not _recently_triggered(supabase, channel["id"], rule_type):
        send_alert(
            channel["channel_type"],
            channel["webhook_url"],
            f"Guardloop alert: today's AI agent spend is ${spent:.2f}, "
            f"which has reached your ${budget:.2f} daily budget.",
        )
        _record_trigger(supabase, channel["id"], rule_type)


def run_checks_for_channel(supabase, channel: dict) -> None:
    if not channel.get("enabled", True):
        return
    check_queue_depth(supabase, channel)
    check_daily_budget(supabase, channel)
