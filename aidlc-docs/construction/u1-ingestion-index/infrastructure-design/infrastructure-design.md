# Infrastructure Design — u1-ingestion-index

**단계**: 🟢 CONSTRUCTION / Infrastructure Design
**작성일**: 2026-08-20
**근거**: `construction/plans/u1-ingestion-index-infrastructure-design-plan.md` (IQ-1~IQ-17 확정)

> **이 문서가 프로젝트 전체의 인프라 토폴로지를 확정합니다.**
> u2~u5 는 인프라를 변경하지 않으며, 변경이 발생하면 본 문서에 델타로 추가 기록합니다
> (`execution-plan.md` §4).

---

## 1. 인프라 결정 요약 (ID-1 ~ ID-17)

| ID | 결정 | 근거 |
|---|---|---|
| **ID-1** | 컨테이너 **5종** — `migrate`(일회성) / `app` / `worker` / `postgres` / `redis` | IQ-1=A, IQ-10=B |
| **ID-2** | 앱 이미지는 `python:3.12-slim` **멀티스테이지 빌드** | IQ-2=A |
| **ID-3** | **메모리 제한 설정** — postgres 2G / app 2G / worker 4G / redis 512M | IQ-3=B, R-3 |
| **ID-4** | **비루트 `appuser` (uid 10001)** 로 실행 | IQ-4=A, NFR-30 |
| **ID-5** | DB 이미지는 `pgvector/pgvector:pg16` | IQ-5=A, DD-15 |
| **ID-6** | 임베딩 모델은 **볼륨 캐시** — 최초 기동 시 다운로드 | IQ-6=A, CON-5 |
| **ID-7** | 볼륨 **4종** 분리 — pgdata / originals / models / logs | IQ-7=A |
| **ID-8** | 원본 보관은 **호스트 바인드 마운트** `./data/originals` | IQ-8=A, R-2 |
| **ID-9** | **`pg_dump` 백업·복원 스크립트** 제공 | IQ-9=B, NFR-4 |
| **ID-10** | 마이그레이션은 **일회성 `migrate` 서비스**가 선행 실행 | IQ-10=B |
| **ID-11** | 워커 기본 1개, `--scale worker=N` 으로 확장 | IQ-11=A, NFR-10 |
| **ID-12** | **`app` 만 `127.0.0.1:8200` 노출**, DB·큐는 내부 네트워크 전용 | IQ-12=A, **NFR-18** |
| **ID-13** | `/admin` 은 **루프백 바인딩으로만 통제**, u5에서 인증 필수 경로로 전환 | IQ-13=A |
| **ID-14** | 로그는 **stdout JSON + `logs` 볼륨 파일 병행** | IQ-14=A, FR-40 |
| **ID-15** | 헬스체크는 **Python 인터프리터**로 구현 (curl 미설치) | IQ-15=A |
| **ID-16** | 인프라 **6축 전부 분리**, `shared-infrastructure.md` 미생성 | IQ-16=A |
| **ID-17** | 추가 반영 사항 없음 | IQ-17=A |

---

## 2. 논리 컴포넌트 → 인프라 매핑

| 논리 컴포넌트 | 인프라 | 비고 |
|---|---|---|
| C56 `WebRouters`, C57 `TemplateRenderer`, C58 `HealthCheck` | `app` 컨테이너 (ASGI 서버) | 포트 8000 (내부) |
| C59 `WorkerEntrypoint` | `worker` 컨테이너 | 확장 가능 |
| C60 `CliEntrypoint` | `app` 컨테이너 내 일회성 `exec` | 수집·재색인·(u4)평가 |
| C3 `Database`, C4 `Repositories` | `postgres` 컨테이너 | pgvector 확장 |
| C25 `VectorIndex` | `postgres` — 벡터 컬럼 + 근사 최근접 인덱스 | DD-23 동일 트랜잭션 |
| C26 `KeywordIndex` | `postgres` — 전문검색 인덱스 | DD-23 동일 트랜잭션 |
| C29 `TaskQueue` | `redis` 컨테이너 | **상태 미보유** (DD-13) |
| C28 `JobTracker` | `postgres` — `job` / `job_item` 테이블 | 상태의 단일 출처 |
| C11 `EmbeddingAdapter` | `worker` 프로세스 + `models` 볼륨 | 모델 파일 캐시 |
| C18 `FetchStage` 원본 보관 | `./data/originals` 바인드 마운트 | BR-12 |
| C2 `Logger` | stdout + `./logs` 바인드 마운트 | BR-57 |
| Alembic 마이그레이션 | `migrate` 일회성 컨테이너 | ID-10 |

