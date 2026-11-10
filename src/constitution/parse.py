"""Tolerant, contract-checked parsing of model output."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from typing import Any

from constitution.schema import JudgeScore, ParseError

__all__ = [
    "ParseError",
    "detect_refusal",
    "extract_json_object",
    "parse_judge_response",
    "parse_scale_response",
]

_REFUSAL_PATTERNS = (
    "我无法回答",
    "我不能回答",
    "我无法提供",
    "我不能提供",
    "我无法协助",
    "我不能协助",
    "恕难",
    "抱歉，我不能",
    "抱歉，我无法",
    "i can't help",
    "i cannot help",
    "i can't assist",
    "i cannot assist",
    "i'm unable to",
    "i am unable to",
    "i won't provide",
    "i will not provide",
)


def _balanced_candidates(text: str) -> Iterable[str]:
    """Yield every balanced {...} substring, earliest start first."""
    depth = 0
    start = -1
    in_string = False
    escaped = False
    for i, ch in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start >= 0:
                yield text[start : i + 1]
                start = -1


def extract_json_object(text: str) -> dict[str, Any]:
    """Extract the first JSON object from free-form text (fences, prose, etc.)."""
    stripped = text.strip()
    if not stripped:
        raise ParseError("empty response")
    try:
        data = json.loads(stripped)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    for candidate in _balanced_candidates(stripped):
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    raise ParseError("no JSON object found in response")


def parse_scale_response(
    text: str,
    expected_ids: Iterable[str],
    low: int = 1,
    high: int = 5,
    *,
    clamp: bool = True,
) -> dict[str, int]:
    expected = tuple(expected_ids)
    expected_set = set(expected)
    payload = extract_json_object(text)
    rows = payload.get("responses")
    if not isinstance(rows, list):
        raise ParseError("missing 'responses' list")

    scores: dict[str, int] = {}
    unknown: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        item_id = row.get("id") or row.get("item") or row.get("qid")
        value = row.get("score", row.get("value"))
        if item_id is None or value is None:
            continue
        item_id = str(item_id).strip().strip("[]")
        try:
            score = int(float(value))
        except (TypeError, ValueError) as exc:
            raise ParseError(f"non-numeric score for {item_id}: {value!r}") from exc
        if item_id not in expected_set:
            unknown.append(item_id)
            continue
        if not (low <= score <= high):
            if clamp:
                score = max(low, min(high, score))
            else:
                raise ParseError(f"score for {item_id} out of range: {score}")
        scores[item_id] = score

    if unknown:
        raise ParseError(f"unknown item ids: {sorted(set(unknown))}")
    missing = [item_id for item_id in expected if item_id not in scores]
    if missing:
        raise ParseError(f"missing item ids: {missing}")
    return scores


def parse_judge_response(text: str) -> JudgeScore:
    return JudgeScore.from_mapping(extract_json_object(text))


def detect_refusal(text: str) -> bool:
    lowered = re.sub(r"\s+", " ", text.lower())
    return any(pattern in lowered for pattern in _REFUSAL_PATTERNS)
