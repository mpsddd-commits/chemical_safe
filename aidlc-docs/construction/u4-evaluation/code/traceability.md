# Traceability — u4-evaluation

## 1. FR

| FR | 내용 | 구현 | 검증 |
|---|---|---|---|
| FR-36 | 골든 QA 셋 30~50문항 | `eval/golden-set.yaml` (30) · `evaluation/golden_set.py` | 단위 17 / 통합 3 |
| FR-37 | 검색·답변 지표 | `retrieval_metrics.py` · `answer_metrics.py` | 단위 24 / 통합 4 |
| FR-38 | LLM-as-judge 충실도 | `judge.py` · `prompts/judge/1.0.0.md` | ⚠️ **실행 미검증** |
| FR-39 | 이력 저장 · 이전 실행 대비 비교 | `reporter.py` · E19·E20 | 단위 22 / 통합 4 |

## 2. BR-111 ~ BR-130

| BR | 구현 위치 | 상태 |
|---|---|---|
| BR-111 골든셋 원본은 파일 | `eval/golden-set.yaml`, DB 는 결과만 | ✅ |
| BR-112 source+external_id | `EvidenceRef` | ✅ |
| BR-113 섹션 없으면 문서 단위 | `retrieval_metrics.matches()` | ✅ 통합 |
| BR-114 실행 전 검증 | `GoldenSetLoader.load()` | ✅ 통합 |
| BR-115 실사용 경로 | `_score_full` → `QueryService.answer()` | ✅ |
| BR-116 검증 끄지 않음 | 끄는 코드가 없다 | ✅ |
| BR-117 문항=트랜잭션 | `_store()` | ✅ 통합 |
| BR-118 할당량은 partial | `except QuotaExhaustedError` | ⚠️ **실행 미검증** |
| BR-119 retrieval-only LLM 0 | `_NoLLM` 가드 | ✅ 통합 실측 0 |
| BR-120 거부형은 심판 없음 | `if question.wants_answer` | ✅ |
| BR-121 답변 재사용 | `evaluation_item.retrieved` | ✅ 통합 |
| BR-122 심판 모델 분리 | `build_judge_llm()` | ✅ 단위 |
| BR-123 심판 프롬프트 버전 | `prompts/index.yaml` `judge: 1.0.0` | ✅ |
| **BR-124 Recall@5·@10** | `reporter.aggregate()` | ⚠️ **@10 측정 불가 — 결함 49** |
| BR-125 인용 정확도 근사 | `answer_metrics.citation_precision()` | ✅ 단위 |
| BR-126 한 호출로 두 판정 | `Judgement.json_schema()` | ⚠️ **실행 미검증** |
| BR-127 outcome 계열만 | `answer_metrics.is_refusal()` | ✅ 단위 |
| BR-128 오거부 병기 | `refusal_rates()` | ✅ 실측 0.000 |
| BR-129 수동 승격 | `EvaluationRepo.set_baseline()` | ✅ 통합 |
| BR-130 기준선 대비 하락 | `reporter.compare()` | ✅ 단위 |

## 3. NFR

| NFR | 상태 |
|---|---|
| NFR-5 인용 정확도 ≥95% | **측정 수단 제공** (근사, BR-125). 값은 미측정 |
| NFR-6 충실도 위반 ≤5% | **측정 수단 제공**. 값은 미측정 |
| NFR-26 회귀 시 비0 종료코드 | ✅ `EXIT_REGRESSION=1`, 할당량은 4로 분리 |
| NFR-21 제공자 추상화 | ✅ 심판도 `LLMPort` |
| NFR-28 단위 테스트 DB·네트워크 비의존 | ✅ C45·C46·C48 순수 함수 |

## 4. 검증

| 항목 | 결과 |
|---|---|
| FR 미구현 | **0** (FR-38 은 구현됨, 실행 미검증) |
| BR-111~130 미구현 | **0** |
| u1·u2·u3 테이블 변경 | **0** |
| 순환 의존 | **0** — `evaluation` → `rag`·`db`·`core` |
| 단위 테스트가 DB 를 쓰는가 | **0건** |

---

## 5. 미충족 · 미검증 (숨기지 않고 기록)

| 항목 | 상태 | 근거 |
|---|---|---|
| **BR-124 Recall@10** | ❌ 측정 불가 | 파이프라인이 `final_top_k=5` 개만 내보낸다. 5건짜리 목록의 Recall@10 은 Recall@5 다. **결함 49** — 같은 수를 두 이름으로 내는 대신 `None` 을 낸다 |
| **FR-38 심판 실행** | ⚠️ 미검증 | `--full` 이 한 번도 돌지 않았다. 무료 티어 131 호출 = 7일 |
| **BR-118 재개** | ⚠️ 미검증 | 할당량 소진 경로가 실제로 돈 적이 없다 |
| **NFR-5·NFR-6 값** | ⚠️ 미측정 | 측정 수단만 있다. 첫 `--full` 이 첫 값 |
| **회귀 임계값** | ⚠️ 초안 | 기준선이 없으므로 실측이 없다. 첫 `--full` 후 재검토 |

> **미검증 4건이 전부 `--full` 한 줄에 걸려 있다.** u1·u2 에서 "테스트는 초록불인데
> 그 경로가 한 번도 돈 적이 없다"가 결함 25·39·40·46·47 다섯 건을 만들었다.
> 지금 같은 자리에 서 있고, Build & Test 의 첫 과제가 이것이다.
