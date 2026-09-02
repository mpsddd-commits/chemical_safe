# Code Generation Plan — u1-ingestion-index

**프로젝트**: safeenv
**단계**: 🟢 CONSTRUCTION / Code Generation — **Part 1 (Planning)**
**작성일**: 2026-08-20
**상태**: Part 1 승인 완료 + Part 2 생성 완료 (2026-08-20)

> **이 문서는 Code Generation 의 단일 진실 공급원(single source of truth)입니다.**
> Part 2 생성 단계는 아래 Step 1~18 을 순서대로만 실행하며, 계획에 없는 것을 만들지 않습니다.

---

## 1. 유닛 컨텍스트

| 항목 | 내용 |
|---|---|
| **유닛** | `u1-ingestion-index` (1/5) |
| **워크스페이스 루트** | `c:\Users\403\IDE\safeenv` — 애플리케이션 코드는 여기에만 생성 |
| **문서 경로** | `aidlc-docs/construction/u1-ingestion-index/code/` (마크다운만) |
| **프로젝트 유형** | Greenfield / 단일 배포 단위 모놀리스 (UD-3) |
| **구조 패턴** | 단일 `app/` 패키지. **유닛명 디렉터리를 만들지 않음** (UD-4) |
| **구현 FR** | FR-1~13, FR-40, FR-43, FR-48 — **16건** |
| **구현 컴포넌트** | C1~C29, C56~C60 — **32종** |
| **구현 서비스** | S1 `IngestionService`, S2 `IndexingService` |
| **의존 유닛** | **없음** (기반 유닛) |
| **엔터티 소유** | E1~E12 — 12종 전부 |
| **설계 근거** | `functional-design/` 4종 (BR-01~BR-62) + `infrastructure-design/` 2종 (ID-1~ID-17) |

### 이 유닛이 노출하는 인터페이스 (후행 유닛이 사용)

| 인터페이스 | 사용 유닛 | 선반영 여부 |
|---|---|---|
| `C25 VectorIndex.search(vector, top_k, filters, scope)` | u2 | `scope` 필수 인자 포함 |
| `C26 KeywordIndex.search(query, top_k, filters, scope)` | u2 | `scope` 필수 인자 포함 |
| `C4 Repositories` 8종 | u2~u5 | 전체 |
| `C6/C7/C8` 포트 + `C13` 추적 데코레이터 | u2 | 포트 정의만, LLM 구현은 u2 |
| `C23 PipelineRunner` | u5 | 업로드 문서 처리 재사용 |
| `chunk.owner_id`, `substance_synonym` | u5, u3 | 스키마 선반영 |

---

## 2. 생성 대상 디렉터리 구조

```
c:\Users\403\IDE\safeenv\
├── app/
│   ├── core/            config.py  logging.py  errors.py  types.py
│   ├── db/              engine.py  models.py  repositories/*.py
│   ├── ports/           source.py  llm.py  embedding.py  reranker.py
│   ├── adapters/        sources/*.py  embedding_local.py  reranker_local.py
│   │                    llm_anthropic.py  tracing.py
│   ├── jobs/            tracker.py  queue.py  tasks.py
│   ├── ingestion/       policy.py  change_detector.py  retry.py  orchestrator.py
│   ├── processing/      stages/*.py  runner.py  chunker.py  structure/*.py
│   ├── indexing/        embedder.py  vector_index.py  keyword_index.py  reindexer.py
│   ├── services/        ingestion_service.py  indexing_service.py
│   ├── web/             routers/*.py  templates/*.html  static/*
│   ├── main.py          worker.py   cli.py
├── config/              sources.yaml
├── migrations/          alembic.ini  versions/0001_base.py
├── tests/               unit/*  fixtures/*
├── scripts/             backup.sh  restore.sh
├── data/originals/      (런타임 생성)
├── logs/                (런타임 생성)
├── Dockerfile  docker-compose.yml  .dockerignore  .gitignore
├── .env.example  pyproject.toml  README.md
```

**⚠️ 애플리케이션 코드는 `aidlc-docs/` 안에 절대 생성하지 않습니다.**

---

## 3. 생성 단계 (Step 1 ~ Step 18)

