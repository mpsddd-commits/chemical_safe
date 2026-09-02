# Domain Entities — u4-evaluation

**FR**: FR-36, 37, 38, 39
**신규 테이블 2개** — `evaluation_run`, `evaluation_item`. 마이그레이션 `0003_evaluation`
(0002 이후 최초). u1·u2·u3 의 테이블은 **하나도 바뀌지 않는다.**

---

## 0. 골든셋은 왜 테이블이 아닌가

FR-36 은 "저장소에서 관리한다"이고, 그 말대로 파일이다 — `eval/golden-set.yaml`.

DB 에 넣으면 **리뷰가 불가능해진다.** 이 파일은 사람이 손으로 쓰고 고치는 유일한
산출물이고(R-5), 변경 이력이 코드와 같은 곳에 남아야 "지표가 좋아진 것"과
"정답을 느슨하게 고친 것"을 구분할 수 있다. DB 에는 **실행 결과만** 들어간다.

대신 실행은 자신이 무엇을 채점했는지 알아야 하므로 `golden_set_hash` 를 남긴다.
파일이 바뀌면 해시가 바뀌고, 비교 시 경고가 나간다.

---

## 1. `evaluation_run` — 실행 1회

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `id` | PK | |
| `mode` | varchar(16) | `retrieval_only` \| `full` (BR-117) |
| `status` | varchar(16) | `running` \| `partial` \| `succeeded` \| `failed` |
| `golden_set_path` | varchar(512) | |
| `golden_set_hash` | char(64) | 파일 내용 SHA-256 |
| `question_count` | int | 이 실행이 대상으로 한 문항 수 |
| `config` | JSONB | `RetrievalConfig` 스냅샷 — `top_k`, `rerank_enabled`, `refusal_score_threshold`, `retrieval_mode` |
| `embedding_model` | varchar(128) | |
| `answer_model` | varchar(128) | `retrieval_only` 이면 NULL |
| `judge_model` | varchar(128) | BR-119 — 답변 모델과 달라야 한다 |
| `prompt_versions` | JSONB | `{answer: "1.0.0", verify: "1.0.0", judge: "1.0.0"}` |
| `corpus_fingerprint` | JSONB | `{documents, chunks, latest_revised_at}` |
| `metrics` | JSONB | 집계 지표 (4절) |
| `baseline_id` | FK → self, NULL | 이 실행이 비교한 기준선 |
| `is_baseline` | bool | **명시적 승격** (BR-126) |
| `llm_calls` | int | 이 실행이 실제로 쓴 호출 수 |
| `started_at` · `finished_at` | timestamptz | |
| `note` | text | |

**왜 이만큼 기록하는가.** u2 결함 34 에서 "타임아웃을 예산에서 유도했다가 성공한
11,582ms 생성을 죽인" 일이 있었다. 지표가 나빠졌을 때 **모델이 바뀐 것인지,
프롬프트가 바뀐 것인지, 코퍼스가 바뀐 것인지** 구분할 수 없으면 그 숫자는 진단에
쓸 수 없다. `metrics` 만 남기면 반드시 그 상황이 온다.

인덱스: `ix_eval_run_baseline (is_baseline, finished_at desc)`

---

## 2. `evaluation_item` — 문항 1건의 채점 결과

**행 하나 = 트랜잭션 하나** (BR-115). u1 의 수집 잡이 문서 단위로 커밋하는 것과
같은 이유다(DD-24/BR-53): 8일에 걸쳐 도는 작업은 중간에 반드시 끊긴다.

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `id` | PK | |
| `run_id` | FK → `evaluation_run` ON DELETE CASCADE | |
| `question_id` | varchar(64) | 골든셋의 `id` (`law-01`) |
| `category` | varchar(16) | `law` \| `substance` \| `msds` \| `incident` \| `refusal` |
| `expects` | varchar(8) | `answer` \| `refusal` |
| `status` | varchar(24) | `done` \| `skipped` \| `quota_exhausted` \| `failed` |
| `query_id` | FK → `query_log`, NULL, **ON DELETE SET NULL** | DD-22 의 증거 |
| `outcome` | varchar(32) | `query_log.outcome` 사본 |
| `retrieved` | JSONB | 순위대로 `[{rank, chunk_id, document_id, section_code}]` |
| `recall_at_5` · `recall_at_10` | numeric(4,3) | |
| `reciprocal_rank` | numeric(4,3) | |
| `citation_precision` | numeric(4,3), NULL | 답변형만 |
| `refusal_correct` | bool, NULL | 거부형만 |
| `judge_correct` · `judge_faithful` | bool, NULL | FR-38 |
| `judge_reason` | text, NULL | 심판의 근거. **숫자만 남기지 않는다** |
| `llm_calls` · `total_ms` | int | |
| `error_kind` | varchar(64), NULL | |
| `evaluated_at` | timestamptz | |

