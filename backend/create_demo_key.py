from app.auth.api_keys import generate_api_key
from app.db.supabase_client import get_supabase

DEMO_ORG_ID = "00000000-0000-0000-0000-000000000001"

full_key, prefix, hashed = generate_api_key()
get_supabase().table("api_keys").insert({
    "organization_id": DEMO_ORG_ID,
    "key_hash": hashed,
    "key_prefix": prefix,
    "label": "Demo key",
}).execute()
print("Demo key (shown once, save it):", full_key)