import time

import jwt

from app.config import settings

REALTIME_TOKEN_TTL_SECONDS = 60 * 60  # 1 hour; the dashboard refreshes it


class RealtimeNotConfigured(Exception):
    """Raised when SUPABASE_JWT_SECRET has not been set."""


def mint_realtime_token(organization_id: str) -> str:
    """
    Signs a short-lived JWT with the Supabase project's JWT secret, carrying a
    custom organization_id claim. The dashboard uses it ONLY to authenticate
    its direct Supabase Realtime connection; row-level-security policies on
    agent_events and escalations compare that claim to each row's
    organization_id, so a connection can only ever see its own org's rows.

    It is never accepted by Guardloop's own REST API, which uses API keys.
    """
    secret = settings.supabase_jwt_secret
    if not secret:
        raise RealtimeNotConfigured("SUPABASE_JWT_SECRET is not set.")

    now = int(time.time())
    payload = {
        "aud": "authenticated",
        "role": "authenticated",
        "sub": organization_id,
        "organization_id": organization_id,
        "iat": now,
        "exp": now + REALTIME_TOKEN_TTL_SECONDS,
    }
    return jwt.encode(payload, secret, algorithm="HS256")
