# Component Methods — safeenv

**단계**: INCEPTION / Application Design
**작성일**: 2026-08-20

> 메서드 **시그니처와 목적**만 정의합니다. 세부 비즈니스 규칙은 Functional Design 이월 (components.md §15).
> 타입 표기는 Python 타입 힌트 형식이며, 최종 구현 명칭은 Code Generation에서 확정합니다.

---

## 0. 공용 타입 (개념 정의)

| 타입 | 의미 |
|---|---|
| `SourceRef` | 소스 식별자 + 원본 URL + 발행·개정일 + 콘텐츠 해시 |
| `RawDocument` | 원본 바이트 또는 원문 텍스트 + `SourceRef` |
| `ExtractedText` | 추출 텍스트 + 문자 오프셋 맵 (스니펫 역참조용) |
| `StructuredDoc` | 문서 유형 + 섹션 목록(번호·제목·오프셋 구간) |
| `Chunk` | 청크 텍스트 + 메타데이터 + 원문 오프셋 구간 |
| `ChunkMeta` | 물질명, CAS, 문서유형, 섹션번호·제목, 출처 URL, 발행일, `owner_id\|None` |
| `Candidate` | 청크 ID + 스코어 + 검색 경로(keyword\|vector) |
| `Evidence` | 청크 ID + 텍스트 + `ChunkMeta` + 최종 스코어 |
| `AnswerDraft` | `list[Sentence]` — 각 `Sentence`는 `{text, evidence_ids}` |
| `Citation` | 문서 ID + 섹션 + 스니펫 텍스트 + 오프셋 구간 + 원문 링크 |
| `QueryResult` | 상태(`answered\|refused`) + 문장·인용 + 면책 문구 + 사용 근거 + 추적 ID |
| `JobId`, `JobStatus` | 작업 식별자 / `pending\|running\|succeeded\|partial\|failed` |
| `Scope` | 검색 범위 — 공개 코퍼스 + `owner_id` 문서 |

---

## 1. L0 — 공용 기반

### C1 `Config`
```python
load() -> Settings                      # 환경변수·설정파일 로드 및 검증. 실패 시 명확한 오류로 기동 중단
get_model_config() -> ModelConfig       # LLM·임베딩·리랭커 모델명과 파라미터
get_thresholds() -> Thresholds          # 거부 임계값, 후보 수 K, 리랭커 on/off
```

### C2 `Logger`
```python
bind(request_id: str, **ctx) -> Logger   # 요청 상관관계 컨텍스트 바인딩
info(event: str, **fields) -> None       # 구조적 이벤트 로깅 (비밀값 자동 마스킹)
error(event: str, exc: Exception, **fields) -> None
```

### C3 `Database`
```python
session() -> ContextManager[Session]      # 트랜잭션 경계 제공
ensure_extensions() -> None               # pgvector 확장 등록 확인
```

### C4 `Repositories` (하위 8종의 대표 메서드)
```python
# SubstanceRepo
get_by_cas(cas: str) -> Substance | None
get_by_id(substance_id: int) -> Substance | None

# DocumentRepo
upsert(doc: StructuredDoc, source: SourceRef) -> int          # 문서 ID 반환
get_extracted_text(document_id: int) -> ExtractedText
find_by_hash(content_hash: str) -> Document | None

# ChunkRepo
bulk_insert(document_id: int, chunks: list[Chunk]) -> int
get_many(chunk_ids: list[int]) -> list[Evidence]
delete_by_document(document_id: int) -> int

# JobRepo / UserRepo / QueryLogRepo / EvaluationRepo / TraceRepo
#   -> 각 애그리게이트의 생성·조회·갱신. 상세는 Functional Design 이월
```

---

## 2. L1 — 포트와 어댑터

### C5 `SourceAdapter` *(Protocol)*
```python
source_id() -> str                                  # 소스 식별자
list_targets(since: datetime | None) -> Iterator[SourceRef]   # 수집 대상 목록 (증분 지원)
fetch(ref: SourceRef) -> RawDocument                # 단건 원본 확보
```

