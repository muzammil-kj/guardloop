# Connecting an n8n workflow to Guardloop

This connects an existing n8n workflow (for example the Task 6 email triage) so every classification is reported to Guardloop, retries never duplicate events, and the workflow respects its daily budget.

You change four things: store the API key as a credential, add a confidence score to the model's output, add one HTTP Request node, and test.

## 1. Store the API key as an n8n credential (not in the workflow)

1. In n8n, open **Credentials** (left sidebar), click **Create credential**.
2. Search for **Header Auth**, then choose it.
3. **Name:** `Authorization`
4. **Value:** `Bearer ` followed by your Guardloop key (keep the space after "Bearer").
5. Name the credential `Guardloop API key` and save.

Exporting the workflow never includes this value, so the workflow file is safe to share.

## 2. Ask the model for a confidence score

Guardloop's policies work on a confidence number between 0 and 1. The Task 6 prompt returns only a classification and a reason, so add a confidence field.

In the Gemini node's prompt, change the required JSON format to:

```
{
  "classification": "<category>",
  "reason": "Short explanation",
  "confidence": 0.0
}
```

and add the line: `confidence is a number from 0 to 1 for how sure you are of the classification.`

In the node that parses Gemini's reply, carry the new field through. Field names in this guide (`classification`, `reason`, `cleanText`) come from the Task 1 workflow; use the names your own nodes produce.

Test this step on its own before continuing.

## 3. Add the Guardloop node

Place it directly after the node that parses Gemini's classification.

1. Click **+**, search for **HTTP Request**, add it, and rename it `Guardloop report`.
2. **Method:** POST
3. **URL:** `https://guardloop-api.onrender.com/ingest`
4. **Authentication:** Generic Credential Type, then **Header Auth**, then select `Guardloop API key`.
5. **Send Headers:** turn on. Add one header:
   - **Name:** `Idempotency-Key`
   - **Value** (switch to Expression): the Gmail message id, for example `{{ $('Gmail Trigger').item.json.id }}`. Use whichever node holds the Gmail message id in your workflow.
6. **Send Body:** turn on. **Body Content Type:** JSON. **Specify Body:** Using JSON. Paste:
   ```
   ={{ JSON.stringify({
     agent_name: "email-triage-agent",
     event_type: $json.classification,
     confidence: $json.confidence,
     input_summary: $json.cleanText,
     output_summary: $json.reason,
     cost_usd: 0
   }) }}
   ```
7. **Options**, then **Timeout:** `10000`.
8. **Settings** (the gear icon on the node), then **On Error:** **Continue (regular output)**.

Why "Continue": Guardloop watches the workflow, it should never stop an email from being handled. If Guardloop is unreachable, the email is still processed.

## 4. Test it

1. Send yourself one important email and one promotional email.
2. Run the workflow manually. The Guardloop node should show a green check.
3. Open the dashboard. Both emails appear under `email-triage-agent`.
4. Open the Swagger page (`https://guardloop-api.onrender.com/docs`), find `POST /ingest`, and check that the stored input shows `[EMAIL]` in place of the real address.
5. Run the workflow again with the same email. The Gmail id is the same, so no second event appears. This is the idempotency check.

## 5. Optional: set a daily budget

In Swagger, use `PUT /agents/email-triage-agent/budget` with `{"daily_budget_usd": 1}`. Once the day's reported spend reaches that amount, further reports return `blocked`.

Guardloop can only stop the workflow if the workflow asks first. To make it do that, add an HTTP Request node before the classification step that calls `GET https://guardloop-api.onrender.com/agents/email-triage-agent/permission` with the same credential, then an IF node that stops when `allowed` is false.

## If it fails

| Symptom | Likely cause |
|---|---|
| 401 in the Guardloop node | The credential value is missing "Bearer " or has a typo |
| 400 about the Idempotency-Key | The expression resolves to an empty value. Check the Gmail node's output. |
| 429 | The agent is over its budget. This is working as designed. |
| 409 | A duplicate run started while the first was still running. It resolves itself; the workflow continues. |
| No event on the dashboard | Check the Guardloop node's output for the response body. |
