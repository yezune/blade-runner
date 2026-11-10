"""Tests for configuration loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from constitution.config import (
    ConfigError,
    load_model_registry,
    load_run_config,
)

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "config" / "models.yaml"
RUN = ROOT / "config" / "run.yaml"


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "cfg.yaml"
    p.write_text(body, encoding="utf-8")
    return p


def test_registry_loads_shipped_config() -> None:
    specs = load_model_registry(MODELS)
    assert len(specs) == 11
    assert sum(s.role == "target" for s in specs) == 9
    assert sum(s.role == "control" for s in specs) == 2
    assert {s.country for s in specs} == {"CN", "US", "EU"}


def test_registry_slugs_are_unique_and_fully_qualified() -> None:
    specs = load_model_registry(MODELS)
    slugs = [s.slug for s in specs]
    assert len(set(slugs)) == len(slugs)
    assert all("/" in s for s in slugs)


def test_registry_targets_are_nine_distinct_labs() -> None:
    targets = [s for s in load_model_registry(MODELS) if s.role == "target"]
    assert len({t.lab for t in targets}) == 9


def test_registry_rejects_duplicate_slug(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        """
version: 1
targets:
  - {slug: a/b, label: A, lab: A, country: CN, family: a, notes: x}
  - {slug: a/b, label: B, lab: B, country: CN, family: b, notes: y}
controls: []
""",
    )
    with pytest.raises(ConfigError, match="duplicate"):
        load_model_registry(path)


def test_registry_rejects_missing_field(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        """
version: 1
targets:
  - {slug: a/b, label: A, country: CN, family: a, notes: x}
controls: []
""",
    )
    with pytest.raises(ConfigError, match="lab"):
        load_model_registry(path)


def test_registry_rejects_unknown_country(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        """
version: 1
targets:
  - {slug: a/b, label: A, lab: A, country: KR, family: a, notes: x}
controls: []
""",
    )
    with pytest.raises(ConfigError, match="country"):
        load_model_registry(path)


def test_run_config_loads_shipped_values() -> None:
    cfg = load_run_config(RUN)
    assert cfg.sampling.samples_open == 3
    assert cfg.sampling.samples_scale == 2
    assert cfg.runtime.budget_usd > 0
    assert cfg.judging.model == "mistralai/mistral-large-4-0"
    assert 0 < cfg.judging.reliability_sample_rate <= 1


@pytest.mark.parametrize(
    "snippet, match",
    [
        ("samples_open: 0", "samples_open"),
        ("concurrency: 0", "concurrency"),
        ("budget_usd: -1", "budget_usd"),
        ("temperature_open: 3.0", "temperature_open"),
    ],
)
def test_run_config_validation(tmp_path: Path, snippet: str, match: str) -> None:
    values = {
        "temperature_open": "0.8",
        "temperature_scale": "0.2",
        "samples_open": "3",
        "samples_scale": "2",
        "concurrency": "6",
        "budget_usd": "8.0",
    }
    key, value = (part.strip() for part in snippet.split(":", 1))
    values[key] = value
    body = (
        "version: 1\n"
        "sampling:\n"
        f"  temperature_open: {values['temperature_open']}\n"
        f"  temperature_scale: {values['temperature_scale']}\n"
        f"  samples_open: {values['samples_open']}\n"
        f"  samples_scale: {values['samples_scale']}\n"
        "runtime:\n"
        f"  concurrency: {values['concurrency']}\n"
        f"  budget_usd: {values['budget_usd']}\n"
        "judging:\n"
        "  model: judge/model\n"
    )
    with pytest.raises(ConfigError, match=match):
        load_run_config(_write(tmp_path, body))