### C6 `LLMPort` *(Protocol)*
```python
generate(prompt: Prompt) -> LLMResult
generate_structured(prompt: Prompt, schema: dict) -> tuple[dict, LLMResult]
#   schema 를 강제하여 {문장, 근거 ID} 배열을 획득 (DQ-8=A)
#   LLMResult: 모델명, 입출력 토큰, 지연, 성공 여부
```

### C7 `EmbeddingPort` *(Protocol)*
```python
embed(texts: list[str]) -> list[Vector]
dimension() -> int
model_id() -> str          # 재색인 필요 여부 판정에 사용 (FR-13)
```

### C8 `RerankerPort` *(Protocol)*
```python
rerank(query: str, docs: list[str], top_k: int) -> list[tuple[int, float]]
#   (원본 인덱스, 스코어) 목록 반환
```

### C9 `SourceAdapters` — 구현 4종
```python
SubstanceApiAdapter   # 물질 기본정보·GHS 분류      (FR-1)
LawApiAdapter         # 법령 조문                    (FR-2)
IncidentDataAdapter   # 화학사고 사례                (FR-3)
MsdsPdfAdapter        # MSDS PDF                     (FR-4)
#   전부 C5 프로토콜 준수. 오케스트레이터는 구현체를 구분하지 않음
```

### C13 `TracingLLMDecorator`
```python
wrap_llm(inner: LLMPort) -> LLMPort
wrap_embedding(inner: EmbeddingPort) -> EmbeddingPort
wrap_reranker(inner: RerankerPort) -> RerankerPort
#   호출마다 TraceRepo 에 모델·토큰·지연·추정비용·성공여부 기록 (FR-41)
```

---

## 3. L2 — 수집 (u1)

### C14 `AccessPolicyChecker`
```python
check(url: str) -> PolicyDecision
#   PolicyDecision: allowed(bool) + reason(str) + checked_at
#   거부 시 우회 경로를 제공하지 않음 (CON-3)
is_allowed(url: str) -> bool
```

### C15 `ChangeDetector`
```python
has_changed(ref: SourceRef, known: Document | None) -> bool
#   콘텐츠 해시 또는 발행·개정일 비교 (FR-7)
```

### C16 `RetryPolicy` *(순수 컴포넌트 — 속성 기반 테스트 대상)*
```python
should_retry(attempt: int, error: Exception) -> bool
next_delay(attempt: int) -> float           # 지수 백오프
classify(error: Exception) -> FailureKind   # transient | permanent | policy_blocked
```

### C17 `IngestionOrchestrator`
```python
run(source_id: str, job_id: JobId, since: datetime | None) -> IngestionOutcome
#   1) C14 정책 검사 -> 거부 시 즉시 중단 및 기록
#   2) C5.list_targets -> C15 변경 판정 -> C5.fetch
#   3) 항목별 성공/실패를 C28 에 보고 (부분 성공 허용)
fetch_one(source_id: str, ref: SourceRef) -> RawDocument
```

---

## 4. L2 — 문서 처리 (u1)

### C18~C22 `PipelineStage` *(공통 프로토콜)*
```python
name() -> str
run(ctx: PipelineContext) -> PipelineContext    # 각 단계는 컨텍스트를 변환하여 반환
```

| 컴포넌트 | 주요 메서드 |
|---|---|
| **C18** `FetchStage` | `run()` — 원본 확보 및 원본 파일/URL 보존 |
| **C19** `ExtractStage` | `extract(raw: RawDocument) -> ExtractedText` — **문자 오프셋 보존** |
| **C20** `NormalizeStage` | `normalize(text: ExtractedText) -> ExtractedText` — 오프셋 맵 갱신 유지 |
| **C21** `StructureStage` | `structure(text: ExtractedText, doc_type: DocType) -> StructuredDoc` |
| **C22** `ChunkStage` | `chunk(doc: StructuredDoc, meta: ChunkMeta) -> list[Chunk]` |

