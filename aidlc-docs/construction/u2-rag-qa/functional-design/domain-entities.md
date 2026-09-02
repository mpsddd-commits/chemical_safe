# Domain Entities — u2-rag-qa

**유닛**: `u2-rag-qa` (2/5)
**작성일**: 2026-08-24
**근거 답변**: FQ2-1~20 (권장안, FQ2-4 = b)

u1 의 엔터티(E1~E13)는 그대로 사용합니다. 여기서는 **u2 가 새로 만드는 것**만 정의합니다.
Alembic 리비전 **`0002_query`** 로 생성합니다.

---

## 0. u1 에서 물려받는 것 (변경 없음)

| u1 엔터티 | u2 에서의 역할 |
|---|---|
| `document` | 인용 대상. `source_url`·`title`·`law_name`·`structure_status` 를 인용 표기에 사용 |
| `document_section` | 인용 라벨(`section_code`, `section_title`). **NULL 일 수 있다** — BR-20a 강등 문서와 BR-31a 통합 청크 |
| `extracted_text` | 스니펫 원문. 청크 오프셋은 **이 텍스트 기준**(BR-30) |
| `chunk` | 검색 단위이자 인용 단위. `start_offset`·`end_offset`·`meta` |
| `chunk_embedding` | 벡터 검색 대상 |
| `substance` / `substance_synonym` | 질의 엔티티 해석에 사용 |

> **BR-30 이 u2 의 전제입니다.** 실데이터 1,564청크에서 위반 0건이 확인되었으므로,
> `extracted_text.text[start_offset:end_offset]` 가 청크 본문과 정확히 일치한다고 가정합니다.
> 이 가정 위에 C41 의 스니펫 하이라이트가 성립합니다.

---

## 1. 신규 영속 엔터티

### E14. `query_log` — 질의 기록 (FQ2-20)

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `id` | bigint | PK | |
| `question` | text | not null | 질의문 원문 |
| `asked_at` | timestamptz | not null, default now() | |
| `owner_id` | int | null, FK→(u5) | **u5 계정 연동 전까지 항상 NULL** |
| `mode` | varchar(16) | not null | `RetrievalMode` |
| `outcome` | varchar(24) | not null | `AnswerOutcome` |
| `refusal_reason` | varchar(32) | null | `RefusalReason`. `outcome` 이 거부일 때만 |
| `retrieval_ms` | int | null | NFR-2 측정 |
| `total_ms` | int | null | NFR-1 측정 |
| `candidate_count` | int | null | 융합 후 후보 수 |
| `top_score` | double | null | 1단 거부 판정에 쓰인 최상위 스코어 |

인덱스: `ix_query_log_asked_at (asked_at DESC)`, `ix_query_log_outcome (outcome, asked_at DESC)`

**보존**: `QUERY_LOG_RETENTION_DAYS` (기본 90). 만료분은 삭제. 질의문은 개인정보일 수 있으므로
보존 기간을 설정으로 두고, u5 이전에는 소유자를 기록하지 않습니다.

---

### E15. `answer_sentence` — 생성된 문장과 그 근거 (FR-19)

인용의 저장 단위입니다. 답변 본문을 통째로 저장하지 않고 **문장 단위로** 저장하는 이유는,
2단 검증(FR-21)의 판정 대상이 문장이고 인용도 문장 단위이기 때문입니다.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `id` | bigint | PK | |
| `query_id` | bigint | not null, FK→`query_log`, ON DELETE CASCADE | |
| `ordinal` | int | not null | 답변 내 순서 |
| `text` | text | not null | 문장 본문 |
| `support` | varchar(16) | not null | `SupportVerdict` |
| `removed` | boolean | not null, default false | 2단 검증에서 제거되었는지 (FQ2-9) |

제약: `uq_answer_sentence (query_id, ordinal)`

---

