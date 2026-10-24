from unittest.mock import MagicMock

from app.judge.gemini import JudgeError, JudgeRateLimited, JudgeResult
from app.judge.reviewer import MAX_ATTEMPTS, review_pending


def event_row(id=1, **overrides):
    row = {
        "id": id,
        "organization_id": "org-1",
        "agent_name": "support-bot",
        "event_type": "answer",
        "input_summary": "How do I reset my password?",
        "output_summary": "Use the Forgot password link.",
        "judge_attempts": 0,
    }
    row.update(overrides)
    return row


def setup(make_fake_supabase, fake_query, rows, update_data=None, escalations=None):
    events = fake_query(data=rows, update_data=update_data)
    esc = fake_query(data=escalations or [])
    return make_fake_supabase(agent_events=events, escalations=esc), events, esc


def stub(verdict="agree", score=0.9, reason="Looks right."):
    return MagicMock(return_value=JudgeResult(verdict, score, reason))


def final_update(events):
    return events.updates[-1]


# --- verdicts ---------------------------------------------------------------

def test_agree_is_recorded_and_nothing_is_escalated(make_fake_supabase, fake_query):
    fake, events, esc = setup(make_fake_supabase, fake_query, [event_row()])
    stats = review_pending(fake, organization_id="org-1", judge=stub("agree"))

    assert stats["reviewed"] == 1 and stats["flagged"] == 0
    assert stats["last_error"] is None
    update = final_update(events)
    assert update["judge_status"] == "reviewed"
    assert update["judge_verdict"] == "agree"
    assert update["judge_attempts"] == 1
    assert esc.inserted is None


def test_disagree_puts_the_event_in_the_human_queue(make_fake_supabase, fake_query):
    fake, events, esc = setup(make_fake_supabase, fake_query, [event_row(id=7)])
    stats = review_pending(
        fake, organization_id="org-1", judge=stub("disagree", 0.1, "The answer is wrong.")
    )

    assert stats["reviewed"] == 1 and stats["flagged"] == 1
    assert esc.inserted["event_id"] == 7
    assert esc.inserted["organization_id"] == "org-1"
    assert esc.inserted["status"] == "pending"
    assert "The answer is wrong." in esc.inserted["reason"]
    assert final_update(events)["judge_verdict"] == "disagree"


def test_unsure_is_recorded_but_not_escalated(make_fake_supabase, fake_query):
    fake, events, esc = setup(make_fake_supabase, fake_query, [event_row()])
    stats = review_pending(fake, judge=stub("unsure", 0.5, "Cannot tell."))

    assert stats["reviewed"] == 1 and stats["flagged"] == 0
    assert esc.inserted is None


def test_an_already_flagged_event_is_not_escalated_twice(make_fake_supabase, fake_query):
    fake, _, esc = setup(
        make_fake_supabase, fake_query, [event_row()], escalations=[{"id": 99}]
    )
    review_pending(fake, judge=stub("disagree", 0.1, "Wrong."))
    assert esc.inserted is None


# --- skipping and claiming --------------------------------------------------

def test_events_with_nothing_to_review_are_skipped_without_calling_the_judge(
    make_fake_supabase, fake_query
):
    blank = event_row(input_summary="  ", output_summary=None)
    fake, events, _ = setup(make_fake_supabase, fake_query, [blank])
    judge = stub()

    stats = review_pending(fake, judge=judge)

    assert stats["skipped"] == 1
    judge.assert_not_called()
    assert final_update(events)["judge_status"] == "skipped"


def test_an_event_claimed_by_another_pass_is_left_alone(make_fake_supabase, fake_query):
    # update_data=[] is exactly what a lost atomic claim looks like.
    fake, _, esc = setup(make_fake_supabase, fake_query, [event_row()], update_data=[])
    judge = stub("disagree")

    stats = review_pending(fake, judge=judge)

    judge.assert_not_called()
    assert stats["reviewed"] == 0
    assert esc.inserted is None


# --- failures ---------------------------------------------------------------

def test_a_failed_attempt_goes_back_to_pending_with_the_attempt_counted(
    make_fake_supabase, fake_query
):
    fake, events, _ = setup(make_fake_supabase, fake_query, [event_row(judge_attempts=0)])
    judge = MagicMock(side_effect=JudgeError("model hiccup"))

    stats = review_pending(fake, judge=judge)

    assert stats["retry_later"] == 1 and stats["failed"] == 0
    assert stats["last_error"] == "model hiccup"
    update = final_update(events)
    assert update["judge_status"] == "pending"
    assert update["judge_attempts"] == 1
    assert "model hiccup" in update["judge_reason"]


def test_after_the_last_attempt_the_event_is_marked_failed(make_fake_supabase, fake_query):
    row = event_row(judge_attempts=MAX_ATTEMPTS - 1)
    fake, events, _ = setup(make_fake_supabase, fake_query, [row])

    stats = review_pending(fake, judge=MagicMock(side_effect=JudgeError("still broken")))

    assert stats["failed"] == 1
    assert final_update(events)["judge_status"] == "failed"


def test_an_unexpected_exception_is_contained_and_the_batch_continues(
    make_fake_supabase, fake_query
):
    rows = [event_row(id=1), event_row(id=2)]
    fake, _, _ = setup(make_fake_supabase, fake_query, rows)
    judge = MagicMock(
        side_effect=[ValueError("bug"), JudgeResult("agree", 0.9, "fine")]
    )

    stats = review_pending(fake, judge=judge)

    assert stats["retry_later"] == 1
    assert stats["reviewed"] == 1


def test_rate_limiting_stops_the_batch_without_burning_attempts(
    make_fake_supabase, fake_query
):
    rows = [event_row(id=1), event_row(id=2), event_row(id=3)]
    fake, events, _ = setup(make_fake_supabase, fake_query, rows)
    judge = MagicMock(side_effect=JudgeRateLimited("slow down"))

    stats = review_pending(fake, judge=judge)

    assert stats["rate_limited"] is True
    assert stats["deferred"] == 3
    assert stats["failed"] == 0 and stats["retry_later"] == 0
    judge.assert_called_once()  # did not keep hammering the model
    released = final_update(events)
    assert released["judge_status"] == "pending"
    assert "judge_attempts" not in released


# --- budgets ----------------------------------------------------------------

def test_an_exhausted_time_budget_defers_everything(make_fake_supabase, fake_query):
    rows = [event_row(id=1), event_row(id=2)]
    fake, _, _ = setup(make_fake_supabase, fake_query, rows)
    judge = stub()

    stats = review_pending(fake, time_budget_seconds=0, judge=judge)

    assert stats["deferred"] == 2
    judge.assert_not_called()


def test_a_normal_pass_reviews_every_claimed_event(make_fake_supabase, fake_query):
    rows = [event_row(id=1), event_row(id=2), event_row(id=3)]
    fake, _, _ = setup(make_fake_supabase, fake_query, rows)
    judge = stub("agree")

    stats = review_pending(fake, judge=judge)

    assert stats["reviewed"] == 3
    assert judge.call_count == 3
