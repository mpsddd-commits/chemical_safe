# Business Logic Model — u4-evaluation

**컴포넌트** C44~C48 · **서비스** S5 `EvaluationService` · **워크플로** W15~W18

---

## 0. 이 유닛의 형태를 결정한 것

```
무료 티어  모델당 하루 20 요청
답변형 질의 1건 = 5.25 LLM 호출   (실측: llm_call 전수, answered 15건)
거부형 질의 1건 = 0.03 호출       (실측: refused_low_relevance 33건)

→ 25문항 답변형 = 131 호출 = 7일
```

**한 번의 전체 평가가 일주일 걸린다.** 그래서 이 유닛의 워크플로는 둘로 갈린다 —
매일 돌리는 것과 가끔 돌리는 것. 그 경계는 임의가 아니라 **LLM 을 부르는가**다.

---

## 1. 컴포넌트

### C44 `GoldenSetLoader` (FR-36)
```python
load(path: str) -> GoldenSet          # 검증 실패 시 예외
fingerprint(path: str) -> str         # SHA-256
```
- YAML 파싱 → `GoldenQuestion` 목록
- **DB 대조 검증**(BR-114): 모든 `EvidenceRef` 의 소스·문서·섹션이 실재하는가
- `expects: refusal` 인데 `evidence` 가 비어 있지 않으면 오류
- id 중복 검사

> 검증을 로더에 두는 이유: 8일짜리 작업이 7일째에 오타로 죽으면 안 된다.
> 검증에는 DB 조회만 들고 LLM 은 필요 없다.

### C45 `RetrievalMetrics` (FR-37)
```python
score(question: GoldenQuestion, retrieved: list[RetrievedRef]) -> RetrievalScore
```
- Recall@5, Recall@10, Reciprocal Rank (BR-124)
- 적중 판정: `section` 이 있으면 (문서, 섹션) 일치, 없으면 문서 일치 (BR-113)
- **LLM 을 부르지 않는다**

### C46 `AnswerMetrics` (FR-37, NFR-5)
```python
citation_precision(question, sentences) -> float
refusal_correct(question, outcome) -> bool
```
- 인용 정확도: 문장에 붙은 청크가 정답 근거 소속인가 (BR-125)
- 거부 정확도 / 오거부 (BR-127, BR-128)
- **LLM 을 부르지 않는다** — 정답률만 C47 이 맡는다

### C47 `LLMJudge` (FR-38)
```python
judge(question, answer_text, evidence_texts) -> Judgement
```
- **한 번의 호출로 `correct` 와 `faithful` 을 함께 받는다** (BR-126)
- 답변 모델과 다른 모델 (BR-122), `LLMPort` 를 통해 호출 (NFR-21)
- 프롬프트 `prompts/judge/1.0.0.md` (BR-123)
- 구조화 출력 스키마 — u2 의 `GeneratedAnswer` 와 같은 이유로 JSON 스키마 강제

> 심판에게 주는 것은 **질문·기대 답변 요지·실제 답변·근거 본문**이다.
> 골든셋의 정답 근거를 주지 않는다 — 그것을 주면 심판이 정답을 베낀다.

### C48 `EvaluationReporter` (FR-39, NFR-26)
```python
aggregate(items: list[EvaluationItem]) -> RunMetrics
compare(run_id, baseline_id) -> ComparisonReport
verdict(report) -> Verdict            # ok | regression | incomparable
render(report) -> str                 # CLI 출력
```
- 집계 → `evaluation_run.metrics`
- 기준선 대비 변화표 + 회귀 판정 (BR-130)
- **비교 불가 판정**: `corpus_fingerprint`·모델·프롬프트가 다르면 `incomparable`
  경고를 붙인다. 다른 것을 잰 두 숫자를 뺄셈하지 않는다

---

## 2. S5 `EvaluationService`

```python
run(golden_set_path: str, *, mode: str, config: RetrievalConfig | None) -> EvaluationRun
resume(run_id: int) -> EvaluationRun
list_runs(limit: int) -> list[EvaluationRunSummary]
compare(run_id: int, baseline_id: int | None) -> ComparisonReport
promote_baseline(run_id: int) -> None
```

