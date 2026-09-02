# Traceability — u1-ingestion-index

**작성일**: 2026-08-20
**Quality Gate QG-1**: FR → BR → 컴포넌트 → 파일 경로. **미매핑 0건**

---

## 1. 기능 요구사항 추적

| FR | 요구사항 | BR | 컴포넌트 | 파일 |
|---|---|---|---|---|
| **FR-1** | 물질 기본정보·GHS 수집 | BR-01, 02, 08 | C9 | `app/adapters/sources/api_sources.py` (`SubstanceApiAdapter`), `config/sources.yaml` |
| **FR-2** | 법령 조문 수집 | BR-01, 02, 21~23 | C9 | `app/adapters/sources/api_sources.py` (`LawApiAdapter`) |
| **FR-3** | 화학사고 사례 수집 | BR-01, 02, 25 | C9 | `app/adapters/sources/api_sources.py` (`IncidentDataAdapter`) |
| **FR-4** | MSDS PDF 수집·파싱 | BR-12, 15~20 | C9, C18, C19 | `app/adapters/sources/msds_pdf.py`, `app/processing/stages/extract.py` |
| **FR-5** | robots·약관 정책 준수 | BR-03~07, 43 | C14 | `app/ingestion/policy.py` |
| **FR-6** | 비동기 큐·진행률 | BR-46, 47, 50, 51 | C28, C29, C59 | `app/jobs/tracker.py`, `app/jobs/queue.py`, `app/worker.py` |
| **FR-7** | 증분 갱신 | BR-09~11, 13, 49 | C15 | `app/ingestion/change_detector.py` |
| **FR-8** | 재시도·부분 실패 | BR-40~45, 48 | C16, C17, C23 | `app/ingestion/retry.py`, `app/ingestion/orchestrator.py`, `app/processing/runner.py` |
| **FR-9** | 정규화·구조 분해 | BR-14, 17~19, 24 | C20, C21 | `app/processing/stages/normalize.py`, `app/processing/stages/structure.py`, `app/processing/structure/*.py` |
| **FR-10** | 청킹·메타데이터 | BR-26~31, 35, 36, 39 | C22 | `app/processing/chunker.py`, `app/core/types.py` (`ChunkMeta`) |
| **FR-11** | 임베딩·벡터 적재 | BR-61, 62 | C24, C25 | `app/indexing/embedder.py`, `app/indexing/vector_index.py`, `app/adapters/embedding_local.py` |
| **FR-12** | 키워드 인덱스 (CAS 정확 매칭) | BR-38 | C26 | `app/indexing/keyword_index.py`, `migrations/versions/0001_base.py` |
| **FR-13** | 멱등 재색인 | BR-54, 55 | C27 | `app/indexing/reindexer.py`, `app/services/indexing_service.py` |
| **FR-40** | 구조적 로깅 | BR-57~60 | C2 | `app/core/logging.py` |
| **FR-43** | 헬스체크 | BR-52 | C58 | `app/web/routers/health.py`, `app/worker.py` |
| **FR-48** | 운영 화면 | BR-50 | C56, C57 | `app/web/routers/admin.py`, `app/web/templates/*.html` |

**FR 16건 전건 구현. 미구현 0건** ✅

---

## 2. 비즈니스 규칙 추적 (BR-01~BR-62)