### E16. `answer_citation` — 문장 ↔ 청크 (FR-19)

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `id` | bigint | PK | |
| `sentence_id` | bigint | not null, FK→`answer_sentence`, ON DELETE CASCADE | |
| `chunk_id` | bigint | **null 허용**, FK→`chunk`, **ON DELETE SET NULL** | 현재 코퍼스에 그 청크가 살아 있는지를 나타내는 **선택적 링크** |
| `rank` | int | not null | 근거 목록 내 순위 |

제약: `uq_answer_citation (sentence_id, chunk_id)`
— PostgreSQL 은 UNIQUE 에서 NULL 을 서로 구별하므로, 재색인 후 한 문장에 NULL 인용이 여럿
남는 것이 허용됩니다. 이는 의도된 동작입니다. 각 행은 자기 스냅샷(E17)을 갖고 있어
서로 다른 근거이며, 중복 제거의 대상이 아닙니다.

> **`chunk_id` 가 SET NULL 인 이유** *(2026-08-25 정정)*: 재색인(BR-54)은 청크를 **전량 교체**합니다.
> CASCADE 면 과거 답변의 인용이 조용히 사라집니다. **RESTRICT 는 더 나쁩니다** — 참조가 남아 있는
> 한 청크 DELETE 자체가 거부되므로, **한 번이라도 인용된 문서는 영구히 재색인 불가**가 됩니다.
> 재색인은 이 시스템의 핵심 운영 경로입니다. BR-44(원본 보존)가 존재하는 이유가 "소스 재호출 없이
> 파싱 규칙 변경을 적용한다"이고, BR-20a·BR-31a·BR-27a 가 모두 그 경로로 배포되었습니다.
> u2 가 그 능력을 없애서는 안 됩니다.
>
> SET NULL 을 기각했던 근거("근거 없는 문장이 남는다")는 **E17 도입 이전의 판단**이었습니다.
> E17 은 `source_url` · `snippet` 이 NOT NULL 인 완전한 인용 기록이므로, 인용 표시는 전적으로
> 스냅샷이 담당합니다. `chunk_id` 는 "지금도 검색 가능한 청크인가"를 나타내는 링크일 뿐이고,
> NULL 은 정보 소실이 아니라 **"재색인되었다"는 사실 그 자체**입니다.
>
> 따라서 **인용 표시 경로는 `chunk` 를 절대 조인하지 않습니다.** E17 만 읽습니다(BR-92a).
> `chunk_id` 는 "원문의 현재 판본 보기" 같은 부가 기능에만 씁니다.

---

### E17. `citation_snapshot` — 인용 시점의 근거 동결

재색인이 청크를 교체해도 **과거 답변의 인용이 무엇을 가리켰는지**는 남아야 합니다.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `citation_id` | bigint | PK, FK→`answer_citation`, ON DELETE CASCADE | |
| `document_id` | int | not null | 인용 당시 문서 |
| `source_url` | text | not null | BR-32 — 원문 추적은 항상 가능해야 한다 |
| `document_title` | text | null | |
| `section_code` | varchar(64) | null | **NULL 허용** — BR-20a·BR-31a |
| `section_title` | varchar(200) | null | |
| `snippet` | text | not null | 인용 당시 청크 본문 그대로 |
| `start_offset` | int | not null | 당시 오프셋 (참고용) |
| `end_offset` | int | not null | |

**동결 시점**: 답변 확정 직후(2단 검증 통과 후) 즉시 기록합니다. 나중에 만들면
그 사이의 재색인으로 원본이 바뀔 수 있습니다.

> **동결은 답변 확정과 같은 트랜잭션입니다** *(2026-08-25 정정)*. `answer_sentence` ·
> `answer_citation` · `citation_snapshot` 이 함께 커밋되거나 함께 롤백됩니다.
> 스냅샷 없는 인용 행은 **존재해서는 안 됩니다** — 그 행은 인용을 표시할 수도 없고
> (표시 경로가 E17 만 읽으므로) 재색인이 지나가면 무엇을 가리켰는지도 알 수 없습니다.
> 동결 실패는 답변 자체의 실패로 처리합니다(W8-7).
>
> 이 엔터티는 **불변**입니다. 한 번 기록되면 갱신하지 않습니다. 답변이 인용한 시점의
> 사실을 보존하는 것이 목적이므로, 이후 원본이 개정되어도 스냅샷은 그대로 둡니다.

