# Build Instructions — safeenv

**작성일**: 2026-08-20
**대상**: 유닛 `u1-ingestion-index`

---

## 1. 사전 요구 사항

| 항목 | 값 | 실측 |
|---|---|---|
| Python | ≥ 3.12 | **3.14.6** 확인 |
| Docker | Docker Desktop | **29.7.2** 확인 |
| 호스트 메모리 | 12GB 권장 (컨테이너 합계 8.5GB) | — |
| 디스크 여유 | 약 15GB | — |
| **호스트 포트** | **`8300`** | 8200은 `trip-app` 점유 중 (§5 참조) |

### 필수 환경 변수

```bash
cp .env.example .env
```

`POSTGRES_PASSWORD` 만 채우면 기동합니다. 나머지 23종은 기본값이 있습니다.
공공 API 인증키(`NCIS_API_KEY`, `LAW_API_KEY`, `INCIDENT_API_KEY`)는 **없어도 기동**하며,
해당 소스 수집 시에만 명확한 오류로 실패합니다 (BR-02).

---

## 2. 로컬 빌드 (테스트용)

### 2.1 의존성 설치

```bash
pip install -e ".[dev]"
```

**ML 스택(`sentence-transformers`, `torch`)은 단위 테스트에 필요 없습니다.**
없으면 `DeterministicEmbeddingAdapter` 로 자동 대체됩니다 (NFR-28).

단위 테스트에 실제로 필요한 것:
`pytest` `hypothesis` `pydantic` `pydantic-settings` `sqlalchemy` `pgvector` `httpx` `pyyaml` `pypdf`

### 2.2 컴파일 검증

```bash
python -m compileall -q app migrations tests
```

**기대 결과**: 종료 코드 0, 출력 없음 — ✅ 실측 통과

### 2.3 린트

```bash
ruff check app tests
```

**기대 결과**: `All checks passed!` — ✅ 실측 통과

> `app/web/routers/*.py` 는 `B008` 을 per-file-ignore 합니다.
> `Depends()` / `Query()` 를 인자 기본값에 두는 것은 FastAPI 의 문서화된 관용구이며,
> 이 규칙이 잡으려는 가변 기본값 버그가 아닙니다. `pyproject.toml` 에 근거를 기록했습니다.

---

## 3. Docker 빌드

```bash
docker compose build
```

### 빌드 산출물

| 이미지 | 용도 |
|---|---|
| `safeenv-app:latest` | `migrate` / `app` / `worker` 3개 서비스가 **공유** (UD-3) |
| `pgvector/pgvector:pg16` | 외부 이미지 |
| `redis:7-alpine` | 외부 이미지 |

### 멀티스테이지 구조

```
stage 1 builder  : python:3.12-slim + build-essential -> wheel 생성
stage 2 runtime  : python:3.12-slim + wheel 설치 + 앱 코드 + 비루트 appuser(10001)
```

빌드 도구는 런타임 이미지에 포함되지 않습니다 (ID-2).

### 예상 소요

**첫 빌드는 오래 걸립니다.** `torch` CPU 휠만 200MB 이상이며,
`sentence-transformers` 의 전이 의존성까지 합치면 다운로드가 대부분의 시간을 차지합니다.
두 번째 빌드부터는 레이어 캐시로 크게 단축됩니다
(의존성 정의를 앱 코드보다 먼저 복사하도록 배치).

---

## 4. 기동

```bash
mkdir -p data/originals logs backups   # 바인드 마운트 대상 미리 생성
docker compose up -d
docker compose ps
```

### 기동 순서 (ID-10)

```
postgres (healthy) + redis (healthy)
        -> migrate (alembic upgrade head, 종료코드 0)
                -> app + worker
```

`app` 과 `worker` 는 `migrate` 가 **성공 종료해야만** 기동합니다
(`depends_on: service_completed_successfully`). 두 프로세스가 각자 마이그레이션을
실행하는 경합이 구조적으로 발생하지 않습니다.

### 성공 확인

```bash
curl http://127.0.0.1:8300/healthz
# {"app":"ok","db":"ok","queue":"ok","worker":"ok"}
```

---

## 5. ⚠️ 포트 충돌 — CON-2 정정

Infrastructure Design 은 호스트 포트 **8200** 을 지정했고,
ID-16 의 6축 분석에서 `news`(8100) 와 `petmate`(8000/5173) 만 확인했습니다.

**Build & Test 실측 결과 `trip-app` 컨테이너가 이미 `127.0.0.1:8200` 을 점유하고 있었습니다.**

```
$ docker ps --format "table {{.Names}}\t{{.Ports}}"
NAMES      PORTS
trip-app   127.0.0.1:8200->8200/tcp
news-app   127.0.0.1:8100->8000/tcp
```

**조치**: 호스트 포트를 **8300** 으로 변경. 나머지 5축(프로젝트명·네트워크·볼륨·이미지·컨테이너명)은
충돌 없음을 실측 확인했습니다.

```
network  safeenv_net   : free
volumes  safeenv_*     : free
image    safeenv-app   : free
```

이 정정은 `requirements.md` CON-2 와 인프라 설계 문서에 반영했습니다.

---

## 6. 문제 해결

### 기동이 `POSTGRES_PASSWORD must be set in .env` 로 실패

`.env` 파일이 없거나 `POSTGRES_PASSWORD` 가 비어 있습니다.
`cp .env.example .env` 후 값을 채우십시오. Compose 의 `${VAR:?...}` 로 **기동 전에** 차단됩니다.

### `migrate` 가 실패하고 `app`·`worker` 가 뜨지 않음

의도된 동작입니다. 스키마 없이 앱이 뜨는 것을 막습니다.

```bash
docker compose logs migrate
```

`CREATE EXTENSION vector` 실패라면 `pgvector/pgvector:pg16` 이미지가 맞는지 확인하십시오.

### 워커가 `sentence-transformers` 관련 오류

모델 다운로드 실패는 `transient` 로 분류되어 재시도됩니다.
계속 실패하면 `safeenv_models` 볼륨 권한과 네트워크를 확인하십시오.
임시로는 `DeterministicEmbeddingAdapter` 가 파이프라인을 끝까지 돌리지만
**벡터 검색 결과가 의미를 갖지 않습니다.**

### 바인드 마운트 쓰기 권한 오류

컨테이너는 uid 10001 로 실행됩니다. `docker compose up` 전에
`mkdir -p data/originals logs` 로 호스트에 디렉터리를 만들어 두면
Docker 가 root 소유로 생성하는 것을 피할 수 있습니다.

### 포트가 이미 사용 중

```bash
netstat -ano | grep ":8300 .*LISTENING"
docker ps --format "table {{.Names}}\t{{.Ports}}"
```

다른 프로젝트가 점유 중이면 `docker-compose.yml` 의 호스트 포트만 바꾸십시오.
**`127.0.0.1:` 접두사는 제거하면 안 됩니다** (NFR-18).
