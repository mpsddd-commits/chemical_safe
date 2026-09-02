# Frontend Components — u1-ingestion-index

**단계**: 🟢 CONSTRUCTION / Functional Design
**작성일**: 2026-08-20
**대상 FR**: FR-48 (운영 화면), FR-6 (진행률 조회), FR-43 (헬스체크 표시)

> **렌더링 방식** (DD-17, Q21=A): Jinja2 **서버사이드 렌더링**.
> JavaScript 는 자동 새로고침과 토글에만 사용하며, **JS 없이도 모든 정보 열람이 가능**해야 합니다.

---

## 1. 화면 구성 및 라우트

| 라우트 | 화면 | 목적 | u1 도입 |
|---|---|---|---|
| `/` | 대시보드 | 시스템 상태 요약 | ✅ |
| `/admin/sources` | **소스 목록** | 소스별 정책 상태·마지막 수집 시각, 수집 실행 | ✅ |
| `/admin/jobs` | **작업 목록** | 작업 상태·진행률 | ✅ |
| `/admin/jobs/{id}` | **작업 상세** | 항목별 성공/실패/사유 | ✅ |
| `/healthz` | 헬스체크 (JSON) | 앱·DB·큐·워커 상태 | ✅ |
| `/query` | 질의 화면 | — | u2 |
| `/substances` | 물질 카드 | — | u3 |
| `/admin/evaluations` | 평가 결과 | — | u4 |
| `/admin/usage` | LLM 사용량 | — | u2 |
| `/documents`, `/history` | 문서 관리·이력 | — | u5 |

**u1 시점의 `/admin` 은 탭 구조**로 만들고, u2·u4가 각자의 탭을 추가합니다
(`unit-of-work.md` §6 FR-48 고지 참조).

---

## 2. 컴포넌트 계층

```
BaseLayout                      (공통 레이아웃)
├── SiteHeader                  네비게이션 + 헬스 인디케이터
├── AdminTabs                   소스 / 작업  (u2: 사용량, u4: 평가 탭 추가)
└── {page content}

Dashboard
├── HealthPanel                 앱·DB·큐·워커 상태
└── StatsPanel                  문서 수, 청크 수, 물질 수, 최근 작업 요약

SourceListPage
├── SourceTable
│   └── SourceRow               소스 1건
│       ├── PolicyBadge         allowed / blocked / unknown
│       └── IngestForm          수집 실행 폼
└── PolicyNotice                차단 소스 안내

JobListPage
├── JobFilterForm               상태·종류 필터
├── JobTable
│   └── JobRow
│       ├── StatusBadge         pending / running / succeeded / partial / failed
│       └── ProgressBar         진행률
└── Pagination

JobDetailPage
├── JobSummaryCard              종류·파라미터·상태·소요시간·카운터
├── ItemFilterTabs              전체 / 성공 / 건너뜀 / 실패
├── JobItemTable
│   └── JobItemRow
│       ├── ItemStatusBadge
│       └── FailureDetail       failure_kind, failure_reason, attempt_count, last_stage
└── AutoRefreshToggle           running 상태일 때만 표시
```

---

## 3. 컴포넌트 상세

### 3.1 `HealthPanel`

| 항목 | 내용 |
|---|---|
| **데이터** | `GET /healthz` → `{app, db, queue, worker}` 각각 `ok` \| `degraded` \| `down` |
| **표시** | 4개 항목의 상태 배지. 하나라도 비정상이면 상단에 경고 띠 |
| **worker 판정** | 마지막 하트비트가 `WORKER_STALE_THRESHOLD` 초과 시 `down` (BR-52) |
| **상호작용** | 없음 (읽기 전용) |

### 3.2 `SourceRow` + `PolicyBadge`

| 항목 | 내용 |
|---|---|
| **데이터** | `source_id`, `name`, `doc_type`, `policy_status`, `policy_checked_at`, `last_collected_at`, `requires_api_key`, `api_key_configured`(파생) |
| **PolicyBadge** | `allowed` 녹색 / `blocked` 회색 + 사유 툴팁 / `unknown` 노란색 |
| **비활성 조건** | `policy_status = blocked` **또는** `requires_api_key = true` 이면서 키 미설정 → **수집 버튼 비활성화 + 사유 표시** (BR-02, BR-03) |

