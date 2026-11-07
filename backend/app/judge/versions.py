from collections import defaultdict


def summarize_versions(rows: list[dict]) -> list[dict]:
    """
    One line per (agent, version). A regression shows up as a version whose
    disagreement or escalation rate is higher than the versions before it.
    `rows` are agent_events with agent_name, agent_version, status, judge_verdict, created_at.
    """
    buckets: dict = defaultdict(lambda: {
        "events": 0, "escalated": 0, "blocked": 0,
        "reviewed": 0, "disagreed": 0, "first_seen": None,
    })
    for row in rows:
        key = (row.get("agent_name") or "unknown", row.get("agent_version") or "unversioned")
        bucket = buckets[key]
        bucket["events"] += 1
        if row.get("status") == "escalated":
            bucket["escalated"] += 1
        if row.get("status") == "blocked":
            bucket["blocked"] += 1
        verdict = row.get("judge_verdict")
        if verdict in ("agree", "disagree", "unsure"):
            bucket["reviewed"] += 1
            if verdict == "disagree":
                bucket["disagreed"] += 1
        created = row.get("created_at")
        if created and (bucket["first_seen"] is None or created < bucket["first_seen"]):
            bucket["first_seen"] = created

    result = []
    for (agent, version), b in buckets.items():
        result.append({
            "agent_name": agent,
            "agent_version": version,
            "first_seen": b["first_seen"],
            "events": b["events"],
            "escalation_rate": round(b["escalated"] / b["events"], 3),
            "block_rate": round(b["blocked"] / b["events"], 3),
            "reviewed": b["reviewed"],
            "disagreement_rate": round(b["disagreed"] / b["reviewed"], 3) if b["reviewed"] else None,
        })
    result.sort(key=lambda r: (r["agent_name"], r["first_seen"] or ""))
    return result