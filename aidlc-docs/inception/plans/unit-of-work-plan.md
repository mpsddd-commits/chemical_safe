# Unit of Work Plan — safeenv

**프로젝트**: safeenv — 화학 안전·규제 근거 기반 질의응답(RAG) 시스템
**단계**: INCEPTION / Units Generation — **Part 1 (Planning)**
**작성일**: 2026-08-20
**상태**: Part 1 완료 (답변 확정) + Part 2 완료 (산출물 3종 생성)

---

## 답변 방법

**2부 분해 질문(UQ-1 ~ DQ-12)** 의 `[Answer]:` 태그 뒤에 선택지 문자를 적어 주세요.
*(권장)* 표시는 요구사항·설계·방향 (a)에 비추어 유리한 선택지입니다.

**"권장안대로 진행"** 이라고 하시면 *(권장)* 선택지로 채운 뒤 유닛 산출물 3종을 생성합니다.

---

# 1부. 분해 실행 계획 (체크리스트)

### 1. 컨텍스트 로드
- [x] 1.1 `requirements.md` — FR 48 / NFR 32
- [x] 1.2 `execution-plan.md` — 유닛 5개 제안 및 실행 순서
- [x] 1.3 `application-design/` 5종 — 컴포넌트 60, 서비스 8, DD-1~DD-25

### 2. 유닛 경계 확정
- [x] 2.1 유닛 목록 및 명칭 확정
- [x] 2.2 유닛별 FR·NFR 배정 (중복·누락 검증)
- [x] 2.3 유닛별 컴포넌트·서비스 배정
- [x] 2.4 유닛별 완료 정의(Definition of Done) 확정
- [x] 2.5 유닛별 시연 가능 산출물 정의 (방향 (a)의 전제)

### 3. 의존 관계 확정
- [x] 3.1 유닛 간 의존 매트릭스 작성
- [x] 3.2 역방향 의존 0건 검증
- [x] 3.3 선행 유닛에 선반영할 확장 지점 목록화 (DD-21)
- [x] 3.4 유닛 실행 순서와 의존 순서의 정합성 검증

### 4. 코드 조직 전략 (Greenfield)
- [x] 4.1 배포 모델 확정 (단일 배포 단위 vs 서비스 분리)
- [x] 4.2 디렉터리 구조 확정
- [x] 4.3 유닛과 디렉터리의 매핑 규칙 확정
- [x] 4.4 DB 마이그레이션 전략 확정

### 5. 산출물 생성
- [x] 5.1 `inception/application-design/unit-of-work.md` — 유닛 정의·책임·DoD·코드 조직 전략
- [x] 5.2 `inception/application-design/unit-of-work-dependency.md` — 의존 매트릭스
- [x] 5.3 `inception/application-design/unit-of-work-story-map.md` — FR·NFR ↔ 유닛 매핑

### 6. 검증
- [x] 6.1 FR 48건 전건이 정확히 하나의 유닛에 배정되었는지 확인
- [x] 6.2 NFR 32건의 검증 시점(유닛) 지정
- [x] 6.3 컴포넌트 60종 전건 배정 확인
- [x] 6.4 각 유닛이 단독으로 시연 가능한지 확인

---

# 2부. 분해 질문

## 유닛 그룹핑

### UQ-1
Application Design에서 제안된 **유닛 5개 분해**를 그대로 확정합니까?

> u1 수집·색인 / u2 질의응답 / u4 평가 / u3 물질카드 / u5 계정·업로드

A) 그대로 확정 *(권장 — 각 유닛이 단독 시연 가능하고 의존이 단방향)*

B) 더 잘게 분해 — u1을 `수집`과 `문서처리·색인` 두 유닛으로 분리 (u1이 컴포넌트 32종으로 가장 큼)

C) 더 크게 병합 — 3유닛으로 (`기반+색인` / `질의응답+평가` / `카드+계정·업로드`)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### UQ-2
**유닛 실행 순서**를 확정합니까?

> u1 → u2 → u4(평가) → u3(카드) → u5(계정·업로드)

A) 그대로 확정 *(권장 — 평가 하네스를 조기 확보하여 이후 변경의 품질 회귀를 즉시 감지)*

B) 2순위 기능인 u3(물질 카드)를 u4보다 앞으로 (u1 → u2 → u3 → u4 → u5)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## 배포 모델 및 코드 조직

### UQ-3
**배포 모델**은?

A) **단일 배포 단위(모놀리스) + 논리 모듈** — 웹 프로세스와 워커 프로세스가 같은 이미지를 공유하고
   실행 명령만 다름 *(권장 — CON-4 로컬 실행, DD-14 직접 호출과 정합)*