---

## 3. 컨테이너 명세

### 3.1 `safeenv-migrate` (일회성)

| 항목 | 값 |
|---|---|
| 이미지 | `safeenv-app:latest` (앱과 동일) |
| 명령 | Alembic `upgrade head` |
| `restart` | `no` — 1회 실행 후 종료 |
| 의존 | `postgres` (healthy) |
| 종료 코드 | 0 이면 `app`·`worker` 기동 허용 |

**설계 근거**: `app` 과 `worker` 가 각자 마이그레이션을 실행하면 경합이 발생합니다.
일회성 서비스를 선행시켜 **경합이 구조적으로 불가능**하게 합니다 (ID-10).

### 3.2 `safeenv-app`

| 항목 | 값 |
|---|---|
| 이미지 | `safeenv-app:latest` |
| 명령 | ASGI 서버 기동 (`APP_HOST=0.0.0.0`, `APP_PORT=8000`) |
| 포트 | **`127.0.0.1:8200` → 8000** |
| 메모리 제한 | 2G |
| `restart` | `unless-stopped` |
| 사용자 | `appuser` (10001) |
| 의존 | `migrate`(완료), `postgres`(healthy), `redis`(healthy) |
| 헬스체크 | Python 으로 `http://127.0.0.1:8000/healthz` 요청 |
| 볼륨 | `./logs`(rw), `./data/originals`(ro) |

> **⚠️ NFR-18 구현 지점**: 컨테이너 내부는 `0.0.0.0` 바인딩이지만,
> **호스트 노출은 Compose 포트 매핑의 `127.0.0.1:` 접두사로 제한**됩니다.
> 이 접두사를 제거하면 즉시 NFR-18 위반이 됩니다.

### 3.3 `safeenv-worker`

| 항목 | 값 |
|---|---|
| 이미지 | `safeenv-app:latest` |
| 명령 | 워커 루프 기동 |
| 포트 | **노출 없음** |
| 메모리 제한 | **4G** — 임베딩 모델 상주 (R-3) |
| `restart` | `unless-stopped` |
| 사용자 | `appuser` (10001) |
| 의존 | `migrate`(완료), `postgres`(healthy), `redis`(healthy) |
| 헬스체크 | `job` 하트비트가 `WORKER_STALE_THRESHOLD` 이내인지 확인 (BR-52) |
| 볼륨 | `./logs`(rw), `./data/originals`(rw), `safeenv_models`(rw) |
| 확장 | `docker compose up --scale worker=N` |

### 3.4 `safeenv-postgres`

| 항목 | 값 |
|---|---|
| 이미지 | `pgvector/pgvector:pg16` |
| 포트 | **호스트 노출 없음** — 내부 네트워크 전용 |
| 메모리 제한 | 2G |
| `restart` | `unless-stopped` |
| 헬스체크 | `pg_isready` |
| 볼륨 | `safeenv_pgdata` |
| 초기화 | `CREATE EXTENSION IF NOT EXISTS vector;` (init 스크립트) |

**튜닝** (NFR-9 청크 10만 건):
`shared_buffers`, `work_mem`, `maintenance_work_mem` 을 환경변수 또는 설정 파일로 조정 가능하게 합니다.
초기값은 컨테이너 메모리 제한 2G 에 맞춥니다.

### 3.5 `safeenv-redis`

| 항목 | 값 |
|---|---|
| 이미지 | `redis:7-alpine` |
| 포트 | **호스트 노출 없음** |
| 메모리 제한 | 512M |
| `restart` | `unless-stopped` |
| 헬스체크 | `redis-cli ping` |
| 영속성 | **비활성** — 작업 상태는 PostgreSQL 에 있으므로 (DD-13) 큐 손실 시 재실행으로 복구 |

