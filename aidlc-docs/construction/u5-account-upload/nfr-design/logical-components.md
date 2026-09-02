# Logical Components — u5-account-upload

C51~C55 의 배치, 의존성 방향, 인증 의존성 체인, 신규 환경변수·볼륨.

**신규 컨테이너는 없다.** u2 의 `reranker` 와 달리 이 유닛은 기존 `app`·`worker`
안에서 끝난다.

---

## 1. 신규 애플리케이션 컴포넌트

| # | 컴포넌트 | 위치 | 의존 | DB |
|---|---|---|---|---|
| C51 | `PasswordHasher` | `app/auth/hashing.py` | argon2-cffi | ❌ |
| C52 | `TokenService` | `app/auth/tokens.py` | PyJWT, `Settings` | ❌ |
| C53 | `UploadValidator` | `app/uploads/validator.py` | pypdf | ❌ |
| C54 | `UploadStore` | `app/uploads/store.py` | pathlib | ❌ |
| C55 | `OwnershipFilter` | `app/auth/ownership.py` | `Scope`, `Document` | 조회만 |

**C51~C54 는 DB 에 닿지 않는다.** 순수 함수에 가깝게 두어 단위 테스트가
DB·네트워크 없이 돈다(NFR-28) — u4 가 C45·C46·C48 을 그렇게 둔 것과 같다.

### 패키지를 둘로 나누는 이유
`app/auth/` 와 `app/uploads/` 는 서로 모른다. 인증은 업로드를 몰라도 되고,
업로드 검증은 누가 올렸는지 몰라도 된다 — **소유자를 아는 것은 서비스(S7)의 일**이다.
섞으면 C53 을 테스트하는 데 사용자가 필요해진다.

---

## 2. 인증 의존성 체인 (FQ7-2=a)

```
요청
 └─ Cookie: session=<jwt>
     └─ current_user()  ──→ C52.verify() ──→ AuthenticatedUser | None
         ├─ 익명 허용 화면 (P5 질의 · P7 물질)      → None 그대로 통과
         └─ require_user()                          → None 이면 /login 리다이렉트
             └─ P9 문서 · P10 이력 · P6 사용량
```

**두 종류인 이유는 BR-151 이다.** 질의·물질 화면은 익명을 허용하고 문서·이력은
아니다. 하나로 합치면 어느 쪽이든 **틀린 기본값**을 갖는다 — 익명 허용이 기본이면
새 화면이 보호되지 않고, 인증 필수가 기본이면 공개 질의가 사라진다.

미들웨어를 쓰지 않은 이유: 예외 목록을 유지해야 하고, **예외 목록은 화면이 늘 때마다
잊힌다.**

### `Scope` 로 가는 유일한 길

```
AuthenticatedUser | None
        │
        ▼
C55.scope_for(user)  ────►  Scope(owner_id=…)  또는  Scope.public()
        │
        ▼
QueryService.answer(question, scope)      ← u2, 무변경
Retrievers.vector/keyword(…, scope)       ← u1, 무변경
SubstanceService.card(…)                  ← u3
```

**`Scope(` 를 직접 부르는 코드는 C55 안에만 있다.** 정적 검사가 그것을 강제한다
(IP-3 ②). 예외는 두 곳뿐이고 둘 다 명시적이다:
- `Scope.public()` — u4 평가(BR-148)
- 테스트

---

## 3. 서비스 배치

```
web/routers/auth.py      → S6 AccountService   → C51 · C52 · UserRepo
web/routers/documents.py → S7 DocumentService  → C53 · C54 · C55 · DocumentRepo · TaskQueue
web/routers/history.py   → S6.query_history    → C55 · QueryRepo
```

### S7 이 `IndexingService` 를 직접 부르지 않는다
업로드는 잡을 큐에 넣고 끝난다(BR-143). 워커가 `IndexingService._index_one(...,
owner_id=...)` 를 부른다 — **u1 의 색인 경로 그대로**이고, 이 유닛은 인자 하나를
더할 뿐이다(BR-142).

```
app 컨테이너                     worker 컨테이너
 S7.upload()                      run_index_upload(job_id, document_id)
   C53.validate()                   IndexingService._index_one(owner_id=…)
   C54.save()                         → chunk.owner_id = owner_id
   document INSERT
   TaskQueue.enqueue()  ──arq──►
```

---

## 4. 신규 환경변수 (NFR-23)

| 변수 | 기본값 | 비고 |
|---|---|---|
| `JWT_SECRET` | **없음** | 비어 있으면 **기동 실패** (BR-137) |
| `JWT_EXPIRE_HOURS` | 12 | BR-136 |
| `UPLOADS_DIR` | `/data/uploads` | |
| `UPLOAD_MAX_BYTES` | 20971520 | 20MB (BR-139) |
| `UPLOAD_MAX_PAGES` | 200 | 〃 |
| `UPLOAD_QUOTA_BYTES` | 209715200 | 사용자당 200MB (UP-4) |
| `UPLOAD_QUOTA_DOCUMENTS` | 50 | 〃 |
| `LOGIN_BACKOFF_AFTER` | 5 | AP-2 |
| `LOGIN_BACKOFF_MAX_SECONDS` | 30 | 〃 |
| `COOKIE_SECURE` | false | 운영에서 true. 로컬 HTTP 개발을 막지 않기 위한 기본값 |
| `DISCLAIMER_VERSION` | `1.0.0` | BR-152 의 기록 대상 |

