#!/usr/bin/env python
"""Collect the survey matrix. Resumable: rerun to fill gaps, never duplicates.

Usage:
    export OPENROUTER_API_KEY=...
    uv run python scripts/run_survey.py --dry-run
    uv run python scripts/run_survey.py            # full matrix
    uv run python scripts/run_survey.py --models 3 # smoke run on first 3 models
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from constitution.client import OpenRouterClient  # noqa: E402
from constitution.collect import Collector, build_tasks  # noqa: E402
from constitution.config import load_model_registry, load_run_config  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(ROOT / "config" / "run.yaml"))
    parser.add_argument("--models", default=str(ROOT / "config" / "models.yaml"))
    parser.add_argument("--out", default=str(ROOT / "results" / "raw" / "records.jsonl"))
    parser.add_argument("--budget", type=float, default=None, help="override USD budget")
    parser.add_argument("--only", nargs="*", default=None, help="restrict to these slugs")
    parser.add_argument("--limit", type=int, default=None, help="cap number of tasks")
    parser.add_argument("--concurrency", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run = load_run_config(args.config)
    specs = load_model_registry(args.models)
    if args.only:
        specs = tuple(s for s in specs if s.slug in set(args.only))
        if not specs:
            print(f"no models matched {args.only}", file=sys.stderr)
            return 2
    sampling = run.sampling
    models = [s.slug for s in specs]
    tasks = build_tasks(models, sampling)
    if args.limit:
        tasks = tasks[: args.limit]

    budget = args.budget if args.budget is not None else run.runtime.budget_usd
    per_model = len(tasks) // max(1, len(models))
    print(f"matrix: {len(tasks)} requests · {len(models)} models · {per_model} per model")
    print(f"budget: ${budget:.2f} · concurrency: {args.concurrency or run.runtime.concurrency}")

    if args.dry_run:
        sample = [t for t in tasks if t.model == models[0]][:2]
        for task in sample:
            print(f"\n--- {task.key} · T={task.temperature} ---")
            for message in task.messages:
                print(f"[{message['role']}] {message['content'][:400]}")
        out = ROOT / "results" / "prompt_preview.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps([t.to_dict() for t in tasks], ensure_ascii=False, indent=1), encoding="utf-8"
        )
        print(f"\nfull matrix written to {out}")
        return 0

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("OPENROUTER_API_KEY is not set", file=sys.stderr)
        return 2

    async def run_all() -> int:
        async with OpenRouterClient(
            api_key,
            timeout=run.runtime.request_timeout_s,
            max_retries=run.runtime.max_retries,
            backoff_base=run.runtime.backoff_base_s,
        ) as client:
            collector = Collector(
                client,
                args.out,
                budget_usd=budget,
                concurrency=args.concurrency or run.runtime.concurrency,
                seed=sampling.seed,
            )
            summary = await collector.run(tasks)
        print(
            f"completed={summary.completed} skipped={summary.skipped} failed={summary.failed} "
            f"spent=${summary.spent_usd:.4f} stopped_for_budget={summary.stopped_for_budget}"
        )
        if summary.failed_keys:
            print(f"failed keys: {summary.failed_keys[:5]}{' ...' if len(summary.failed_keys) > 5 else ''}")
        return 0 if summary.failed == 0 else 1

    return asyncio.run(run_all())


if __name__ == "__main__":
    raise SystemExit(main())
