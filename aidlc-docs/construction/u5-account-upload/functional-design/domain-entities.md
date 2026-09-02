# Domain Entities — u5-account-upload

**FR**: FR-27~33, FR-46, FR-47
**신규 테이블 1개** — `user_account`. 마이그레이션 `0004_account`.
`document` 에 업로드용 컬럼 3개를 더한다. **u1~u4 의 다른 테이블은 바뀌지 않는다.**

---

## 0. 격리는 이미 스키마에 있다

u5 를 시작하기 전에 확인한 것이다.

```
owner_id 컬럼:  document · chunk · query_log     (전부 항상 NULL)
apply_scope():  owner_id IS NULL  OR  owner_id = :caller
Scope:          모든 검색 메서드의 필수 인자 (DD-19)
DocType:        USER_UPLOAD = "user_upload"      ← u1 이 미리 선언해 둔 것 (DD-21)
```

**FR-28 의 질의 경로는 구현되어 있다.** 이 유닛은 `owner_id` 에 **값을 넣는다**.
격리 로직을 새로 만드는 것이 아니므로, 격리의 위험은 "새 코드가 틀릴 위험"이 아니라
**"어딘가에서 `Scope` 를 안 만들어 넘길 위험"** 이다. BR-145 와 C55 가 그것을 겨냥한다.

---

## 1. `user_account` — E21

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `id` | PK | `owner_id` 가 참조하는 값 |
| `email` | varchar(320), **UNIQUE** | 로그인 식별자. 저장 시 소문자로 정규화 |
| `password_hash` | varchar(255) | **argon2id**. 평문·가역 암호화 금지 (NFR-11) |
| `disclaimer_version` | varchar(16) | 동의한 면책 문구 버전 (FR-34) |
| `disclaimer_agreed_at` | timestamptz | 동의 시각 |
| `created_at` | timestamptz | |
| `last_login_at` | timestamptz, NULL | |
| `failed_attempts` | integer, default 0 | **NFR Design 에서 추가** — AP-2 지수 백오프 |
| `last_failed_at` | timestamptz, NULL | 〃 |

인덱스: `email` UNIQUE 하나면 충분하다. 로그인은 이메일로만 조회한다.

### 이메일을 소문자로 정규화하는 이유
`A@x.com` 으로 가입하고 `a@x.com` 으로 로그인하는 것을 사용자는 같은 계정이라고
생각한다. UNIQUE 제약이 대소문자를 구분하면 **같은 사람이 두 계정을 가질 수 있고**,
그 순간 한쪽 계정의 업로드 문서가 다른 쪽에서 안 보인다 — 격리 버그처럼 보이지만
원인은 여기다.

### `failed_attempts` 는 FD 이후에 늘었다
NFR Design 에서 AP-2(지수 백오프)를 정하며 생긴 컬럼이다. 계정 잠금이 아니라
**지연**이므로 상태는 두 컬럼이면 되고, 성공하면 0으로 되돌린다.
잠금을 쓰지 않은 이유는 `nfr-design-patterns.md` AP-2 에 있다 — 공격자가 이메일만
알면 남의 계정을 잠글 수 있어 **방어가 서비스 거부 도구**가 된다.

### 비밀번호 정책은 컬럼이 아니다
FR-33 의 "최소 길이·복잡도"는 C51 의 검증 규칙이고 스키마에 남기지 않는다.
정책이 바뀌면 기존 해시는 그대로 유효해야 한다.

### `disclaimer_*` 를 별도 테이블로 두지 않는 이유
FR-34 는 "**1회** 동의, 동의 기록 저장"이다. 계정당 한 행이면 문장 그대로다.
문구가 개정되면 재동의 이력이 필요해지겠지만 **개정 절차가 아직 없다** — 없는
절차를 위해 테이블을 만들지 않는다. `disclaimer_version` 을 남겨 두었으므로
필요해지면 이력 테이블로 옮길 수 있다.

> ⚠️ 익명 사용자는 계정이 없으므로 이 동의를 남기지 못한다. 익명에 대한 고지는
> **화면의 상시 면책 표시(FR-35, BR-84)** 가 전부다. 숨기지 않고 적는다.

---

## 2. `document` 확장 — 업로드 문서도 문서다

