from fastapi import APIRouter, Depends, Header, HTTPException, Response

from app.auth.dependencies import get_current_org
from app.db.supabase_client import get_supabase
from app.ingestion.idempotency import (
    MAX_KEY_LENGTH,
    IdempotencyConflict,
    claim,
    complete,
    release,
)
from app.ingestion.service import process_event
from app.models import IngestEvent

router = APIRouter(tags=["ingestion"])


@router.post("/ingest")
async def ingest_event(
    event: IngestEvent,
    response: Response,
    org: dict = Depends(get_current_org),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """
    Report one agent decision. Send an Idempotency-Key header (for example the
    n8n execution or message id) so a retried call is never recorded twice.
    Returns 200 normally, 429 when the agent is over its daily budget, and
    409 when an identical request is still being processed.
    """
    supabase = get_supabase()

    key = None
    if idempotency_key is not None:
        key = idempotency_key.strip()
        if not key or len(key) > MAX_KEY_LENGTH:
            raise HTTPException(
                status_code=400,
                detail=f"Idempotency-Key must be 1 to {MAX_KEY_LENGTH} characters.",
            )
        try:
            owned, stored = claim(supabase, org["id"], key)
        except IdempotencyConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        if not owned:
            response.headers["Idempotent-Replayed"] = "true"
            response.status_code = 429 if stored.get("status") == "blocked" else 200
            return stored

    try:
        result = process_event(supabase, org, event)
    except Exception:
        if key is not None:
            release(supabase, org["id"], key)
        raise

    if key is not None:
        complete(supabase, org["id"], key, result["event_id"], result)

    response.status_code = 429 if result["status"] == "blocked" else 200
    return result
