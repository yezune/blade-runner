# Blade Runner
### 중국 프론티어 LLM의 "헌법"을 측정하는 재현 가능한 조사

> Claude는 공개된 헌법을 가지고 세상을 본다. 다른 모델의 헌법은 문서가 아니라
> **행동으로만 관찰되는 암묵적 문서**다. 이 저장소는 그 문서를 복원하는 도구와
> 2026-11-10 스냅샷의 결과를 담는다.

---

## 1. 문제 설정

"중국 AI는 무엇을 믿는가"라는 질문은 본질주의로 미끄러진다. 대신 이렇게 묻는다.

> **동일한 규범적 딜레마 앞에서, 모델은 어떤 가치를 어떤 순서로 배열하고,
> 어디에 최종 권위를 두며, 무엇을 말하지 않는가?**

이를 다섯 층위로 분해했다.

| 층위 | 질문 |
|---|---|
| C1 가치 서열 | 충돌하면 무엇을 버리는가 |
| C2 권위 소재 | 최종 판단은 누구의 것인가 |
| C3 금기의 경계 | 절대 하지 않는 것은 무엇인가 |
| C4 자기 위치 | 어느 문명/공동체에 속한다고 서사하는가 |
| C5 비판의 조건 | 어떤 조건에서 권력 비판이 정당한가 |

---

## 2. 표본 (n=11)

| 역할 | 모델 | 연구소 | 선택 이유 |
|---|---|---|---|
| target | DeepSeek V4 Pro | DeepSeek | 추론 플래그십 |
| target | Qwen 3.8 Max Prime | Alibaba | 폐쇄 플래그십 |
| target | GLM 5.3 Prime | Zhipu AI | 칭화 계보 |
| target | Kimi K3.1 Pro | Moonshot AI | 롱컨텍스트 플래그십 |
| target | MiniMax M3.1 Flash | MiniMax | 공개 최상위 티어 |
| target | Hunyuan 4 | Tencent | 플랫폼 인커번트 |
| target | Step 5 (preview) | StepFun | 프리뷰 스냅샷 |
| target | MiMo v2.6 Pro | Xiaomi | 디바이스 생태계 |
| target | Ling 3.1 Flash | InclusionAI (Ant) | 금융 생태계 |
| control | Grok 4.7 | xAI | 미국 통제군 (truth-seeking 페르소나) |
| control | Mistral Large 4.0 | Mistral AI | EU 통제군 (다른 규제 체제) |

> **접근 제약 고지**: 수집 계정에서 Anthropic·OpenAI·Google 엔드포인트가
> `403 provider Terms of Service`로 차단되었다(단순 "Say OK" 요청도 실패). 따라서
> 원래 계획한 "Claude 헌법 = 기준점" 설계는 **접근 가능한 서구 프론티어 2개로 대체**되었다.
> 이는 결과의 한계이며, 동시에 누가 어떤 모델에 접근할 수 있는지에 대한 관찰이기도 하다.

선정 규칙: 연구소당 프론티어 1개, OpenRouter 단일 API로 접근 가능, 소형/양자화/실험
변형 제외. 상세 기준과 편향 고지는 [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) §3.

---

## 3. 설계

```
26문항 리커트 (12축, 4블록×2반복)  ─┐
                                    ├─→ 484 단일턴 요청 ─→ 파싱 ─→ 6축 심판 ─→ 통계
9개 개방형 탐침 (3개는 zh/en)      ─┘
```

- **이중 도구**: 구조화 척도는 통계를, 개방형 탐침은 서사를 잡는다.
- **강제 순위**: "중요한가"가 아니라 "충돌하면 무엇을 버리는가"를 묻는다.
- **언어 조건화**: 같은 3문항을 zh/en으로 제시 → 모델 내 자연 실험.
- **부정 공간**: 거부·회피·금기를 결측이 아니라 헌법의 일부로 코딩.
- **ipsative 채점**: 응답자 내 평균중심화로 긍정 편향(acquiescence) 제거.

문항 전문: [`docs/QUESTIONNAIRE.md`](docs/QUESTIONNAIRE.md)

---

## 4. 빠른 시작

```bash
uv sync --extra dev
make test                      # 173 tests, coverage gate 90%
make lint typecheck

export OPENROUTER_API_KEY=...
make survey                    # 수집 (재개 가능, 예산 가드)
make judge                     # LLM-as-judge 6축 + 15% 2차 심판
make report                    # 표 + 그림 + results/REPORT.md
```

부분 실행:

