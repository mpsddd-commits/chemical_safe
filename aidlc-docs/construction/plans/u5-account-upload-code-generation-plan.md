# Code Generation Plan — u5-account-upload

**단계**: 🟢 CONSTRUCTION / Code Generation — 유닛 `u5-account-upload` (5/5)
**작성일**: 2026-08-30
**선행 승인**: Functional Design · NFR Design (2026-08-30)

---

## 유닛 컨텍스트

| 항목 | 내용 |
|---|---|
| **FR** | FR-27~33, FR-46, FR-47 / **BR** BR-131~152 |
| **엔터티** | 신규 1개 `user_account` + `document` 컬럼 3개 |
| **마이그레이션** | **`0004_account`** |
| **신규 의존성** | `argon2-cffi` · `PyJWT` — u2 의 `google-genai` 이후 처음 |
| **신규 컨테이너** | 없음 |

---

## 착수 전 실측 (설계 문서 대비 정정 없음)

세 가지를 확인했고 전부 문서대로다.

```
apply_scope()          owner_id IS NULL OR owner_id = :caller       구현되어 있다
Scope                  모든 검색 메서드의 필수 인자 (DD-19)
DocType.USER_UPLOAD    u1 이 미리 선언 (DD-21)
IndexingService        _index_one(..., owner_id=…) 인자를 이미 받는다
require_db_password()  기동 시 fail-fast 패턴이 이미 있다 → JWT_SECRET 에 그대로 적용
```

**u4 때와 달리 정정할 것이 없다.** 확인하는 절차는 같다.

---

## 파일 목록

### 신규 20

| 파일 | 역할 |
|---|---|
| `migrations/versions/0004_account.py` | E21 + `document` 컬럼 3 |
| `app/auth/__init__.py` · `types.py` | `AuthenticatedUser` 등 값객체 |
| `app/auth/hashing.py` | **C51** argon2id · 정책 검증 |
| `app/auth/tokens.py` | **C52** JWT 발급·검증 |
| `app/auth/ownership.py` | **C55** `scope_for` · `owned_or_404` |
| `app/uploads/__init__.py` | |
| `app/uploads/validator.py` | **C53** 5단계 검증 |
| `app/uploads/store.py` | **C54** 웹 루트 밖 저장 |
| `app/db/repositories/accounts.py` | `UserRepo` |
| `app/services/account_service.py` | **S6** |
| `app/services/document_service.py` | **S7** |
| `app/web/deps.py` | `current_user` · `require_user` · CSRF |
| `app/web/routers/auth.py` · `documents.py` · `history.py` | P8·P9·P10 |
| `app/web/templates/{login,register,documents,history}.html` | |
| `tests/unit/test_auth.py` · `test_upload_validator.py` | |
| `tests/integration/test_isolation.py` | **IP-3 ①③** |
| `tests/unit/test_scope_discipline.py` | **IP-3 ②** 정적 검사 |

### 수정 9
`pyproject.toml` · `app/core/config.py` · `app/core/logging.py` · `app/db/models.py` ·
`app/worker.py` · `app/main.py` · `docker-compose.yml` · `Dockerfile` · `.env.example`

---

## 이 단계에서 지킬 것

| 규칙 | 코드에서의 모습 |
|---|---|
| BR-131 argon2id | `argon2.PasswordHasher` 기본 파라미터 |
| BR-132 이메일 정규화 | 저장·조회 양쪽에서 `.strip().lower()` |
| BR-134 실패 미구분 | 계정이 없어도 더미 해시로 `verify` 수행 |
| BR-137 비밀키 기본값 없음 | `require_jwt_secret()` — `require_db_password()` 와 같은 형태 |
| BR-140 검증 순서 | 크기 → 매직 → 파싱 → 페이지 → 위험 요소 |
| BR-141 저장 경로 | `/data/uploads/{owner}/{uuid}.pdf`, 0700 |
| BR-142 같은 색인 경로 | 워커가 `IndexingService._index_one(owner_id=…)` |
| BR-144 하드 삭제 | DB 먼저, 파일 나중 |
| BR-145 `Scope` 단일 생성 | C55 밖 `Scope(` 금지 — 정적 테스트가 강제 |
| BR-146 404 | `owned_or_404` |
| BR-148 평가는 공개 스코프 | 정적 테스트의 허용 목록에 명시 |

---

## 검증 순서 (Build & Test 로 이월하지 않고 이 단계에서 확인)

1. 단위 테스트 — C51~C55 · 정적 검사
2. 마이그레이션 적용 → `0004_account`
3. 통합 — 두 계정 교차 접근
4. `JWT_SECRET` 없이 기동 → **실패해야 한다**
5. 공개 코퍼스 78문서가 익명에게 그대로 보이는가
6. u4 `evaluate --retrieval-only` 지표 불변

**6번을 넣는 이유**: u5 가 검색 경로를 건드리지 않는다는 주장을 **숫자로 확인**한다.
Recall@5 0.700 · MRR 0.546 이 그대로여야 한다.
