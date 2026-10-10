import secrets
import hashlib

KEY_PREFIX = "gl_live_"


def generate_api_key() -> tuple[str, str, str]:
    """
    Returns (full_key, display_prefix, hashed_key).

    The full key is shown to the user exactly once, at creation time, and is
    never stored or retrievable again, only its hash is kept in the database.
    """
    random_part = secrets.token_urlsafe(32)
    full_key = f"{KEY_PREFIX}{random_part}"
    hashed = hash_key(full_key)
    display_prefix = full_key[:16] + "..."
    return full_key, display_prefix, hashed


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()