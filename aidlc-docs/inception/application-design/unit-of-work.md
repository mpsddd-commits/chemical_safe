# Unit of Work — safeenv

**단계**: INCEPTION / Units Generation — Part 2 (Generation)
**작성일**: 2026-08-20
**근거**: `inception/plans/unit-of-work-plan.md` (UQ-1~UQ-12 답변 확정)

---

## 1. 분해 결정 요약 (UD-1 ~ UD-12)

| ID | 결정 | 근거 |
|---|---|---|
| **UD-1** | **유닛 5개**로 확정 — u1 / u2 / u4 / u3 / u5 | UQ-1=A |
| **UD-2** | 실행 순서 **u1 → u2 → u4 → u3 → u5** 확정 | UQ-2=A |
| **UD-3** | **단일 배포 단위(모놀리스) + 논리 모듈.** 웹·워커가 같은 이미지를 공유하고 실행 명령만 다름 | UQ-3=A |
| **UD-4** | 단일 `app/` 패키지. **유닛은 개발 순서 개념이며 디렉터리 경계가 아님** | UQ-4=A |
| **UD-5** | 유닛 간 통합은 **직접 import**. 계층 규칙만 준수 | UQ-5=A |
| **UD-6** | 유닛별 Alembic 리비전 + **재색인 유발 요소만 u1에 선반영** | UQ-6=B, DD-21 |
| **UD-7** | DoD = 코드 + 단위 + 통합 + **Docker 기동 실측** + README 갱신 | UQ-7=C |
| **UD-8** | **순차 진행** (1인 개발) | UQ-8=A |
| **UD-9** | 유닛 완료 시 **README에 사용법·실행 결과·설계 결정 기록** | UQ-9=A |
| **UD-10** | 평가 회귀는 **로컬 CLI 종료코드**까지만. CI 워크플로 미구축 | UQ-10=A |
| **UD-11** | 스토리 맵을 **FR·NFR ↔ 유닛 매핑표**로 대체 | UQ-11=A |
| **UD-12** | 추가 반영 사항 없음 | UQ-12=A |

### ⚠️ UD-10에 따른 요구사항 정정

**NFR-26** 원문은 "품질 저하를 **CI에서** 자동 탐지"였으나, **OOS-4**(CI/CD 파이프라인 범위 외)와
상충하여 UQ-10=A 로 정리했습니다.

> **NFR-26 (정정)**: 평가셋 회귀 테스트 — 골든 QA 셋 지표가 기준선 아래로 떨어지면
> `CliEntrypoint.evaluate()` 가 **비0 종료코드를 반환**한다. CI 파이프라인 연동은 범위 외이나,
> 이 종료코드만으로 향후 어떤 CI에도 즉시 연결 가능하다.

`requirements.md` §4.7 및 §7(OOS-4)에 본 정정을 반영합니다.

---

## 2. 코드 조직 전략 (Greenfield)

### 2.1 배포 모델 (UD-3)

| 프로세스 | 이미지 | 실행 명령 | 역할 |
|---|---|---|---|
| `web` | 동일 | ASGI 서버 기동 | HTTP 요청 처리 (C56, C57, C58) |
| `worker` | 동일 | 워커 루프 기동 | 큐 소비 및 파이프라인 실행 (C59) |
| `cli` | 동일 | 일회성 명령 | 수집·재색인·평가 (C60) |

**단일 이미지**를 공유하므로 코드·의존성 불일치가 발생하지 않습니다.

### 2.2 디렉터리 구조 (UD-4)

```
safeenv/
  app/
    core/            # C1 Config, C2 Logger, 예외, 공통 타입
    db/              # C3 Database, ORM 모델, C4 Repositories
    ports/           # C5~C8 추상 인터페이스
    adapters/        # C9~C12 구현체, C13 추적 데코레이터
    jobs/            # C28 JobTracker, C29 TaskQueue
    ingestion/       # C14~C17                        [u1]
    processing/      # C18~C23                        [u1]
    indexing/        # C24~C27                        [u1]
    retrieval/       # C30~C35                        [u2]
    generation/      # C36~C42                        [u2]
    observability/   # C43                            [u2]
    evaluation/      # C44~C48                        [u4]
    substances/      # C49, C50                       [u3]
    accounts/        # C51, C52, C55                  [u5]
    documents/       # C53, C54                       [u5]
    services/        # S1~S8 (유닛별로 추가)
    web/             # C56 라우터, C57 템플릿, 정적 파일
    cli.py           # C60
    worker.py        # C59
  config/            # 설정 파일, 소스 정의
  prompts/           # 프롬프트 템플릿 + 버전 (DD-7)
  eval/              # 골든 QA 셋 (DD-18)
  migrations/        # Alembic 리비전
  tests/             # 단위·통합·회귀 테스트
  data/              # 볼륨 마운트 지점 (원본 파일, 업로드)
  Dockerfile
  docker-compose.yml
  pyproject.toml
  README.md
```