### Step 1 — 프로젝트 구조 및 빌드 설정
- [x] 디렉터리 골격 생성 (§2 구조)
- [x] `pyproject.toml` — 의존성 선언, 도구 설정
- [x] `.gitignore` / `.dockerignore` — `.env`, `data/`, `logs/`, 모델 캐시 제외 (NFR-14)
- [x] `.env.example` — 환경변수 23종, **값은 비움** (ID-7 §7)
- [x] 패키지 마커 파일

**대상 FR/NFR**: NFR-14, NFR-23

---

### Step 2 — `app/core` : 설정 · 로깅 · 예외 · 공통 타입
- [x] `config.py` — C1 `Config`. 환경변수 23종 로드·검증, 기동 시 필수값 누락이면 명확한 오류
- [x] `logging.py` — C2 `Logger`. 구조적 JSON, `request_id`/`job_id` 상관관계, **비밀값 마스킹** (BR-57~60)
- [x] `errors.py` — 예외 계층 + `FailureKind` 분류 매핑 (BR-42, BR-43)
- [x] `types.py` — `SourceRef`, `RawDocument`, `ExtractedText`, `StructuredDoc`, `Chunk`, `ChunkMeta`, `Scope` 등

**대상 FR**: FR-40 | **BR**: BR-57~60 | **컴포넌트**: C1, C2

---

### Step 3 — `app/db` : 엔진 · ORM 모델
- [x] `engine.py` — C3 `Database`. 세션·트랜잭션 경계, pgvector 확장 확인
- [x] `models.py` — 엔터티 **E1~E12** 및 **Enum 11종** (`domain-entities.md` §2, §3)
- [x] 인덱스 정의 8종 (`domain-entities.md` §7)
- [x] **u3·u5 선반영 컬럼 포함** — `chunk.owner_id`, `document.owner_id`, `substance_synonym`

**대상 FR**: FR-10~12 | **컴포넌트**: C3

---

### Step 4 — `app/db/repositories` : 리포지터리 8종
- [x] `SubstanceRepo` / `DocumentRepo` / `ChunkRepo` / `JobRepo` / `UserRepo`(스텁) / `QueryLogRepo`(스텁) / `EvaluationRepo`(스텁) / `TraceRepo`
- [x] **도메인 컴포넌트가 세션을 직접 받지 않도록** 리포지터리 경유 접근 강제 (DD-20)

**컴포넌트**: C4
**참고**: `UserRepo`, `QueryLogRepo`, `EvaluationRepo` 는 u2·u4·u5 용 **스텁만** 생성 (테이블은 후행 리비전)

---

### Step 5 — 데이터베이스 마이그레이션
- [x] `migrations/alembic.ini` + `env.py`
- [x] `versions/0001_base.py` — E1~E12 테이블, Enum, 인덱스, pgvector 확장
- [x] `db/init/01-extensions.sql` — `CREATE EXTENSION IF NOT EXISTS vector;`

**근거**: UD-6 (u1 리비전에 재색인 유발 요소 선반영), ID-10

---

### Step 6 — `app/ports` : 추상 인터페이스 4종
- [x] `source.py` — C5 `SourceAdapter` Protocol
- [x] `llm.py` — C6 `LLMPort` Protocol (**u2 용 정의만**)
- [x] `embedding.py` — C7 `EmbeddingPort` Protocol
- [x] `reranker.py` — C8 `RerankerPort` Protocol (**u2 용 정의만**)

**NFR**: NFR-21 | **컴포넌트**: C5~C8

---

### Step 7 — `app/adapters/sources` : 소스 어댑터 4종
- [x] `substance_api.py` — FR-1 물질 기본정보·GHS
- [x] `law_api.py` — FR-2 법령 조문
- [x] `incident_data.py` — FR-3 화학사고 사례
- [x] `msds_pdf.py` — FR-4 MSDS PDF
- [x] `config/sources.yaml` — 소스 정의 (엔드포인트·파라미터·인증키 환경변수명)

**대상 FR**: FR-1~4 | **BR**: BR-02 | **컴포넌트**: C9
**⚠️ 위험 R-1**: 공공 API 실제 스펙 미확인. 어댑터를 **설정 주도**로 작성하고
`tests/fixtures/` 의 샘플 응답으로 오프라인 개발이 가능하도록 합니다.

