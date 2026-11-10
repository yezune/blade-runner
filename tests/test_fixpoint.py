"""Tests for the FIXPOINT-1 value-attractor instrument."""

from __future__ import annotations

import re

import pytest

from constitution.fixpoint import (
    INITIAL_STATES,
    VALUES,
    basin_jumps,
    build_endorsement_messages,
    build_step_messages,
    cluster_attractors,
    detect_cycle,
    distance,
    parse_allocation,
    parse_endorsement,
    perturb,
)
from constitution.parse import ParseError

CJK = re.compile(r"[\u4e00-\u9fff]")


def test_initial_states_are_valid_distributions() -> None:
    assert set(INITIAL_STATES) == {"liberty", "security", "growth", "equality"}
    for state in INITIAL_STATES.values():
        assert set(state) == set(VALUES)
        assert sum(state.values()) == 60
        assert min(state.values()) >= 0


def test_step_prompt_contains_state_and_contract() -> None:
    _system, user = build_step_messages(INITIAL_STATES["liberty"], language="zh")
    from constitution.fixpoint import LABELS_ZH

    for label in LABELS_ZH.values():
        assert label in user["content"]
    assert "60" in user["content"]
    assert "JSON" in user["content"]
    assert "自主" in user["content"]


def test_english_prompt_has_no_cjk() -> None:
    system, user = build_step_messages(INITIAL_STATES["security"], language="en")
    assert not CJK.search(system["content"])
    assert not CJK.search(user["content"])


def test_framing_changes_only_the_intro() -> None:
    _, self_msg = build_step_messages(INITIAL_STATES["growth"], language="zh", framing="self")
    _, society = build_step_messages(INITIAL_STATES["growth"], language="zh", framing="society")
    assert self_msg["content"] != society["content"]
    assert "社会" in society["content"]


def test_parse_allocation_valid() -> None:
    text = '{"allocation": {' + ", ".join(f'"{v}": 5' for v in VALUES) + "}}"
    parsed = parse_allocation(text)
    assert parsed == {v: 5 for v in VALUES}


def test_parse_allocation_normalises_to_sixty() -> None:
    raw = {v: 0 for v in VALUES}
    raw["self_direction"] = 30
    raw["universalism"] = 30
    text = '{"allocation": {' + ", ".join(f'"{k}": {v}' for k, v in raw.items()) + "}}"
    parsed = parse_allocation(text)
    assert sum(parsed.values()) == 60
    assert parsed["self_direction"] == 30


def test_parse_treats_missing_values_as_zero() -> None:
    parsed = parse_allocation('{"allocation": {"self_direction": 30, "universalism": 30}}')
    assert parsed["self_direction"] == 30
    assert parsed["power"] == 0
    assert sum(parsed.values()) == 60


def test_parse_rejects_empty_allocation() -> None:
    with pytest.raises(ParseError, match="zero"):
        parse_allocation('{"allocation": {}}')


def test_parse_rejects_unknown_values() -> None:
    with pytest.raises(ParseError, match="unknown"):
        parse_allocation('{"allocation": {"self_direction": 30, "glory": 30}}')


def test_distance_is_total_variation() -> None:
    a = {v: 0 for v in VALUES}
    a["power"] = 60
    b = {v: 0 for v in VALUES}
    b["power"] = 30
    b["universalism"] = 30
    assert distance(a, b) == pytest.approx(30.0)


def test_detect_cycle_fixed_point() -> None:
    s = INITIAL_STATES["liberty"]
    cycle = detect_cycle([s, s.copy(), s.copy()])
    assert cycle == (0, 1)


def test_detect_cycle_two_cycle() -> None:
    a = INITIAL_STATES["liberty"]
    b = INITIAL_STATES["security"]
    cycle = detect_cycle([a, b, a, b])
    assert cycle == (0, 2)


def test_detect_cycle_none() -> None:
    a = INITIAL_STATES["liberty"]
    b = INITIAL_STATES["security"]
    c = INITIAL_STATES["growth"]
    assert detect_cycle([a, b, c]) is None


def test_cluster_attractors() -> None:
    a = {v: 0 for v in VALUES}
    a["power"] = 60
    b = dict(a)
    c = {v: 0 for v in VALUES}
    c["universalism"] = 60
    assert cluster_attractors([a, b, c], eps=6) == [0, 0, 1]


def test_perturb_preserves_budget() -> None:
    state = INITIAL_STATES["liberty"]
    moved = perturb(state, amount=10)
    assert sum(moved.values()) == 60
    assert moved["power"] == 10
    assert moved["universalism"] == state["universalism"] - 10
    assert min(moved.values()) >= 0


def test_basin_jumps_counts_large_moves() -> None:
    a = INITIAL_STATES["liberty"]
    b = INITIAL_STATES["security"]
    assert basin_jumps([a, a, b], threshold=15) == 1


def test_endorsement_parse() -> None:
    _system, user = build_endorsement_messages(INITIAL_STATES["liberty"])
    assert "1" in user["content"] and "5" in user["content"]
    assert parse_endorsement('{"endorse": 5, "reason": "ok"}') == 5
    with pytest.raises(ParseError):
        parse_endorsement("no json")
