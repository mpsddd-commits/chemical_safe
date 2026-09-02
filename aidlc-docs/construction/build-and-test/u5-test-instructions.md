# u5 재현 절차 — 계정·업로드·격리

u2~u4 절차를 대체하지 않는다. u5 에서 **추가된 것만** 적는다.

| 계층 | 대상 | 기본 실행 | 무엇을 확인하는가 |
|---|---|---|---|
| 단위 | 없음 | ✅ | 해싱·토큰·업로드 검증 · **정적 격리 검사** |
| 통합 | PostgreSQL | ❌ (`-m integration`) | 격리가 실제로 새지 않는가 |
| 종단 | 실행 중인 앱 | ❌ 수동 | HTTP 로 본 격리·CSRF·백오프 |
| 로그 | `/logs/safeenv.log` | ❌ 수동 | 비밀값이 실제로 없는가 |

---

## 0. 전제

```bash
cd safeenv
```

`.env` 에 **`JWT_SECRET` 이 있어야 앱이 뜬다**(BR-137). 없으면 만든다 —
값을 화면에 찍지 말 것(NFR-14).

```bash
python -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(48))" >> .env
```

```bash
docker compose up -d
docker compose exec -T postgres psql -U safeenv -d safeenv -At -c "select version_num from alembic_version;"
# 0004_account 이어야 한다
```

---

## 1. 단위 — 618 passed, 1 skipped

```bash
python -m pytest tests/unit -q && python -m ruff check app tests
```

**NFR-28 증명** — 도달 불가 주소로 돌린다.

```bash
POSTGRES_HOST=203.0.113.1 REDIS_URL=redis://203.0.113.1:6379 python -m pytest tests/unit -q
```

### 정적 격리 검사만 따로

```bash
python -m pytest tests/unit/test_scope_discipline.py -q
```

이것이 **C55 밖에서 `Scope(` 를 만드는 코드**를 잡는다. 통합 테스트는 자기가 덮는
경로만 보므로, 새 화면이 스코프를 손으로 조립하면 이 테스트만 실패한다.
실제로 u5 개발 중 `web/routers/query.py` 를 이 검사가 찾아냈다.

---

## 2. 통합 — 53 passed, 1 skipped

```bash
export POSTGRES_PASSWORD="$(grep -m1 '^POSTGRES_PASSWORD=' .env | cut -d= -f2-)"
export POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433
python -m pytest tests/integration -m integration -q
```

`test_isolation.py` 11건이 두 계정과 각자의 문서를 **만들고 지운다**.
공개 코퍼스에 `owner_id` 를 붙여 재사용하지 않는다 — 결함 48·53 과 같은 부류를
자초하는 일이다. 마지막 두 테스트가 원복 자체를 검증한다.

---

## 3. 기동 규칙 — 비밀키가 없으면 뜨지 않는다

```bash
docker compose run --rm --no-deps -e JWT_SECRET= app python -c "from app.main import create_app; create_app()"
```

기대: `RuntimeError: JWT_SECRET 이 설정되지 않았습니다 …`

**이 유닛에서 가장 쉽게 잊히는 검증이다.** 기본값이 있으면 테스트는 통과하고
배포는 비밀 없이 나간다.

---

## 4. 종단 — 격리·CSRF·백오프

앱이 뜬 상태에서 확인한다. 계정은 `@test.invalid` 로 만들고 **끝나면 지운다**(6절).

| 확인 | 방법 | 기대 |
|---|---|---|
| CSRF | 토큰 없이/틀리게 폼 POST | **400** |
| 쿠키 | 가입 응답의 `Set-Cookie` | `HttpOnly` · `SameSite=lax` |
| 오픈 리다이렉트 | `POST /login` 에 `next=//evil.example.com` | `/` 로 |
| 백오프 | 같은 계정에 8회 연속 실패 | 7회째부터 1s → 2s |
| 잠금 없음 | 그 뒤 올바른 비밀번호 | **즉시 성공** |
| 격리 | B 로 A 의 문서 삭제·재색인·다운로드 | 전부 **404** |
| 원본 링크 | A 가 자기 원본 | **200 application/pdf** |
| 이스케이프 | 파일명에 `<img onerror=…>` | `&lt;img` 로 |

업로드 거부 5종:

| 파일 | 기대 메시지 |
|---|---|
| `MZ…` (확장자 위장) | PDF 파일이 아닙니다 (파일 시작 바이트 불일치) |
| `%PDF-1.7\nbroken` | PDF 를 읽을 수 없습니다: … |
| 정상 PDF + `/OpenAction` | 자동 실행 요소가 포함되어 있습니다 |
| 0바이트 | 빈 파일입니다 |
| 한도 초과 | 문서 수 / 저장 용량 한도 |

한도는 설정을 낮춰 확인한다(실 데이터에 50건을 올리지 않는다):

```bash
docker compose run --rm --no-deps -e UPLOAD_QUOTA_DOCUMENTS=1 app python - <<'PY'
# DocumentService.upload 를 두 번 호출하면 두 번째가 ValidationError
PY
```

---

## 5. 로그에 비밀값이 없는지 — 눈으로 본다

```bash
docker compose exec -T app python - <<'PY'
import re, io
tail = io.open("/logs/safeenv.log", encoding="utf-8", errors="replace").read()[-400000:]
pats = {
  "세션 쿠키": r"safeenv_session=[A-Za-z0-9._\-]{10,}",
  "argon2":  r"\$argon2[a-z]*\$[^\s\"']{10,}",
  "이메일":    r"\b[A-Za-z0-9._%+-]{3,}@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
  "JWT":     r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
}
for label, p in pats.items():
    print(f"{label:10s} {len(re.findall(p, tail))}건")
for event in ("isolation_denied","login_failed","login_succeeded","upload_rejected","upload_accepted"):
    print(f"{event:18s} {tail.count(event)}")
PY
```

기대: 앞 네 줄 전부 **0건**. 뒤 다섯 줄은 0이 아니어야 한다 —
**`isolation_denied` 가 0이고 로그도 없으면 격리가 도는지 알 수 없다.**

---

## 6. 정리 — 테스트가 만든 것은 테스트가 지운다

```bash
docker compose exec -T app python - <<'PY'
from sqlalchemy import select
from app.db.engine import session_scope
from app.db.models import Document, UserAccount
from app.uploads.store import UploadStore
store = UploadStore()
with session_scope() as s:
    users = list(s.scalars(select(UserAccount).where(UserAccount.email.like("%@test.invalid"))))
    ids = [u.id for u in users]
    docs = list(s.scalars(select(Document).where(Document.owner_id.in_(ids)))) if ids else []
    paths = [d.original_path for d in docs]
    for d in docs: s.delete(d)
    for u in users: s.delete(u)
for p in paths: store.delete(p)
PY
```

> 파일 삭제는 **`app` 에서** 한다. `worker` 는 `/data/uploads` 를 읽기 전용으로
> 마운트하므로 `upload_file_delete_failed` 가 난다 — 설계대로다(UP-3, BR-144).

확인:

```bash
docker compose exec -T postgres psql -U safeenv -d safeenv -At -c \
  "select count(*) from user_account; select count(*) from document; select count(*) from chunk;"
# 0 / 78 / 1633
```

---

## 7. 검색이 안 바뀌었는지 — 숫자로 확인

```bash
docker compose run --rm worker python -m app.cli evaluate --retrieval-only
```

기대: 기준선 73 대비 **전 항목 +0.000, 판정 `ok`**, `incomparable` 경고 없음.

업로드 테스트 데이터가 남아 있으면 `corpus_fingerprint 가 기준선과 다릅니다` 와
함께 `incomparable` 이 나온다. **그것도 설계대로다** — 6절을 먼저 하고 돌린다.

---

## 8. 알려진 것

| 현상 | 원인 | 정상인가 |
|---|---|---|
| 로그아웃 후에도 복사된 토큰이 동작 | 무상태 토큰, 최대 12시간 (AP-3) | ⚠️ 설계상. 무효화 없음 |
| 로그인 실패 응답 시간이 8.5ms 차 | argon2 비용 지배, 완전 동일은 아님 | ⚠️ AP-1 은 동작 |
| 스캔 PDF 업로드가 색인 실패 | 텍스트가 없다 | ✅ 화면에 사유 표시 |
| 익명 질의가 이력에 없음 | `owner_id NULL` (BR-151) | ✅ 설계 |
| `/usage` 를 로그인한 아무나 봄 | 역할 개념 없음 | ⚠️ FR 에 역할이 없다 |
