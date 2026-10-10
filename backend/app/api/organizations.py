from fastapi import APIRouter, Depends, HTTPException

from app.db.supabase_client import get_supabase
from app.auth.api_keys import generate_api_key
from app.auth.dependencies import get_current_org
from app.models import (
    CreateOrganization,
    OrganizationCreated,
    CreateApiKey,
    ApiKeyCreated,
    ApiKeyInfo,
)

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("", response_model=OrganizationCreated)
async def create_organization(payload: CreateOrganization):
    """
    Signup: no auth required here, this is how a new org is born. Issues
    the organization's first API key immediately.
    """
    supabase = get_supabase()
    org = supabase.table("organizations").insert({"name": payload.name}).execute()
    org_id = org.data[0]["id"]

    full_key, prefix, hashed = generate_api_key()
    supabase.table("api_keys").insert({
        "organization_id": org_id,
        "key_hash": hashed,
        "key_prefix": prefix,
        "label": "Default key",
    }).execute()

    return OrganizationCreated(organization_id=org_id, name=payload.name, api_key=full_key)


@router.get("/me")
async def get_my_organization(org: dict = Depends(get_current_org)):
    return org


@router.post("/me/api-keys", response_model=ApiKeyCreated)
async def create_api_key(payload: CreateApiKey, org: dict = Depends(get_current_org)):
    supabase = get_supabase()
    full_key, prefix, hashed = generate_api_key()
    result = supabase.table("api_keys").insert({
        "organization_id": org["id"],
        "key_hash": hashed,
        "key_prefix": prefix,
        "label": payload.label,
    }).execute()
    row = result.data[0]
    return ApiKeyCreated(id=row["id"], key_prefix=prefix, api_key=full_key, label=payload.label)


@router.get("/me/api-keys", response_model=list[ApiKeyInfo])
async def list_api_keys(org: dict = Depends(get_current_org)):
    supabase = get_supabase()
    result = (
        supabase.table("api_keys")
        .select("id, key_prefix, label, revoked, last_used_at, created_at")
        .eq("organization_id", org["id"])
        .execute()
    )
    return result.data


@router.delete("/me/api-keys/{key_id}")
async def revoke_api_key(key_id: int, org: dict = Depends(get_current_org)):
    supabase = get_supabase()
    result = (
        supabase.table("api_keys")
        .update({"revoked": True})
        .eq("id", key_id)
        .eq("organization_id", org["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"status": "revoked"}