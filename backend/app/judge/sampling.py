import logging
import random
from typing import Callable

from app.config import settings

logger = logging.getLogger("guardloop.judge")

DEFAULT_SAMPLE_RATE = 0.2


def should_sample(sample_rate: float, rng: Callable[[], float] = random.random) -> bool:
    """True for roughly `sample_rate` of calls. `rng` is injectable for tests."""
    if sample_rate <= 0:
        return False
    if sample_rate >= 1:
        return True
    return rng() < sample_rate


def get_judge_settings(supabase, organization_id: str) -> dict:
    """An organization with no row has the judge OFF at the default rate."""
    result = (
        supabase.table("judge_settings")
        .select("*")
        .eq("organization_id", organization_id)
        .execute()
    )
    if result.data:
        row = result.data[0]
        return {
            "enabled": bool(row["enabled"]),
            "sample_rate": float(row["sample_rate"]),
        }
    return {"enabled": False, "sample_rate": DEFAULT_SAMPLE_RATE}


def decide_judge_sampling(supabase, organization_id: str, has_content: bool) -> bool:
    """
    Called at ingest for events that were auto-approved. Returns True when the
    event should be queued for a second opinion.

    The judge is an optional quality layer, so this must never get in the way
    of recording events: any failure (a missing table, a database hiccup)
    means "don't sample" and a warning in the logs, never an error to the agent.
    """
    if not has_content or not settings.gemini_api_key:
        return False  # nothing to review, or no model to review it with

    try:
        config = get_judge_settings(supabase, organization_id)
        return config["enabled"] and should_sample(config["sample_rate"])
    except Exception as exc:
        logger.warning("Judge sampling skipped for org %s: %s", organization_id, exc)
        return False
