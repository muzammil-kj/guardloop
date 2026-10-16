from dataclasses import dataclass
from typing import Optional

import requests


class GuardloopError(Exception):
    """Raised when Guardloop rejects a request, or can't be reached at all."""


@dataclass
class IngestResult:
    event_id: int
    status: str
    reason: Optional[str]

    @property
    def approved(self) -> bool:
        return self.status == "approved"

    @property
    def escalated(self) -> bool:
        return self.status == "escalated"


class GuardloopClient:
    """
    Minimal client for reporting AI agent decisions to Guardloop.

    Example:
        client = GuardloopClient(
            api_key="gl_live_...",
            base_url="https://guardloop-api.onrender.com",
        )
        result = client.report(
            agent_name="invoice-parser",
            event_type="classification",
            confidence=0.62,
            input_summary="Invoice #4921 from Acme Corp",
            output_summary="Classified as: needs_manual_review",
        )
        if result.escalated:
            print("A human needs to look at this one:", result.reason)
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

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

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
    ) -> IngestResult:
        """
        Reports one agent decision to Guardloop. Guardloop decides, based on
        your organization's configured policy, whether this is safe to
        auto-approve or needs to be escalated to a human. Raises
        GuardloopError if the request fails for any reason, network issues
        included, so a calling agent can decide how to degrade gracefully
        rather than silently assuming "approved."
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

        try:
            response = requests.post(
                f"{self.base_url}/ingest",
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise GuardloopError(f"Could not reach Guardloop: {exc}") from exc

        if response.status_code == 401:
            raise GuardloopError(
                "Guardloop rejected this API key (missing, invalid, or revoked)."
            )

        if not response.ok:
            raise GuardloopError(
                f"Guardloop returned an error: {response.status_code} {response.text}"
            )

        data = response.json()
        return IngestResult(
            event_id=data["event_id"],
            status=data["status"],
            reason=data.get("reason"),
        )