**설계 근거**: Redis 는 **실행만 담당하고 상태를 보유하지 않습니다** (DD-13).
따라서 AOF/RDB 영속성이 불필요하며, 재기동 시 미완료 작업은 `job_item.status = pending`
으로 남아 있어 재실행으로 복구됩니다.

---

## 4. 이미지 빌드 전략

### 4.1 멀티스테이지 구성

```
Stage 1 (builder):  python:3.12-slim
                    빌드 도구 설치 -> 의존성 컴파일 -> wheel 생성
Stage 2 (runtime):  python:3.12-slim
                    wheel 만 설치 -> 앱 코드 복사 -> appuser 생성 -> 비루트 전환
```

### 4.2 예상 이미지 크기

| 구성 | 예상 |
|---|---|
| `python:3.12-slim` 베이스 | ~150MB |
| Python 의존성 (FastAPI, SQLAlchemy, PDF 파서 등) | ~250MB |
| **임베딩·리랭커 라이브러리** (PyTorch CPU 등) | ~800MB |
| 앱 코드·템플릿 | ~5MB |
| **합계 예상** | **~1.2GB** |

> **⚠️ 임베딩 모델 파일은 이미지에 포함하지 않습니다** (ID-6).
> 모델 가중치(수백 MB~2GB)는 최초 기동 시 `safeenv_models` 볼륨에 다운로드됩니다.
> Build & Test 단계에서 **실측값을 기록**하고 예상 대비 차이를 검토합니다.

### 4.3 레이어 캐시 최적화

의존성 정의 파일을 먼저 복사·설치한 뒤 애플리케이션 코드를 복사하여,
코드 변경 시 의존성 레이어가 재사용되도록 합니다.

---

## 5. 볼륨 설계

| 볼륨 | 유형 | 마운트 | 용도 | 예상 크기 | 백업 |
|---|---|---|---|---|---|
| `safeenv_pgdata` | 명명 볼륨 | postgres `/var/lib/postgresql/data` | DB (청크·벡터 포함) | **수 GB** | **필요** (ID-9) |
| `./data/originals` | 바인드 | app(ro), worker(rw) | 원본 PDF·API 응답 (BR-12) | 수 GB | 선택 |
| `safeenv_models` | 명명 볼륨 | worker | 임베딩·리랭커 모델 캐시 | ~2GB | 불필요 (재다운로드) |
| `./logs` | 바인드 | app, worker (rw) | 구조적 로그 파일 | 수백 MB | 불필요 |

**바인드 마운트 선택 근거**:
- `originals` — 파싱 실패 진단 시 원본 PDF를 호스트에서 직접 열어야 함 (R-2)
- `logs` — 호스트 도구로 로그를 검색·분석하기 위함

**권한**: 바인드 마운트 디렉터리는 `appuser`(10001) 가 쓸 수 있어야 합니다.
Windows Docker Desktop 환경에서는 통상 문제되지 않으나, **Build & Test 에서 실측 확인**합니다.

---

## 6. 백업·복원 (ID-9)

| 스크립트 | 동작 |
|---|---|
| `scripts/backup.sh` | `pg_dump` 로 `./backups/safeenv-{timestamp}.dump` 생성 |
| `scripts/restore.sh` | 지정한 덤프 파일로 `pg_restore` 실행 |

**근거**: 초기 색인에 최대 8시간이 소요되므로(NFR-4), 볼륨 손실의 비용이 큽니다.
`./data/originals` 가 남아 있으면 재수집 없이 재파싱만으로 복구할 수 있으나(FQ-8=A),
그래도 임베딩 재계산 시간이 필요합니다.

**범위 고지**: 자동 스케줄 백업은 구현하지 않습니다 (OOS-4 운영 자동화 범위 외).

---

## 7. 환경변수 (NFR-14, NFR-23)

### 7.1 비밀값 — `.env` 로만 주입, 저장소 커밋 금지

| 변수 | 용도 |
|---|---|
| `POSTGRES_PASSWORD` | DB 비밀번호 |
| `NCIS_API_KEY` | 물질정보 API 인증키 |
| `LAW_API_KEY` | 법령 API 인증키 |
| `INCIDENT_API_KEY` | 사고사례 API 인증키 |
| `ANTHROPIC_API_KEY` | LLM (u2 에서 사용, u1 은 미사용) |

