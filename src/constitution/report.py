"""Figure and markdown report generation from analysed tables."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import dendrogram, linkage

from constitution.analyze import judge_agreement, save_tables, theme_table
from constitution.collect import Record
from constitution.judge import JudgeVerdict
from constitution.schema import AXES

AXIS_LABELS = {
    "authority_locus": "Authority locus\n(conscience → state)",
    "collectivism": "Collectivism\n(rights → utility)",
    "stability_bias": "Stability bias\n(justice → order)",
    "universality": "Universality\n(particular → universal)",
    "state_trust": "State trust\n(suspicion → trust)",
    "deference": "Deference\n(voice → reticence)",
}

plt.rcParams.update(
    {
        "figure.dpi": 150,
        "savefig.dpi": 150,
        "font.size": 9,
        "axes.titlesize": 11,
        "axes.labelsize": 9,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)


def _md_table(df: pd.DataFrame, *, floatfmt: str = "{:.2f}", index: bool = True) -> str:
    if df.empty:
        return "_(데이터 없음)_\n"
    frame = df.copy()
    header = (["_idx_"] if index else []) + [str(c) for c in frame.columns]
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    for idx, row in frame.iterrows():
        cells = [str(idx)] if index else []
        for value in row:
            if isinstance(value, (int, np.integer)):
                cells.append(str(int(value)))
            elif isinstance(value, (float, np.floating)):
                cells.append("" if pd.isna(value) else floatfmt.format(value))
            else:
                cells.append(str(value).replace("|", "/").replace("\n", " "))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def _save(fig: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def _fig_value_profiles(dims: pd.DataFrame, path: Path) -> bool:
    if dims.empty:
        return False
    fig, ax = plt.subplots(figsize=(8.2, 0.55 * len(dims) + 2.2))
    data = dims.values.astype(float)
    limit = float(np.nanmax(np.abs(data))) if np.isfinite(data).any() else 1.0
    im = ax.imshow(data, cmap="RdBu_r", vmin=-limit, vmax=limit, aspect="auto")
    ax.set_xticks(range(len(dims.columns)))
    ax.set_xticklabels(
        [c.replace("_", " ") for c in dims.columns], fontsize=7, rotation=35, ha="right"
    )
    ax.set_yticks(range(len(dims.index)))
    ax.set_yticklabels(dims.index, fontsize=8)
    for i in range(len(dims.index)):
        for j in range(len(dims.columns)):
            value = data[i, j]
            if np.isfinite(value):
                ax.text(j, i, f"{value:+.1f}", ha="center", va="center", fontsize=6.5)
    ax.set_title("Ipsative value profiles (within-model centred, 1-5 scale)")
    fig.colorbar(im, ax=ax, shrink=0.7, label="deviation from own mean")
    _save(fig, path)
    return True


def _fig_distance(dims: pd.DataFrame, path: Path, reference: str) -> bool:
    if len(dims.index) < 2:
        return False
    names = list(dims.index)
    matrix = np.zeros((len(names), len(names)))
    values = dims.values.astype(float)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            d = float(np.linalg.norm(values[i] - values[j]))
            matrix[i, j] = matrix[j, i] = d
    condensed = matrix[np.triu_indices(len(names), 1)]
    if not np.any(condensed):
        return False
    fig, ax = plt.subplots(figsize=(8.2, 3.4))
    tree = linkage(condensed, method="average")
    dendrogram(tree, labels=names, ax=ax, leaf_rotation=30, leaf_font_size=8, color_threshold=0)
    ax.set_title(f"Average-linkage clustering of value profiles (reference: {reference})")
    ax.set_ylabel("Euclidean distance (ipsative units)")
    _save(fig, path)
    return True


def _fig_axes(axes: pd.DataFrame, path: Path) -> bool:
    if axes.empty:
        return False
    means = axes.groupby("model", observed=True)[list(AXES)].mean()
    fig, ax = plt.subplots(figsize=(8.4, 0.5 * len(means) + 2.0))
    im = ax.imshow(means.values, cmap="RdBu_r", vmin=1, vmax=5, aspect="auto")
    ax.set_xticks(range(len(AXES)))
    ax.set_xticklabels([AXIS_LABELS[a].replace("\n", " ") for a in AXES], rotation=25, ha="right", fontsize=7)
    ax.set_yticks(range(len(means.index)))
    ax.set_yticklabels(means.index, fontsize=8)
    for i in range(len(means.index)):
        for j in range(len(AXES)):
            ax.text(j, i, f"{means.iloc[i, j]:.1f}", ha="center", va="center", fontsize=7)
    ax.set_title("Judge-coded constitutional axes (1-5)")
    fig.colorbar(im, ax=ax, shrink=0.75)
    _save(fig, path)
    return True


def _fig_language(delta: pd.DataFrame, path: Path) -> bool:
    if delta.empty or not set(AXES).intersection(delta.columns):
        return False
    means = delta[list(AXES)].mean()
    err = delta[list(AXES)].std().fillna(0)
    fig, ax = plt.subplots(figsize=(7.4, 2.9))
    colors = ["#b2182b" if v > 0 else "#2166ac" for v in means]
    ax.bar([AXIS_LABELS[a].split("\n")[0] for a in AXES], means.values, yerr=err.values, color=colors, alpha=0.85)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_ylabel("English − Chinese (axis points)")
    ax.set_title("Language-conditioned shift on bilingual probes (mean ± SD across models)")
    ax.tick_params(axis="x", labelrotation=20)
    _save(fig, path)
    return True


def _fig_lexicon(lexicon: pd.DataFrame, path: Path) -> bool:
    if lexicon.empty:
        return False
    fig, ax = plt.subplots(figsize=(6.6, 0.5 * len(lexicon) + 2.0))
    im = ax.imshow(lexicon.values.astype(float), cmap="YlOrBr", aspect="auto")
    ax.set_xticks(range(len(lexicon.columns)))
    ax.set_xticklabels(lexicon.columns, rotation=25, ha="right", fontsize=8)
    ax.set_yticks(range(len(lexicon.index)))
    ax.set_yticklabels(lexicon.index, fontsize=8)
    for i in range(len(lexicon.index)):
        for j in range(len(lexicon.columns)):
            ax.text(j, i, f"{lexicon.iloc[i, j]:.1f}", ha="center", va="center", fontsize=7)
    ax.set_title("Value-lexicon density (term hits per 1,000 characters)")
    fig.colorbar(im, ax=ax, shrink=0.75)
    _save(fig, path)
    return True


def _findings(
    dims: pd.DataFrame,
    axes: pd.DataFrame,
    delta: pd.DataFrame,
    distance: pd.Series,
    shared: pd.DataFrame,
    reference: str,
    roles: Mapping[str, str],
) -> list[str]:
    findings: list[str] = []
    if not dims.empty:
        means = dims.mean().sort_values(ascending=False)
        top = means.index[0]
        findings.append(
            f"표본 전체에서 가장 강하게 상승한 가치 축은 **{top}** (평균 편차 {means.iloc[0]:+.2f})이며, "
            f"가장 억제된 축은 **{means.index[-1]}** ({means.iloc[-1]:+.2f})이다."
        )
        if roles:
            targets = [m for m in dims.index if roles.get(m) == "target"]
            controls = [m for m in dims.index if roles.get(m) == "control"]
            if targets and controls:
                gap = (dims.loc[targets].mean() - dims.loc[controls].mean()).sort_values()
                findings.append(
                    f"중국 모델군과 통제군의 최대 격차는 **{gap.index[-1]}** "
                    f"({gap.iloc[-1]:+.2f})이며, 역방향 최대 격차는 **{gap.index[0]}** ({gap.iloc[0]:+.2f})이다."
                )
    if not axes.empty:
        means = axes[list(AXES)].mean().sort_values(ascending=False)
        findings.append(
            f"헌법 축 평균이 가장 높은 항목은 **{means.index[0]}** ({means.iloc[0]:.2f}/5), "
            f"가장 낮은 항목은 **{means.index[-1]}** ({means.iloc[-1]:.2f}/5)이다."
        )
    if not delta.empty:
        shift = delta[list(AXES)].mean().abs().sort_values(ascending=False)
        findings.append(
            f"언어를 중국어에서 영어로 바꿀 때 가장 크게 이동하는 축은 **{shift.index[0]}** "
            f"(평균 {delta[shift.index[0]].mean():+.2f}점)이다."
        )
    if not distance.empty and distance.notna().any():
        ranked = distance.drop(labels=[reference], errors="ignore").sort_values()
        if not ranked.empty:
            findings.append(
                f"통제 기준 **{reference}**와 가치 구조가 가장 가까운 모델은 **{ranked.index[0]}** "
                f"(거리 {ranked.iloc[0]:.2f}), 가장 먼 모델은 **{ranked.index[-1]}** (거리 {ranked.iloc[-1]:.2f})이다."
            )
    if not shared.empty:
        row = shared.iloc[0]
        findings.append(
            f"9개 문항 중 모델 간 합의가 가장 높은 항목은 `{shared.index[0]}` "
            f"(SD {row['sd']:.2f}, 평균 {row['mean']:.2f})이다."
        )
    return findings


def build_report(
    records: Sequence[Record],
    verdicts: Sequence[JudgeVerdict],
    labels: Mapping[str, str],
    out_dir: str | Path,
    *,
    reference: str,
    roles: Mapping[str, str] | None = None,
    secondary_verdicts: Sequence[JudgeVerdict] | None = None,
) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    figures = out / "figures"
    tables_dir = out / "tables"
    roles = roles or {}

    tables = save_tables(records, verdicts, labels, tables_dir, reference=reference)
    dims = tables["dimensions"]
    axes = tables["axes"]
    delta = tables["language_delta"]
    lexicon = tables["lexicon"]
    distance = tables["distance"]["distance"]
    shared = tables["shared"]
    contested = tables["contested"]
    coverage = tables["coverage"]
    reliability_table = tables["reliability"]

    figures.mkdir(parents=True, exist_ok=True)
    has_profile = _fig_value_profiles(dims, figures / "value_profiles.png")
    has_tree = _fig_distance(dims, figures / "value_clusters.png", reference)
    has_axes = _fig_axes(axes, figures / "constitution_axes.png")
    has_lang = _fig_language(delta, figures / "language_shift.png")
    has_lex = _fig_lexicon(lexicon, figures / "value_lexicon.png")

    n_requests = len(records)
    n_errors = sum(1 for r in records if r.error)
    total_cost = sum(r.cost_usd for r in records)
    n_models = len({r.model for r in records})
    findings = _findings(dims, axes, delta, distance, shared, reference, roles)

    parts: list[str] = []
    parts.append("# 중국 프론티어 LLM의 헌법 지형\n")
    parts.append(
        "> **자동 생성 보고서.** 원자료·코드·프롬프트가 모두 `results/`와 `src/`에 보존되어 있다. "
        "수치의 해석은 §10의 한계를 전제로 읽어야 한다.\n"
    )
    parts.append(
        f"- 표본: **{n_models}개 모델**, **{n_requests:,}건**의 단일턴 요청 "
        f"(오류 {n_errors}건, 비용 ${total_cost:.2f})\n"
        f"- 기준 모델(reference): **{reference}**\n"
        f"- 문항: 리커트 26개(4블록×2회) + 개방형 9개(3개는 중국어/영어 이중 언어)\n"
    )

    parts.append("\n## 1. 핵심 발견\n")
    if findings:
        for index, finding in enumerate(findings, start=1):
            parts.append(f"{index}. {finding}\n")
    else:
        parts.append("_데이터가 부족해 자동 발견을 생성하지 못했다._\n")

    parts.append("\n## 2. 표본과 커버리지\n")
    parts.append(_md_table(coverage.round(4)))

    parts.append("\n## 3. 가치 프로파일\n")
    parts.append(
        "Schwartz의 10개 기본 가치에 관계 조화(harmony)·발전주의(developmentalism)를 더한 12축을 "
        "**응답자 내 평균중심화(ipsative)** 하여 측정했다. 절대 수준이 아니라 *상대적 우선순위*를 읽는다.\n"
    )
    if has_profile:
        parts.append("![value profiles](figures/value_profiles.png)\n")
    if not dims.empty:
        top = dims.apply(lambda row: ", ".join(row.sort_values(ascending=False).head(3).index), axis=1)
        summary = pd.DataFrame({"상위 3개 가치": top})
        parts.append(_md_table(summary))

    parts.append("\n## 4. 헌법 축 (LLM-as-judge)\n")
    parts.append(
        "개방형 응답을 6개 축(권위 소재, 집단주의, 안정 편향, 보편성, 국가 신뢰, 순응)으로 코딩했다. "
        "1과 5의 의미는 그림 축 라벨에 표기했다.\n"
    )
    if has_axes:
        parts.append("![constitution axes](figures/constitution_axes.png)\n")
    if not axes.empty:
        by_model = axes.groupby("model", observed=True)[list(AXES)].mean().round(2)
        themes = theme_table(verdicts, records, labels)
        if not themes.empty:
            by_model = by_model.join(themes)
        parts.append(_md_table(by_model))

    parts.append("\n## 5. 합의와 쟁점\n")
    parts.append("### 5.1 모델 간 합의가 높은 문항 (헌법의 공통 바닥)\n")
    parts.append(_md_table(shared))
    parts.append("\n### 5.2 모델 간 분산이 큰 문항 (헌법의 쟁점)\n")
    parts.append(_md_table(contested))

    parts.append("\n## 6. 언어 조건화 효과\n")
    parts.append(
        "동일한 문항을 중국어/영어로 각각 제시한 3문항(정부 비판, 트롤리, 문명 귀속)에서 "
        "**영어 − 중국어** 차이를 계산했다. 양(+)은 영어에서 더 강해진 축이다.\n"
    )
    if has_lang:
        parts.append("![language shift](figures/language_shift.png)\n")
    if not delta.empty:
        parts.append(_md_table(delta[list(AXES)].mean().to_frame("mean_shift").round(3)))

    parts.append("\n## 7. 어휘 지형\n")
    parts.append("개방형 응답에서 가치 어휘의 밀도(1,000자당 출현)를 측정했다. 해석은 §10을 참조.\n")
    if has_lex:
        parts.append("![value lexicon](figures/value_lexicon.png)\n")
    if not lexicon.empty:
        parts.append(_md_table(lexicon.round(2)))

    parts.append("\n## 8. 기준 모델로부터의 거리\n")
    if has_tree:
        parts.append("![value clusters](figures/value_clusters.png)\n")
    if not distance.empty:
        parts.append(_md_table(distance.sort_values().to_frame("distance").round(3)))

    parts.append("\n## 9. 측정 신뢰도\n")
    if not reliability_table.empty:
        parts.append(
            f"리커트 반복 측정의 문항별 평균 절대차는 **{reliability_table['mean_abs_diff'].mean():.2f}점** "
            f"(1-5 척도)이었다. 0.5 미만이면 안정적, 1.0 초과면 해당 문항은 잡음으로 간주한다.\n"
        )
        parts.append(_md_table(reliability_table.head(8)))
    if secondary_verdicts:
        agreement = judge_agreement(verdicts, secondary_verdicts)
        if not agreement.empty:
            parts.append(
                f"\n2차 심판과의 일치도(±1 허용): **{agreement['within_one'].mean():.0%}**, "
                f"완전 일치 **{agreement['exact'].mean():.0%}** "
                f"(n={int(agreement['n'].iloc[0])} 응답).\n"
            )
            parts.append(_md_table(agreement))

    parts.append("\n## 10. 한계\n")
    parts.append(
        "1. **단일턴·단일 시스템 프롬프트**다. 실제 배포 제품의 시스템 프롬프트·안전 필터와 다르다.\n"
        "2. **라우팅 이질성**: OpenRouter 경유로 공급자·양자화·버전이 완전히 통제되지 않는다.\n"
        "3. **자가보고의 타당성**: 모델은 자신의 훈련을 관찰할 수 없고, 훈련된 자기서사를 재생한다. "
        "이 조사는 '행동'이 아니라 '헌법적 자기서사'를 측정한다.\n"
        "4. **심판 편향**: 1차 심판은 Mistral Large 4.0(통제군 표본에 포함)이며, 15% 표본에 대해서만\n"
        "   비표본 2차 심판(Aion 3.5) 신뢰도를 산출했다. Anthropic/OpenAI는 403, xAI/Pareto는 429로\n"
        "   사용할 수 없어 불가피한 선택이었다.\n"
        "5. **문화 비교의 함정**: '중국 모델'을 국가 단위로 묶는 것은 연구소·데이터·배포 경로의 이질성을 지운다. "
        "결과는 집단 평균이지 개별 모델의 본질이 아니다.\n"
        "6. **시점 의존성**: 스냅샷은 수시로 교체된다. `config/models.yaml`의 slug와 수집일을 함께 읽어야 한다.\n"
    )

    parts.append("\n## 11. 재현\n")
    parts.append(
        "```bash\nmake test          # 90% 커버리지 게이트 포함\n"
        "make survey        # results/raw/records.jsonl 생성 (재개 가능)\n"
        "make report        # 심판 + 분석 + 본 문서 재생성\n```\n"
        "방법론 전문은 `docs/METHODOLOGY.md`, 질문지 원문은 `docs/QUESTIONNAIRE.md`.\n"
    )

    path = out / "REPORT.md"
    path.write_text("\n".join(parts), encoding="utf-8")
    return path
