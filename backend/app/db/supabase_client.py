from functools import lru_cache
from supabase import create_client, Client
from app.config import settings


@lru_cache
def get_supabase() -> Client:
    """
    Lazily creates and caches the Supabase client on first use, rather than
    at import time. This means the app can start, and individual routes
    that don't touch the database can still run, even if Supabase is
    temporarily unreachable, and it makes the client trivial to mock in
    tests without needing a real connection just to import the app.
    """
    return create_client(settings.supabase_url, settings.supabase_secret_key)