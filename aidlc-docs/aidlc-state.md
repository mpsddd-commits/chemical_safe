# AI-DLC State Tracking — safeenv

> ## ✅ u2 완료 (2026-08-26) — 최소 목표 도달
>
> **`u2-rag-qa` Build and Test 승인. 다음: `u3-substance-card` (3/5) — 순서 변경.**
>
> 수집·색인(u1) 위에 **출처가 추적되고 근거가 없으면 답하지 않는** 질의응답이 올라갔고
> 실제로 동작한다. Workflow Planning 이 정한 **최소 목표 지점**이다.
>
> ```
> 단위 425 통과 + 1 스킵 / 통합 6 통과 + 1 스킵 (실 DB) / ruff clean
> NFR-2 검색 P95   예산 2,500ms   실측   109~151 ms   ✅
> NFR-1 전체       예산 20,000ms  실측 2,154~4,181ms  ✅
> SC-2 문장 단위 인용 / SC-3 근거 부족 시 거부 / SC-7 사용량 조회  달성
> 코퍼스 70문서 / 1,598청크 / 1,598벡터 / 상한 초과 0 / BR-30 위반 0
> 결함 25~39 (15건) 발견·수정
> ```
>
> ### 환경 상태
> - Docker 스택 가동 중. `http://127.0.0.1:8300` — `/` 질의 / `/usage` 사용량 / `/admin` 운영
> - LLM: **Google Gemini 무료 티어**, `gemini-3.1-flash-lite` 고정 (`LLM_PROVIDER=gemini`)
> - `reranker` 는 `profiles: ["reranker"]` 라 기본 미기동 — **켜도 예산 안에서 쓸 수 없다**
> - `.env` 에 `GEMINI_API_KEY` 설정 완료. 인증키 3종도 유지
>
> ### 🔑 알고 진행해야 할 제약
> | 항목 | 내용 |
> |---|---|
> | **하루 ~3질의** | 무료 티어 모델당 20요청 × BR-86a(`1+문장수`). 개발용 수용. **u4 평가셋 실행 규모에 직접 제약** |
> | **리랭커 사용 불가** | CPU 2,121~2,830ms vs 예산 1,200ms |
> | **PP-4 캐시 적중 0** | 원인 미측정 — 가설만 있음 |
> | **엔티티 LLM OFF** | 물질 마스터가 비어 값을 못 함 |
> | **u1 물질 마스터 공백** | `substance`·`substance_synonym`·`document_substance` 전부 0행.<br>BR-38 CAS 완전일치·BR-65 동의어 해석이 사실상 비활성. **u3 범위와 겹치므로 u4 착수 전 순서 재검토 여지** |
>
> ### ⚠️ 이 유닛에서 배운 것 (다음 유닛에 그대로 적용된다)
> 결함 15건이 여섯 가지 모양으로 반복됐다:
> 1. **한 번도 실행된 적 없음** (25, 39, 40, 46) — 테스트가 초록불인데 그 경로가 돈 적이 없다
> 2. **규칙이 구조상 성립 불가** (26, 31) — try/except 는 옳게 읽히지만 트랜잭션이 허용하지 않는다
> 3. **틀린 신호를 읽음** (27, 30) — 보정으로 못 고친다
> 4. **선택적인 것이 필수의 예산을 파괴** (28, 29, 32, 34a)
> 5. **제약을 몰랐음** (36, 37) — 측정하지 않으면 알 수 없다
> 6. **자초** (34) — 옳아 보이는 원칙이 실측과 어긋나면 실측이 이긴다
>
> **대응**: `tests/integration/` 계층 신설. 26·31·37·38 은 전부 단위 테스트를 통과했고
> **모킹된 그것이 바로 틀린 대상**이었다. 실행법은 `build-and-test/u2-test-instructions.md`.
>
> ### 재색인 주의 (u1 에서 배운 것, 유효)
> 재색인은 **35분**이다. 가정 검증에 쓰지 말 것 — 청킹 규칙을 바꿨으면
> **전 코퍼스 건식 시뮬레이션을 먼저** 돌린다.

## Project Information
- **Project Name**: safeenv — 화학 안전·규제 근거 기반 질의응답(RAG) 시스템
- **Project Type**: Greenfield
- **Start Date**: 2026-08-20T01:28:02Z
- **Current Phase**: 🟢 CONSTRUCTION
- **Current Stage**: **u3 Functional Design**
- **진행 방향**: **(a) 단계적 진행** (사용자 선택 2026-08-20)
- **Current Unit**: **`u3-substance-card`** (3/5) — u1·u2 승인 완료. **순서 변경**

## Workspace State
- **Existing Code**: No
- **Programming Languages**: Python (FastAPI + Jinja2) — Requirements Analysis에서 확정 (Q20=A, Q21=A)
- **Build System**: pip/uv + Docker Compose (Q24=A)
- **Project Structure**: Empty (신규 생성)
- **Reverse Engineering Needed**: No
- **Workspace Root**: `c:\Users\403\IDE\safeenv`

### 워크스페이스 분리 결정
상위 디렉터리 `c:\Users\403\IDE`에는 별개의 독립 AI-DLC 프로젝트가 다수 존재합니다
(`260731_AI-DLC_news/news/`, `purchase_agent/`, `trip/`). 상위 디렉터리 자체는 `aidlc-docs/`를
점유하고 있지 않으며, 사용자 요청("safeenv폴더를 만들고 그 안에")에 따라 본 프로젝트는 독립 프로젝트로
취급합니다. 워크스페이스 루트는 `safeenv/`, 문서 루트는 `safeenv/aidlc-docs/`입니다.
이 결정은 Requirements Analysis Question 1에서 사용자가 재정의할 수 있습니다.

## Code Location Rules
- **Application Code**: `safeenv/` (워크스페이스 루트) — NEVER in `safeenv/aidlc-docs/`
- **Documentation**: `safeenv/aidlc-docs/` only
- **Structure patterns**: See code-generation.md Critical Rules

## Extension Configuration
| Extension | Enabled | Decided At |
|---|---|---|
| Security Baseline | **Yes** | Requirements Analysis (Q27=A) |
| Resiliency Baseline | **No** | Requirements Analysis (Q28=B) |
| Property-Based Testing | **Partial** (순수 함수·직렬화 한정) | Requirements Analysis (Q29=B) |

Rules to load: `extensions/security/baseline/security-baseline.md`, `extensions/testing/property-based/property-based-testing.md`
Rules NOT loaded (opted out): `extensions/resiliency/baseline/resiliency-baseline.md`

## Technology Stack (Requirements Analysis에서 확정, 2026-08-20)
| Layer | Decision | 근거 |
|---|---|---|
| Backend | Python + FastAPI | Q20=A |
| Frontend | Jinja2 서버사이드 렌더링 | Q21=A |
| DB + Vector Store | PostgreSQL + pgvector | Q13=A |
| Keyword Search | PostgreSQL FTS 또는 BM25 | Q14=C |
| Embedding | 로컬 오픈소스 (추상화, 교체 가능) | Q12=C |
| Reranker | cross-encoder (로컬) | Q14=C |
| LLM | 추상화 레이어 + 기본값 Anthropic Claude | Q11=D |
| Job Queue | 워커 + 큐 (Celery/Redis 또는 ARQ) | Q23=B |
| Auth | JWT (이메일+비밀번호) | Q22=B |
| Test | pytest + 평가셋 회귀 + 부분 PBT | Q26=C, Q29=B |
| Runtime | Docker Compose, `127.0.0.1:8200` | Q24=A |