---

### E18. `llm_call` — LLM 호출 추적 (FR-41, NFR-19)

u1 의 `TraceRepo` 는 인메모리였습니다. 여기서 실제 테이블이 됩니다.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `id` | bigint | PK | |
| `query_id` | bigint | null, FK→`query_log`, ON DELETE SET NULL | 질의와 무관한 호출도 있을 수 있음 |
| `called_at` | timestamptz | not null, default now() | |
| `purpose` | varchar(24) | not null | `LlmPurpose` — 생성 / 검증 / 엔티티추출 |
| `provider` | varchar(32) | not null | `anthropic` |
| `model` | varchar(64) | not null | 예: `claude-opus-5` |
| `prompt_name` | varchar(64) | null | FQ2-16 |
| `prompt_version` | varchar(32) | null | FQ2-16 |
| `input_tokens` | int | null | |
| `output_tokens` | int | null | |
| `cache_read_tokens` | int | null | 프롬프트 캐시 적중 확인용 |
| `latency_ms` | int | not null | |
| `cost_usd` | numeric(12,6) | **null 허용** | 단가 미등록 모델은 NULL (FQ2-19) |
| `ok` | boolean | not null | |
| `stop_reason` | varchar(32) | null | `refusal` 포함 |
| `error_kind` | varchar(32) | null | `FailureKind` 재사용 |

인덱스: `ix_llm_call_called_at (called_at DESC)`, `ix_llm_call_purpose (purpose, called_at DESC)`

> **`cost_usd` 가 NULL 을 허용하는 이유**: 단가가 등록되지 않은 모델의 비용을 0 으로 기록하면
> 사용량 화면이 "무료"라고 거짓말합니다. NFR-8(데이터 부재 시 추정 금지)이 비용에도 적용됩니다.
> 화면은 NULL 을 "단가 미등록"으로 표시하고 합계에서 제외하되, **제외된 호출 수를 함께 표시**합니다.

---

## 2. 요청 수명 동안만 존재하는 값 객체 (비영속)

### V1. `QueryIntent` — 엔티티 추출 결과 (C30, FR-17)

```
substance_names: list[str]     # 물질명 (동의어 해석 후)
cas_numbers:     list[str]     # 정규화된 CAS
un_numbers:      list[str]
doc_type_hint:   DocType | None  # "법적 기준" 같은 표현에서 추정, 확신 없으면 None
raw_terms:       list[str]     # 키워드 검색에 그대로 넘길 어휘
```

`doc_type_hint` 는 **필터가 아니라 가중치 힌트**입니다. 필터로 쓰면 질문이 조금만 어긋나도
정답 문서가 후보에서 사라집니다.

### V2. `Candidate` — 검색 후보

```
chunk_id:    int
keyword_rank: int | None       # 키워드 검색 순위 (없으면 None)
vector_rank:  int | None       # 벡터 검색 순위
fused_score:  float            # RRF 점수
rerank_score: float | None     # 리랭커를 켰을 때만
doc_type:     DocType
document_id:  int
```

### V3. `Evidence` — 최종 근거 (C35 산출물)

```
chunk_id, document_id, source_url, document_title
section_code: str | None       # NULL 가능 — 없는 라벨을 만들지 않는다
section_title: str | None
text: str
start_offset, end_offset: int
score: float
```

### V4. `GeneratedAnswer` — 구조화 출력 (C38, FQ2-11)

LLM 이 **스키마로 강제되어** 반환하는 형태입니다.

```
sentences: list[{ text: str, chunk_ids: list[int] }]
```

Anthropic SDK 의 `client.messages.parse(..., output_format=GeneratedAnswer)` 로 받고
`response.parsed_output` 을 사용합니다. Pydantic 모델이 그대로 스키마가 됩니다.