---

### Step 8 — `app/adapters` : 모델 어댑터 · 추적 데코레이터
- [x] `embedding_local.py` — C11. 로컬 임베딩, 배치 32, 모델 캐시 디렉터리 (BR-61)
- [x] `reranker_local.py` — C12 **인터페이스 구현만** (실제 사용은 u2)
- [x] `llm_anthropic.py` — C10 **스텁만** (실제 사용은 u2)
- [x] `tracing.py` — C13 `TracingLLMDecorator`. 포트 3종을 감싸 자동 계측 (DD-16)

**NFR**: NFR-20, NFR-21 | **컴포넌트**: C10~C13

---

### Step 9 — `app/jobs` : 작업 추적 · 큐
- [x] `tracker.py` — C28 `JobTracker`. 진행률·부분 실패·재개 지점 (BR-46~51)
- [x] `queue.py` — C29 `TaskQueue`. **상태 미보유**, 등록·소비만 (DD-13)
- [x] `tasks.py` — 워커 핸들러 등록

**대상 FR**: FR-6, FR-8 | **BR**: BR-46~51 | **컴포넌트**: C28, C29

---

### Step 10 — `app/ingestion` : 수집
- [x] `policy.py` — C14 `AccessPolicyChecker`. robots·약관 검사, **우회 경로 없음** (BR-03~05)
- [x] `change_detector.py` — C15. 해시 우선, 발행일 대체 (BR-09, BR-10)
- [x] `retry.py` — C16 `RetryPolicy`. **순수 컴포넌트** — 3회 / 1s·4s·16s / 3분류 (BR-41~43)
- [x] `orchestrator.py` — C17. 정책→대상→변경감지→수집→기록 (BR-01~08)

**대상 FR**: FR-1~8 | **BR**: BR-01~13, BR-40~45 | **컴포넌트**: C14~C17

---

### Step 11 — `app/processing` : 문서 처리 파이프라인
- [x] `stages/fetch.py` — C18. 원본 보관 (BR-12)
- [x] `stages/extract.py` — C19. PDF 텍스트 추출, **오프셋 보존**
- [x] `stages/normalize.py` — C20. 5종 정규화 (BR-14)
- [x] `structure/msds.py` — MSDS 16섹션, 8개 미만이면 `unstructured` (BR-15~20)
- [x] `structure/law.py` — 조 단위 분해, 항·호 내부 보존, 부칙·별표 (BR-21~23)
- [x] `structure/incident.py` — 사고사례 필드 매핑 (BR-25)
- [x] `stages/structure.py` — C21. 유형별 분기, **실패해도 진행** (BR-24)
- [x] `chunker.py` + `stages/chunk.py` — C22. 섹션=청크, 1000토큰 상한, 중첩 0, 20토큰 병합 (BR-26~31)
- [x] `runner.py` — C23 `PipelineRunner`. 단계 체인, 재개 지점 (BR-44)

**대상 FR**: FR-4, FR-9, FR-10 | **BR**: BR-14~31 | **컴포넌트**: C18~C23

---

### Step 12 — `app/indexing` : 색인
- [x] `embedder.py` — C24. 배치 32, 텍스트 해시 캐시 (BR-61, BR-62)
- [x] `vector_index.py` — C25. pgvector 적재·조회, **`scope` 필수 인자** (DD-19)
- [x] `keyword_index.py` — C26. 전문검색 + **CAS·UN·물질명 정확 매칭** (BR-38)
- [x] `reindexer.py` — C27. 멱등 재색인, 모델 교체 시 병행 적재 (BR-54, BR-55)

**대상 FR**: FR-11~13 | **BR**: BR-38, BR-54, BR-55, BR-61, BR-62 | **컴포넌트**: C24~C27

---

### Step 13 — `app/services` : 서비스 계층
- [x] `ingestion_service.py` — S1. W1 워크플로, 큐 위임 후 즉시 `job_id` 반환 (BR-47)
- [x] `indexing_service.py` — S2. W2·W3 워크플로, **문서 1건 = 1 트랜잭션** (DD-24, BR-53)