제약: `UNIQUE (run_id, question_id)` — 재개가 같은 문항을 두 번 채점하지 못하게 한다.
인덱스: `ix_eval_item_run_status (run_id, status)` — 재개가 남은 문항을 찾는 경로.

### `query_id` 가 SET NULL 인 이유
u2 가 `answer_citation` 에서 같은 결정을 했다(BR-93). 재색인이 청크를 지워도 답변
기록은 남아야 한다. 여기서도 **평가 결과는 질의 로그보다 오래 살아야 한다** — 6개월
전 실행의 Recall 은 그 질의 로그가 정리된 뒤에도 의미가 있다.

### `retrieved` 를 JSONB 로 두는 이유
FQ5-7(답변 재사용)의 핵심이다. 검색 결과를 그대로 남겨두면 **지표 코드를 고쳐도
검색을 다시 돌릴 필요가 없다** — Recall@k 의 k 를 바꾸거나 인용 정확도 정의를
고칠 때 무료로 재계산된다.

---

## 3. 값 객체 (영속되지 않는다)

u2 의 `rag/types.py` 와 같은 분리다. 저장 형태는 위 두 테이블이고, 아래는 실행 중에만
산다.

```python
@dataclass
class GoldenQuestion:      # C44 가 만든다
    id: str
    category: str
    question: str
    expects: Literal["answer", "refusal"]
    answer_points: list[str]
    evidence: list[EvidenceRef]
    rationale: str | None

@dataclass
class EvidenceRef:
    source: str            # source_id
    external_id: str
    section: str | None    # BR-130 - None 이면 문서 단위 채점

@dataclass
class ItemResult:          # C45·C46·C47 이 채운다
    question_id: str
    retrieved: list[RetrievedRef]
    recall: dict[int, float]
    reciprocal_rank: float
    citation_precision: float | None
    refusal_correct: bool | None
    judgement: Judgement | None

@dataclass
class Judgement:           # C47 이 한 번의 호출로 둘 다 받는다
    correct: bool
    faithful: bool
    reason: str

@dataclass
class RunMetrics:          # C48 이 집계한다
    ...

@dataclass
class ComparisonReport:    # C48 - 기준선 대비
    ...
```

### `EvidenceRef` 가 청크 ID 를 쓰지 않는 이유
이 프로젝트는 이미 **재색인을 네 번** 돌렸다. 청크 ID 로 정답을 적으면 그때마다
골든셋 30문항이 통째로 무효가 된다. `source + external_id` 는 BR-09 가 변경 판단에
쓰는 키라 재수집에도 살아남고, `section_code` 는 BR-26 이 만든 인용 단위다.

### `section` 이 nullable 인 이유 (BR-130)
BR-31a 로 섹션이 접힌 문서가 코퍼스에 **13건** 있다 — 사고 12건과 물질 1건. 그
문서들의 청크는 `section_id` 가 NULL 이므로 섹션으로 채점할 수 없다. 골든셋에서
`section` 을 생략하면 문서 단위로 채점한다. **없는 섹션을 지어내지 않는다**(NFR-8).

---

## 4. `metrics` JSONB 의 모양

```json
{
  "counts":    {"total": 30, "answered": 22, "refused": 8, "failed": 0, "skipped": 0},
  "retrieval": {"recall_at_5": 0.84, "recall_at_10": 0.92, "mrr": 0.71},
  "answer":    {"accuracy": 0.80, "citation_precision": 0.91},
  "refusal":   {"accuracy": 1.00, "false_refusal": 0.04},
  "judge":     {"faithfulness": 0.96, "judged": 22},
  "cost":      {"llm_calls": 118, "usd": 0.0}
}
```

`retrieval_only` 실행이면 `answer`·`judge` 가 없다. **0 이 아니라 없다** — 0.0 은
"측정했더니 0"으로 읽히고, 그것은 u1 이 `stats.substances = 0` 을 "아직 수집 안 함"
으로 읽었던 결함 40 과 같은 오독이다.

---

## 5. 마이그레이션 `0003_evaluation`

- `evaluation_run`, `evaluation_item` 생성
- 인덱스 3종
- **다운그레이드는 두 테이블 DROP** — 다른 테이블을 건드리지 않으므로 안전하다
- 기존 데이터 마이그레이션 없음
