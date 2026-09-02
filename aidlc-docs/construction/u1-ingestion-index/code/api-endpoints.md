# API Endpoints — u1-ingestion-index

**작성일**: 2026-08-20
**베이스 URL (로컬)**: `http://127.0.0.1:8200`

> ⚠️ **인증 없음.** u1 시점의 모든 엔드포인트는 인증을 요구하지 않습니다 (ID-13).
> 접근 통제는 `127.0.0.1` 바인딩뿐이며, 인증은 u5에서 도입됩니다.

---

## 1. 헬스체크

### `GET /healthz`
4개 구성요소의 상태를 개별 보고합니다 (FR-43, BR-52).

**200** — 전부 정상 / **503** — 하나 이상 비정상

```json
{ "app": "ok", "db": "ok", "queue": "ok", "worker": "down" }
```

`worker` 는 마지막 하트비트가 `WORKER_STALE_THRESHOLD`(기본 120초) 이내인지로 판정합니다.
단일 boolean 이 아닌 이유는, 웹 프로세스는 멀쩡한데 워커가 죽어 수집이 멈춘 상태를
구분해야 하기 때문입니다.

---

## 2. 소스

### `GET /api/sources`
소스 목록과 정책·인증키 상태 (FR-1~5).

```json
[
  {
    "source_id": "ncis_substance",
    "name": "화학물질정보 (물질 기본정보·GHS 분류)",
    "kind": "api",
    "doc_type": "msds",
    "policy_status": "allowed",
    "policy_reason": "permitted by robots.txt",
    "last_collected_at": "2026-08-20T01:00:00Z",
    "requires_api_key": true,
    "api_key_env": "NCIS_API_KEY",
    "api_key_configured": false,
    "enabled": true
  }
]
```

`api_key_configured` 는 **값이 아니라 설정 여부**만 알려줍니다 (NFR-14).

### `POST /api/sources/{source_id}/ingest`
수집 작업을 생성하고 큐에 등록한 뒤 **즉시 반환**합니다 (BR-47).

**요청 본문** (선택)
```json
{ "since": "2024-01-01" }
```

**200**
```json
{ "job_id": 12, "accepted": true, "reason": null }
```

**409** — 수집할 수 없는 상태
- `인증키 미설정: NCIS_API_KEY 환경변수를 설정하세요` (BR-02)
- `정책상 수집 불가: robots.txt disallows safeenv-collector for this path` (BR-03)

409 인 경우 **작업 자체가 생성되지 않습니다.** 실패한 작업을 남기지 않는 것이
의도된 동작입니다.

**422** — `since` 가 미래이거나 형식이 잘못됨 (NFR-17)

---

## 3. 작업

### `GET /api/jobs`
| 파라미터 | 기본 | 설명 |
|---|---|---|
| `status` | 없음 | 다중 지정 가능. 알 수 없는 값은 **무시** |
| `kind` | 없음 | `ingest` \| `index` \| `reindex` \| `upload_index` |
| `limit` | 25 | 1~100 |

```json
[
  {
    "id": 12, "kind": "ingest", "status": "partial",
    "params": {"source_id": "law_api", "since": null},
    "total_count": 120, "success_count": 100,
    "skipped_count": 15, "failure_count": 5,
    "ratio": 1.0,
    "created_at": "...", "started_at": "...", "finished_at": "..."
  }
]
```

`ratio` 는 `(성공 + 건너뜀 + 실패) / 전체` 이며, `total_count == 0` 이면 **0.0** 입니다 (BR-50).

### `GET /api/jobs/{job_id}`
**404** — 없는 작업

```json
{
  "job_id": 12, "status": "partial", "total_count": 120,
  "success_count": 100, "skipped_count": 15, "failure_count": 5, "ratio": 1.0
}
```

### `GET /api/jobs/{job_id}/items`
| 파라미터 | 기본 | 설명 |
|---|---|---|
| `status` | 없음 | `pending`/`running`/`succeeded`/`skipped`/`failed` |
| `limit` | 200 | 1~1000 |

```json
[
  {
    "ref_key": "law_api:001234",
    "status": "failed",
    "last_stage": "extract",
    "failure_kind": "permanent",
    "failure_reason": "PDF produced no usable text (likely scanned image)",
    "attempt_count": 1,
    "document_id": null
  }
]
```

**`failure_kind` 3분류의 의미** (BR-41~43)
| 값 | 재시도 (같은 실행) | 재시도 (다음 실행) |
|---|---|---|
| `transient` | 예 (최대 3회, 1s·4s·16s) | 예 |
| `permanent` | 아니오 | **예** — 소스가 고쳐졌을 수 있음 |
| `policy_blocked` | 아니오 | **아니오** — 정책 재검사가 허용으로 바뀌기 전까지 |

`failure_reason` 은 저장 전에 비밀값이 마스킹됩니다 (BR-60).

---

## 4. 통계

### `GET /api/stats`
```json
{
  "documents": 1042, "chunks": 96310, "substances": 1000,
  "embedding_model": "BAAI/bge-m3", "needs_reindex": false
}
```

`embedding_model` 이 `deterministic-hash-*` 이면 오프라인 대체 구현이 활성화된 상태이며,
**벡터 검색 결과가 의미를 갖지 않습니다.**

---

## 5. HTML 화면

| 경로 | 화면 |
|---|---|
| `GET /` | 대시보드 |
| `GET /admin/sources` | 소스 목록 |
| `POST /admin/sources/{source_id}/ingest` | 폼 제출 → **303** → `/admin/jobs/{id}` |
| `GET /admin/jobs` | 작업 목록 (GET 폼 필터) |
| `GET /admin/jobs/{job_id}` | 작업 상세 (항목별 실패 사유) |
| `GET /docs` | OpenAPI |

HTML 라우트와 JSON API 는 **동일한 서비스 메서드**를 호출합니다 (DD-12).
폼 제출 후 303 리다이렉트를 쓰므로 새로고침으로 재제출되지 않습니다.

---

## 6. u2~u5 예정 엔드포인트

| 경로 | 유닛 |
|---|---|
| `POST /api/query` | u2 — 인용 답변 / 근거 부족 시 거부 |
| `GET /api/usage` | u2 — LLM 토큰·비용 집계 |
| `GET /api/substances/{term}` | u3 — 물질 안전 카드 |
| `GET /api/evaluations` | u4 — 평가 결과 |
| `POST /api/auth/register`, `/login` | u5 |
| `POST /api/documents`, `GET`, `DELETE` | u5 — 업로드 문서 |
