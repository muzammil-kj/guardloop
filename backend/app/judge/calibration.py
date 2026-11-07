"""
How often is the judge right?

When the judge flags an auto-approved decision, that flag goes to a human. If the
human REJECTS the escalation, the agent's decision really was wrong, so the judge
was right. If the human APPROVES it, the decision was fine and the judge was wrong.

Precision = confirmed flags / all resolved judge flags.
"""
import math

MIN_REVIEWS_FOR_RELIABLE = 30


def wilson_interval(successes: int, n: int, z: float = 1.96):
    """95% confidence interval for a proportion. Honest at small sample sizes,
    unlike the simple percentage."""
    if n == 0:
        return None, None
    p = successes / n
    z2 = z * z
    denominator = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denominator
    margin = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denominator
    return round(max(0.0, centre - margin), 3), round(min(1.0, centre + margin), 3)


def _agent_name(row: dict) -> str:
    event = row.get("agent_events")
    if isinstance(event, list):
        event = event[0] if event else None
    return (event or {}).get("agent_name") or "unknown"


def _tally(rows: list[dict]) -> dict:
    confirmed = sum(1 for row in rows if row.get("status") == "rejected")
    overruled = sum(1 for row in rows if row.get("status") == "approved")
    reviews = confirmed + overruled
    low, high = wilson_interval(confirmed, reviews)
    return {
        "reviews": reviews,
        "flags_confirmed": confirmed,
        "flags_overruled": overruled,
        "precision": round(confirmed / reviews, 3) if reviews else None,
        "precision_ci_low": low,
        "precision_ci_high": high,
        "reliable": reviews >= MIN_REVIEWS_FOR_RELIABLE,
    }


def summarize_calibration(rows: list[dict]) -> dict:
    """`rows` are resolved judge escalations, each with its agent_events.agent_name."""
    by_agent: dict = {}
    for row in rows:
        by_agent.setdefault(_agent_name(row), []).append(row)

    agents = [{"agent_name": name, **_tally(items)} for name, items in by_agent.items()]
    agents.sort(key=lambda a: (-a["reviews"], a["agent_name"]))
    return {**_tally(rows), "by_agent": agents}