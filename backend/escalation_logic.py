import os

CONFIDENCE_THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", 0.75))


def should_escalate(confidence: float | None, force_escalate: bool) -> tuple[bool, str | None]:
    """
    The core guardrail decision: should this event go to a human instead of
    being auto-approved?

    This mirrors the same principle used in the Task 6 email triage system:
    certain things are hard-gated to a human regardless of the model's own
    confidence (force_escalate), and anything else below a numeric
    confidence threshold is treated as "not safe to decide alone."
    """
    if force_escalate:
        return True, "Agent explicitly flagged this as requiring human review."

    if confidence is not None and confidence < CONFIDENCE_THRESHOLD:
        return True, f"Confidence {confidence:.2f} is below threshold {CONFIDENCE_THRESHOLD:.2f}."

    return False, None