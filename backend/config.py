"""Environment settings for pipeline v2."""

import math
from typing import ClassVar

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PIPELINE_VERSION = 2


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    ANTHROPIC_API_KEY: str = ""
    BRAVE_API_KEY: str = ""
    GOOGLE_FACTCHECK_API_KEY: str = ""
    EXTRACTION_MODEL: str = "claude-sonnet-5-5"
    EXTRACTION_EFFORT: str = "medium"
    VERDICT_MODEL: str = "claude-sonnet-5-5"
    VERDICT_EFFORT: str = "medium"
    SUMMARY_MODEL: str = "claude-sonnet-5-5"
    SUMMARY_EFFORT: str = "low"
    MAX_VIDEO_DURATION_SECONDS: int = 1800
    MAX_CLAIMS_PER_VIDEO: int = 20
    MIN_CHECKWORTHINESS: int = 3
    SEARCH_MODE: str = "llm_context"
    SEARCH_QUERIES_PER_CLAIM: int = 2
    SEARCH_RESULTS_PER_QUERY: int = 5
    EVIDENCE_MAX_SOURCES: int = 8
    SEARCH_CACHE_DAYS: int = 14
    FACT_CHECK_CONCURRENCY: int = 4
    DATABASE_PATH: str = "data/factchecker.db"
    DAILY_VIDEO_LIMIT: int = 30
    IP_DAILY_LIMIT: int = 5
    DAILY_BUDGET_USD: float = 10.0
    QUEUE_INTERVAL_MINUTES: int = 15
    TRANSCRIPT_PROXY_URL: str = ""
    TRUSTED_PROXY_HOPS: int = 1
    CORS_ORIGINS: str = ""
    BASE_URL: str = "https://backend-production-e740.up.railway.app"

    _ranges: ClassVar[dict] = {
        "MAX_VIDEO_DURATION_SECONDS": (60, 7200),
        "MAX_CLAIMS_PER_VIDEO": (1, 40),
        "MIN_CHECKWORTHINESS": (1, 5),
        "SEARCH_QUERIES_PER_CLAIM": (1, 3),
        "SEARCH_RESULTS_PER_QUERY": (1, 20),
        "EVIDENCE_MAX_SOURCES": (3, 12),
        "FACT_CHECK_CONCURRENCY": (1, 10),
        "DAILY_VIDEO_LIMIT": (1, 1000),
        "IP_DAILY_LIMIT": (1, 100),
        "DAILY_BUDGET_USD": (0.5, 1000),
        "QUEUE_INTERVAL_MINUTES": (1, 1440),
        "TRUSTED_PROXY_HOPS": (0, 5),
    }

    @field_validator(*_ranges, "SEARCH_CACHE_DAYS", mode="before")
    @classmethod
    def clamp_number(cls, value, info):
        default = cls.model_fields[info.field_name].default
        try:
            number = float(value) if isinstance(default, float) else int(value)
            if not math.isfinite(number):
                number = default
        except (TypeError, ValueError, OverflowError):
            number = default
        bounds = cls._ranges.get(info.field_name)
        return max(bounds[0], min(bounds[1], number)) if bounds else number

    @field_validator("SEARCH_MODE", mode="before")
    @classmethod
    def search_mode(cls, value):
        return value if value in {"llm_context", "web"} else "llm_context"

    @field_validator("BASE_URL")
    @classmethod
    def base_url(cls, value):
        return value.rstrip("/")


settings = Settings()


def validate_settings():
    missing = [name for name in ("ANTHROPIC_API_KEY", "BRAVE_API_KEY") if not getattr(settings, name)]
    if missing:
        raise RuntimeError(
            f"Missing required environment variable(s): {', '.join(missing)}. Add them to your .env file."
        )
