#!/usr/bin/env python
"""Code open-ended answers with a judge model, with resume + reliability sample."""

from __future__ import annotations

import argparse
import asyncio
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from constitution.analyze import load_verdicts, write_verdicts  # noqa: E402
from constitution.client import OpenRouterClient  # noqa: E402
from constitution.collect import read_jsonl  # noqa: E402
from constitution.config import load_run_config  # noqa: E402
from constitution.judge import judge_records  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(ROOT / "config" / "run.yaml"))
    parser.add_argument("--records", default=str(ROOT / "results" / "raw" / "records.jsonl"))
    parser.add_argument("--out", default=str(ROOT / "results" / "raw" / "verdicts.jsonl"))
    parser.add_argument("--second-out", default=str(ROOT / "results" / "raw" / "verdicts_second.jsonl"))
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--no-second", action="store_true")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    run = load_run_config(args.config)
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("OPENROUTER_API_KEY is not set", file=sys.stderr)
        return 2

    records = [r for r in read_jsonl(args.records) if r.instrument == "probe" and r.error is None]
    done = {
        v.task_key
        for v in load_verdicts(args.out)
        if v.judge_model == run.judging.model and v.score is not None
    }
    pending = [r for r in records if r.key not in done]
    print(f"probe answers: {len(records)} · already judged: {len(done)} · pending: {len(pending)}")

    semaphore = asyncio.Semaphore(args.concurrency)

    async with OpenRouterClient(
        api_key, timeout=run.runtime.request_timeout_s, max_retries=run.runtime.max_retries
    ) as client:

        async def one(record):
            async with semaphore:
                verdicts = await judge_records(
                    client,
                    [record],
                    run.judging.model,
                    temperature=run.judging.temperature,
                    max_tokens=run.judging.max_tokens,
                )
                write_verdicts(args.out, verdicts)
                return verdicts[0]

        verdicts = await asyncio.gather(*(one(r) for r in pending))
        errors = [v for v in verdicts if v.score is None]
        print(f"judged={len(verdicts)} errors={len(errors)}")

        if not args.no_second and run.judging.second_model:
            primary_done = {v.task_key for v in load_verdicts(args.out) if v.score is not None}
            second_done = {
                v.task_key
                for v in load_verdicts(args.second_out)
                if v.judge_model == run.judging.second_model
            }
            pool = [r for r in records if r.key in primary_done and r.key not in second_done]
            rng = random.Random(run.sampling.seed)
            sample_size = max(1, round(len(records) * run.judging.reliability_sample_rate))
            sample = rng.sample(sorted(pool, key=lambda r: r.key), min(sample_size, len(pool)))
            print(f"second judge ({run.judging.second_model}): {len(sample)} answers")
            sem2 = asyncio.Semaphore(max(1, args.concurrency // 2))

            async def one_second(record):
                async with sem2:
                    verdicts = await judge_records(
                        client,
                        [record],
                        run.judging.second_model,
                        temperature=run.judging.temperature,
                        max_tokens=run.judging.max_tokens,
                    )
                    write_verdicts(args.second_out, verdicts)

            await asyncio.gather(*(one_second(r) for r in sample))

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
