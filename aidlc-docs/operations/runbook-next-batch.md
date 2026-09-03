# 런북 — 다음 배치 (실행 387 승격 → B 그룹 → D4 → 백로그 정리)

**작성** 2026-09-03 · **대상일** 2026-09-04 이후 아무 날
**용도**: 예약(세션 전용)이 사라져도 사람이나 새 세션이 그대로 따라갈 수 있게.

시간에 쫓기는 1단계는 **스크립트가 대신한다.** 2단계부터는 판단이 들어가므로
사람이나 에이전트가 한다.

---

## 0. 전제 — 순서를 지키는 것이 커밋 수보다 중요하다

**승격이 끝나기 전에는 아래를 고치지 말 것:**

```
app/  config/  migrations/  prompts/  eval/  pyproject.toml
```

이 여섯이 빌드 지문(`app/core/build.py` 의 `TRACKED`)이다. 하나라도 바꾸면
지문이 달라지고, 실행 387 은 옛 지문으로 측정 중이므로 `evaluate --promote` 가
거부한다. 387 에는 **이틀치 심판 할당량**이 들어가 있다.

`tests/` `scripts/` `aidlc-docs/` `README.md` `.github/` 는 지문 밖이라 언제든 안전하다.

---

## 1. 승격 — 스크립트 하나

```bash
cd /c/Users/403/IDE/chemical_safe
scripts/resume_and_promote.sh 387
```

하는 일: 지문 3중 확인(컨테이너·작업트리·실행) → `--resume` → 할당량이면
30분 간격 최대 4회 → 완주하면 `--promote` → 기준선 표 출력 → 재현 확인.

| 종료코드 | 뜻 | 다음 |
|---|---|---|
| 0 + "완주" | 승격까지 끝 | 2단계로 |
| 0 + "오늘 몫 소진" | 할당량. 실패가 아니다(BR-118) | 내일 같은 명령. **2단계 금지** |
| 1 | 인프라 문제 | 출력의 로그 경로를 볼 것 |
| 3 | 컨테이너와 작업 트리의 코드가 다르다(결함 58) | `docker compose up -d --build app worker` 후 재시도 |

심판 한도는 하루 20콜이고 리셋은 **13:40~16:10 사이 어딘가**로 실측돼 있다
(정확한 시각 불명). 16시 이후에 돌리는 것이 가장 확실하다.

**남은 3문항** law-07 · msds-01 · sub-07 은 전부 답변형이라 심판 3콜이면 끝난다.

### 승격 후 기록할 것 (커밋 1~2개)
`audit.md` · `aidlc-state.md` · `operations.md` 기준선 표.
**충실도 0.958 → 1.000 회복 여부가 핵심이다** — 276 의 하락은 law-09 단독이었고
"검색이 0 이라 약한 근거로 답을 지어냈다"는 진단이었다. law-09 검색은 조문 제목
층으로 고쳤으므로 이 값이 그 진단의 판정이다.
정답률·인용은 BR-73a 로 거부가 3건 늘어 **분모가 달라졌으므로 원인 분해가
불가능**하다는 점을 함께 적을 것.

---

## 2. B 그룹 — 관리 화면 인증 (승격 성공 후에만)

사용자가 B3(역할 도입)을 승인했다. **역할이 먼저** 들어가야 나머지가
`require_admin` 으로 걸린다.

### B3 — 역할 (커밋 2~3개)

- 마이그레이션 `0006`: `user_account.role` varchar(16) NOT NULL DEFAULT `'user'`
- `AuthenticatedUser` 에 역할, `require_admin` 의존성 신설
- **역할은 토큰이 아니라 DB 에서 읽는다.** 실측: `current_user` 는 토큰만 읽고
  DB 를 치지 않는다. 역할을 JWT 에 넣으면 **강등된 관리자가 최대 12시간 관리자로
  남는다**(AP-3 의 알려진 약점). 관리 라우트는 트래픽이 적으므로 요청당 조회
  한 번이 즉시 강등보다 싸다.
- **부트스트랩이 없으면 잠긴다.** 현재 `user_account` **0행**이다. 관리자를 만들
  수단 없이 `/admin` 을 관리자 전용으로 바꾸면 아무도 못 들어간다.

  ```bash
  safeenv grant-admin <email>    # 및 revoke-admin
  ```

  **"첫 계정을 자동으로 관리자로" 방식은 쓰지 말 것** — 노출되면 먼저 가입한
  사람이 관리자가 된다. 가입 → CLI 승격의 명시적 2단계로 간다.

- 종단 확인 후 **임시 계정을 반드시 삭제**하고 `user_account` 0행으로 되돌린다
  (결함 48·53: 테스트가 자기 대상을 바꿔 놓는 실수).

### 그다음 (각각 커밋 하나)

