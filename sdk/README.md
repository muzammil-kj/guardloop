# guardloop-sdk

Python client for [Guardloop](https://github.com/muzammil-kj/guardloop), a
guardrail and observability layer for AI agents.

## Install

```bash
pip install guardloop-sdk
```

Requires Python 3.9 or newer.

## Usage

```python
from guardloop_sdk import GuardloopClient

client = GuardloopClient(
    api_key="gl_live_your_real_key_here",
    base_url="https://guardloop-api.onrender.com",
)

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
```

`client.report(...)` raises `GuardloopError` if the request fails, network
issues included, rather than silently assuming an event was approved.