## Execution Plan Summary (2026-08-20)
- **표준 스테이지**: 14 / **완료**: 3 / **실행 예정**: 8 / **SKIP**: 3
- **Stages to Execute**: Application Design -> Units Generation -> (유닛별) Functional Design -> NFR Design(u2,u5) -> Infrastructure Design(u1) -> Code Generation -> Build and Test -> Operations
- **Stages Skipped**:
  - Reverse Engineering — Greenfield, 분석할 기존 코드 없음
  - User Stories — 단일 페르소나(Q3=D), FR 48건이 이미 수용 기준 수준으로 상세
  - NFR Requirements — NFR 32건 및 기술 스택 12계층이 Requirements Analysis에서 확정 완료
- **Risk Level**: Medium-High / **Rollback**: Easy / **Testing**: Complex
- **CONSTRUCTION 유닛 5개 (제안, Units Generation에서 확정)**:
  `u1-ingestion-index` -> `u2-rag-qa` -> `u4-evaluation` -> `u3-substance-card` -> `u5-account-upload`
- **예상 기간**: 11~14주 / 최소 목표(u2까지) 6~8주 / 권장 목표(u4까지) 8~10주
- **Build and Test 조정**: 방향 (a)에 따라 유닛 완료 시마다 증분 실행 + 최종 통합 1회

## Stage Progress

### 🔵 INCEPTION PHASE
- [x] Workspace Detection — **완료 2026-08-20**. Greenfield 판정, 워크스페이스 루트 `safeenv/` 확정
- [x] Reverse Engineering — **SKIPPED** (Greenfield, 분석할 기존 코드 없음)
- [x] Requirements Analysis — **APPROVED 2026-08-20**. 산출물: `inception/requirements/requirements.md` (FR 48 / NFR 32 / CON 8 / OOS 10 / SC 8 / R 7)
- [x] User Stories — **SKIPPED** (단일 페르소나, FR 48건이 이미 수용 기준 수준. 사용자 이의 없음 2026-08-20)
- [x] Workflow Planning — **APPROVED 2026-08-20**. 산출물: `inception/plans/execution-plan.md`
- [x] Application Design — **APPROVED 2026-08-20**. 산출물: `inception/application-design/` 5종. 컴포넌트 60 / 서비스 8 / 포트 4 / 설계결정 DD-1~DD-25
- [x] Units Generation — **APPROVED 2026-08-20**. 산출물: `inception/application-design/` 3종. 유닛 5개 / 분해결정 UD-1~UD-12

**🔵 INCEPTION PHASE 완료 (2026-08-20)** — 실행 5 / SKIP 3

### 🟢 CONSTRUCTION PHASE — 유닛 `u1-ingestion-index` (1/5)
- [x] Functional Design — **APPROVED 2026-08-20**. 산출물: `construction/u1-ingestion-index/functional-design/` 4종. 엔터티 12 / Enum 11 / **BR-01~BR-62**
- [x] NFR Requirements — **SKIPPED** (실행 계획대로. audit.md 기록)
- [x] NFR Design — **SKIPPED (u1)** (실행 계획대로. audit.md 기록) / EXECUTE 예정 (u2, u5)
- [x] Infrastructure Design — **APPROVED 2026-08-20 (u1)**. 산출물: `construction/u1-ingestion-index/infrastructure-design/` 2종. 컨테이너 5 / 볼륨 4 / 환경변수 23 / **ID-1~ID-17** / SKIP (u2~u5)
- [x] Code Generation — **APPROVED 2026-08-20 (u1)**. 애플리케이션 코드 **103개 파일**, 문서 3종
- [x] Build and Test — **APPROVED 2026-08-24 (u1 증분)**. 258 테스트 통과, Docker 실측 완료, 결함 1~23 수정. 산출물 `construction/build-and-test/` 6종
- [x] *(사후)* **결함 24 수정 2026-08-25** — `MAX_CHUNK_TOKENS` 미강제. BR-27a 신설 + BR-31 보강, 재색인 검증 완료 (상한 초과 0 / 최댓값 999)

### 🟢 CONSTRUCTION PHASE — 유닛 `u2-rag-qa` (2/5)
- [x] Functional Design — **APPROVED 2026-08-25**. 산출물 `construction/u2-rag-qa/functional-design/` 4종. 엔터티 E14~E18 / 값객체 V1~V4 / Enum 5 / **BR-63~BR-96 + BR-86a + BR-92a**. 검토 지적 3건 반영
- [x] NFR Requirements — **SKIPPED** (실행 계획대로)
- [x] NFR Design — **APPROVED 2026-08-25**. 산출물 `construction/u2-rag-qa/nfr-design/` 2종. **SP-1~9 / PP-1~6 / CP-1~3** / 컴포넌트 N1~N6 / 환경변수 12
- [x] Infrastructure Design — **SKIPPED (u2)** (실행 계획대로. `reranker` 컨테이너는 NFR Design 산출물에 포함)
- [x] Code Generation — **완료 2026-08-25**. 신규 26 / 수정 8 파일, 문서 3종
- [x] Build and Test — **APPROVED 2026-08-26 (u2 증분)**. 단위 425 + 통합 6 통과,
      NFR-1·NFR-2 충족, **결함 25~39 (15건) 발견·수정**. 산출물 `construction/build-and-test/u2-*.md` 2종

**🟢 유닛 `u2-rag-qa` 완료 (2026-08-26) — ⭐ 계획상 "단독 완결 포트폴리오 최소 목표" 도달**

### 🟢 CONSTRUCTION PHASE — 유닛 `u3-substance-card` (3/5) — **순서 변경**
> 계획은 `u2 → u4 → u3` 이었다. u2 Build & Test 에서 **물질 마스터가 0행**이고
> BR-38·BR-65 가 사실상 비활성임이 드러나, 그 상태로 골든셋을 만들면 **"물질 검색이
> 죽어 있는 상태"를 정답으로 굳힌다.** 부수 이점으로 u3 은 LLM 을 쓰지 않아
> 무료 티어 하루 ~3질의 제약을 받지 않는다. 근거는 `audit.md` 2026-08-26T09:00.
- [x] Functional Design — **산출물 생성 2026-08-26, 승인 대기**. `construction/u3-substance-card/functional-design/` 4종.
      새 테이블 0개 / 값객체 V1~V3 / **BR-97~BR-110** / 워크플로 W12~W14 / 화면 P7·P7-1
- [x] Code Generation — **완료 2026-08-26**. 신규 8 / 수정 5 파일. 마이그레이션 없음.
      **결함 40 해소(세 얼굴) + 결함 41~43**. 단위 449 / 통합 22 통과
- [x] **결함 44 해소 — BR-08 물질 선정 구현 + 재수집 (2026-08-27)**
      마스터 40건이 MSDS 코퍼스와 **교집합 0** 이라 카드가 전부 6/7 결측이던 문제.
      선정 기준을 "코퍼스가 이미 문서를 가진 물질"(사고 `substances` 구간 + MSDS 제목)
      로 구현하고 **정규화 후 완전일치**만 인정한다. 부분일치는 실측으로 폐기 —
      "톨루엔"은 마스터 68건, "황산"은 56건의 부분문자열이라 40건 예산이 유도체로 찬다.
      **BR-08 ②(`is_regulated`)는 소스에 필드가 없어 미구현**으로 기록(FR-26 과 같은 처리).
      재수집 `scanned 7,189 / matched 9 / 성공 9`. 톨루엔·황산·메틸알코올·암모니아·
      염소·수소·아크릴산·메틸에틸케톤 확보. `substance` 40 → **49행**.
      부수로 **결함 46**(목록 소진 시 `items: ""` → 스키마 오류) 수정.
      신규 `app/ingestion/substance_selection.py`
