"""
LangChain callback handler: reports every top-level chain run to Guardloop.

    from guardloop_sdk import GuardloopClient
    from guardloop_sdk.langchain import GuardloopCallbackHandler

    handler = GuardloopCallbackHandler(GuardloopClient(api_key="gl_live_..."), agent_name="support-bot")
    chain.invoke({"question": "..."}, config={"callbacks": [handler]})

Only the outermost chain is reported, so one user request gives one event.
Reporting never breaks the chain: a Guardloop outage is logged and ignored.
The LangChain run id is the idempotency key, so retried runs aren't double-counted.
"""
import logging
from typing import Callable, Optional

try:
    from langchain_core.callbacks import BaseCallbackHandler
except ImportError:  # LangChain isn't installed; the handler still works when its methods are called directly
    class BaseCallbackHandler:  # type: ignore[no-redef]
        pass

logger = logging.getLogger("guardloop_sdk.langchain")
SUMMARY_LIMIT = 2000


def _short(value) -> str:
    text = value if isinstance(value, str) else repr(value)
    return text[:SUMMARY_LIMIT]


class GuardloopCallbackHandler(BaseCallbackHandler):
    def __init__(self, client, agent_name: str,
                 confidence_fn: Optional[Callable[[dict], float]] = None,
                 event_type: str = "chain_run"):
        self.client = client
        self.agent_name = agent_name
        self.confidence_fn = confidence_fn
        self.event_type = event_type
        self._inputs: dict = {}

    def _report(self, run_id, **kwargs) -> None:
        try:
            self.client.report(
                agent_name=self.agent_name,
                event_type=self.event_type,
                idempotency_key=str(run_id) if run_id is not None else None,
                **kwargs,
            )
        except Exception as exc:
            logger.warning("Guardloop report skipped: %s", type(exc).__name__)

    def on_chain_start(self, serialized, inputs, *, run_id=None, parent_run_id=None, **kwargs):
        if parent_run_id is None and run_id is not None:
            self._inputs[run_id] = _short(inputs)

    def on_chain_end(self, outputs, *, run_id=None, parent_run_id=None, **kwargs):
        input_summary = self._inputs.pop(run_id, None) if run_id is not None else None
        if parent_run_id is not None:
            return
        confidence = None
        if self.confidence_fn is not None:
            try:
                confidence = float(self.confidence_fn(outputs))
            except Exception:
                confidence = None
        self._report(run_id, confidence=confidence, input_summary=input_summary,
                     output_summary=_short(outputs))

    def on_chain_error(self, error, *, run_id=None, parent_run_id=None, **kwargs):
        input_summary = self._inputs.pop(run_id, None) if run_id is not None else None
        if parent_run_id is not None:
            return
        # A failed run is always sent to a human: a crash is never silently approved.
        self._report(run_id, force_escalate=True, input_summary=input_summary,
                     escalate_reason=f"Chain failed: {_short(str(error))}")