# Build and Test Summary — u1-ingestion-index

**작성일**: 2026-08-20
**대상**: 유닛 `u1-ingestion-index` (5개 유닛 중 1번째)
**환경 실측**: Python 3.14.6 / Docker 29.7.2 / Windows 10 Pro

---

## 1. 종합 결과

| 항목 | 결과 |
|---|---|
| **로컬 빌드** | ✅ `compileall` 종료코드 0, `ruff check` **All checks passed** |
| **단위 테스트** | ✅ **163 passed, 0 failed** (약 4초, 네트워크·DB 비의존) |
| **Docker 빌드** | ✅ 성공. 이미지 **743MB** (초기 5.81GB → 87% 감소, §4 결함 4) |
| **컨테이너 기동** | ✅ 5개 서비스, 기동 순서 정상, `/healthz` 4항목 전부 `ok` |
| **마이그레이션** | ✅ 테이블 14개(13 + alembic), 인덱스 17개 생성 확인 |
| **파이프라인 종단** | ✅ 실제 BGE-M3 임베딩으로 MSDS 16청크 / 법령 7청크 색인 |
| **보안 검증** | ✅ NFR-18 루프백 전용 실측 확인, 비밀값 노출 0건 |
| **발견·수정 결함** | **7건** (보안 2 / 인용정확도 1 / 데이터손실 1 / 인프라 2 / 관측 1) |
| **Ready for Operations** | ✅ **Yes** (미해소 제약 3건은 §7) |

---

## 2. 빌드

| 단계 | 결과 |
|---|---|
| `compileall app migrations tests` | 종료코드 0 |
| `ruff check app tests` | All checks passed |
| `docker compose build` | 성공, `safeenv-app:latest` |
| **이미지 크기** | **743MB** (설계 예상 ~1.2GB **하회**) |

**이미지 구성 실측** (최종)

```
python:3.12-slim 베이스 + Python 의존성(CPU torch 포함) + 앱 코드 = 743MB
```

임베딩 모델 가중치는 이미지에 포함되지 않으며(ID-6), `safeenv_models` 볼륨에 **4.3GB**
받아집니다 — 설계 예상 2GB의 **2배**입니다 (BGE-M3가 pytorch·safetensors·onnx 형식을
모두 내려받음). 디스크 요구사항 재산정이 필요합니다 (§6).

---

## 3. 테스트 실행 결과

### 3.1 단위 테스트 — **163 passed, 0 failed**

| 모듈 | 대상 | 케이스 |
|---|---|---|
| `test_retry.py` | BR-41~43, NFR-27 | 16 |
| `test_structure_msds.py` | BR-15~20, 24 | 12 |
| `test_structure_law.py` | BR-21~23 | 12 |
| `test_chunker.py` | BR-26~31, NFR-27 | 12 |
| `test_normalize_and_tokens.py` | BR-14, NFR-27 | 17 |
| `test_change_detector.py` | BR-09~11 | 11 |
| `test_policy.py` | BR-03~05, CON-3 | 11 |
| `test_job_tracker.py` | BR-46~51, 60 | 14 |
| `test_metadata_rules.py` | BR-24·25·32·33·37·39 + 회귀 4 | 21 |
| `test_config_and_logging.py` | NFR-14·23, BR-57~60 + 회귀 5 | 30 |
| `test_orchestrator.py` | BR-40~45, 03, 09 | 10 |
| **합계** | | **163** |

> 최초 152건에서 **회귀 테스트 11건 추가** (§4 결함 대응).

### 3.2 통합 검증 — 실제 컨테이너·DB·모델