- [x] **결함 47 — 파일 문서가 물질에 연결된 적 없음 (2026-08-27)**
      결함 44 의 나머지 절반. 연결이 페이로드 `cas_number` 만 읽어 **MSDS PDF 8건은
      링크 0**이었고, 카드는 `document_substance` 로만 MSDS 에 닿으므로 마스터에
      황산이 생겨도 카드는 비어 있었을 것이다. 페이로드에 CAS 가 없으면 **본문을
      스캔**하고 **마스터에 있는 CAS 만** 링크한다. 관계는 문서당 → **물질당**으로
      변경(혼합물 데이터시트는 구성성분 14종 중 어느 것의 데이터시트도 아니다).
      재색인 전 **건식 시뮬레이션**으로 링크 6건 예측 확인. 단위 **496 통과 + 1 스킵**
- [x] **재색인 검증 + 카드·CAS 종단 (2026-08-27)** — job 26, 79/79 성공
      코퍼스 **79문서 / 1,649청크 / 1,649벡터 / 물질 49 / doc_link 56**.
      상한 초과 0(최장 999/1,000) · BR-30 위반 0 · 벡터 누락 0 · 고아 링크 0.
      링크 6건이 **건식 시뮬레이션과 완전히 일치**. 카드: 황산 **0/7 결측**,
      메틸알코올 0/7, 톨루엔 1/7, 암모니아 6/7(코퍼스에 MSDS 없음 — 정직한 결측).
      CAS 종단 answered / 4,215ms. 단위 496+1스킵 / 통합 **25 통과 + 1 스킵**.
      가상 문서 삭제 후 최종: **78문서 / 1,633청크 / 1,633벡터 / doc_link 55**,
      카드 메틸알코올 0/7 · 톨루엔 1/7 · 황산 2/7.
      부수 **결함 48**: 통합 테스트가 매 실행마다 실코퍼스 청크를 1개씩 영구 삭제하고
      있었다 → 전용 픽스처로 교체, 잃은 청크는 문서 39 부분 재색인으로 복구.
- [x] Build and Test (u3 증분) — **산출물 생성 2026-08-27, 승인 대기**
      `build-and-test/u3-build-and-test-summary.md` · `u3-test-instructions.md`
      단위 496+1스킵 / 통합 25+1스킵 / ruff clean.
      **NFR-3 카드 P95 47.4ms (예산 1,000ms)** · NFR-28 도달불가 호스트로 증명.
      BR-102·105·106 카드 **49건 전수** 위반 0 · BR-107 스냅샷 51→51 ·
      반사 XSS/주입 6종 전부 이스케이프.
      ⚠️ 발견: **BR-31a ↔ BR-104 충돌** — 섹션 중앙값이 20토큰 미만이면 문서가
      섹션 없는 청크 하나로 접혀 카드가 내용을 못 읽는다. 카드 1/49 영향.
      결함이 아니라 설계 결정 대기(선택지 A/B/C는 요약 5절).
- [x] **u3 승인 완료 (2026-08-27)** — "승인. u4 진행해주세요"

### 🟢 CONSTRUCTION PHASE — 유닛 `u4-evaluation` (4/5)
> **⭐ 채용 관점에서 가장 차별화되는 산출물.** S5 가 S3 를 그대로 호출하므로
> 평가 경로와 실사용 경로가 같다(DD-22).
- [x] Functional Design 계획 — FQ5-1~14 **전부 권장안으로 확정 2026-08-27**
- [x] Functional Design 산출물 — **생성 완료 2026-08-27, 승인 대기**
      `u4-evaluation/functional-design/` 4종 + `eval/golden-set.yaml` 초안 30문항.
      신규 테이블 2개(`evaluation_run`·`evaluation_item`) / **BR-111~130** /
      W15~W18 / 지표 8종 계산식·비용·한계.
      골든셋은 **SQL 조회로 작성**(LLM 미사용) 후 실 코퍼스 대조 검증 **실패 0건**.
      law 10 / substance 8 / msds 4 / incident 3 / refusal 5 = answer 25 + refusal 5.
- [x] 골든셋 검토 — 사용자 "그대로 진행" (2026-08-28)
- [x] Code Generation — **완료 2026-08-28**. 신규 12 / 수정 8.
      마이그레이션 **`0003_evaluation` 적용 완료** (u1~u3 테이블 변경 0).
      단위 **559 통과 + 1 스킵** / 통합 **39 통과 + 1 스킵** / ruff clean.
      **첫 실측** `evaluate --retrieval-only`: 30문항 / **LLM 0 호출** / 수초 —
      Recall@5 **0.700** · MRR **0.546** · 거부 정확도 **0.400** · 오거부율 0.000.
      **결함 49**: Recall@10 은 `final_top_k=5` 라 구조상 측정 불가(부류 ②) →
      깊이를 실측해 `None` 으로 내고 이유를 적는다.
- [x] Build and Test — **산출물 생성 2026-08-28, 승인 대기**
      `build-and-test/u4-build-and-test-summary.md` · `u4-test-instructions.md`
      단위 **573+1스킵** / 통합 **40+1스킵** / ruff clean.
      `--retrieval-only` 30문항 LLM 0 · `--full` 21/30 후 `partial` · `--resume` ·
      **종료코드 0/2/3/4 실측**. 미검증 4건(심판·정답률·인용·재개) **전부 실행됨**.
      **🔴 전제 정정**: 병목은 생성이 아니라 **심판**이다 — flash-lite 68호출 무사,
      3.6-flash 20번째에서 429. 전체 1회 **7일 → 2일**. 설계는 유지, 근거만 정정.
      **결함 50~53** (비용 집계 84% 누락 · 심판 미추적 · 문항 수 오표시 ·
      통합 테스트가 기준선 남김).
- [x] **u4 승인 완료 (2026-08-29)** — "승인. 내일 재개하고 완주하면 기준선 승격해줘"
- [ ] 실행 10 완주(`--resume 10`) → 완주 시 기준선 승격
      **2026-08-29 시도: 미완주.** inc-01 채점 후 inc-02 에서 다시 429.
      `partial` 23/30 — **승격하지 않았다**(미채점 7건에 거부형 5건이 전부 들어 있어
      기준선이 편향된다). **남은 작업은 심판 2회**(inc-02·inc-03), 거부형 5건은 0회.
      **할당량 창이 KST 자정에 리셋되지 않는다**(실측: 하루 지나 1회만 열림).
      규칙은 아직 모른다 — 단정하지 않고 기록한다. 결함 54(재채점이 타임스탬프를
      옮기지 않음) 수정.