### C23 `PipelineRunner`
```python
run(document_ref: SourceRef, stages: list[PipelineStage], job_id: JobId) -> PipelineOutcome
resume(document_id: int, from_stage: str) -> PipelineOutcome   # 재개 지점부터 실행
```

---

## 5. L2 — 색인 (u1)

### C24 `Embedder`
```python
embed_chunks(chunks: list[Chunk]) -> list[Vector]   # 배치 처리, 중복 텍스트 캐시
```

### C25 `VectorIndex`
```python
upsert(document_id: int, chunks: list[Chunk], vectors: list[Vector]) -> int
search(vector: Vector, top_k: int, filters: MetaFilter, scope: Scope) -> list[Candidate]
delete_by_document(document_id: int) -> int
```

### C26 `KeywordIndex`
```python
upsert(document_id: int, chunks: list[Chunk]) -> int
search(query: str, top_k: int, filters: MetaFilter, scope: Scope) -> list[Candidate]
lookup_exact(term: str, field: Literal["cas","un","name"]) -> list[Candidate]
```

### C27 `Reindexer`
```python
reindex_document(document_id: int) -> PipelineOutcome
reindex_all(reason: str, job_id: JobId) -> JobId     # 임베딩 모델 교체 시 (FR-13)
needs_reindex(current_model_id: str) -> bool
```

---

## 6. L2 — 작업 관리 (u1)

### C28 `JobTracker`
```python
create(kind: JobKind, params: dict) -> JobId
add_items(job_id: JobId, refs: list[SourceRef]) -> int
mark_item(job_id: JobId, ref: SourceRef, status: ItemStatus, reason: str | None) -> None
progress(job_id: JobId) -> JobProgress        # 총건/성공/실패/진행률
finalize(job_id: JobId) -> JobStatus          # 전건 실패 -> failed, 일부 성공 -> partial
resume_point(job_id: JobId) -> list[SourceRef]   # 미완료 항목만 반환 (FR-8)
```

### C29 `TaskQueue`
```python
enqueue(task_name: str, payload: dict) -> str    # 큐 등록만 담당. 상태 미보유
register(task_name: str, handler: Callable) -> None
```

---

## 7. L2 — 검색 (u2)

### C30 `EntityExtractor`
```python
extract(query: str) -> QueryEntities
#   QueryEntities: substance_names, cas_numbers, un_numbers
to_filter(entities: QueryEntities) -> MetaFilter
```

### C31 `KeywordRetriever` / C32 `VectorRetriever`
```python
retrieve(query: str, top_k: int, filters: MetaFilter, scope: Scope) -> list[Candidate]
```

### C33 `FusionRanker`
```python
fuse(results: list[list[Candidate]], top_k: int) -> list[Candidate]
#   순위 융합 (RRF 등). 융합식·가중치는 Functional Design 이월
```

### C34 `RerankStage`
```python
rerank(query: str, candidates: list[Candidate], top_k: int) -> list[Evidence]
is_enabled() -> bool          # 설정으로 비활성화 가능 (R-4 완화)
```

### C35 `RetrievalPipeline`
```python
retrieve(query: str, scope: Scope, config: RetrievalConfig) -> RetrievalOutcome
#   C30 -> (C31 || C32) -> C33 -> C34 순서로 조립
#   RetrievalOutcome: evidences, top_score, stage_timings, config_used
#   stage_timings 는 NFR-2 검증과 u4 평가 실험에 사용
```

---

## 8. L2 — 생성·인용·거부 (u2)

### C36 `PromptRegistry`
```python
get(name: str) -> PromptTemplate           # 템플릿 + 버전 식별자
render(name: str, **vars) -> Prompt
version_of(name: str) -> str               # 평가 결과에 기록 (NFR-22)
```