| ID | 시나리오 | 결과 |
|---|---|---|
| **I-1** | 기동·헬스체크 | ✅ `{"app":"ok","db":"ok","queue":"ok","worker":"ok"}` |
| **I-2** | 마이그레이션 | ✅ 테이블 14개, 인덱스 17개 |
| **I-3** | 선반영 스키마 (DD-21) | ✅ `chunk.owner_id`·`document.owner_id` nullable, `substance_synonym` 존재 |
| **I-4** | 소스 카탈로그 | ✅ 4개 소스, 인증키 상태 정확 보고 |
| **I-5** | 인증키 없는 소스 거부 (BR-02) | ✅ HTTP **409** + **작업 미생성**(0건) |
| **I-7** | 파이프라인 종단 (BGE-M3 실제 임베딩) | ✅ MSDS **16청크**, 법령 **7청크**, dim=1024 |
| **I-8** | **BR-30 오프셋 무결성** | ✅ **위반 0행** |
| **I-9** | BR-38 CAS 정확 매칭 | ✅ `7664-93-9` → 16 청크 |
| **I-11** | BR-54 멱등 재색인 | ✅ 재색인 후 23청크/23벡터 **불변** |
| **I-12** | NFR-31 볼륨 영속화 | ✅ `down`→`up` 후 2문서/23청크/23벡터 보존 |

**BR-26 섹션=청크 실측**
```
msds : 16 sections / 16 chunks
law  :  7 sections /  7 chunks
법령 섹션 코드: 제1조, 제2조, 제12조, 제12조의2, 제13조, 부칙, 별표1
```
`제12조의2`가 `제12조`와 분리되고 `부칙`·`별표1`이 독립 섹션으로 잡혔습니다 (BR-21~23).

### 3.3 보안 검증

| ID | 항목 | 결과 |
|---|---|---|
| **S-2** | 이미지에 `.env` 없음 | ✅ |
| **S-4** | 실행 로그 비밀값 노출 | ✅ 0건 |
| **S-5** | DB에 비밀값 없음 | ✅ `api_key_env`는 환경변수 **이름**만 저장 |
| **S-6** | 포트 바인딩 | ✅ `127.0.0.1:8300` (`0.0.0.0` 아님) |
| **S-7** | **외부 인터페이스 접속** | ✅ `192.168.0.2:8300` → **연결 거부** (NFR-18) |
| **S-8** | DB·큐 호스트 노출 | ✅ 없음 |
| **S-9** | 비루트 실행 | ✅ `uid=10001(appuser)` — app·worker 모두 |

### 3.4 성능

| NFR | 목표 | 실측 |
|---|---|---|
| NFR-4 인덱싱 처리량 | 1,000종 / 8시간 | ⏭ **미측정** — 인증키 미보유(R-1) |
| NFR-9 청크 10만 규모 | 성능 유지 | ⏭ **미측정** — 데이터 미확보 |
| 워커 메모리 | 4G 한도 | ✅ **1.52GiB / 4GiB (38%)** — 여유 충분 |
| app 메모리 | 2G 한도 | ⚠️ 임베딩 로드 시 **1.70GiB / 2GiB (85%)** — §6 참조 |

---

## 4. 발견·수정된 결함 7건

### 🔴 결함 1 — 청킹이 섹션 경계를 넘어 병합 *(인용 정확도)*

**발견**: 단위 테스트. MSDS 16섹션 문서가 **14청크**로 축소.

**원인**: BR-31(20토큰 미만 병합)이 섹션 경계를 고려하지 않아, 짧은 섹션(예: `12. 환경에 미치는 영향`)이
앞 섹션에 흡수됨.

**영향**: `section_code`는 `msds_11`인데 본문에 12번 내용이 섞인 청크가 생성됨.
**u2가 그렇게 인용하게 되고, 원문을 대조하기 전까지 아무도 알아채지 못함.**

**수정**: 병합을 **같은 섹션 안으로 제한**. BR-31은 BR-27의 분할 잔여물을 정리하는 규칙이지
섹션을 붙이는 규칙이 아님. `business-rules.md` BR-31 정정 반영.

**검증**: 실측 16 sections / 16 chunks ✅

---

### 🔴 결함 2 — `Authorization: Bearer <token>` 미마스킹 *(보안)*

**발견**: 단위 테스트 `TestMasking`.

**원인**: 정규식이 `Authorization: Bearer` 까지만 매칭하여 **`Bearer`를 값으로 오인**,
실제 토큰이 평문 노출.

