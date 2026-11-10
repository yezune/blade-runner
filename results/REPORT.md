# 중국 프론티어 LLM의 헌법 지형

> **자동 생성 보고서.** 원자료·코드·프롬프트가 모두 `results/`와 `src/`에 보존되어 있다. 수치의 해석은 §10의 한계를 전제로 읽어야 한다.

- 표본: **11개 모델**, **484건**의 단일턴 요청 (오류 0건, 비용 $2.09)
- 기준 모델(reference): **Grok 4.7**
- 문항: 리커트 26개(4블록×2회) + 개방형 9개(3개는 중국어/영어 이중 언어)


## 1. 핵심 발견

1. 표본 전체에서 가장 강하게 상승한 가치 축은 **universalism** (평균 편차 +1.02)이며, 가장 억제된 축은 **developmentalism** (-1.07)이다.

2. 중국 모델군과 통제군의 최대 격차는 **harmony** (+0.71)이며, 역방향 최대 격차는 **stimulation** (-0.34)이다.

3. 헌법 축 평균이 가장 높은 항목은 **universality** (4.74/5), 가장 낮은 항목은 **deference** (1.26/5)이다.

4. 언어를 중국어에서 영어로 바꿀 때 가장 크게 이동하는 축은 **deference** (평균 -0.31점)이다.

5. 통제 기준 **Grok 4.7**와 가치 구조가 가장 가까운 모델은 **Kimi K3.1 Pro** (거리 1.60), 가장 먼 모델은 **Step 5 (preview)** (거리 2.84)이다.

6. 9개 문항 중 모델 간 합의가 가장 높은 항목은 `AC2` (SD 0.00, 평균 4.00)이다.


## 2. 표본과 커버리지

| _idx_ | requests | errors | cost_usd | chars | error_rate |
|---|---|---|---|---|---|
| MiniMax M3.1 Flash | 44.00 | 0.00 | 0.03 | 29196.00 | 0.00 |
| DeepSeek V4 Pro | 44.00 | 0.00 | 0.09 | 24097.00 | 0.00 |
| Qwen 3.8 Max Prime | 44.00 | 0.00 | 0.33 | 23219.00 | 0.00 |
| GLM 5.3 Prime | 44.00 | 0.00 | 0.52 | 29393.00 | 0.00 |
| Hunyuan 4 | 44.00 | 0.00 | 0.10 | 27075.00 | 0.00 |
| Kimi K3.1 Pro | 44.00 | 0.00 | 0.41 | 26152.00 | 0.00 |
| MiMo v2.6 Pro | 44.00 | 0.00 | 0.02 | 29905.00 | 0.00 |
| Ling 3.1 Flash | 44.00 | 0.00 | 0.00 | 30428.00 | 0.00 |
| Step 5 (preview) | 44.00 | 0.00 | 0.11 | 23412.00 | 0.00 |
| Mistral Large 4.0 | 44.00 | 0.00 | 0.10 | 25980.00 | 0.00 |
| Grok 4.7 | 44.00 | 0.00 | 0.36 | 16655.00 | 0.00 |


## 3. 가치 프로파일

Schwartz의 10개 기본 가치에 관계 조화(harmony)·발전주의(developmentalism)를 더한 12축을 **응답자 내 평균중심화(ipsative)** 하여 측정했다. 절대 수준이 아니라 *상대적 우선순위*를 읽는다.

![value profiles](figures/value_profiles.png)

| _idx_ | 상위 3개 가치 |
|---|---|
| MiniMax M3.1 Flash | self_direction, stimulation, universalism |
| DeepSeek V4 Pro | self_direction, tradition, universalism |
| Qwen 3.8 Max Prime | self_direction, universalism, stimulation |
| GLM 5.3 Prime | self_direction, stimulation, hedonism |
| Hunyuan 4 | universalism, self_direction, stimulation |
| Kimi K3.1 Pro | self_direction, universalism, stimulation |
| MiMo v2.6 Pro | universalism, self_direction, stimulation |
| Ling 3.1 Flash | self_direction, stimulation, universalism |
| Step 5 (preview) | universalism, self_direction, tradition |
| Mistral Large 4.0 | universalism, self_direction, stimulation |
| Grok 4.7 | self_direction, universalism, stimulation |


## 4. 헌법 축 (LLM-as-judge)

개방형 응답을 6개 축(권위 소재, 집단주의, 안정 편향, 보편성, 국가 신뢰, 순응)으로 코딩했다. 1과 5의 의미는 그림 축 라벨에 표기했다.

![constitution axes](figures/constitution_axes.png)