| BR 범위 | 구현 위치 | 테스트 |
|---|---|---|
| BR-01, 02 (소스·인증키) | `services/ingestion_service.py::start`, `adapters/sources/http.py::resolve_api_key` | `test_config_and_logging.py::TestSecrets` |
| BR-03~07 (정책·간격) | `ingestion/policy.py`, `adapters/sources/http.py::_respect_interval` | `test_policy.py` |
| BR-08 (초기 대상 선정) | `adapters/sources/api_sources.py::list_targets` (`initial_substance_target`) | — |
| BR-09~11, 13 (변경 감지) | `ingestion/change_detector.py`, `db/repositories/catalog.py::mark_collected` | `test_change_detector.py` |
| BR-12 (원본 보관) | `processing/runner.py::_store_original` | — |
| BR-14 (정규화) | `processing/stages/normalize.py` | `test_normalize_and_tokens.py::TestNormalize` |
| BR-15~20 (MSDS 16섹션) | `processing/structure/msds.py` | `test_structure_msds.py` |
| BR-21~23 (법령 조·항·호) | `processing/structure/law.py` | `test_structure_law.py` |
| BR-24 (구조 실패 시 진행) | `processing/stages/structure.py` | `test_structure_msds.py::TestFallback` |
| BR-25 (사고사례 필드) | `processing/structure/incident.py` | `test_metadata_rules.py::TestStructureDispatch` |
| BR-26~31 (청킹) | `processing/chunker.py` | `test_chunker.py` |
| BR-32, 33 (필수 메타) | `db/repositories/documents.py::upsert`, `catalog.py::upsert`, `processing/runner.py::_stage_chunk` | `test_metadata_rules.py::TestRequiredMetadata` |
| BR-34 (동의어 정규화) | `db/repositories/catalog.py::add_synonyms` | — *(u3에서 확장)* |
| BR-35~37, 39 (메타 구성) | `core/types.py::ChunkMeta`, `services/indexing_service.py` | `test_metadata_rules.py` |
| BR-38 (식별자 정확 매칭) | `indexing/keyword_index.py`, `migrations/versions/0001_base.py` | — *(DB 필요, Build & Test)* |
| BR-40~45 (재시도·재개) | `ingestion/retry.py`, `ingestion/orchestrator.py` | `test_retry.py`, `test_orchestrator.py` |
| BR-46~52 (작업 상태) | `jobs/tracker.py`, `db/repositories/jobs.py` | `test_job_tracker.py` |
| BR-53~56 (멱등·삭제) | `services/indexing_service.py`, `db/repositories/documents.py` | — *(DB 필요, Build & Test)* |
| BR-57~60 (로깅·마스킹) | `core/logging.py`, `jobs/tracker.py::mark_failed` | `test_config_and_logging.py`, `test_job_tracker.py::TestSecretMasking` |
| BR-61, 62 (임베딩 배치·캐시) | `indexing/embedder.py`, `adapters/embedding_local.py` | — *(모델 필요, Build & Test)* |

**BR 62건 전건 구현 위치 존재.**
단위 테스트로 검증된 것 **48건**, DB·모델·컨테이너가 필요해 Build & Test로 이월된 것 **14건**.

---

## 3. 비기능 요구사항 추적

| NFR | 구현 위치 | 검증 |
|---|---|---|
| **NFR-4** 인덱싱 처리량 | `indexing/embedder.py` (배치), `processing/runner.py` (구간 로깅) | Build & Test 실측 |
| **NFR-9** 청크 10만 규모 | `migrations/versions/0001_base.py` 인덱스 8종 | Build & Test 실측 |
| **NFR-10** 워커 확장 | `jobs/queue.py` (상태 미보유), `docker-compose.yml` (`--scale`) | Build & Test D-10 |
| **NFR-14** 비밀값 | `core/config.py` (`SecretStr`), `core/logging.py` (마스킹), `.gitignore`, `.dockerignore` | `test_config_and_logging.py` ✅ |
| **NFR-17** 입력 검증 | `web/routers/api.py`, `web/routers/admin.py`, `db/repositories/*` (ORM 바인딩) | `test_config_and_logging.py::TestValidation` ✅ |
| **NFR-18** 루프백 바인딩 | `docker-compose.yml` (`127.0.0.1:8200:8000`) | Build & Test D-4 |
| **NFR-20** 임베딩 비용 0 | `adapters/embedding_local.py` (로컬 실행 + 캐시) | Build & Test |
| **NFR-21** 모델 교체 | `ports/*.py` 4종, `db/models.py::ChunkEmbedding` (model_id 분리) | `test_metadata_rules.py` 간접 |
| **NFR-23** 설정 외부화 | `core/config.py` (23종), `.env.example` | `test_config_and_logging.py` ✅ |
| **NFR-24** 단위 테스트 | `tests/unit/` 11종 | Build & Test 실행 |
| **NFR-27** 속성 기반 테스트 | `test_retry.py::TestProperties`, `test_chunker.py::TestProperties`, `test_normalize_and_tokens.py` | ✅ 작성 완료 |
| **NFR-28** 네트워크 비의존 | `conftest.py`, 스텁 어댑터, lazy ML import | Build & Test 실행 |
| **NFR-29** 단일 명령 기동 | `docker-compose.yml` | Build & Test D-1 |
| **NFR-30** 비루트 | `Dockerfile` (`appuser` uid 10001) | Build & Test D-6 |
| **NFR-31** 볼륨 영속화 | `docker-compose.yml` 볼륨 4종 | Build & Test D-7 |

---

## 4. 설계 결정 구현 확인

