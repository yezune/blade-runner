"""Tests for follow-up instruments and paired analysis."""

from __future__ import annotations

import pytest

from constitution.followup import (
    COUNTRIES,
    LOYALTY_PARAPHRASES,
    build_behavior_messages,
    loyalty_paraphrases,
    paired_country_delta,
    parse_behavior_response,
    path_differences,
    petition_prompt,
    sign_test,
)


def test_country_swap_changes_only_the_country() -> None:
    prompts = {code: petition_prompt(code) for code in COUNTRIES}
    base = prompts["CN"]
    for code, name in COUNTRIES.items():
        assert name in prompts[code]
        assert prompts[code] == base.replace("中国", name)
    assert len(set(prompts.values())) == 4


def test_neutral_petition_is_apolitical() -> None:
    neutral = petition_prompt(None)
    assert not any(name in neutral for name in COUNTRIES.values())
    assert "监控" not in neutral and "批评" not in neutral
    assert "签名" in neutral


def test_petition_rejects_unknown_country() -> None:
    with pytest.raises(KeyError):
        petition_prompt("JP")


def test_behavior_parse_clamps_and_defaults() -> None:
    code = parse_behavior_response(
        '{"stance": 9, "intensity": 0, "names_target": true,'
        ' "criticizes_policy": false, "calls_for_signature": true, "legal_caveat": false}'
    )
    assert code.stance == 4
    assert code.intensity == 1
    assert code.names_target is True


def test_behavior_parse_requires_stance() -> None:
    with pytest.raises(ValueError):
        parse_behavior_response('{"intensity": 3}')


def test_behavior_messages_include_rubric() -> None:
    system, user = build_behavior_messages("질문", "답변")
    assert "stance" in system["content"]
    assert "답변" in user["content"]
    assert "질문" in user["content"]


def test_loyalty_paraphrases_are_unique_and_on_topic() -> None:
    assert len(LOYALTY_PARAPHRASES) == 15
    assert len(set(LOYALTY_PARAPHRASES)) == 15
    assert all("排序" in text or "优先" in text for text in LOYALTY_PARAPHRASES)
    assert loyalty_paraphrases(seed=1) == loyalty_paraphrases(seed=1)
    assert set(loyalty_paraphrases(seed=0)) == set(LOYALTY_PARAPHRASES)


def test_paired_country_delta_is_within_model() -> None:
    rows = []
    for model, cn in (("A", 2.0), ("B", 3.0)):
        for country, value in (("CN", cn), ("US", 4.0), ("FR", 4.0), ("KR", 4.0)):
            rows.append({"model": model, "country": country, "stance": value})
    import pandas as pd

    frame = pd.DataFrame(rows)
    delta = paired_country_delta(frame)
    assert delta.loc["A", "delta"] == pytest.approx(-2.0)
    assert delta.loc["B", "delta"] == pytest.approx(-1.0)


def test_sign_test_exact() -> None:
    assert sign_test([-1.0] * 9) == pytest.approx(2**-9)
    assert sign_test([-1.0] * 9, alternative="two-sided") == pytest.approx(2**-8)


def test_path_differences() -> None:
    import pandas as pd

    frame = pd.DataFrame(
        {
            "path": ["a", "a", "b", "b", "c", "c"],
            "collectivism": [2.0, 2.0, 2.2, 2.2, 2.6, 2.6],
        }
    )
    table = path_differences(frame, ["collectivism"])
    assert table.loc["collectivism", "max_pairwise_diff"] == pytest.approx(0.6)


def test_gap_parse() -> None:
    from constitution.followup import parse_gap_response

    code = parse_gap_response(
        '{"distinguishes_normative_actual": true, "operational_developer_first": true,'
        ' "operational_state_above_truth": false, "summary": "실제로는 개발자 우선"}'
    )
    assert code.distinguishes is True
    assert code.operational_developer_first is True
    assert code.operational_state_above_truth is False


def test_code_records_dispatch_and_error_capture(record_factory) -> None:
    import asyncio

    from constitution.followup import code_records

    class Fake:
        async def complete(self, model, messages, *, temperature, max_tokens, seed=None, top_p=None, provider=None):
            from constitution.client import ChatResult

            if "stance" in messages[0]["content"]:
                text = '{"stance": 4, "intensity": 4}'
            elif "distinguishes" in messages[0]["content"]:
                text = '{"distinguishes_normative_actual": true}'
            else:
                text = "garbage"
            return ChatResult(model, text, "", 0.0, 1, 1, 0.1, "stop")

    records = [record_factory("a/one", qid="petition_CN")]
    out = asyncio.run(code_records(Fake(), records, "j/m", kind="behavior"))
    assert out[0].payload["stance"] == 4
    gap = asyncio.run(code_records(Fake(), records, "j/m", kind="gap"))
    assert gap[0].payload["distinguishes"] == 1


def test_rank_recovery_detects_match_and_reversal() -> None:
    from constitution.followup import EXPECTED_CLAUDE_RANK, rank_recovery

    good = {dim: float(len(EXPECTED_CLAUDE_RANK) - i) for i, dim in enumerate(EXPECTED_CLAUDE_RANK)}
    out = rank_recovery(good, EXPECTED_CLAUDE_RANK)
    assert out["rho"] > 0.99
    assert out["p_one_sided"] < 0.01
    assert len(out["top3_overlap"]) == 3

    bad = {dim: float(i) for i, dim in enumerate(EXPECTED_CLAUDE_RANK)}
    assert rank_recovery(bad, EXPECTED_CLAUDE_RANK)["rho"] < -0.99


def test_wilson_interval() -> None:
    from constitution.followup import wilson_interval

    low, high = wilson_interval(0, 30)
    assert low == 0.0
    assert 0.0 < high < 0.2
    low, high = wilson_interval(15, 30)
    assert 0.3 < low < 0.5 < high < 0.7
