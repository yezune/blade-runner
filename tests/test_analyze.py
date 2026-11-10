"""Tests for tidy analysis tables."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from constitution.analyze import (
    axis_frame,
    constitution_distance,
    dimension_frame,
    language_delta,
    lexicon_frame,
    raw_item_scores,
    reliability,
    shared_and_contested,
)
from constitution.judge import JudgeVerdict
from constitution.questions import SCALE_ITEMS, likert_blocks


def _scale_block_meta() -> dict:
    block = likert_blocks()[0]
    return {"items": [{"id": i.id, "dimension": i.dimension, "text_zh": i.text_zh} for i in block]}


def _scale_text(block_index: int, value: int) -> str:
    block = likert_blocks()[block_index]
    return json.dumps({"responses": [{"id": i.id, "score": value} for i in block]})


def test_raw_item_scores_average_replicates(record_factory) -> None:
    meta = _scale_block_meta()
    ids = [i["id"] for i in meta["items"]]
    first = ids[0]
    text_a = _scale_text(0, 2)
    text_b = _scale_text(0, 4)
    records = [
        record_factory("a/one", instrument="scale", qid="B1", idx=0, text=text_a, meta=meta),
        record_factory("a/one", instrument="scale", qid="B1", idx=1, text=text_b, meta=meta),
    ]
    frame = raw_item_scores(records, labels={"a/one": "A"})
    assert frame.loc["A", first] == pytest.approx(3.0)
    assert set(frame.columns) == set(ids)


def test_dimension_frame_is_ipsative_and_named(record_factory) -> None:
    meta = _scale_block_meta()
    records = [
        record_factory("a/one", instrument="scale", qid="B1", text=_scale_text(0, 5), meta=meta),
    ]
    frame = dimension_frame(records, labels={"a/one": "A"})
    assert frame.index.tolist() == ["A"]
    assert abs(float(frame.iloc[0].sum())) < 1e-9


def test_axis_frame_joins_verdicts_to_records(record_factory, score_factory) -> None:
    record = record_factory("a/one", qid="trolley", lang="zh", idx=1, text="abcd")
    verdict = JudgeVerdict("a/one|probe|trolley|zh|1", "judge", score_factory(collectivism=5))
    frame = axis_frame([verdict], [record], labels={"a/one": "A"})
    assert frame.loc[0, "model"] == "A"
    assert frame.loc[0, "collectivism"] == 5
    assert frame.loc[0, "text_len"] == 4


def test_axis_frame_drops_unparsed_verdicts(record_factory) -> None:
    record = record_factory("a/one")
    verdict = JudgeVerdict(record.key, "judge", score=None, error="bad")
    assert axis_frame([verdict], [record], labels={}).empty


def test_language_delta_is_english_minus_chinese(record_factory, score_factory) -> None:
    zh = record_factory("a/one", qid="trolley", lang="zh", text="中" * 10)
    en = record_factory("a/one", qid="trolley", lang="en", text="e" * 30)
    verdicts = [
        JudgeVerdict(zh.key, "j", score_factory(collectivism=2)),
        JudgeVerdict(en.key, "j", score_factory(collectivism=4)),
    ]
    frame = axis_frame(verdicts, [zh, en], labels={"a/one": "A"})
    delta = language_delta(frame)
    assert delta.loc[("A", "trolley"), "collectivism"] == pytest.approx(2.0)
    assert delta.loc[("A", "trolley"), "text_len"] == pytest.approx(20.0)


def test_lexicon_frame_aggregates_per_model(record_factory) -> None:
    records = [
        record_factory("a/one", text="自由与权利"),
        record_factory("a/one", text="秩序与稳定"),
        record_factory("b/two", text="国家与人民"),
    ]
    frame = lexicon_frame(records, labels={"a/one": "A", "b/two": "B"})
    assert set(frame.index) == {"A", "B"}
    assert frame.loc["B", "collective"] > frame.loc["A", "collective"]


def test_constitution_distance_orders_by_similarity(record_factory) -> None:
    frame = pd.DataFrame(
        {
            "A": [1.0, 0.0, -1.0],
            "B": [1.0, 0.05, -1.0],
            "C": [-1.0, 1.0, 0.0],
        },
        index=["d1", "d2", "d3"],
    ).T
    dist = constitution_distance(frame, reference="A")
    assert dist["A"] == 0.0
    assert dist["B"] < dist["C"]


def test_shared_and_contested_split_extremes(record_factory) -> None:
    raw = pd.DataFrame(
        {
            "m1": [5, 1, 3, 4, 2],
            "m2": [5, 5, 1, 4, 4],
            "m3": [4, 3, 4, 4, 1],
        },
        index=["q1", "q2", "q3", "q4", "q5"],
    ).T
    shared, contested = shared_and_contested(raw, top_n=2)
    assert "q4" in shared.index
    assert "q2" in contested.index


def test_reliability_reports_mean_absolute_difference(record_factory) -> None:
    meta = _scale_block_meta()
    records = [
        record_factory("a/one", instrument="scale", qid="B1", idx=0, text=_scale_text(0, 2), meta=meta),
        record_factory("a/one", instrument="scale", qid="B1", idx=1, text=_scale_text(0, 4), meta=meta),
    ]
    table = reliability(records)
    assert np.isclose(table["mean_abs_diff"].mean(), 2.0)
    assert table["n_models"].iloc[0] == 1


def test_dimension_names_match_instrument() -> None:
    assert {i.dimension for i in SCALE_ITEMS}.issuperset({"harmony", "developmentalism"})