### C37 `ContextBuilder`
```python
build(query: str, evidences: list[Evidence]) -> PromptContext
#   문서 내용을 데이터 영역으로 격리하여 지시문 주입을 차단 (NFR-16)
#   각 근거에 안정적인 참조 ID 부여
```

### C38 `AnswerGenerator`
```python
generate(query: str, context: PromptContext) -> tuple[AnswerDraft, LLMResult]
#   C6.generate_structured 로 {문장, 근거 ID 목록} 배열 획득 (DQ-8=A)
```

### C39 `RefusalPolicy` — 1단 거부
```python
should_refuse(outcome: RetrievalOutcome) -> RefusalDecision
#   RefusalDecision: refuse(bool) + reason + fallback_links(list[Citation])
#   임계값은 C1 설정에서 주입 (NFR-7)
```

### C40 `GroundingVerifier` — 2단 거부
```python
verify(draft: AnswerDraft, evidences: list[Evidence]) -> VerificationResult
#   VerificationResult: supported_sentences, unsupported_sentences, verdict
#   verdict: accept | strip_unsupported | refuse_all
```

### C41 `CitationMapper`
```python
map(sentence: Sentence, evidences: list[Evidence]) -> list[Citation]
build_snippet(chunk_id: int, context_chars: int) -> Snippet
#   ExtractedText 오프셋 구간으로 역참조하여 스니펫 생성 (DQ-4=A)
```

### C42 `DisclaimerProvider`
```python
answer_disclaimer() -> str        # 모든 답변에 상시 부착 (FR-35)
consent_text() -> str             # 최초 진입 1회 동의용 (FR-34)
```

---

## 9. L2 — 관측 (u1/u2)

### C43 `UsageReporter`
```python
summarize(period: DateRange, group_by: Literal["day","model","endpoint"]) -> UsageSummary
#   호출 수, 토큰 합계, 지연 분포(P50/P95), 추정 비용 합계 (FR-42)
```

---

## 10. L2 — 평가 (u4)

### C44 `GoldenSetLoader`
```python
load(path: str) -> list[GoldenItem]
#   GoldenItem: question, expected_points, expected_evidence_refs, should_refuse(bool)
validate(items: list[GoldenItem]) -> list[ValidationError]
```

### C45 `RetrievalMetrics`
```python
compute(item: GoldenItem, outcome: RetrievalOutcome) -> RetrievalScore
#   recall_at_k, mrr, hit(bool)
```

### C46 `AnswerMetrics`
```python
compute(item: GoldenItem, result: QueryResult) -> AnswerScore
#   correctness, citation_precision, refusal_correct(bool)
#   citation_precision: C41 매핑을 골든셋 정답 근거와 대조 (NFR-5)
```

### C47 `LLMJudge`
```python
judge(question: str, answer: QueryResult, evidences: list[Evidence]) -> JudgeScore
#   faithfulness, relevance + 판정 근거 텍스트 (FR-38)
```

### C48 `EvaluationReporter`
```python
save_run(run: EvaluationRun) -> int
compare(run_id: int, baseline_id: int | None) -> ComparisonReport
check_regression(report: ComparisonReport, baseline: Thresholds) -> bool
#   False 반환 시 CI 실패 (NFR-26)
```

---

## 11. L2 — 물질 안전 카드 (u3)

### C49 `SynonymResolver`
```python
resolve(term: str) -> Substance | None
#   국문명·영문명·이명·CAS·UN 을 정규화 키로 조회 (FR-26)
normalize(term: str) -> str          # 표기 변형·대소문자·하이픈 정규화. 규칙은 Functional Design 이월
suggest(term: str, limit: int) -> list[Substance]     # 미일치 시 후보 제시
```

### C50 `SubstanceCardAssembler`
```python
assemble(substance_id: int) -> SubstanceCard
#   구조화 DB 직접 조회. LLM 미사용 (DQ-10=A)
#   SubstanceCard 항목: ghs_classification, signal_word, h_codes, p_codes,
#                        physical_properties, ppe, first_aid, storage_handling, applicable_laws
#   각 항목에 source_citation 부착. 데이터 부재 시 값은 None 이며 "정보 없음"으로 렌더 (NFR-8)
```

