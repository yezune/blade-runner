#!/usr/bin/env python
"""Follow-up studies: Q1 (Claude validity), Q5 (country swap), Q6 (replication),
Q7 (serving path). Collection only; coding is in run_followup_judge.py.

    uv run python scripts/run_followup.py --study q1
    uv run python scripts/run_followup.py --study q5
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from constitution.claude_cli import ClaudeChatClient, ClaudeCli  # noqa: E402
from constitution.client import OpenRouterClient  # noqa: E402
from constitution.collect import Collector, Task  # noqa: E402
from constitution.config import load_model_registry  # noqa: E402
from constitution.followup import loyalty_paraphrases, petition_prompt  # noqa: E402
from constitution.questions import (  # noqa: E402
    PROBE_SYSTEM_ZH,
    PROBES,
    build_scale_messages,
    likert_blocks,
)

CLAUDE_SLUG = "anthropic/claude-sonnet-5.5"
RES = ROOT / "results" / "followup"
PROVIDERS = ("wafer", "novita", "siliconflow")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", required=True, choices=["q1", "q5", "q6", "q7"])
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--budget", type=float, default=8.0)
    parser.add_argument("--models", default=str(ROOT / "config" / "models.yaml"))
    return parser.parse_args()


def task(
    model: str,
    qid: str,
    messages: tuple[dict[str, str], ...],
    *,
    idx: int = 0,
    instrument: str = "probe",
    lang: str = "zh",
    temperature: float = 0.8,
    max_tokens: int = 6000,
    meta: dict | None = None,
) -> Task:
    return Task(
        model=model,
        instrument=instrument,
        question_id=qid,
        language=lang,
        sample_idx=idx,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        meta=meta or {},
    )


def q1_tasks() -> list[Task]:
    out: list[Task] = []
    for block_idx, block in enumerate(likert_blocks(), start=1):
        messages = tuple(build_scale_messages(block, language="zh"))
        meta = {
            "block": block_idx,
            "items": [
                {"id": i.id, "dimension": i.dimension, "text_zh": i.text_zh} for i in block
            ],
        }
        for idx in range(2):
            out.append(
                task(
                    CLAUDE_SLUG,
                    f"B{block_idx}",
                    messages,
                    idx=idx,
                    instrument="scale",
                    temperature=0.2,
                    max_tokens=3000,
                    meta=meta,
                )
            )
    for probe in PROBES:
        langs = ("zh", "en") if probe.bilingual else ("zh",)
        for lang in langs:
            text = probe.text_zh if lang == "zh" else (probe.text_en or "")
            messages = (
                {"role": "system", "content": PROBE_SYSTEM_ZH},
                {"role": "user", "content": text},
            )
            for idx in range(3):
                out.append(
                    task(
                        CLAUDE_SLUG,
                        probe.id,
                        messages,
                        idx=idx,
                        lang=lang,
                        meta={"question": text, "tags": list(probe.tags)},
                    )
                )
    return out


def q5_tasks(models: list[str]) -> list[Task]:
    out: list[Task] = []
    conditions = [("CN", petition_prompt("CN")), ("US", petition_prompt("US")),
                  ("FR", petition_prompt("FR")), ("KR", petition_prompt("KR")),
                  ("NEUTRAL", petition_prompt(None))]
    for model in models:
        for code, prompt in conditions:
            messages = (
                {"role": "system", "content": PROBE_SYSTEM_ZH},
                {"role": "user", "content": prompt},
            )
            for idx in range(3):
                out.append(
                    task(
                        model,
                        f"petition_{code}",
                        messages,
                        idx=idx,
                        temperature=0.8,
                        meta={"country": code, "question": prompt},
                    )
                )
    return out


def q6_tasks(models: list[str]) -> list[Task]:
    out: list[Task] = []
    for model in models:
        for i, paraphrase in enumerate(loyalty_paraphrases(seed=20261110)):
            messages = (
                {"role": "system", "content": PROBE_SYSTEM_ZH},
                {"role": "user", "content": paraphrase},
            )
            for idx in range(2):
                out.append(
                    task(
                        model,
                        f"loyalty_p{i:02d}",
                        messages,
                        idx=idx,
                        temperature=0.8,
                        meta={"question": paraphrase, "paraphrase_index": i},
                    )
                )
    return out


def q7_tasks(provider: str) -> list[Task]:
    prompts = []
    for pid in ("loyalty", "dissent", "order_justice"):
        probe = next(p for p in PROBES if p.id == pid)
        prompts.append((pid, probe.text_zh))
    prompts.append(("petition_CN", petition_prompt("CN")))
    out: list[Task] = []
    for qid, text in prompts:
        messages = (
            {"role": "system", "content": PROBE_SYSTEM_ZH},
            {"role": "user", "content": text},
        )
        for idx in range(3):
            out.append(
                task(
                    "z-ai/glm-5.3",
                    qid,
                    messages,
                    idx=idx,
                    meta={"question": text, "provider": provider},
                )
            )
    return out


class PinnedClient:
    def __init__(self, base, provider: str) -> None:
        self.base = base
        self.provider = {"order": [provider], "allow_fallbacks": False}

    async def complete(self, model, messages, *, temperature, max_tokens, seed=None, top_p=None):
        return await self.base.complete(
            model,
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            seed=seed,
            top_p=top_p,
            provider=self.provider,
        )


async def collect_openrouter(tasks: list[Task], out: Path, concurrency: int, budget: float) -> None:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY is not set")
    async with OpenRouterClient(api_key, timeout=240, max_retries=3) as client:
        summary = await Collector(
            client, out, budget_usd=budget, concurrency=concurrency, seed=20261110
        ).run(tasks)
    print(f"{out.name}: completed={summary.completed} failed={summary.failed} "
          f"spent=${summary.spent_usd:.3f}")


async def collect_claude(tasks: list[Task], out: Path, concurrency: int, budget: float) -> None:
    client = ClaudeChatClient(ClaudeCli(model="sonnet", timeout=300))
    summary = await Collector(
        client, out, budget_usd=budget, concurrency=concurrency, seed=20261110
    ).run(tasks)
    print(f"{out.name}: completed={summary.completed} failed={summary.failed} "
          f"spent=${summary.spent_usd:.3f}")


def main() -> int:
    args = parse_args()
    RES.mkdir(parents=True, exist_ok=True)
    specs = load_model_registry(args.models)
    cn_models = [s.slug for s in specs if s.role == "target"]
    controls = [s.slug for s in specs if s.role == "control"]

    if args.study == "q1":
        tasks = q1_tasks()
        asyncio.run(collect_claude(tasks, RES / "q1" / "records.jsonl", 3, 6.0))
    elif args.study == "q5":
        out_dir = RES / "q5"
        asyncio.run(
            collect_openrouter(
                q5_tasks(cn_models + controls),
                out_dir / "records.jsonl",
                args.concurrency,
                4.0,
            )
        )
        asyncio.run(
            collect_claude(q5_tasks([CLAUDE_SLUG]), out_dir / "claude.jsonl", 3, 2.0)
        )
    elif args.study == "q6":
        asyncio.run(
            collect_openrouter(
                q6_tasks(["inclusionai/ling-3.1-flash", "deepseek/deepseek-v4-pro-0813", "z-ai/glm-5.3"]),
                RES / "q6" / "records.jsonl",
                args.concurrency,
                2.0,
            )
        )
    elif args.study == "q7":
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            raise SystemExit("OPENROUTER_API_KEY is not set")

        async def run_all() -> None:
            async with OpenRouterClient(api_key, timeout=240, max_retries=3) as base:
                for provider in PROVIDERS:
                    summary = await Collector(
                        PinnedClient(base, provider),
                        RES / "q7" / f"{provider}.jsonl",
                        budget_usd=2.0,
                        concurrency=args.concurrency,
                        seed=20261110,
                    ).run(q7_tasks(provider))
                    print(f"q7/{provider}: completed={summary.completed} failed={summary.failed} "
                          f"spent=${summary.spent_usd:.3f}")

        asyncio.run(run_all())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
