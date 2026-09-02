# Traceability — u2-rag-qa

**작성일**: 2026-08-25
**범위**: FR 14건 / BR 36건 / SP·PP·CP 18건 / 엔터티 E14~E18 / 컴포넌트 C30~C43 + N1~N6

---

## 1. FR → 구현

| FR | 내용 | 구현 | 테스트 |
|---|---|---|---|
| FR-14 | 질의 접수 | `web/routers/query.py`, `pages.py` | 실측 |
| FR-15 | 하이브리드 검색 | `rag/retrieval/{retrievers,fusion}.py` | `test_fusion` 9 |
| FR-16 | 리랭킹 | `rag/retrieval/rerank_client.py`, `rerank_service.py` | ⬜ 이월 |
| FR-17 | 엔티티 추출 | `rag/entities.py` | 부분 |
| FR-18 | 근거 기반 생성 | `rag/generator.py` | `test_generation…` 16 |
| FR-19 | 문장 단위 인용 | `rag/citations.py`, `db/repositories/queries.py` | 부분 |
| FR-20 | 1단 거부 | `rag/refusal.py` | `test_retrieval_regressions` 8 |
| FR-21 | 2단 검증 | `rag/verifier.py` | `test_generation…` 6 |
| FR-22 | 무상태 | `services/query_service.py` — 세션 개념 없음 | 구조 |
| FR-34·35 | 면책 문구 | `templates/query.html` | 실측(렌더 확인) |
| FR-41 | 호출 추적 | `db/repositories/traces.py`, `adapters/tracing.py` | ⬜ 이월 |
| FR-42 | 사용량 조회 | `services/observability_service.py`, `routers/usage.py` | 실측 |
| FR-44 | 질의 화면 | `templates/query.html`, `static/query.js` | 실측 |

---

## 2. BR → 구현

### 질의 해석 (BR-63~66)

| BR | 구현 |
|---|---|
| BR-63 색인과 동일 정규화 | `query_service.retrieve` → u1 `normalize()` |
| BR-64 규칙 해석 시 LLM 미호출 | `entities.extract` → `QueryIntent.resolved_by_rules` |
| BR-65 동의어 해석, 미해석은 원문 유지 | `entities._match_synonyms` |
| BR-66 유형 힌트는 가중치, 필터 아님 | `Retrievers.meta_filter` — 힌트를 넣지 않는다 |

### 검색 (BR-67~72)

| BR | 구현 | 비고 |
|---|---|---|
| BR-67 30/20/5 | `config.py` `keyword_top_k`·`fusion_top_k`·`final_top_k` | |
| BR-68 RRF k=60 | `fusion.reciprocal_rank_fusion` | `test_fusion` |
| BR-69 문서유형 최소 할당 | `fusion.ensure_doc_type_spread` | `test_fusion` 5 |
| BR-70 리랭커 기본 OFF·별도 컨테이너 | `RERANKER_ENABLED=false`, compose `profiles` | |
| BR-71 리랭커 실패 → 융합 순위 | `rerank_client.rerank` | ⬜ 이월 |
| **BR-72** 한쪽 실패 허용 | `Retrievers._isolated` — **세이브포인트** | **결함 26** |

> **BR-72 는 처음에 실현 불가능하게 구현되었다.** 두 검색이 Session 을 공유하므로
> 한쪽의 SQL 오류가 트랜잭션을 중단시키면 다른 쪽도 반드시 실패한다. try/except 는
> 올바르게 보였고, 실환경 첫 질의에서만 드러났다.

### 거부 (BR-73~78)

| BR | 구현 | 비고 |
|---|---|---|
| **BR-73** 1단 거부 | `refusal.decide` | **결함 27 — RRF → 코사인 유사도** |
| BR-74 임계값 설정화 | `REFUSAL_SCORE_THRESHOLD=0.50` | u4 캘리브레이션 대기 |
| BR-75 원문 링크 필수 | `refusal.source_links` — 문서 단위 중복 제거 | 실측 |
| BR-76 2단 거부 | `query_service.answer` | |
| BR-77 `provider_refusal` | `llm_anthropic.ProviderRefusal` | `test_generation…` |
| BR-78 거부는 실패 아님 | `QueryRepo.refuse` — 오류 지표에 넣지 않음 | |