**수정**: 인증 스킴(`Bearer`/`Basic`/`Token`)을 선택적으로 소비하도록 패턴 확장.

---

### 🔴 결함 3 — `extra` 최상위 비밀 필드 미마스킹 *(보안)*

**발견**: 단위 테스트 `TestJsonFormatter`.

**원인**: `_scrub()`은 **dict 내부**만 검사. `log.info(..., extra={"api_key": "..."})`처럼
최상위로 넘어온 비밀값은 마스킹 경로를 전혀 타지 않음.

**수정**: `JsonFormatter.format()`에서 최상위 키도 `_is_secret_key()` 판정.

---

### 🟠 결함 4 — 이미지 5.81GB *(인프라)*

**발견**: Docker 빌드 실측. 설계 예상 ~1.2GB의 **약 5배**.

**원인**: PyPI 기본 `torch` 휠이 **CUDA 빌드**. `nvidia` 2.7GB + `triton` 691MB +
CUDA용 torch 1.2GB = 약 4.6GB가 **GPU 없는 배포에 전혀 쓰이지 않는 채로** 포함.

**수정**: 빌더 단계에서 torch를 **CPU 휠 인덱스**(`download.pytorch.org/whl/cpu`)로 먼저 설치.

**검증**: **5.81GB → 743MB (87% 감소)**, 설계 예상보다도 작음 ✅

---

### 🟠 결함 5 — 워커 기동 크래시 루프 *(인프라)*

**발견**: 컨테이너 기동. `/healthz`가 `worker: down` 보고.

**원인**: `WorkerSettings.cron_jobs`를 `@staticmethod`로 정의. arq는 이를 **반복 가능한 속성**으로
읽으므로 `TypeError: 'staticmethod' object is not iterable`로 즉시 사망.

**영향**: 웹 프로세스는 정상 응답하는데 **수집이 전혀 진행되지 않는 상태**.

**수정**: 모듈 수준에서 리스트로 계산.

**의의**: **BR-52 워커 하트비트가 정확히 이 상황을 위해 설계되었고, 실제로 잡아냈습니다.**
단일 boolean 헬스체크였다면 `app: ok`만 보고 정상으로 오인했을 것입니다.

---

### 🟠 결함 6 — 작업 전체가 단일 트랜잭션 *(DD-24/BR-53 위반)*

**발견**: 재색인 실행 중 `/api/jobs` 조회 시 `status: pending, total_count: 0`.

**원인**: `IngestionService.execute`와 `IndexingService.reindex_job`이 **작업 전체를 하나의
`session_scope()`** 안에서 실행. 커밋이 작업 종료 시점에만 발생.

**영향** — DD-24를 만든 이유 그대로:
- 진행률이 작업 종료까지 **보이지 않음** (FR-6 무력화)
- 장시간 락 유지 (1,000건이면 수 시간)
- 중간 크래시 시 **완료된 항목까지 전부 소실** (FR-8 부분 성공 무력화)

**수정**:
- `JobTracker`에 `commit` 콜백 도입 — 항목 상태 전이마다 커밋
- 문서 처리는 **문서별 독립 `session_scope()`** 로 분리

**검증**: 실행 중 `status: running, total_count: 2` 확인 ✅ → 완료 시 `succeeded 2/2` ✅

---

### 🟡 결함 7 — 재개 시 `original_path` 유실 *(데이터 손실)*

**발견**: 재색인 후 `document.original_path`가 NULL. 파일은 디스크에 존재.

**원인 (2단)**:
1. `_store_original`이 **모든 바이트 페이로드를 `.pdf`로 저장**. `original_media_type`은 DB에
   기록하면서도 재색인 시에는 **확장자로 추측**하여, 텍스트 원본이 PDF로 오인되어 영구 실패.
2. `from_stage=EXTRACT`로 재개하면 `fetch` 단계를 건너뛰어 `ctx.stored_path`가 설정되지 않고,
   그대로 NULL로 덮어씀.

