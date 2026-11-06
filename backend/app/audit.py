import logging

logger = logging.getLogger("guardloop.audit")


def record_audit(supabase, actor: dict, action: str, target_type=None, target_id=None, detail=None) -> None:
    """
    Records a human or administrative action. Best-effort by design: a failed
    audit write is logged and never blocks the action itself. Stricter
    (fail-closed) auditing is on the roadmap for compliance customers.
    """
    try:
        supabase.table("audit_log").insert({
            "organization_id": actor["id"],
            "actor_name": str(actor.get("actor_name") or "API key")[:200],
            "actor_type": actor.get("actor_type", "api_key"),
            "action": action,
            "target_type": target_type,
            "target_id": None if target_id is None else str(target_id),
            "detail": detail or {},
        }).execute()
    except Exception as exc:
        logger.warning("Audit write failed for %s: %s", action, type(exc).__name__)