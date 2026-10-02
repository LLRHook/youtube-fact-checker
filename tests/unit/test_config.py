import pytest

from backend.config import PIPELINE_VERSION, Settings, settings, validate_settings


@pytest.mark.parametrize("name,bounds", Settings._ranges.items())
def test_numeric_clamping(name, bounds):
    lo, hi = bounds
    assert getattr(Settings(_env_file=None, **{name: lo - 100}), name) == lo
    assert getattr(Settings(_env_file=None, **{name: hi + 100}), name) == hi


@pytest.mark.parametrize("name", [*Settings._ranges, "SEARCH_CACHE_DAYS"])
@pytest.mark.parametrize("value", ["garbage", "", None])
def test_garbage_uses_default(name, value):
    assert getattr(Settings(_env_file=None, **{name: value}), name) == Settings.model_fields[name].default


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_nonfinite_budget_uses_default(value):
    assert Settings(_env_file=None, DAILY_BUDGET_USD=value).DAILY_BUDGET_USD == 10.0


def test_environment_and_dotenv(monkeypatch, tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("DAILY_VIDEO_LIMIT=bad\nUNRELATED_SETTING=ignored\nBASE_URL=https://example.com///\n")
    monkeypatch.setenv("MAX_CLAIMS_PER_VIDEO", "100")
    config = Settings(_env_file=dotenv)
    assert config.MAX_CLAIMS_PER_VIDEO == 40
    assert config.DAILY_VIDEO_LIMIT == 30
    assert config.BASE_URL == "https://example.com"


@pytest.mark.parametrize("value,expected", [("invalid", "llm_context"), ("web", "web"), ("llm_context", "llm_context")])
def test_search_mode(value, expected):
    assert Settings(_env_file=None, SEARCH_MODE=value).SEARCH_MODE == expected
    assert PIPELINE_VERSION == 2


def test_validate_keys(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(settings, "BRAVE_API_KEY", "")
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY, BRAVE_API_KEY.*Add them to your .env file"):
        validate_settings()
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "dummy")
    monkeypatch.setattr(settings, "BRAVE_API_KEY", "dummy")
    validate_settings()
