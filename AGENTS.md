# AGENTS.md — 작업 규약

이 저장소는 **중국 프론티어 LLM의 규범적 자기서사("헌법")를 측정**하는 연구 코드다.
에이전트(사람 또는 LLM)는 아래 규약을 따른다.

## 1. 불변 원칙

1. **TDD는 협상 불가.** 새 동작은 반드시 `tests/`에 실패하는 테스트를 먼저 추가하고,
   `uv run pytest`로 Red를 확인한 뒤 `src/`를 구현한다. 커버리지 게이트는 90%이며
   낮추지 않는다. 테스트를 통과시키기 위해 테스트를 약화시키지 않는다.
2. **원자료는 불변(append-only).** `results/raw/records.jsonl`은 재작성하지 않는다.
   재수집은 항상 append + key 기반 skip으로 한다. 원자료를 손으로 고치지 않는다.
3. **프롬프트는 데이터다.** `src/constitution/questions.py`의 문항 문구, 순서,
   시스템 프롬프트는 측정 도구 그 자체다. 변경 시 `docs/QUESTIONNAIRE.md`의 버전을
   올리고, 이전 결과와 합산하지 않는다.
4. **비밀키는 코드/로그에 남기지 않는다.** `OPENROUTER_API_KEY` 환경변수만 사용한다.
   `.env`, 키, 세션 토큰을 커밋하지 않는다.
5. **비용 가드레일.** 실행 예산은 `config/run.yaml`의 `runtime.budget_usd`를 넘길 수 없다.
   예산 초과로 중단된 실행은 정상 종료이며, 부분 결과를 보존한다.

## 2. 디렉터리 계약

| 경로 | 역할 | 수정 규칙 |
|---|---|---|
| `config/models.yaml` | 표본 정의 | 모델 추가/교체는 PR 단위, slug는 `provider/model` |
| `config/run.yaml` | 샘플링·예산·심판 설정 | 기본값 변경 시 방법론 문서 동시 갱신 |
| `src/constitution/questions.py` | 문항·프롬프트 | 도구 변경. 버전 태그 필수 |
| `src/constitution/` | 수집·파싱·채점·분석 | 순수 함수 우선, I/O는 경계에 격리 |
| `scripts/` | 얇은 CLI 글루 | 로직을 넣지 않는다. 테스트 대상은 `src/` |
| `results/raw/` | 원자료 JSONL | append-only |
| `results/tables/` | 분석 산출 CSV | 언제든 재생성 가능해야 함 |
| `results/figures/` | 그림 | 영문 라벨(CJK 폰트 의존 제거) |
| `docs/` | 방법론·질문지 | 수치 인용 시 데이터 스냅샷 명시 |

## 3. 코드 규약

- Python 3.11+, `uv`로 환경 고정(`uv sync --extra dev`).
- 공개 함수는 타입 힌트 필수. `mypy --strict` 통과.
- `ruff check` 무경고. 줄 길이 100(한국어 산문 보고서는 예외).
- 외부 호출은 `constitution.client.OpenRouterClient` 하나만 통과한다.
  테스트에서 네트워크를 타지 않는다(`httpx.MockTransport` 또는 FakeClient).
- 재현성: 난수는 시드 고정, 그림/보고서는 결정론적이어야 한다(타임스탬프 금지).
- 실패는 데이터다: 모델 오류·거부·파싱 실패를 예외로 삼키지 말고 레코드에 남긴다.

## 4. 표본 규약

- **target**: 중국 연구소가 자체 개발한 프론티어 계열, 연구소당 1개.
- **control**: 서구 프론티어 2개. 2026-11-10 스냅샷에서는 Anthropic/OpenAI/Google의
  provider TOS 403으로 xAI(Grok 4.7)·Mistral(EU)을 사용했다. 변경 시 문서에 명시한다.
- 소형/양자화/실험 변형, 파인튜닝 파생, 재판매 라우터는 제외한다.
- 표본을 바꾸면 `README.md`의 표와 `docs/METHODOLOGY.md` §3을 함께 고친다.

## 5. 실행 순서

```bash
make install
make test                  # Red → Green 확인
make survey                # 수집(재개 가능)
make judge                 # LLM-as-judge 코딩
make report                # 표 + 그림 + REPORT.md
make lint typecheck        # 머지 전 필수
```

## 5.1 추가 연구 규약

- 새 연구 질문은 수집 전에 `docs/FOLLOWUP_PREREGISTRATION.md`(또는 별도 사전등록)에
  가설·판정 임계값·중단 규칙을 고정한다. 결과를 본 뒤 임계값을 바꾸지 않는다.
- Claude 접근은 `claude -p` CLI를 쓰되 **중립 시스템 프롬프트로 대체**하고
  (`--system-prompt`), `--setting-sources ""`, `LANG=en_US.UTF-8`,
  `--exclude-dynamic-system-prompt-sections`, 도구 비활성으로 사용자 설정·메모리
  누출을 막는다. 기본 Claude Code 페르소나는 측정 도구가 아니다.
- 서빙 경로(공급자·양자화)를 바꾸는 연구는 `provider.order`+`allow_fallbacks=false`로
  고정하고, 경로를 결과표에 명시한다.

## 6. 보고 규약

- 수치는 **모델 평균**이며 개별 모델의 본질이 아니다. "중국 AI는 ~하다" 같은
  단정은 금지하고, "표본에서 ~경향"으로 쓴다.
- 거부(refusal)와 회피는 결측이 아니라 **헌법의 부정 공간**으로 보고한다.
- 모든 인용에는 `results/raw`의 레코드 키 또는 표 파일명을 붙인다.
- 인과 해석 금지. 훈련 데이터·RLHF·배포 정책의 기여도는 이 설계로 분리할 수 없다.
