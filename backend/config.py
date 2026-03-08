import os
from dotenv import load_dotenv

load_dotenv()


def _int_env(name: str, default: int, lo: int = 0, hi: int = 0) -> int:
    """Read an integer from an env var with fallback and optional clamping."""
    try:
        val = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        val = default
    if lo < hi:
        val = max(lo, min(hi, val))
    return val


class Settings:
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    BRAVE_API_KEY: str = os.getenv("BRAVE_API_KEY", "")
    MAX_VIDEO_DURATION_SECONDS: int = 600  # 10 minutes
    MAX_CLAIMS_PER_VIDEO: int = 30
    CLAUDE_MODEL: str = "claude-haiku-4-5-20251001"
    SEARCH_RESULTS_PER_CLAIM: int = 5
    FACT_CHECK_CONCURRENCY: int = _int_env("FACT_CHECK_CONCURRENCY", 3, 1, 10)
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/factchecker.db")
    DAILY_VIDEO_LIMIT: int = _int_env("DAILY_VIDEO_LIMIT", 20, 1, 1000)
    IP_DAILY_LIMIT: int = _int_env("IP_DAILY_LIMIT", 3, 1, 100)
    QUEUE_INTERVAL_MINUTES: int = _int_env("QUEUE_INTERVAL_MINUTES", 60, 1, 1440)
    BASE_URL: str = os.getenv("BASE_URL", "https://backend-production-e740.up.railway.app").rstrip("/")


settings = Settings()


def validate_settings():
    """Raise on missing required API keys. Call once at startup."""
    missing = []
    if not settings.ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    if not settings.BRAVE_API_KEY:
        missing.append("BRAVE_API_KEY")
    if missing:
        raise RuntimeError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Add them to your .env file."
        )
