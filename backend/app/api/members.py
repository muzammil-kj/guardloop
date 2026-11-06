from fastapi import APIRouter, Depends, HTTPException

from app.audit import record_audit
from app.auth.actors import get_actor, require_role
from app.db.supabase_client import get_supabase
from app.models import MemberCreate, MemberInfo

router = APIRouter(prefix="/members", tags=["members"])


@router.get("", response_model=list[MemberInfo])
async def list_members(actor: dict = Depends(get_actor)):
    return (
        get_supabase().table("memberships").select("*")
        .eq("organization_id", actor["id"]).order("created_at")
        .execute().data
    )


@router.post("", response_model=MemberInfo)
async def add_member(payload: MemberCreate, actor: dict = Depends(get_actor)):
    """Invites a person by email. They sign in with that email in Supabase Auth and get this role."""
    require_role(actor, "owner")
    email = payload.email.strip().lower()
    if "@" not in email or " " in email:
        raise HTTPException(status_code=400, detail="Enter a valid email address.")

    supabase = get_supabase()
    existing = (
        supabase.table("memberships").select("id")
        .eq("organization_id", actor["id"]).eq("email", email)
        .execute().data
    )
    if existing:
        raise HTTPException(status_code=409, detail="This person is already a member.")

    result = supabase.table("memberships").insert({
        "organization_id": actor["id"],
        "email": email,
        "role": payload.role,
        "display_name": payload.display_name,
    }).execute()
    row = result.data[0]
    record_audit(supabase, actor, "member.added", "membership", row["id"], {"email": email, "role": payload.role})
    return row


@router.delete("/{membership_id}")
async def remove_member(membership_id: int, actor: dict = Depends(get_actor)):
    require_role(actor, "owner")
    supabase = get_supabase()
    rows = (
        supabase.table("memberships").select("*")
        .eq("id", membership_id).eq("organization_id", actor["id"])
        .execute().data
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Member not found.")
    target = rows[0]

    if target["role"] == "owner":
        owners = (
            supabase.table("memberships").select("id")
            .eq("organization_id", actor["id"]).eq("role", "owner")
            .execute().data
        )
        if len(owners) <= 1:
            raise HTTPException(status_code=400, detail="An organization must keep at least one owner.")

    supabase.table("memberships").delete().eq("id", membership_id).execute()
    record_audit(supabase, actor, "member.removed", "membership", membership_id, {"email": target["email"]})
    return {"status": "removed"}