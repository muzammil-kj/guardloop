
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.auth.api_keys import hash_key
from app.db.supabase_client import get_supabase


bearer_scheme = HTTPBearer(
    scheme_name="BearerAuth",
    description="Enter your Guardloop API key without the 'Bearer ' prefix.",
    auto_error=False,
)


async def get_current_org(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    """
    Validate the organization API key and return its organization.
    Every protected route must depend on this function.
    """
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header. Expected: Bearer <api_key>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raw_key = credentials.credentials.strip()

    if not raw_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

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
        raise HTTPException(
            status_code=401,
            detail="Invalid or revoked API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    key_row = result.data[0]

    supabase.table("api_keys").update(
        {"last_used_at": "now()"}
    ).eq("id", key_row["id"]).execute()

    return key_row["organizations"]