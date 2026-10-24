from types import SimpleNamespace
from unittest.mock import patch

from app.judge.sampling import (
    DEFAULT_SAMPLE_RATE,
    decide_judge_sampling,
    get_judge_settings,
    should_sample,
)
from app.judge.summary import summarize


# --- should_sample ----------------------------------------------------------

def test_rate_zero_never_samples_and_rate_one_always_does():
    assert not any(should_sample(0, rng=lambda: 0.0) for _ in range(5))
    assert all(should_sample(1, rng=lambda: 0.999) for _ in range(5))


def test_fractional_rate_compares_against_the_random_draw():
    assert should_sample(0.3, rng=lambda: 0.29) is True
    assert should_sample(0.3, rng=lambda: 0.30) is False
    assert should_sample(0.3, rng=lambda: 0.95) is False


# --- settings lookup --------------------------------------------------------

def test_an_org_with_no_row_has_the_judge_off(make_fake_supabase, fake_query):
    fake = make_fake_supabase(judge_settings=fake_query(data=[]))
    assert get_judge_settings(fake, "org-1") == {
        "enabled": False,
        "sample_rate": DEFAULT_SAMPLE_RATE,
    }


def test_an_existing_row_is_read_back(make_fake_supabase, fake_query):
    row = {"enabled": True, "sample_rate": 0.5}
    fake = make_fake_supabase(judge_settings=fake_query(data=[row]))
    assert get_judge_settings(fake, "org-1") == {"enabled": True, "sample_rate": 0.5}


# --- decide_judge_sampling --------------------------------------------------

def with_key(key="k"):
    return patch("app.judge.sampling.settings", SimpleNamespace(gemini_api_key=key))


def test_sampled_when_enabled_configured_and_there_is_content(
    make_fake_supabase, fake_query
):
    fake = make_fake_supabase(
        judge_settings=fake_query(data=[{"enabled": True, "sample_rate": 1.0}])
    )
    with with_key():
        assert decide_judge_sampling(fake, "org-1", has_content=True) is True


def test_not_sampled_when_the_org_has_not_turned_the_judge_on(
    make_fake_supabase, fake_query
):
    fake = make_fake_supabase(
        judge_settings=fake_query(data=[{"enabled": False, "sample_rate": 1.0}])
    )
    with with_key():
        assert decide_judge_sampling(fake, "org-1", has_content=True) is False


def test_not_sampled_without_content_or_without_a_model_key(
    make_fake_supabase, fake_query
):
    fake = make_fake_supabase(
        judge_settings=fake_query(data=[{"enabled": True, "sample_rate": 1.0}])
    )
    with with_key():
        assert decide_judge_sampling(fake, "org-1", has_content=False) is False
    with with_key(""):
        assert decide_judge_sampling(fake, "org-1", has_content=True) is False


def test_a_database_failure_means_not_sampled_rather_than_an_error(
    make_fake_supabase, fake_query
):
    class Broken(fake_query):
        def execute(self):
            raise RuntimeError("relation judge_settings does not exist")

    fake = make_fake_supabase(judge_settings=Broken())
    with with_key():
        assert decide_judge_sampling(fake, "org-1", has_content=True) is False


# --- summarize --------------------------------------------------------------

def review(agent, verdict, confidence=0.9):
    return {"agent_name": agent, "judge_verdict": verdict, "confidence": confidence}


def test_totals_and_per_agent_counts():
    rows = [
        review("a", "agree"),
        review("a", "disagree"),
        review("b", "unsure"),
        review("b", "agree"),
    ]
    result = summarize(rows)
    assert result["totals"] == {"reviewed": 4, "agree": 2, "disagree": 1, "unsure": 1}
    by_name = {a["agent_name"]: a for a in result["agents"]}
    assert by_name["a"]["disagreement_rate"] == 0.5
    assert by_name["b"]["disagreement_rate"] == 0.0


def test_an_agent_needs_attention_only_with_enough_reviews_and_a_high_rate():
    flagged = [review("bad", "disagree")] + [review("bad", "agree")] * 4  # 1/5 = 20%
    too_few = [review("new", "disagree")] * 2  # 100% but only 2 reviews
    fine = [review("ok", "agree")] * 10

    by_name = {a["agent_name"]: a for a in summarize(flagged + too_few + fine)["agents"]}

    assert by_name["bad"]["needs_attention"] is True
    assert by_name["new"]["needs_attention"] is False
    assert by_name["ok"]["needs_attention"] is False


def test_agents_are_sorted_worst_first():
    rows = [review("calm", "agree")] * 3 + [review("shaky", "disagree")] * 3
    names = [a["agent_name"] for a in summarize(rows)["agents"]]
    assert names == ["shaky", "calm"]


def test_missing_confidence_is_handled():
    result = summarize([review("a", "agree", confidence=None)])
    assert result["agents"][0]["avg_agent_confidence"] is None


def test_rows_without_a_verdict_are_ignored():
    result = summarize([{"agent_name": "a", "judge_verdict": None, "confidence": 0.5}])
    assert result["totals"]["reviewed"] == 0
    assert result["agents"] == []
