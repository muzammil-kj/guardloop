from pydantic import BaseModel
from typing import Optional


class IngestEvent(BaseModel):
    agent_name: str
    event_type: str
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    confidence: Optional[float] = None     # 0.0 - 1.0, omit if agent doesn't report one
    force_escalate: bool = False           # let the agent hard-flag a category itself
    escalate_reason: Optional[str] = None  # required if force_escalate is True
    cost_usd: float = 0.0


class ResolveEscalation(BaseModel):
    status: str             # "approved" | "rejected" | "corrected"
    resolved_by: str
    resolution_note: Optional[str] = None