### 답변 생성 (BR-79~84)

| BR | 구현 | 테스트 |
|---|---|---|
| BR-79 구조화 출력 강제 | `GeneratedAnswer.json_schema` | |
| BR-80 모든 문장 인용 필수 | `generator._apply_whitelist` | 2건 |
| BR-81 ID 화이트리스트 | 동상 | 3건 |
| BR-82 근거만으로 생성 | `prompts/answer/1.0.0.md` | |
| BR-83 네이티브 citations 미사용 | `llm_anthropic` — 사용하지 않음 | |
| BR-84 면책 문구 항상 | `query.html` — 거부에도 표시 | 실측 |

### 근거 검증 (BR-85~88)

| BR | 구현 | 테스트 |
|---|---|---|
| BR-85 자신의 근거만으로 판정 | `verifier.verify_one` | 1건 |
| BR-86 병렬 호출 | `verifier.verify_all` | |
| **BR-86a** 호출 수 배수 명시 | `E18.purpose` 분리 집계, P6 용도별 분해 | ⬜ 실측 이월 |
| BR-87 실패 → `unverified` → 제거 | `verifier.verify_one` | 2건 |
| BR-88 제거 사실 표시 | `query.html` FE-18, `removed` 행 저장 | |

### 인용 표시 (BR-89~92a)

| BR | 구현 | 비고 |
|---|---|---|
| BR-89 스니펫 = 오프셋 구간 | `citations.resolve_evidence` | BR-30 전제 |
| BR-90 라벨 없으면 "섹션 정보 없음" | `citations.display_label` | |
| BR-91 원문 링크 필수 | `CitationDraft.source_url` NOT NULL | |
| BR-92 답변 확정 시 동결 | `QueryRepo.finalise` — **단일 트랜잭션** | |
| **BR-92a** 표시는 스냅샷만 | `citations_for_answer` — `chunk` 미조인 | |

### 프롬프트·추적 (BR-93~96)

| BR | 구현 |
|---|---|
| BR-93 파일 기반 버전 관리 | `prompts/index.yaml` + `rag/prompts.py` |
| BR-94 캐시 접두사 배치 | `llm_anthropic._system_blocks` — `cache_control` |
| BR-95 실패 호출도 기록 | `LlmCallRepo.record` |
| BR-96 미등록 단가는 NULL | `rag/pricing.py`, `UsageSummary.unpriced_calls` |

---

## 3. NFR 패턴 → 구현

| 패턴 | 구현 | 검증 |
|---|---|---|
| SP-1 역할 분리 | `PromptAssembler.for_answer` | `test_prompt_assembly` 2 |
| SP-2 XML 구획·속성 | 동상 | 1 |
| **SP-3 이스케이프 + nonce** | `sanitize.py`, `assembler._nonce` | **9** |
| SP-4 색인 시점 탐지 | `processing/injection_scan.py` | 8 |
| **SP-5 탐지해도 제외 안 함** | `runner._flag_suspected_injection` | **12** (오탐 방지 10) |
| **SP-6 검증자 최소 권한** | `for_verification` 시그니처 | **2** |
| SP-7 질의문도 비신뢰 | `clip_question`, `QueryRequest._validate` | 3 |
| SP-8 출력 ID 검증 | `generator._apply_whitelist` | 3 |
| SP-9 입력 검증 | `QueryRequest`, SQLAlchemy 바인딩 | |
| PP-1 지연 예산 | `config` top_k 값 | 실측 웜 339ms |
| PP-2 리랭커 격리·타임아웃 | `rerank_client`, compose | ⬜ 이월 |
| PP-3 질의 임베딩 캐시 | `QueryEmbeddingCache` | |
| PP-4 캐시 접두사 | `_system_blocks`, `cache_hit_ratio` | ⬜ 이월 |
| PP-5 검증 동시성 상한 | `verifier.verify_all` | 2 |
| PP-6 첫 토큰 스트리밍 | `rag/streaming.py`, `query.js` | 25 |
| CP-1 단가표 외부화 | `config/llm_pricing.yaml`, `rag/pricing.py` | |
| CP-2 프롬프트 저장소 | `prompts/`, `rag/prompts.py` | 1 |
| CP-3 LLM 포트 추상화 | `LLMPort`, `llm_factory`, 어댑터 2종 | **전환 실증** — `rag/` 무변경 |
| BR-79 제공자 독립 강제 | `rag/schema_guard.py` | 23건 |