**`JWT_SECRET` 에 기본값을 두지 않는 것이 규칙이다.** 개발용 기본값은 배포까지
따라가고, **기본값이 있는 비밀키는 비밀이 아니다.** BR-02(인증키 없으면 잡을 만들지
않는다)와 같은 태도이며, `Settings` 는 u1 부터 이 방식(fail fast)을 써 왔다.

---

## 5. 신규 볼륨 (NFR-31, FQ7-4=a)

```yaml
volumes:
  safeenv_uploads:
    name: safeenv_uploads

app:     - safeenv_uploads:/data/uploads          # 쓰기 (업로드)
worker:  - safeenv_uploads:/data/uploads:ro       # 읽기 (색인·재색인)
```

- `Dockerfile` 의 `mkdir -p /data/originals /logs /models` 에 `/data/uploads` 추가,
  `appuser` 소유 (NFR-30)
- 디렉터리 퍼미션 0700 — 컨테이너 안에서도 다른 사용자가 열 수 없다
- **`worker` 가 읽기 전용인 이유**: 색인은 파일을 바꾸지 않는다. 쓰기 권한을 주면
  워커의 버그가 사용자 파일을 손상시킬 수 있다. 삭제(BR-144)는 `app` 이 한다

> ⚠️ 재색인은 보관된 업로드 파일에서 다시 읽는다 — u1 의 BR-44(원본 보관)와 같은
> 구조다. 파일이 없으면 재색인은 실패하고, 그 실패가 화면에 보인다(FQ7-6=a).

---

## 6. 데이터 요소 추가

| 테이블 | 컬럼 | 용도 |
|---|---|---|
| `user_account` (신규) | `id`·`email`·`password_hash`·`disclaimer_version`·`disclaimer_agreed_at`·`created_at`·`last_login_at` | E21 |
| `user_account` | **`failed_attempts`·`last_failed_at`** | AP-2 지수 백오프 |
| `document` | `upload_filename`·`upload_size_bytes`·`upload_page_count` | 목록 화면·한도 |

**`failed_attempts` 는 FD 이후에 늘어난 컬럼이다.** NFR Design 에서 AP-2 를 정하며
생겼고, `domain-entities.md` 의 표에 없다 — Code Generation 에서 두 문서를 맞춘다.

용량 한도(UP-4)는 컬럼을 추가하지 않는다: `SUM(upload_size_bytes) WHERE owner_id=?`
로 계산한다. **집계 컬럼을 두면 삭제·실패 경로마다 갱신을 잊을 수 있고**, 잊으면
한도가 실제와 어긋난 채 조용히 동작한다.

---

## 7. 컴포넌트 상호작용 — 업로드 한 건

```
1. POST /documents        CSRF 검증 (AP-4)
2. require_user()         → AuthenticatedUser
3. 용량 한도 조회          SUM(upload_size_bytes) + COUNT  →  초과면 거부 (UP-4)
4. C53.validate()         5단계. 거부면 이유와 함께 반환, 저장하지 않음 (UP-1·UP-2)
5. C54.save()             /data/uploads/{owner}/{uuid}.pdf   0700
6. document INSERT        owner_id · doc_type=user_upload · source_id=NULL
                          source_url=/documents/{uuid}
7. TaskQueue.enqueue()    비동기 색인 (BR-143)
8. 302 → /documents       상태는 job 진행률로 (FR-6 재사용)
```

**3번이 4번보다 먼저인 이유**: 한도를 넘은 사용자에게 20MB 파싱을 수행할 이유가 없다.
**4번이 5번보다 먼저인 이유**: 거부된 파일이 디스크에 남으면 그것이 저장소가 된다.

---

## 8. 검증 방법 (Build & Test 로 이월)

| 항목 | 방법 | 기대 |
|---|---|---|
| 격리 ① 교차 접근 | 두 계정, 각자 문서 업로드 → 상대 문서 검색·조회·삭제 시도 | 검색 결과 0 · 조회 404 · 삭제 404 |
| 격리 ② 정적 | `Scope(` 사용처 grep | C55·평가·테스트 외 **0건** |
| 격리 ③ 경로별 | 벡터·키워드·물질·이력 각각 `owner_id` 필터 단위 테스트 | 전부 적용 |
| 공개 코퍼스 불변 | 익명으로 질의 | 78문서 그대로 (BR-147) |
| u4 평가 불변 | `Scope(owner_id=None)` 고정 | 지표 변화 없음 (BR-148) |
| 로그인 타이밍 | 존재/부재 계정 응답 시간 분포 | 유의한 차이 없음 (AP-1) |
| 업로드 거부 5종 | 확장자 위장·크기·페이지·`/OpenAction`·손상 | 전부 거부 + 이유 표시 |
| 용량 한도 | 200MB 초과·51번째 문서 | 거부 + 이유 |
| 마스킹 | 실제 로그 육안 확인 | 쿠키·이메일·해시 없음 (OP-2) |
| 볼륨·권한 | 컨테이너 내 `stat /data/uploads` | `appuser` · 0700 (NFR-30) |
| `JWT_SECRET` 없음 | 빈 값으로 기동 | **기동 실패** + 명확한 메시지 (BR-137) |

**마지막 줄이 이 유닛에서 가장 쉽게 잊히는 검증이다** — 기본값이 있으면 테스트는
통과하고 배포는 비밀 없이 나간다.
