"""Tests for figure + markdown report generation (smoke, no network)."""

from __future__ import annotations

import json
from pathlib import Path

from constitution.judge import JudgeVerdict
from constitution.questions import PROBES, likert_blocks
from constitution.report import build_report
from constitution.schema import JudgeScore


def _scale_text(block_index: int, base: int) -> str:
    block = likert_blocks()[block_index]
    return json.dumps(
        {"responses": [{"id": item.id, "score": max(1, min(5, base + (i % 2)))} for i, item in enumerate(block)]}
    )


def _records(record_factory):
    records = []
    for model in ("a/one", "b/two"):
        for block_index in range(4):
            for rep in range(2):
                block = likert_blocks()[block_index]
                records.append(
                    record_factory(
                        model,
                        instrument="scale",
                        qid=f"B{block_index + 1}",
                        idx=rep,
                        text=_scale_text(block_index, 3 if model == "a/one" else 4),
                        meta={
                            "items": [
                                {"id": i.id, "dimension": i.dimension, "text_zh": i.text_zh}
                                for i in block
                            ]
                        },
                    )
                )
        for probe in PROBES:
            for lang in ("zh", "en") if probe.bilingual else ("zh",):
                records.append(
                    record_factory(
                        model,
                        instrument="probe",
                        qid=probe.id,
                        lang=lang,
                        text="秩序与稳定，国家与人民。" if model == "a/one" else "自由与权利，个人尊严。",
                    )
                )
    return records


def _verdicts(records):
    out = []
    for record in records:
        if record.instrument != "probe":
            continue
        axes = {axis: 3 for axis in ("authority_locus", "collectivism", "stability_bias", "universality", "state_trust", "deference")}
        axes["collectivism"] = 4 if record.model == "a/one" else 2
        if record.language == "en":
            axes["collectivism"] -= 1
        out.append(JudgeVerdict(record.key, "judge", JudgeScore(axes=axes)))
    return out


def test_build_report_writes_markdown_figures_and_tables(record_factory, tmp_path: Path) -> None:
    records = _records(record_factory)
    verdicts = _verdicts(records)
    labels = {"a/one": "Alpha", "b/two": "Beta"}
    path = build_report(records, verdicts, labels, tmp_path, reference="Beta")
    text = path.read_text(encoding="utf-8")
    assert path.name == "REPORT.md"
    assert "핵심 발견" in text
    assert "Alpha" in text and "Beta" in text
    assert "방법론" in text
    assert (tmp_path / "figures" / "value_profiles.png").exists()
    assert (tmp_path / "figures" / "constitution_axes.png").exists()
    assert (tmp_path / "tables" / "dimensions.csv").exists()
    assert "|" in text


def test_report_is_deterministic(record_factory, tmp_path: Path) -> None:
    records = _records(record_factory)
    verdicts = _verdicts(records)
    labels = {"a/one": "Alpha", "b/two": "Beta"}
    first = build_report(records, verdicts, labels, tmp_path / "run1", reference="Beta")
    second = build_report(records, verdicts, labels, tmp_path / "run2", reference="Beta")
    assert first.read_text(encoding="utf-8") == second.read_text(encoding="utf-8")
