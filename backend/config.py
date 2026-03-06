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
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/factchecker.db")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")
    SESSION_SECRET: str = os.getenv("SESSION_SECRET", "change-me-in-production")


settings = Settings()
