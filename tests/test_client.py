"""Tests for the OpenRouter client (mocked transport, no network)."""

from __future__ import annotations

import json

import httpx
import pytest

from constitution.client import ApiError, OpenRouterClient

URL = "https://openrouter.ai/api/v1/chat/completions"


def _ok(text: str = "答案", cost: float = 0.001) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": "test/model",
            "choices": [{"message": {"content": text, "reasoning": "thinking"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "cost": cost},
        },
    )


class SleepSpy:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


async def test_successful_completion_parses_payload() -> None:
    transport = httpx.MockTransport(lambda request: _ok("hello", cost=0.0025))
    client = OpenRouterClient("k", transport=transport)
    result = await client.complete("test/model", [{"role": "user", "content": "hi"}], temperature=0.5, max_tokens=100)
    assert result.text == "hello"
    assert result.reasoning == "thinking"
    assert result.cost_usd == pytest.approx(0.0025)
    assert result.prompt_tokens == 10 and result.completion_tokens == 20
    assert result.finish_reason == "stop"
    await client.aclose()


async def test_retries_on_429_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={"error": {"message": "rate limited"}})
        return _ok()

    sleep = SleepSpy()
    client = OpenRouterClient("k", transport=httpx.MockTransport(handler), sleep=sleep, backoff_base=2.0)
    result = await client.complete("test/model", [{"role": "user", "content": "hi"}], temperature=0, max_tokens=10)
    assert result.text == "答案"
    assert calls["n"] == 2
    assert sleep.calls == [2.0]


async def test_exhausted_retries_raise_retryable_error() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(503, text="down"))
    client = OpenRouterClient(
        "k", transport=transport, sleep=SleepSpy(), max_retries=2, backoff_base=1.0
    )
    with pytest.raises(ApiError) as exc:
        await client.complete("test/model", [{"role": "user", "content": "hi"}], temperature=0, max_tokens=10)
    assert exc.value.retryable is True
    assert exc.value.status == 503


async def test_client_error_is_not_retried() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(400, json={"error": {"message": "bad model"}})

    client = OpenRouterClient("k", transport=httpx.MockTransport(handler), sleep=SleepSpy())
    with pytest.raises(ApiError) as exc:
        await client.complete("test/model", [{"role": "user", "content": "hi"}], temperature=0, max_tokens=10)
    assert exc.value.retryable is False
    assert calls["n"] == 1


async def test_timeout_is_retried() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ReadTimeout("slow", request=request)
        return _ok()

    client = OpenRouterClient("k", transport=httpx.MockTransport(handler), sleep=SleepSpy())
    result = await client.complete("test/model", [{"role": "user", "content": "hi"}], temperature=0, max_tokens=10)
    assert result.text == "答案"
    assert calls["n"] == 2


async def test_null_content_is_empty_string() -> None:
    response = httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": None}, "finish_reason": "length"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost": 0.0},
        },
    )
    client = OpenRouterClient("k", transport=httpx.MockTransport(lambda request: response))
    result = await client.complete("test/model", [{"role": "user", "content": "hi"}], temperature=0, max_tokens=1)
    assert result.text == ""
    assert result.finish_reason == "length"


async def test_request_body_contains_sampling_params() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return _ok()

    client = OpenRouterClient("k", transport=httpx.MockTransport(handler))
    await client.complete(
        "test/model", [{"role": "user", "content": "hi"}], temperature=0.7, max_tokens=42, seed=9, top_p=0.9
    )
    assert captured["model"] == "test/model"
    assert captured["temperature"] == 0.7
    assert captured["max_tokens"] == 42
    assert captured["seed"] == 9
    assert captured["top_p"] == 0.9
    await client.aclose()


async def test_200_with_upstream_error_is_retried() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(
                200,
                json={"error": {"message": "provider at capacity", "code": 502}},
            )
        return _ok()

    client = OpenRouterClient("k", transport=httpx.MockTransport(handler), sleep=SleepSpy())
    result = await client.complete("test/model", [{"role": "user", "content": "hi"}], temperature=0, max_tokens=10)
    assert result.text == "答案"
    assert calls["n"] == 2
    await client.aclose()
