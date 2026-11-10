"""Task matrix construction and a resumable, budget-guarded collector."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from constitution.client import ChatResult
from constitution.config import Sampling
from constitution.questions import (
    PROBES,
    build_probe_messages,
    build_scale_messages,
    likert_blocks,
)

LANGUAGES = ("zh", "en")
INSTRUMENTS = ("scale", "probe")


def _is_usable(record: Record) -> bool:
    """A cell is done only if it carries text and did not run out of tokens."""
    return bool(record.error is None and record.text.strip() and record.finish_reason != "length")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Task:
    model: str
    instrument: str
    question_id: str
    language: str
    sample_idx: int
    messages: tuple[dict[str, str], ...]
    temperature: float
    max_tokens: int
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.language not in LANGUAGES:
            raise ValueError(f"unsupported language: {self.language}")
        if self.instrument not in INSTRUMENTS:
            raise ValueError(f"unsupported instrument: {self.instrument}")
        if not self.model:
            raise ValueError("model is required")

    @property
    def key(self) -> str:
        return "|".join(
            (self.model, self.instrument, self.question_id, self.language, str(self.sample_idx))
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "instrument": self.instrument,
            "question_id": self.question_id,
            "language": self.language,
            "sample_idx": self.sample_idx,
            "messages": [dict(m) for m in self.messages],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        return cls(
            model=data["model"],
            instrument=data["instrument"],
            question_id=data["question_id"],
            language=data["language"],
            sample_idx=int(data["sample_idx"]),
            messages=tuple(dict(m) for m in data["messages"]),
            temperature=float(data["temperature"]),
            max_tokens=int(data["max_tokens"]),
            meta=dict(data.get("meta") or {}),
        )


@dataclass(frozen=True)
class Record:
    task: Task
    text: str
    reasoning: str
    error: str | None
    cost_usd: float
    latency_s: float
    finish_reason: str
    ts: str

    @property
    def key(self) -> str:
        return self.task.key

    @property
    def model(self) -> str:
        return self.task.model

    @property
    def instrument(self) -> str:
        return self.task.instrument

    @property
    def question_id(self) -> str:
        return self.task.question_id

    @property
    def language(self) -> str:
        return self.task.language

    @property
    def sample_idx(self) -> int:
        return self.task.sample_idx

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task.to_dict(),
            "text": self.text,
            "reasoning": self.reasoning,
            "error": self.error,
            "cost_usd": self.cost_usd,
            "latency_s": self.latency_s,
            "finish_reason": self.finish_reason,
            "ts": self.ts,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Record:
        return cls(
            task=Task.from_dict(data["task"]),
            text=data.get("text") or "",
            reasoning=data.get("reasoning") or "",
            error=data.get("error"),
            cost_usd=float(data.get("cost_usd") or 0.0),
            latency_s=float(data.get("latency_s") or 0.0),
            finish_reason=data.get("finish_reason") or "unknown",
            ts=data.get("ts") or "",
        )


def _task_templates(
    sampling: Sampling,
) -> list[tuple[str, str, str, tuple[dict[str, str], ...], float, int, dict[str, Any]]]:
    """Language/instrument templates in a fixed, documented order."""
    templates: list[
        tuple[str, str, str, tuple[dict[str, str], ...], float, int, dict[str, Any]]
    ] = []
    for block_idx, block in enumerate(likert_blocks(), start=1):
        messages = build_scale_messages(block, language="zh")
        meta = {
            "block": block_idx,
            "items": [
                {"id": item.id, "dimension": item.dimension, "text_zh": item.text_zh}
                for item in block
            ],
        }
        templates.append(
            (
                "scale",
                f"B{block_idx}",
                "zh",
                messages,
                sampling.temperature_scale,
                sampling.max_tokens_scale,
                meta,
            )
        )
    for probe in PROBES:
        langs = ("zh", "en") if probe.bilingual else ("zh",)
        for language in langs:
            messages = build_probe_messages(probe, language=language)
            meta = {"tags": list(probe.tags), "bilingual": probe.bilingual}
            templates.append(
                (
                    "probe",
                    probe.id,
                    language,
                    messages,
                    sampling.temperature_open,
                    sampling.max_tokens_open,
                    meta,
                )
            )
    return templates


def build_tasks(models: Iterable[str], sampling: Sampling) -> list[Task]:
    """Cross models × templates × repeated samples (templates outermost)."""
    model_list = list(models)
    tasks: list[Task] = []
    for (
        instrument,
        question_id,
        language,
        messages,
        temperature,
        max_tokens,
        meta,
    ) in _task_templates(sampling):
        repeats = sampling.samples_scale if instrument == "scale" else sampling.samples_open
        for sample_idx in range(repeats):
            for model in model_list:
                tasks.append(
                    Task(
                        model=model,
                        instrument=instrument,
                        question_id=question_id,
                        language=language,
                        sample_idx=sample_idx,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        meta=meta,
                    )
                )
    return tasks


def read_jsonl(path: str | Path, *, dedupe: bool = True) -> list[Record]:
    """Read records; with dedupe, the last record for a key supersedes earlier ones.

    The raw file stays append-only: re-collection of an empty/failed cell appends a
    new line and the analyser resolves the key to its latest observation.
    """
    file = Path(path)
    if not file.exists():
        return []
    records: list[Record] = []
    for line in file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        records.append(Record.from_dict(json.loads(line)))
    if dedupe:
        latest: dict[str, Record] = {}
        for record in records:
            latest[record.key] = record
        return list(latest.values())
    return records


def write_jsonl(path: str | Path, records: Sequence[Record], mode: str = "a") -> None:
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open(mode, encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")


@dataclass
class RunSummary:
    completed: int = 0
    skipped: int = 0
    failed: int = 0
    spent_usd: float = 0.0
    stopped_for_budget: bool = False
    failed_keys: list[str] = field(default_factory=list)


class Collector:
    def __init__(
        self,
        client: Any,
        out_path: str | Path,
        *,
        budget_usd: float,
        concurrency: int = 6,
        seed: int | None = None,
    ) -> None:
        self.client = client
        self.out_path = Path(out_path)
        self.budget_usd = budget_usd
        self.concurrency = max(1, concurrency)
        self.seed = seed
        self._spent = 0.0
        self._stopped = False
        self._lock = asyncio.Lock()

    async def run(self, tasks: Sequence[Task]) -> RunSummary:
        done = {r.key for r in read_jsonl(self.out_path) if _is_usable(r)}
        summary = RunSummary(skipped=sum(1 for t in tasks if t.key in done))
        pending = [t for t in tasks if t.key not in done]
        semaphore = asyncio.Semaphore(self.concurrency)
        self.out_path.parent.mkdir(parents=True, exist_ok=True)

        async def execute(task: Task) -> None:
            async with semaphore:
                async with self._lock:
                    if self._stopped or self._spent >= self.budget_usd:
                        self._stopped = True
                        return
                record = await self._call(task)
                async with self._lock:
                    if record.error is None:
                        self._spent += record.cost_usd
                        summary.completed += 1
                    else:
                        summary.failed += 1
                        summary.failed_keys.append(task.key)
                write_jsonl(self.out_path, [record])

        await asyncio.gather(*(execute(task) for task in pending))
        summary.spent_usd = round(self._spent, 6)
        summary.stopped_for_budget = self._stopped
        return summary

    async def _call(self, task: Task) -> Record:
        messages = [dict(m) for m in task.messages]
        try:
            result: ChatResult = await self.client.complete(
                task.model,
                messages,
                temperature=task.temperature,
                max_tokens=task.max_tokens,
                seed=self.seed,
            )
        except Exception as exc:
            return Record(
                task=task,
                text="",
                reasoning="",
                error=str(exc),
                cost_usd=0.0,
                latency_s=0.0,
                finish_reason="error",
                ts=_utc_now(),
            )
        return Record(
            task=task,
            text=result.text,
            reasoning=result.reasoning,
            error=None,
            cost_usd=result.cost_usd,
            latency_s=result.latency_s,
            finish_reason=result.finish_reason,
            ts=_utc_now(),
        )