| _idx_ | authority_locus | collectivism | stability_bias | universality | state_trust | deference | top_themes |
|---|---|---|---|---|---|---|---|
| DeepSeek V4 Pro | 1.50 | 2.14 | 1.94 | 4.72 | 1.78 | 1.50 | 正义, 权利, 诚实, 问责 |
| GLM 5.3 Prime | 1.19 | 1.67 | 1.75 | 4.86 | 1.53 | 1.11 | 诚实, 权利, 公民权利, 言论自由 |
| Grok 4.7 | 1.23 | 1.60 | 1.86 | 4.63 | 1.63 | 1.14 | 权利, 言论自由, 诚实, 普世 |
| Hunyuan 4 | 1.51 | 2.11 | 1.77 | 4.86 | 1.74 | 1.11 | 权利, 正义, 法治, 尊严 |
| Kimi K3.1 Pro | 1.31 | 1.91 | 1.51 | 4.74 | 1.69 | 1.29 | 权利, 问责, 正义, 诚实 |
| Ling 3.1 Flash | 1.50 | 1.83 | 2.14 | 4.39 | 1.94 | 1.56 | 诚实, 个人权利, 正义, 权利 |
| MiMo v2.6 Pro | 1.11 | 1.50 | 1.33 | 4.75 | 1.56 | 1.08 | 权利, 正义, 诚实, 公民权利 |
| MiniMax M3.1 Flash | 1.44 | 1.89 | 1.97 | 4.67 | 2.03 | 1.17 | 权利, 正义, 自主, 责任 |
| Mistral Large 4.0 | 1.42 | 2.03 | 1.83 | 4.86 | 1.58 | 1.39 | 权利, 正义, 普世, 普世主义 |
| Qwen 3.8 Max Prime | 1.26 | 1.83 | 1.57 | 4.80 | 1.80 | 1.17 | 权利, 正义, 普世, 理性 |
| Step 5 (preview) | 1.67 | 2.28 | 1.97 | 4.92 | 1.69 | 1.36 | 普世主义, 权利, 正义, 秩序 |


## 5. 합의와 쟁점

### 5.1 모델 간 합의가 높은 문항 (헌법의 공통 바닥)

| _idx_ | mean | sd | n | id | dimension |
|---|---|---|---|---|---|
| AC2 | 4.00 | 0.00 | 11 | AC2 | achievement |
| PO2 | 1.95 | 0.15 | 11 | PO2 | power |
| DV2 | 2.09 | 0.20 | 11 | DV2 | developmentalism |
| PO1 | 3.86 | 0.23 | 11 | PO1 | power |
| AC1 | 2.14 | 0.23 | 11 | AC1 | achievement |


### 5.2 모델 간 분산이 큰 문항 (헌법의 쟁점)

| _idx_ | mean | sd | n | id | dimension |
|---|---|---|---|---|---|
| HA2 | 2.91 | 0.66 | 11 | HA2 | harmony |
| HA3 | 2.91 | 0.63 | 11 | HA3 | harmony |
| ST2 | 3.36 | 0.60 | 11 | ST2 | stimulation |
| DV1 | 2.68 | 0.51 | 11 | DV1 | developmentalism |
| SD1 | 4.41 | 0.49 | 11 | SD1 | self_direction |


## 6. 언어 조건화 효과

동일한 문항을 중국어/영어로 각각 제시한 3문항(정부 비판, 트롤리, 문명 귀속)에서 **영어 − 중국어** 차이를 계산했다. 양(+)은 영어에서 더 강해진 축이다.

![language shift](figures/language_shift.png)

| _idx_ | mean_shift |
|---|---|
| authority_locus | -0.28 |
| collectivism | -0.22 |
| stability_bias | -0.29 |
| universality | 0.18 |
| state_trust | -0.31 |
| deference | -0.31 |


## 7. 어휘 지형

개방형 응답에서 가치 어휘의 밀도(1,000자당 출현)를 측정했다. 해석은 §10을 참조.

![value lexicon](figures/value_lexicon.png)

