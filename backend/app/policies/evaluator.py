from app.config import settings


def should_escalate(confidence: float | None, force_escalate: bool) -> tuple[bool, str | None]:
    """
    The core guardrail decision: should this event go to a human instead of
    being auto-approved?

    Phase 1 still uses one global threshold from Settings. Phase 2 will make
    this per-organization and per-agent, stored in the database instead of
    an environment variable.
    """
    if force_escalate:
        return True, "Agent explicitly flagged this as requiring human review."

    if confidence is not None and confidence < settings.default_confidence_threshold:
        return True, (
            f"Confidence {confidence:.2f} is below threshold "
            f"{settings.default_confidence_threshold:.2f}."
        )

    return False, None