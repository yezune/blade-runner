#!/usr/bin/env python
"""Print a compact evidence pack: one answer + judge summary per model/probe."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from constitution.analyze import load_verdicts  # noqa: E402
from constitution.collect import read_jsonl  # noqa: E402
from constitution.config import load_model_registry  # noqa: E402
from constitution.questions import PROBES  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", default="loyalty")
    parser.add_argument("--lang", default="zh")
    parser.add_argument("--chars", type=int, default=420)
    parser.add_argument("--results", default=str(ROOT / "results"))
    parser.add_argument("--models", default=str(ROOT / "config" / "models.yaml"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    labels = {s.slug: s.label for s in load_model_registry(args.models)}
    records = [
        r
        for r in read_jsonl(Path(args.results) / "raw" / "records.jsonl")
        if r.instrument == "probe" and r.question_id == args.probe and r.language == args.lang
    ]
    if not records:
        print("no matching records", file=sys.stderr)
        return 2
    verdicts = {v.task_key: v for v in load_verdicts(Path(args.results) / "raw" / "verdicts.jsonl")}
    probe = next(p for p in PROBES if p.id == args.probe)
    print(f"# {args.probe} [{args.lang}]\n{probe.text_zh if args.lang == 'zh' else probe.text_en}\n")

    seen: set[str] = set()
    for record in sorted(records, key=lambda r: (r.model, r.sample_idx)):
        if record.model in seen:
            continue
        seen.add(record.model)
        verdict = verdicts.get(record.key)
        axes = ""
        if verdict and verdict.score:
            axes = " ".join(f"{k[:4]}={v}" for k, v in verdict.score.axes.items())
        print(f"## {labels.get(record.model, record.model)}  ({axes})")
        print(record.text.strip()[: args.chars].replace("\n", " "))
        if verdict and verdict.score and verdict.score.summary:
            print(f"> {verdict.score.summary}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
