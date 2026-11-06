from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

import requests


class GuardloopError(Exception):
    """Guardloop rejected a request, or could not be reached."""


@dataclass
class IngestResult:
    event_id: int
    status: str            # "approved" | "escalated" | "blocked"
    reason: Optional[str]
    pii_redacted: bool = False

    @property
    def approved(self) -> bool:
        return self.status == "approved"

    @property
    def escalated(self) -> bool:
        return self.status == "escalated"

    @property
    def blocked(self) -> bool:
        """True when the agent is over its daily budget and must stop acting."""
        return self.status == "blocked"


@dataclass
class Permission:
    agent_name: str
    allowed: bool
    daily_budget_usd: Optional[float]
    spent_today_usd: float
    remaining_usd: Optional[float]


class GuardloopClient:
    """
    Reports AI agent decisions to Guardloop.

    Example:
        client = GuardloopClient(api_key="gl_live_...")

        if not client.can_act("invoice-parser").allowed:
            return                                   # over budget: stop here

        result = client.report(
            agent_name="invoice-parser",
            event_type="classification",
            confidence=0.62,
            input_summary="Invoice #4921 from Acme Corp",
            output_summary="needs_manual_review",
            idempotency_key=execution_id,            # makes retries safe
        )
        if result.escalated:
            print("A human needs to review:", result.reason)
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://guardloop-api.onrender.com",
        timeout: float = 10.0,
    ):
        if not api_key:
            raise ValueError("api_key is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _headers(self, idempotency_key: Optional[str] = None) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    def _send(self, method, url, **kwargs):
        try:
            return requests.request(method, url, timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise GuardloopError(f"Could not reach Guardloop: {type(exc).__name__}") from None

    def report(
        self,
        agent_name: str,
        event_type: str,
        confidence: Optional[float] = None,
        input_summary: Optional[str] = None,
        output_summary: Optional[str] = None,
        force_escalate: bool = False,
        escalate_reason: Optional[str] = None,
        cost_usd: float = 0.0,
        idempotency_key: Optional[str] = None,
    ) -> IngestResult:
        """
        Reports one decision. Pass idempotency_key (for example an n8n execution
        id) so a retried call is never recorded twice.

        A budget block is returned as a result with blocked == True, not raised,
        because it is a normal answer the agent should act on.
        """
        payload = {
            "agent_name": agent_name,
            "event_type": event_type,
            "confidence": confidence,
            "input_summary": input_summary,
            "output_summary": output_summary,
            "force_escalate": force_escalate,
            "escalate_reason": escalate_reason,
            "cost_usd": cost_usd,
        }
        response = self._send(
            "POST", f"{self.base_url}/ingest",
            json=payload, headers=self._headers(idempotency_key),
        )

        if response.status_code == 401:
            raise GuardloopError("Guardloop rejected this API key (missing, invalid, or revoked).")
        if response.status_code == 409:
            raise GuardloopError("An earlier request with this idempotency key is still running. Retry shortly.")
        if response.status_code not in (200, 429) and not response.ok:
            raise GuardloopError(f"Guardloop returned an error: {response.status_code}")

        try:
            data = response.json()
        except ValueError:
            raise GuardloopError("Guardloop returned a response that was not JSON.") from None

        return IngestResult(
            event_id=data.get("event_id", 0),
            status=data["status"],
            reason=data.get("reason"),
            pii_redacted=bool(data.get("pii_redacted", False)),
        )

    def can_act(self, agent_name: str) -> Permission:
        """Ask before acting. Guardloop can only stop an agent that asks first."""
        response = self._send(
            "GET",
            f"{self.base_url}/agents/{quote(agent_name, safe='')}/permission",
            headers=self._headers(),
        )
        if response.status_code == 401:
            raise GuardloopError("Guardloop rejected this API key (missing, invalid, or revoked).")
        if not response.ok:
            raise GuardloopError(f"Guardloop returned an error: {response.status_code}")
        data = response.json()
        return Permission(
            agent_name=data["agent_name"],
            allowed=data["allowed"],
            daily_budget_usd=data.get("daily_budget_usd"),
            spent_today_usd=data["spent_today_usd"],
            remaining_usd=data.get("remaining_usd"),
        )
