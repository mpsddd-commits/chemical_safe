# Business Logic Model — u5-account-upload

**컴포넌트** C51~C55 · **서비스** S6 `AccountService`, S7 `DocumentService` ·
**워크플로** W19~W24

---

## 0. 이 유닛이 실제로 하는 일

격리 로직은 이미 있다. 이 유닛은 **`owner_id` 에 값이 들어가는 경로**를 만든다.

```
로그인 → 토큰 → 인증된 사용자 → Scope(owner_id=id) → 기존 검색·색인 경로
                                    ↑
                            여기서 값이 생긴다
```

그래서 위험은 "새 격리 코드가 틀릴 위험"이 아니라 **"어딘가에서 `Scope` 를 안
만들거나 잘못 만들 위험"** 이다. C55 와 BR-145 가 그 하나를 겨냥한다.

---

## 1. 컴포넌트

### C51 `PasswordHasher` (FR-33, NFR-11, BR-131·BR-133)
```python
hash(password: str) -> str
verify(password: str, stored: str) -> bool
validate_policy(password: str) -> None      # 위반 시 예외, 메시지는 사용자용
```
- argon2id, 라이브러리 기본 파라미터
- `verify` 는 **존재하지 않는 계정에도 호출된다**(BR-134) — 더미 해시 상수를 둔다
- 순수하다. DB·네트워크 없음 → 단위 테스트 (NFR-28)

### C52 `TokenService` (FR-31, NFR-12, BR-135~BR-137)
```python
issue(user_id: int, email: str) -> str
verify(token: str) -> AuthenticatedUser | None
```
- HS256, `exp` 12시간, 비밀키는 `Settings.jwt_secret`
- 비밀키가 비어 있으면 **생성 시점에** `ConfigurationError`
- `verify` 는 만료·서명 실패·형식 오류를 **전부 `None`** 으로 만든다 — 호출부가
  이유를 구분할 필요가 없고, 구분하면 이유가 응답에 새어 나간다

### C53 `UploadValidator` (FR-30, BR-139·BR-140)
```python
validate(candidate: UploadCandidate) -> UploadVerdict
```
순서가 규칙이다 — **싼 검사부터, 내용 검사는 파싱 전에**:
```
1. 크기 ≤ 20MB              (바이트만 본다)
2. 매직 바이트 %PDF-         (확장자·MIME 은 업로더의 주장일 뿐)
3. pypdf 파싱 성공
4. 페이지 수 ≤ 200
5. /JavaScript · /EmbeddedFile · /Launch · /OpenAction 없음
```
- 어느 단계에서 걸렸는지 `reason` 에 담아 **사용자에게 그대로 보여준다**
- 파일을 실행하지 않는다. 렌더링·미리보기·링크 추적 없음

### C54 `UploadStore` (NFR-13, BR-141)
```python
save(owner_id: int, data: bytes) -> StoredUpload   # /data/uploads/{owner}/{uuid}.pdf
delete(path: Path) -> None
```
- 파일명은 UUID. 원본 파일명은 **경로에 절대 들어가지 않는다**
- `delete` 는 파일이 이미 없어도 조용히 성공한다 — 삭제는 되돌릴 수 없으므로
  절반 삭제 상태에서 재시도가 막히면 안 된다

### C55 `OwnershipFilter` (FR-28, NFR-15, BR-145·BR-146)
```python
scope_for(user: AuthenticatedUser | None) -> Scope
owned_or_404(session, document_id: int, user) -> Document
```
- `scope_for(None)` → `Scope.public()`. 익명도 공개 코퍼스를 본다(BR-151)
- `owned_or_404` 는 **남의 문서에 404** 를 낸다(BR-146) — 403 은 존재를 알려 준다
- 이 두 함수 밖에서 `Scope(...)` 를 직접 만드는 코드가 없어야 한다.
  Build & Test 에서 grep 으로 확인한다

---

## 2. 서비스

### S6 `AccountService`
```python
register(email, password, disclaimer_version) -> AuthenticatedUser
login(email, password) -> str                    # 토큰
current_user(token: str | None) -> AuthenticatedUser | None
query_history(user, limit, offset) -> list[HistoryEntry]
```
- `register` 는 면책 동의 없이는 계정을 만들지 않는다(BR-152)
- `login` 은 실패 이유를 구분하지 않는다(BR-134)
- `query_history` 는 `query_log.owner_id = user.id` 만 읽는다(BR-149)

