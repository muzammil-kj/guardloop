from app.policies.resolver import resolve_policy


def should_escalate(
    supabase,
    organization_id: str,
    agent_name: str,
    event_type: str,
    confidence: float | None,
    force_escalate: bool,
) -> tuple[bool, str | None]:
    """
    The core guardrail decision: should this event go to a human instead of
    being auto-approved?

    Three checks, in order:
    1. The caller (the agent itself) explicitly flagged it - always wins.
    2. This organization has configured this event_type as a hard gate for
       this agent, e.g. "job_application" always needs a human, regardless
       of how confident the model is. This is data now, not code - an org
       can add a new hard-gated category without a redeploy.
    3. Otherwise, fall back to a numeric confidence threshold.
    """
    if force_escalate:
        return True, "Agent explicitly flagged this as requiring human review."

    policy = resolve_policy(supabase, organization_id, agent_name)

    if event_type in policy.get("hard_escalate_event_types", []):
        return True, (
            f"Event type '{event_type}' is configured to always require "
            "human review for this organization."
        )

    threshold = policy["confidence_threshold"]
    if confidence is not None and confidence < threshold:
        return True, f"Confidence {confidence:.2f} is below threshold {threshold:.2f}."

    return False, None