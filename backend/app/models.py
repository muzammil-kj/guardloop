from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from app.alerts.dispatcher import validate_webhook_url


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


class AlertChannelCreate(BaseModel):
    channel_type: Literal["discord", "slack"]
    webhook_url: str
    queue_depth_threshold: int = Field(default=10, ge=1, le=10_000)
    daily_budget_usd: float = Field(default=5.0, gt=0, le=1_000_000)

    @model_validator(mode="after")
    def webhook_must_match_provider(self):
        validate_webhook_url(self.channel_type, self.webhook_url)
        return self


class AlertChannelInfo(BaseModel):
    id: int
    channel_type: str
    webhook_hint: str  # masked; the full webhook URL is never returned
    queue_depth_threshold: int
    daily_budget_usd: float
    enabled: bool
    created_at: str
