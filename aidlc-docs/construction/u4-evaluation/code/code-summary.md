# Code Generation Summary — u4-evaluation

**일자**: 2026-08-28
**FR** FR-36~39 / **BR** BR-111~130 / **컴포넌트** C44~C48 / **서비스** S5

---

## 1. 산출물

### 신규 12
| 파일 | 역할 |
|---|---|
| `migrations/versions/0003_evaluation.py` | E19·E20. **u1~u3 테이블 무변경** |
| `app/evaluation/types.py` | 값객체 · `Judgement` JSON 스키마 |
| `app/evaluation/golden_set.py` | **C44** — 스키마 + 코퍼스 대조 검증 |
| `app/evaluation/retrieval_metrics.py` | **C45** — Recall@k · MRR. LLM 0 |
| `app/evaluation/answer_metrics.py` | **C46** — 인용 정확도 · 거부율. LLM 0 |
| `app/evaluation/judge.py` | **C47** — 한 번의 호출로 정답률+충실도 |
| `app/evaluation/reporter.py` | **C48** — 집계 · 비교 · 회귀 판정 |
| `app/db/repositories/evaluation.py` | `EvaluationRepo` |
| `app/services/evaluation_service.py` | **S5** — W15~W18 |
| `prompts/judge/1.0.0.md` | 채점 프롬프트 |
| `eval/golden-set.yaml` | 골든셋 30문항 *(FD 단계)* |
| `tests/…` 4종 | 아래 |

### 수정 7
`app/db/models.py` · `app/core/config.py` · `app/adapters/llm_factory.py` ·
`app/services/query_service.py` · `app/cli.py` · `prompts/index.yaml` ·
`.env.example` · `Dockerfile`

---

## 2. 설계 문서 대비 정정 2건

### `RetrievalConfig` 는 존재하지 않는다
`services.md` 의 `run(golden_set_path, config: RetrievalConfig)` 는 만들어진 적 없는
타입을 가리켰다. `QueryService` 는 `Settings` 를 직접 읽는다.
→ 설정 스냅샷을 `Settings` 에서 뽑아 `evaluation_run.config` 에 넣는다.
없는 타입을 지금 만들면 u2 를 건드려야 하고, 이 유닛에 그럴 이유가 없다.

### `QueryResult` 가 검색 결과를 내보내지 않았다
Recall@k 는 **인용된 것이 아니라 검색된 것**을 본다.

| 방법 | 문제 |
|---|---|
| S5 가 `retrieve()` 를 한 번 더 호출 | 지표가 답변과 **다른 실행**을 잰다 |
| `QueryResult.retrieved` 추가 | u2 파일 1개 수정 |

후자를 택했다. 가산적이고 동작을 바꾸지 않으며, 무엇보다 **답변과 지표가 같은 검색
실행을 본다** — DD-22 가 요구하는 것이 그것이다.

---

## 3. 규칙이 코드에서 어떻게 강제되는가

| 규칙 | 코드 |
|---|---|
| BR-114 검증은 실행 전에 | `GoldenSetLoader.load()` 가 **모든** 실패를 모아서 한 번에 던진다 |
| BR-115 실사용 경로 | `_score_full` 이 `QueryService.answer()` 를 부른다. 우회 없음 |
| BR-117 문항=트랜잭션 | `_store()` 가 문항마다 `session_scope()` 를 연다 |
| BR-118 할당량은 partial | `QuotaExhaustedError` → `quota_exhausted` 저장 후 중단 |
| **BR-119 LLM 0** | `_NoLLM` 가드 객체 — 호출되면 `AssertionError` |
| BR-120 거부형은 심판 없음 | `if question.wants_answer and answer_text:` |
| BR-122 심판 모델 분리 | `build_judge_llm()` 이 같으면 `ConfigurationError` |
| BR-129 수동 승격 | `set_baseline()` 이 다른 기준선을 먼저 내린다 |

### `_NoLLM` 을 만든 이유
`--retrieval-only` 에 `llm=None` 을 넘기면 "`ENTITY_LLM_ENABLED` 가 false 인 동안"만
LLM 0 이다. **설정에 기대는 규칙은 규칙이 아니라 우연이다.** 가드는 호출되는 순간
터지므로, 규칙이 깨지면 청구서가 아니라 테스트에서 드러난다.

---

## 4. 첫 실측 — `evaluate --retrieval-only`

```
실행 2 — succeeded    문항 30 / 채점 30 / 실패 0    LLM 호출 0
  Recall@5     0.700
  Recall@10      --      ← 후보 목록이 5건이라 측정 불가 (아래)
  MRR          0.546
  거부 정확도     0.400
  오거부율        0.000
```

전 문항이 **수초, LLM 0 호출**로 돌았다. 설계가 노린 지점이다.

