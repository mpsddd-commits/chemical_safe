# Code Generation Summary — u5-account-upload

**일자**: 2026-08-30
**FR** FR-27~33, FR-46, FR-47 / **BR** BR-131~152 / **C51~C55** / **S6·S7**

---

## 1. 산출물

### 신규 22
| 파일 | 역할 |
|---|---|
| `migrations/versions/0004_account.py` | E21 + `document` 컬럼 3 |
| `app/auth/{__init__,types}.py` | `AuthenticatedUser`·업로드 값객체 |
| `app/auth/hashing.py` | **C51** argon2id · 정책 · 더미 해시 |
| `app/auth/tokens.py` | **C52** JWT |
| `app/auth/ownership.py` | **C55** `scope_for` · `owned_document` |
| `app/uploads/{__init__,validator,store}.py` | **C53·C54** |
| `app/db/repositories/accounts.py` | `UserRepo` (+용량 집계) |
| `app/services/{account,document}_service.py` | **S6·S7** |
| `app/web/deps.py` | `current_user`·`require_user`·CSRF·쿠키 |
| `app/web/routers/{auth,documents}.py` | P8·P9·P10 |
| `app/web/templates/{login,register,documents,history}.html` | |
| `prompts` 변경 없음 | u5 는 LLM 을 쓰지 않는다 |
| `tests/unit/{test_auth,test_upload_validator,test_scope_discipline}.py` | |
| `tests/integration/test_isolation.py` | **IP-3 ①③** |

### 수정 12
`pyproject.toml`(의존성 2) · `app/core/{config,errors,logging}.py` · `app/db/models.py` ·
`app/jobs/{queue,tasks}.py` · `app/worker.py` · `app/main.py` ·
`app/web/routers/{pages,query,substances}.py` · `app/web/templates/base.html` ·
`docker-compose.yml` · `Dockerfile` · `.env.example`

---

## 2. 격리는 만든 것이 아니라 값을 넣은 것

```
로그인 → 토큰 → AuthenticatedUser → C55.scope_for() → 기존 검색·색인 경로
```

**세 파일이 안 바뀌었다** — 설계가 약속한 그대로다:

| 파일 | 변경 |
|---|---|
| `services/query_service.py` | 없음 (`scope` 인자를 이미 받는다) |
| `services/indexing_service.py` | 없음 (`owner_id` 를 이미 받는다) |
| `indexing/vector_index.py` | 없음 (`apply_scope` 가 이미 구현) |

`web/routers/query.py` 는 바뀌었는데, 그것이 **없었으면 결함이 됐을 곳**이다 —
스트리밍 질의만 공개 스코프로 하드코딩돼 있어 같은 질문에 SSR 은 내 업로드를
찾고 스트리밍은 못 찾는 상태가 됐을 것이다. 정적 검사(IP-3 ②)가 잡았다.

---

## 3. 실행하면서 드러난 것 5건

이 유닛에서 고친 것들은 전부 **문서를 읽어서가 아니라 돌려봐서** 나왔다.

### ① 마스킹 정규식에 백스페이스가 들어가 전체가 무력화될 뻔했다
편집 중 `\b` 가 실제 백스페이스 문자(0x08)로 들어가 `_SECRET_PARAM` 이 **아무것도
매칭하지 않는 상태**가 됐다. `api_key=...` 조차 그대로 로그에 남는다.
동작을 실제로 확인해서 잡았다 — 패턴을 눈으로 읽으면 정상으로 보인다.

### ② `JWT_SECRET` 이 짧아도 통과했다
PyJWT 가 테스트 중 `InsecureKeyLengthWarning` 을 냈다(11바이트 < 32).
**로그의 경고는 통제가 아니다.** `require_jwt_secret()` 이 32자 미만을 거부한다
(RFC 7518 §3.2). 라이브러리가 말해 주고 있었고 아무도 읽지 않았다.

### ③ 로그인 리다이렉트에 Location 헤더가 없었다
`require_user` 가 `HTTPException(303)` 을 던지는데 FastAPI 는 그것을 JSON 본문으로
렌더한다 — **303 인데 갈 곳이 없다.** 브라우저는 그대로 멈춘다.
`create_app` 에 예외 핸들러를 붙여 `/login?next=...` 로 보낸다.

### ④ 색인 실패가 사용자에게 보이지 않았다
빈 PDF 를 올려 확인했다: `ExtractionError: PDF produced no usable text` 가
워커 로그에만 남고 문서는 청크 0으로 남아, 화면은 **영원히 "색인 중"** 이라고 말한다.
FQ7-6 이 "상태만 표시"라고 정했는데 표시할 상태가 없었다.
→ 업로드마다 `job` + `job_item` 을 만들어 u1 의 FR-6·FR-8 기계를 그대로 쓴다.
지금은 이렇게 보인다:
```
⛔ 색인 실패   PDF produced no usable text (likely scanned image)
```
**스캔 MSDS 는 흔하다.** 이것은 예외가 아니라 평범한 경우다.