### S7 `DocumentService`
```python
upload(user, candidate) -> int                   # document_id, 색인은 비동기
list_documents(user) -> list[DocumentSummary]
delete(user, document_id) -> None
reindex(user, document_id) -> int                # job_id
```
- 전부 `user` 를 첫 인자로 받는다. **익명은 이 서비스를 부를 수 없다**
- `list_documents` 는 소유 문서만 — 공개 코퍼스는 여기 나오지 않는다
  (문서 관리 화면은 "내가 올린 것"이지 "검색 대상 전체"가 아니다)

---

## 3. 워크플로

### W19 — 가입 (FR-31, FR-33, FR-34)
```
1. 이메일 정규화(소문자) · 중복 확인
2. C51.validate_policy() → 위반 시 사용자용 메시지
3. C51.hash()
4. 면책 동의 확인 → 미동의면 중단 (BR-152)
5. user_account INSERT (disclaimer_version, disclaimer_agreed_at 포함)
6. C52.issue() → HttpOnly 쿠키
```

### W20 — 로그인 (FR-31)
```
1. 이메일 정규화 → 계정 조회
2. 계정이 없어도 C51.verify(더미 해시) 를 수행한다 (BR-134)
3. 성공 → last_login_at 갱신, C52.issue() → 쿠키
   실패 → 동일한 메시지, 동일한 소요 시간
```

### W21 — 업로드 (FR-27, FR-30)
```
1. CSRF 토큰 검증 (BR-138)
2. C53.validate() → 거부면 이유와 함께 반환. **파일을 저장하지 않는다**
3. C54.save(owner_id, data)
4. document INSERT   owner_id=user.id · doc_type=user_upload
                     source_id=NULL · external_id=uuid
                     original_path=저장경로 · source_url=/documents/{uuid}
                     upload_filename=원본명 · size · page_count
5. 색인 잡 enqueue (BR-143)
6. 목록 화면으로 리다이렉트 — 상태는 job 진행률로 보인다 (FR-6 재사용)
```
**검증 전에 저장하지 않는다.** 거부된 파일이 디스크에 남으면 그것이 곧 저장소다.

### W22 — 색인 (워커, BR-142)
```
IndexingService._index_one(raw, doc_type=user_upload, owner_id=user.id)
  → 청킹·구조화·임베딩 전부 공개 문서와 같은 규칙
  → chunk.owner_id = user.id
```
**새 색인 경로가 없다.** 이 워크플로는 인자 하나가 다를 뿐이다.

### W23 — 목록·삭제·재색인 (FR-29, FR-46)
```
list     document WHERE owner_id = user.id
delete   C55.owned_or_404() → DocumentRepo.delete()(캐스케이드) → C54.delete(파일)
reindex  C55.owned_or_404() → 기존 재색인 잡 (보관된 업로드 파일에서)
```
삭제 순서가 **DB 먼저, 파일 나중**이다: 파일을 먼저 지우면 DB 트랜잭션이 실패했을 때
**행은 있는데 파일이 없는** 상태가 남는다. 반대는 고아 파일이고, 그쪽이 덜 나쁘다.

### W24 — 질의 이력 (FR-32, FR-47)
```
query_log WHERE owner_id = :user  ORDER BY asked_at DESC
  → answer_sentence · answer_citation · citation_snapshot 으로 재열람
```
재실행 없음(BR-150).

---

## 4. 기존 코드에 생기는 변화

| 파일 | 변화 |
|---|---|
| `web/routers/query.py`·`pages.py` | `current_user` 의존성 추가. **익명이면 `None`**, 스코프는 C55 가 만든다 |
| `services/query_service.py` | **없음** — `scope` 인자를 이미 받는다 |
| `services/indexing_service.py` | **없음** — `owner_id` 인자를 이미 받는다 |
| `indexing/vector_index.py` | **없음** — `apply_scope` 가 이미 구현되어 있다 |

**세 곳이 안 바뀐다는 것이 u1·u2 설계가 값을 한 지점이다.**

---

## 5. 이 유닛이 하지 않는 것

| 안 하는 것 | 이유 |
|---|---|
| 이메일 인증 | SMTP 인프라가 `docker compose up` 단일 명령(NFR-29)을 깬다 |
| 비밀번호 재설정 | FR 에 없다. 메일 발송이 전제된다 |
| 계정 삭제 | FR 에 없다. 문서 캐스케이드 정책을 미리 정하지 않는다 |
| 역할·권한 | FR 에 없다. 소유자 격리가 전부다 |
| 안티바이러스 | 컨테이너와 정의 파일 갱신을 운영에 얹는다. BR-140 에 범위를 적었다 |
| 재실행 버튼 | 할당량을 사용자 손에 쥐여준다 (BR-150) |
| 전면 로그인 강제 | 요구사항이 시키지 않은 기능 축소 (BR-151) |
