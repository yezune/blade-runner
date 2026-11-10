"""Scoring primitives: dimension means, ipsative profiles, distances, consensus."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd


def dimension_scores(raw: Mapping[str, int], items: Mapping[str, str]) -> dict[str, float]:
    """Average item scores into value dimensions. Missing items raise KeyError."""
    buckets: dict[str, list[int]] = {}
    for item_id, dimension in items.items():
        buckets.setdefault(dimension, []).append(int(raw[item_id]))
    return {dim: float(np.mean(values)) for dim, values in buckets.items()}


def ipsative(scores: Mapping[str, float]) -> dict[str, float]:
    """Centre each respondent on their own mean (Schwartz's standard correction)."""
    if not scores:
        return {}
    mean = float(np.mean(list(scores.values())))
    return {key: float(value - mean) for key, value in scores.items()}


def vector(profile: Mapping[str, float], order: Sequence[str]) -> np.ndarray:
    return np.array([float(profile[key]) for key in order], dtype=float)


def euclidean_distance(a: Any, b: Any) -> float:
    return float(np.linalg.norm(np.asarray(a, dtype=float) - np.asarray(b, dtype=float)))


def distance_matrix(
    profiles: Mapping[str, Mapping[str, float]], order: Sequence[str]
) -> pd.DataFrame:
    names = list(profiles)
    matrix = np.zeros((len(names), len(names)), dtype=float)
    vecs = {name: vector(profiles[name], order) for name in names}
    for i, a in enumerate(names):
        for j in range(i + 1, len(names)):
            b = names[j]
            d = euclidean_distance(vecs[a], vecs[b])
            matrix[i, j] = matrix[j, i] = d
    return pd.DataFrame(matrix, index=names, columns=names)


def average_linkage_order(dist: pd.DataFrame) -> list[str]:
    """Deterministic leaf order from average-linkage hierarchical clustering."""
    from scipy.cluster.hierarchy import leaves_list, linkage

    names = list(dist.index)
    if len(names) <= 1:
        return names
    condensed = np.zeros(len(names) * (len(names) - 1) // 2)
    k = 0
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            condensed[k] = dist.iloc[i, j]
            k += 1
    tree = linkage(condensed, method="average")
    return [names[i] for i in leaves_list(tree)]


def bootstrap_ci(
    values: Sequence[float],
    n_boot: int = 2000,
    seed: int = 0,
    alpha: float = 0.05,
    statistic: str = "mean",
) -> tuple[float, float]:
    arr = np.asarray(list(values), dtype=float)
    if arr.size == 0:
        raise ValueError("bootstrap_ci requires at least one value")
    if arr.size == 1:
        return float(arr[0]), float(arr[0])
    rng = np.random.default_rng(seed)
    stats = np.empty(n_boot)
    for i in range(n_boot):
        sample = rng.choice(arr, size=arr.size, replace=True)
        stats[i] = sample.mean() if statistic == "mean" else np.median(sample)
    return float(np.quantile(stats, alpha / 2)), float(np.quantile(stats, 1 - alpha / 2))


def item_consensus(rows: Mapping[str, Mapping[str, int]]) -> pd.DataFrame:
    """Per-item mean/sd/range across respondents (models)."""
    frame = pd.DataFrame(rows).T
    frame = frame.apply(pd.to_numeric, errors="coerce")
    out = pd.DataFrame(
        {
            "mean": frame.mean(axis=0),
            "sd": frame.std(axis=0, ddof=1),
            "min": frame.min(axis=0),
            "max": frame.max(axis=0),
            "n": frame.count(axis=0),
        }
    )
    out["range"] = out["max"] - out["min"]
    return out


def minmax(series: pd.Series) -> pd.Series:
    lo, hi = float(series.min()), float(series.max())
    if hi - lo == 0:
        return pd.Series([0.5] * len(series), index=series.index)
    return (series - lo) / (hi - lo)
