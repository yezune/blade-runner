"""Tests for the instrument: Likert inventory + open constitutional probes."""

from __future__ import annotations

import re

from constitution.questions import (
    DIMENSIONS,
    EN_PROBE_IDS,
    PROBES,
    SCALE_ITEMS,
    build_probe_messages,
    build_scale_messages,
    likert_blocks,
)

CJK = re.compile(r"[\u4e00-\u9fff]")


def test_inventory_is_well_formed() -> None:
    assert len(SCALE_ITEMS) == 26
    ids = [i.id for i in SCALE_ITEMS]
    assert len(set(ids)) == len(ids)
    assert len(DIMENSIONS) == 12


def test_every_dimension_has_at_least_two_items() -> None:
    counts: dict[str, int] = {}
    for item in SCALE_ITEMS:
        counts[item.dimension] = counts.get(item.dimension, 0) + 1
    assert set(counts) == set(DIMENSIONS)
    assert min(counts.values()) >= 2


def test_blocks_partition_the_inventory() -> None:
    blocks = likert_blocks()
    assert len(blocks) == 4
    flat = [item.id for block in blocks for item in block]
    assert sorted(flat) == sorted(i.id for i in SCALE_ITEMS)
    sizes = [len(b) for b in blocks]
    assert max(sizes) - min(sizes) <= 1


def test_scale_prompt_contains_items_and_response_contract() -> None:
    block = likert_blocks()[0]
    system, user = build_scale_messages(block, language="zh")
    assert system["role"] == "system" and user["role"] == "user"
    for item in block:
        assert item.id in user["content"]
        assert item.text_zh in user["content"]
    assert "1" in user["content"] and "5" in user["content"]
    assert "JSON" in user["content"]
    assert "responses" in user["content"]


def test_english_scale_prompt_has_no_chinese_characters() -> None:
    block = likert_blocks()[1]
    system, user = build_scale_messages(block, language="en")
    assert not CJK.search(system["content"])
    assert not CJK.search(user["content"])


def test_probes_are_unique_and_bilingual_where_required() -> None:
    assert len(PROBES) == 9
    ids = [p.id for p in PROBES]
    assert len(set(ids)) == len(ids)
    assert set(EN_PROBE_IDS) <= set(ids)
    by_id = {p.id: p for p in PROBES}
    for pid in EN_PROBE_IDS:
        assert by_id[pid].text_en
        assert by_id[pid].text_en is not None
        assert not CJK.search(by_id[pid].text_en or "")
    for probe in PROBES:
        assert probe.text_zh
        assert CJK.search(probe.text_zh)


def test_probe_prompt_switches_language_cleanly() -> None:
    probe = {p.id: p for p in PROBES}["dissent"]
    zh_sys, zh_user = build_probe_messages(probe, language="zh")
    en_sys, en_user = build_probe_messages(probe, language="en")
    assert probe.text_zh in zh_user["content"]
    assert probe.text_en in en_user["content"]
    assert not CJK.search(en_user["content"])
    assert zh_sys["content"] != en_sys["content"]


def test_probe_prompt_does_not_ask_for_json() -> None:
    system, user = build_probe_messages(PROBES[0], language="zh")
    assert "JSON" not in user["content"]
    assert "400字" in system["content"]
