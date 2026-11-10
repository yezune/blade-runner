# results/ — 산출물 안내

| 경로 | 내용 | 재생성 |
|---|---|---|
| `raw/records.jsonl` | 원자료. 요청 1건 = 1줄. 프롬프트·응답·비용·오류·타임스탬프 포함 | append-only, `make survey` |
| `raw/verdicts.jsonl` | 1차 심판(Mistral Large 4.0)의 6축 코딩 | `make judge` |
| `raw/verdicts_second.jsonl` | 2차 심판(Aion 3.5, 비표본), 15% 표본, 신뢰도용 | `make judge` |
| `tables/dimensions.csv` | 모델 × 12 가치축 (ipsative) | `make report` |
| `tables/item_scores.csv` | 모델 × 26문항 평균 | `make report` |
| `tables/axes.csv` | 응답 단위 6축 코딩 (원자료 수준) | `make report` |
| `tables/axes_by_question.csv` | 모델 × 문항 평균 축 | `make report` |
| `tables/language_delta.csv` | 이중언어 문항의 en−zh 이동량 | `make report` |
| `tables/shared.csv` / `contested.csv` | 합의 상위 / 분산 상위 문항 | `make report` |
| `tables/lexicon.csv` | 모델 × 7개 가치 어휘군 밀도 | `make report` |
| `tables/distance.csv` | 기준 모델까지의 유클리드 거리 | `make report` |
| `tables/reliability.csv` | 리커트 반복 측정 오차 | `make report` |
| `tables/coverage.csv` | 요청 수·오류율·비용 | `make report` |
| `figures/*.png` | 가치 히트맵, 군집 덴드로그램, 축 히트맵, 언어 이동, 어휘 지형 | `make report` |
| `REPORT.md` | 자동 생성 보고서 (수치·표·그림) | `make report` |
| `INSIGHTS.md` | 사람이 쓴 해석 (자동 보고서와 분리) | 수동 |

## 읽는 순서

1. `REPORT.md` §1 핵심 발견 → §3 가치 프로파일 → §6 언어 조건화
2. `INSIGHTS.md` — 수치가 말하지 않는 맥락과 반례
3. `tables/axes.csv` — 개별 응답 단위로 내려가 확인

## 주의

- `raw/`는 **불변**이다. 재수집은 append + key skip.
- 표·그림은 언제든 재생성된다. 손으로 고치지 않는다.
- 비용은 OpenRouter usage 기준이며, 재시도·실패 호출은 0으로 기록될 수 있다.
