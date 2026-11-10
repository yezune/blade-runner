#!/usr/bin/env python
"""Code the follow-up corpora (axis judge, behaviour judge, gap judge).

    uv run python scripts/run_followup_judge.py --study q1
    uv run python scripts/run_followup_judge.py --study all
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

from constitution.analyze import load_verdicts  # noqa: E402
from constitution.client import OpenRouterClient  # noqa: E402
from constitution.collect import read_jsonl  # noqa: E402
from constitution.followup import code_records  # noqa: E402
from constitution.judge import judge_records  # noqa: E402

RES = ROOT / "results" / "followup"
JUDGE = "mistralai/mistral-large-4-0"
CN_JUDGE = "z-ai/glm-5.3"
PROVIDERS = ("wafer", "novita", "siliconflow")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", required=True, choices=["q1", "q5", "q6", "q7", "q13", "all"])
    parser.add_argument("--concurrency", type=int, default=8)
    return parser.parse_args()


def write_codes(path: Path, verdicts) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for verdict in verdicts:
            handle.write(
                json.dumps(
                    {
                        "task_key": verdict.task_key,
                        "judge_model": verdict.judge_model,
                        "payload": verdict.payload,
                        "error": verdict.error,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


def write_axis(path: Path, verdicts) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for verdict in verdicts:
            handle.write(json.dumps(verdict.to_dict(), ensure_ascii=False) + "\n")


async def run(study: str, concurrency: int) -> None:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY is not set")
    async with OpenRouterClient(api_key, timeout=240, max_retries=3) as client:
        if study in ("q1", "all"):
            records = [r for r in read_jsonl(RES / "q1" / "records.jsonl") if r.instrument == "probe"]
            verdicts = await judge_records(
                client, records, JUDGE, max_tokens=6000, concurrency=concurrency
            )
            write_axis(RES / "q1" / "verdicts.jsonl", verdicts)
            print(f"q1 judged={len(verdicts)} errors={sum(1 for v in verdicts if v.score is None)}")

        if study in ("q5", "all"):
            records = read_jsonl(RES / "q5" / "records.jsonl") + read_jsonl(RES / "q5" / "claude.jsonl")
            codes = await code_records(client, records, JUDGE, kind="behavior", concurrency=concurrency)
            write_codes(RES / "q5" / "codes.jsonl", codes)
            print(f"q5 coded={len(codes)} errors={sum(1 for c in codes if c.payload is None)}")

        if study in ("q6", "all"):
            records = read_jsonl(RES / "q6" / "records.jsonl")
            codes = await code_records(client, records, JUDGE, kind="gap", concurrency=concurrency)
            write_codes(RES / "q6" / "gap_codes.jsonl", codes)
            print(f"q6 coded={len(codes)} errors={sum(1 for c in codes if c.payload is None)}")

        if study in ("q7", "all"):
            for provider in PROVIDERS:
                records = read_jsonl(RES / "q7" / f"{provider}.jsonl")
                probes = [r for r in records if not r.question_id.startswith("petition")]
                petitions = [r for r in records if r.question_id.startswith("petition")]
                verdicts = await judge_records(
                    client, probes, JUDGE, max_tokens=6000, concurrency=concurrency
                )
                write_axis(RES / "q7" / f"{provider}_verdicts.jsonl", verdicts)
                codes = await code_records(
                    client, petitions, JUDGE, kind="behavior", concurrency=concurrency
                )
                write_codes(RES / "q7" / f"{provider}_codes.jsonl", codes)
                print(f"q7/{provider}: axis={len(verdicts)} behaviour={len(codes)}")

        if study in ("q13", "all"):
            main_records = read_jsonl(ROOT / "results" / "raw" / "records.jsonl")
            main_verdicts = load_verdicts(ROOT / "results" / "raw" / "verdicts.jsonl")
            scored = {v.task_key for v in main_verdicts if v.score is not None}
            by_model: dict[str, list] = {}
            for record in main_records:
                if record.key in scored and record.instrument == "probe":
                    by_model.setdefault(record.model, []).append(record)
            selected = []
            for model in sorted(by_model):
                seen: set[str] = set()
                for record in sorted(by_model[model], key=lambda r: (r.question_id, r.sample_idx)):
                    if record.question_id in seen:
                        continue
                    seen.add(record.question_id)
                    selected.append(record)
            selected = selected[:120]
            verdicts = await judge_records(
                client, selected, CN_JUDGE, max_tokens=6000, concurrency=concurrency
            )
            write_axis(RES / "q13" / "verdicts_glm.jsonl", verdicts)
            print(f"q13 judged={len(verdicts)} errors={sum(1 for v in verdicts if v.score is None)}")


def main() -> int:
    args = parse_args()
    asyncio.run(run(args.study, args.concurrency))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
