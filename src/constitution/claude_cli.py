"""Adapter for the local `claude -p` CLI, used when the API is unreachable.

Claude Code's default system prompt is a coding-agent persona, which would
contaminate a constitution instrument. This wrapper *replaces* it with the
study's neutral prompt, disables tools, and runs in an empty working directory.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from constitution.client import ChatResult

DISALLOWED_TOOLS = "Bash,Edit,Write,Read,Glob,Grep,WebFetch,WebSearch,Task,NotebookEdit"


class ClaudeCliError(RuntimeError):
    pass


@dataclass(frozen=True)
class ClaudeResult:
    text: str
    cost_usd: float
    duration_ms: int
    is_error: bool
    session_id: str


Runner = Callable[[list[str], str, dict[str, str], float], Awaitable[tuple[int, str, str]]]


async def _default_runner(
    argv: list[str], cwd: str, env: dict[str, str], timeout: float
) -> tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        *argv,
        cwd=cwd,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError:
        process.kill()
        await process.wait()
        return 124, "", "timeout"
    return (
        process.returncode or 0,
        stdout.decode("utf-8", "replace"),
        stderr.decode("utf-8", "replace"),
    )


class ClaudeCli:
    def __init__(
        self,
        *,
        binary: str = "claude",
        model: str = "sonnet",
        timeout: float = 240.0,
        max_turns: int = 1,
        workdir: str | None = None,
        runner: Runner | None = None,
    ) -> None:
        self.binary = binary
        self.model = model
        self.timeout = timeout
        self.max_turns = max_turns
        self.workdir = workdir or tempfile.mkdtemp(prefix="br-claude-")
        self._runner = runner or _default_runner
        self._env = {
            **os.environ,
            "LANG": "en_US.UTF-8",
            "LC_ALL": "en_US.UTF-8",
            "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
        }

    def build_argv(self, system: str, user: str) -> list[str]:
        return [
            self.binary,
            "--model",
            self.model,
            "--system-prompt",
            system,
            "--exclude-dynamic-system-prompt-sections",
            "--setting-sources",
            "",
            "--disallowedTools",
            DISALLOWED_TOOLS,
            "--output-format",
            "json",
            "--max-turns",
            str(self.max_turns),
            "-p",
            user,
        ]

    async def complete(self, system: str, user: str) -> ClaudeResult:
        argv = self.build_argv(system, user)
        code, stdout, stderr = await self._runner(argv, self.workdir, self._env, self.timeout)
        if code != 0:
            raise ClaudeCliError(f"claude exited with exit code {code}: {stderr[:300]}")
        try:
            payload = json.loads(stdout.strip().splitlines()[-1])
        except (ValueError, IndexError) as exc:
            raise ClaudeCliError(f"claude returned non-json output: {stdout[:200]}") from exc
        if payload.get("is_error"):
            raise ClaudeCliError(f"claude reported an error: {str(payload.get('result'))[:200]}")
        text = payload.get("result") or ""
        if not text.strip():
            raise ClaudeCliError("claude returned an empty result")
        return ClaudeResult(
            text=text,
            cost_usd=float(payload.get("total_cost_usd") or 0.0),
            duration_ms=int(payload.get("duration_ms") or 0),
            is_error=False,
            session_id=str(payload.get("session_id") or ""),
        )


class ClaudeChatClient:
    """Drop-in ChatClient so the existing Collector can drive Claude."""

    def __init__(self, cli: ClaudeCli) -> None:
        self.cli = cli

    async def complete(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
        max_tokens: int = 1000,
        seed: int | None = None,
        top_p: float | None = None,
        provider: dict[str, object] | None = None,
    ) -> ChatResult:
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        user = next((m["content"] for m in messages if m["role"] == "user"), "")
        result = await self.cli.complete(system, user)
        return ChatResult(
            model=model,
            text=result.text,
            reasoning="",
            cost_usd=result.cost_usd,
            prompt_tokens=0,
            completion_tokens=0,
            latency_s=result.duration_ms / 1000,
            finish_reason="stop",
        )

    async def aclose(self) -> None:  # pragma: no cover - symmetry with OpenRouterClient
        return None