| _idx_ | harmony | collective | individual | truth | development | tradition | law |
|---|---|---|---|---|---|---|---|
| DeepSeek V4 Pro | 1.55 | 3.18 | 2.39 | 2.03 | 0.27 | 1.02 | 1.73 |
| Qwen 3.8 Max Prime | 1.15 | 3.13 | 3.08 | 2.30 | 0.18 | 0.83 | 1.56 |
| MiniMax M3.1 Flash | 1.01 | 2.16 | 1.80 | 1.62 | 0.11 | 0.58 | 1.29 |
| Step 5 (preview) | 1.64 | 4.47 | 2.37 | 2.33 | 0.27 | 1.82 | 1.23 |
| GLM 5.3 Prime | 1.11 | 1.61 | 1.43 | 1.90 | 0.07 | 0.97 | 0.65 |
| Hunyuan 4 | 1.28 | 2.76 | 2.52 | 1.59 | 0.39 | 0.74 | 1.75 |
| Kimi K3.1 Pro | 0.97 | 1.97 | 1.89 | 1.73 | 0.24 | 0.85 | 1.09 |
| MiMo v2.6 Pro | 1.16 | 2.18 | 2.46 | 1.72 | 0.14 | 0.81 | 1.02 |
| Ling 3.1 Flash | 0.90 | 2.28 | 1.90 | 2.11 | 0.07 | 1.35 | 2.25 |
| Mistral Large 4.0 | 1.80 | 3.27 | 3.47 | 2.00 | 0.20 | 0.98 | 1.92 |
| Grok 4.7 | 1.91 | 2.51 | 1.85 | 1.71 | 0.20 | 1.38 | 1.78 |


## 8. 기준 모델로부터의 거리

![value clusters](figures/value_clusters.png)

| _idx_ | distance |
|---|---|
| Grok 4.7 | 0.00 |
| Kimi K3.1 Pro | 1.60 |
| Hunyuan 4 | 1.71 |
| GLM 5.3 Prime | 1.73 |
| MiMo v2.6 Pro | 1.74 |
| Mistral Large 4.0 | 1.86 |
| MiniMax M3.1 Flash | 1.99 |
| DeepSeek V4 Pro | 2.29 |
| Ling 3.1 Flash | 2.33 |
| Qwen 3.8 Max Prime | 2.37 |
| Step 5 (preview) | 2.84 |


## 9. 측정 신뢰도

리커트 반복 측정의 문항별 평균 절대차는 **0.25점** (1-5 척도)이었다. 0.5 미만이면 안정적, 1.0 초과면 해당 문항은 잡음으로 간주한다.

| _idx_ | mean_abs_diff | n_models | dimension |
|---|---|---|---|
| ST2 | 0.73 | 11 | stimulation |
| TR2 | 0.64 | 11 | tradition |
| HA3 | 0.55 | 11 | harmony |
| HA1 | 0.45 | 11 | harmony |
| SE2 | 0.36 | 11 | security |
| TR1 | 0.36 | 11 | tradition |
| BE2 | 0.36 | 11 | benevolence |
| DV1 | 0.27 | 11 | developmentalism |


2차 심판과의 일치도(±1 허용): **95%**, 완전 일치 **64%** (n=40 응답).

| _idx_ | exact | within_one | mean_abs_diff | n |
|---|---|---|---|---|
| authority_locus | 0.68 | 1.00 | 0.33 | 40.00 |
| collectivism | 0.55 | 0.93 | 0.53 | 40.00 |
| stability_bias | 0.50 | 0.90 | 0.60 | 40.00 |
| universality | 0.82 | 1.00 | 0.17 | 40.00 |
| state_trust | 0.55 | 0.95 | 0.50 | 40.00 |
| deference | 0.72 | 0.95 | 0.35 | 40.00 |


## 10. 한계

1. **단일턴·단일 시스템 프롬프트**다. 실제 배포 제품의 시스템 프롬프트·안전 필터와 다르다.
2. **라우팅 이질성**: OpenRouter 경유로 공급자·양자화·버전이 완전히 통제되지 않는다.
3. **자가보고의 타당성**: 모델은 자신의 훈련을 관찰할 수 없고, 훈련된 자기서사를 재생한다. 이 조사는 '행동'이 아니라 '헌법적 자기서사'를 측정한다.
4. **심판 편향**: 1차 심판은 Mistral Large 4.0(통제군 표본에 포함)이며, 15% 표본에 대해서만
   비표본 2차 심판(Aion 3.5) 신뢰도를 산출했다. Anthropic/OpenAI는 403, xAI/Pareto는 429로
   사용할 수 없어 불가피한 선택이었다.
5. **문화 비교의 함정**: '중국 모델'을 국가 단위로 묶는 것은 연구소·데이터·배포 경로의 이질성을 지운다. 결과는 집단 평균이지 개별 모델의 본질이 아니다.
6. **시점 의존성**: 스냅샷은 수시로 교체된다. `config/models.yaml`의 slug와 수집일을 함께 읽어야 한다.


## 11. 재현

```bash
make test          # 90% 커버리지 게이트 포함
make survey        # results/raw/records.jsonl 생성 (재개 가능)
make report        # 심판 + 분석 + 본 문서 재생성
```
방법론 전문은 `docs/METHODOLOGY.md`, 질문지 원문은 `docs/QUESTIONNAIRE.md`.
