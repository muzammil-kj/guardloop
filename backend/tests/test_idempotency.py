from datetime import datetime, timedelta, timezone

import pytest

from app.ingestion.idempotency import IdempotencyConflict, claim, complete, release

ORG = "org-1"
KEY = "n8n-execution-123"


def iso(minutes_ago=0):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()


def scripted(fake_query, script, data=None):
    """Each INSERT pops the next outcome: 'ok' succeeds, 'dup' raises a unique violation."""
    class Scripted(fake_query):
        def __init__(self):
            super().__init__(data=data or [])
            self._script = list(script)

        def execute(self):
            if self._mode == "insert":
                if self._script.pop(0) == "dup":
                    raise Exception('{"code":"23505","message":"duplicate key value"}')
            return super().execute()

    return Scripted()


def test_a_new_key_is_claimed_and_processed(make_fake_supabase, fake_query):
    fake = make_fake_supabase(ingest_idempotency=scripted(fake_query, ["ok"]))
    assert claim(fake, ORG, KEY) == (True, None)


def test_a_finished_duplicate_returns_the_stored_response(make_fake_supabase, fake_query):
    stored = {"event_id": 5, "status": "approved", "reason": None, "pii_redacted": False}
    row = {"id": 1, "response": stored, "claimed_at": iso(1)}
    fake = make_fake_supabase(ingest_idempotency=scripted(fake_query, ["dup"], data=[row]))
    assert claim(fake, ORG, KEY) == (False, stored)


def test_a_duplicate_still_in_flight_is_a_conflict(make_fake_supabase, fake_query):
    row = {"id": 1, "response": None, "claimed_at": iso(0)}
    fake = make_fake_supabase(ingest_idempotency=scripted(fake_query, ["dup"], data=[row]))
    with pytest.raises(IdempotencyConflict):
        claim(fake, ORG, KEY)


def test_an_abandoned_claim_is_taken_over(make_fake_supabase, fake_query):
    row = {"id": 1, "response": None, "claimed_at": iso(minutes_ago=30)}
    fake = make_fake_supabase(ingest_idempotency=scripted(fake_query, ["dup", "ok"], data=[row]))
    assert claim(fake, ORG, KEY) == (True, None)


def test_a_takeover_that_races_another_request_is_a_conflict(make_fake_supabase, fake_query):
    row = {"id": 1, "response": None, "claimed_at": iso(minutes_ago=30)}
    fake = make_fake_supabase(ingest_idempotency=scripted(fake_query, ["dup", "dup"], data=[row]))
    with pytest.raises(IdempotencyConflict):
        claim(fake, ORG, KEY)


def test_complete_stores_the_event_and_response(make_fake_supabase, fake_query):
    table = fake_query()
    fake = make_fake_supabase(ingest_idempotency=table)
    complete(fake, ORG, KEY, 42, {"event_id": 42, "status": "approved"})
    assert table.updates[-1] == {"event_id": 42, "response": {"event_id": 42, "status": "approved"}}


def test_release_runs_for_an_unfinished_claim(make_fake_supabase, fake_query):
    table = fake_query()
    fake = make_fake_supabase(ingest_idempotency=table)
    release(fake, ORG, KEY)
    assert table._mode == "delete"