### ⑤ 워커의 읽기 전용 마운트가 실제로 강제된다
정리 스크립트를 워커에서 돌렸더니 `upload_file_delete_failed` — 설계대로다(UP-3).
삭제는 `app` 의 일이고(BR-144), 워커에 쓰기 권한이 없다는 것이 실측으로 확인됐다.

---

## 4. 검증 (Build & Test 로 미루지 않고 이 단계에서 수행)

| # | 항목 | 결과 |
|---|---|---|
| 1 | 단위 | **618 passed, 1 skipped** (u4 시점 573 → +45) |
| 2 | 마이그레이션 | `0003_evaluation` → **`0004_account`** 적용 |
| 3 | 통합 (실 DB) | **53 passed, 1 skipped** (40 → +13) |
| 4 | `JWT_SECRET` 없이 기동 | **RuntimeError 로 실패** — 메시지에 규칙 근거 포함 |
| 5 | 공개 코퍼스 불변 | 익명 조회 정상 · **78문서 / 1,633청크 그대로** |
| 6 | u4 지표 불변 | Recall@5 0.700 · MRR 0.546 · 거부 0.400 — **전 지표 +0.000, 판정 `ok`** |
| 7 | 가입→로그인→업로드→목록 | 종단 통과 |
| 8 | 교차 접근 | B 의 목록에 A 문서 없음 · 남의 문서 조회 404 |
| 9 | 업로드 거부 | 위장·크기·페이지·`/OpenAction`·손상 5종 |
| 10 | 볼륨·권한 | `/data/uploads` **700 appuser** (NFR-30) |

**6번이 이 유닛의 핵심 증거다.** "검색 경로를 건드리지 않았다"는 주장을 숫자로
확인했고, 정확히 같은 값이 나왔다.

> 검증 중 만든 테스트 계정 4개와 업로드 2건은 삭제했다. `user_account` 0행,
> 문서 78, 청크 1,633 — 착수 전과 같다. 결함 48·53 에서 배운 습관이다.

---

## 5. 격리 증명 세 겹 (IP-3)

| 겹 | 파일 | 무엇을 잡는가 |
|---|---|---|
| ① 교차 접근 | `tests/integration/test_isolation.py` | 실제로 새는지 (키워드 경로·문서 조회) |
| ② 정적 검사 | `tests/unit/test_scope_discipline.py` | **C55 밖의 `Scope(` 생성** |
| ③ 경로별 | 위 통합 테스트 안 | 익명·본인·타인 각각의 결과 |

②는 실제로 일을 했다 — `web/routers/query.py` 의 하드코딩된 공개 스코프를
이 테스트가 찾아냈다. 통합 테스트만 있었다면 그 경로를 덮는 테스트가 없어
**통과했을 것이다.**

②는 u4 평가도 지킨다: `evaluation_service.py` 는 허용 목록에 있되
`Scope.public()` 만 쓰도록 별도로 고정된다(BR-148).

---

## 6. 미충족 · 정직하게 남기는 것

| 항목 | 상태 |
|---|---|
| **탈취 토큰** | 최대 **12시간 유효**. 서버 측 무효화 없음(AP-3). "무효화 지원" 아님 |
| **무차별 대입** | 지수 백오프는 **늦출 뿐 막지 않는다**. 분산·저빈도 시도에 무력 |
| **업로드 검증** | 안티바이러스 아님. 시그니처 미탐지, 새 `pypdf` 취약점 못 막음 — **파싱 자체가 공격면** |
| **`/usage`** | **관리자 전용**(B2, 2026-09-04). u5 시점에는 인증 없음이었다 — 이 줄은 원래 "로그인만 요구"라고 잘못 적혀 있었고, 2026-09-02 실측이 그것을 뒤집었다. 남은 구멍: **`/api/usage` 는 아직 익명 200** 이며 같은 수치를 준다 |
| **익명 질의 이력** | `owner_id NULL` 이라 **아무의 이력도 아니다**. 화면에 안 나온다(BR-151의 대가) |
| **이메일 중복 검사** | 가입 폼은 존재 여부를 알려 준다. 가입이 그것을 필요로 한다 — 로그인 쪽만 닫았다 |
| **비밀번호 재설정·계정 삭제** | FR 에 없다. 만들지 않았다 |
