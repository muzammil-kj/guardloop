from unittest.mock import patch
from app.policies.evaluator import should_escalate


def test_force_escalate_always_wins_regardless_of_confidence():
    escalate, reason = should_escalate(
        supabase=None,
        organization_id="org-1",
        agent_name="agent-1",
        event_type="anything",
        confidence=0.99,
        force_escalate=True,
    )
    assert escalate is True
    assert "explicitly flagged" in reason


def test_hard_escalate_event_type_overrides_high_confidence():
    policy = {
        "confidence_threshold": 0.5,
        "hard_escalate_event_types": ["job_application"],
    }
    with patch("app.policies.evaluator.resolve_policy", return_value=policy):
        escalate, reason = should_escalate(
            supabase=None,
            organization_id="org-1",
            agent_name="agent-1",
            event_type="job_application",
            confidence=0.99,
            force_escalate=False,
        )
    assert escalate is True
    assert "job_application" in reason


def test_low_confidence_below_threshold_escalates():
    policy = {"confidence_threshold": 0.75, "hard_escalate_event_types": []}
    with patch("app.policies.evaluator.resolve_policy", return_value=policy):
        escalate, _ = should_escalate(
            supabase=None,
            organization_id="org-1",
            agent_name="agent-1",
            event_type="classification",
            confidence=0.5,
            force_escalate=False,
        )
    assert escalate is True


def test_high_confidence_above_threshold_approves():
    policy = {"confidence_threshold": 0.75, "hard_escalate_event_types": []}
    with patch("app.policies.evaluator.resolve_policy", return_value=policy):
        escalate, reason = should_escalate(
            supabase=None,
            organization_id="org-1",
            agent_name="agent-1",
            event_type="classification",
            confidence=0.95,
            force_escalate=False,
        )
    assert escalate is False
    assert reason is None