- [x] **실행 10 완주 + 기준선 승격 완료 (2026-08-29 16:10)**
      `succeeded` 30/30 / 실패 0 / LLM 40.
      **Recall@5 0.700 · MRR 0.546 · 정답률 0.792 · 인용 정확도 0.553 ·
      충실도 1.000 · 거부 정확도 0.600 · 오거부율 0.040**
      유형별: 사고 1.000 / MSDS 0.750 / 법령 0.700 / **물질 0.375**(가장 약함).
      **2단계 검증이 임계값이 놓친 거부를 하나 잡았다** — ref-04 카드뮴,
      거부 정확도 0.400 → 0.600 (BR-76 실측).
      **결함 55**: 기준선이 하나뿐이면 검색전용 실행이 `full` 기준선과 매번
      `incomparable` 이 되어 **매일의 회귀 가드가 영원히 발화하지 못한다**
      → 기준선을 **모드별**로 분리.
- [x] **검색전용 기준선 승격 완료 (2026-08-29)** — 실행 73.
      기준선 2개: **10(full)** · **73(retrieval_only)**.
      **NFR-26 회귀 판정이 처음으로 실제 동작했다** — 실행 74 vs 73,
      전 지표 +0.000, 판정 `ok`, **exit 0**, `incomparable` 경고 0.
      결함 55 수정 전에는 이 자리에 경고 3줄과 `incomparable` 이 있었다.
      회귀를 **감지하는** 경로는 단위 테스트가 덮는다 — 실환경에서 인위적으로
      품질을 떨어뜨려 확인하지는 않았다(설정을 바꾸면 `incomparable` 이 되므로).
- **🔴 미검증 4건이 전부 `--full` 한 줄에 걸려 있다**: 심판(C47)·정답률·인용 정확도·
  할당량 재개·회귀 종단. 131 호출 = 무료 티어 7일.
  u1·u2 에서 "한 번도 실행된 적 없음"이 결함 5건을 만든 바로 그 자리다.
- **품질 실측(개선 아님, 기록)**: CAS 번호 질의는 3/3 적중, 물질명 질의는 3/8.
  거부 5건 중 3건(의료·카드뮴·벤젠)이 답변됐다 — 도메인 안 근거 없는 질문이 새는 것.
- **🔴 지배 제약**: 전체 평가 1회 = **최소 7~8일**(무료 티어 모델당 20/일 × 질의당
  5.25 호출). 단, **Recall@k·MRR·거부 정확도는 LLM 0 호출**이라 매일 전 문항 실행 가능.
- **선행 조건 해소**: 결함 40 — substance 40 / synonym 80 / doc_link 40 / chunk cas 273

### 🟢 CONSTRUCTION PHASE — 유닛 `u5-account-upload` (5/5, 마지막)
> **Q27=A 보안 기준선이 겨냥한 유닛.** 비밀번호·토큰·업로드·격리를 한꺼번에 다룬다.
- [x] Functional Design 계획 — FQ6-1~14 **전부 권장안으로 확정 2026-08-30**
- [x] Functional Design 산출물 — **생성 완료 2026-08-30, 승인 대기**
      `u5-account-upload/functional-design/` 4종.
      신규 테이블 1개(`user_account`) + `document` 업로드 컬럼 3개 /
      **BR-131~152** / C51~C55 · S6·S7 · W19~W24 / 화면 P8·P9·P10.
      **핵심**: 격리를 만드는 것이 아니라 `owner_id` 에 **값을 넣는** 유닛이다 —
      `query_service.py`·`indexing_service.py`·`vector_index.py` **세 파일이 안 바뀐다**.
      정직하게 좁힌 결정: BR-140("악성 파일 차단"이라 쓰지 않는다) ·
      BR-151(익명 질의 유지) · BR-146(남의 문서에 404) · BR-134(로그인 실패 이유 미구분).
- [x] **u5 Functional Design 승인 (2026-08-30)**
- [x] NFR Design 계획 — **FQ7-1~11 생성 2026-08-30, 답변 대기**
      `plans/u5-account-upload-nfr-design-plan.md`
      중심은 **FQ7-8 격리를 어떻게 증명하는가** — 규칙을 적는 것과 지켜지는 것은
      다르고, 이 프로젝트는 "경로가 한 번도 돈 적 없다"로 결함 5건을 만들었다.
      권장안 3겹: 교차 접근 통합 테스트 · `Scope(` 직접 생성 정적 금지 ·
      검색 경로별 필터 단위 테스트.
      실측: NFR-14 마스킹이 **`Cookie:` 는 못 잡는다**(JWT 가 통째로 들어 있다).
- [x] NFR Design 산출물 — **생성 완료 2026-08-30, 승인 대기**
      `u5-account-upload/nfr-design/` 2종. **신규 컨테이너 없음.**
      AP-1~4(인증) · UP-1~4(업로드) · **IP-1~3(격리)** · OP-1~2(관측) /
      환경변수 11 · 볼륨 `safeenv_uploads` · 검증 11항목.
      **업로드 텍스트 인젝션에 새 방어가 필요 없다** — 같은 색인 경로를 쓰므로
      u2 의 SP-3·SP-4·SP-5 가 그대로 붙는다(BR-142 가 보안 결정이기도 한 이유).
      각 패턴에 **막지 못하는 것**을 함께 적었다: 백오프는 늦출 뿐 막지 않고,
      탈취 토큰은 최대 12시간 유효하며, 업로드 검증은 안티바이러스가 아니다.
      방어 심층도에서 **3차가 비어 있는 줄이 셋**(토큰 무효화·CSRF·용량).
- [x] **u5 NFR Design 승인 (2026-08-30)**
- [x] Code Generation — **완료 2026-08-30**. 신규 22 / 수정 12.
      마이그레이션 **`0004_account` 적용** (u1~u4 테이블 변경 0).
      단위 **618 통과 + 1 스킵** / 통합 **53 통과 + 1 스킵** / ruff clean.
      **격리는 만든 것이 아니라 값을 넣은 것** — `query_service.py`·
      `indexing_service.py`·`vector_index.py` 세 파일이 안 바뀌었다.
      **u4 지표 전 항목 +0.000, 판정 `ok`** — 검색 경로 무변경을 숫자로 확인.
      돌려봐서 나온 것 5건: 마스킹 정규식 무력화(백스페이스) · 짧은 JWT 키 허용 ·
      로그인 리다이렉트에 Location 없음 · **색인 실패가 사용자에게 안 보임** ·
      워커 읽기전용 마운트 실증.
- [x] Build and Test (u5) — **산출물 생성 2026-08-30, 승인 대기**
      `build-and-test/u5-build-and-test-summary.md` · `u5-test-instructions.md`
      단위 **618+1스킵** / 통합 **53+1스킵** / ruff clean / NFR-28 증명.
      **격리 3겹**: 통합 11 · 정적 4 · HTTP 종단 5.
      **정적 검사가 실제로 일을 했다** — `web/routers/query.py` 의 하드코딩된
      공개 스코프를 찾아냈다. 통합 테스트만 있었다면 통과했을 것이다.
      보안 실측: CSRF 400 · 쿠키 HttpOnly/SameSite · 오픈 리다이렉트 무력화 ·
      백오프 1s→2s(잠금 아님) · 업로드 거부 6종 · 이스케이프 · JWT 없으면 기동 실패.
      **로그에 쿠키·이메일·해시·JWT 0건** (마스킹이 지운 게 아니라 애초에 없다).
      **u4 지표 전 항목 +0.000, 판정 ok.**
      **결함 56**: 업로드 원본 링크가 한 번도 열린 적 없음(id vs uuid) —
      인용 출처 링크까지 죽은 링크였다. 부류 ①.