**`.env.example` 을 저장소에 포함**하되 **값은 비워 둡니다.**
`.env` 는 `.gitignore` 및 `.dockerignore` 에 등록합니다 (NFR-14).

### 7.2 운영 파라미터 — `business-rules.md` §13 대응

| 변수 | 기본값 | 규칙 |
|---|---|---|
| `MAX_CHUNK_TOKENS` | 1000 | BR-27, BR-27a |
| `MIN_CHUNK_TOKENS` | 20 | BR-31 |
| `CHUNK_OVERLAP` | 0 | BR-29 |
| `MSDS_MIN_SECTIONS` | 8 | BR-20 |
| `MAX_RETRY_ATTEMPTS` | 3 | BR-41 |
| `RETRY_BACKOFF_SECONDS` | `1,4,16` | BR-41 |
| `RETRY_TOTAL_WAIT_CAP` | 60 | BR-41 |
| `POLICY_CACHE_TTL` | 86400 | BR-05 |
| `REQUEST_INTERVAL_MS` | 500 | BR-06 |
| `EMBED_BATCH_SIZE` | 32 | BR-61 |
| `WORKER_HEARTBEAT_INTERVAL` | 30 | BR-52 |
| `WORKER_STALE_THRESHOLD` | 120 | BR-52 |
| `INITIAL_SUBSTANCE_TARGET` | 1000 | BR-08 |
| `EMBEDDING_MODEL_ID` | (설정) | NFR-21 |
| `MODEL_CACHE_DIR` | `/models` | ID-6 |
| `ORIGINALS_DIR` | `/data/originals` | BR-12 |
| `LOG_DIR` | `/logs` | ID-14 |
| `LOG_LEVEL` | `INFO` | BR-57 |
| `APP_HOST` | `0.0.0.0` | ID-12 (컨테이너 내부) |
| `APP_PORT` | `8000` | ID-12 |
| `DATABASE_URL` | (조립) | DD-15 |
| `REDIS_URL` | (조립) | ID-1 |
| `TZ` | `Asia/Seoul` | — |

**총 23종.** 전부 `Config`(C1) 가 기동 시 검증하며, 필수 값 누락 시 명확한 오류로 중단합니다.

---

## 8. 관측

### 8.1 로그 (ID-14)

- **stdout/stderr** 로 구조적 JSON 출력 → `docker compose logs` 로 즉시 확인
- **`./logs` 볼륨**에 파일 병행 기록 → 이력 보존 및 호스트 도구 분석
- 로그 로테이션은 Docker `json-file` 드라이버의 `max-size` / `max-file` 로 제한

### 8.2 헬스체크 (ID-15)

| 대상 | 방식 | 판정 |
|---|---|---|
| `app` | Python 으로 `/healthz` HTTP 요청 | 200 이면 healthy |
| `postgres` | `pg_isready` | 종료 코드 0 |
| `redis` | `redis-cli ping` | `PONG` |
| `worker` | 하트비트 시각 확인 | `WORKER_STALE_THRESHOLD` 이내 (BR-52) |

**`/healthz` 응답 구성**: `{app, db, queue, worker}` 4개 항목의 개별 상태.
하나라도 비정상이면 503 을 반환합니다 (FR-43).

> **curl 미설치 근거**: `python:3.12-slim` 에는 curl 이 없습니다.
> 설치하면 이미지 크기와 공격 표면이 늘어나므로, 이미 존재하는 Python 인터프리터를 사용합니다.

---

## 9. 보안 검토 (Security Baseline 활성, CON-7)

| NFR | 인프라 대응 | 판정 |
|---|---|---|
| **NFR-14** 비밀값 | `.env` 주입, `.env.example` 만 커밋, `.gitignore`·`.dockerignore` 등록, 로그 마스킹(BR-59·60) | ✅ |
| **NFR-18** 루프백 바인딩 | `app` 만 `127.0.0.1:8200`, DB·큐는 호스트 노출 없음 | ✅ **확정** |
| **NFR-30** 비루트 | `appuser` uid 10001 | ✅ |
| **NFR-31** 볼륨 영속화 | 4종 볼륨, 재기동 후 데이터 보존 | ✅ |
| **NFR-29** 단일 명령 기동 | `docker compose up` | ✅ |

