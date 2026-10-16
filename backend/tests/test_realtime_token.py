from types import SimpleNamespace
from unittest.mock import patch

import jwt
import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_org
from app.main import app
from app.realtime.token import RealtimeNotConfigured, mint_realtime_token

SECRET = "test-jwt-secret-that-is-at-least-32-bytes-long"


def with_secret(secret):
    return patch(
        "app.realtime.token.settings", SimpleNamespace(supabase_jwt_secret=secret)
    )


def test_token_carries_the_organization_claim():
    with with_secret(SECRET):
        token = mint_realtime_token("org-123")
    decoded = jwt.decode(
        token, SECRET, algorithms=["HS256"], audience="authenticated"
    )
    assert decoded["organization_id"] == "org-123"
    assert decoded["role"] == "authenticated"
    assert decoded["exp"] > decoded["iat"]


def test_token_signed_with_a_different_secret_is_rejected():
    with with_secret(SECRET):
        token = mint_realtime_token("org-123")
    with pytest.raises(jwt.InvalidTokenError):
        jwt.decode(
            token,
            "a-completely-different-secret-of-32-bytes!!",
            algorithms=["HS256"],
            audience="authenticated",
        )


def test_minting_without_a_secret_raises():
    with with_secret(""):
        with pytest.raises(RealtimeNotConfigured):
            mint_realtime_token("org-123")


def test_endpoint_returns_a_token_for_the_callers_org():
    app.dependency_overrides[get_current_org] = lambda: {"id": "org-abc"}
    try:
        with with_secret(SECRET):
            response = TestClient(app).post("/organizations/me/realtime-token")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    decoded = jwt.decode(
        body["token"], SECRET, algorithms=["HS256"], audience="authenticated"
    )
    assert decoded["organization_id"] == "org-abc"


def test_endpoint_returns_503_when_realtime_is_not_configured():
    app.dependency_overrides[get_current_org] = lambda: {"id": "org-abc"}
    try:
        with with_secret(""):
            response = TestClient(app).post("/organizations/me/realtime-token")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503


def test_endpoint_requires_an_api_key():
    response = TestClient(app).post("/organizations/me/realtime-token")
    assert response.status_code == 401