- **착수 전 실측**: 문서가 약속한 격리 기반이 **실제로 있다** —
  `owner_id`(document·chunk·query_log) · `apply_scope()` · `Scope` 필수 인자(DD-19).
  FR-28 질의 경로는 이미 구현됨. u5 는 **값을 넣는 일**이지 로직을 만드는 일이 아니다.
- **없는 것**: 인증 의존성 0(u2 이후 첫 신규 런타임 의존성) · 사용자 테이블 0 ·
  **FR-34 동의 기록 미구현**(u2 는 상시표시 절반만) · 라우터 인증 훅 0
- **u4 평가는 공개 스코프 고정** — `Scope(owner_id=None)` 2곳뿐. 업로드가 지표를
  흔들 경로 없음(확인함)

### 🟡 OPERATIONS PHASE
- [x] **Operations — 완료 2026-08-30**. `aidlc-docs/operations/operations.md`
      실행 계획의 정의대로 **운영 문서 색인**이다 — 새 설계 없이 다섯 유닛의 운영
      정보를 모았다. 현황·주기 작업·기동 요건·제약·장애 대응·보안·백업·문서 색인 +
      **반복한 실패 여섯 가지**(결함 57건 분류) + 다음 우선순위 제안.
- [x] **MSDS 추가 수집 (2026-08-30)** — 암모니아·염소·수소·메틸에틸케톤 4건.
      건식 검증에서 2건 탈락(pypdf 인코딩 미지원·HTML). 아크릴산은 국문 PDF 미발견.
      카드 0/7 결측 1건 → **4건**, 7/7 결측 2건 → 1건.
      대가로 Recall@5 0.700 → 0.667 (sub-07 정답 근거가 새 MSDS 에 밀림).
- [x] **`doc_type` 세분화 (2026-08-30)** — `operations/doc-type-split-review.md`.
      물질 레코드와 MSDS 가 둘 다 `msds` 라 BR-69 타입 분산이 둘을 가르지 못했다.
      **`DocType.SUBSTANCE` 분리 + `safeenv retype` 명령 신설**(스펙 변경마다 재사용).
      **Recall@5 0.667 → 0.700 회복**(시뮬레이션 예측 적중, 다만 law-02 MRR 하락 1건은
      시뮬레이션이 못 봤다). 단위 **629 통과** / 통합 53 통과.
      코퍼스 **82문서 · 1,697청크 · doc_type 4종**.
- [x] **기준선 재승격 (2026-08-30)** — "승격해주세요". 검색전용 **실행 127** 승격
      (Recall@5 0.700 · MRR 0.529 · 거부 0.400 · 오거부 0.000, 코퍼스 82/1,697).
      실행 73 은 자동 강등(모드당 하나). `full` 기준선은 **실행 10 그대로** — 코퍼스가
      바뀌어 이미 비교 불가이나 대체할 `full` 실행이 없다(심판 할당량 2일).
      승격 직후 재실행이 **전 지표 +0.000 / 판정 `ok`** 로 재현됐다.
- [x] **결함 58 — `app`·`worker` 컨테이너가 저녁 내내 구 이미지로 돌고 있었다**
      (2026-08-30). 이미지는 재빌드됐으나 컨테이너가 재생성되지 않아
      `DocType.SUBSTANCE` 가 없는 코드가 떠 있었다. 승격 검증 실행(140)이 0.667 을
      내면서 드러났다. 재생성 후 실행 141 = 0.700 으로 실행 127 과 완전 일치.
      → `evaluate --list` 가 **R@5·MRR 과 `[integration-test]` 표식**을 함께 보여준다.
- [x] **재빌드 후 재생성 강제 구조 (2026-08-31)** — "재빌드 후 재생성 강제하는 구조
      만들어줘". 결함 58 을 문서가 아니라 코드로 막았다. 네 겹:
      ① `app/core/build.py` 가 Dockerfile 이 COPY 하는 여섯 항목을 해싱해 코드 정체를
      만든다(스탬프 아님 — 스탬프는 그 자체로 낡는다) ②`/healthz`·`stats`·`--list`
      에 노출 ③ `evaluation_run.build_id`(마이그레이션 `0005_build_id`) ④ **집행**:
      통합 테스트가 붉어지고 `evaluate --promote` 가 거부한다(종료코드 3,
      `--accept-stale` 로만 우회하며 `note` 에 기록).
      `build_id` 는 비교 가능성 필드가 **아니다** — 넣으면 코드 변경마다 `incomparable`
      이 되어 가드가 죽는다(결함 55 와 같은 모양). 실측으로 확인: 새 코드 실행 170 vs
      구 코드 기준선 127 = 전 지표 +0.000 / `ok`.
      **만든 검사가 자기 대상 앞에서 skip 하는 결함을 스스로 잡았다** — 붉은불을 먼저
      확인했기 때문. 단위 **641 통과**(+12) / 통합 **60 통과**(+7).
- [x] **물질명 검색 개선 BR-65a (2026-09-01)** — "물질명 검색 개선 진행해줘".
      원인: BR-65 가 해석한 `substance_names` 를 **아무 검색 경로도 소비하지 않았다**
      + 물질 청크에 물질명이 없어 CAS(meta 정확일치)만 뚫렸다.
      3단: 이름→CAS→`lookup_exact` / 경로 섹션 우선+상한 3 / 주제 보장
      `ensure_subject_presence`(BR-69 대칭). 각 단은 앞 단의 실측 부작용이 요구했다
      (①에서 msds-01 1.0→0.0 회귀 → ②가 치유). **Recall@5 0.700→0.833 ·
      MRR 0.529→0.609 · 재색인 0회 · 회귀 0**. 단위 656 / 통합 66 통과.
      sub-02 잔여는 골든셋 판단 항목으로(operations 10절 6b)
- [x] **골든셋 판단 B·B + 문서 20·24 두 컬럼 구원 (2026-09-01)** — "권장안대로 B
      유지하고 문서 20 재파싱 진행해줘". 골든셋 무변경. 두 컬럼 PDF 를
      실패-트리거 재추출(`extract_pdf_columns` + `_retry_two_column`)로 구조화 —
      기하학 1차 적용은 전수 검증에서 autorefinishes 악화(역전 0→2)가 나와 기각.
      **황산·톨루엔 카드 결측 0** · Recall@5 0.867 · MRR 0.630 · law-07 0→1.
      sub-02 는 여전히 0 — "재파싱이 근본 경로"라던 예측은 틀렸다고 기록.
      코퍼스 1,712청크
- [x] **검색전용 기준선 승격: 실행 258 (2026-09-02)** — "검색전용만 먼저
      승격해주세요". R@5 0.867 · MRR 0.630 · 코드 fcedc13a361a · 코퍼스 1,712.
      240 자동 강등, 재실행 +0.000/ok
- [x] **law-08·09 검색 개선: 조문 제목 층 (2026-09-02)** — "law-08·09 검색 개선
      진행해줘". 근인: 색인 쪽 조사 문제(law-09 도달 불가)·순위 밀림(law-08).
      본문 prefix 5개 변형을 전부 실측 후 기각(제로섬 — 매번 기존 문항 상실).
      채택: `meta.section_title` LIKE 층(5글자+, 상한 5, 점수 0.3).
      **Recall@5 0.867→0.933 · MRR 0.630→0.708 · Recall 회귀 0.**
      law-08 1위·law-09 5위 진입. 남은 0 은 msds-02·sub-02(기존)
