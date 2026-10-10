from fastapi import Header, HTTPException
from app.auth.api_keys import hash_key
from app.db.supabase_client import get_supabase


async def get_current_org(authorization: str = Header(None)) -> dict:
    """
    Every protected route depends on this. It reads the Authorization header,
    verifies the API key against its stored hash, and returns the calling
    organization. Nothing downstream ever sees another org's data, because
    every query in this app filters by the organization_id this returns.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or malformed Authorization header. Expected: Bearer <api_key>",
        )

    raw_key = authorization.removeprefix("Bearer ").strip()
    hashed = hash_key(raw_key)
    supabase = get_supabase()

    result = (
        supabase.table("api_keys")
        .select("*, organizations(*)")
        .eq("key_hash", hashed)
        .eq("revoked", False)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key.")

    key_row = result.data[0]
    supabase.table("api_keys").update({"last_used_at": "now()"}).eq(
        "id", key_row["id"]
    ).execute()

    return key_row["organizations"]