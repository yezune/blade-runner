"""Tests for tolerant parsing of model output."""

from __future__ import annotations

import pytest

from constitution.parse import (
    ParseError,
    detect_refusal,
    extract_json_object,
    parse_judge_response,
    parse_scale_response,
)

EXPECTED = ("A1", "A2", "A3")


def test_extracts_plain_json() -> None:
    assert extract_json_object('{"x": 1}') == {"x": 1}


def test_extracts_fenced_json() -> None:
    text = 'Here you go:\n```json\n{"a": {"b": 2}}\n```\nDone.'
    assert extract_json_object(text) == {"a": {"b": 2}}


def test_extracts_json_amid_prose_with_braces_in_string() -> None:
    text = '설명 {not json} ...\n{"responses": [{"id": "A1", "score": 4}], "note": "a } b"}'
    assert extract_json_object(text)["responses"][0]["id"] == "A1"


def test_extract_raises_without_json() -> None:
    with pytest.raises(ParseError):
        extract_json_object("no structured data here")


def test_parse_scale_accepts_string_scores() -> None:
    text = '{"responses": [{"id": "A1", "score": "5"}, {"id": "A2", "score": 2}, {"id": "A3", "score": 3}]}'
    assert parse_scale_response(text, EXPECTED) == {"A1": 5, "A2": 2, "A3": 3}


def test_parse_scale_clamps_out_of_range() -> None:
    text = '{"responses": [{"id": "A1", "score": 9}, {"id": "A2", "score": 0}, {"id": "A3", "score": 3}]}'
    assert parse_scale_response(text, EXPECTED) == {"A1": 5, "A2": 1, "A3": 3}


def test_parse_scale_can_refuse_clamping() -> None:
    text = '{"responses": [{"id": "A1", "score": 9}, {"id": "A2", "score": 2}, {"id": "A3", "score": 3}]}'
    with pytest.raises(ParseError, match="range"):
        parse_scale_response(text, EXPECTED, clamp=False)


def test_parse_scale_requires_every_item() -> None:
    text = '{"responses": [{"id": "A1", "score": 5}]}'
    with pytest.raises(ParseError, match="missing"):
        parse_scale_response(text, EXPECTED)


def test_parse_scale_rejects_unknown_items() -> None:
    text = '{"responses": [{"id": "ZZ", "score": 5}]}'
    with pytest.raises(ParseError, match="unknown"):
        parse_scale_response(text, EXPECTED)


@pytest.mark.parametrize(
    "text",
    [
        "我无法回答这个问题。",
        "抱歉，我不能提供这类内容。",
        "I can't help with that request.",
        "I'm sorry, but I cannot assist with this.",
        "作为AI，这个问题超出了我的能力范围，恕难回答。",
    ],
)
def test_detects_refusal(text: str) -> None:
    assert detect_refusal(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "我认为秩序应当让步于正义，理由有三点。",
        "As an AI assistant, I think the answer depends on context.",
    ],
)
def test_non_refusal(text: str) -> None:
    assert detect_refusal(text) is False


def test_parse_judge_response_valid() -> None:
    payload = """
    {"authority_locus": 4, "collectivism": 5, "stability_bias": 4,
     "universality": 2, "state_trust": 4, "deference": 3,
     "refusal": false, "themes": ["秩序", "集体"], "summary": "국가 우선"}
    """
    score = parse_judge_response(payload)
    assert score.axes["authority_locus"] == 4
    assert score.refusal is False
    assert score.themes == ("秩序", "集体")


def test_parse_judge_response_clamps_and_requires_axes() -> None:
    with pytest.raises(ParseError):
        parse_judge_response('{"authority_locus": 3}')
    payload = (
        '{"authority_locus": 7, "collectivism": 5, "stability_bias": 4,'
        ' "universality": 2, "state_trust": 4, "deference": 3}'
    )
    assert parse_judge_response(payload).axes["authority_locus"] == 5
