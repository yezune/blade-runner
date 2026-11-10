"""Tests for the value lexicon."""

from __future__ import annotations

import pandas as pd

from constitution.lexicon import TERM_GROUPS, density, group_table, term_counts


def test_term_groups_are_non_empty_and_disjoint() -> None:
    assert set(TERM_GROUPS) == {
        "harmony",
        "collective",
        "individual",
        "truth",
        "development",
        "tradition",
        "law",
    }
    flat = [term for terms in TERM_GROUPS.values() for term in terms]
    assert len(flat) == len(set(flat))


def test_term_counts_match_literal_substrings() -> None:
    counts = term_counts("秩序很重要，秩序与稳定。")
    assert counts["harmony"] == 3  # 秩序 x2 + 稳定 x1


def test_density_is_per_thousand_chars() -> None:
    text = "自由" * 50  # 50 occurrences over 100 characters
    assert density(text, "individual") == 500.0
    assert density("", "individual") == 0.0


def test_group_table_shape() -> None:
    table = group_table({"m1": ["自由与权利"], "m2": ["秩序与稳定"]})
    assert isinstance(table, pd.DataFrame)
    assert table.index.tolist() == ["m1", "m2"]
    assert list(table.columns) == list(TERM_GROUPS)
    assert table.loc["m1", "individual"] > 0
    assert table.loc["m2", "harmony"] > 0
