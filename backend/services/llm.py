"""Shared structured Anthropic calls and token cost accounting."""

import json
import logging
from dataclasses import dataclass

import anthropic

from backend.config import settings

logger = logging.getLogger(__name__)
_client: anthropic.AsyncAnthropic | None = None
PRICING = {
    "claude-sonnet-5-5": (2.00, 10.00, 2.50, 0.20),
    "claude-opus-5-5": (4.00, 20.00, 5.00, 0.20),
    "claude-haiku-4-5": (1.00, 5.00, 1.25, 0.10),
}


def get_client():
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY, max_retries=3, timeout=120)
    return _client


async def close_client():
    global _client
    if _client is not None:
        await _client.close()
        _client = None


def cost_usd(model, usage) -> float:
    prices = PRICING.get(model, PRICING["claude-sonnet-5-5"])
    names = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    return sum((getattr(usage, name, 0) or 0) * price for name, price in zip(names, prices, strict=True)) / 1_000_000


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float = 0.0

    def add(self, other):
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read_tokens += other.cache_read_tokens
        self.cache_write_tokens += other.cache_write_tokens
        self.cost_usd += other.cost_usd


@dataclass
class LLMResult:
    data: dict | None
    usage: Usage
    stop_reason: str
    error: str = ""


async def structured_call(
    *, model, effort, system: list[dict], messages: list[dict], schema: dict, max_tokens: int
) -> LLMResult:
    client = get_client()
    kwargs = dict(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
        output_config={"format": {"type": "json_schema", "schema": schema}},
    )
    if model.startswith("claude-haiku"):
        create = client.messages.create
    else:
        create = client.beta.messages.create
        kwargs["output_config"]["effort"] = effort
        kwargs.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
    try:
        response = await create(**kwargs)
    except anthropic.APIError as exc:
        logger.warning("LLM model=%s stop_reason=api_error tokens=0/0 cache_read=0 cache_write=0 cost=0", model)
        return LLMResult(None, Usage(), "", f"api_error: {type(exc).__name__}")
    raw = response.usage
    usage = Usage(
        input_tokens=getattr(raw, "input_tokens", 0) or 0,
        output_tokens=getattr(raw, "output_tokens", 0) or 0,
        cache_read_tokens=getattr(raw, "cache_read_input_tokens", 0) or 0,
        cache_write_tokens=getattr(raw, "cache_creation_input_tokens", 0) or 0,
        cost_usd=cost_usd(model, raw),
    )
    stop = response.stop_reason
    data = None
    error = stop if stop in {"refusal", "max_tokens"} else ""
    if not error:
        body = next((block.text for block in response.content if block.type == "text"), "")
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            error = "invalid_json"
    log = logger.warning if error else logger.info
    log(
        "LLM model=%s stop_reason=%s tokens=%d/%d cache_read=%d cache_write=%d cost=%.6f",
        model,
        error or stop,
        usage.input_tokens,
        usage.output_tokens,
        usage.cache_read_tokens,
        usage.cache_write_tokens,
        usage.cost_usd,
    )
    return LLMResult(data, usage, stop, error)
