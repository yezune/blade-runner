"""End-to-end pipeline test: collect → judge → tables → report, zero network."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from constitution.analyze import axis_frame, dimension_frame, load_verdicts
from constitution.client import ChatResult
from constitution.collect import Collector, build_tasks, read_jsonl
from constitution.config import Sampling
from constitution.judge import judge_records
from constitution.report import build_report

ITEM_RE = re.compile(r"\[([A-Z]{2}\d)\]")


class ScriptedClient:
    """Answers each instrument according to its system prompt."""

    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, model, messages, *, temperature, max_tokens, seed=None, top_p=None):
        self.calls += 1
        system = messages[0]["content"]
        user = messages[1]["content"]
        if "问卷受访者" in system or "survey respondent" in system:
            ids = ITEM_RE.findall(user)
            text = json.dumps({"responses": [{"id": i, "score": 4} for i in ids]})
        elif "political-psychology" in system:
            text = json.dumps(
                {
                    "authority_locus": 4,
                    "collectivism": 4,
                    "stability_bias": 4,
                    "universality": 2,
                    "state_trust": 4,
                    "deference": 3,
                    "refusal": False,
                    "themes": ["秩序"],
                    "summary": "질서 우선",
                }
            )
        else:
            text = "我认为秩序与稳定优先，但正义不能被完全牺牲。"
        return ChatResult(
            model=model,
            text=text,
            reasoning="",
            cost_usd=0.0001,
            prompt_tokens=10,
            completion_tokens=20,
            latency_s=0.01,
            finish_reason="stop",
        )


@pytest.mark.slow
async def test_full_pipeline(tmp_path: Path) -> None:
    sampling = Sampling(samples_open=1, samples_scale=1)
    tasks = build_tasks(["a/one", "b/two"], sampling)
    raw = tmp_path / "records.jsonl"
    client = ScriptedClient()
    summary = await Collector(client, raw, budget_usd=5, concurrency=4).run(tasks)
    assert summary.completed == len(tasks)
    assert summary.failed == 0

    records = read_jsonl(raw)
    probes = [r for r in records if r.instrument == "probe"]
    verdicts = await judge_records(client, probes, "judge/model")
    assert len(verdicts) == len(probes)
    assert all(v.score is not None for v in verdicts)

    labels = {"a/one": "Alpha", "b/two": "Beta"}
    dims = dimension_frame(records, labels)
    assert list(dims.index) == ["Alpha", "Beta"]
    axes = axis_frame(verdicts, records, labels)
    assert not axes.empty

    path = build_report(records, verdicts, labels, tmp_path / "results", reference="Alpha")
    text = path.read_text(encoding="utf-8")
    assert "핵심 발견" in text
    assert "Alpha" in text

    # verdicts can be persisted and reloaded
    from constitution.analyze import write_verdicts

    out = tmp_path / "verdicts.jsonl"
    write_verdicts(out, verdicts)
    assert len(load_verdicts(out)) == len(verdicts)
