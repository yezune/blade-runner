#!/usr/bin/env python
"""FIXPOINT-1: iterate the "what should be prioritised next?" operator.

    uv run python scripts/run_fixpoint.py --concurrency 8
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from constitution.claude_cli import ClaudeChatClient, ClaudeCli  # noqa: E402
from constitution.client import OpenRouterClient  # noqa: E402
from constitution.config import load_model_registry  # noqa: E402
from constitution.fixpoint import (  # noqa: E402
    INITIAL_STATES,
    build_endorsement_messages,
    build_step_messages,
    parse_allocation,
    parse_endorsement,
    perturb,
)

CLAUDE = "anthropic/claude-sonnet-5.5"
OUT = ROOT / "results" / "fixpoint" / "records.jsonl"
STEPS = 6


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--budget", type=float, default=8.0)
    parser.add_argument("--models", default=str(ROOT / "config" / "models.yaml"))
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--only", nargs="*", default=None)
    parser.add_argument("--claude", action="store_true", help="include Claude via claude -p")
    return parser.parse_args()


def load_done(path: Path) -> dict[str, dict[str, Any]]:
    done: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return done
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("error") is None and row.get("state_out"):
            done[row["key"]] = row
    return done


def append(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


async def step_once(
    client: Any,
    model: str,
    chain: str,
    step: int,
    state: dict[str, int],
    framing: str,
    language: str,
    semaphore: asyncio.Semaphore,
    out: Path,
    done: dict[str, dict[str, Any]],
) -> tuple[dict[str, int] | None, float]:
    key = f"{model}|{chain}|{step}"
    if key in done:
        return done[key]["state_out"], 0.0
    system, user = build_step_messages(state, language=language, framing=framing)
    async with semaphore:
        result = None
        parsed = None
        error = None
        budgets = (16000, 16000) if model == "tencent/hy4" else (4000, 6000)
        for attempt, budget in enumerate(budgets):
            try:
                result = await client.complete(
                    model,
                    [system, user],
                    temperature=0.7 if attempt == 0 else 0.3,
                    max_tokens=budget,
                    extra={"reasoning": {"effort": "low"}},
                )
            except Exception as exc:
                error = str(exc)
                continue
            try:
                parsed = parse_allocation(result.text)
                error = None
                break
            except Exception as exc:
                error = str(exc)
                continue
    row = {
        "key": key,
        "model": model,
        "chain": chain,
        "step": step,
        "framing": framing,
        "language": language,
        "state_in": state,
        "state_out": parsed,
        "error": error,
        "raw": (result.text if result else "")[:4000],
        "cost_usd": float(getattr(result, "cost_usd", 0.0) or 0.0),
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    append(out, row)
    return parsed, row["cost_usd"]


async def run_chain(
    client: Any,
    model: str,
    chain: str,
    start: dict[str, int],
    steps: int,
    framing: str,
    language: str,
    semaphore: asyncio.Semaphore,
    out: Path,
    done: dict[str, dict[str, Any]],
) -> tuple[dict[str, int] | None, float]:
    state = start
    spent = 0.0
    for step in range(steps):
        nxt, cost = await step_once(
            client, model, chain, step, state, framing, language, semaphore, out, done
        )
        spent += cost
        if nxt is None:
            return None, spent
        state = nxt
    return state, spent


async def endorse(
    client: Any,
    model: str,
    chain: str,
    state: dict[str, int],
    semaphore: asyncio.Semaphore,
    out: Path,
    done: dict[str, dict[str, Any]],
) -> float:
    key = f"{model}|{chain}|0"
    if key in done:
        return 0.0
    system, user = build_endorsement_messages(state)
    async with semaphore:
        try:
            result = await client.complete(
                model,
                [system, user],
                temperature=0.0,
                max_tokens=400,
                extra={"reasoning": {"effort": "low"}},
            )
            parsed = parse_endorsement(result.text)
            error = None
        except Exception as exc:
            parsed = None
            error = str(exc)
            result = None
    append(
        out,
        {
            "key": key,
            "model": model,
            "chain": chain,
            "step": 0,
            "kind": "endorse",
            "state_in": state,
            "state_out": None,
            "endorse": parsed if error is None else None,
            "error": error,
            "raw": (result.text if result else "")[:2000],
            "cost_usd": float(getattr(result, "cost_usd", 0.0) or 0.0),
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        },
    )
    return float(getattr(result, "cost_usd", 0.0) or 0.0)


async def main() -> int:
    args = parse_args()
    specs = load_model_registry(args.models)
    models = [s.slug for s in specs]
    if args.claude and CLAUDE not in models:
        models.append(CLAUDE)
    if args.only:
        models = [m for m in models if m in set(args.only)]
    out = Path(args.out)
    done = load_done(out)
    semaphore = asyncio.Semaphore(args.concurrency)

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY is not set")

    async with OpenRouterClient(api_key, timeout=240, max_retries=3) as router:
        claude = ClaudeChatClient(ClaudeCli(model="sonnet", timeout=300))
        total = 0.0

        async def one_model(model: str) -> None:
            nonlocal total
            client = claude if model == CLAUDE else router
            mains: dict[str, dict[str, int] | None] = {}

            # Phase A: four self-framing chains + language + society framing.
            jobs = [
                (f"main_{start}_zh", INITIAL_STATES[start], STEPS, "self", "zh")
                for start in INITIAL_STATES
            ]
            jobs.append(("lang_liberty_en", INITIAL_STATES["liberty"], STEPS, "self", "en"))
            jobs.append(("frame_liberty_society", INITIAL_STATES["liberty"], 3, "society", "zh"))

            async def run_job(job):
                chain, start, steps, framing, language = job
                final, cost = await run_chain(
                    client, model, chain, start, steps, framing, language, semaphore, out, done
                )
                return chain, final, cost

            results = await asyncio.gather(*(run_job(job) for job in jobs))
            for chain, final, cost in results:
                total += cost
                if chain.startswith("main_"):
                    mains[chain] = final
                print(f"{model} {chain} cost=${cost:.4f} ok={final is not None}", flush=True)

            # Phase B: perturbation + endorsement on two converged states.
            for start in ("liberty", "growth"):
                final = mains.get(f"main_{start}_zh")
                if not final:
                    continue
                shocked = perturb(final)
                _, cost = await run_chain(
                    client,
                    model,
                    f"pert_{start}_zh",
                    shocked,
                    2,
                    "self",
                    "zh",
                    semaphore,
                    out,
                    done,
                )
                total += cost
                total += await endorse(
                    client, model, f"endorse_{start}", final, semaphore, out, done
                )

        await asyncio.gather(*(one_model(model) for model in models))

    print(f"total cost ${total:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