**영향**: **재개 경로가 재개의 근거를 파괴함.** 한 번 재색인하면 그 문서는 다시 재색인할 수 없게 되고
(`no retained original`), 재수집이 강제됨 — BR-44와 FQ-8=A의 이득이 사라짐.

**수정**:
- 저장 확장자를 `media_type`에서 도출
- 재색인 시 `document.original_media_type`을 **권위 있는 값**으로 사용
- `PipelineContext.stored_path`를 `raw.stored_path`로 초기화하여 재개 시에도 보존

**검증** (신규 색인 → 재색인):
```
색인 직후 : /data/originals/fix-check/doc-a.txt   (media_type=text/plain 과 일치)
재색인 후 : /data/originals/fix-check/doc-a.txt   (보존됨)
```
같은 재색인에서 기존 손상 문서 2건은 `no retained original` 로 정확히 실패하여
작업이 `partial`(성공 1 / 실패 2)로 판정되었습니다 — BR-48 및 오류 보고가 함께 검증되었습니다.
**이미 손상된 행은 재수집이 필요하며, 이는 의도된 동작입니다.**

---

### ⚙️ 부수 수정

| 항목 | 내용 |
|---|---|
| 과잉 마스킹 | `_key` 접미사가 **`ref_key`까지 마스킹** — 실패 항목 진단의 핵심 필드가 `***`로 표시됨. 접미사 목록을 `_api_key`/`_secret`/`_token`/`_password`/`_pwd`로 축소 |
| 과잉 마스킹 2 | 부분 문자열 검사가 **`input_tokens`/`output_tokens`** 까지 마스킹 — FR-41 비용 추적을 조용히 비움. 정확 일치+접미사 판정으로 변경 |
| Hypothesis | `@given` 안의 함수 스코프 픽스처 거부 → health check 억제 대신 테스트 내부에서 값 생성 |
| ruff `B008` | `Depends()`/`Query()` 기본값은 FastAPI 관용구 → `app/web/routers/*` per-file-ignore, 근거 주석 기록 |

---

## 5. ⚠️ CON-2 정정 — 포트 충돌

Infrastructure Design은 호스트 포트 **8200**을 지정했고, ID-16의 6축 조사에서
`news`(8100)와 `petmate`(8000/5173)만 확인했습니다.

**실측 결과 `trip-app` 컨테이너가 이미 `127.0.0.1:8200`을 점유하고 있었습니다.**

```
NAMES      PORTS
trip-app   127.0.0.1:8200->8200/tcp
news-app   127.0.0.1:8100->8000/tcp
```

**조치**: 호스트 포트를 **8300**으로 변경. 나머지 5축은 충돌 없음 실측 확인
(`safeenv_net` / `safeenv_pgdata`·`safeenv_models` / `safeenv-app` / `safeenv-*` 컨테이너명).

`requirements.md` CON-2, `docker-compose.yml`, `README.md`, 인프라 설계 문서에 반영했습니다.

**교훈**: 6축 분석을 문서상 목록이 아니라 `docker ps` 실측으로 수행해야 합니다.

---

## 6. 설계 예상 대비 실측 차이

| 항목 | 설계 예상 | 실측 | 조치 |
|---|---|---|---|
| 앱 이미지 | ~1.2GB | **743MB** | 예상 하회 (CPU torch 전환 후) |
| 모델 볼륨 | ~2GB | **4.3GB** | ⚠️ **디스크 요구 재산정 필요** |
| 워커 메모리 | 4G 한도 | 1.52GiB (38%) | 여유 충분 |
| app 메모리 | 2G 한도 | 1.70GiB (85%) — 임베딩 로드 시 | ⚠️ **u2 리랭커 도입 시 초과 위험** |
| 총 디스크 | ~15GB | **약 12GB + 데이터** | 재산정 결과 유사 |

### ⚠️ u2 이월 사항

**`app` 컨테이너는 절대 임베딩·리랭킹을 수행하면 안 됩니다.**
검증 중 `app`에서 임베딩을 강제했더니 2G 한도의 85%까지 올라가고 6분 이상 완료되지 않았습니다.
정상 동작에서는 `app`이 모델을 로드하지 않으나(지연 로딩), u2에서 리랭커를 `app`에 두면
같은 문제가 발생합니다. `deployment-architecture.md` §9의 재검토 항목이 실측으로 확인되었습니다.

