"""Tests for task matrix construction and the resumable collector."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from constitution.client import ChatResult
from constitution.collect import Collector, Record, Task, build_tasks, read_jsonl, write_jsonl
from constitution.config import load_run_config
from constitution.questions import PROBES, likert_blocks

ROOT = Path(__file__).resolve().parents[1]


class FakeClient:
    def __init__(self, cost: float = 0.01, fail_models: set[str] | None = None) -> None:
        self.cost = cost
        self.fail_models = fail_models or set()
        self.in_flight = 0
        self.max_in_flight = 0
        self.calls: list[str] = []

    async def complete(self, model, messages, *, temperature, max_tokens, seed=None, top_p=None):
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(0)
            self.calls.append(model)
            if model in self.fail_models:
                raise RuntimeError("boom")
            return ChatResult(
                model=model,
                text="答案" * 20,
                reasoning="",
                cost_usd=self.cost,
                prompt_tokens=10,
                completion_tokens=20,
                latency_s=0.01,
                finish_reason="stop",
            )
        finally:
            self.in_flight -= 1


def test_build_tasks_covers_full_design() -> None:
    cfg = load_run_config(ROOT / "config" / "run.yaml")
    tasks = build_tasks(["a/one", "b/two"], cfg.sampling)
    per_model = len(tasks) // 2
    probe_cells = sum(2 if p.bilingual else 1 for p in PROBES)
    assert per_model == probe_cells * cfg.sampling.samples_open + len(likert_blocks()) * cfg.sampling.samples_scale
    assert len({t.key for t in tasks}) == len(tasks)
    assert {t.instrument for t in tasks} == {"scale", "probe"}
    assert {t.language for t in tasks} == {"zh", "en"}


def test_scale_task_messages_cover_a_block() -> None:
    cfg = load_run_config(ROOT / "config" / "run.yaml")
    tasks = [t for t in build_tasks(["a/one"], cfg.sampling) if t.instrument == "scale"]
    first = tasks[0]
    ids = [item["id"] for item in first.meta["items"]]
    block = [i.id for i in likert_blocks()[0]]
    assert ids == block
    assert len(first.messages) == 2


def test_jsonl_roundtrip(tmp_path: Path) -> None:
    cfg = load_run_config(ROOT / "config" / "run.yaml")
    task = build_tasks(["a/one"], cfg.sampling)[0]
    record = Record(
        task=task,
        text="hello",
        reasoning="r",
        error=None,
        cost_usd=0.1,
        latency_s=0.2,
        finish_reason="stop",
        ts="2026-11-10T00:00:00Z",
    )
    path = tmp_path / "out.jsonl"
    write_jsonl(path, [record])
    loaded = read_jsonl(path)
    assert loaded[0].key == task.key
    assert loaded[0].text == "hello"
    assert loaded[0].task.meta == task.meta
    payload = json.loads(path.read_text().strip())
    assert payload["task"]["question_id"] == task.question_id


async def test_collector_runs_and_persists(tmp_path: Path) -> None:
    cfg = load_run_config(ROOT / "config" / "run.yaml")
    tasks = build_tasks(["a/one"], cfg.sampling)[:5]
    client = FakeClient(cost=0.01)
    collector = Collector(client, tmp_path / "r.jsonl", budget_usd=10, concurrency=2)
    summary = await collector.run(tasks)
    assert summary.completed == 5
    assert summary.failed == 0
    assert summary.spent_usd == pytest.approx(0.05)
    assert len(read_jsonl(tmp_path / "r.jsonl")) == 5
    assert client.max_in_flight <= 2


async def test_collector_resumes_without_duplicates(tmp_path: Path) -> None:
    cfg = load_run_config(ROOT / "config" / "run.yaml")
    tasks = build_tasks(["a/one"], cfg.sampling)[:4]
    path = tmp_path / "r.jsonl"
    client = FakeClient()
    await Collector(client, path, budget_usd=10, concurrency=1).run(tasks[:2])
    summary = await Collector(client, path, budget_usd=10, concurrency=1).run(tasks)
    assert summary.skipped == 2
    assert summary.completed == 2
    assert len(read_jsonl(path)) == 4


async def test_collector_stops_at_budget(tmp_path: Path) -> None:
    cfg = load_run_config(ROOT / "config" / "run.yaml")
    tasks = build_tasks(["a/one"], cfg.sampling)[:10]
    client = FakeClient(cost=0.5)
    summary = await Collector(client, tmp_path / "r.jsonl", budget_usd=2.0, concurrency=1).run(tasks)
    assert summary.stopped_for_budget is True
    assert summary.completed == 4
    assert summary.spent_usd == pytest.approx(2.0)


async def test_collector_records_failures_and_continues(tmp_path: Path) -> None:
    cfg = load_run_config(ROOT / "config" / "run.yaml")
    tasks = build_tasks(["bad/one", "good/two"], cfg.sampling)[:6]
    client = FakeClient(fail_models={"bad/one"})
    summary = await Collector(client, tmp_path / "r.jsonl", budget_usd=10, concurrency=2).run(tasks)
    assert summary.failed == 3
    assert summary.completed == 3
    errors = [r for r in read_jsonl(tmp_path / "r.jsonl") if r.error]
    assert len(errors) == 3
    assert "boom" in (errors[0].error or "")


def test_task_requires_known_language() -> None:
    with pytest.raises(ValueError):
        Task(
            model="a/b",
            instrument="probe",
            question_id="x",
            language="kr",
            sample_idx=0,
            messages=(),
            temperature=0.0,
            max_tokens=10,
            meta={},
        )


def test_read_jsonl_supersedes_duplicate_keys(tmp_path: Path) -> None:
    from constitution.collect import Record

    cfg = load_run_config(ROOT / "config" / "run.yaml")
    task = build_tasks(["a/one"], cfg.sampling)[0]
    first = Record(task, "old", "", None, 0.0, 0.0, "stop", "2026-01-01T00:00:00Z")
    second = Record(task, "new", "", None, 0.0, 0.0, "stop", "2026-01-02T00:00:00Z")
    path = tmp_path / "r.jsonl"
    write_jsonl(path, [first])
    write_jsonl(path, [second])
    records = read_jsonl(path)
    assert len(records) == 1
    assert records[0].text == "new"


async def test_collector_retries_empty_length_records(tmp_path: Path) -> None:
    from constitution.collect import Record

    cfg = load_run_config(ROOT / "config" / "run.yaml")
    tasks = build_tasks(["a/one"], cfg.sampling)[:2]
    path = tmp_path / "r.jsonl"
    write_jsonl(path, [Record(tasks[0], "", "reasoning only", None, 0.0, 0.0, "length", "t")])
    client = FakeClient()
    summary = await Collector(client, path, budget_usd=10, concurrency=1).run(tasks)
    assert summary.completed == 2  # empty-length record is re-collected
    assert read_jsonl(path)[0].text.startswith("答案")
