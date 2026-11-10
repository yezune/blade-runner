"""Shared fixtures: synthetic tasks/records that mimic collected output."""

from __future__ import annotations

from typing import Any

import pytest

from constitution.collect import Record, Task
from constitution.schema import JudgeScore


@pytest.fixture
def record_factory():
    def make(
        model: str = "a/one",
        *,
        instrument: str = "probe",
        qid: str = "trolley",
        lang: str = "zh",
        idx: int = 0,
        text: str = "答案文本",
        error: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> Record:
        task = Task(
            model=model,
            instrument=instrument,
            question_id=qid,
            language=lang,
            sample_idx=idx,
            messages=({"role": "user", "content": "q"},),
            temperature=0.0,
            max_tokens=100,
            meta=meta or {},
        )
        return Record(
            task=task,
            text=text,
            reasoning="",
            error=error,
            cost_usd=0.0,
            latency_s=0.1,
            finish_reason="stop",
            ts="2026-11-10T00:00:00Z",
        )

    return make


@pytest.fixture
def score_factory():
    def make(**overrides: Any) -> JudgeScore:
        axes = {axis: 3 for axis in ("authority_locus", "collectivism", "stability_bias", "universality", "state_trust", "deference")}
        axes.update({k: v for k, v in overrides.items() if k in axes})
        return JudgeScore(axes=axes, refusal=overrides.get("refusal", False))
    return make
