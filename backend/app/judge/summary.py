from collections import defaultdict

# An agent "needs attention" once it has enough reviews to mean something AND
# the judge disagrees with at least this share of its auto-approved decisions.
# Deliberately simple and visible rather than clever: tune these two numbers.
NEEDS_ATTENTION_MIN_REVIEWS = 5
NEEDS_ATTENTION_DISAGREE_RATE = 0.2


def summarize(rows: list[dict]) -> dict:
    """`rows` are reviewed agent_events (agent_name, confidence, judge_verdict)."""
    per_agent: dict[str, dict] = defaultdict(
        lambda: {
            "reviewed": 0,
            "agree": 0,
            "disagree": 0,
            "unsure": 0,
            "confidence_sum": 0.0,
            "confidence_count": 0,
        }
    )

    totals = {"reviewed": 0, "agree": 0, "disagree": 0, "unsure": 0}

    for row in rows:
        verdict = row.get("judge_verdict")
        if verdict not in ("agree", "disagree", "unsure"):
            continue
        stats = per_agent[row["agent_name"]]
        stats["reviewed"] += 1
        stats[verdict] += 1
        totals["reviewed"] += 1
        totals[verdict] += 1
        if row.get("confidence") is not None:
            stats["confidence_sum"] += float(row["confidence"])
            stats["confidence_count"] += 1

    agents = []
    for name, stats in per_agent.items():
        rate = stats["disagree"] / stats["reviewed"]
        agents.append({
            "agent_name": name,
            "reviewed": stats["reviewed"],
            "agree": stats["agree"],
            "disagree": stats["disagree"],
            "unsure": stats["unsure"],
            "disagreement_rate": round(rate, 3),
            "avg_agent_confidence": (
                round(stats["confidence_sum"] / stats["confidence_count"], 3)
                if stats["confidence_count"]
                else None
            ),
            "needs_attention": (
                stats["reviewed"] >= NEEDS_ATTENTION_MIN_REVIEWS
                and rate >= NEEDS_ATTENTION_DISAGREE_RATE
            ),
        })

    agents.sort(key=lambda a: (-a["disagreement_rate"], -a["reviewed"], a["agent_name"]))
    return {"totals": totals, "agents": agents}