---

## 4. 엔터티 → 테이블

| 엔터티 | 테이블 | 마이그레이션 | 실측 |
|---|---|---|---|
| E14 `query_log` | ✅ | `0002_query` | ✅ |
| E15 `answer_sentence` | ✅ | 동상 | ✅ |
| E16 `answer_citation` | ✅ (**chunk_id SET NULL**) | 동상 | ✅ |
| E17 `citation_snapshot` | ✅ | 동상 | ✅ |
| E18 `llm_call` | ✅ | 동상 | ✅ |

`alembic_version = 0002_query`, 테이블 19개 확인 (2026-08-25).

---

## 5. 컴포넌트 → 파일

| ID | 컴포넌트 | 파일 |
|---|---|---|
| C30 | EntityExtractor | `rag/entities.py` |
| C31·C32 | Keyword/Vector Retriever | `rag/retrieval/retrievers.py` |
| C33 | Fusion | `rag/retrieval/fusion.py` |
| C34 | Reranker | `rag/retrieval/rerank_client.py` + `rerank_service.py` |
| C36·C37 | Prompt template / Context | `rag/prompts.py`, `rag/assembler.py` |
| C38 | AnswerGenerator | `rag/generator.py` |
| C39 | RefusalGate | `rag/refusal.py` |
| C40 | SupportVerifier | `rag/verifier.py` |
| C41 | CitationResolver | `rag/citations.py` |
| C13·C43 | TracedLLM / Usage | `adapters/tracing.py`, `db/repositories/traces.py` |
| N1~N6 | (NFR Design) | `assembler` `sanitize` `injection_scan` `prompts` `pricing` `tracing` |
| S3·S8 | QueryService / ObservabilityService | `services/` |

---

## 6. 미매핑 점검

| 검사 | 결과 |
|---|---|
| FR 미구현 | **0** (FR-16 은 코드 완료·검증 이월) |
| BR 미구현 | **0** |
| SP·PP·CP 미구현 | **0** |
| 엔터티 미생성 | **0** |
| u1 규칙 위반 | **0** — BR-54 재색인 경로 무변경 확인 |
| 순환 의존 | **0** — `rag` → `db`·`core`, 역방향 없음 |
| 후행 유닛 역방향 의존 | **0** — u3~u5 참조 없음 |

---

## 7. 검증 이월 (Build & Test)

| 항목 | 필요 조건 |
|---|---|
| FR-18·19·21 종단 | **`GEMINI_API_KEY`** (무료 티어) |
| NFR-1 첫 토큰 P95 | 동상 |
| BR-86a 호출 수 배수 | 동상 |
| PP-4 캐시 적중률 | 동상 |
| BR-71·PP-2 리랭커 폴백 | `--profile reranker` 기동 |
| BR-92 롤백 | 저장 실패 주입 |
| SP-4·5 전 코퍼스 | 재색인 1회 (기존 청크에 플래그 없음) |
| NFR-5·6 수치 | u4 골든셋 |

> **u2 Build & Test DoD 보강**: u1 의 "Docker 기동 실측"은 기동만 검증했고, 그래서
> 결함 25~27 이 u2 까지 살아남았다. **실질의 종단 실행**을 명시 항목으로 둔다.
