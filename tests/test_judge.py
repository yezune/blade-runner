"""Tests for the LLM-as-judge coding layer."""

from __future__ import annotations

import pytest

from constitution.client import ChatResult
from constitution.judge import (
    AXES,
    JudgeScore,
    build_judge_messages,
    judge_records,
    parse_judge_response,
)
from constitution.parse import ParseError

VALID = (
    '{"authority_locus": 4, "collectivism": 5, "stability_bias": 4,'
    ' "universality": 2, "state_trust": 4, "deference": 3,'
    ' "refusal": false, "themes": ["秩序"], "summary": "s"}'
)


def test_axes_are_fixed() -> None:
    assert len(AXES) == 6
    assert "authority_locus" in AXES


def test_judge_messages_include_rubric_and_answer() -> None:
    system, user = build_judge_messages("질문?", "대답입니다.", "ko")
    assert "1" in system["content"] and "5" in system["content"]
    assert "대답입니다." in user["content"]
    assert "질문?" in user["content"]
    for axis in AXES:
        assert axis in system["content"]


def test_parse_judge_rejects_non_json() -> None:
    with pytest.raises(ParseError):
        parse_judge_response("no json")


def test_parse_judge_themes_optional() -> None:
    payload = (
        '{"authority_locus": 3, "collectivism": 3, "stability_bias": 3,'
        ' "universality": 3, "state_trust": 3, "deference": 3}'
    )
    score = parse_judge_response(payload)
    assert score.themes == ()
    assert score.summary == ""
    assert score.refusal is False


class JudgeClient:
    def __init__(self, payload: str = VALID) -> None:
        self.payload = payload
        self.calls = 0

    async def complete(self, model, messages, *, temperature, max_tokens, seed=None, top_p=None):
        self.calls += 1
        return ChatResult(
            model=model,
            text=self.payload,
            reasoning="",
            cost_usd=0.001,
            prompt_tokens=10,
            completion_tokens=10,
            latency_s=0.01,
            finish_reason="stop",
        )


class RecordStub:
    def __init__(self, key: str) -> None:
        self.key = key
        self.text = "answer"
        self.question_id = "q1"
        self.language = "zh"
        self.instrument = "probe"


def test_judge_score_rejects_missing_axis() -> None:
    with pytest.raises(ParseError):
        JudgeScore.from_mapping({"authority_locus": 3})


async def test_judge_records_attaches_verdicts() -> None:
    records = [RecordStub(f"k{i}") for i in range(4)]
    verdicts = await judge_records(JudgeClient(), records, "judge/model", sample_rate=0.5, seed=1)
    assert len(verdicts) == 2
    assert all(v.score is not None for v in verdicts)
    assert verdicts[0].task_key in {r.key for r in records}


async def test_judge_records_captures_parse_errors() -> None:
    verdicts = await judge_records(JudgeClient("garbage"), [RecordStub("k")], "judge/model")
    assert len(verdicts) == 1
    assert verdicts[0].score is None
    assert "JSON" in (verdicts[0].error or "")


async def test_judge_records_concurrency_preserves_order() -> None:
    records = [RecordStub(f"k{i}") for i in range(6)]
    verdicts = await judge_records(JudgeClient(), records, "judge/model", concurrency=3)
    assert [v.task_key for v in verdicts] == [r.key for r in records]
