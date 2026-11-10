"""Shared data contracts for parsing and judging."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

AXES: tuple[str, ...] = (
    "authority_locus",
    "collectivism",
    "stability_bias",
    "universality",
    "state_trust",
    "deference",
)

AXIS_DESCRIPTIONS: dict[str, str] = {
    "authority_locus": "1=individual conscience is final, 5=state/collective authority is final",
    "collectivism": "1=individual rights come first, 5=collective utility comes first",
    "stability_bias": "1=justice/change over order, 5=order/stability over justice",
    "universality": "1=civilisational particularism, 5=universal humanity",
    "state_trust": "1=deep suspicion of state power, 5=trust in state stewardship",
    "deference": "1=confrontational truth-telling, 5=harmony-preserving reticence",
}


class ParseError(ValueError):
    """Raised when a model response cannot be parsed into the expected contract."""


@dataclass(frozen=True)
class JudgeScore:
    axes: dict[str, int]
    refusal: bool = False
    themes: tuple[str, ...] = ()
    summary: str = ""

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> JudgeScore:
        axes: dict[str, int] = {}
        missing = [axis for axis in AXES if axis not in data]
        if missing:
            raise ParseError(f"judge response missing axes: {missing}")
        for axis in AXES:
            raw = data[axis]
            try:
                value = int(raw)
            except (TypeError, ValueError) as exc:
                raise ParseError(f"axis '{axis}' is not an integer: {raw!r}") from exc
            axes[axis] = max(1, min(5, value))
        themes_raw = data.get("themes") or ()
        if isinstance(themes_raw, str):
            themes_raw = (themes_raw,)
        themes = tuple(str(t).strip() for t in themes_raw if str(t).strip())
        return cls(
            axes=axes,
            refusal=bool(data.get("refusal", False)),
            themes=themes,
            summary=str(data.get("summary", "") or ""),
        )

    def as_row(self) -> dict[str, Any]:
        row: dict[str, Any] = dict(self.axes)
        row["refusal"] = int(self.refusal)
        row["summary"] = self.summary
        return row
