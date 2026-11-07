from app.judge.versions import summarize_versions


def event(version, status="approved", verdict=None, created="2026-10-01T00:00:00", agent="bot"):
    return {"agent_name": agent, "agent_version": version, "status": status,
            "judge_verdict": verdict, "created_at": created}


def test_events_are_grouped_by_agent_and_version():
    rows = [event("v1"), event("v1"), event("v2")]
    by_version = {r["agent_version"]: r for r in summarize_versions(rows)}
    assert by_version["v1"]["events"] == 2
    assert by_version["v2"]["events"] == 1


def test_untagged_events_are_kept_in_their_own_bucket():
    result = summarize_versions([event(None)])
    assert result[0]["agent_version"] == "unversioned"


def test_escalation_and_block_rates():
    rows = [event("v1", "escalated"), event("v1", "approved"), event("v1", "blocked"), event("v1", "approved")]
    row = summarize_versions(rows)[0]
    assert row["escalation_rate"] == 0.25
    assert row["block_rate"] == 0.25


def test_a_regression_shows_as_higher_disagreement():
    rows = [
        event("v1", verdict="agree", created="2026-10-01"),
        event("v1", verdict="agree", created="2026-10-01"),
        event("v2", verdict="disagree", created="2026-10-08"),
        event("v2", verdict="disagree", created="2026-10-08"),
    ]
    by_version = {r["agent_version"]: r for r in summarize_versions(rows)}
    assert by_version["v1"]["disagreement_rate"] == 0.0
    assert by_version["v2"]["disagreement_rate"] == 1.0


def test_no_judge_reviews_means_no_disagreement_rate_not_zero():
    row = summarize_versions([event("v1")])[0]
    assert row["disagreement_rate"] is None


def test_versions_are_ordered_oldest_first_within_an_agent():
    rows = [event("new", created="2026-10-08"), event("old", created="2026-10-01")]
    assert [r["agent_version"] for r in summarize_versions(rows)] == ["old", "new"]