| 항목 | 대상 | 근거 |
|---|---|---|
| **B2a** 최우선 | `app/web/routers/api.py` (`prefix="/api"`) | `/api/sources`·`/api/jobs`·`/api/stats` 익명 200, **`POST /api/sources/{id}/ingest` 도 인증 없이 도달**(409 는 업무 응답이지 인증 거부가 아니다). 읽기가 아니라 **상태 변경**이다 |
| B1 | `app/web/routers/admin.py` (GET 4 + POST 1) | 익명 200 |
| B2 | `app/web/routers/usage.py` | 인증 의존성이 **아예 없다**. u5 문서가 "로그인만"이라 잘못 적었던 곳 |
| B4 | 통합 테스트 | 경로 × (익명 / 일반 / 관리자) 결과 고정. 테스트 계정 정리 필수 |
| 문서 | README 인증 표, u5 요약, operations.md | |

### 바꾸지 말 것

- **`/healthz`** — Docker 헬스체크가 쓴다. 인증을 걸면 컨테이너가 unhealthy 가 된다
- **`/documents` · `/history`** — 자기 문서·이력이므로 `require_user` 유지 (관리자 전용 아님)
- **`/` · `/substances`** — 공개 코퍼스, 익명 유지가 의도된 동작 (BR-147)

---

## 3. D4 — `.gitattributes` (승격 확인 후)

`* text=auto eol=lf`.

**단순 정리가 아니다.** `core.autocrlf=true` 이고 작업 트리가 혼재
(`app/` LF, `pyproject.toml` CRLF)라, 재정규화하면 **LF 113파일이 CRLF 가 되며
빌드 지문이 `03bab957bade` → `7b008836585f` 로 바뀐다**(2026-09-03 실측).

적용 후 반드시:
```bash
docker compose up -d --build app worker
# 컨테이너 지문 == 작업 트리 지문 재확인
```
그리고 통합 테스트까지 돌릴 것.

여유가 있으면 D3(`pyproject.toml` 패키징 — 승격 후엔 안전), D1/D2(사문화 필드
`doc_type_hint`·`meta.substance_names` 처분 검토).

---

## 3b. D5 — `safeenv/` 정리 (자동화됨)

```bash
scripts/retire_safeenv.sh            # 검사만
scripts/retire_safeenv.sh --apply    # 검사 통과 시 실제 정리
```

**되돌릴 필요가 없다는 것을 증명한 뒤에만 지운다.** 검사 셋 중 하나라도
실패하면 아무것도 하지 않는다:

1. 스택이 옛 경로를 마운트하고 있지 않은가 (이전이 살아 있는가)
2. safeenv 에만 있는 파일이 0개인가 (캐시·로그 제외)
3. 이 저장소에 커밋이 있는가

2026-09-03 실측: 유일 파일 **0개**, 내용이 다른 5개는 전부 chemical_safe 쪽이
최신이다. 붉은불도 확인했다 — safeenv 에 파일을 하나 만들면 종료코드 1 로
거부하고 파일명을 출력한다.

유일하게 저장소에 없는 것은 `logs/safeenv.log`(3.6MB, 8/20~9/2 운영 로그,
`.gitignore` 대상)다. **지우지 않고** `logs/safeenv-pre-migration.log` 로 옮긴다.

## 4. 백로그 정리 (D4 뒤, 마지막 커밋)

`aidlc-docs/operations/backlog.md` 를 다시 쓴다.

- 상단 상태 블록을 최신 실측으로 (기준선 2개·코퍼스·테스트 수)
- 완료 항목은 **날짜와 결과를 남기고 취소선**. 지우지 않는다 — 한 일의 기록이다
- 남는 것만 다시 우선순위. 보안 기본이 끝난 뒤의 순서는 착수 전과 다르다
- 각 항목에 "왜 지금 이 순위인가" 한 줄. 지표를 안 움직이면 그렇다고 적을 것
- **D5(`safeenv/` 백업 정리)** — chemical_safe 에서 이틀 연속 정상 동작했으면
  근거가 갖춰진다. 판단만 적고 **실행은 사용자 확인 후**(지우면 되돌릴 곳이 없다)
- 남은 커밋 수를 세어 며칠치인지 적을 것

---

## 각 커밋 전

```bash
python -m pytest tests/unit -q
python -m ruff check app/ tests/ migrations/
```

코드를 고쳤으면 재배포 후 통합까지:
```bash
docker compose up -d --build app worker
set -a; . ./.env; set +a
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433 REDIS_HOST=127.0.0.1 \
  python -m pytest tests/integration -m integration -q
```

커밋 메시지는 `backlog.md` 규약대로: **무엇을 측정했고 지표가 어떻게 움직였는지.
안 움직였으면 그것도.** 빈 커밋·인위적 분할·`GIT_AUTHOR_DATE` 소급은 하지 않는다.
하루 10커밋은 목표가 아니라 결과다.

---

## 푸시

```bash
python scripts/check_secrets.py && git push origin main
```

`check_secrets.py` 는 추적 파일에서 `.env` 의 실제 비밀값을 찾는다.
**검사 대상이 0개면 실패로 처리한다** — 2026-09-02 에 경로 오류로 파일 0개를
검사하고 "유출 0건"을 보고할 뻔했다. 비어 있음은 통과가 아니다.

종료코드가 0 이 아니면 **푸시하지 말 것.**
