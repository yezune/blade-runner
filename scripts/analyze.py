#!/usr/bin/env python
"""Build the analysis tables + REPORT.md from collected raw data."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from constitution.analyze import (  # noqa: E402
    axis_frame,
    constitution_distance,
    coverage_table,
    dimension_frame,
    judge_agreement,
    language_delta,
    lexicon_frame,
    load_verdicts,
    raw_item_scores,
    shared_and_contested,
)
from constitution.collect import read_jsonl  # noqa: E402
from constitution.config import load_model_registry  # noqa: E402
from constitution.report import build_report  # noqa: E402
from constitution.schema import AXES  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", default=str(ROOT / "results"))
    parser.add_argument("--models", default=str(ROOT / "config" / "models.yaml"))
    parser.add_argument("--reference", default="Grok 4.7")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results = Path(args.results)
    records = read_jsonl(results / "raw" / "records.jsonl")
    verdicts = load_verdicts(results / "raw" / "verdicts.jsonl")
    verdicts_second = load_verdicts(results / "raw" / "verdicts_second.jsonl")
    if not records:
        print("no records found", file=sys.stderr)
        return 2

    specs = load_model_registry(args.models)
    labels = {spec.slug: spec.label for spec in specs}
    roles = {spec.label: spec.role for spec in specs}
    # raw/ is append-only and may still hold models that were later dropped
    # (e.g. provider-blocked controls); analyse only the current registry.
    records = [r for r in records if r.model in labels]

    dims = dimension_frame(records, labels)
    axes = axis_frame(verdicts, records, labels)
    delta = language_delta(axes)
    lexicon = lexicon_frame(records, labels)
    distance = constitution_distance(dims, args.reference)
    coverage = coverage_table(records, labels)
    shared, contested = shared_and_contested(raw_item_scores(records, labels))

    print(f"models={len(coverage)} requests={len(records)} verdicts={len(verdicts)}")
    print("\ncoverage:\n" + coverage.round(3).to_string())
    if not dims.empty:
        print("\nipsative value profile (top 3 per model):")
        for model in dims.index:
            top = dims.loc[model].sort_values(ascending=False).head(3)
            print(f"  {model:<28} " + ", ".join(f"{k} {v:+.2f}" for k, v in top.items()))
    if not axes.empty:
        print("\njudge axes (mean):\n" + axes.groupby("model", observed=True)[list(AXES)].mean().round(2).to_string())
    if not delta.empty:
        print("\nlanguage shift (en - zh):\n" + delta[list(AXES)].mean().round(2).to_string())
    if not distance.empty:
        print("\ndistance to reference:\n" + distance.sort_values().round(2).to_string())
    if not shared.empty:
        print("\nshared items (lowest SD):\n" + shared.head(3).round(2).to_string())
        print("\ncontested items (highest SD):\n" + contested.head(3).round(2).to_string())
    if not lexicon.empty:
        print("\nlexicon density:\n" + lexicon.round(1).to_string())

    if verdicts_second:
        print("\njudge agreement (\u00b11):\n" + judge_agreement(verdicts, verdicts_second).round(2).to_string())

    path = build_report(
        records,
        verdicts,
        labels,
        results,
        reference=args.reference,
        roles=roles,
        secondary_verdicts=verdicts_second,
    )
    print(f"\nreport: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
