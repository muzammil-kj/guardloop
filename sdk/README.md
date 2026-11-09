# guardloop-sdk

Python client for [Guardloop](https://github.com/muzammil-kj/guardloop), a guardrail and observability layer for AI agents.

## Install

```bash
pip install guardloop-sdk
```

Requires Python 3.9 or newer.

## Usage

```python
from guardloop_sdk import GuardloopClient

client = GuardloopClient(api_key="gl_live_your_real_key_here")

# 1. Ask before acting. If the agent is over its daily budget, stop.
permission = client.can_act("invoice-parser")
if not permission.allowed:
    raise SystemExit("Daily budget reached; not acting.")

# 2. Report the decision. The idempotency key makes retries safe.
result = client.report(
    agent_name="invoice-parser",
    event_type="classification",
    confidence=0.62,
    input_summary="Invoice #4921 from Acme Corp, amount $14,200",
    output_summary="needs_manual_review (unusual amount)",
    cost_usd=0.0008,
    idempotency_key="run-2026-10-26-0001",
)

if result.blocked:
    print("Blocked by budget:", result.reason)
elif result.escalated:
    print("Escalated to a human:", result.reason)
else:
    print("Auto-approved.")
```

`report` raises `GuardloopError` for authentication failures, a conflicting request still in progress, or network errors. A budget block is returned as a result (`result.blocked`), not raised.

Personal data (emails, card numbers, phone numbers, national ID numbers) is masked by Guardloop before it is stored. `result.pii_redacted` tells you whether masking happened.

## LangChain integration

Install LangChain separately:

```bash
pip install langchain-core
```

Example:

```python
from langchain_core.runnables import RunnableLambda
from guardloop_sdk import GuardloopClient
from guardloop_sdk.langchain import GuardloopCallbackHandler

client = GuardloopClient(api_key="gl_live_your_real_key_here")

handler = GuardloopCallbackHandler(
    client,
    agent_name="support-bot",
)

chain = RunnableLambda(
    lambda inputs: {"answer": f"Processed: {inputs['question']}"}
)

result = chain.invoke(
    {"question": "How do I reset my password?"},
    config={"callbacks": [handler]},
)

print(result)
```

Guardloop reports one event per top-level chain run. Failed runs are automatically escalated. Reporting errors are logged without interrupting the chain.

You can also provide a confidence function:

```python
handler = GuardloopCallbackHandler(
    client,
    agent_name="support-bot",
    confidence_fn=lambda outputs: outputs.get("confidence", 0.0),
)
```

## Decision replay

Replay past decisions to see how a new version of your agent would respond before deploying it.

Export your decisions from Guardloop's Audit page or the decisions CSV endpoint:

`GET /exports/decisions.csv`

Each row must contain `input_summary` and `output_summary`.

Example:

```python
from guardloop_sdk.replay import load_decisions_csv, replay

# Load previously exported decisions.
rows = load_decisions_csv(
    "guardloop-decisions.csv",
    agent_name="invoice-parser",
)

# Define your updated agent.
def updated_agent(input_text: str) -> str:
    return "needs_manual_review"

# Replay past inputs using the updated agent.
report = replay(
    rows,
    agent=updated_agent,
    limit=100,
)

print("Total decisions:", report.total)
print("Unchanged:", report.unchanged)
print("Changed:", report.changed)
print("Errors:", report.errors)

for change in report.changes:
    print("Before:", change.before)
    print("After:", change.after)
```

By default, outputs are compared while ignoring case and extra whitespace. You can provide a custom comparison function using the `same` parameter.

Replay reports include:
- `total`: number of decisions processed.
- `unchanged`: number of outputs that stayed the same.
- `changed`: number of outputs that changed.
- `changes`: details of changed decisions, including previous and new outputs.
- `errors`: decisions that could not be replayed.

You can filter exported decisions by agent name and limit the number of decisions replayed.

**Note:** Exported inputs are already masked for personal data. Agents that depend on original personal information may produce different results during replay.

## Changelog

- **0.3.0:** LangChain callback handler, decision replay, n8n report template.
- **0.2.0:** idempotency keys, `can_act()` budget check, budget-block results, personal-data masking reported in results.
- **0.1.0:** first release.