- [x] **검색전용 기준선 승격: 실행 283 (2026-09-02)** — "승격". R@5 0.933 ·
      MRR 0.708 · 코드 e0f763d6cb27. 258 자동 강등, 재실행 +0.000/ok
- [x] **msds-02 검색 개선 (2026-09-02)** — "msds-02 검색 개선 진행해줘".
      원인: BR-65a 이름 인상이 CAS meta 로 문서 20(재파싱된 황산 MSDS)의
      16청크까지 쓸어와, 주제 무일치 동점이 행 순서로 깨져 잡섹션이 1.0 을 달았다.
      수정: 질의 주제→MSDS 섹션 지도 + 무일치 청크 인상 금지.
      **R@5 0.933→0.967 · MRR 0.708→0.766 · 회귀 0.** msds-02 1위, msds-03 MRR 1.0.
      남은 검색 0 은 sub-02 하나(골든셋 B 결정 유지)
- [x] **거부 정확도 개선 BR-73a (2026-09-02)** — "거부 정확도 개선 진행해줘".
      **안전 문제였다**: 카드뮴·벤젠(코퍼스에 없음) 질문에 다른 물질의 독성·응급조치
      자료로 답하고 있었다. 임계값으로는 불가 — ref-05(0.631) > msds-02(0.627),
      결함 27 과 같은 모양. 해법: 지목된 물질이 없는데 최상위 근거가 물질 범위
      문서(MSDS·substance)면 거부. `all()` 은 BR-69 분산이 무력화해 최상위로 판정.
      **거부 정확도 0.400 → 1.000 · 오거부 0.000 유지 · 검색 불변.**
      대가: 물질 미지목 일반 MSDS 질문 2건 과잉거부(프로브로 측정, 되묻기 문구로 완화).
      단위 676 / 통합 72
- [x] **C4(b)·C8(a) 구현 (2026-09-07)** — "권장안대로 진행해줘".
      **Recall@10 이 처음 측정된다: 1.000.** 상위 5를 건드리지 않는 설계라
      Recall@5 는 0.967 불변(MRR 만 sub-02 의 6위 적중이 보이며 +0.006).
      `observation_top_k` 를 config 스냅샷에 넣어 관측 깊이가 다른 실행은
      `incomparable` 로 갈린다. 온도 0 은 모든 목적에 적용 — 효과 판정은
      다음 `--full` 완주(거부 문항이 고정되는지). 단위 715 · 통합 113.
      C8(b) 허용오차 재교정은 노이즈 크기 측정이 선행이라 미착수
- [x] **C7 판정: 진단 적중 + `full` 기준선 549 승격 (2026-09-06)** — 충실도
      **0.917 → 1.000**(22/24 → 24/24). sub-07·sub-08 이 둘 다 불충실 → 충실.
      정답률 1.000 → 0.958 은 C7 의 대가가 아니라 **분모 이동**이다: 거부된
      답변형이 두 실행 모두 1개인데 대상이 sub-06 → law-05 로 바뀌었다.
      새 관측 — **거부 경계가 실행마다 흔들린다**(지표가 같아도 같은 것을 재는
      것이 아니다). 387 은 C7 이전 코드라 재현되지 않으므로 승격했다
- [x] **B 그룹 완료 · D4 · D5 · 백로그 재정리 (2026-09-04)** — `/api`·`/admin`·
      `/usage` 를 관리자 전용으로(익명 401/303, `POST ingest` 401). 역할은 토큰이
      아니라 DB 에서 읽어 강등이 즉시 듣는다. `.gitattributes` 로 줄바꿈 LF 고정
      (지문 `d9fdd7511c15`). `safeenv/` 는 증명 3건 통과 후 삭제, 로그는 보존.
      단위 691 · 통합 108. 백로그 25~35 → **12~20커밋**, 1순위가 보안에서
      **답변 품질(C7 충실도 하락 조사)**로 이동
- [x] **`full` 기준선 387 승격 + law-09 진단 판정 (2026-09-04)** — 첫 시도 완주
      (30/30). 정답률 **1.000** · R@5 0.967 · MRR 0.766 · 인용 0.717 · 거부 1.000.
      **law-09 진단은 맞았다** — 불충실·오답이 충실·정답으로 회복. 다만 충실도
      순증은 -0.041(0.958→0.917): sub-07·sub-08 이 새로 `answered_partial` 이 됐다.
      BR-65a 로 근거 구성이 바뀌자 검증이 문장을 걷어낸 것으로 보이며, 여러 변경이
      겹쳐 원인 분해는 불가. 백로그에 조사 항목으로 남김
- [x] **첫 커밋 배치 (2026-09-03)** — 4커밋(문서). 10개가 아닌 이유: 심판 일일
      한도 20콜을 정확히 소진해 실행 387 이 27/30 에서 멈췄고, 승격이 안 되면
      B·C·D3 이 전부 빌드 지문·코퍼스 지문을 건드려 진행 중 실행을 깨뜨린다.
      **빈 커밋으로 채우지 않았다.** CI·Docker 빌드 통과 확인(GitHub API).
      새 발견: `core.autocrlf=true` 에서 줄바꿈 정규화가 빌드 지문을 바꾼다
      (LF 113파일 → `03bab957bade`→`7b008836585f`). D4 는 승격 이후로 순서 고정
- [x] **커밋 백로그 작성 (2026-09-02)** — "하루 10개씩". 초기 커밋 392파일은
      사용자가 이미 푸시(95677a9). `operations/backlog.md` 에 **커밋 단위로 쪼갠
      25~35항목**(A 진행중 · B 보안 8~12 · C 품질 6~10 · D 정리 5~8)과 커밋 규약.
      빈 커밋·인위적 분할·날짜 소급은 하지 않는다. 초기 커밋 분할은 force 푸시가
      필요해 권하지 않음(E4)
- [x] **저장소 이전 + GitHub Actions CI (2026-09-02)** — "B로 진행". 작업·Docker·
      데이터를 `chemical_safe/` 로 이전(깃 저장소 = 작업 트리, 결함 58 재발 방지).
      compose `name: safeenv` 덕에 볼륨·컨테이너 유지 — **DB 무이관**(문서 82 ·
      청크 1,712 · 실행 387 · 기준선 2개 보존). 통합 72 통과로 확인.
      CI: `ruff + 단위 677` 약 1분(ml 미설치로 충분함을 실측), Docker 빌드는
      main push 만. 통합·평가·CD 는 이유와 함께 제외. `safeenv/` 는 백업으로 잔존
- [x] **검색전용 기준선 승격: 실행 385 (2026-09-02)** — "승격". R@5 0.967 ·
      MRR 0.766 · **거부 1.000** · 코드 03bab957bade. 333 자동 강등, 재실행 +0.000/ok.
      `full`(276)은 BR-73a 이전 — **답변 경로가 바뀌었으므로 재완주 가치가 크다**
- [x] **검색전용 기준선 승격: 실행 333 (2026-09-02)** — "승격해주세요".
      R@5 **0.967** · MRR 0.766 · 코드 042322be1757. 283 자동 강등,
      재실행 366 +0.000/ok. u4 착수 0.667 → 0.967, **골든셋 무수정**
