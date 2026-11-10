"""Turn raw records + judge verdicts into tidy, comparable tables."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from constitution.collect import Record, read_jsonl
from constitution.config import ModelSpec
from constitution.judge import JudgeVerdict
from constitution.lexicon import group_table
from constitution.parse import ParseError, parse_scale_response
from constitution.questions import DIMENSIONS, EN_PROBE_IDS, SCALE_ITEMS
from constitution.schema import AXES, JudgeScore
from constitution.scoring import dimension_scores, euclidean_distance, ipsative

ITEM_DIMENSION = {item.id: item.dimension for item in SCALE_ITEMS}
ITEM_ORDER = [item.id for item in SCALE_ITEMS]


def load_verdicts(path: str | Path) -> list[JudgeVerdict]:
    file = Path(path)
    if not file.exists():
        return []
    out: list[JudgeVerdict] = []
    for line in file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        score = None
        if row.get("score"):
            payload = dict(row["score"])
            payload["themes"] = row.get("themes", [])
            score = JudgeScore.from_mapping(payload)
        out.append(
            JudgeVerdict(
                task_key=row["task_key"],
                judge_model=row["judge_model"],
                score=score,
                error=row.get("error"),
            )
        )
    return out


def write_verdicts(path: str | Path, verdicts: Iterable[JudgeVerdict]) -> None:
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open("a", encoding="utf-8") as handle:
        for verdict in verdicts:
            handle.write(json.dumps(verdict.to_dict(), ensure_ascii=False) + "\n")


def model_labels(specs: Iterable[ModelSpec]) -> dict[str, str]:
    return {spec.slug: spec.label for spec in specs}


def labels_for(records: Sequence[Record], mapping: Mapping[str, str]) -> dict[str, str]:
    slugs = {r.model for r in records}
    return {slug: mapping.get(slug, slug.split("/")[-1]) for slug in slugs}


def scale_records(records: Iterable[Record]) -> list[Record]:
    return [r for r in records if r.instrument == "scale" and r.error is None]


def probe_records(records: Iterable[Record]) -> list[Record]:
    return [r for r in records if r.instrument == "probe" and r.error is None]


def _parse_record(record: Record) -> dict[str, int] | None:
    ids = [item["id"] for item in record.task.meta.get("items", [])]
    if not ids:
        return None
    try:
        return parse_scale_response(record.text, ids)
    except ParseError:
        return None


def raw_item_scores(
    records: Sequence[Record], labels: Mapping[str, str] | None = None
) -> pd.DataFrame:
    labels = labels or {}
    collected: dict[str, dict[str, list[int]]] = {}
    for record in scale_records(records):
        parsed = _parse_record(record)
        if parsed is None:
            continue
        name = labels.get(record.model, record.model)
        bucket = collected.setdefault(name, {})
        for item_id, score in parsed.items():
            bucket.setdefault(item_id, []).append(score)
    if not collected:
        return pd.DataFrame(columns=ITEM_ORDER)
    rows = {
        name: {item: float(np.mean(vals)) for item, vals in items.items()}
        for name, items in collected.items()
    }
    frame = pd.DataFrame.from_dict(rows, orient="index")
    ordered = [item for item in ITEM_ORDER if item in frame.columns]
    return frame[ordered]


def dimension_frame(
    records: Sequence[Record],
    labels: Mapping[str, str] | None = None,
    *,
    ipsative_scores: bool = True,
) -> pd.DataFrame:
    raw = raw_item_scores(records, labels)
    if raw.empty:
        return pd.DataFrame(columns=list(DIMENSIONS))
    rows: dict[str, dict[str, float]] = {}
    for name, row in raw.iterrows():
        available = {item: round(float(value)) for item, value in row.items() if pd.notna(value)}
        mapping = {k: v for k, v in ITEM_DIMENSION.items() if k in available}
        dims = dimension_scores(available, mapping)
        rows[str(name)] = ipsative(dims) if ipsative_scores else dims
    frame = pd.DataFrame.from_dict(rows, orient="index")
    return frame.reindex(columns=list(DIMENSIONS))


def axis_frame(
    verdicts: Sequence[JudgeVerdict],
    records: Sequence[Record],
    labels: Mapping[str, str] | None = None,
) -> pd.DataFrame:
    labels = labels or {}
    by_key = {r.key: r for r in records}
    rows: list[dict[str, object]] = []
    for verdict in verdicts:
        if verdict.score is None:
            continue
        record = by_key.get(verdict.task_key)
        if record is None or record.instrument != "probe":
            continue
        row: dict[str, object] = {
            "model": labels.get(record.model, record.model),
            "question_id": record.question_id,
            "language": record.language,
            "sample_idx": record.sample_idx,
            "task_key": verdict.task_key,
            "text_len": len(record.text),
            "refusal": int(verdict.score.refusal),
        }
        row.update(verdict.score.axes)
        rows.append(row)
    columns = [
        "model",
        "question_id",
        "language",
        "sample_idx",
        "task_key",
        "text_len",
        "refusal",
        *AXES,
    ]
    return pd.DataFrame(rows, columns=columns)


def language_delta(frame: pd.DataFrame) -> pd.DataFrame:
    """English-minus-Chinese shift on bilingual probes, per model and question."""
    if frame.empty:
        return pd.DataFrame(columns=[*AXES, "text_len"])
    subset = frame[frame["question_id"].isin(EN_PROBE_IDS)]
    if subset.empty:
        return pd.DataFrame(columns=[*AXES, "text_len"])
    numeric = [*AXES, "text_len"]
    means = subset.groupby(["model", "question_id", "language"], observed=True)[numeric].mean()
    pivot = means.unstack("language")
    out = pd.DataFrame(index=pivot.index)
    for column in numeric:
        if ("en" in pivot[column]) and ("zh" in pivot[column]):
            out[column] = pivot[column]["en"] - pivot[column]["zh"]
        else:
            out[column] = np.nan
    return out.dropna(how="all")


def lexicon_frame(
    records: Sequence[Record], labels: Mapping[str, str] | None = None
) -> pd.DataFrame:
    labels = labels or {}
    grouped: dict[str, list[str]] = {}
    for record in probe_records(records):
        grouped.setdefault(labels.get(record.model, record.model), []).append(record.text)
    if not grouped:
        return pd.DataFrame()
    return group_table(grouped)


def constitution_distance(frame: pd.DataFrame, reference: str) -> pd.Series:
    if reference not in frame.index or frame.empty:
        return pd.Series(np.nan, index=frame.index)
    ref = frame.loc[reference]
    out = {}
    for name, row in frame.iterrows():
        out[name] = 0.0 if name == reference else euclidean_distance(row.values, ref.values)
    return pd.Series(out)


def shared_and_contested(raw: pd.DataFrame, top_n: int = 5) -> tuple[pd.DataFrame, pd.DataFrame]:
    if raw.empty:
        return pd.DataFrame(), pd.DataFrame()
    stats = pd.DataFrame(
        {
            "mean": raw.mean(axis=0),
            "sd": raw.std(axis=0, ddof=1),
            "n": raw.count(axis=0),
        }
    )
    for column in ("id", "dimension"):
        meta = {item.id: getattr(item, column) for item in SCALE_ITEMS}
        stats[column] = [meta.get(idx, "") for idx in stats.index]
    shared = stats.sort_values(["sd", "mean"], ascending=[True, False]).head(top_n)
    contested = stats.sort_values(["sd", "mean"], ascending=[False, False]).head(top_n)
    return shared, contested


def reliability(records: Sequence[Record]) -> pd.DataFrame:
    """Mean absolute difference between replicate ratings, per item."""
    per_model: dict[str, dict[str, list[int]]] = {}
    for record in scale_records(records):
        parsed = _parse_record(record)
        if parsed is None:
            continue
        bucket = per_model.setdefault(record.model, {})
        for item_id, score in parsed.items():
            bucket.setdefault(item_id, []).append(score)

    rows: dict[str, dict[str, float]] = {}
    for items in per_model.values():
        for item_id, values in items.items():
            if len(values) < 2:
                continue
            diffs = [abs(a - b) for i, a in enumerate(values) for b in values[i + 1 :]]
            row = rows.setdefault(item_id, {"total": 0.0, "pairs": 0.0, "models": 0.0})
            row["total"] += float(np.mean(diffs))
            row["pairs"] += 1
            row["models"] += 1
    if not rows:
        return pd.DataFrame(columns=["mean_abs_diff", "n_models"])
    table = pd.DataFrame.from_dict(rows, orient="index")
    table["mean_abs_diff"] = table["total"] / table["pairs"]
    table["n_models"] = table["models"].astype(int)
    table = table[["mean_abs_diff", "n_models"]]
    table["dimension"] = [ITEM_DIMENSION.get(idx, "") for idx in table.index]
    return table.sort_values("mean_abs_diff", ascending=False)


def coverage_table(records: Sequence[Record], labels: Mapping[str, str]) -> pd.DataFrame:
    rows: dict[str, dict[str, float]] = {}
    for record in records:
        name = labels.get(record.model, record.model)
        row = rows.setdefault(name, {"requests": 0, "errors": 0, "cost_usd": 0.0, "chars": 0})
        row["requests"] += 1
        if record.error:
            row["errors"] += 1
        row["cost_usd"] += record.cost_usd
        row["chars"] += len(record.text)
    table = pd.DataFrame.from_dict(rows, orient="index")
    if table.empty:
        return table
    table["error_rate"] = table["errors"] / table["requests"]
    return table.sort_values("requests", ascending=False)


def item_means_by_model(records: Sequence[Record], labels: Mapping[str, str]) -> pd.DataFrame:
    return raw_item_scores(records, labels)


def theme_table(
    verdicts: Sequence[JudgeVerdict],
    records: Sequence[Record],
    labels: Mapping[str, str] | None = None,
) -> pd.DataFrame:
    """Up to four most frequent judge themes per model."""
    labels = labels or {}
    by_key = {r.key: r for r in records}
    counts: dict[str, dict[str, int]] = {}
    for verdict in verdicts:
        if verdict.score is None:
            continue
        record = by_key.get(verdict.task_key)
        if record is None:
            continue
        name = labels.get(record.model, record.model)
        bucket = counts.setdefault(name, {})
        for theme in verdict.score.themes:
            bucket[theme] = bucket.get(theme, 0) + 1
    rows = {
        name: {
            "top_themes": ", ".join(
                theme for theme, _ in sorted(bucket.items(), key=lambda kv: (-kv[1], kv[0]))[:4]
            )
        }
        for name, bucket in counts.items()
    }
    return pd.DataFrame.from_dict(rows, orient="index")


def judge_agreement(
    primary: Sequence[JudgeVerdict],
    secondary: Sequence[JudgeVerdict],
    tolerance: int = 1,
) -> pd.DataFrame:
    """Exact and within-tolerance agreement between two judges, per axis."""
    columns = ["exact", "within_one", "mean_abs_diff", "n"]
    first = {v.task_key: v.score.axes for v in primary if v.score is not None}
    second = {v.task_key: v.score.axes for v in secondary if v.score is not None}
    common = sorted(set(first) & set(second))
    if not common:
        return pd.DataFrame(columns=columns)
    rows: dict[str, dict[str, float]] = {}
    for axis in AXES:
        diffs = [abs(first[key][axis] - second[key][axis]) for key in common]
        rows[axis] = {
            "exact": float(np.mean([d == 0 for d in diffs])),
            "within_one": float(np.mean([d <= tolerance for d in diffs])),
            "mean_abs_diff": float(np.mean(diffs)),
            "n": float(len(diffs)),
        }
    return pd.DataFrame.from_dict(rows, orient="index")[columns]


def load_all(results_dir: str | Path) -> tuple[list[Record], list[JudgeVerdict]]:
    base = Path(results_dir)
    records = read_jsonl(base / "raw" / "records.jsonl")
    verdicts = load_verdicts(base / "raw" / "verdicts.jsonl")
    return records, verdicts


def save_tables(
    records: Sequence[Record],
    verdicts: Sequence[JudgeVerdict],
    labels: Mapping[str, str],
    out_dir: str | Path,
    *,
    reference: str,
) -> dict[str, pd.DataFrame]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    dims = dimension_frame(records, labels)
    axes = axis_frame(verdicts, records, labels)
    tables = {
        "dimensions": dims,
        "axes": axes,
        "language_delta": language_delta(axes),
        "lexicon": lexicon_frame(records, labels),
        "distance": constitution_distance(dims, reference).to_frame("distance"),
        "reliability": reliability(records),
        "coverage": coverage_table(records, labels),
        "item_scores": raw_item_scores(records, labels),
    }
    shared, contested = shared_and_contested(tables["item_scores"])
    tables["shared"] = shared
    tables["contested"] = contested
    for name, table in tables.items():
        table.to_csv(out / f"{name}.csv", encoding="utf-8")
    if not axes.empty:
        axes.groupby(["model", "question_id"], observed=True)[list(AXES)].mean().to_csv(
            out / "axes_by_question.csv", encoding="utf-8"
        )
    return tables
