from pydantic import BaseModel
from typing import Optional


class IngestEvent(BaseModel):
    agent_name: str
    event_type: str
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    confidence: Optional[float] = None
    force_escalate: bool = False
    escalate_reason: Optional[str] = None
    cost_usd: float = 0.0


class ResolveEscalation(BaseModel):
    status: str
    resolved_by: str
    resolution_note: Optional[str] = None


class CreateOrganization(BaseModel):
    name: str


class OrganizationCreated(BaseModel):
    organization_id: str
    name: str
    api_key: str  # shown once only, never retrievable again


class CreateApiKey(BaseModel):
    label: Optional[str] = None


class ApiKeyCreated(BaseModel):
    id: int
    key_prefix: str
    api_key: str  # shown once only
    label: Optional[str] = None


class ApiKeyInfo(BaseModel):
    id: int
    key_prefix: str
    label: Optional[str] = None
    revoked: bool
    last_used_at: Optional[str] = None
    created_at: str


class PolicyUpdate(BaseModel):
    confidence_threshold: float
    hard_escalate_event_types: list[str] = []


class PolicyInfo(BaseModel):
    agent_name: Optional[str] = None  # None = this org's default policy
    confidence_threshold: float
    hard_escalate_event_types: list[str]
    updated_at: str