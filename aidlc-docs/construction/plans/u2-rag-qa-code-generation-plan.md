# Code Generation Plan — u2-rag-qa

**프로젝트**: safeenv
**단계**: 🟢 CONSTRUCTION / Code Generation — 유닛 `u2-rag-qa` (2/5)
**작성일**: 2026-08-25
**선행 승인**: Functional Design (2026-08-25, 지적 3건 반영) · NFR Design (2026-08-25)
**상태**: **완료 2026-08-25** — 산출물은 `construction/u2-rag-qa/code/` 3종

---

## 유닛 컨텍스트

| 항목 | 내용 |
|---|---|
| **워크스페이스 루트** | `c:\Users\403\IDE\safeenv` |
| **애플리케이션 코드** | `safeenv/app/` — **`aidlc-docs/` 아래에 코드를 두지 않는다** |
| **프로젝트 유형** | Greenfield (u1 코드 위에 증분) |
| **FR** | FR-14~22, FR-34, FR-35, FR-41, FR-42, FR-44 (14건) |
| **BR** | BR-63 ~ BR-96, BR-86a, BR-92a (36건) |
| **패턴** | SP-1~9 / PP-1~6 / CP-1~3 |
| **엔터티** | E14~E18 (리비전 `0002_query`), 값객체 V1~V4, Enum 5종 |
| **컴포넌트** | C30~C43 + N1~N6 |

### u1 에 대한 변경 (최소화 확인)

| 대상 | 변경 | 근거 |
|---|---|---|
| `app/processing/runner.py` (또는 청킹 호출부) | `InjectionScanner` 호출 삽입 | N3, SP-4 |
| `app/adapters/llm_anthropic.py` | `NotImplementedError` → 실제 구현 | u1 이 남긴 확장점 |
| `app/core/config.py` | 환경변수 12종 추가 | NFR-23 |
| `docker-compose.yml` | `reranker` 서비스, `app` 에 `safeenv_models` 마운트 | §1 인프라 |
| `ChunkRepo.replace_for_document` | **변경 없음** | E16 SET NULL 정정으로 불필요해짐 |

---

## 실행 계획

### 1. 인프라·설정 (선행)
- [x] 1.1 `app/core/config.py` — 환경변수 12종 + 검증기
- [x] 1.2 `.env.example` 갱신
- [x] 1.3 `config/llm_pricing.yaml` 신규 (CP-1)
- [x] 1.4 `docker-compose.yml` — `reranker` 서비스 추가, `app` 에 `safeenv_models` 마운트
- [x] 1.5 `prompts/` 디렉터리 + `index.yaml` + 3종 프롬프트 (CP-2, BR-93)

### 2. 데이터 계층
- [x] 2.1 `app/db/models.py` — `QueryLogRow`, `AnswerSentenceRow`, `AnswerCitationRow`,
      `CitationSnapshotRow`, `LlmCallRow` (E14~E18)
- [x] 2.2 `migrations/versions/0002_query.py` — 테이블 5, 인덱스 5
- [x] 2.3 `app/db/repositories/queries.py` — `QueryRepo` (확정 저장 단일 트랜잭션, BR-92)
- [x] 2.4 `app/db/repositories/traces.py` — `LlmCallRepo` (u1 인메모리 `TraceRepo` 승격)
- [ ] 2.5 단위 테스트 — 저장 트랜잭션 원자성, SET NULL 동작 → **DB 필요, Build and Test 로 이월**

### 3. 도메인 타입
- [x] 3.1 `app/core/types.py` — Enum 5종 (`RetrievalMode`, `AnswerOutcome`,
      `RefusalReason`, `SupportVerdict`, `LlmPurpose`)
- [x] 3.2 `app/rag/types.py` — 값객체 V1~V4 (`QueryIntent`, `Candidate`, `Evidence`,
      `GeneratedAnswer`)

### 4. 검색 계층 (W7)
- [x] 4.1 `app/rag/entities.py` — C30 `EntityExtractor` (BR-64~66)
- [x] 4.2 C31 키워드 → **`retrievers.py` 로 통합** (조정 1)
- [x] 4.3 C32 벡터 + 질의 임베딩 LRU (PP-3) → **`retrievers.py` 로 통합** (조정 1)
- [x] 4.4 `app/rag/retrieval/fusion.py` — C33 RRF + 문서유형 최소 할당 (BR-68, BR-69)
- [x] 4.5 `app/rag/retrieval/rerank_client.py` — C34 HTTP 클라이언트 (PP-2, BR-70·71)
- [x] 4.6 `app/rerank_service.py` — reranker 컨테이너 진입점
- [x] 4.7 단위 테스트 — RRF 순위·유형 할당 9건 / 키워드 tsquery·거부 18건
- [ ] 4.7a **BR-72 폴백·리랭커 타임아웃 폴백** → DB·컨테이너 필요, Build and Test 로 이월
      *(BR-72 는 실환경에서 결함 26 으로 드러났다 — 모킹으로는 잡히지 않는 종류다)*

### 5. 프롬프트 조립 (SP-1~3, SP-7)
- [x] 5.1 `app/rag/prompts.py` — N4 `PromptRepository` (BR-93)
- [x] 5.2 `app/rag/sanitize.py` — N2 `EvidenceSanitizer` (**사본만 변형**)
- [x] 5.3 `app/rag/assembler.py` — N1 `PromptAssembler` (nonce 구획)
- [x] 5.4 단위 테스트 — **구분자 위조 탈출 실패**, 원문 불변, 질의문 상한