**핵심 규칙**: 디렉터리는 **컴포넌트 계층**을 따르고, 유닛은 **언제 그 디렉터리가 채워지는지**만
결정합니다. 유닛명이 붙은 디렉터리는 만들지 않습니다.

### 2.3 유닛 ↔ 디렉터리 매핑

| 유닛 | 신규 생성 | 기존 확장 |
|---|---|---|
| **u1** | `core/` `db/` `ports/` `adapters/` `jobs/` `ingestion/` `processing/` `indexing/` `config/` `migrations/` | — |
| **u2** | `retrieval/` `generation/` `observability/` `prompts/` | `services/` `web/` `db/`(질의이력) |
| **u4** | `evaluation/` `eval/` | `services/` `web/` `cli.py` |
| **u3** | `substances/` | `services/` `web/` `db/`(동의어 데이터) |
| **u5** | `accounts/` `documents/` | `services/` `web/` `db/` `retrieval/`(스코프 적용) |

### 2.4 DB 마이그레이션 전략 (UD-6)

**원칙**: 유닛별로 Alembic 리비전을 추가하되, **재색인을 유발하는 요소는 u1 리비전에 선반영**합니다.

| 리비전 | 유닛 | 내용 |
|---|---|---|
| `0001_base` | u1 | 물질·법령·사고사례·문서·추출텍스트·청크·벡터·작업 테이블<br/>**선반영: `chunk.owner_id`(nullable, 기본 NULL=공개), `substance_synonym` 테이블** |
| `0002_query` | u2 | 질의 이력, LLM 추적 테이블 |
| `0003_eval` | u4 | 평가 실행·문항 결과 테이블 |
| `0004_account` | u5 | 사용자, 면책 동의, 업로드 문서 메타 |

**선반영 근거 (DD-21)**: `chunk.owner_id`를 u5에서 추가하면 이미 적재된 수십만 청크에
`ALTER TABLE`과 재색인이 발생합니다. `substance_synonym`도 u1 수집 시점에 이명 데이터를
함께 적재해야 u3에서 재수집을 피할 수 있습니다.

---

## 3. 유닛 정의

### u1 — `u1-ingestion-index`

| 항목 | 내용 |
|---|---|
| **책임** | 3종 코퍼스를 수집·파싱·정규화·청킹·색인하여 검색 가능한 상태로 만든다. 시스템의 기반(설정·로깅·DB·포트·작업 큐·컨테이너 토폴로지)을 확립한다 |
| **FR** | FR-1~13, FR-40, FR-43, FR-48(운영 화면 골격 + 작업 상태) — **16건** |
| **NFR 검증** | NFR-4, 9, 10, 14, 17, 23, 29, 30, 31 |
| **컴포넌트** | C1~C29, C58, C59, C60(수집·재색인 명령) — **32종** |
| **서비스** | S1 `IngestionService`, S2 `IndexingService` |
| **CONSTRUCTION 스테이지** | Functional Design ✅ / NFR Requirements ⏭ / NFR Design ⏭ / **Infrastructure Design ✅** / Code Generation ✅ / Build & Test ✅ |
| **시연 산출물** | 운영 화면에서 수집 작업을 실행하고 진행률·부분 실패를 확인. DB에 물질 1,000종의 청크·벡터가 적재된 상태 |
| **예상 기간** | 3~4주 |

**주요 위험**: R-2(PDF 파싱 실패율), R-3(로컬 임베딩 속도), R-1(공공 API 키·스펙)

---

### u2 — `u2-rag-qa` — **MVP 핵심**

