# Security Test Instructions — safeenv

**작성일**: 2026-08-20
**근거**: Security Baseline 확장 **활성** (Q27=A, CON-7)

---

## 1. 검증 대상 NFR

| NFR | 내용 | u1 상태 |
|---|---|---|
| NFR-14 | 비밀값을 로그·저장소·이미지에 남기지 않음 | ✅ 자동 테스트 |
| NFR-17 | 입력 검증, 파라미터 바인딩 | ✅ 자동 테스트 |
| NFR-18 | 루프백 전용 바인딩 | 실측 필요 |
| NFR-30 | 비루트 컨테이너 실행 | 실측 필요 |
| NFR-11~13, 15 | 해싱·JWT·업로드·접근통제 | **u5 범위** |
| NFR-16 | 프롬프트 인젝션 방어 | **u2 범위** |

---

## 2. 비밀값 노출 검사 (NFR-14)

### S-1. 저장소에 비밀값 없음

```bash
git ls-files 2>/dev/null | xargs grep -l "POSTGRES_PASSWORD=.\+" 2>/dev/null
grep -rn "serviceKey=[A-Za-z0-9]\{8,\}" --include="*.py" --include="*.yaml" app config
```
**기대**: 0건. `.env` 는 `.gitignore` 에 있고 `.env.example` 은 값이 비어 있어야 합니다.

```bash
grep -c "^[A-Z_]*=$" .env.example      # 값이 빈 항목 수
```

### S-2. 이미지 레이어에 비밀값 없음

```bash
docker history safeenv-app:latest --no-trunc | grep -iE "password|api_key|token" || echo "clean"
docker run --rm safeenv-app:latest sh -c "ls -a /app" | grep -x ".env" && echo "LEAK" || echo "clean"
```
**기대**: `.env` 가 이미지에 포함되지 않음 (`.dockerignore` 로 제외).

### S-3. 로그 마스킹 (BR-59, BR-60)

자동 테스트로 검증합니다.

```bash
pytest tests/unit/test_config_and_logging.py -v -k "Masking"
```

**검증 케이스**
- `serviceKey=...`, `api_key=...`, `password=...`, `token: ...` 마스킹
- **`Authorization: Bearer <token>`** 마스킹 ← Build & Test 에서 발견된 결함의 회귀 테스트
- **`extra` 최상위 필드**(`api_key=...`) 마스킹 ← 동일
- 중첩 dict 내부 마스킹
- **`input_tokens` / `output_tokens` 는 마스킹되지 않음** ← 과잉 마스킹 회귀 테스트

마지막 항목이 중요합니다. 단순 부분 문자열 검사는 `token` 을 포함하는 정상 필드까지
가려 버려 FR-41 의 비용 추적을 조용히 비워 버립니다.

### S-4. 실행 중 로그 검사

```bash
docker compose logs 2>&1 | grep -iE "(serviceKey|api_key|password)=[A-Za-z0-9]{8,}" && echo "LEAK" || echo "clean"
```
**기대**: 0건.

### S-5. DB 에 비밀값 없음

```sql
SELECT api_key_env FROM source;                    -- 환경변수 '이름'만
SELECT failure_reason FROM job_item
 WHERE failure_reason ~ '[A-Za-z0-9]{16,}' LIMIT 5; -- 마스킹 확인
```
**기대**: `source.api_key_env` 는 `NCIS_API_KEY` 같은 **이름**만 저장. 값은 없음.

---

## 3. 네트워크 노출 (NFR-18) — 최우선

u1 에는 인증이 없으므로 (ID-13) **이것이 유일한 접근 통제**입니다.

### S-6. 루프백 전용 확인

```bash
docker compose ps --format "table {{.Name}}\t{{.Ports}}"
```
**기대**: `app` 만 `127.0.0.1:8300->8000/tcp`. `postgres`·`redis` 는 포트 매핑 **없음**.

