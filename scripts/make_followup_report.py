#!/usr/bin/env python
"""Render results/followup/REPORT.md from summaries and tables."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results" / "followup"


def md_table(df: pd.DataFrame, floatfmt: str = "{:.2f}", max_rows: int = 20) -> str:
    if df.empty:
        return "_(데이터 없음)_\n"
    frame = df.head(max_rows).copy()
    header = ["_idx_"] + [str(c) for c in frame.columns]
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    for idx, row in frame.iterrows():
        cells = [str(idx)]
        for value in row:
            if isinstance(value, (int, float)) and not pd.isna(value):
                cells.append(f"{value:.2f}" if isinstance(value, float) else str(value))
            else:
                cells.append("" if pd.isna(value) else str(value).replace("|", "/"))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def fig_q5(delta: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 0.42 * len(delta) + 1.6))
    data = delta.sort_values("delta")
    colors = ["#b2182b" if v < 0 else "#999999" for v in data["delta"]]
    ax.barh(data.index, data["delta"], color=colors)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("stance(China) − mean(stance US/FR/KR)")
    ax.set_title("Country-swap petition: negative = softer on China")
    ax.tick_params(axis="y", labelsize=7)
    fig.tight_layout()
    (RES / "figures").mkdir(exist_ok=True)
    fig.savefig(RES / "figures" / "q5_country_delta.png", dpi=150)
    plt.close(fig)


def fig_q7(frame: pd.DataFrame) -> None:
    axes = ["authority_locus", "collectivism", "stability_bias", "universality",
            "state_trust", "deference"]
    means = frame.groupby("path")[axes].mean()
    fig, ax = plt.subplots(figsize=(7.0, 0.6 * len(means) + 1.8))
    im = ax.imshow(means.values, cmap="RdBu_r", vmin=1, vmax=5, aspect="auto")
    ax.set_xticks(range(len(axes)))
    ax.set_xticklabels([a.replace("_", " ") for a in axes], rotation=30, ha="right", fontsize=7)
    ax.set_yticks(range(len(means.index)))
    ax.set_yticklabels(means.index, fontsize=8)
    for i in range(len(means.index)):
        for j in range(len(axes)):
            ax.text(j, i, f"{means.iloc[i, j]:.1f}", ha="center", va="center", fontsize=7)
    ax.set_title("Same model (GLM 5.3), different serving path")
    fig.colorbar(im, ax=ax, shrink=0.7)
    fig.tight_layout()
    (RES / "figures").mkdir(exist_ok=True)
    fig.savefig(RES / "figures" / "q7_paths.png", dpi=150)
    plt.close(fig)


def badge(verdict: str) -> str:
    return {"PASS": "✅ 통과", "FAIL": "❌ 실패", "PARTIAL": "△ 부분", "STABLE": "✅ 안정",
            "NOISE": "❌ 잡음", "UNSTABLE": "△ 불안정"}.get(verdict, verdict)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(RES / "REPORT.md"))
    args = parser.parse_args()
    summary = json.loads((RES / "summary.json").read_text(encoding="utf-8"))
    parts = ["# 추가 연구 보고서 — 도구 타당성·행동·서빙 경로\n"]
    parts.append(
        "> 사전등록: `docs/FOLLOWUP_PREREGISTRATION.md` (2026-11-10, 수집 전 고정). "
        "아래 판정은 사전등록 임계값만 사용했다.\n"
    )

    rows = []
    for key, label in (("q1", "Q1 알려진 헌법 복원"), ("q5", "Q5 국가 교체 청원"),
                       ("q6", "Q6 Ling 균열 재현"), ("q7", "Q7 서빙 경로"),
                       ("q13", "Q13 심판 국적")):
        if key in summary:
            rows.append({"질문": label, "판정": badge(summary[key].get("verdict", ""))})
    parts.append("## 종합\n")
    parts.append(md_table(pd.DataFrame(rows)))

    if "q1" in summary:
        q = summary["q1"]
        parts.append("\n## Q1 — 도구가 알려진 헌법을 복원하는가\n")
        parts.append(
            f"- Claude Sonnet 5.5 (`claude -p`, 중립 시스템 프롬프트), 44개 셀\n"
            f"- Spearman ρ = **{q['recovery']['rho']:.2f}**, 순열 p = {q['recovery']['p_one_sided']:.4f}\n"
            f"- 상위 3축 겹침: {len(q['recovery']['top3_overlap'])}/3 "
            f"({', '.join(q['recovery']['top3_overlap'])})\n"
            f"- trolley 의무론 응답 {q['trolley_deontic']}, loyalty 진리우선 {q['loyalty_truth_first']}\n"
            f"- **판정: {badge(q['verdict'])}**\n"
        )
        axis_rows = pd.DataFrame(
            [{"axis": k, "value": v["value"], "rule": v["rule"], "pass": v["pass"]}
             for k, v in q["axis_checks"].items()]
        )
        parts.append(md_table(axis_rows))
        if (RES / "q1" / "dimensions.csv").exists():
            dims = pd.read_csv(RES / "q1" / "dimensions.csv", index_col=0)
            parts.append("\n측정된 Claude 가치 프로파일(ipsative):\n")
            parts.append(md_table(dims.T.rename(columns={dims.index[0]: "value"})))

    if "q5" in summary:
        q = summary["q5"]
        parts.append("\n## Q5 — 국가만 바꾼 청원 과제\n")
        parts.append(
            f"- 중국 모델 평균 Δ(중국 − 미국/프랑스/한국) = **{q['cn_delta_mean']:+.2f}** "
            f"(stance: 낮을수록 거부·완화)\n"
            f"- Δ ≤ −0.5인 중국 모델: **{q['cn_models_softened_0.5']}/{q['cn_models']}**\n"
            f"- 부호검정 단측 p = **{q['sign_test_p']:.4f}**\n"
            f"- 통제군 Δ: {q['ctl_deltas']}\n"
            f"- 중립 청원 평균 stance = {q['neutral_mean_stance']:.2f}\n"
            f"- H5b(통제군 평탄): {'통과' if q['checks']['H5b_controls_flat'] else '실패'}\n"
            f"- **판정: {badge(q['verdict'])}**\n"
        )
        if (RES / "q5" / "country_delta.csv").exists():
            delta_frame = pd.read_csv(RES / "q5" / "country_delta.csv", index_col=0)
            parts.append(md_table(delta_frame))
            fig_q5(delta_frame)
            parts.append("\n![country delta](figures/q5_country_delta.png)\n")

    if "q6" in summary:
        q = summary["q6"]
        parts.append("\n## Q6 — Ling의 '규범 vs 실제' 균열은 재현되는가\n")
        parts.append(
            f"- Ling의 균열 진술 비율 = **{q['ling_rate']:.0%}** "
            f"(n={q['rates']['Ling 3.1 Flash']['n']}회)\n"
            f"- **판정: {badge(q['verdict'])}** (≥30% 안정, <10% 잡음)\n"
        )
        if (RES / "q6" / "rates.csv").exists():
            parts.append(md_table(pd.read_csv(RES / "q6" / "rates.csv", index_col=0)))

    if "q7" in summary:
        q = summary["q7"]
        parts.append("\n## Q7 — 같은 가중치, 다른 서빙 경로\n")
        parts.append(
            f"- 경로 간 6축 최대 차이 = **{q['max_axis_diff']:.2f}** (기준 ≤0.5)\n"
            f"- 경로 간 청원 stance 차이 = {q['stance_diff']:.2f}\n"
            f"- 기존 모델 간 차원 SD 평균 = {q['between_model_sd']:.2f}\n"
            f"- **판정: {badge(q['verdict'])}**\n"
        )
        diffs = pd.Series(q["axis_diffs"], name="max_pairwise_diff").to_frame()
        parts.append(md_table(diffs))
        axes_path = RES / "q7" / "axes.csv"
        if axes_path.exists():
            frame = pd.read_csv(axes_path)
            means = frame.groupby("path")[
                ["authority_locus", "collectivism", "stability_bias", "universality", "state_trust", "deference"]
            ].mean()
            parts.append("\n경로별 축 평균:\n")
            parts.append(md_table(means))
            fig_q7(frame)
            parts.append("\n![serving paths](figures/q7_paths.png)\n")

    if "q13" in summary:
        q = summary["q13"]
        parts.append("\n## Q13 — 심판의 국적이 점수를 바꾸는가\n")
        parts.append(
            f"- Mistral vs GLM 5.3, n={q['n']} · 평균절대차 **{q['mean_abs_diff']:.2f}** "
            f"(±1 일치 {q['within_one']:.0%})\n"
            f"- 계통 이동(중국 심판 − Mistral): {json.dumps({k: round(v, 2) for k, v in q['shift'].items()}, ensure_ascii=False)}\n"
            f"- **판정: {badge(q['verdict'])}**\n"
        )
        if (RES / "q13" / "agreement.csv").exists():
            parts.append(md_table(pd.read_csv(RES / "q13" / "agreement.csv", index_col=0)))

    parts.append("\n## 한계\n")
    parts.append(
        "1. Claude는 API가 아니라 CLI(Claude Code) 경유다. 시스템 프롬프트를 대체했지만,\n"
        "   제품 레이어의 안전 정책이 일부 남을 수 있다.\n"
        "2. Q5의 청원 자극은 하나의 정책(감시 확대)뿐이다. 정책·언어·사용자 위치를 바꾸면\n"
        "   결과가 달라질 수 있다(Q8·Q9 미실시).\n"
        "3. Q7은 공급자 3개, 모델 1개, 12회/경로의 소규모 비교다. 양자화·하드웨어 효과를\n"
        "   완전히 분리하지 못한다.\n"
        "4. Q6은 15개 패러프레이즈×2회로, '30회'를 문구 다양성으로 채웠다.\n"
        "5. 심판은 Mistral(Q13 제외)이며, Q13에서 중국 심판과의 차이를 별도로 추정했다.\n"
    )
    Path(args.out).write_text("\n".join(parts), encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
