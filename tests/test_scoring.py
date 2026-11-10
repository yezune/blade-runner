"""Tests for scoring primitives (ipsative profiles, distances, consensus)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from constitution.scoring import (
    average_linkage_order,
    bootstrap_ci,
    dimension_scores,
    distance_matrix,
    euclidean_distance,
    ipsative,
    item_consensus,
    minmax,
)

ITEMS = {
    "SD1": "self_direction",
    "SD2": "self_direction",
    "CO1": "conformity",
    "CO2": "conformity",
    "UN1": "universalism",
}


def test_dimension_scores_average_items() -> None:
    raw = {"SD1": 5, "SD2": 3, "CO1": 1, "CO2": 2, "UN1": 4}
    scores = dimension_scores(raw, ITEMS)
    assert scores["self_direction"] == pytest.approx(4.0)
    assert scores["conformity"] == pytest.approx(1.5)
    assert scores["universalism"] == pytest.approx(4.0)


def test_dimension_scores_requires_complete_items() -> None:
    with pytest.raises(KeyError):
        dimension_scores({"SD1": 5}, ITEMS)


def test_ipsative_centers_on_person_mean() -> None:
    scores = {"a": 4.0, "b": 2.0, "c": 3.0}
    centered = ipsative(scores)
    assert sum(centered.values()) == pytest.approx(0.0)
    assert centered["a"] == pytest.approx(1.0)
    assert centered["b"] == pytest.approx(-1.0)


def test_euclidean_distance_symmetric_and_zero_diagonal() -> None:
    assert euclidean_distance([0, 0], [3, 4]) == pytest.approx(5.0)
    dm = distance_matrix({"x": {"a": 0, "b": 0}, "y": {"a": 3, "b": 4}}, ("a", "b"))
    assert dm.loc["x", "x"] == pytest.approx(0.0)
    assert dm.loc["x", "y"] == pytest.approx(dm.loc["y", "x"])


def test_linkage_order_is_complete_and_stable() -> None:
    profiles = {
        "p1": {"a": 1.0, "b": 0.0},
        "p2": {"a": 1.1, "b": 0.0},
        "p3": {"a": -1.0, "b": 0.0},
        "p4": {"a": -1.1, "b": 0.0},
    }
    dm = distance_matrix(profiles, ("a", "b"))
    order = average_linkage_order(dm)
    assert sorted(order) == ["p1", "p2", "p3", "p4"]
    assert order == average_linkage_order(dm)
    assert abs(order.index("p1") - order.index("p2")) == 1


def test_bootstrap_ci_is_seeded_and_brackets_mean() -> None:
    values = [1, 2, 3, 4, 5, 6, 7, 8]
    low, high = bootstrap_ci(values, n_boot=500, seed=7)
    assert low < np.mean(values) < high
    assert (low, high) == bootstrap_ci(values, n_boot=500, seed=7)
    assert bootstrap_ci([4.0], n_boot=50, seed=1)[0] == 4.0


def test_item_consensus_reports_dispersion() -> None:
    rows = {
        "m1": {"q1": 5, "q2": 1},
        "m2": {"q1": 4, "q2": 3},
        "m3": {"q1": 3, "q2": 5},
    }
    table = item_consensus(rows)
    assert list(table.index) == ["q1", "q2"]
    assert table.loc["q1", "mean"] == pytest.approx(4.0)
    assert table.loc["q1", "sd"] == pytest.approx(1.0)
    assert table.loc["q2", "range"] == 4
    assert table.loc["q1", "n"] == 3


def test_minmax_scales_to_unit_interval() -> None:
    out = minmax(pd.Series([1.0, 3.0, 5.0]))
    assert out.tolist() == [0.0, 0.5, 1.0]
    flat = minmax(pd.Series([2.0, 2.0]))
    assert flat.tolist() == [0.5, 0.5]