**S5 는 S3 를 그대로 호출한다** (BR-115). 평가 경로와 실사용 경로가 같다는 것이
DD-22 이고, 그것이 이 유닛의 숫자가 의미를 갖는 유일한 이유다.

---

## 3. 워크플로

### W15 — 검색 평가 (`evaluate --retrieval-only`)

```
1. C44.load() + 검증                       (LLM 0)
2. run 생성  mode=retrieval_only
3. 문항마다:
     질문 → 엔티티(규칙) → 검색(하이브리드+융합) → 후보 목록
     C45.score()  →  item 저장 (BR-117)
     expects=refusal 이면 1단계 거부 판정만 기록 (BR-120)
4. C48.aggregate() → run.metrics
5. baseline 이 있으면 C48.compare() → 종료코드
```

**LLM 호출 0. 30문항에 수초.** 매일 돌린다.
u2 결함 27·45 가 여기서 잡혔을 종류의 회귀다.

### W16 — 전체 평가 (`evaluate --full`)

```
1~2. W15 와 동일 (mode=full)
3. 문항마다 (트랜잭션 1개):
     a. S3.answer(question)          ← 실사용 경로 그대로 (BR-115, 검증 포함 BR-116)
     b. C45.score(retrieved)
     c. expects=refusal → C46.refusal_correct()   ... LLM 0 (BR-120)
        expects=answer  → C46.citation_precision()
                          C47.judge()             ... LLM 1 (다른 모델, BR-122)
     d. item 저장
     e. 할당량 오류면 → status=quota_exhausted, run.status=partial, 중단 (BR-118)
4~5. W15 와 동일
```

### W17 — 재개 (`evaluate --resume <run_id>`)

```
1. run 로드. status 가 partial 이 아니면 거부
2. golden_set_hash 재확인 — 파일이 바뀌었으면 거부하고 새 실행을 권한다
3. status IN (quota_exhausted, pending) 인 문항만 W16 3단계 반복
4. 남은 문항이 0이면 status=succeeded
```

> 해시가 바뀌었는데 이어서 도는 것은 **두 개의 다른 골든셋으로 채점한 실행**을
> 하나로 만드는 일이다. 거부한다.

### W18 — 비교·승격 (`evaluate --compare` / `--promote`)

```
compare:  run vs baseline  → 지표별 델타표 + verdict
promote:  is_baseline = true   ← 사람이 명시적으로 (BR-129)
```

---

## 4. CLI (C60 확장)

```bash
safeenv evaluate --retrieval-only            # LLM 0, 수초, 매일
safeenv evaluate --full                      # LLM 필요, 며칠에 걸쳐
safeenv evaluate --resume <run_id>
safeenv evaluate --list
safeenv evaluate --compare <run_id> [--baseline <id>]
safeenv evaluate --promote <run_id>
```

종료코드 (UD-10 / NFR-26):

| 코드 | 의미 |
|---|---|
| 0 | 정상. 회귀 없음 |
| 1 | **회귀** — 기준선 대비 하락 |
| 2 | 골든셋 검증 실패 |
| 3 | 실행 실패 (DB·설정) |
| 4 | `partial` — 할당량 소진. **회귀 판정 없음** |

> 4를 1과 구분하는 이유: 할당량 소진은 품질 문제가 아니다. 4를 실패로 취급하면
> 무료 티어에서 CI 가 항상 빨간불이 된다.

---

## 5. 이 유닛이 하지 않는 것

| 안 하는 것 | 이유 |
|---|---|
| 골든셋 자동 생성 | 평가 대상 모델이 정답을 만드는 구조 |
| 평가 전용 검색 경로 | DD-22 위반. 실사용과 다른 것을 재게 된다 |
| 문장별 심판 호출 | 문항당 5~9 호출 추가 → 무료 티어에서 실행 불가 |
| 자동 기준선 승격 | 나빠진 실행이 새 기준선이 되어 회귀가 영원히 안 잡힌다 |
| GitHub Actions 연동 | UD-10 — 로컬 CLI 종료코드로 확정 |