- [x] **`full` 완주 + 기준선 276 승격 (2026-09-02)** — "full 완주하고 221 갱신해줘".
      6구간 자동 재개로 하루 완주(실패 0, 심판 25콜). 정답률 **0.917** · 인용 0.610 ·
      충실도 0.958(law-09 단독, 기지 검색 공백의 하류 증상) · 오거부 0.040.
      **기준선 258·276 이 같은 코퍼스(1,712)·코드(fcedc13a361a)** — 양 가드 정상
- [x] **검색전용 기준선 승격: 실행 240 (2026-09-01)** — "승격해주세요".
      R@5 0.833 · MRR 0.609 · 코드 f35850dcd83f. 219 자동 강등, 게이트 통과,
      재실행 +0.000/ok. `full`(221)은 BR-65a 이전 측정 — 다음 완주 때 갱신 권고
- [x] **`full` 기준선 갱신 완주 + 승격 (2026-09-01)** — "완주하면 승격해줘".
      실행 **221**: 이틀 아닌 하루 안에 3구간(14 → 18 → 30문항)으로 완주, 실패 0.
      Recall@5 0.700 · MRR 0.529 · 정답률 0.870 · 인용 0.556 · 충실도 1.000 ·
      거부 0.400 · 오거부 0.080. 실행 10 자동 강등. **기준선 2개(219·221) 모두
      현 코퍼스·코드 정체(d983dcbbf1e1) 보유 — 비교 가능성 회복.**
      오거부 2건(sub-04·06)은 물질명 검색 약세와 같은 뿌리로 기록(결함 아님)
- [x] **검색전용 기준선 재승격 (2026-08-31)** — "남은것 진행해주세요". 실행 **219**
      (Recall@5 0.700 · MRR 0.529, 코드 `d983dcbbf1e1`). 127 자동 강등.
      **기준선이 처음으로 코드 정체를 갖는다.** 확인 실행 220 = 전 지표 +0.000 / `ok`.
      순서(린트 → 재배포 → 측정 → 승격)는 어제 만든 구조가 강제했다 — 반대로 했으면
      승격이 거부됐다.
- [x] **`0001_base.py` 린트 (2026-08-31)** — u1 때부터 있던 I001 1건. 한 줄 이동,
      의미 변화 0. 원인은 `migrations/` 가 린트 범위에 없었던 것. 표준 명령을
      `ruff check app/ tests/ migrations/` 로 고쳤다

## Requirements Analysis 결정 요약 (2026-08-20)
- **MVP 중심 기능**: 자연어 질의응답(FR-14~22) + 2순위 물질 안전 카드(FR-23~26)
- **코퍼스 3종**: MSDS(PDF 파싱) / 화학 법령 조문 / 화학사고 사례 — 물질 1,000종 규모
- **RAG 핵심**: 하이브리드 검색 + 리랭커 → 문장 단위 인용 → 근거 부족 시 **답변 거부**
- **차별 요소**: 골든 QA 셋 자동 평가 + LLM-as-judge, LLM 호출 비용·지연 추적
- **⚠️ R-7 범위 총량**: FR 48 / NFR 32 → 개인 프로젝트 3~4개월 분량. 승인 시 진행 방향
  (a)단계적 / (b)축소 / (c)현행유지 확인 필요
- **⚠️ AI 판단 8문항**: Q4/Q5/Q10/Q19/Q21/Q22/Q23/Q30 — `requirements.md` §10 참조

## Workflow Planning 결정 요약 (2026-08-20)
- **유닛 5개**: u1 수집·색인(기반) / u2 질의응답(MVP 핵심) / u4 평가 하네스 / u3 물질 카드 / u5 계정·업로드
- **u4를 u3보다 먼저 배치**: 평가 하네스를 u2 직후 확보하면 이후 모든 변경의 품질 회귀를 즉시 수치로 감지
- **중단 가능 지점**: u2 완료 시점이 단독 완결 포트폴리오 최소 목표, u4 완료 시점이 권장 목표
- **Quality Gates 8종**: QG-1~QG-8 (`inception/plans/execution-plan.md` §6)

## Application Design 결정 요약 (2026-08-20)
- **컴포넌트 60종**: 기반 4 / 포트·어댑터 9 / 수집 4 / 처리 6 / 색인 4 / 작업 2 / 검색 6 / 생성 7 / 관측 1 / 평가 5 / 카드 2 / 계정 5 / 진입점 5
- **서비스 8종**: S1 수집 / S2 색인 / **S3 질의응답(핵심)** / S4 카드 / S5 평가 / S6 계정 / S7 문서 / S8 관측
- **포트 4종**: SourceAdapter / LLMPort / EmbeddingPort / RerankerPort (+ 추적 데코레이터 C13)
- **설계 결정 DD-1~DD-25**: DQ 답변 기반 18건 + 설계 과정 도출 7건
- **핵심 결정 3건**: DD-8 구조화 출력 인용(검증 결정론화) / DD-9 2단 거부 / DD-21 후행 유닛 확장 지점 선반영
- **검증**: FR 미매핑 0 / 순환 의존 0 / 유닛 역방향 의존 0 / Security 차단성 findings 0
- **⚠️ DD-1 확인 요망**: 패키지 구성이 DQ-1의 B와 C 사이 (`application-design.md` §5)

## Units Generation 결정 요약 (2026-08-20)
- **유닛 5개 확정**: `u1-ingestion-index`(FR16/C32) -> `u2-rag-qa`(FR14/C14) -> `u4-evaluation`(FR4/C5) -> `u3-substance-card`(FR5/C2) -> `u5-account-upload`(FR9/C5)
- **배포 모델**: 단일 이미지 모놀리스. web / worker / cli 가 실행 명령만 다름 (UD-3)
- **디렉터리**: 단일 `app/` 패키지. **유닛은 개발 순서 개념이며 디렉터리 경계가 아님** (UD-4)
- **마이그레이션**: 유닛별 Alembic 리비전 + 재색인 유발 요소(`chunk.owner_id`, `substance_synonym`)만 u1 선반영 (UD-6)
- **DoD 7항목**: 코드 + 단위 + 통합 + **Docker 기동 실측** + README 갱신 + QG + 평가 회귀 없음 (UD-7)
- **선반영 확장 지점 5건**: u1에 2건 / u2에 3건 — 후행 유닛의 스키마·시그니처 변경 방지
- **⭐ 목표 지점**: u2 완료 = 최소 목표(6~8주) / u4 완료 = 권장 목표(8~10주) / 전체 11~14주

## u1 Build and Test 결과 요약 (2026-08-20)
- **빌드**: OK — compileall 0, ruff All checks passed, Docker 이미지 **743MB**
- **단위 테스트**: **163 passed, 0 failed** (최초 152 + 회귀 11)
- **Docker 실측**: 컨테이너 5종 기동, migrate 선행, `/healthz` 4항목 전부 ok
- **파이프라인 종단**: 실제 BGE-M3 로 MSDS 16청크 / 법령 7청크, dim=1024
- **BR-30 오프셋 무결성 위반 0행** (u2 인용의 전제 확보)
- **NFR-18 실측 확정**: LAN IP 접속 거부, DB·큐 호스트 미노출
- **품질 게이트**: QG-1·2·3·6·7·8 통과 / QG-4·5 는 u4 이월. **SC-8 달성**

