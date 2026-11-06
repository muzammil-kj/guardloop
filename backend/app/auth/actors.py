"""
Who is making a request?

Two kinds of caller:
  - Services (n8n, the SDK, scripts) use an organization API key that starts with gl_live_.
    They act as the organization's owner, exactly as before.
  - People (reviewers) sign in with Supabase Auth. Their access token is verified by
    Supabase itself, then matched to a membership row that sets their role.

Routes that only need "someone in this organization" depend on get_actor. Routes
that change settings or keys still depend on the API key (get_current_org), so a
reviewer can't alter policies through a route that doesn't check roles.
"""
import requests
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from starlette.concurrency import run_in_threadpool

from app.auth.dependencies import bearer_scheme, get_current_org
from app.config import settings
from app.db.supabase_client import get_supabase

API_KEY_PREFIX = "gl_live_"
ROLE_RANK = {"viewer": 1, "reviewer": 2, "owner": 3}


def verify_user_token(token: str) -> dict:
    if not settings.supabase_publishable_key:
        raise HTTPException(status_code=401, detail="Reviewer sign-in is not configured on this server.")
    try:
        response = requests.get(
            f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
            headers={"Authorization": f"Bearer {token}", "apikey": settings.supabase_publishable_key},
            timeout=10,
        )
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="Could not verify sign-in right now. Try again.") from None

    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Your sign-in has expired. Sign in again.")
    user = response.json()
    if not user.get("email") or not user.get("email_confirmed_at"):
        raise HTTPException(status_code=403, detail="Confirm your email address before using Guardloop.")
    return user


def find_membership(supabase, user: dict) -> dict:
    email = user["email"].strip().lower()
    rows = supabase.table("memberships").select("*").eq("email", email).order("created_at").execute().data
    if not rows:
        raise HTTPException(
            status_code=403,
            detail="Your account is not a member of a Guardloop organization. Ask the owner to invite you.",
        )
    membership = rows[0]
    if membership.get("user_id") is None:
        # First sign-in: link this account to the invitation.
        supabase.table("memberships").update({"user_id": user["id"]}).eq("id", membership["id"]).execute()
        membership["user_id"] = user["id"]
    elif membership["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="This membership belongs to a different account.")
    return membership


async def get_actor(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials.strip()
    if token.startswith(API_KEY_PREFIX):
        org = await get_current_org(credentials)
        return {**org, "actor_name": "API key", "actor_type": "api_key", "actor_role": "owner"}

    user = await run_in_threadpool(verify_user_token, token)
    supabase = get_supabase()
    membership = await run_in_threadpool(find_membership, supabase, user)
    orgs = supabase.table("organizations").select("*").eq("id", membership["organization_id"]).execute().data
    if not orgs:
        raise HTTPException(status_code=403, detail="Your organization no longer exists.")
    return {
        **orgs[0],
        "actor_name": membership.get("display_name") or user["email"],
        "actor_email": user["email"],
        "actor_type": "user",
        "actor_role": membership["role"],
    }


def require_role(actor: dict, minimum: str) -> None:
    role = actor.get("actor_role", "owner")
    if ROLE_RANK.get(role, 0) < ROLE_RANK[minimum]:
        raise HTTPException(status_code=403, detail=f"This action needs the '{minimum}' role.")