### 6. 생성·검증 (W8)
- [x] 6.1 `app/adapters/llm_anthropic.py` — 실제 구현 (`messages.parse`, 재시도, `refusal`)
- [x] 6.2 `app/adapters/tracing.py` — `TracedLlm` 추가 (N6, BR-95)
- [x] 6.3 `app/rag/refusal.py` — C39 1단 거부 (BR-73~75)
- [x] 6.4 `app/rag/generator.py` — C38 (BR-79~83) + SP-8 화이트리스트
- [x] 6.5 `app/rag/verifier.py` — C40 2단 검증, 동시성 4 (SP-6, PP-5, BR-85~87)
- [x] 6.6 단위 테스트 — 화이트리스트 제거, `unverified` 처리, 동시성 상한

### 7. 인용 표시 (W9)
- [x] 7.1 `app/rag/citations.py` — C41 스니펫·라벨 (BR-89~91)
- [x] 7.2 동결 로직 — E17 (BR-92, 확정 트랜잭션 내)
- [ ] 7.3 단위 테스트 — `section_code` NULL 처리, 표시가 `chunk` 미조인(BR-92a) → **DB 필요, 이월**

### 8. 서비스 계층
- [x] 8.1 `app/services/query_service.py` — S3 (W7·W8·W9 오케스트레이션)
- [x] 8.2 `app/services/observability_service.py` — S8 (W10·W11)
- [ ] 8.3 단위 테스트 — 거부 경로, `answered_partial`, 저장 실패 롤백 → **DB 필요, 이월**
      *(거부 판정 로직 자체는 `test_retrieval_regressions.py` 8건으로 커버)*

### 9. 인젝션 스캐너 (u1 경로)
- [x] 9.1 `app/processing/injection_scan.py` — N3 (SP-4)
- [x] 9.2 청킹 경로에 삽입
- [x] 9.3 단위 테스트 — **MSDS 응급조치 문장이 제외되지 않는지**(SP-5 오탐 방지)

### 10. 웹 계층
- [x] 10.1 `app/web/routers/query.py` — `POST /api/query` (SSE), `GET /api/query/{id}`,
      `GET /api/citations/{id}/snippet`
- [x] 10.2 `app/web/routers/usage.py` — `GET /api/usage`
- [x] 10.3 `app/web/templates/query.html` — P5 (FE-14~19)
- [x] 10.4 `app/web/templates/usage.html` — P6 (FE-20~23)
- [x] 10.5 SP-9 입력 검증
- [ ] 10.6 단위 테스트 — SSE 이벤트 순서, `final`/`refused` 배타성 → **이월**
      *(스트림 파서 자체는 `test_streaming.py` 25건으로 커버)*

### 11. 문서
- [x] 11.1 `construction/u2-rag-qa/code/code-summary.md`
- [x] 11.2 `construction/u2-rag-qa/code/api-endpoints.md`
- [x] 11.3 `construction/u2-rag-qa/code/traceability.md`
- [x] 11.4 `README.md` 갱신

---

## 코드 배치 규칙

```
app/
  rag/                    ← u2 신규 패키지
    types.py  entities.py  prompts.py  sanitize.py  assembler.py
    refusal.py  generator.py  verifier.py  citations.py
    retrieval/  keyword.py  vector.py  fusion.py  rerank_client.py
  services/  query_service.py  observability_service.py
  db/repositories/  queries.py  traces.py
  web/routers/  query.py  usage.py
  rerank_service.py       ← reranker 컨테이너 진입점
prompts/                  ← 코드 아님. 버전 관리 대상 (BR-93)
config/llm_pricing.yaml
```

> **유닛은 개발 순서 개념이며 디렉터리 경계가 아닙니다**(UD-4). `app/rag/` 는 유닛
> 경계가 아니라 **책임 경계**입니다 — 검색·생성·인용은 u3~u5 에서도 쓰입니다.

## DoD (UD-7)

- [x] 코드 + 단위 테스트 (통합 테스트는 Build and Test)
- [ ] **Docker 기동 실측** (`reranker` ON/OFF 양쪽)
- [x] README 갱신
- [ ] Quality Gate 통과
- [ ] 평가 회귀 없음 → **u4 이월** (골든셋 미존재)
- [ ] **실질의 종단 실행** — u1 DoD 의 "Docker 기동 실측"이 기동만 검증해 결함 25~27 이 u2 까지 살아남았다. 명시 항목으로 추가한다


---

## 완료 시점 정정 (2026-08-25)

체크박스를 일괄 표시하면서 **작성하지 않은 테스트가 완료로 표시**되었고, 위에서
되돌렸다. 미완 항목은 전부 **실제 DB 나 컨테이너가 필요한 테스트**이며 Build and Test
로 이월한다.

작성한 u2 테스트는 **111건**이고 전부 순수 로직이다 — 프롬프트 조립 20, 인젝션 스캔 23,
스트림 파서 25, 생성·검증 16, 검색 회귀 18, 융합 9.

이 구분이 중요한 이유는 결함 25~27 이 정확히 그 경계에서 나왔기 때문이다. 세 결함 모두
순수 로직 테스트를 통과했고, DB 를 실제로 때리는 순간 드러났다.