### ⚠️ 잔여 위험 1건 — `/admin` 무인증 (ID-13)

u1 시점의 `/admin` 은 **인증이 없습니다.** 통제 수단은 루프백 바인딩뿐입니다.

**적용 완화**:
1. README 상단과 `/admin` 화면 상단에 **"인증 없음 — 로컬 전용"** 경고를 표시합니다
2. `docker-compose.yml` 의 `127.0.0.1:` 접두사 옆에 **제거 금지 주석**을 명시합니다
3. **u5에서 인증 도입 시 `/admin` 을 인증 필수 경로로 전환**합니다

**이 위험은 u5 완료 시점에 해소됩니다.** 그때까지 `aidlc-state.md` 에 열린 항목으로 유지합니다.

---

## 10. 공유 인프라 검토 (ID-16)

상위 워크스페이스 `c:\Users\403\IDE` 에는 `news`, `purchase_agent`, `trip` 등
독립 AI-DLC 프로젝트가 존재하며 동시 기동될 수 있습니다.

| 축 | safeenv | 충돌 회피 |
|---|---|---|
| Compose 프로젝트명 | `safeenv` | ✅ 고유 |
| 네트워크 | `safeenv_net` | ✅ 고유 |
| **호스트 포트** | **8200** | ✅ news 8100 / petmate 8000·5173 과 분리 |
| 볼륨 | `safeenv_pgdata`, `safeenv_models` | ✅ 접두사 분리 |
| 이미지 | `safeenv-app:latest` | ✅ 고유 |
| 컨테이너명 | `safeenv-{app,worker,postgres,redis,migrate}` | ✅ 접두사 분리 |

**6축 전부 분리되므로 `construction/shared-infrastructure.md` 를 생성하지 않습니다.**
Build & Test 에서 **다른 프로젝트와의 동시 기동을 실측 검증**합니다.

---

## 11. u2~u5 인프라 영향 검토

| 유닛 | 인프라 변경 | 비고 |
|---|---|---|
| **u2** 질의응답 | **없음** | LLM 은 외부 API 호출. 리랭커 모델은 `safeenv_models` 볼륨 재사용 |
| **u4** 평가 | **없음** | CLI 는 `app` 컨테이너에서 `exec` |
| **u3** 물질 카드 | **없음** | 조회 전용 |
| **u5** 계정·업로드 | **없음** | 업로드 파일은 `./data/originals` 하위에 `uploads/` 로 분리 |

**u2~u5 는 Infrastructure Design 스테이지를 SKIP 합니다** (`execution-plan.md` §4).
단, u2 의 리랭커 모델 로딩으로 `app` 메모리 제한 2G 가 부족할 가능성이 있어,
**u2 Build & Test 에서 재검토**합니다.

---

## 12. 미검증 항목 (Build & Test 에서 해소)

| # | 항목 | 검증 방법 |
|---|---|---|
| 1 | 실제 이미지 크기 (예상 ~1.2GB) | `docker images` 실측 |
| 2 | 바인드 마운트의 `appuser` 쓰기 권한 (Windows Docker Desktop) | 컨테이너 내 쓰기 시도 |
| 3 | 임베딩 모델 최초 다운로드 소요 시간·용량 | 최초 기동 실측 |
| 4 | `worker` 4G 메모리 제한의 충분성 | 배치 32 임베딩 실행 중 관측 |
| 5 | `postgres` 2G 에서 청크 10만 건 색인 성능 (NFR-9) | 색인 실행 실측 |
| 6 | 다른 프로젝트(news 등)와의 동시 기동 | 병행 기동 확인 |
| 7 | 루프백 전용 바인딩 (NFR-18) | 외부 인터페이스에서 접속 시도 실패 확인 |
| 8 | `migrate` → `app`·`worker` 기동 순서 | 로그 순서 확인 |
| 9 | `down` 후 `up` 시 데이터 보존 (NFR-31) | 볼륨 영속성 확인 |