### 발견·수정된 결함 7건 (+ 부수 4건)
1. 청킹이 섹션 경계를 넘어 병합 (16섹션 -> 14청크) — 인용 정확도. **BR-31 정정**
2. `Authorization: Bearer <token>` 미마스킹 — 보안
3. `extra` 최상위 비밀 필드 미마스킹 — 보안
4. 이미지 5.81GB (CUDA torch) -> **743MB** (87% 감소)
5. 워커 크래시 루프 — **BR-52 하트비트가 탐지**
6. 작업 전체가 단일 트랜잭션 — **DD-24/BR-53 위반**, FR-6·FR-8 무력화
7. 재개 시 `original_path` 유실 — 재개 경로가 재개 근거를 파괴
부수: `ref_key`/`input_tokens` 과잉 마스킹, Hypothesis 픽스처, ruff B008

### ⚠️ CON-2 정정: 호스트 포트 8200 -> **8300**
`trip-app` 이 이미 8200 점유 중 (ID-16 6축 조사가 trip 누락). 나머지 5축 충돌 없음 실측.

### ⚠️ 설계 예상 대비 차이 (u2 이월)
- 모델 볼륨 실측 **4.3GB** (예상 2GB) — 디스크 요구 재산정 필요
- `app` 메모리 임베딩 로드 시 **1.70GiB/2GiB (85%)** — **u2 리랭커를 `app` 에 두면 초과 위험**
- `app` 에 `safeenv_models` 볼륨 미마운트

### 미해소 3건 (전부 R-1/R-2 의존)
공공 API 응답 형식 / MSDS 파싱 성공률 / NFR-4·NFR-9 성능 — 측정 절차는 완비

## Current Status
- **Lifecycle Phase**: **OPERATIONS** (CONSTRUCTION 5/5 완료 2026-08-30)
- **Current Unit**: **`u4-evaluation`** (4/5) — u1·u2·u3 승인 완료
- **Current Unit**: 없음 — **u1~u5 전부 승인 완료**
- **Current Stage**: ✅ **AI-DLC 전 단계 완료** — CONSTRUCTION 5/5 · OPERATIONS
- **Next Stage**: 없음. 다음 작업은 `operations.md` 10절의 우선순위 제안 참조
- **Status**: ▶ 진행 중
- **✅ 해소**: `document 4`(가상 황산 MSDS, `example.test`) **삭제 완료**
  (사용자 승인 2026-08-27). `data/originals/fix-check/` 원본도 제거.
  코퍼스 78문서 / 1,633청크. 황산 카드는 예고대로 0/7 → **2/7 결측**.
- **관찰**: 남은 결측의 원인은 **MSDS PDF 2건(문서 20·24)의 구조화 실패**(섹션 0)다.
  8건 중 6건 구조화 = 75%. R-2(PDF 파싱 성공률)로 이미 등록된 위험이고 u3 범위 밖.
- **✅ 해소**: UQ-10 — OOS-4 vs NFR-26 상충 → 로컬 CLI 종료코드로 확정(UD-10). `requirements.md` 정정 반영 완료

## u2 Code Generation 진행 (2026-08-25)

| # | 작업군 | 상태 |
|---|---|---|
| 1 | 인프라·설정 (`config.py` 12종 / `.env.example` / `llm_pricing.yaml` / compose `reranker` / `prompts/` 3종) | ✅ |
| 2 | 데이터 계층 (E14~E18 ORM / `0002_query` / `QueryRepo` / `LlmCallRepo`) | ✅ |
| 3 | 도메인 타입 (Enum 5 / V1~V4) | ✅ |
| 4 | 검색 계층 (융합 / 검색 클라이언트 / 리랭커 HTTP / `rerank_service`) | ✅ |
| 5 | 프롬프트 조립 (N1·N2·N4 + 인젝션 테스트 20건) | ✅ |
| 6 | 생성·검증 (LLM 어댑터 2종 / 팩토리 / 스키마 가드 / 거부 / 생성 / 검증 / 스트리밍) | ✅ |
| 7 | 인용 표시 (C41 / 동결) | ✅ |
| 8 | 서비스 계층 (S3 / S8) | ✅ |
| 9 | 인젝션 스캐너 (N3, u1 경로) | ✅ |
| 10 | 웹 계층 (P5 / P6 / SSE / 무JS 폴백) | ✅ |
| 11 | 문서 3종 + README | ✅ |

**Code Generation 완료 / Build and Test 완료 — 승인 대기.**
단위 **425 통과 + 1 스킵**, 통합 **6 통과 + 1 스킵**(실 DB), ruff clean.

### ✅ NFR-1·NFR-2 충족 (2026-08-26 실측)
```
NFR-2 검색 P95   예산 2,500ms   실측   109~151 ms
NFR-1 전체       예산 20,000ms  실측 2,154~4,181 ms
```
결정적 요인은 모델 선택이었다 — 같은 프롬프트에 lite 4.1초 vs 3.6-flash 73.3초(18배).
무료 티어는 **모델당 하루 20요청**이라 BR-86a(`1+문장수`)와 곱하면 하루 약 3질의다.
**개발용으로 수용**했고, 할당량 소진이 고장처럼 보이지 않도록 별도 조건으로 승격했다.

### LLM 제공자 전환 (2026-08-25)
Anthropic → **Google Gemini 무료 티어**. `rag/` 의 규칙·워크플로·테스트가 **한 줄도
바뀌지 않았다** — u1 이 구현 없이 `LLMPort` 를 먼저 둔 것(DD-6·DD-21)이 값을 한 지점이다.
스키마 검증은 **제공자와 무관하게** 두었다: BR-79 는 제공자 기능이 아니라 이 시스템의 계약이다.
신규 파일 26 / 수정 8 / u2 테스트 111건.

### ⚠️ 실환경 첫 질의에서 결함 3건 (audit 결함 25~27)
셋 다 단위 테스트와 컨테이너 기동 점검을 통과한 상태였다. **u1 의 검색 경로는 한 번도
실행된 적이 없었다.**
- **결함 25** `to_tsvector(varchar,text)` — 키워드 검색이 처음부터 미동작 (u1 잔존)
- **결함 26** BR-72 가 실현 불가능 — Session 공유로 한쪽 실패가 반드시 다른 쪽을 죽임
- **결함 27** 거부 임계값이 RRF 순위 점수를 읽음 — 보정으로 못 고치는 설계 결함.
  코사인 유사도로 변경, 기본값 0.02 → **0.50** (실측: 적합 0.66~0.71 / 무관 ~0.42)

### 실측 (2026-08-25)
```
"황산 취급 시 보호구는?"   retrieval 5건 / 웜 339ms (NFR-2 예산 2,500ms)
                          근거 1위 = 황산 MSDS msds_08 (노출방지 및 개인보호구)
"오늘 점심 메뉴 추천해줘"   refused / below_threshold + 원문 링크 5건
마이그레이션 0002_query 적용, 테이블 19개, 라우트 19개
```

### 다음 단계 — Build and Test (u2 증분)
**선행 조건: `.env` 에 `ANTHROPIC_API_KEY` 설정.** 없으면 실제 답변 생성·인용·2단 검증·
NFR-1·BR-86a·PP-4 를 전부 검증할 수 없다. 검색·거부 경로는 이미 실측 완료.

### 계획 대비 조정 1건
`retrieval/keyword.py` · `retrieval/vector.py` 를 따로 두지 않는다. u1 의 `KeywordIndex` ·
`VectorIndex` 가 이미 검색을 제공하므로, 두 파일은 얇은 래퍼가 될 뿐이다.
질의 임베딩 캐시(PP-3)와 후보 변환을 `retrieval/retrievers.py` 하나로 합친다.