B) 유닛별 독립 서비스 — 각각 별도 이미지·배포

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### UQ-4
**디렉터리 구조**는?

A) 단일 저장소 + 단일 `app/` 패키지. DD-1의 모듈 구조를 그대로 사용하고,
   **유닛은 개발 순서 개념일 뿐 디렉터리 경계가 아님** *(권장)*

B) 유닛별 최상위 디렉터리 — `u1_ingestion/`, `u2_qa/` …

C) `src/` 레이아웃 + 단일 패키지

X) Other (please describe after [Answer]: tag below)

[Answer]: A

**참고 — A 선택 시의 구조**
```
safeenv/
  app/
    core/  db/  ports/  adapters/  jobs/
    ingestion/  processing/  indexing/          <- u1
    retrieval/  generation/  observability/     <- u2
    evaluation/                                 <- u4
    substances/                                 <- u3
    accounts/  documents/                       <- u5
    web/                                        <- 유닛별로 화면 추가
  config/  prompts/  eval/  migrations/  tests/
  Dockerfile  docker-compose.yml  pyproject.toml
```

### UQ-5
**유닛 간 통합 방식**은?

A) 직접 import — 계층 규칙(L4→L3→L2→L1→L0)만 준수하면 모듈 간 자유 참조 *(권장 — UQ-3=A와 정합)*

B) 유닛 간 명시적 인터페이스 계약 모듈을 두고 그것만 참조

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### UQ-6
**DB 마이그레이션 전략**은? (DD-21 확장 지점 선반영과 연관)

A) u1에서 전 유닛의 스키마를 한 번에 생성 — 재색인 위험 완전 회피, 초기 부담 큼

B) 유닛별 Alembic 리비전을 추가하되, **재색인을 유발하는 요소만 u1에 선반영**
   (`chunk.owner_id`, `substance_synonym` 테이블) *(권장 — DD-21)*

C) 유닛별로 완전히 독립적인 리비전

X) Other (please describe after [Answer]: tag below)

[Answer]: B

## 완료 정의 및 진행 방식

### UQ-7
**유닛의 완료 정의(DoD)** 는?

A) 코드 + 단위 테스트 통과

B) 코드 + 단위 테스트 + 통합 테스트

C) 코드 + 단위 + 통합 + **Docker 기동 실측** + README 갱신
   *(권장 — "어디서 멈춰도 동작하는 결과물"이라는 방향 (a)의 목표를 만족)*

X) Other (please describe after [Answer]: tag below)

[Answer]: C

### UQ-8
**유닛 개발 진행 방식**은?

A) 순차 진행 — 1인 개발 *(권장)*

B) 일부 유닛 병렬 진행

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### UQ-9
각 유닛 완료 시 **포트폴리오 산출물**을 남길까요?

A) 유닛 완료 시 README에 해당 기능의 사용법·실행 결과·핵심 설계 결정을 기록
   *(권장 — 나중에 몰아 쓰면 세부 근거가 소실됨)*

B) 최종 완료 시 한 번에 정리

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## 요구사항 정합성 확인

### UQ-10
**⚠️ 요구사항 간 긴장 1건을 확인해 주세요.**

`OOS-4`는 **CI/CD 파이프라인 구축을 범위 외**로 두었으나, `NFR-26`은 평가셋 회귀를
**"CI에서 자동 탐지"** 한다고 기술되어 있습니다. 어느 쪽으로 해석할까요?

A) **로컬 스크립트**로 평가 회귀를 실행 (CI 파이프라인 미구축) — OOS-4 준수.
   `CliEntrypoint.evaluate()` 가 회귀 시 비0 종료코드를 반환하는 것까지만 구현 *(권장)*

B) **GitHub Actions 워크플로까지 구축** — OOS-4의 범위를 명시적으로 확대.
   포트폴리오에 CI 배지와 자동 품질 리포트가 남음

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### UQ-11
User Stories 단계가 SKIP되었으므로 `unit-of-work-story-map.md` 의 매핑 대상이 없습니다.
무엇으로 대체할까요?

A) **FR·NFR ↔ 유닛 매핑표**로 대체 — 스토리 대신 요구사항 ID를 추적 단위로 사용 *(권장)*

B) 이 시점에 User Stories 단계를 실행하여 스토리를 생성

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## 자유 기술

### UQ-12
유닛 분해와 관련하여 추가로 반영할 사항이 있습니까?

A) 없음

B) 있음 (아래 [Answer]: 뒤에 기술)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

**답변 완료 후 채팅에 "완료" 또는 "권장안대로 진행" 이라고 알려 주세요.**
답변의 모호성·모순을 검증한 뒤 Part 2 (Generation)에서 유닛 산출물 3종을 생성합니다.