**서비스**: S1, S2 | **워크플로**: W1~W4

---

### Step 14 — `app/web` : 라우터 · 템플릿 · 정적 파일
- [x] `routers/admin.py` — 소스·작업·작업상세 HTML 라우트
- [x] `routers/api.py` — `/api/sources`, `/api/jobs`, `/api/stats` 등 JSON
- [x] `routers/health.py` — C58 `HealthCheck`. app/db/queue/worker 4항목 (FR-43, BR-52)
- [x] `templates/` — `base.html`, `dashboard.html`, `sources.html`, `jobs.html`, `job_detail.html`, 부분 템플릿
- [x] `static/style.css` + 최소 `app.js` (자동 새로고침 토글, **JS 없이도 동작**)
- [x] **`data-testid` 속성 부여** — `{component}-{element-role}` 규칙
- [x] **"인증 없음 — 로컬 전용" 경고 배너** (ID-13)

**대상 FR**: FR-43, FR-48 | **컴포넌트**: C56~C58 | **참고**: `frontend-components.md` 전체

---

### Step 15 — 진입점
- [x] `app/main.py` — ASGI 앱 조립, 라우터 등록, 의존성 주입
- [x] `app/worker.py` — C59. 큐 소비 루프 + 하트비트 (BR-52)
- [x] `app/cli.py` — C60. `ingest`, `reindex` 명령 (평가 명령은 u4)

**대상 FR**: FR-6 | **컴포넌트**: C59, C60

---

### Step 16 — 테스트
- [x] `tests/unit/test_retry.py` — C16 순수 컴포넌트 (**속성 기반 테스트 포함**, NFR-27)
- [x] `tests/unit/test_chunker.py` — BR-26~31 청킹 규칙
- [x] `tests/unit/test_structure_msds.py` — BR-15~20, **8섹션 미만 폴백 포함**
- [x] `tests/unit/test_structure_law.py` — BR-21~23
- [x] `tests/unit/test_normalize.py` — BR-14
- [x] `tests/unit/test_change_detector.py` — BR-09, BR-10
- [x] `tests/unit/test_policy.py` — BR-03~05, **차단 시 우회 경로 없음 검증**
- [x] `tests/unit/test_job_tracker.py` — BR-46~51 상태 판정
- [x] `tests/unit/test_metadata_rules.py` — BR-32, BR-33 색인 거부
- [x] `tests/unit/test_config.py` — 필수값 누락 시 기동 실패
- [x] `tests/fixtures/` — MSDS 샘플, 법령 샘플, 사고사례 샘플, API 응답 샘플
- [x] `conftest.py` — 인메모리/트랜잭션 격리 픽스처

**NFR**: NFR-24, NFR-27, **NFR-28(네트워크 비의존)**
**⚠️ 테스트는 이 단계에서 작성만 하고, 실행은 Build & Test 단계입니다.**

---

### Step 17 — 배포 산출물
- [x] `Dockerfile` — `python:3.12-slim` 멀티스테이지, 비루트 `appuser`(10001) (ID-2, ID-4)
- [x] `docker-compose.yml` — 컨테이너 5종, 볼륨 4종, 헬스체크, 메모리 제한 (ID-1, ID-3, ID-7)
  - **`127.0.0.1:8200` 접두사에 제거 금지 주석** (NFR-18, ID-12)
  - `depends_on: service_completed_successfully` 로 migrate 선행 (ID-10)
- [x] `db/init/01-extensions.sql`
- [x] `scripts/backup.sh` / `scripts/restore.sh` (ID-9)

**NFR**: NFR-18, NFR-29, NFR-30, NFR-31 | **참고**: `deployment-architecture.md`

---

### Step 18 — 문서
- [x] `README.md` — 개요, 요구사항(**호스트 12G 메모리**), 기동 방법, 환경변수, **u1 완료 시점 상태**,
      **"인증 없음 — 로컬 전용" 경고** (UD-9, ID-13)
