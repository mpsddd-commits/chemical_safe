# Code Summary — u1-ingestion-index

**단계**: 🟢 CONSTRUCTION / Code Generation — Part 2 완료
**작성일**: 2026-08-20
**애플리케이션 코드 위치**: `c:\Users\403\IDE\safeenv\`

---

## 1. 생성 파일 집계

| 구분 | 개수 |
|---|---|
| Python 소스 (`app/`) | 47 (패키지 마커 12 포함) |
| Alembic (`migrations/`) | 4 (`alembic.ini`, `env.py`, `script.py.mako`, `versions/0001_base.py`) |
| HTML 템플릿 | 6 |
| 정적 파일 | 2 (`style.css`, `app.js`) |
| 테스트 + 픽스처 | 18 (테스트 11 + 픽스처 4 + `conftest.py` + 마커 2) |
| 설정 | 3 (`config/sources.yaml`, `config/msds_manifest.json`, `db/init/01-extensions.sql`) |
| 배포 | 4 (`Dockerfile`, `docker-compose.yml`, `scripts/backup.sh`, `scripts/restore.sh`) |
| 빌드·메타 | 4 (`pyproject.toml`, `.gitignore`, `.dockerignore`, `.env.example`) |
| 문서 | 1 (`README.md`) + 본 문서 외 `code/` 3종 |
| **합계** | **약 103개** (계획 예상 100개) |

**검증 QG-2**: 애플리케이션 코드가 `aidlc-docs/` 밖에만 존재함 ✅
(`aidlc-docs/construction/u1-ingestion-index/code/` 에는 마크다운 문서 3종만)

---

## 2. 디렉터리 구조 (실제 생성 결과)

```
safeenv/
├── app/
│   ├── core/          config.py  errors.py  logging.py  types.py
│   ├── db/            engine.py  models.py
│   │   └── repositories/  catalog.py  documents.py  jobs.py  stubs.py
│   ├── ports/         source.py  llm.py  embedding.py  reranker.py
│   ├── adapters/      embedding_local.py  reranker_local.py  llm_anthropic.py  tracing.py
│   │   └── sources/   http.py  api_sources.py  msds_pdf.py  __init__.py(registry)
│   ├── jobs/          tracker.py  queue.py  tasks.py
│   ├── ingestion/     policy.py  change_detector.py  retry.py  orchestrator.py
│   ├── processing/    tokens.py  chunker.py  runner.py
│   │   ├── stages/    extract.py  normalize.py  structure.py
│   │   └── structure/ msds.py  law.py  incident.py
│   ├── indexing/      embedder.py  vector_index.py  keyword_index.py  reindexer.py
│   ├── services/      ingestion_service.py  indexing_service.py
│   ├── web/           routers/{admin,api,health}.py  templates/  static/
│   ├── main.py  worker.py  cli.py
├── config/  migrations/  db/init/  scripts/  tests/
├── Dockerfile  docker-compose.yml  pyproject.toml  README.md
```

**유닛명 디렉터리는 생성하지 않았습니다** (UD-4). 디렉터리는 컴포넌트 계층을 따르고,
유닛은 그 디렉터리가 **언제 채워지는지**만 결정합니다.

---

## 3. 설계 대비 조정 사항 (7건)

설계 위반이 아니라 구현 과정에서 내린 배치·구성 결정입니다.

### 3.1 리포지터리를 8개 파일이 아닌 4개 모듈로 묶음
**계획**: `repositories/*.py`, 리포지터리 8종
**실제**: 클래스 8종은 그대로이되 응집도 기준으로 4개 모듈에 배치
- `catalog.py` — `SourceRepo`, `SubstanceRepo`
- `documents.py` — `DocumentRepo`, `ChunkRepo`
- `jobs.py` — `JobRepo`, `WorkerHeartbeatRepo`, `TraceRepo`
- `stubs.py` — `UserRepo`, `QueryLogRepo`, `EvaluationRepo`

**근거**: `DocumentRepo`와 `ChunkRepo`는 같은 트랜잭션에서 함께 쓰이며(DD-23),
파일을 나누면 순환 import를 유발합니다. 계획이 요구한 것은 "리포지터리 8종"이지
"파일 8개"가 아닙니다.

### 3.2 `app/processing/tokens.py` 추가 (계획 외)
청킹 규칙 BR-27·BR-31이 토큰 수를 요구하는데 계획에 계수 지점이 없었습니다.
의존성 없는 휴리스틱(한글 1.3자/토큰, 그 외 4자/토큰)으로 구현하고,
정확한 계수가 필요해지면 교체할 수 있도록 **단일 함수**로 격리했습니다.

### 3.3 `DeterministicEmbeddingAdapter` 추가 (계획 외)
**근거**: NFR-28(테스트 네트워크 비의존)과 모델 볼륨이 비어 있는 최초 기동을 동시에 만족시키려면
오프라인 대체 구현이 필요합니다. 해시 투영이므로 **의미 있는 유사도를 주지 않으며**,
활성화 시 로그에 경고와 함께 영향("vector search results are not meaningful")을 남깁니다.

### 3.4 `IdentityReranker` 추가 (계획 외)
R-4(리랭커 지연) 완화를 위해 리랭킹을 설정으로 끌 수 있어야 하는데,
`None` 처리를 호출부에 흩뿌리는 대신 무동작 구현을 두었습니다. u2에서 사용됩니다.

### 3.5 `worker_heartbeat` 테이블 추가 (E1~E12 외 1종)
**근거**: BR-52의 워커 헬스 판정에 마지막 하트비트 시각이 필요합니다.
Functional Design의 엔터티 목록에는 없었으나 규칙 BR-52가 이를 요구합니다.
`domain-entities.md`에 반영이 필요합니다 → **§5 문서 갱신 필요 항목**

### 3.6 테스트 모듈 구성 변경
**계획 10개 → 실제 11개.** `normalize`와 `tokens`를 한 모듈로, `config`와 `logging`을 한 모듈로
합치고, **`test_orchestrator.py`를 추가**했습니다.
**추가 근거**: BR-40(부분 실패), BR-41(재시도), BR-43(정책 차단 미재시도)은 오케스트레이터 수준에서만
검증 가능하며, 이것이 u1에서 가장 중요한 동작입니다.

### 3.7 `config/msds_manifest.json` 추가 (계획 외)
MSDS PDF 대상을 크롤링으로 발견하지 않기 위한 매니페스트 파일입니다.
BR-04("우회 경로를 제공하지 않는다")의 직접적 귀결 — 정책을 알 수 없는 사이트를 훑지 않고,
운영자가 명시한 URL만 수집합니다.

---

## 4. 주요 구현 판단

| # | 판단 | 근거 |
|---|---|---|
| 1 | 어댑터를 `sources.yaml` **설정 주도**로 구현 | 위험 R-1 — 공공 API 실제 스펙 미검증. 필드명 수정이 코드 변경이 아닌 설정 변경이 되도록 |
| 2 | `AccessPolicyChecker`에 **우회 진입점을 두지 않음** | BR-04. `test_policy.py::test_no_bypass_is_offered`가 이를 구조적으로 강제 |
| 3 | `RESPECT_ROBOTS=false` override 시 **사유를 명시적으로 기록** | 조용한 우회를 만들지 않기 위함. 일반 `allowed`와 구분됨 |
| 4 | robots.txt 부재/도달불가를 `ALLOWED`가 아닌 **`UNKNOWN`** 으로 기록 | 감사 기록이 "허용받았다"고 주장하지 않도록 |
| 5 | 스캔 PDF(텍스트 40자 미만)를 **`permanent` 실패**로 처리 | OCR 범위 외. 빈 색인 항목을 만드는 것보다 진단 가능한 실패가 낫음 |
| 6 | 키워드 검색에 **`simple` FTS 설정** 사용 | 한국어를 형태소 분석하는 기본 설정이 없고, `simple`이 최소한 식별자를 보존함 |
| 7 | CAS·UN을 **JSON 표현식 인덱스**로 별도 색인 | BR-38. 전문검색 토크나이저가 `7664-93-9`를 분해함 |
| 8 | `Job` 카운터를 **상태 전이 시 감산·가산** | 항목이 failed→succeeded로 바뀔 때 중복 집계 방지 |
| 9 | CLI `ingest`가 **큐를 거치지 않고 동기 실행** | Redis 없이도 색인 가능하고 실패 재현이 쉬움 |
| 10 | `partial` 을 CLI **종료코드 0**으로 처리 | 일부라도 색인되었으면 성공. 전건 실패만 1 |

---

## 5. ⚠️ 문서 갱신 필요 항목 (Build & Test 전 반영 권장)

| # | 문서 | 갱신 내용 |
|---|---|---|
| 1 | `functional-design/domain-entities.md` | `worker_heartbeat` 테이블 추가 (§3.5). 엔터티 12종 → 13종 |
| 2 | `functional-design/business-rules.md` §13 | `RESPECT_ROBOTS`, `EMBEDDING_MODEL_ID`, `EMBEDDING_DIM`, `MODEL_CACHE_DIR`, `ORIGINALS_DIR`, `LOG_DIR` 등 실제 환경변수 23종과 대조 |
| 3 | `components.md` §15 | 이월 항목 1~6번 해소 표시 (완료) |

---

## 6. 미검증 항목 (Build & Test 이월)

| # | 항목 | 사유 |
|---|---|---|
| 1 | **테스트 실행 결과** | 본 단계는 작성만. `pytest` 미실행 |
| 2 | **Docker 빌드·기동** | 이미지 크기(예상 ~1.2GB), 기동 순서, 헬스체크 미실측 |
| 3 | **마이그레이션 적용** | `alembic upgrade head` 실제 실행 미확인. HNSW 인덱스 생성 포함 |
| 4 | 공공 API 실제 응답 | 인증키 미보유 (R-1) |
| 5 | MSDS PDF 실제 파싱 성공률 | 실제 문서 샘플 미확보 (R-2) |
| 6 | 임베딩 모델 다운로드·속도·메모리 | 최초 기동 미실행 (R-3) |
| 7 | 바인드 마운트 쓰기 권한 (Windows) | `appuser`(10001) 쓰기 가능 여부 |
| 8 | 루프백 전용 바인딩 | 외부 인터페이스에서 접속 실패 확인 (NFR-18) |
| 9 | 다른 프로젝트와 동시 기동 | news(8100) 등과 충돌 없음 확인 |
| 10 | `--scale worker=2` 동작 | 워커 확장 (NFR-10) |

**배포 검증 절차 D-1~D-14**는 `infrastructure-design/deployment-architecture.md` §10 참조.

---

## 7. u2 착수 시 유의사항

| # | 항목 |
|---|---|
| 1 | `LLMPort`·`RerankerPort` 는 **정의만** 존재. `AnthropicLLMAdapter`는 `NotImplementedError` |
| 2 | `TraceRepo` 는 현재 **인메모리 버퍼 + 로그**. 실제 테이블은 u2 리비전(`0002_query`)에서 생성 |
| 3 | `VectorIndex.search` / `KeywordIndex.search` 는 이미 `scope` 필수 인자 보유 (DD-19) |
| 4 | `MetaFilter` 는 `vector_index.py` 에 정의되어 있고 두 인덱스가 공유 |
| 5 | **리랭커를 `app` 프로세스에서 로드하면 메모리 2G 초과 가능** — u2 Build & Test에서 실측 필요 |
| 6 | `DeterministicEmbeddingAdapter` 가 활성화된 상태로 평가하면 검색 품질 수치가 무의미 |
