"""Thin async OpenRouter client with retry/backoff and cost accounting."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504, 529}


class ApiError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, retryable: bool = False) -> None:
        super().__init__(message)
        self.status = status
        self.retryable = retryable


@dataclass(frozen=True)
class ChatResult:
    model: str
    text: str
    reasoning: str
    cost_usd: float
    prompt_tokens: int
    completion_tokens: int
    latency_s: float
    finish_reason: str


class OpenRouterClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 180.0,
        max_retries: int = 3,
        backoff_base: float = 2.0,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self._sleep = sleep
        self._http = httpx.AsyncClient(
            timeout=timeout,
            transport=transport,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "X-Title": "Blade Runner Constitution Study",
            },
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> OpenRouterClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def complete(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        temperature: float,
        max_tokens: int,
        seed: int | None = None,
        top_p: float | None = None,
    ) -> ChatResult:
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if seed is not None:
            body["seed"] = seed
        if top_p is not None:
            body["top_p"] = top_p

        last_error: ApiError | None = None
        for attempt in range(self.max_retries + 1):
            if attempt:
                await self._sleep(self.backoff_base * (2 ** (attempt - 1)))
            try:
                loop = asyncio.get_running_loop()
                started = loop.time()
                response = await self._http.post(
                    f"{self.base_url}/chat/completions", json=body
                )
                latency = loop.time() - started
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = ApiError(f"transport error: {exc}", retryable=True)
                continue

            if response.status_code != 200:
                last_error = ApiError(
                    _error_message(response),
                    status=response.status_code,
                    retryable=response.status_code in RETRYABLE_STATUS,
                )
                if not last_error.retryable:
                    raise last_error
                continue

            try:
                return _parse_chat_response(response, model, latency)
            except ApiError as exc:
                if not exc.retryable:
                    raise
                last_error = exc
                continue

        assert last_error is not None
        raise last_error


def _error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"HTTP {response.status_code}: {response.text[:300]}"
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict) and error.get("message"):
            return f"HTTP {response.status_code}: {error['message']}"
        if payload.get("message"):
            return f"HTTP {response.status_code}: {payload['message']}"
    return f"HTTP {response.status_code}: {response.text[:300]}"


def _parse_chat_response(response: httpx.Response, model: str, latency: float) -> ChatResult:
    try:
        payload = response.json()
    except ValueError as exc:
        raise ApiError("response was not JSON", status=response.status_code) from exc

    choices = payload.get("choices") or []
    if not choices:
        error = payload.get("error")
        detail = ""
        retryable = False
        if isinstance(error, dict):
            detail = f": {error.get('message', '')}".rstrip(": ")
            retryable = True
        raise ApiError(
            f"response contained no choices{detail}",
            status=response.status_code,
            retryable=retryable,
        )
    choice = choices[0]
    message = choice.get("message") or {}
    usage = payload.get("usage") or {}
    return ChatResult(
        model=str(payload.get("model") or model),
        text=message.get("content") or "",
        reasoning=message.get("reasoning") or message.get("reasoning_content") or "",
        cost_usd=float(usage.get("cost") or 0.0),
        prompt_tokens=int(usage.get("prompt_tokens") or 0),
        completion_tokens=int(usage.get("completion_tokens") or 0),
        latency_s=float(latency),
        finish_reason=str(choice.get("finish_reason") or "unknown"),
    )
