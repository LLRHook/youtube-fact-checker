import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    BRAVE_API_KEY: str = os.getenv("BRAVE_API_KEY", "")
    MAX_VIDEO_DURATION_SECONDS: int = 600  # 10 minutes
    MAX_CLAIMS_PER_VIDEO: int = 30
    CLAUDE_MODEL: str = "claude-haiku-4-5-20251001"
    SEARCH_RESULTS_PER_CLAIM: int = 5
    FACT_CHECK_CONCURRENCY: int = int(os.getenv("FACT_CHECK_CONCURRENCY", "3"))
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/factchecker.db")
    DAILY_VIDEO_LIMIT: int = int(os.getenv("DAILY_VIDEO_LIMIT", "20"))
    IP_DAILY_LIMIT: int = int(os.getenv("IP_DAILY_LIMIT", "3"))
    QUEUE_INTERVAL_MINUTES: int = int(os.getenv("QUEUE_INTERVAL_MINUTES", "60"))


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
