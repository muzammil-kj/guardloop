"""
Makes retries safe. If an agent sends the same Idempotency-Key twice, the second
call receives the first call's stored response and no duplicate event is made.

Flow: claim the key (insert a row). If it already exists:
  - finished earlier  -> return the stored response
  - still running     -> 409, the caller should retry shortly
  - abandoned (older than STALE_CLAIM_AFTER) -> take the key over and process it
"""
from datetime import datetime, timedelta, timezone

MAX_KEY_LENGTH = 255
STALE_CLAIM_AFTER = timedelta(minutes=5)
TABLE = "ingest_idempotency"


class IdempotencyConflict(Exception):
    """An earlier request with this key is still being processed."""


def _is_unique_violation(exc: Exception) -> bool:
    return getattr(exc, "code", None) == "23505" or "23505" in str(exc)


def _insert_claim(supabase, organization_id: str, key: str) -> None:
    supabase.table(TABLE).insert({
        "organization_id": organization_id,
        "idempotency_key": key,
    }).execute()


def _find(supabase, organization_id: str, key: str):
    rows = (
        supabase.table(TABLE).select("*")
        .eq("organization_id", organization_id)
        .eq("idempotency_key", key)
        .execute().data
    )
    return rows[0] if rows else None


def claim(supabase, organization_id: str, key: str) -> tuple[bool, dict | None]:
    """Returns (True, None) if this request must process the event, or
    (False, stored_response) if an earlier request already finished."""
    try:
        _insert_claim(supabase, organization_id, key)
        return True, None
    except Exception as exc:
        if not _is_unique_violation(exc):
            raise

    row = _find(supabase, organization_id, key)
    if row is None:
        raise IdempotencyConflict("Please retry this request shortly.")
    if row.get("response") is not None:
        return False, row["response"]

    claimed_at = datetime.fromisoformat(row["claimed_at"].replace("Z", "+00:00"))
    if datetime.now(timezone.utc) - claimed_at < STALE_CLAIM_AFTER:
        raise IdempotencyConflict(
            "A request with this Idempotency-Key is still being processed. "
            "Retry in a few seconds."
        )

    # The earlier attempt died before finishing. Take the key over.
    supabase.table(TABLE).delete().eq("id", row["id"]).execute()
    try:
        _insert_claim(supabase, organization_id, key)
    except Exception as exc:
        if _is_unique_violation(exc):
            raise IdempotencyConflict("Please retry this request shortly.") from None
        raise
    return True, None


def complete(supabase, organization_id: str, key: str, event_id: int, response: dict) -> None:
    (
        supabase.table(TABLE)
        .update({"event_id": event_id, "response": response})
        .eq("organization_id", organization_id)
        .eq("idempotency_key", key)
        .execute()
    )


def release(supabase, organization_id: str, key: str) -> None:
    """Called when processing failed, so an immediate retry can succeed."""
    (
        supabase.table(TABLE).delete()
        .eq("organization_id", organization_id)
        .eq("idempotency_key", key)
        .is_("response", "null")
        .execute()
    )
