from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app import ratelimit
from app.ratelimit import RateLimiter, enforce_ingest_limits


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_a_burst_up_to_the_limit_is_allowed_then_refused():
    limiter = RateLimiter(clock=FakeClock())
    assert [limiter.hit("k", 3) for _ in range(3)] == [0.0, 0.0, 0.0]
    assert limiter.hit("k", 3) > 0


def test_refused_requests_say_how_long_to_wait():
    clock = FakeClock()
    limiter = RateLimiter(clock=clock)  # 60 per minute = one per second
    for _ in range(60):
        limiter.hit("k", 60)
    assert limiter.hit("k", 60) == pytest.approx(1.0)


def test_tokens_refill_over_time():
    clock = FakeClock()
    limiter = RateLimiter(clock=clock)
    for _ in range(60):
        limiter.hit("k", 60)
    assert limiter.hit("k", 60) > 0
    clock.now += 1.0
    assert limiter.hit("k", 60) == 0.0


def test_different_keys_do_not_share_a_budget():
    limiter = RateLimiter(clock=FakeClock())
    for _ in range(2):
        limiter.hit("org:a", 2)
    assert limiter.hit("org:a", 2) > 0
    assert limiter.hit("org:b", 2) == 0.0


def test_enforce_raises_429_with_retry_after_for_an_exhausted_organization():
    limiter = RateLimiter(clock=FakeClock())
    with patch.object(ratelimit, "ENABLED", True), \
         patch.object(ratelimit, "ORG_PER_MINUTE", 1), \
         patch.object(ratelimit, "AGENT_PER_MINUTE", 100), \
         patch.object(ratelimit, "limiter", limiter):
        enforce_ingest_limits("org-1", "bot")
        with pytest.raises(HTTPException) as exc:
            enforce_ingest_limits("org-1", "bot")
    assert exc.value.status_code == 429
    assert exc.value.headers["Retry-After"] == "60"


def test_enforce_raises_429_for_an_exhausted_agent_even_when_the_org_has_room():
    limiter = RateLimiter(clock=FakeClock())
    with patch.object(ratelimit, "ENABLED", True), \
         patch.object(ratelimit, "ORG_PER_MINUTE", 100), \
         patch.object(ratelimit, "AGENT_PER_MINUTE", 1), \
         patch.object(ratelimit, "limiter", limiter):
        enforce_ingest_limits("org-1", "loop-bot")
        with pytest.raises(HTTPException) as exc:
            enforce_ingest_limits("org-1", "loop-bot")
        enforce_ingest_limits("org-1", "other-bot")  # a different agent is unaffected
    assert "loop-bot" in exc.value.detail


def test_disabled_limits_never_refuse():
    limiter = RateLimiter(clock=FakeClock())
    with patch.object(ratelimit, "ENABLED", False), \
         patch.object(ratelimit, "ORG_PER_MINUTE", 1), \
         patch.object(ratelimit, "limiter", limiter):
        for _ in range(10):
            enforce_ingest_limits("org-1", "bot")