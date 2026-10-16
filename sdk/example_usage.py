"""
Example: how a Python-based AI agent reports its decisions to Guardloop.
Run with: python example_usage.py   (after `pip install -e .` from this folder)
"""
from guardloop_sdk import GuardloopClient, GuardloopError

client = GuardloopClient(
    api_key="gl_live_NC3pvbYyYzJQNaVUJBiijCIRsMoik7JG3-dBmhwmNZo",
    base_url="http://127.0.0.1:8000",
)

try:
    result = client.report(
        agent_name="invoice-parser",
        event_type="classification",
        confidence=0.62,
        input_summary="Invoice #4921 from Acme Corp, amount $14,200",
        output_summary="Classified as: needs_manual_review (unusual amount)",
        cost_usd=0.0008,
    )

    if result.escalated:
        print(f"Escalated to a human: {result.reason}")
    else:
        print("Auto-approved, no human needed.")

except GuardloopError as exc:
    print(f"Guardloop call failed: {exc}")