```bash
netstat -ano | grep ":8300 .*LISTENING"
```
**기대**: `127.0.0.1:8300` — **`0.0.0.0:8300` 이면 즉시 위반**입니다.

### S-7. 외부 인터페이스에서 접속 실패 확인

```bash
# 호스트의 LAN IP 확인
ipconfig | grep -A2 "IPv4"

# 그 IP 로 접속 시도 -> 반드시 실패해야 함
curl -m 5 http://<LAN_IP>:8300/healthz && echo "LEAK" || echo "correctly refused"
```
**기대**: 연결 거부/타임아웃.

### S-8. DB·큐 직접 접속 차단

```bash
curl -m 3 http://127.0.0.1:5432 ; echo "exit=$?"
redis-cli -h 127.0.0.1 -p 6379 ping 2>&1
```
**기대**: 둘 다 접속 불가 (호스트에 노출되지 않음).

---

## 4. 컨테이너 하드닝 (NFR-30)

### S-9. 비루트 실행

```bash
docker compose exec app id
docker compose exec worker id
```
**기대**: `uid=10001(appuser) gid=10001(appuser)`

### S-10. 쓰기 권한 최소화

```bash
docker compose exec app sh -c "touch /data/originals/x 2>&1"   # app 은 ro 마운트
```
**기대**: `app` 은 원본 디렉터리에 **쓸 수 없어야** 합니다 (읽기 전용 마운트).
`worker` 만 쓰기 가능합니다.

---

## 5. 입력 검증 (NFR-17)

### S-11. 파라미터 검증

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  http://127.0.0.1:8300/api/sources/ncis_substance/ingest \
  -H "Content-Type: application/json" -d '{"since":"2099-01-01"}'      # 미래 -> 422

curl -s -o /dev/null -w "%{http_code}\n" \
  "http://127.0.0.1:8300/api/jobs?limit=99999"                          # 범위 초과 -> 422

curl -s "http://127.0.0.1:8300/api/jobs?status=nonsense" | head -c 80   # 무시하고 기본 목록
```

### S-12. SQL 인젝션

```bash
curl -s "http://127.0.0.1:8300/api/jobs?kind=ingest';DROP%20TABLE%20job;--" | head -c 80
docker compose exec postgres psql -U safeenv -d safeenv -c "\dt job"
```
**기대**: `job` 테이블 정상 존재. 모든 DB 접근이 SQLAlchemy 파라미터 바인딩을 거칩니다.

### S-13. 경로 순회

```bash
curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:8300/static/../../.env"
```
**기대**: 404 또는 400. `.env` 내용이 반환되면 위반입니다.

---

## 6. 의존성 취약점

```bash
pip install pip-audit
pip-audit -r <(python -c "
import tomllib,pathlib
d=tomllib.loads(pathlib.Path('pyproject.toml').read_text())
print('\n'.join(d['project']['dependencies']))
")
```

**범위 고지**: 자동 스캔을 CI 에 붙이는 것은 OOS-4(CI/CD 범위 외)입니다.
수동 실행 절차만 제공합니다.

---

## 7. ⚠️ u1 의 알려진 보안 상태

| 항목 | 상태 |
|---|---|
| **`/admin` 무인증 노출** | ⚠️ **열린 위험.** 통제 수단은 루프백 바인딩뿐. u5 에서 해소 |
| 비밀값 관리 | ✅ 환경변수 주입 + 로그 마스킹 + gitignore/dockerignore |
| 네트워크 노출 | ✅ 설계상 루프백 전용 (S-6, S-7 실측 필요) |
| 컨테이너 권한 | ✅ 비루트 uid 10001 |
| 입력 검증 | ✅ Pydantic + ORM 바인딩 |
| 인증·인가 | ❌ u5 |
| 프롬프트 인젝션 | ❌ u2 |

**`docker-compose.yml` 의 `127.0.0.1:` 접두사를 제거하면 무인증 관리 화면이
네트워크에 그대로 노출됩니다.** 파일에 제거 금지 주석을 명시했습니다.