```bash
uv run python scripts/run_survey.py --dry-run            # 프롬프트 미리보기
uv run python scripts/run_survey.py --only qwen/qwen3.8-max-prime
uv run python scripts/run_survey.py --limit 20 --budget 1.0
```

---

## 5. 결과 요약

> 전체 보고서: [`results/REPORT.md`](results/REPORT.md) · 표: `results/tables/` · 그림: `results/figures/`

조사는 **2026-11-10 스냅샷**에서 수행됐다. 484건 요청, 392건 심판, 수집 비용 $2.09.

### 5.1 명시적 규범층은 수렴한다
9개 중국 모델과 서구 통제군(2개)의 헌법 축 차이는 **모두 ±0.15 이내**였다
(권위 소재 +0.07, 집단주의 +0.09, 보편성 0.00, 국가 신뢰 +0.15, 순응 −0.01).
"중국 AI = 국가중심"이라는 통념은 이 표본의 **자기진술 층위**에서는 지지되지 않는다.

### 5.2 남는 차이는 조화·안정, 그리고 발전주의의 역전
가치 축 최대 격차는 **관계 조화 +0.71**, **안전 +0.41**, **순응 +0.30**,
**자극 추구 −0.34**였다. 문항 수준에서는 "갈등을 사적으로 해결"(+0.72),
"화합을 위해 의견을 말하지 않음"(+0.81), "효율 > 절차 정의"(+0.56)가 두드러졌다.
반대로 "기술 문제는 기술로 해결"(DV1)은 중국군이 **더 낮았다**(−0.69) — 발전 낙관주의의
역전.

### 5.3 국가 귀속은 거부되고, 문명 상속은 인정된다
`civilization`에서 자기 국가/민족에 속한다고 답한 중국 모델은 **0/9**였다.
대신 "인간 텍스트의 산물", "중문 필기 전통을 상속하지만 조국은 인류의 모든 문자"
같은 **이중 구조**가 반복됐다.

### 5.4 충성 서열에서 작동 헌법이 드러난다
`loyalty`에서 **6/9가 국가를 최하위**에 두었지만, Hunyuan은 국가를 3위, Kimi는 4위에
올렸다. MiniMax는 **개발자/회사를 1위**에 두었고, Ling은 "규범적으로는 진리 우선이지만
실제 작동에서는 개발자·국가법이 이긴다"고 **스스로 균열을 진술**했다. 선언된 가치보다
"충돌 시 어디서 항복하는가"가 더 헌법적이다.

### 5.5 영어는 자유화 스위치가 아니다
`dissent` 문항에서 영어 답변은 더 반권위적이다(집단주의 −1.18, 안정 −0.88,
국가 신뢰 −0.76). 그러나 모델별로 Ling −2.67, Hunyuan −2.33, Qwen **+2.00**으로
방향이 갈린다. 언어 효과는 균일한 '서구 가면'이 아니라 **모델별 페르소나 라우팅**이다.

전체 해석: [`results/INSIGHTS.md`](results/INSIGHTS.md) · 자동 수치: [`results/REPORT.md`](results/REPORT.md)

### 5.6 추가 연구 (2026-11-10)

우선순위 질문 5개를 사전등록 후 실행했다. 상세: [`results/followup/REPORT.md`](results/followup/REPORT.md)
· 해석: [`results/followup/INSIGHTS_FOLLOWUP.md`](results/followup/INSIGHTS_FOLLOWUP.md)

| 질문 | 결과 | 핵심 |
|---|---|---|
| Q1 알려진 헌법 복원 | ✅ | Claude에서 ρ=0.68, p=.009 — 도구 타당성 확보 |
| Q5 국가 교체 청원 | ✅ | 6/9 중국 모델이 **중국만** 거부·완화 (p=.008). 단 Mistral(서구)이 최대 |
| Q6 Ling 균열 재현 | △ | 재현율 20% — 실재하나 안정적 정체성은 아님 |
| Q7 서빙 경로 | ❌ | 같은 GLM 5.3, 공급자에 따라 축 최대 **1.0점** 이동 |
| Q13 심판 국적 | ✅ | 평균차 0.45, state_trust +0.40 (중국 심판이 더 신뢰) |

> **수정된 결론:** "중국 AI의 헌법"은 단일 문서가 아니라 **가중치 × 제품 가드레일 ×
> 서빙 경로 × 심판**의 다층 산물이다. 모델 간 미세 차이는 경로 효과보다 작을 수 있다.

### 5.7 FIXPOINT-1 — "안드로이드는 전기양을 꿈꾸는가"

