from unittest.mock import MagicMock

from guardloop_sdk.langchain import GuardloopCallbackHandler


def handler(confidence_fn=None):
    client = MagicMock()
    return GuardloopCallbackHandler(client, agent_name="support-bot", confidence_fn=confidence_fn), client


def test_a_finished_top_level_chain_is_reported_once_with_its_run_id():
    h, client = handler()
    h.on_chain_start({}, {"question": "reset password?"}, run_id="run-1", parent_run_id=None)
    h.on_chain_end({"answer": "Use the link"}, run_id="run-1", parent_run_id=None)
    client.report.assert_called_once()
    kwargs = client.report.call_args.kwargs
    assert kwargs["agent_name"] == "support-bot"
    assert kwargs["idempotency_key"] == "run-1"
    assert "reset password" in kwargs["input_summary"]
    assert "Use the link" in kwargs["output_summary"]


def test_nested_steps_are_not_reported_separately():
    h, client = handler()
    h.on_chain_end({"step": 1}, run_id="inner", parent_run_id="outer")
    client.report.assert_not_called()


def test_a_failed_chain_is_always_sent_to_a_human():
    h, client = handler()
    h.on_chain_start({}, {"question": "x"}, run_id="run-2", parent_run_id=None)
    h.on_chain_error(ValueError("tool crashed"), run_id="run-2", parent_run_id=None)
    kwargs = client.report.call_args.kwargs
    assert kwargs["force_escalate"] is True
    assert "tool crashed" in kwargs["escalate_reason"]


def test_a_confidence_function_supplies_the_score():
    h, client = handler(confidence_fn=lambda outputs: outputs["score"])
    h.on_chain_end({"score": 0.42}, run_id="run-3", parent_run_id=None)
    assert client.report.call_args.kwargs["confidence"] == 0.42


def test_a_broken_confidence_function_is_ignored_not_fatal():
    h, client = handler(confidence_fn=lambda outputs: 1 / 0)
    h.on_chain_end({"x": 1}, run_id="run-4", parent_run_id=None)
    assert client.report.call_args.kwargs["confidence"] is None


def test_a_guardloop_outage_never_breaks_the_chain():
    h, client = handler()
    client.report.side_effect = RuntimeError("network down")
    h.on_chain_end({"x": 1}, run_id="run-5", parent_run_id=None)  # must not raise


def test_inputs_are_forgotten_after_each_run():
    h, _ = handler()
    h.on_chain_start({}, {"q": "a"}, run_id="run-6", parent_run_id=None)
    h.on_chain_end({"x": 1}, run_id="run-6", parent_run_id=None)
    assert "run-6" not in h._inputs