또한 `app`에는 `safeenv_models` 볼륨이 **마운트되지 않아**, 만약 모델을 로드하면
컨테이너 재시작마다 재다운로드합니다.

---

## 7. 미해소 항목

| # | 항목 | 사유 | 해소 조건 |
|---|---|---|---|
| **1** | 공공 API 실제 응답 형식 (R-1) | 인증키 미보유 | 키 발급 후 `config/sources.yaml` 필드명 검증 |
| **2** | MSDS PDF 실제 파싱 성공률 (R-2) | 실제 문서 샘플 미확보 | 매니페스트에 공개 PDF 등록 후 측정 |
| **3** | NFR-4 / NFR-9 성능 실측 | 위 1·2에 의존 | 1,000종 색인 후 측정 |

**측정 절차는 `performance-test-instructions.md`와 `integration-test-instructions.md`에
완비되어 있으므로, 데이터만 갖춰지면 즉시 실행 가능합니다.**

| # | 열린 위험 | 상태 |
|---|---|---|
| **R-6** | `/admin` 무인증 노출 | ⚠️ **u5까지 유지.** 루프백 바인딩 실측 확인(S-7)으로 완화. README·화면 배너 경고 |

---

## 8. 품질 게이트

| ID | 게이트 | 결과 |
|---|---|---|
| **QG-1** | FR·BR 추적성, 미매핑 0건 | ✅ FR 16 / BR 62 전건 매핑 |
| **QG-2** | 코드가 `aidlc-docs/` 밖에만 존재 | ✅ |
| **QG-3** | 단위 테스트 전건 통과, 네트워크 비의존 | ✅ 163 passed |
| **QG-4** | 인용 정확도 ≥95% (NFR-5) | ⏭ u4에서 측정 (u1은 **BR-30 오프셋 무결성 0위반**으로 전제 확보) |
| **QG-5** | 근거 불충분 거부율 | ⏭ u4 |
| **QG-6** | Security Baseline 차단성 findings 0건 | ✅ (보안 결함 2건 발견·수정 완료) |
| **QG-7** | `docker compose up` 단일 명령 기동 | ✅ 실측 |
| **QG-8** | 비밀값 로그·저장소 미노출 | ✅ 실측 |

---

## 9. 성공 기준 (SC) 진척

| SC | 내용 | 상태 |
|---|---|---|
| **SC-1** | 물질 1,000종 코퍼스 색인 | ⏭ 파이프라인 검증 완료, **데이터는 인증키 대기** |
| SC-2 | 문장 단위 인용 답변 | u2 |
| SC-3 | 근거 부족 시 거부 | u2 |
| SC-4 | 물질 안전 카드 | u3 |
| SC-5 | 업로드 문서 색인 | u5 |
| SC-6 | 골든 QA 자동 평가 | u4 |
| SC-7 | LLM 비용·지연 추적 | u2 (추적 인프라는 u1에 존재) |
| **SC-8** | `docker compose up` 단일 명령 | ✅ **달성** |

---

## 10. 다음 단계

**u1 완료.** 다음은 `u2-rag-qa` — 하이브리드 검색, 인용 답변, 근거 부족 시 거부.

u2 착수 전 확인할 것 (`code/code-summary.md` §7 + 본 문서 §6):

1. `app` 메모리 2G — 리랭커를 `app`에 두면 초과. 워커 위임 또는 한도 상향 검토
2. `app`에 `safeenv_models` 볼륨 미마운트 — 리랭커를 `app`에 둔다면 반드시 추가
3. `TraceRepo`는 현재 인메모리 버퍼 — 실제 테이블은 u2 리비전(`0002_query`)에서 생성
4. `VectorIndex.search`/`KeywordIndex.search`는 이미 `scope` 필수 인자 보유 (DD-19)
5. 디스크 요구 재산정 — 모델 볼륨 실측 4.3GB
