from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import anthropic
import httpx2
import pytest

from backend.services import llm


@pytest.mark.parametrize(
    "model,expected",
    [
        ("claude-sonnet-5-5", 14.7),
        ("claude-opus-5-5", 29.2),
        ("claude-haiku-4-5", 7.35),
        ("unknown", 14.7),
    ],
)
def test_cost_usd(model, expected):
    usage = SimpleNamespace(
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cache_creation_input_tokens=1_000_000,
        cache_read_input_tokens=1_000_000,
    )
    assert llm.cost_usd(model, usage) == pytest.approx(expected)


def test_none_tokens_and_addition():
    assert (
        llm.cost_usd("unknown", SimpleNamespace(input_tokens=None, output_tokens=100, cache_read_input_tokens=None))
        == 0.001
    )
    usage = llm.Usage(1, 2, 3, 4, 0.5)
    usage.add(llm.Usage(10, 20, 30, 40, 0.25))
    assert usage == llm.Usage(11, 22, 33, 44, 0.75)


@pytest.fixture
def mocked_client(monkeypatch):
    client = SimpleNamespace(
        beta=SimpleNamespace(messages=SimpleNamespace(create=AsyncMock())), messages=SimpleNamespace(create=AsyncMock())
    )
    monkeypatch.setattr(llm, "get_client", lambda: client)
    return client


async def call(model="claude-sonnet-5-5"):
    return await llm.structured_call(
        model=model,
        effort="medium",
        system=[{"type": "text", "text": "rubric"}],
        messages=[{"role": "user", "content": "claim"}],
        schema={"type": "object"},
        max_tokens=100,
    )


@pytest.mark.parametrize(
    "stop,body,error",
    [
        ("end_turn", '{"answer": true}', ""),
        ("refusal", "{}", "refusal"),
        ("max_tokens", "{", "max_tokens"),
        ("end_turn", "invalid", "invalid_json"),
    ],
)
async def test_response_handling(mocked_client, stop, body, error):
    mocked_client.beta.messages.create.return_value = SimpleNamespace(
        stop_reason=stop,
        usage=SimpleNamespace(
            input_tokens=100, output_tokens=20, cache_creation_input_tokens=40, cache_read_input_tokens=10
        ),
        content=[SimpleNamespace(type="thinking"), SimpleNamespace(type="text", text=body)],
    )
    result = await call()
    assert result.error == error
    assert result.data == (None if error else {"answer": True})
    assert result.usage == llm.Usage(100, 20, 10, 40, pytest.approx(0.000502))
    kwargs = mocked_client.beta.messages.create.call_args.kwargs
    assert kwargs["fallbacks"] == "default"
    assert kwargs["betas"] == ["server-side-fallback-2026-07-01"]
    assert kwargs["output_config"]["effort"] == "medium"
    assert "thinking" not in kwargs and "temperature" not in kwargs


@pytest.mark.parametrize("kind", ["base", "connection", "status"])
async def test_api_errors(mocked_client, kind):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    error = {
        "base": anthropic.APIError("failure", request, body=None),
        "connection": anthropic.APIConnectionError(request=request),
        "status": anthropic.APIStatusError("failure", response=httpx2.Response(500, request=request), body=None),
    }[kind]
    mocked_client.beta.messages.create.side_effect = error
    result = await call()
    assert result.data is None and result.usage == llm.Usage()
    assert result.error == f"api_error: {type(error).__name__}"


async def test_haiku_omits_unsupported_parameters(mocked_client):
    mocked_client.messages.create.return_value = SimpleNamespace(
        stop_reason="end_turn", usage=SimpleNamespace(), content=[SimpleNamespace(type="text", text="{}")]
    )
    assert (await call("claude-haiku-4-5")).data == {}
    kwargs = mocked_client.messages.create.call_args.kwargs
    assert not {"betas", "fallbacks", "thinking", "temperature"} & kwargs.keys()
    assert "effort" not in kwargs["output_config"]
    mocked_client.beta.messages.create.assert_not_called()


async def test_client_lifecycle(monkeypatch):
    client = SimpleNamespace(close=AsyncMock())
    constructor = Mock(return_value=client)
    monkeypatch.setattr(llm, "_client", None)
    monkeypatch.setattr(llm.anthropic, "AsyncAnthropic", constructor)
    assert llm.get_client() is llm.get_client() is client
    constructor.assert_called_once_with(api_key=llm.settings.ANTHROPIC_API_KEY, max_retries=3, timeout=120)
    await llm.close_client()
    client.close.assert_awaited_once()
    assert llm._client is None
