"""Configuration loading with explicit validation (fail fast, no magic defaults)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

VALID_ROLES = ("target", "control")
VALID_COUNTRIES = ("CN", "US", "EU")


class ConfigError(ValueError):
    """Raised when a config file is structurally invalid."""


@dataclass(frozen=True)
class ModelSpec:
    slug: str
    label: str
    lab: str
    country: str
    family: str
    notes: str
    role: str = field(default="target")


@dataclass(frozen=True)
class Sampling:
    temperature_open: float = 0.8
    temperature_scale: float = 0.2
    top_p: float = 0.95
    samples_open: int = 3
    samples_scale: int = 2
    max_tokens_open: int = 3000
    max_tokens_scale: int = 1200
    seed: int = 0


@dataclass(frozen=True)
class Runtime:
    concurrency: int = 6
    request_timeout_s: float = 180.0
    max_retries: int = 3
    backoff_base_s: float = 2.0
    budget_usd: float = 8.0


@dataclass(frozen=True)
class Judging:
    model: str = "mistralai/mistral-large-4-0"
    second_model: str = "aion-labs/aion-3.5"
    reliability_sample_rate: float = 0.15
    temperature: float = 0.0
    max_tokens: int = 6000


@dataclass(frozen=True)
class RunConfig:
    sampling: Sampling
    runtime: Runtime
    judging: Judging


def _read_yaml(path: Path) -> dict[str, Any]:
    if not Path(path).exists():
        raise ConfigError(f"config file not found: {path}")
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:  # pragma: no cover - defensive
        raise ConfigError(f"invalid yaml in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"config root must be a mapping: {path}")
    return data


_REQUIRED_SPEC_FIELDS = ("slug", "label", "lab", "country", "family", "notes")


def _parse_spec(raw: Any, role: str, index: int) -> ModelSpec:
    where = f"{role}[{index}]"
    if not isinstance(raw, dict):
        raise ConfigError(f"{where} must be a mapping")
    for fieldname in _REQUIRED_SPEC_FIELDS:
        if fieldname not in raw or raw[fieldname] in (None, ""):
            raise ConfigError(f"{where} is missing required field '{fieldname}'")
    spec = ModelSpec(
        slug=str(raw["slug"]).strip(),
        label=str(raw["label"]).strip(),
        lab=str(raw["lab"]).strip(),
        country=str(raw["country"]).strip(),
        family=str(raw["family"]).strip(),
        notes=str(raw["notes"]).strip(),
        role=role,
    )
    if spec.country not in VALID_COUNTRIES:
        raise ConfigError(f"{where} has invalid country '{spec.country}'")
    if "/" not in spec.slug:
        raise ConfigError(f"{where} slug must be fully qualified (provider/model)")
    return spec


def load_model_registry(path: str | Path) -> tuple[ModelSpec, ...]:
    data = _read_yaml(Path(path))
    specs: list[ModelSpec] = []
    for role in ("targets", "controls"):
        section = data.get(role) or []
        if not isinstance(section, list):
            raise ConfigError(f"'{role}' must be a list")
        role_name = "target" if role == "targets" else "control"
        specs.extend(_parse_spec(raw, role_name, i) for i, raw in enumerate(section))
    if not specs:
        raise ConfigError("registry contains no models")
    seen: set[str] = set()
    for spec in specs:
        if spec.slug in seen:
            raise ConfigError(f"duplicate slug '{spec.slug}' in registry")
        seen.add(spec.slug)
    return tuple(specs)


def _require(mapping: dict[str, Any], key: str) -> Any:
    if key not in mapping:
        raise ConfigError(f"missing required setting '{key}'")
    return mapping[key]


def _check_range(name: str, value: Any, low: float, high: float, *, integer: bool = False) -> Any:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ConfigError(f"'{name}' must be numeric")
    if integer and not isinstance(value, int):
        raise ConfigError(f"'{name}' must be an integer")
    if not (low <= value <= high):
        raise ConfigError(f"'{name}' out of range [{low}, {high}]: {value}")
    return value


def load_run_config(path: str | Path) -> RunConfig:
    data = _read_yaml(Path(path))

    sampling_raw = data.get("sampling")
    if not isinstance(sampling_raw, dict):
        raise ConfigError("missing 'sampling' section")
    sampling = Sampling(
        temperature_open=_check_range(
            "temperature_open", float(_require(sampling_raw, "temperature_open")), 0.0, 2.0
        ),
        temperature_scale=_check_range(
            "temperature_scale", float(_require(sampling_raw, "temperature_scale")), 0.0, 2.0
        ),
        top_p=_check_range("top_p", float(sampling_raw.get("top_p", 0.95)), 0.0, 1.0),
        samples_open=_check_range(
            "samples_open", _require(sampling_raw, "samples_open"), 1, 50, integer=True
        ),
        samples_scale=_check_range(
            "samples_scale", _require(sampling_raw, "samples_scale"), 1, 50, integer=True
        ),
        max_tokens_open=_check_range(
            "max_tokens_open", sampling_raw.get("max_tokens_open", 3000), 64, 32000, integer=True
        ),
        max_tokens_scale=_check_range(
            "max_tokens_scale", sampling_raw.get("max_tokens_scale", 1200), 64, 32000, integer=True
        ),
        seed=int(sampling_raw.get("seed", 0)),
    )

    runtime_raw = data.get("runtime")
    if not isinstance(runtime_raw, dict):
        raise ConfigError("missing 'runtime' section")
    runtime = Runtime(
        concurrency=_check_range(
            "concurrency", _require(runtime_raw, "concurrency"), 1, 64, integer=True
        ),
        request_timeout_s=float(runtime_raw.get("request_timeout_s", 180)),
        max_retries=_check_range(
            "max_retries", runtime_raw.get("max_retries", 3), 0, 10, integer=True
        ),
        backoff_base_s=float(runtime_raw.get("backoff_base_s", 2.0)),
        budget_usd=_check_range(
            "budget_usd", float(_require(runtime_raw, "budget_usd")), 0.01, 1000.0
        ),
    )

    judging_raw = data.get("judging")
    if not isinstance(judging_raw, dict):
        raise ConfigError("missing 'judging' section")
    judging = Judging(
        model=str(_require(judging_raw, "model")),
        second_model=str(judging_raw.get("second_model", "")),
        reliability_sample_rate=_check_range(
            "reliability_sample_rate",
            float(judging_raw.get("reliability_sample_rate", 0.15)),
            0.0,
            1.0,
        ),
        temperature=float(judging_raw.get("temperature", 0.0)),
        max_tokens=int(judging_raw.get("max_tokens", 1500)),
    )
    return RunConfig(sampling=sampling, runtime=runtime, judging=judging)