- [x] `aidlc-docs/construction/u1-ingestion-index/code/code-summary.md` — 생성 파일 목록, 설계 대비 조정 사항
- [x] `aidlc-docs/construction/u1-ingestion-index/code/traceability.md` — **FR → BR → 컴포넌트 → 파일 경로** (QG-1)
- [x] `aidlc-docs/construction/u1-ingestion-index/code/api-endpoints.md` — 엔드포인트 명세

---

## 4. FR 추적성 (생성 완료 시 [x] 표시)

| FR | 요구사항 | Step |
|---|---|---|
| [ ] FR-1 | 물질 기본정보 수집 | 7, 10, 13 |
| [ ] FR-2 | 법령 조문 수집 | 7, 10, 11 |
| [ ] FR-3 | 화학사고 사례 수집 | 7, 10, 11 |
| [ ] FR-4 | MSDS PDF 수집·파싱 | 7, 11 |
| [ ] FR-5 | 정책 준수 | 10 |
| [ ] FR-6 | 큐·진행률 | 9, 13, 14, 15 |
| [ ] FR-7 | 증분 갱신 | 10 |
| [ ] FR-8 | 재시도·부분 실패 | 9, 10, 11 |
| [ ] FR-9 | 정규화·구조 분해 | 11 |
| [ ] FR-10 | 청킹·메타데이터 | 3, 11 |
| [ ] FR-11 | 임베딩·벡터 적재 | 8, 12 |
| [ ] FR-12 | 키워드 인덱스 | 3, 12 |
| [ ] FR-13 | 멱등 재색인 | 12 |
| [ ] FR-40 | 구조적 로깅 | 2 |
| [ ] FR-43 | 헬스체크 | 14 |
| [ ] FR-48 | 운영 화면 | 14 |

---

## 5. 생성 원칙

1. **계획에 없는 파일을 만들지 않는다.** 필요가 생기면 계획을 먼저 갱신한다
2. **애플리케이션 코드는 `c:\Users\403\IDE\safeenv\` 하위에만** 생성한다 (`aidlc-docs/` 금지)
3. 모든 파라미터는 `Config`(C1)를 통해 주입하며 **하드코딩하지 않는다** (NFR-23)
4. 계층 규칙을 준수한다 — L4 → L3 → L2 → L1 → L0, 역방향 금지
5. 도메인 컴포넌트는 **DB 세션을 직접 받지 않는다** (DD-20)
6. 검색 계열 메서드는 **`scope` 를 필수 인자**로 받는다 (DD-19)
7. **u2~u5 확장 지점을 미리 반영**하되, 미사용 코드에는 사유를 주석으로 명시한다 (DD-21)
8. UI 요소에 **`data-testid`** 를 부여한다 (`{component}-{element-role}`)
9. 테스트는 **네트워크에 의존하지 않는다** (NFR-28)
10. **비밀값을 코드·로그·저장소에 남기지 않는다** (NFR-14)

---

## 6. 예상 규모

| 구분 | 예상 파일 수 |
|---|---|
| Python 소스 | ~55 |
| HTML 템플릿 | ~10 |
| 정적 파일 | 2 |
| 테스트 + 픽스처 | ~18 |
| 설정·마이그레이션 | ~6 |
| 배포·문서 | ~10 |
| **합계** | **약 100개** |

**⚠️ 전 18단계를 한 번에 실행합니다.** 중간 승인 게이트는 없으며,
완료 후 Step 14의 완료 메시지로 일괄 검토를 요청합니다.

---

## 7. 알려진 제약 (Build & Test 로 이월)

| # | 항목 | 사유 |
|---|---|---|
| 1 | 공공 API 실제 응답 스펙 미확인 | 인증키 미보유 (R-1). 어댑터는 설정 주도 + 픽스처 기반 |
| 2 | MSDS PDF 실제 레이아웃 다양성 | 샘플 확보 범위 한계 (R-2). 파싱 성공률은 실측 필요 |
| 3 | 임베딩 모델 실제 성능·메모리 | 로컬 실행 실측 필요 (R-3) |
| 4 | 테스트 실행 결과 | 본 단계는 작성만 |
| 5 | Docker 기동·이미지 크기 | Build & Test 에서 실측 |

---

**Part 1 완료. 이 계획을 승인하시면 Part 2 (Generation) 를 실행합니다.**