| 항목 | 내용 |
|---|---|
| **책임** | 자연어 질의에 대해 **출처가 붙은 답변**을 생성하고, 근거가 불충분하면 **거부**한다. LLM 호출을 추적한다 |
| **FR** | FR-14~22, FR-34, FR-35, FR-41, FR-42, FR-44 — **14건** |
| **NFR 검증** | NFR-1, 2, 5, 6, 7, 16, 19, 20, 21, 22 |
| **컴포넌트** | C30~C43 — **14종** |
| **서비스** | S3 `QueryService`, S8 `ObservabilityService` |
| **CONSTRUCTION 스테이지** | Functional Design ✅ / NFR Requirements ⏭ / **NFR Design ✅**(프롬프트 인젝션 방어) / Infrastructure Design ⏭ / Code Generation ✅ / Build & Test ✅ |
| **시연 산출물** | "황산 취급 시 보호구는?" 질문에 문장별 인용이 붙은 답변. 인용 클릭 시 원문 스니펫 하이라이트. 근거 없는 질문은 거부 + 원문 링크. LLM 사용량·비용 화면 |
| **예상 기간** | 3~4주 |

**⭐ 이 유닛 완료 시점이 "단독 완결된 포트폴리오"의 최소 목표입니다.**

**주요 위험**: R-4(리랭커 지연 vs NFR-1·2), R-6(안전 정보 오답)

---

### u4 — `u4-evaluation`

| 항목 | 내용 |
|---|---|
| **책임** | 골든 QA 셋으로 검색·답변 품질을 수치화하고, 기준선 대비 회귀를 감지한다 |
| **FR** | FR-36~39 — **4건** |
| **NFR 검증** | NFR-5·NFR-6의 **측정 수단 제공**, NFR-26 |
| **컴포넌트** | C44~C48 — **5종** |
| **서비스** | S5 `EvaluationService` |
| **CONSTRUCTION 스테이지** | Functional Design ✅ / NFR Requirements ⏭ / NFR Design ⏭ / Infrastructure Design ⏭ / Code Generation ✅ / Build & Test ✅ |
| **시연 산출물** | `evaluate` CLI 실행 → Recall@k / MRR / 정답률 / **인용 정확도** / 거부 정확도 / 충실도 리포트. 이전 실행 대비 변화표. 회귀 시 비0 종료코드 |
| **예상 기간** | 2주 |

**⭐ 채용 관점에서 가장 차별화되는 산출물입니다. 권장 목표 지점.**

**주요 위험**: R-5(골든셋 정답 근거 구축 수작업)

**설계 요점**: S5가 S3를 그대로 호출하므로 (DD-22) 평가 경로와 실사용 경로가 동일합니다.
`RetrievalConfig`를 인자로 받아 **리랭커 on/off·K 변경에 따른 품질 비교 실험**이 가능합니다.

---

### u3 — `u3-substance-card`

| 항목 | 내용 |
|---|---|
| **책임** | 물질명·CAS·UN 번호로 구조화된 안전 카드를 조회한다. **LLM을 사용하지 않는다** |
| **FR** | FR-23~26, FR-45 — **5건** |
| **NFR 검증** | NFR-3, NFR-8 |
| **컴포넌트** | C49, C50 — **2종** |
| **서비스** | S4 `SubstanceService` |
| **CONSTRUCTION 스테이지** | Functional Design ✅ / NFR Requirements ⏭ / NFR Design ⏭ / Infrastructure Design ⏭ / Code Generation ✅ / Build & Test ✅ |
| **시연 산출물** | CAS 번호 입력 → GHS 분류·신호어·H/P 문구·보호구·응급조치·저장취급·적용법령 카드. 항목별 출처 표기. 결측 항목은 "정보 없음" |
| **예상 기간** | 1~2주 |

**설계 요점**: u1의 `substance_synonym` 선반영 덕분에 이 유닛에서 재수집이 발생하지 않습니다.

---

### u5 — `u5-account-upload`

| 항목 | 내용 |
|---|---|
| **책임** | 계정 인증과 사용자 문서 업로드를 제공하고, 업로드 문서를 **소유자에게만** 노출한다 |
| **FR** | FR-27~33, FR-46, FR-47 — **9건** |
| **NFR 검증** | NFR-11, 12, 13, 15 |
| **컴포넌트** | C51~C55 — **5종** |
| **서비스** | S6 `AccountService`, S7 `DocumentService` |
| **CONSTRUCTION 스테이지** | Functional Design ✅ / NFR Requirements ⏭ / **NFR Design ✅**(인증·업로드 통제) / Infrastructure Design ⏭ / Code Generation ✅ / Build & Test ✅ |
| **시연 산출물** | 로그인 → 자사 MSDS PDF 업로드 → 처리 진행률 확인 → 본인 계정에서만 검색됨을 확인. 질의 이력 열람 |
| **예상 기간** | 2주 |

