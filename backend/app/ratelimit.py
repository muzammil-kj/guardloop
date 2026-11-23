"""
Per-organization and per-agent rate limits for /ingest.

Token bucket in memory. On Render's free tier there is one instance, so the
limits are exact. They reset when the server restarts, and they would not be
shared between several instances. A shared store (Redis) is needed only if
you later run more than one instance.
"""
import math
import os
import threading
import time

from fastapi import HTTPException

ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() != "false"
ORG_PER_MINUTE = int(os.getenv("INGEST_RATE_PER_ORG_PER_MINUTE", "600"))
AGENT_PER_MINUTE = int(os.getenv("INGEST_RATE_PER_AGENT_PER_MINUTE", "120"))
MAX_TRACKED_KEYS = 10_000


class RateLimiter:
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._buckets: dict = {}
        self._lock = threading.Lock()

    def hit(self, key: str, per_minute: int) -> float:
        """Takes one token. Returns 0.0 if allowed, otherwise seconds until the next one is free."""
        with self._lock:
            if len(self._buckets) > MAX_TRACKED_KEYS:
                # Bounds memory. Clearing resets everyone's limits, which is acceptable at this scale.
                self._buckets.clear()
            now = self._clock()
            rate = per_minute / 60.0
            tokens, last = self._buckets.get(key, (float(per_minute), now))
            tokens = min(float(per_minute), tokens + (now - last) * rate)
            if tokens >= 1.0:
                self._buckets[key] = (tokens - 1.0, now)
                return 0.0
            self._buckets[key] = (tokens, now)
            return (1.0 - tokens) / rate


limiter = RateLimiter()


def enforce_ingest_limits(organization_id: str, agent_name: str) -> None:
    if not ENABLED:
        return
    retry = limiter.hit(f"org:{organization_id}", ORG_PER_MINUTE)
    if retry:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded for this organization. Slow down and retry.",
            headers={"Retry-After": str(math.ceil(retry))},
        )
    retry = limiter.hit(f"agent:{organization_id}:{agent_name}", AGENT_PER_MINUTE)
    if retry:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded for agent '{agent_name}'. Slow down and retry.",
            headers={"Retry-After": str(math.ceil(retry))},
        )