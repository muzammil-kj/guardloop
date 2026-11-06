from fastapi import APIRouter, Depends

from app.auth.actors import get_actor

router = APIRouter(tags=["me"])


@router.get("/me")
async def who_am_i(actor: dict = Depends(get_actor)):
    """Tells the dashboard who is signed in and what they may do."""
    return {
        "organization": {"id": actor["id"], "name": actor.get("name")},
        "actor_name": actor["actor_name"],
        "actor_type": actor["actor_type"],
        "role": actor["actor_role"],
    }