# Code Generation Plan — u4-evaluation

**단계**: 🟢 CONSTRUCTION / Code Generation — 유닛 `u4-evaluation` (4/5)
**작성일**: 2026-08-28
**선행 승인**: Functional Design (2026-08-27, "그대로 진행")

---

## 유닛 컨텍스트

| 항목 | 내용 |
|---|---|
| **FR** | FR-36~39 (4건) / **BR** BR-111~BR-130 (20건) |
| **엔터티** | **신규 2개** — `evaluation_run`, `evaluation_item` |
| **마이그레이션** | **`0003_evaluation`** — 0002 이후 최초 |
| **LLM** | 심판만. 답변 모델과 **다른 모델** (BR-122) |

---

## 실측으로 확인한 배선 (설계 문서 대비 정정)

### `RetrievalConfig` 는 존재하지 않는다

설계 문서(`services.md`)의 `run(golden_set_path, config: RetrievalConfig)` 는
아직 만들어진 적이 없는 타입을 가리킨다. `QueryService` 는 `Settings` 를 직접 읽는다.

→ **설정 스냅샷은 `Settings` 에서 뽑는다.** `top_k`·`rerank_enabled`·
`refusal_score_threshold`·`rrf_k` 를 `evaluation_run.config` JSONB 에 넣는다.
없는 타입을 지금 만들면 u2 를 건드려야 하고, 이 유닛에 그럴 이유가 없다.

### `QueryResult` 는 검색 결과를 내보내지 않는다

```python
@dataclass
class QueryResult:
    query_id: int; outcome: ...; sentences: ...; citations: ...
    # 검색 후보 목록이 없다 — 인용된 것만 있다
```

Recall@k 는 **인용된 것이 아니라 검색된 것**을 본다. 두 가지 길이 있었다:

| 방법 | 문제 |
|---|---|
| S5 가 `retrieve()` 를 따로 한 번 더 호출 | 검색이 두 번 돈다. 지표가 답변과 **다른 실행**을 잰다 |
| `QueryResult` 에 `retrieved` 추가 | u2 파일 1개 수정 |

→ **후자.** 필드 추가는 가산적이고 u2 의 동작을 바꾸지 않는다. 무엇보다
**답변과 지표가 같은 검색 실행을 본다** — DD-22 가 요구하는 것이 그것이다.

### `retrieve()` 는 이미 공개 메서드다

`QueryService.retrieve(question, scope) -> (list[Evidence], RetrievalMode)`.
`--retrieval-only` 는 이것과 `refusal.decide()` 만 쓴다 — **LLM 경로에 들어가지 않는다.**

단, `retrieve()` 안의 엔티티 추출은 BR-64 에 따라 LLM 을 부를 수 있다
(`ENTITY_LLM_ENABLED=false` 라 현재는 안 부른다). BR-119 가 "한 번도 호출하지
않는다"이므로 **`--retrieval-only` 는 `entity_llm=None` 으로 서비스를 만든다** —
설정에 기대지 않는다.

### 프롬프트 레지스트리는 그대로 쓴다

`PromptRepository.get("judge")` 가 `prompts/index.yaml` 의 `judge: 1.0.0` 을 읽는다.
u2 의 answer·verify 와 완전히 같은 경로다.

---

## 파일 목록

### 신규 12

| 파일 | 컴포넌트 |
|---|---|
| `migrations/versions/0003_evaluation.py` | — |
| `app/db/repositories/evaluation.py` | `EvaluationRepo` |
| `app/evaluation/__init__.py` | — |
| `app/evaluation/types.py` | 값객체 |
| `app/evaluation/golden_set.py` | **C44** `GoldenSetLoader` |
| `app/evaluation/retrieval_metrics.py` | **C45** |
| `app/evaluation/answer_metrics.py` | **C46** |
| `app/evaluation/judge.py` | **C47** |
| `app/evaluation/reporter.py` | **C48** |
| `app/services/evaluation_service.py` | **S5** |
| `prompts/judge/1.0.0.md` | — |
| `eval/golden-set.yaml` | *(FD 단계에서 생성 완료)* |

### 수정 6

| 파일 | 변경 |
|---|---|
| `app/db/models.py` | `EvaluationRun`·`EvaluationItem` 추가 |
| `app/core/config.py` | 심판 모델·골든셋 경로·회귀 임계 |
| `app/adapters/llm_factory.py` | `build_judge_llm()` |
| `app/services/query_service.py` | `QueryResult.retrieved` 추가 |
| `app/cli.py` | `evaluate` 하위명령 6종 |
| `prompts/index.yaml` · `.env.example` | `judge: 1.0.0` / 새 환경변수 |

### 테스트 4

| 파일 | 대상 |
|---|---|
| `tests/unit/test_golden_set.py` | C44 — 스키마 검증, 실패가 실행 전에 나는가 |
| `tests/unit/test_evaluation_metrics.py` | C45·C46 — 계산식, 섹션 없는 문서 |
| `tests/unit/test_evaluation_reporter.py` | C48 — 집계·비교·회귀 판정·비교 불가 |
| `tests/integration/test_evaluation.py` | 실 DB — 골든셋 30문항 검증, `--retrieval-only` 종단 |

---

## 이 단계에서 지킬 것

| 규칙 | 코드에서의 모습 |
|---|---|
| BR-114 검증은 실행 전에 | `GoldenSetLoader.load()` 가 DB 대조까지 끝내고 예외를 던진다 |
| BR-115 실사용 경로 | S5 가 `QueryService.answer()` 를 부른다. 우회 없음 |
| BR-117 문항 1건 = 트랜잭션 1개 | `session_scope()` 를 문항 루프 **안**에서 연다 |
| BR-118 할당량은 `partial` | 할당량 예외를 잡아 `quota_exhausted` 로 저장하고 중단 |
| BR-119 `--retrieval-only` LLM 0 | `entity_llm=None`, 생성기 미구성 |
| BR-122 심판은 다른 모델 | 같으면 실행 시작 시 `ConfigurationError` |
| BR-129 기준선은 수동 승격 | `--promote` 없이는 `is_baseline` 이 바뀌지 않는다 |
| NFR-28 단위 테스트 DB 비의존 | C45·C46·C48 은 순수 함수. C44 만 DB 를 쓰고 통합에 둔다 |

---

## 하지 않는 것

- `RetrievalConfig` 타입 신설 — 설계 문서가 가정한 타입이 없다. 만들면 u2 를 건드린다
- 평가 전용 검색 경로 — DD-22 위반
- 웹 화면 — u4 는 CLI 유닛이다 (FR-36~39 어디에도 화면이 없다)
- GitHub Actions — UD-10 으로 로컬 CLI 종료코드 확정