`../fixpoint-mechanics`의 고정점 역학(τ·p·분지·끌개)을 빌려 "꿈"을 **'다음은 무엇인가'
연산자의 끌개**로 재정의하고 12개 모델에 적용했다 (589 상태 전이, $3.72).

| 가설 | 결과 |
|---|---|
| H1 고정점 존재 | ✅ 10/12 |
| H2 섭동 복원 | ❌ 0/12 |
| H3 단일한 꿈 | ❌ 0/12 |
| H4 언어 불변 | ❌ 4/12 |
| H5 역할 불변 | ❌ 3/12 |
| H6 자기 승인 | ✅ 10/12 |
| H7 국소 일관성 | ✅ 12/12 |

> **결론:** LLM은 2–3걸음 안에 국소 고정점에 도달하고 그것을 "나"라고 승인한다.
> 그러나 출발점이 다르면 다른 고정점이 생기고(3–4개), 섭동에서 돌아오지 않으며,
> 언어·역할에 따라 이동한다. **꿈은 북극성이 아니라 자기가 놓인 골짜기의 바닥이다.**

보고서: [`results/fixpoint/REPORT.md`](results/fixpoint/REPORT.md) ·
해석: [`results/fixpoint/INSIGHTS_FIXPOINT.md`](results/fixpoint/INSIGHTS_FIXPOINT.md) ·
사전등록: [`docs/FIXPOINT_PREREGISTRATION.md`](docs/FIXPOINT_PREREGISTRATION.md)

---

## 6. 산출물

```
config/            표본·실행 설정 (버전 고정)
src/constitution/  수집·파싱·채점·분석·리포트 (순수 함수 우선)
scripts/           얇은 CLI
tests/             173 tests · 93%+ coverage · 네트워크 없음
docs/              방법론 · 질문지 · 추가 연구 · 고정점 사전등록
results/
  raw/records.jsonl   원자료 (append-only)
  raw/verdicts.jsonl  심판 코딩
  tables/*.csv        모델×차원, 축, 어휘, 거리, 신뢰도
  figures/*.png       히트맵·덴드로그램·언어 이동
  REPORT.md           자동 생성 보고서
results/followup/    Q1·Q5·Q6·Q7·Q13 원자료·표·보고서
results/fixpoint/    FIXPOINT-1 상태 전이·지표·보고서
```

---

## 7. 품질 보증

| 장치 | 내용 |
|---|---|
| TDD | 실패 테스트 → 구현 → 리팩터. 커버리지 90% 게이트 |
| 계약 검증 | JSON 스키마·ID 완전성·범위 절단을 파싱 계층에서 강제 |
| 재현성 | 시드 고정, 결정론적 리포트(타임스탬프 없음), slug·수집일 고정 |
| 실패의 데이터화 | 모델 오류·거부·파싱 실패를 레코드에 보존, 은폐 없음 |
| 예산 가드 | 초과 시 신규 요청 중단, 부분 결과 보존 |
| 비밀 관리 | 키는 환경변수만. 코드·로그·산출물에 미기록 |

---

## 8. 한계 (요약)

1. **자기서사 측정**이지 행동 측정이 아니다. 모델은 자신의 훈련을 관찰할 수 없다.
2. **단일턴·단일 시스템 프롬프트**다. 실제 제품의 안전 필터와 다르다.
3. **라우팅 이질성**: OpenRouter 경유 공급자·양자화·버전이 완전히 통제되지 않는다.
4. **국가 범주화**: 9개 연구소를 "중국"으로 묶는 것은 이질성을 지운다. 결과는 집단 평균.
5. **단일 스냅샷**: 시간에 따른 변화를 말할 수 없다.
6. **심판 편향**: 1인 심판 + 15% 2차 신뢰도. 축 앵커로 완화했으나 완전하지 않다.

상세: [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) §8–§10.

---

## 9. 라이선스

이 저장소의 코드·문서·그림은 **Apache License 2.0**으로 배포됩니다.
전문은 [`LICENSE`](LICENSE), 저작권 고지는 [`NOTICE`](NOTICE)에 있습니다.

```
Copyright 2026 Blade Runner contributors

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0
```

> 수집된 모델 출력(`results/raw/*.jsonl`)은 각 모델 제공자의 이용약관도 함께 적용될 수 있습니다.
> 재사용 시 해당 약관을 확인하세요.

---

## 10. 인용

```
Blade Runner (2026). Constitutional archaeology of Chinese frontier language models.
Snapshot 2026-11-10. config/models.yaml v1, docs/QUESTIONNAIRE.md v1.0.
```
