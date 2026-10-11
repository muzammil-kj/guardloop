from unittest.mock import MagicMock
from app.policies.resolver import resolve_policy


def test_resolve_policy_uses_agent_specific_when_present():
    agent_policy = {
        "confidence_threshold": 0.9,
        "hard_escalate_event_types": ["job_application"],
    }
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
        agent_policy
    ]

    result = resolve_policy(mock_supabase, "org-1", "email-triage-agent")

    assert result == agent_policy


def test_resolve_policy_falls_back_to_org_default_when_no_agent_specific_policy():
    org_default = {"confidence_threshold": 0.8, "hard_escalate_event_types": []}
    mock_supabase = MagicMock()
    # Agent-specific lookup (.eq().eq()) returns nothing
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
    # Org default lookup (.eq().is_()) returns the default row
    mock_supabase.table.return_value.select.return_value.eq.return_value.is_.return_value.execute.return_value.data = [
        org_default
    ]

    result = resolve_policy(mock_supabase, "org-1", "unknown-agent")

    assert result == org_default


def test_resolve_policy_falls_back_to_global_default_when_org_has_configured_nothing():
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
    mock_supabase.table.return_value.select.return_value.eq.return_value.is_.return_value.execute.return_value.data = []

    result = resolve_policy(mock_supabase, "org-1", "brand-new-agent")

    assert "confidence_threshold" in result
    assert result["hard_escalate_event_types"] == []