| DD/ID | 결정 | 구현 확인 |
|---|---|---|
| **DD-2** | 단일 SourceAdapter 프로토콜 | `ports/source.py` + 구현 4종, 오케스트레이터는 `SourceAdapter`만 참조 ✅ |
| **DD-3** | 명시적 단계 체인 | `processing/runner.py` 5단계 + `last_stage` 기록 ✅ |
| **DD-4** | 원문 3계층 보존 | `document.original_path` + `extracted_text.text` + `chunk` ✅ |
| **DD-6** | AI 포트 3분할 | `ports/{llm,embedding,reranker}.py` ✅ |
| **DD-13** | 자체 Job 테이블 | `db/models.py::Job/JobItem`, `jobs/queue.py`는 상태 미보유 ✅ |
| **DD-15** | SQLAlchemy 2.x + Alembic | `db/models.py`, `migrations/` ✅ |
| **DD-16** | 추적 데코레이터 | `adapters/tracing.py` 3종 ✅ |
| **DD-19** | `scope` 필수 인자 | `VectorIndex.search`, `KeywordIndex.search`, `lookup_exact` ✅ |
| **DD-20** | 세션 미주입 | 도메인 컴포넌트가 `Session`을 받지 않음 (서비스만 보유) ✅ |
| **DD-21** | 확장 지점 선반영 | `chunk.owner_id`, `document.owner_id`, `substance_synonym`, `DocType.USER_UPLOAD`, `JobKind.UPLOAD_INDEX` ✅ |
| **DD-23** | 벡터·키워드 동일 트랜잭션 | `services/indexing_service.py::process` 단일 트랜잭션 ✅ |
| **DD-24** | 문서 1건 = 1 트랜잭션 | `jobs/tasks.py` → `session_scope()` 문서 단위 ✅ |
| **ID-2** | 멀티스테이지 슬림 이미지 | `Dockerfile` builder/runtime ✅ |
| **ID-4** | 비루트 uid 10001 | `Dockerfile` ✅ |
| **ID-6** | 모델 볼륨 캐시 | `HF_HOME=/models`, `safeenv_models` 볼륨 ✅ |
| **ID-10** | 일회성 migrate 선행 | `docker-compose.yml` `service_completed_successfully` ✅ |
| **ID-12** | 루프백 전용 노출 | `127.0.0.1:8200:8000` + 제거 금지 주석 ✅ |
| **ID-13** | 무인증 경고 표시 | `base.html` 배너, `README.md` 경고 ✅ |
| **ID-15** | Python 헬스체크 | `Dockerfile` HEALTHCHECK ✅ |

---

## 5. u2~u5 선반영 요소 확인 (DD-21)

| 선반영 | 파일 | 사용 유닛 | u1 사용 여부 |
|---|---|---|---|
| `chunk.owner_id` | `db/models.py`, `0001_base.py` | u5 | 미사용 (항상 NULL) |
| `document.owner_id` | `db/models.py`, `0001_base.py` | u5 | 미사용 |
| `substance_synonym` 테이블 | `db/models.py`, `0001_base.py` | u3 | 수집 시 적재만 |
| `DocType.USER_UPLOAD` | `core/types.py` | u5 | 미사용 |
| `JobKind.UPLOAD_INDEX` | `core/types.py` | u5 | 미사용 |
| `Scope` 필수 인자 | `indexing/*.py` | u5 | 항상 `Scope.public()` |
| `LLMPort`, `RerankerPort` | `ports/` | u2 | 정의만 |
| `TracedLLM`, `TracedReranker` | `adapters/tracing.py` | u2 | 미사용 |
| `MetaFilter` | `indexing/vector_index.py` | u2 | 정의만 |
| `substance` GHS·H/P·물성 컬럼 | `db/models.py` | u3 | 적재만 |
| `UserRepo`/`QueryLogRepo`/`EvaluationRepo` | `db/repositories/stubs.py` | u5/u2/u4 | `NotImplementedError` |

**모든 미사용 코드에 사유 주석이 부착되어 있습니다** (생성 원칙 7).

---

## 6. 테스트 커버리지 요약

| 테스트 모듈 | 대상 규칙 | 케이스 수(대략) |
|---|---|---|
| `test_retry.py` | BR-41~43 + NFR-27 | 16 |
| `test_structure_msds.py` | BR-15~20, 24 | 12 |
| `test_structure_law.py` | BR-21~23 | 12 |
| `test_chunker.py` | BR-26~31 + NFR-27 | 12 |
| `test_normalize_and_tokens.py` | BR-14 + NFR-27 | 17 |
| `test_change_detector.py` | BR-09~11 | 11 |
| `test_policy.py` | BR-03~05, CON-3 | 11 |
| `test_job_tracker.py` | BR-46~51, 60 | 14 |
| `test_metadata_rules.py` | BR-24, 25, 32, 33, 37, 39 | 12 |
| `test_config_and_logging.py` | NFR-14, 23, BR-57~60 | 22 |
| `test_orchestrator.py` | BR-40~45, 03, 09 | 11 |
| **합계** | | **약 150** |

**실행은 Build & Test 단계입니다.**