> **Anthropic 네이티브 citations 기능은 쓰지 않습니다.** `citations: {enabled: true}` 는
> `output_config.format` 과 **동시 사용이 불가**(400)합니다. 그리고 우리에게는 이미
> 더 나은 출처가 있습니다 — 네이티브 인용은 우리가 넘긴 문서 안의 문자 위치를 주지만,
> BR-30 오프셋은 **원본 `extracted_text` 기준 위치**라 원문 링크까지 이어집니다.

---

## 3. Enum

### `RetrievalMode`
| 값 | 의미 |
|---|---|
| `hybrid` | 키워드 + 벡터 융합 (기본) |
| `hybrid_reranked` | 융합 후 리랭커 적용 |

### `AnswerOutcome`
| 값 | 의미 |
|---|---|
| `answered` | 답변 생성 완료 |
| `answered_partial` | 일부 문장이 2단 검증에서 제거됨 (FQ2-9) |
| `refused_low_relevance` | 1단 거부 (FR-20) |
| `refused_unsupported` | 2단 검증 후 남은 문장 없음 (FQ2-10) |
| `error` | 생성 실패 |

### `RefusalReason`
| 값 | 의미 |
|---|---|
| `no_candidates` | 검색 결과 자체가 없음 |
| `below_threshold` | 최상위 스코어가 임계값 미달 |
| `all_sentences_unsupported` | 전 문장이 근거 미지지 |
| `provider_refusal` | LLM 이 `stop_reason=refusal` 반환 |

### `SupportVerdict`
| 값 | 의미 |
|---|---|
| `supported` | 인용 근거가 문장을 지지함 |
| `unsupported` | 지지하지 않음 → 제거 |
| `unverified` | 검증 호출 실패 — **지지로 간주하지 않는다** |

> `unverified` 를 별도 값으로 두는 이유: 검증에 실패한 것과 검증해서 통과한 것은 다릅니다.
> 안전 정보에서 이 둘을 합치면 위험(R-6)합니다. 처리는 `unsupported` 와 같게 하되
> 기록은 구분합니다.

### `LlmPurpose`
| 값 | 의미 |
|---|---|
| `answer` | 답변 생성 (C38) |
| `verify` | 근거 지지 검증 (C40) |
| `entity` | 질의 엔티티 추출 (C30) — 규칙 기반으로 충분하면 호출하지 않음 |

---

## 4. 마이그레이션 `0002_query`

생성: `query_log`, `answer_sentence`, `answer_citation`, `citation_snapshot`, `llm_call`
인덱스 5종. u1 테이블 변경 **없음**.

`chunk` 에 대한 FK 가 SET NULL 이므로 **재색인 경로(`ChunkRepo.replace_for_document`)는
변경이 필요 없습니다.** 청크는 지금처럼 전량 교체되고, 인용은 `chunk_id` 가 NULL 로 풀리며
표시에 필요한 사실은 이미 E17 에 동결되어 있습니다. u1 코드 수정 없음.

> *(2026-08-25 정정)* 이전 판에서는 RESTRICT 를 전제로 재색인 경로에 "인용 확인 → 동결 → 교체"
> 단계를 추가하려 했습니다. 그 순서는 성립하지 않습니다 — 동결은 **답변 시점**에 일어나야 하고
> (재색인 시점에는 이미 원본이 바뀌었을 수 있습니다), RESTRICT 는 동결 여부와 무관하게
> DELETE 를 막습니다. 동결을 답변 트랜잭션으로 옮기면 재색인은 아무것도 몰라도 됩니다.

---

## 5. 추적성

| FR | 엔터티 |
|---|---|
| FR-14 질의 접수 | E14 |
| FR-17 엔티티 추출 | V1 |
| FR-15/16 검색·리랭크 | V2, `RetrievalMode` |
| FR-18 근거 기반 생성 | V3, V4 |
| FR-19 문장 단위 인용 | E15, E16, E17 |
| FR-20 1단 거부 | E14.`refusal_reason` |
| FR-21 2단 검증 | E15.`support`, `SupportVerdict` |
| FR-22 무상태 | E14 에 세션 개념 없음 |
| FR-41 호출 추적 | E18 |
| FR-42 사용량 조회 | E18 집계 |