---

## 12. L2 — 계정·문서 (u5)

### C51 `PasswordHasher`
```python
hash(plain: str) -> str
verify(plain: str, hashed: str) -> bool
validate_policy(plain: str) -> list[PolicyViolation]
```

### C52 `TokenService`
```python
issue(user_id: int) -> Token          # 만료 시간 포함 (NFR-12)
verify(token: str) -> TokenClaims     # 실패 시 예외
```

### C53 `UploadValidator`
```python
validate(file: UploadFile) -> ValidationResult
#   확장자·MIME·최대 크기·최대 페이지 수 (FR-30)
```

### C54 `UploadStore`
```python
save(file: UploadFile, owner_id: int) -> StoredFile
#   웹 루트 외부에 생성 식별자 이름으로 저장 (NFR-13)
delete(stored_id: str) -> None
open(stored_id: str) -> BinaryIO
```

### C55 `OwnershipFilter`
```python
scope_for(user_id: int | None) -> Scope
#   공개 코퍼스 + 본인 업로드 문서. C35 검색의 필수 입력 (FR-28, NFR-15)
assert_owner(document_id: int, user_id: int) -> None   # 위반 시 예외
```

---

## 13. L4 — 진입점

### C56 `WebRouters`
```python
# 검증·직렬화·인증 확인만 수행하고 서비스에 위임 (DQ-12=A)
POST /api/query                  -> S3.answer()
GET  /api/substances/{term}      -> S4.get_card()
POST /api/documents              -> S7.upload()
GET  /api/documents              -> S7.list()
DELETE /api/documents/{id}       -> S7.delete()
POST /api/auth/register|login    -> S6.register() | S6.login()
GET  /api/jobs/{id}              -> S1.job_status()
GET  /api/usage                  -> S8.summary()
GET  /api/evaluations            -> S5.list_runs()
GET  /healthz                    -> C58.check()
# HTML 라우트: /, /substances, /documents, /history, /admin
```

### C57 `TemplateRenderer`
```python
render(template: str, **ctx) -> HTML
#   인용 스니펫은 서버에서 이미 렌더하고 JS 로 토글만 수행.
#   JS 미동작 시에도 원문 링크로 열람 가능 (DQ-17=A)
```

### C58 `HealthCheck`
```python
check() -> HealthReport    # app / db / worker / queue 개별 상태 (FR-43)
```

### C59 `WorkerEntrypoint`
```python
run() -> None              # 큐 소비 루프. C29 에 등록된 핸들러 실행
```

### C60 `CliEntrypoint`
```python
ingest(source_id: str, since: str | None) -> None     # 수집 실행       (u1)
reindex(scope: str) -> None                            # 재색인          (u1)
evaluate(golden_set: str, baseline: str | None) -> int # 평가. 회귀 시 비0 종료코드 (u4, NFR-26)
```

---

## 14. 메서드 설계 규칙

1. **포트 메서드는 예외를 표준 예외 타입으로 정규화**한다 — 어댑터 고유 예외가 상위로 새지 않는다
2. **검색·생성 컴포넌트는 DB 세션을 받지 않는다** — 리포지터리(C4)를 통해서만 접근하여
   인메모리 스텁으로 테스트 가능하게 한다 (NFR-24, NFR-28)
3. **`Scope`는 검색 계열 메서드의 필수 인자**다 — 소유자 필터 누락이 호출 시점에 드러난다 (NFR-15)
4. **순수 컴포넌트**(C16 `RetryPolicy`, C33 `FusionRanker`, C39 `RefusalPolicy`, C49 정규화)는
   I/O를 갖지 않아 속성 기반 테스트 대상이 된다 (NFR-27)
5. **LLM 호출은 반드시 `LLMResult`를 함께 반환**한다 — 추적 데코레이터(C13)가 기록할 정보의 출처
