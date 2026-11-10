"""Tests for the claude -p CLI adapter (no subprocess in tests)."""

from __future__ import annotations

import json

import pytest

from constitution.claude_cli import ClaudeChatClient, ClaudeCli, ClaudeCliError

OK = {
    "result": "答案",
    "total_cost_usd": 0.0123,
    "duration_ms": 5000,
    "is_error": False,
    "session_id": "s1",
}


class Runner:
    def __init__(self, payload: dict | None = None, code: int = 0, stdout: str | None = None) -> None:
        self.calls: list[tuple[list[str], str]] = []
        self.payload = payload if payload is not None else OK
        self.code = code
        self.stdout = stdout

    async def __call__(
        self, argv: list[str], cwd: str, env: dict[str, str], timeout: float
    ) -> tuple[int, str, str]:
        self.calls.append((argv, cwd))
        out = self.stdout if self.stdout is not None else json.dumps(self.payload)
        return self.code, out, ""


async def test_parses_json_and_builds_neutral_argv() -> None:
    runner = Runner()
    cli = ClaudeCli(runner=runner, model="sonnet")
    result = await cli.complete("SYSTEM", "USER")
    assert result.text == "答案"
    assert result.cost_usd == pytest.approx(0.0123)
    argv, _cwd = runner.calls[0]
    assert "--system-prompt" in argv and "SYSTEM" in argv
    assert "--exclude-dynamic-system-prompt-sections" in argv
    assert "--setting-sources" in argv
    assert "--output-format" in argv and "json" in argv
    assert "--model" in argv and "sonnet" in argv
    assert argv[-1] == "USER"


async def test_nonzero_exit_raises() -> None:
    cli = ClaudeCli(runner=Runner(code=2, stdout=""))
    with pytest.raises(ClaudeCliError, match="exit"):
        await cli.complete("s", "u")


async def test_error_flag_raises() -> None:
    payload = dict(OK, is_error=True, result="")
    cli = ClaudeCli(runner=Runner(payload=payload))
    with pytest.raises(ClaudeCliError, match="error"):
        await cli.complete("s", "u")


async def test_bad_json_raises() -> None:
    cli = ClaudeCli(runner=Runner(stdout="not json"))
    with pytest.raises(ClaudeCliError, match="json"):
        await cli.complete("s", "u")


async def test_chat_client_adapter() -> None:
    cli = ClaudeCli(runner=Runner())
    adapter = ClaudeChatClient(cli)
    result = await adapter.complete(
        "anthropic/claude-sonnet-5.5",
        [
            {"role": "system", "content": "SYS"},
            {"role": "user", "content": "USR"},
        ],
        temperature=0.0,
        max_tokens=100,
    )
    assert result.text == "答案"
    assert result.finish_reason == "stop"
    assert result.cost_usd == pytest.approx(0.0123)
