from app.config import settings


def resolve_policy(supabase, organization_id: str, agent_name: str) -> dict:
    """
    Three-tier fallback for finding the right policy to apply:
    1. An exact policy configured for this specific agent
    2. The organization's own default policy (agent_name is null)
    3. The hardcoded global default, if the org hasn't configured anything

    This means a brand new organization works out of the box with sane
    defaults, but any team can override behavior per-agent, or set their
    own org-wide default, without touching code or redeploying anything.
    """
    agent_specific = (
        supabase.table("agent_policies")
        .select("*")
        .eq("organization_id", organization_id)
        .eq("agent_name", agent_name)
        .execute()
    )
    if agent_specific.data:
        return agent_specific.data[0]

    org_default = (
        supabase.table("agent_policies")
        .select("*")
        .eq("organization_id", organization_id)
        .is_("agent_name", "null")
        .execute()
    )
    if org_default.data:
        return org_default.data[0]

    return {
        "confidence_threshold": settings.default_confidence_threshold,
        "hard_escalate_event_types": [],
    }