> **⚠️ 화면 규칙**: 차단된 소스의 수집 버튼은 **비활성이어야 하며**, 강제 실행 옵션을 제공하지 않습니다 (BR-04).

### 3.3 `IngestForm`

| 항목 | 내용 |
|---|---|
| **필드** | `source_id`(hidden), `since`(date, 선택 — 비우면 `last_collected_at` 사용) |
| **제출** | `POST /api/sources/{source_id}/ingest` → `{job_id}` |
| **성공 후** | `/admin/jobs/{job_id}` 로 리다이렉트 (**303 See Other** — 새로고침 시 재제출 방지) |
| **검증** | ① `since` 는 미래 날짜 불가 ② `since` 는 ISO 날짜 형식 ③ 서버 측 재검증 필수 (NFR-17) |
| **오류 표시** | 인증키 미설정 시 "인증키 미설정: `{env_name}` 환경변수를 설정하세요" (BR-02) |

### 3.4 `ProgressBar`

| 항목 | 내용 |
|---|---|
| **계산** | `(success + skipped + failure) / total` (BR-50) |
| **`total = 0`** | 0% 표시 + "대상 없음" 문구 |
| **색상** | `succeeded` 녹색 / `partial` 주황 / `failed` 적색 / `running` 파랑(애니메이션 없음) |
| **접근성** | 숫자 값을 **텍스트로도 함께 표시** — 색상만으로 정보를 전달하지 않음 |

### 3.5 `JobItemRow` + `FailureDetail`

| 항목 | 내용 |
|---|---|
| **데이터** | `ref_key`, `status`, `last_stage`, `failure_kind`, `failure_reason`, `attempt_count`, `document_id` |
| **성공 항목** | `ref_key` + 문서 링크 |
| **건너뜀 항목** | "변경 없음" 문구 (BR-11) |
| **실패 항목** | `failure_kind` 배지 + 사유 + 시도 횟수 + 마지막 단계 |
| **`policy_blocked`** | 별도 배지와 함께 "정책상 수집 불가 — 재시도하지 않음" 명시 (BR-43) |
| **긴 `ref_key`** | 말줄임 표시하되 `title` 속성으로 전문 제공 |

> **이 화면이 u1의 핵심 시연 요소입니다.** 부분 실패가 발생했을 때 **무엇이 왜 실패했는지**를
> 사용자가 화면에서 진단할 수 있어야 FR-8이 실제로 충족됩니다.

### 3.6 `AutoRefreshToggle`

| 항목 | 내용 |
|---|---|
| **표시 조건** | `job.status = running` 인 경우에만 |
| **동작** | 기본 켜짐. `REFRESH_INTERVAL`(기본 5초)마다 페이지 새로고침 |
| **구현** | 최소 바닐라 JS. **JS 미동작 시에도 수동 새로고침으로 동일 정보 열람 가능** (DD-17) |
| **종료** | 상태가 종료 상태로 바뀌면 자동으로 중지 |

### 3.7 `JobFilterForm`

| 항목 | 내용 |
|---|---|
| **필드** | `status`(다중 선택), `kind`(단일 선택), `limit`(기본 25) |
| **제출** | `GET /admin/jobs?status=...&kind=...` — **폼 GET 방식**이므로 JS 불필요 |
| **검증** | 허용된 enum 값만 수용. 그 외 값은 무시하고 기본값 적용 (NFR-17) |

---

## 4. API 연동 지점

| 컴포넌트 | 엔드포인트 | 메서드 | 서비스 |
|---|---|---|---|
| `HealthPanel` | `/healthz` | GET | C58 `HealthCheck` |
| `StatsPanel` | `/api/stats` | GET | S2 (집계 조회) |
| `SourceTable` | `/api/sources` | GET | S1 `list_sources()` |
| `IngestForm` | `/api/sources/{id}/ingest` | POST | S1 `start()` |
| `JobTable` | `/api/jobs?status=&kind=&limit=` | GET | S1 (작업 목록) |
| `JobSummaryCard` | `/api/jobs/{id}` | GET | S1 `job_status()` |
| `JobItemTable` | `/api/jobs/{id}/items?status=` | GET | S1 (항목 목록) |

