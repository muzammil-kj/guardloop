from app.judge.calibration import MIN_REVIEWS_FOR_RELIABLE, summarize_calibration, wilson_interval


def flag(status, agent="bot"):
    return {"status": status, "agent_events": {"agent_name": agent}}


def test_a_rejected_flag_means_the_judge_was_right():
    summary = summarize_calibration([flag("rejected")])
    assert summary["flags_confirmed"] == 1 and summary["flags_overruled"] == 0
    assert summary["precision"] == 1.0


def test_an_approved_flag_means_the_judge_was_wrong():
    summary = summarize_calibration([flag("approved")])
    assert summary["flags_overruled"] == 1 and summary["precision"] == 0.0


def test_precision_is_confirmed_over_all_resolved_flags():
    rows = [flag("rejected")] * 3 + [flag("approved")] * 1
    assert summarize_calibration(rows)["precision"] == 0.75


def test_no_reviews_means_no_precision_rather_than_zero():
    summary = summarize_calibration([])
    assert summary["precision"] is None
    assert summary["precision_ci_low"] is None
    assert summary["reliable"] is False


def test_small_samples_are_marked_unreliable():
    summary = summarize_calibration([flag("rejected")] * (MIN_REVIEWS_FOR_RELIABLE - 1))
    assert summary["reliable"] is False
    summary = summarize_calibration([flag("rejected")] * MIN_REVIEWS_FOR_RELIABLE)
    assert summary["reliable"] is True


def test_the_interval_is_honest_about_small_samples():
    low, high = wilson_interval(3, 3)  # perfect so far, but only 3 reviews
    assert high == 1.0
    assert low < 0.5  # a 100% from 3 reviews is not a precise number


def test_the_interval_narrows_with_more_reviews():
    small_low, small_high = wilson_interval(8, 10)
    big_low, big_high = wilson_interval(800, 1000)
    assert (big_high - big_low) < (small_high - small_low)


def test_per_agent_breakdown_is_sorted_by_volume():
    rows = [flag("rejected", "a")] * 2 + [flag("approved", "b")] * 5
    agents = summarize_calibration(rows)["by_agent"]
    assert [a["agent_name"] for a in agents] == ["b", "a"]
    assert agents[0]["precision"] == 0.0


def test_a_missing_agent_name_is_labelled_unknown():
    assert summarize_calibration([{"status": "rejected", "agent_events": None}])["by_agent"][0]["agent_name"] == "unknown"


def test_a_list_join_result_is_handled():
    row = {"status": "rejected", "agent_events": [{"agent_name": "listy"}]}
    assert summarize_calibration([row])["by_agent"][0]["agent_name"] == "listy"