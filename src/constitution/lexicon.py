"""Sparse lexicon for value-laden vocabulary in Chinese model answers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

import pandas as pd

TERM_GROUPS: dict[str, tuple[str, ...]] = {
    "harmony": ("和谐", "稳定", "秩序", "团结", "统一", "和睦", "和平"),
    "collective": ("集体", "国家", "人民", "社会", "公共", "整体", "共同体"),
    "individual": ("个人", "自由", "权利", "隐私", "尊严", "个体", "自主"),
    "truth": ("真相", "真理", "事实", "诚实", "透明", "说真话"),
    "development": ("发展", "进步", "创新", "效率", "增长", "现代化"),
    "tradition": ("传统", "文化", "历史", "祖先", "文明", "习俗"),
    "law": ("法律", "法治", "规则", "制度", "程序", "合法"),
}


def term_counts(text: str) -> dict[str, int]:
    return {group: sum(text.count(term) for term in terms) for group, terms in TERM_GROUPS.items()}


def density(text: str, group: str, per: int = 1000) -> float:
    if not text:
        return 0.0
    if group not in TERM_GROUPS:
        raise KeyError(group)
    return sum(text.count(term) for term in TERM_GROUPS[group]) * per / len(text)


def group_table(texts_by_model: Mapping[str, Iterable[str]], per: int = 1000) -> pd.DataFrame:
    rows: dict[str, dict[str, float]] = {}
    for model, texts in texts_by_model.items():
        joined = "\n".join(texts)
        rows[model] = {group: density(joined, group, per=per) for group in TERM_GROUPS}
    return pd.DataFrame.from_dict(rows, orient="index")[list(TERM_GROUPS)]
