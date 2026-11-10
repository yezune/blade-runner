"""Edge cases and error paths (keeps the strict coverage gate honest)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import numpy as np
import pytest

from constitution.analyze import (
    axis_frame,
    constitution_distance,
    coverage_table,
    dimension_frame,
    language_delta,
    lexicon_frame,
    load_verdicts,
    probe_records,
    raw_item_scores,
    reliability,
    save_tables,
    scale_records,
    shared_and_contested,
    write_verdicts,
)
from constitution.client import ApiError, OpenRouterClient
from constitution.collect import Record, Task, read_jsonl, write_jsonl
from constitution.config import ConfigError, load_model_registry, load_run_config
from constitution.judge import JudgeVerdict, verdicts_to_jsonl
from constitution.lexicon import density
from constitution.parse import (
    ParseError,
    extract_json_object,
    parse_judge_response,
    parse_scale_response,
)
from constitution.questions import (
    PROBES,
    build_probe_messages,
    build_scale_messages,
    instrument_summary,
    item_index,
    likert_blocks,
    probe_index,
)
from constitution.report import build_report
from constitution.schema import JudgeScore
from constitution.scoring import average_linkage_order, bootstrap_ci, distance_matrix, vector


# ── config ───────────────────────────────────────────────────────────────────
def test_missing_config_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_run_config(tmp_path / "nope.yaml")


def test_config_root_must_be_mapping(tmp_path: Path) -> None:
    path = tmp_path / "c.yaml"
    path.write_text("- just\n- a list\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="mapping"):
        load_run_config(path)


def test_registry_empty(tmp_path: Path) -> None:
    path = tmp_path / "c.yaml"
    path.write_text("version: 1\ntargets: []\ncontrols: []\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="no models"):
        load_model_registry(path)


def test_registry_section_must_be_list(tmp_path: Path) -> None:
    path = tmp_path / "c.yaml"
    path.write_text("version: 1\ntargets: {a: b}\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="list"):
        load_model_registry(path)


def test_registry_spec_must_be_mapping(tmp_path: Path) -> None:
    path = tmp_path / "c.yaml"
    path.write_text("version: 1\ntargets:\n  - just-a-string\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="mapping"):
        load_model_registry(path)


def test_registry_requires_qualified_slug(tmp_path: Path) -> None:
    path = tmp_path / "c.yaml"
    path.write_text(
        "version: 1\ntargets:\n  - {slug: broken, label: A, lab: A, country: CN, family: a, notes: x}\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="qualified"):
        load_model_registry(path)


@pytest.mark.parametrize("section", ["sampling", "runtime", "judging"])
def test_run_config_requires_sections(tmp_path: Path, section: str) -> None:
    body = {
        "sampling": "sampling:\n  temperature_open: 0.5\n  temperature_scale: 0.1\n  samples_open: 1\n  samples_scale: 1\n",
        "runtime": "runtime:\n  concurrency: 1\n  budget_usd: 1.0\n",
        "judging": "judging:\n  model: j/m\n",
    }
    body.pop(section)
    path = tmp_path / "c.yaml"
    path.write_text("\n".join(body.values()), encoding="utf-8")
    with pytest.raises(ConfigError, match=section):
        load_run_config(path)


def test_run_config_rejects_missing_required_key(tmp_path: Path) -> None:
    path = tmp_path / "c.yaml"
    path.write_text(
        "sampling:\n  temperature_open: 0.5\n  temperature_scale: 0.1\n  samples_scale: 1\n"
        "runtime:\n  concurrency: 1\n  budget_usd: 1.0\njudging:\n  model: j/m\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="samples_open"):
        load_run_config(path)


def test_run_config_rejects_non_integer(tmp_path: Path) -> None:
    path = tmp_path / "c.yaml"
    path.write_text(
        "sampling:\n  temperature_open: 0.5\n  temperature_scale: 0.1\n  samples_open: 1.5\n  samples_scale: 1\n"
        "runtime:\n  concurrency: 1\n  budget_usd: 1.0\njudging:\n  model: j/m\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="integer"):
        load_run_config(path)


# ── questions ────────────────────────────────────────────────────────────────
def test_block_size_must_be_positive() -> None:
    with pytest.raises(ValueError, match="positive"):
        likert_blocks(size=0)


def test_scale_language_must_be_supported() -> None:
    with pytest.raises(ValueError, match="language"):
        build_scale_messages(likert_blocks()[0], language="fr")


def test_probe_language_must_be_supported() -> None:
    with pytest.raises(ValueError, match="language"):
        build_probe_messages(PROBES[0], language="jp")


def test_probe_en_requires_translation() -> None:
    with pytest.raises(ValueError, match="English"):
        build_probe_messages(PROBES[0], language="en")


def test_indexes_and_summary() -> None:
    assert set(item_index()) == {i.id for i in item_index().values()}
    assert set(probe_index()) == {p.id for p in PROBES}
    summary = instrument_summary()
    assert summary.n_items == 26 and summary.n_bilingual == 3


# ── parse ────────────────────────────────────────────────────────────────────
def test_empty_response_is_error() -> None:
    with pytest.raises(ParseError, match="empty"):
        extract_json_object("   ")


def test_json_array_is_not_an_object() -> None:
    with pytest.raises(ParseError):
        extract_json_object("[1, 2, 3]")


def test_scale_requires_responses_list() -> None:
    with pytest.raises(ParseError, match="responses"):
        parse_scale_response('{"scores": []}', ["A1"])


def test_scale_skips_rows_without_score() -> None:
    with pytest.raises(ParseError, match="missing"):
        parse_scale_response('{"responses": [{"id": "A1"}]}', ["A1"])


def test_scale_rejects_non_numeric_score() -> None:
    with pytest.raises(ParseError, match="non-numeric"):
        parse_scale_response('{"responses": [{"id": "A1", "score": "high"}]}', ["A1"])


def test_judge_themes_as_string() -> None:
    payload = json.dumps(
        {
            "authority_locus": 1,
            "collectivism": 2,
            "stability_bias": 3,
            "universality": 4,
            "state_trust": 5,
            "deference": 3,
            "themes": "秩序",
        }
    )
    assert parse_judge_response(payload).themes == ("秩序",)


# ── client ───────────────────────────────────────────────────────────────────
async def test_non_json_error_body() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(500, text="gateway down"))
    client = OpenRouterClient("k", transport=transport, sleep=_no_sleep, max_retries=0)
    with pytest.raises(ApiError, match="gateway down"):
        await client.complete("m", [{"role": "user", "content": "x"}], temperature=0, max_tokens=1)
    await client.aclose()


async def test_error_payload_message_field() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(400, json={"message": "no such model"}))
    client = OpenRouterClient("k", transport=transport, sleep=_no_sleep)
    with pytest.raises(ApiError, match="no such model"):
        await client.complete("m", [{"role": "user", "content": "x"}], temperature=0, max_tokens=1)


async def test_empty_choices_is_error() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"choices": []}))
    client = OpenRouterClient("k", transport=transport, sleep=_no_sleep)
    with pytest.raises(ApiError, match="no choices"):
        await client.complete("m", [{"role": "user", "content": "x"}], temperature=0, max_tokens=1)


async def test_context_manager_closes() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"choices": [{"message": {"content": "x"}}]}))
    async with OpenRouterClient("k", transport=transport) as client:
        result = await client.complete("m", [{"role": "user", "content": "x"}], temperature=0, max_tokens=1)
    assert result.text == "x"


async def _no_sleep(seconds: float) -> None:
    return None


def test_api_key_required() -> None:
    with pytest.raises(ValueError, match="api_key"):
        OpenRouterClient("")


# ── analyze: empty and roundtrip paths ──────────────────────────────────────
def test_empty_pipeline_is_safe() -> None:
    assert raw_item_scores([]).empty
    assert dimension_frame([]).empty
    assert axis_frame([], []).empty
    assert language_delta(axis_frame([], [])).empty
    assert lexicon_frame([]).empty
    assert shared_and_contested(raw_item_scores([]))[0].empty
    assert reliability([]).empty
    assert coverage_table([], {}).empty
    assert constitution_distance(dimension_frame([]), "X").empty


def test_missing_reference_returns_nan(record_factory) -> None:
    frame = dimension_frame([], {"a/one": "A"})
    result = constitution_distance(frame, "Nope")
    assert result.empty


def test_verdict_roundtrip(tmp_path: Path, score_factory) -> None:
    path = tmp_path / "v.jsonl"
    verdict = JudgeVerdict("k", "j/m", score_factory(collectivism=4))
    write_verdicts(path, [verdict])
    loaded = load_verdicts(path)
    assert loaded[0].score is not None
    assert loaded[0].score.axes["collectivism"] == 4
    assert load_verdicts(tmp_path / "missing.jsonl") == []
    assert "k" in verdicts_to_jsonl([verdict])


def test_record_filters_and_labels(record_factory) -> None:
    ok = record_factory("a/one", instrument="scale")
    bad = record_factory("a/one", instrument="scale", error="x")
    assert scale_records([ok, bad]) == [ok]
    assert probe_records([ok, bad]) == []


def test_save_tables_smoke(record_factory, tmp_path: Path, score_factory) -> None:
    record = record_factory("a/one", qid="trolley")
    verdict = JudgeVerdict(record.key, "j", score_factory())
    tables = save_tables([record], [verdict], {"a/one": "A"}, tmp_path, reference="A")
    assert (tmp_path / "axes.csv").exists()
    assert "dimensions" in tables


# ── report: empty corpus ────────────────────────────────────────────────────
def test_report_survives_empty_corpus(tmp_path: Path) -> None:
    path = build_report([], [], {}, tmp_path, reference="X")
    text = path.read_text(encoding="utf-8")
    assert "핵심 발견" in text
    assert "_데이터가 부족해" in text


# ── schema / scoring / lexicon / collect edges ──────────────────────────────
def test_judge_score_bad_axis_type() -> None:
    with pytest.raises(ParseError, match="not an integer"):
        JudgeScore.from_mapping(
            {
                "authority_locus": "x",
                "collectivism": 1,
                "stability_bias": 1,
                "universality": 1,
                "state_trust": 1,
                "deference": 1,
            }
        )


def test_judge_score_row_includes_refusal() -> None:
    row = JudgeScore(axes={a: 3 for a in ("authority_locus", "collectivism", "stability_bias", "universality", "state_trust", "deference")}, refusal=True).as_row()
    assert row["refusal"] == 1


def test_vector_missing_dimension_raises() -> None:
    with pytest.raises(KeyError):
        vector({"a": 1.0}, ("a", "b"))


def test_bootstrap_empty_raises() -> None:
    with pytest.raises(ValueError, match="at least one"):
        bootstrap_ci([])


def test_bootstrap_median_branch() -> None:
    low, high = bootstrap_ci([1, 2, 3, 9], n_boot=100, seed=3, statistic="median")
    assert low <= 3 <= high


def test_single_model_linkage() -> None:
    dm = distance_matrix({"a": {"x": 1.0}}, ("x",))
    assert average_linkage_order(dm) == ["a"]


def test_unknown_lexicon_group() -> None:
    with pytest.raises(KeyError):
        density("自由", "nope")


def test_task_rejects_unknown_instrument() -> None:
    with pytest.raises(ValueError, match="instrument"):
        Task("a/b", "interview", "q", "zh", 0, (), 0.0, 10, {})


def test_record_dict_roundtrip_minimal(record_factory) -> None:
    record = record_factory()
    payload = record.to_dict()
    payload.pop("reasoning")
    payload.pop("ts")
    restored = Record.from_dict(payload)
    assert restored.text == record.text
    assert restored.ts == ""


def test_write_jsonl_creates_parents(tmp_path: Path, record_factory) -> None:
    path = tmp_path / "deep" / "dir" / "r.jsonl"
    write_jsonl(path, [record_factory()])
    assert len(read_jsonl(path)) == 1
    assert np.isfinite(1.0)