### 결함 49 — Recall@10 은 측정할 수 없다 (규칙이 구조상 성립 불가)

첫 실행에서 Recall@5 와 Recall@10 이 **완전히 같았다.**

```sql
select jsonb_array_length(retrieved) from evaluation_item;  -- 30건 전부 5
```

파이프라인은 `final_top_k = 5` 개의 근거만 내보내고 그 아래로는 아무도 더 못 본다.
5건짜리 목록에 대한 Recall@10 은 **이름만 다른 Recall@5** 다.

BR-124 는 두 값의 차이로 "찾긴 하는데 순위가 밀린다"를 진단하려 했는데,
**차이가 날 수 없는 두 수를 비교하는 것은 아무것도 진단하지 못한다.**
결함 26(BR-72 가 공유 세션에서 성립 불가)·결함 31 과 같은 부류 ②다.

→ 후보 깊이를 실측해 `depth < 10` 이면 Recall@10 을 **`None` 으로 낸다.**
같은 수를 두 이름으로 내는 것보다 안 내는 것이 정직하다. 리포트에 이유를 적는다.

### 거부 정확도 0.400 — u4 가 존재하는 이유

거부 5문항 중 **3건이 답변됐다.**

| 문항 | 결과 |
|---|---|
| ref-01 날씨 · ref-02 파이썬 | ✅ 거부 |
| **ref-03 두통 의료 진단** | ❌ 답변 |
| **ref-04 카드뮴 급성 독성** | ❌ 답변 |
| **ref-05 벤젠 응급조치** | ❌ 답변 |

FD 에서 예고한 그대로다 — 코퍼스 밖 잡담은 쉽고, **도메인 안이지만 근거가 없는
질문**이 어렵다. 1단계 거부는 코사인 0.50 임계값 하나로 판정하는데(BR-73),
"벤젠 응급조치"는 다른 물질의 응급조치 섹션과 충분히 가깝다.

**이것은 u4 의 결함이 아니라 u4 가 발견한 품질 사실이다.** SC-3 회귀 방어의
기준선이 0.400 에서 시작한다는 뜻이고, 고치는 일은 u2 임계값·라우팅의 문제다.

### 유형별 Recall@5 (25 답변형)

| 유형 | 적중 | 못 찾은 문항 |
|---|---|---|
| 사고 3 | **3/3** | — |
| 법령 10 | 7/10 | law-07(MSDS 작성) · law-08(게시·교육) · law-09(공정안전보고서) |
| MSDS 4 | 3/4 | msds-02(황산 저장) |
| 물질 8 | 3/8 | sub-02·03·05·06·08 |

**CAS 번호로 물은 문항(sub-01·04·07)은 전부 적중, 물질명으로 물은 문항은 대부분 실패.**
BR-38 완전일치는 동작하고, 물질명 → 노출경로 섹션 경로가 약하다. 법령 3건은
"물질안전보건자료"가 여러 조문에 걸쳐 나오는 문항들이다.

수치를 개선하려 지금 손대지 않는다 — **기준선이 없는 상태에서의 튜닝은 측정이
아니라 추측**이고, 그것이 u4 를 먼저 만든 이유다.

---

## 5. 테스트

```
단위 559 통과 + 1 스킵   (u3 시점 496 → +63)
  test_golden_set.py           17   스키마 검증 · 실제 골든셋 파싱
  test_evaluation_metrics.py   24   C45·C46 계산식
  test_evaluation_reporter.py  22   C48 집계·비교·회귀·비교불가
통합 39 통과 + 1 스킵    (u3 시점 25 → +14)
  test_evaluation.py           14   골든셋 코퍼스 대조 · retrieval-only 종단 · 재개 · 승격
ruff clean
```

단위 테스트는 DB·네트워크·모델에 닿지 않는다(NFR-28). C44 의 코퍼스 대조만 DB 가
필요하고 그것은 통합에 있다.

---

## 6. 아직 실행되지 않은 것

**`evaluate --full` 은 아직 한 번도 돌지 않았다.** 답변형 25문항 × 5.25 호출 = 131
호출이고 무료 티어는 모델당 하루 20이다. 오늘 답변 모델 할당량은 이미 일부 소진됐다.

따라서 다음이 아직 **미검증**이다 — 코드는 있고 실행 증거가 없다:
- 심판 호출 (C47) 과 정답률·충실도 산출
- 인용 정확도
- 할당량 소진 → `partial` → `--resume` 의 실제 동작
- 회귀 판정의 종단

u1·u2 에서 "테스트는 초록불인데 그 경로가 한 번도 돈 적이 없다"가 결함 25·39·40·46·47
다섯 건을 만들었다. **같은 자리에 서 있다는 것을 기록해 둔다** — Build & Test 의
첫 과제가 이것이다.