업로드 문서를 위한 **별도 테이블을 만들지 않는다.** 만들면 검색·색인·인용이 두
갈래가 되고, u4 가 DD-22 로 피한 것과 같은 종류의 분기가 생긴다.

추가 컬럼 3개:

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `upload_filename` | varchar(255), NULL | **원본 파일명은 여기에만** 산다 (NFR-13) |
| `upload_size_bytes` | integer, NULL | 목록 화면과 한도 검증 기록 |
| `upload_page_count` | integer, NULL | 〃 |

기존 컬럼이 업로드에서 갖는 의미:

| 컬럼 | 업로드 문서에서 |
|---|---|
| `owner_id` | **업로더의 `user_account.id`.** 공개 문서는 계속 NULL |
| `doc_type` | `user_upload` (u1 이 이미 선언) |
| `source_id` | **NULL** — 수집 소스가 아니다 |
| `external_id` | 업로드 UUID |
| `original_path` | `/data/uploads/{owner_id}/{uuid}.pdf` |
| `source_url` | `/documents/{uuid}` — 앱 자신의 경로 |

### `source_url` 이 NOT NULL 이라 값을 정해야 했다
업로드 문서에는 URL 이 없다. 세 가지를 놓고:

| 후보 | 문제 |
|---|---|
| `upload://{uuid}` | 인용 화면에서 **깨진 링크**로 렌더된다 |
| 빈 문자열 | NOT NULL 을 형식적으로만 만족시킨다 |
| **`/documents/{uuid}`** | 소유자가 실제로 열어볼 수 있다 |

세 번째를 택한다. u2·u3 는 "모든 값에 **확인 가능한** 출처가 붙는다"(BR-105)를
지켜 왔고, 소유자에게 열리는 경로는 그 조건을 만족한다. 타인에게는 404 다 —
그것이 격리다.

### UNIQUE (source_id, external_id) 는 업로드에서 일을 하지 않는다
`source_id` 가 NULL 이면 PostgreSQL 은 그 튜플을 비교하지 않는다. 즉 업로드 문서
사이의 중복은 이 제약이 막지 못한다. **UUID 충돌 확률이 무시할 만하므로 새 제약을
추가하지 않되, 제약이 지켜 주고 있다고 착각하지 않도록 적어 둔다.**

---

## 3. 값 객체

```python
@dataclass(frozen=True)
class AuthenticatedUser:      # C52 가 토큰에서 복원한다
    id: int
    email: str

    @property
    def scope(self) -> Scope:  # C55 - 서비스는 이것만 만든다
        return Scope(owner_id=self.id)

@dataclass(frozen=True)
class UploadCandidate:        # C53 이 검증하는 대상
    filename: str
    content_type: str
    size_bytes: int
    data: bytes

@dataclass(frozen=True)
class UploadVerdict:          # C53 의 판정
    accepted: bool
    page_count: int | None
    reason: str | None        # 거부 사유를 사용자에게 그대로 보여준다

@dataclass(frozen=True)
class StoredUpload:           # C54 의 결과
    uuid: str
    path: Path
    size_bytes: int
```

### `AuthenticatedUser.scope` 가 프로퍼티인 이유
격리의 유일한 실패 모드는 **`Scope` 를 안 만들거나 잘못 만드는 것**이다.
`Scope(owner_id=user.id)` 를 호출부마다 손으로 쓰면 한 곳에서 틀릴 수 있다.
사용자 객체가 자기 스코프를 알고 있으면 틀릴 자리가 하나로 줄어든다.

---

## 4. 마이그레이션 `0004_account`

- `user_account` 생성 (email UNIQUE, `failed_attempts` default 0)
- `document` 에 `upload_filename` · `upload_size_bytes` · `upload_page_count` 추가
  (전부 nullable — 기존 78행은 그대로 유효하다)
- **기존 데이터 변경 없음.** 공개 코퍼스 78문서는 `owner_id IS NULL` 을 유지하고
  계정이 생겨도 계속 모두에게 보인다
- 다운그레이드: 컬럼 3개 DROP + `user_account` DROP

`document.owner_id` 에 FK 를 걸지 **않는다**: 이미 `Integer` 로 존재하고, FK 를 지금
추가하면 계정 삭제가 문서 삭제로 이어지는 정책을 여기서 정해야 한다. **계정 삭제는
FR 에 없다** — 없는 기능의 캐스케이드를 미리 정하지 않는다.