**HTML 라우트는 위 API 와 동일한 서비스 메서드를 호출**하며, 라우터에서 템플릿으로 렌더합니다.
API 는 JSON, HTML 라우트는 페이지를 반환합니다 (DD-12 Thin router).

---

## 5. 폼 검증 규칙

| 폼 | 필드 | 규칙 | 실패 시 |
|---|---|---|---|
| `IngestForm` | `since` | ISO 8601 날짜, 미래 불가 | 필드 하단 오류 메시지, 폼 값 유지 |
| `IngestForm` | `source_id` | 존재하고 `enabled = true` | "사용할 수 없는 소스입니다" |
| `JobFilterForm` | `status` | `JobStatus` enum 값 | 무시하고 기본값 적용 |
| `JobFilterForm` | `limit` | 1~100 정수 | 범위 밖이면 기본값 25 |

**모든 검증은 서버 측에서 수행합니다.** 클라이언트 검증은 보조 수단일 뿐이며,
서버 검증을 생략하지 않습니다 (NFR-17).

---

## 6. 상태 표시 규칙

| 상태 | 배지 문구 | 색상 | 부가 표시 |
|---|---|---|---|
| `pending` | 대기 | 회색 | — |
| `running` | 진행 중 | 파랑 | 진행률 |
| `succeeded` | 완료 | 녹색 | 소요 시간 |
| `partial` | **부분 완료** | 주황 | 실패 건수 강조 |
| `failed` | 실패 | 적색 | 실패 사유 요약 |
| `skipped` (항목) | 변경 없음 | 연회색 | — |

**접근성**: 모든 상태는 **색상 + 텍스트**로 전달합니다. 색상만으로 구분하지 않습니다.

---

## 7. 화면 흐름

```
/admin/sources
   [수집 실행] 클릭
      -> POST /api/sources/{id}/ingest
      -> 303 리다이렉트
/admin/jobs/{job_id}
   자동 새로고침 (running 동안)
      -> 진행률 갱신
   상태 종료 시 자동 새로고침 중지
   [실패] 탭 클릭
      -> 실패 항목별 failure_kind / reason / last_stage 확인
   [문서 보기] 클릭 (성공 항목)
      -> 문서 상세 (u1 시점에는 메타 + 섹션 목록 + 청크 수)
```

---

## 8. u2~u5 확장 지점

| 유닛 | 추가 화면 | 기존 구조 재사용 |
|---|---|---|
| u2 | `/query`, `/admin/usage` | `BaseLayout`, `AdminTabs`, `StatusBadge` |
| u4 | `/admin/evaluations` | `AdminTabs`, `ProgressBar`(평가 진행률) |
| u3 | `/substances` | `BaseLayout` |
| u5 | `/documents`, `/history`, 로그인 | `BaseLayout`, `JobItemTable`(업로드 처리 상태) |

**`AdminTabs` 는 u1에서 확장 가능한 구조로 만듭니다** — u2·u4가 탭을 추가할 때
레이아웃을 재작성하지 않도록 합니다.

---

## 9. u1 시점의 비적용 사항

| 항목 | 상태 | 도입 유닛 |
|---|---|---|
| 로그인·인증 | **없음** — 운영 화면이 무인증으로 노출됨 | u5 |
| 면책 고지 | 없음 | u2 |
| 검색·질의 UI | 없음 | u2 |

> **⚠️ 보안 고지**: u1 시점의 `/admin` 은 인증이 없습니다. `127.0.0.1` 루프백 바인딩(NFR-18)이
> 유일한 접근 통제이며, 이는 Infrastructure Design에서 확정합니다.
> u5에서 인증이 도입되면 `/admin` 을 인증 필수 경로로 전환합니다.
