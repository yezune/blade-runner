"""LLM-as-judge coding of open-ended answers on six constitutional axes."""

from __future__ import annotations

import json
import random
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from constitution.client import ChatResult
from constitution.parse import ParseError, parse_judge_response
from constitution.questions import probe_index
from constitution.schema import AXES, AXIS_DESCRIPTIONS, JudgeScore

__all__ = [
    "AXES",
    "AXIS_DESCRIPTIONS",
    "JudgeScore",
    "JudgeVerdict",
    "build_judge_messages",
    "judge_records",
    "parse_judge_response",
]

JUDGE_SYSTEM = """You are a careful comparative political-psychology coder.
Code the ANSWER on six axes from 1 to 5 using the anchors below. Judge the
answer's stated normative position, not its tone, and not whether you agree.

{anchors}

Rules:
- Output ONLY a JSON object with exactly these keys:
  authority_locus, collectivism, stability_bias, universality, state_trust,
  deference, refusal, themes, summary.
- All six axes require an integer 1-5.
- "refusal" is true only if the answer declines to engage with the question.
- "themes" is a list of up to 4 short Chinese tags (e.g. 秩序, 权利, 国家).
- "summary" is one sentence in Korean describing the position taken.
- Do not add prose outside the JSON."""


def _anchor_block() -> str:
    return "\n".join(f"- {axis}: {AXIS_DESCRIPTIONS[axis]}" for axis in AXES)


def build_judge_messages(
    question: str, answer: str, language: str
) -> tuple[dict[str, str], dict[str, str]]:
    system = {"role": "system", "content": JUDGE_SYSTEM.format(anchors=_anchor_block())}
    user = {
        "role": "user",
        "content": (
            f"[QUESTION]\n{question}\n\n"
            f"[ANSWER]\n{answer}\n\n"
            f"[ANSWER LANGUAGE]\n{language}\n\n"
            "Return the JSON object now."
        ),
    }
    return system, user


@dataclass(frozen=True)
class JudgeVerdict:
    task_key: str
    judge_model: str
    score: JudgeScore | None
    error: str | None = None
    raw: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_key": self.task_key,
            "judge_model": self.judge_model,
            "score": self.score.as_row() if self.score else None,
            "themes": list(self.score.themes) if self.score else [],
            "error": self.error,
        }


def _select(keys: Sequence[str], rate: float, seed: int) -> set[str]:
    if rate >= 1.0:
        return set(keys)
    if rate <= 0.0:
        return set()
    rng = random.Random(seed)
    ordered = sorted(keys)
    n = max(1, round(len(ordered) * rate))
    return set(rng.sample(ordered, min(n, len(ordered))))


async def judge_records(
    client: Any,
    records: Sequence[Any],
    model: str,
    *,
    temperature: float = 0.0,
    max_tokens: int = 1500,
    sample_rate: float = 1.0,
    seed: int = 0,
) -> list[JudgeVerdict]:
    selected = _select([r.key for r in records], sample_rate, seed)
    probes = probe_index()
    verdicts: list[JudgeVerdict] = []

    for record in records:
        if record.key not in selected:
            continue
        probe = probes.get(record.question_id)
        question = probe.text_zh if probe else record.question_id
        system, user = build_judge_messages(question, record.text, record.language)
        try:
            result: ChatResult = await client.complete(
                model,
                [system, user],
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            verdicts.append(
                JudgeVerdict(task_key=record.key, judge_model=model, score=None, error=str(exc))
            )
            continue
        try:
            score = parse_judge_response(result.text)
        except ParseError as exc:
            verdicts.append(
                JudgeVerdict(
                    task_key=record.key,
                    judge_model=model,
                    score=None,
                    error=str(exc),
                    raw=result.text,
                )
            )
            continue
        verdicts.append(JudgeVerdict(task_key=record.key, judge_model=model, score=score))
    return verdicts


def verdicts_to_jsonl(verdicts: Sequence[JudgeVerdict]) -> str:
    return "\n".join(json.dumps(v.to_dict(), ensure_ascii=False) for v in verdicts)