**설계 요점**: u1의 `chunk.owner_id` 선반영과 u2의 `scope` 필수 인자(DD-19) 덕분에,
이 유닛은 **스키마 변경이나 검색 시그니처 변경 없이** 격리를 도입합니다.

---

## 4. 유닛 완료 정의 (DoD) — UD-7

모든 유닛에 동일하게 적용합니다.

| # | 항목 | 검증 방법 |
|---|---|---|
| 1 | 해당 유닛의 FR 전건 구현 | 추적성 표에서 미구현 0건 |
| 2 | 단위 테스트 통과 | `pytest` 전건 통과, **네트워크 비의존** (NFR-28) |
| 3 | 통합 테스트 통과 | 해당 유닛의 종단 경로 검증 (LLM은 스텁 대체 가능) |
| 4 | **Docker 기동 실측** | `docker compose up` 후 해당 유닛 기능이 컨테이너에서 동작함을 확인 |
| 5 | **README 갱신** | 사용법 + 실행 결과 + 이 유닛에서 내린 설계 결정 기록 (UD-9) |
| 6 | Quality Gate 통과 | `execution-plan.md` §6 의 QG-1~QG-8 중 해당 항목 |
| 7 | u4 이후: 평가 회귀 없음 | 골든셋 지표가 기준선 이상 (u4 완료 후 적용) |

**항목 4·5가 방향 (a)의 핵심입니다.** 이것이 없으면 "어디서 멈춰도 동작하는 결과물"이
성립하지 않습니다.

---

## 5. 유닛 요약표

| 유닛 | 순서 | FR | 컴포넌트 | 서비스 | 기간 | 누적 |
|---|---|---|---|---|---|---|
| `u1-ingestion-index` | 1 | 16 | 32 | S1, S2 | 3~4주 | 3~4주 |
| `u2-rag-qa` ⭐ | 2 | 14 | 14 | S3, S8 | 3~4주 | **6~8주** |
| `u4-evaluation` ⭐ | 3 | 4 | 5 | S5 | 2주 | **8~10주** |
| `u3-substance-card` | 4 | 5 | 2 | S4 | 1~2주 | 9~12주 |
| `u5-account-upload` | 5 | 9 | 5 | S6, S7 | 2주 | **11~14주** |
| 공유 (C56, C57) | 전 유닛 | — | 2 | — | — | — |
| **합계** | | **48** | **60** | **8** | | |

---

## 6. 검증 결과

| 항목 | 결과 |
|---|---|
| FR 48건 유닛 배정 | **48건 배정, 누락 0건, 중복 0건** ✅ |
| 컴포넌트 60종 배정 | **60종 배정** ✅ (u1:32 / u2:14 / u4:5 / u3:2 / u5:5 / 공유:2) |
| 서비스 8종 배정 | **8종 배정** ✅ |
| NFR 32건 검증 시점 지정 | **32건 지정** ✅ (`unit-of-work-story-map.md` §3) |
| 유닛 간 역방향 의존 | **0건** ✅ (`unit-of-work-dependency.md` §2) |
| 각 유닛의 단독 시연 가능성 | **5개 유닛 전부 시연 산출물 정의** ✅ |

### ⚠️ FR-48 의 유닛 간 확장에 대한 고지

**FR-48(운영 화면)** 만이 여러 유닛에 걸쳐 확장됩니다.

- **u1** — 화면 골격 + 수집·색인 작업 상태 탭 (**소유 유닛**)
- **u2** — LLM 사용량·비용 탭 추가 (FR-42가 담당하므로 FR-48의 중복 배정이 아님)
- **u4** — 평가 결과 탭 추가 (FR-39가 담당하므로 FR-48의 중복 배정이 아님)

FR-48 자체는 **u1에만 배정**되며, u2·u4는 각자의 FR(42, 39)로 자신의 탭을 추가합니다.
따라서 중복 배정은 없습니다.
