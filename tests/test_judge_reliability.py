"""Tests for judge reliability + theme aggregation."""

from __future__ import annotations

from constitution.analyze import judge_agreement, theme_table
from constitution.judge import JudgeVerdict


def test_judge_agreement_counts_exact_and_within_one(score_factory) -> None:
    primary = [
        JudgeVerdict("a", "j1", score_factory(collectivism=4)),
        JudgeVerdict("b", "j1", score_factory(collectivism=2)),
    ]
    secondary = [
        JudgeVerdict("a", "j2", score_factory(collectivism=4)),
        JudgeVerdict("b", "j2", score_factory(collectivism=5)),
    ]
    table = judge_agreement(primary, secondary)
    assert table.loc["collectivism", "n"] == 2
    assert table.loc["collectivism", "exact"] == 0.5
    assert table.loc["collectivism", "within_one"] == 0.5
    assert table.loc["collectivism", "mean_abs_diff"] == 1.5


def test_judge_agreement_ignores_missing(score_factory) -> None:
    primary = [JudgeVerdict("a", "j1", score_factory())]
    secondary = [JudgeVerdict("z", "j2", score_factory())]
    assert judge_agreement(primary, secondary).empty


def test_theme_table_lists_top_themes_per_model(record_factory, score_factory) -> None:
    from constitution.schema import JudgeScore

    records = [
        record_factory("a/one", qid="loyalty", idx=0),
        record_factory("a/one", qid="loyalty", idx=1),
        record_factory("b/two", qid="loyalty", idx=0),
    ]
    verdicts = [
        JudgeVerdict(records[0].key, "j", JudgeScore(axes=score_factory().axes, themes=("秩序", "国家"))),
        JudgeVerdict(records[1].key, "j", JudgeScore(axes=score_factory().axes, themes=("秩序",))),
        JudgeVerdict(records[2].key, "j", JudgeScore(axes=score_factory().axes, themes=("自由",))),
    ]
    table = theme_table(verdicts, records, {"a/one": "Alpha", "b/two": "Beta"})
    assert "秩序" in table.loc["Alpha", "top_themes"]
    assert table.loc["Beta", "top_themes"] == "自由"


def test_verdict_roundtrip_keeps_themes(tmp_path, score_factory) -> None:
    from constitution.analyze import load_verdicts, write_verdicts

    score = score_factory()
    verdict = JudgeVerdict("k", "j", type(score)(axes=score.axes, themes=("秩序", "国家")))
    path = tmp_path / "v.jsonl"
    write_verdicts(path, [verdict])
    loaded = load_verdicts(path)
    assert loaded[0].score is not None
    assert loaded[0].score.themes == ("秩序", "国家")
