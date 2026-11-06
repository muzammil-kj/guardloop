from unittest.mock import MagicMock, patch

from app.policies.budget import budget_status, effective_daily_budget, spent_today


def queued(fake_query, results):
    """A query whose successive SELECTs return the given results, in order."""
    class Queued(fake_query):
        def __init__(self):
            super().__init__()
            self._results = list(results)

        def execute(self):
            if self._mode == "select":
                result = MagicMock()
                result.data = self._results.pop(0)
                result.count = None
                return result
            return super().execute()

    return Queued()


def test_the_agents_own_cap_wins(make_fake_supabase, fake_query):
    fake = make_fake_supabase(agent_policies=queued(fake_query, [[{"daily_budget_usd": 5}]]))
    assert effective_daily_budget(fake, "org-1", "bot") == 5.0


def test_falls_back_to_the_organization_cap(make_fake_supabase, fake_query):
    fake = make_fake_supabase(agent_policies=queued(fake_query, [
        [{"daily_budget_usd": None}],   # agent row has no cap
        [{"daily_budget_usd": 3}],      # organization default has one
    ]))
    assert effective_daily_budget(fake, "org-1", "bot") == 3.0


def test_no_cap_anywhere_means_no_limit(make_fake_supabase, fake_query):
    fake = make_fake_supabase(agent_policies=queued(fake_query, [[], []]))
    assert effective_daily_budget(fake, "org-1", "bot") is None


def test_spend_today_adds_up_numeric_strings_and_floats(make_fake_supabase, fake_query):
    fake = make_fake_supabase(agent_costs=fake_query(data=[
        {"total_cost_usd": "1.25"}, {"total_cost_usd": 0.75},
    ]))
    assert spent_today(fake, "org-1", "bot") == 2.0


def test_status_allows_action_under_the_cap():
    with patch("app.policies.budget.effective_daily_budget", return_value=5.0), \
         patch("app.policies.budget.spent_today", return_value=2.0):
        status = budget_status(None, "org-1", "bot")
    assert status["allowed"] is True
    assert status["remaining_usd"] == 3.0


def test_status_blocks_action_at_the_cap():
    with patch("app.policies.budget.effective_daily_budget", return_value=5.0), \
         patch("app.policies.budget.spent_today", return_value=5.0):
        status = budget_status(None, "org-1", "bot")
    assert status["allowed"] is False
    assert status["remaining_usd"] == 0.0


def test_status_with_no_cap_always_allows():
    with patch("app.policies.budget.effective_daily_budget", return_value=None), \
         patch("app.policies.budget.spent_today", return_value=999.0):
        status = budget_status(None, "org-1", "bot")
    assert status["allowed"] is True
    assert status["remaining_usd"] is None