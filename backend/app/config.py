from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str
    supabase_secret_key: str
    default_confidence_threshold: float = 0.75

    # Supabase project JWT secret (Project Settings -> API / JWT Keys). Used to
    # sign short-lived tokens that let the dashboard authenticate to Supabase
    # Realtime, scoped to one organization via row-level security.
    # Optional on purpose: if unset, only the realtime-token endpoint reports
    # "not configured" (503) and the dashboard falls back to polling.
    supabase_jwt_secret: str = ""

    # A secret you choose. Your external cron service must send it in the
    # X-Internal-Secret header to trigger alert checks. If unset, the internal
    # endpoint refuses every request (503) instead of accepting an empty secret.
    internal_cron_secret: str = ""

    # Browser origins allowed to call the API: comma-separated. The default is
    # the production dashboard plus local development. Add a Vercel preview URL
    # here only when you need to test against it.
    cors_allowed_origins: str = "https://guardloop-iota.vercel.app,http://localhost:3000"

    # Phase 5, the LLM judge. Optional: with no key the judge simply stays
    # unavailable ("not configured") and nothing else is affected.
    gemini_api_key: str = ""
    judge_model: str = "gemini-3.5-flash-lite"


settings = Settings()