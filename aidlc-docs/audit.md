# AI-DLC Audit Log — safeenv 프로젝트

이 파일은 safeenv 프로젝트(워크스페이스 루트: `c:\Users\403\IDE\safeenv`)의 모든 사용자 입력과 AI 응답을 기록합니다.
**중요**: 이 파일은 항상 추가(append)만 하며, 절대 전체를 덮어쓰지 않습니다.

---

## Initial User Request
**Timestamp**: 2026-08-20T01:28:02Z
**User Input**: "화학 안전·규제 LLM 관련한 프로젝트를 AI-DLC를 이용해서 진행하고싶습니다. safeenv폴더를 만들고 그 안에 프로젝트 설계서부터 만들고 진행해주세요"
**AI Response**: "AI-DLC 워크플로 시작. 환영 메시지 표시 → Workspace Detection 실행."
**Context**: INCEPTION PHASE 진입 / 신규 요청 접수

**선행 대화 맥락 (요구사항 배경으로 보존)**:
사용자는 화학공학과 졸업 후 IT 업계 백엔드 / AI 엔지니어 직군 취업을 목표로 하며, 전공 배경을 활용한
포트폴리오 프로젝트로 "화학 안전·규제 LLM" 도메인을 선택함. 직전 대화에서 제안된 후보 도메인 중
MSDS·화학 법령·화학사고 사례를 근거로 답변하는 RAG 기반 시스템을 채택.

---

## Workspace Detection
**Timestamp**: 2026-08-20T01:28:02Z
**User Input**: "(N/A — 자동 실행 단계, 사용자 입력 없음)"
**AI Response**: "워크스페이스 스캔 완료. 상세 findings는 아래 Context 참조."
**Context**: INCEPTION - Workspace Detection

**Findings**:
- 상위 워크스페이스 `c:\Users\403\IDE`에는 이미 복수의 독립 AI-DLC 프로젝트가 존재함
  (`260731_AI-DLC_news/news/aidlc-docs/`, `purchase_agent/aidlc-docs/`, `trip/aidlc-docs/`).
  상위 디렉터리 자체에는 `aidlc-docs/`가 없어 점유 충돌은 없음.
- 사용자 요청은 "safeenv폴더를 만들고 그 안에" 이므로, 본 요청은 기존 프로젝트의 연속(resume)이 아닌
  **독립된 신규 프로젝트**로 판단.
- 따라서 워크스페이스 루트를 `c:\Users\403\IDE\safeenv`로, 문서 루트를 `safeenv/aidlc-docs/`로 설정.
- `safeenv/` 폴더 신규 생성 — 소스 코드 파일 0건, 빌드 파일 0건 → **Greenfield**.
- Reverse Engineering 단계: 불필요 (SKIP).
- 이 워크스페이스 루트 결정은 Requirements Analysis의 Question 1에서 사용자가 확인/재정의 가능.

**Rule Details 로딩 완료**: `.aidlc-rule-details/` v1.0.1
(common/process-overview, session-continuity, content-validation, question-format-guide, depth-levels, welcome-message,
 inception/workspace-detection, inception/requirements-analysis)

**Extensions 스캔 완료** (opt-in 파일만 로딩, 전체 룰은 opt-in 후 지연 로딩):
- `extensions/security/baseline/security-baseline.opt-in.md`
- `extensions/resiliency/baseline/resiliency-baseline.opt-in.md`
- `extensions/testing/property-based/property-based-testing.opt-in.md`

---

## Requirements Analysis — Questions Presented
**Timestamp**: 2026-08-20T01:28:02Z
**User Input**: "(대기 중)"
**AI Response**: "`safeenv/aidlc-docs/inception/requirements/requirement-verification-questions.md` 생성 (30문항). 사용자 답변 대기 (GATE)."
**Context**: INCEPTION - Requirements Analysis / Step 6 GATE

**Intent Analysis**:
- **Request Clarity**: Vague — 도메인("화학 안전·규제 LLM")은 명확하나 기능 범위·데이터 소스·기술 스택 미정
- **Request Type**: New Project (Greenfield)
- **Initial Scope Estimate**: System-wide (수집 파이프라인 + 인덱싱 + 검색/생성 + API + UI)
- **Initial Complexity Estimate**: Complex (RAG 품질·근거 추적·안전 도메인 신뢰성 요구)
- **Requirements Depth**: **Comprehensive** — 안전 도메인 특성상 오답의 위험도가 높고, 포트폴리오 목적상
  설계 근거의 추적성이 중요하므로 상세 요구사항 + 수용 기준 필요

---

## Requirements Analysis — Answers Received (사용자 위임)
**Timestamp**: 2026-08-20T01:40:00Z
**User Input**: "권장안대로 진행"
**AI Response**: "사용자 위임에 따라 AI가 각 질문의 (권장) 선택지로 30문항 답변을 기입함. (권장) 표시가 없던 8문항은 AI 판단으로 결정하고 근거를 requirements.md §10에 명시함."
**Context**: INCEPTION - Requirements Analysis / Step 6 GATE 통과 (사용자 위임 방식)

**기입된 답변 (전 30문항)**:
Q1: A / Q2: C / Q3: D / Q4: A / Q5: B(물질 안전 카드를 2순위 포함) / Q6: C / Q7: D / Q8: B / Q9: A / Q10: A
Q11: D / Q12: C / Q13: A / Q14: C / Q15: C / Q16: A / Q17: C / Q18: C / Q19: A / Q20: A
Q21: A / Q22: B / Q23: B / Q24: A / Q25: B / Q26: C / Q27: A / Q28: B / Q29: B / Q30: A

**(권장) 표시가 없어 AI가 판단한 8문항**: Q4=A, Q5=B, Q10=A, Q19=A, Q21=A, Q22=B, Q23=B, Q30=A
→ 판단 근거는 `inception/requirements/requirements.md` §10 표에 문항별로 기록. 승인 시 사용자 확인 대상.

**Extension 결정 확정**:
- Security Baseline: **Yes** (Q27=A) → `extensions/security/baseline/security-baseline.md` 로딩 대상
- Resiliency Baseline: **No** (Q28=B) → 미로딩
- Property-Based Testing: **Partial** (Q29=B) → `extensions/testing/property-based/property-based-testing.md` 로딩 대상 (순수 함수·직렬화 왕복 한정)

**모순·모호성 검증 결과**: 논리적 모순 **0건**. 다만 아래 1건을 위험으로 기록.
- **R-7 범위 총량**: 권장안 조합의 결과로 FR 48건 / NFR 32건 규모가 되어 개인 프로젝트 기준
  3~4개월 분량. 모순은 아니나 완주 위험이 있어 requirements.md §9 에 명시하고, 승인 시
  (a) 단계적 진행 / (b) 범위 축소 / (c) 현행 유지 중 방향 확인을 요청함.

---

## Requirements Analysis — Document Generated
**Timestamp**: 2026-08-20T01:40:00Z
**User Input**: "(N/A)"
**AI Response**: "`inception/requirements/requirements.md` 생성. FR 48 / NFR 32 / CON 8 / OOS 10 / SC 8 / R 7. 질문 30건 전건 매핑, 미매핑 0건. 사용자 승인 대기."
**Context**: INCEPTION - Requirements Analysis / Step 9 승인 게이트

---

## Requirements Analysis — Approval
**Timestamp**: 2026-08-20T01:52:00Z
**AI Prompt**: "요구사항을 승인하고 Workflow Planning 으로 진행할까요? 진행 방향 (a)/(b)/(c) 를 함께 알려 주세요."
**User Response**: "a"
**Status**: **Approved** — 진행 방향 **(a) 단계적 진행** 선택
**Context**: INCEPTION - Requirements Analysis 승인 완료. AI 판단 8문항(Q4/Q5/Q10/Q19/Q21/Q22/Q23/Q30) 이의 없음.
User Stories 추가 요청 없음 → SKIP 확정.

---

## Workflow Planning
**Timestamp**: 2026-08-20T01:52:00Z
**User Input**: "(N/A — 계획 수립 단계)"
**AI Response**: "`inception/plans/execution-plan.md` 생성. 실행 8 / SKIP 3 / 완료 3. CONSTRUCTION 유닛 5개 제안. 사용자 승인 대기."
**Context**: INCEPTION - Workflow Planning / Step 9 승인 게이트

**스테이지 결정**:
- Reverse Engineering — SKIP (Greenfield)
- User Stories — SKIP (단일 페르소나, FR 48건이 이미 수용 기준 수준)
- Application Design — EXECUTE (신규 컴포넌트 다수, 추상화 인터페이스 확정 필요)
- Units Generation — EXECUTE (방향 (a)의 실행 수단, R-7 완화 장치)
- Functional Design — EXECUTE (전 5개 유닛, 비즈니스 규칙 무거움)
- NFR Requirements — SKIP (NFR 32건·스택 12계층 확정 완료, 라이브러리는 Application Design DD로 흡수)
- NFR Design — EXECUTE (u2 프롬프트 인젝션 방어, u5 인증·업로드 통제) / SKIP (u1, u3, u4)
- Infrastructure Design — EXECUTE (u1 전체 토폴로지) / SKIP (u2~u5 인프라 변경 없음)
- Code Generation — EXECUTE (전 5개 유닛)
- Build and Test — EXECUTE (**방향 (a) 적용 조정**: 유닛별 증분 실행 + 최종 통합 1회)

**유닛 분해 제안 (Units Generation에서 확정)**:
u1-ingestion-index (FR-1~13, 40, 43, 48부분) -> u2-rag-qa (FR-14~22, 34, 35, 41, 42, 44)
-> u4-evaluation (FR-36~39, 48부분) -> u3-substance-card (FR-23~26, 45) -> u5-account-upload (FR-27~33, 46, 47)

**u4를 u3보다 먼저 배치한 근거**: 평가 하네스를 u2 직후 확보하면 이후 모든 변경의 품질 회귀를
수치로 즉시 감지 가능. 하네스가 늦으면 저하 시점 추적 불가.

---

## Workflow Planning — Approval
**Timestamp**: 2026-08-20T02:05:00Z
**AI Prompt**: "실행 계획을 승인하고 Application Design 으로 진행할까요?"
**User Response**: "승인 및 계속"
**Status**: **Approved**
**Context**: INCEPTION - Workflow Planning 승인 완료. 실행 8 / SKIP 3 / 완료 3, 유닛 5개 분해 확정.
SKIP 스테이지 추가 요청 없음.

---

## Application Design — Plan and Questions Presented
**Timestamp**: 2026-08-20T02:05:00Z
**User Input**: "(대기 중)"
**AI Response**: "`inception/plans/application-design-plan.md` 생성 — 설계 실행 체크리스트 7단계 + 설계 질문 DQ-1~DQ-19. 사용자 답변 대기 (GATE)."
**Context**: INCEPTION - Application Design / Step 6 GATE

**설계 질문 범주**: 컴포넌트 식별(DQ-1~4), 검색·생성 컴포넌트(DQ-5~11),
서비스 계층·의존 관계(DQ-12~16), 프레젠테이션·운영(DQ-17~18), 자유 기술(DQ-19)

---

## Application Design — Answers Received (사용자 위임)
**Timestamp**: 2026-08-20T02:20:00Z
**User Input**: "권장안대로 진행"
**AI Response**: "설계 질문 DQ-1~DQ-19 를 (권장) 선택지로 기입하고 설계 산출물 5종 생성."
**Context**: INCEPTION - Application Design / Step 7 GATE 통과 (사용자 위임)

**기입된 답변**:
DQ-1: B / DQ-2: A / DQ-3: A / DQ-4: A / DQ-5: B / DQ-6: B / DQ-7: A / DQ-8: A / DQ-9: B / DQ-10: A
DQ-11: A / DQ-12: A / DQ-13: A / DQ-14: A / DQ-15: A / DQ-16: A / DQ-17: A / DQ-18: A / DQ-19: A

**모호성·모순 검증 결과**: 모순 0건. 다만 아래 1건을 사용자 확인 대상으로 표기.
- **DD-1 패키지 구성**: DQ-1=B(기능 기준) 답변이나, 공용 설정·로깅·DB 세션·포트 정의는 도메인 귀속이
  불가하여 `core/`,`db/`,`ports/`,`adapters/` 공용 기반 계층을 병존시킴 → 실질적으로 DQ-1의 C에 근접.
  `application-design.md` §5 에 명시하고 승인 시 확인 요청.

---

## Application Design — Artifacts Generated
**Timestamp**: 2026-08-20T02:20:00Z
**User Input**: "(N/A)"
**AI Response**: "`inception/application-design/` 에 산출물 5종 생성. 컴포넌트 60종 / 서비스 8종 / 포트 4종 / 설계결정 DD-1~DD-25. 사용자 승인 대기."
**Context**: INCEPTION - Application Design / Step 12 승인 게이트

**검증 결과**: FR 48건 미매핑 0건 / 계층 역방향 의존 0건 / L2 상호참조 0건 /
서비스 순환호출 0건 / 유닛 역방향 의존 0건 / Security Baseline 차단성 findings 0건 /
Functional Design 이월 17건 목록화

---

## Application Design — Approval
**Timestamp**: 2026-08-20T02:35:00Z
**AI Prompt**: "설계를 승인하고 Units Generation 으로 진행할까요? DD-1 패키지 구성 확인 요망."
**User Response**: "승인"
**Status**: **Approved** — DD-1 포함 전체 설계 승인. 변경 요청 없음.
**Context**: INCEPTION - Application Design 승인 완료. 컴포넌트 60 / 서비스 8 / DD-1~DD-25 확정.

**부수 수정**: `application-design.md` §7 의 다음 스테이지 산출물 경로를 `inception/units/` 에서
`inception/application-design/` 로 정정 (units-generation.md 규칙 §2 기준).

---

## Units Generation Part 1 — Plan and Questions Presented
**Timestamp**: 2026-08-20T02:35:00Z
**User Input**: "(대기 중)"
**AI Response**: "`inception/plans/unit-of-work-plan.md` 생성 — 분해 실행 체크리스트 6단계 + 분해 질문 UQ-1~UQ-12. 사용자 답변 대기 (GATE)."
**Context**: INCEPTION - Units Generation / Part 1 Step 6 GATE

**질문 범주**: 유닛 그룹핑(UQ-1~2), 배포 모델·코드 조직(UQ-3~6),
완료 정의·진행 방식(UQ-7~9), 요구사항 정합성(UQ-10~11), 자유 기술(UQ-12)

**⚠️ UQ-10 — 요구사항 간 긴장 발견**: OOS-4(CI/CD 파이프라인 범위 외)와
NFR-26("CI에서 자동 탐지")이 상충. 사용자 판단 요청.

---

## Units Generation Part 1 — Answers Received (사용자 위임)
**Timestamp**: 2026-08-20T02:50:00Z
**User Input**: "권장안대로 진행"
**AI Response**: "UQ-1~UQ-12 를 (권장) 선택지로 기입하고 Part 2 Generation 실행."
**Context**: INCEPTION - Units Generation / Part 1 Step 9 GATE 통과 (사용자 위임)

**기입된 답변**:
UQ-1: A / UQ-2: A / UQ-3: A / UQ-4: A / UQ-5: A / UQ-6: B
UQ-7: C / UQ-8: A / UQ-9: A / UQ-10: A / UQ-11: A / UQ-12: A

**모호성·모순 검증 결과**: 모순 0건.

---

## Units Generation Part 2 — Artifacts Generated
**Timestamp**: 2026-08-20T02:50:00Z
**User Input**: "(N/A)"
**AI Response**: "`inception/application-design/` 에 유닛 산출물 3종 생성. 유닛 5개 확정, 분해결정 UD-1~UD-12."
**Context**: INCEPTION - Units Generation / Part 2 Step 16 승인 게이트

**산출물**:
- `unit-of-work.md` — 유닛 5개 정의, 코드 조직 전략, DoD 7항목, 분해결정 UD-1~UD-12
- `unit-of-work-dependency.md` — 의존 매트릭스, 선반영 확장 지점 5건, 중단 가능 지점
- `unit-of-work-story-map.md` — FR 48 / NFR 32 / SC 8 / R 7 ↔ 유닛 매핑 (User Stories 대체)

**검증**: FR 48건 배정(누락 0, 중복 0) / 컴포넌트 60종 배정 / 서비스 8종 배정 /
NFR 32건 검증 시점 지정 / 유닛 역방향 의존 0건 / 5개 유닛 전부 시연 산출물 정의

**⚠️ requirements.md 정정 1건 반영 (UD-10)**:
- NFR-26: "CI에서 자동 탐지" -> "`CliEntrypoint.evaluate()` 가 비0 종료코드 반환"
- OOS-4: CI 워크플로 미구축 방침 명시
사유: OOS-4(CI/CD 범위 외)와 NFR-26(CI 자동 탐지)의 상충 해소. UQ-10=A 사용자 위임 결정.

---

## Units Generation — Approval
**Timestamp**: 2026-08-20T03:05:00Z
**AI Prompt**: "유닛을 승인하고 CONSTRUCTION PHASE (u1 Functional Design) 으로 진행할까요?"
**User Response**: "승인 및 계속"
**Status**: **Approved** — 유닛 5개, 실행 순서, 코드 조직 전략, DoD 전부 승인.
**Context**: **INCEPTION PHASE 완료.** CONSTRUCTION PHASE 진입.

---

## Functional Design (u1-ingestion-index) — Plan and Questions Presented
**Timestamp**: 2026-08-20T03:05:00Z
**User Input**: "(대기 중)"
**AI Response**: "`construction/plans/u1-ingestion-index-functional-design-plan.md` 생성 — 설계 체크리스트 7단계 + 설계 질문 FQ-1~FQ-18. 사용자 답변 대기 (GATE)."
**Context**: CONSTRUCTION - Functional Design / u1 / Step 5 GATE

**이 단계에서 확정할 이월 항목** (components.md §15 의 1~6번):
DB 스키마 상세 / 청킹 규칙 / MSDS 16섹션 매핑·실패처리 / 법령 조·항·호 분해 /
필수 메타데이터·누락처리 / 재시도 파라미터·오류분류

**질문 범주**: 청킹·문서구조(FQ-1~5), 데이터 모델(FQ-6~8), 수집 동작(FQ-9~14),
색인·운영(FQ-15~17), 자유기술(FQ-18)

---

## Functional Design (u1) — Answers Received (사용자 위임)
**Timestamp**: 2026-08-20T03:20:00Z
**User Input**: "권장안대로 진행"
**AI Response**: "FQ-1~FQ-18 을 (권장) 선택지로 기입하고 산출물 4종 생성."
**Context**: CONSTRUCTION - Functional Design / u1 / Step 5 GATE 통과 (사용자 위임)

**기입된 답변**: FQ-1~FQ-18 전부 **A** (전 문항의 권장 선택지가 A 였음)

**모호성·모순 검증 결과**: 모순 0건.

---

## Functional Design (u1) — Artifacts Generated
**Timestamp**: 2026-08-20T03:20:00Z
**User Input**: "(N/A)"
**AI Response**: "`construction/u1-ingestion-index/functional-design/` 에 산출물 4종 생성. 엔터티 12 / Enum 11 / 비즈니스 규칙 BR-01~BR-62 / 워크플로 6종. 사용자 승인 대기."
**Context**: CONSTRUCTION - Functional Design / u1 / Step 7 승인 게이트

**확정된 이월 항목** (components.md §15 의 1~6번 — 전건 해소):
1. DB 스키마 상세 -> `domain-entities.md` 엔터티 12종, Enum 11종, 인덱스 8종
2. 청킹 규칙 -> BR-26~31 (섹션=청크 기본, 최대 1000토큰, 중첩 0, 최소 20토큰 병합)
3. MSDS 16섹션 매핑·실패처리 -> BR-15~20 (인식 8개 미만이면 unstructured + 문단 폴백)
4. 법령 조·항·호 분해 -> BR-21~23 (조 단위 청크, 항·호는 내부 보존, 부칙·별표 별도)
5. 필수 메타데이터·누락처리 -> BR-32, 33, 39 (source_url·doc_type 없으면 색인 거부)
6. 재시도 파라미터·오류분류 -> BR-40~45 (3회 / 1s·4s·16s / transient·permanent·policy_blocked)

**검증**: u1 FR 16건 전건 BR 매핑(미표현 0건) / NFR 9건 반영 확인 /
u2~u5 선반영 요소 7건 확인 / 파라미터 14종 설정 외부화

---

## Functional Design (u1) — Approval
**Timestamp**: 2026-08-20T03:35:00Z
**AI Prompt**: "설계를 승인하고 Infrastructure Design (u1) 으로 진행할까요?"
**User Response**: "승인 및 계속"
**Status**: **Approved** — 엔터티 12종, BR-01~BR-62, 워크플로 6종 전부 승인.
**Context**: CONSTRUCTION - Functional Design (u1) 승인 완료. 이월 항목 1~6번 해소.

---

## NFR Requirements (u1) — SKIPPED
**Timestamp**: 2026-08-20T03:35:00Z
**AI Response**: "실행 계획대로 SKIP."
**Context**: CONSTRUCTION - NFR Requirements / u1
**사유**: NFR 32건과 기술 스택 12계층이 Requirements Analysis 에서 확정 완료되었고,
잔여 라이브러리 선정은 Application Design 의 설계 결정(DD-1~DD-25)으로 흡수됨.
(`execution-plan.md` §4 CONSTRUCTION PHASE 참조)

---

## NFR Design (u1) — SKIPPED
**Timestamp**: 2026-08-20T03:35:00Z
**AI Response**: "실행 계획대로 SKIP."
**Context**: CONSTRUCTION - NFR Design / u1
**사유**: u1 은 u2(프롬프트 인젝션 방어)·u5(인증·업로드 통제)에서 확립될 보안 패턴을 상속만 하며
고유한 NFR 설계 결정이 없음. Security Baseline 관련 u1 항목(NFR-14, 17, 18, 30)은
Functional Design(BR-59, BR-60, BR-32, BR-33) 및 Infrastructure Design 에서 처리.
(`execution-plan.md` §4 CONSTRUCTION PHASE 참조)

---

## Infrastructure Design (u1) — Plan and Questions Presented
**Timestamp**: 2026-08-20T03:35:00Z
**User Input**: "(대기 중)"
**AI Response**: "`construction/plans/u1-ingestion-index-infrastructure-design-plan.md` 생성 — 실행 체크리스트 9단계 + 인프라 질문 IQ-1~IQ-17. 사용자 답변 대기 (GATE)."
**Context**: CONSTRUCTION - Infrastructure Design / u1 / Step 5 GATE

**이 단계에서 해소할 미결 항목 2건**:
- NFR-18 루프백 바인딩 (application-design.md §6 에서 이월)
- u1 시점 `/admin` 무인증 노출 대응 (frontend-components.md §9)

**질문 범주**: 컴퓨트(IQ-1~4), 스토리지(IQ-5~9), 메시징(IQ-10~11),
네트워킹(IQ-12~13), 관측(IQ-14~15), 공유 인프라(IQ-16), 자유기술(IQ-17)

---

## Infrastructure Design (u1) — Answers Received (사용자 위임)
**Timestamp**: 2026-08-20T03:50:00Z
**User Input**: "권장안대로 진행"
**AI Response**: "IQ-1~IQ-17 을 (권장) 선택지로 기입하고 산출물 2종 생성."
**Context**: CONSTRUCTION - Infrastructure Design / u1 / Step 5 GATE 통과 (사용자 위임)

**기입된 답변**:
IQ-1: A / IQ-2: A / IQ-3: B / IQ-4: A / IQ-5: A / IQ-6: A / IQ-7: A / IQ-8: A / IQ-9: B
IQ-10: B / IQ-11: A / IQ-12: A / IQ-13: A / IQ-14: A / IQ-15: A / IQ-16: A / IQ-17: A

**모호성·모순 검증 결과**: 모순 0건.

---

## Infrastructure Design (u1) — Artifacts Generated
**Timestamp**: 2026-08-20T03:50:00Z
**User Input**: "(N/A)"
**AI Response**: "`construction/u1-ingestion-index/infrastructure-design/` 에 산출물 2종 생성. 컨테이너 5종, 볼륨 4종, 환경변수 23종, 인프라결정 ID-1~ID-17. 사용자 승인 대기."
**Context**: CONSTRUCTION - Infrastructure Design / u1 / Step 7 승인 게이트

**해소된 미결 항목 2건**:
- **NFR-18 루프백 바인딩 확정** — `app` 만 `127.0.0.1:8200` 노출, postgres·redis 는 호스트 노출 없음.
  컨테이너 내부는 `APP_HOST=0.0.0.0`, 외부 차단은 Compose 포트 매핑의 `127.0.0.1:` 접두사로 달성.
- **u1 `/admin` 무인증 노출** — 루프백 바인딩만으로 통제하고 README·화면에 경고 표시.
  u5 인증 도입 시 인증 필수 경로로 전환. **u5 완료까지 열린 위험으로 유지.**

**shared-infrastructure.md 미생성** — 인프라 6축(프로젝트명/네트워크/포트/볼륨/이미지/컨테이너명)
전부 news·petmate 등과 분리 확인.

**미검증 9건 / 배포 검증 절차 14건**을 Build & Test 로 이월
(이미지 크기, 바인드 마운트 권한, 모델 다운로드, 워커 메모리, postgres 성능, 동시 기동,
루프백 전용 확인, 기동 순서, 볼륨 보존).

**⚠️ u2 재검토 이월 1건**: 리랭커를 `app` 에서 로드 시 메모리 2G 부족 가능성.

---

## Infrastructure Design (u1) — Approval
**Timestamp**: 2026-08-20T04:05:00Z
**AI Prompt**: "인프라 설계를 승인하고 Code Generation (u1) 으로 진행할까요?"
**User Response**: "승인 및 계속"
**Status**: **Approved** — 컨테이너 5종, 볼륨 4종, 환경변수 23종, ID-1~ID-17 전부 승인.
**Context**: CONSTRUCTION - Infrastructure Design (u1) 승인 완료. NFR-18 확정.

---

## Code Generation Part 1 (u1) — Plan Presented
**Timestamp**: 2026-08-20T04:05:00Z
**User Input**: "(대기 중)"
**AI Response**: "`construction/plans/u1-ingestion-index-code-generation-plan.md` 생성 — Step 1~18, 예상 100개 파일. 계획 승인 대기 (GATE)."
**Context**: CONSTRUCTION - Code Generation / u1 / Part 1 Step 7 승인 게이트

**계획 요약**:
- Step 1 프로젝트 구조·빌드 설정 / Step 2 core / Step 3 db 모델 / Step 4 리포지터리
- Step 5 마이그레이션 / Step 6 포트 / Step 7 소스 어댑터 4종 / Step 8 모델 어댑터·추적
- Step 9 작업 큐 / Step 10 수집 / Step 11 문서처리 파이프라인 / Step 12 색인
- Step 13 서비스 / Step 14 웹 / Step 15 진입점 / Step 16 테스트 / Step 17 배포 / Step 18 문서

**코드 위치**: `c:\Users\403\IDE\safeenv\` (워크스페이스 루트). `aidlc-docs/` 에는 마크다운 문서만.

**알려진 제약 5건을 Build & Test 로 이월** (공공 API 스펙, MSDS 레이아웃, 임베딩 성능,
테스트 실행, Docker 실측).

---

## Code Generation Part 1 (u1) — Approval
**Timestamp**: 2026-08-20T04:20:00Z
**AI Prompt**: "코드 생성 계획을 승인하고 Part 2 (Generation) 를 실행할까요?"
**User Response**: "승인 및 계속"
**Status**: **Approved** — Step 1~18 전체 계획 승인.
**Context**: CONSTRUCTION - Code Generation / u1 / Part 1 완료

---

## Code Generation Part 2 (u1) — Generation Complete
**Timestamp**: 2026-08-20T04:20:00Z
**User Input**: "(N/A)"
**AI Response**: "Step 1~18 전건 실행 완료. 애플리케이션 코드 103개 파일 생성. 사용자 승인 대기."
**Context**: CONSTRUCTION - Code Generation / u1 / Step 14 승인 게이트

**생성 위치**: `c:\Users\403\IDE\safeenv\` (워크스페이스 루트).
문서는 `aidlc-docs/construction/u1-ingestion-index/code/` 3종.

**집계**: Python 47 / 마이그레이션 4 / 템플릿 6 / 정적 2 / 테스트·픽스처 18 /
설정 3 / 배포 4 / 빌드·메타 4 / README 1 = **약 103개**

**설계 대비 조정 7건** (code-summary.md §3):
1. 리포지터리 8종을 4개 모듈로 묶음 (순환 import 회피)
2. `processing/tokens.py` 추가 (BR-27/31 토큰 계수 지점이 설계에 없었음)
3. `DeterministicEmbeddingAdapter` 추가 (NFR-28 오프라인 테스트 + 최초 기동)
4. `IdentityReranker` 추가 (R-4 리랭커 off 스위치)
5. `worker_heartbeat` 테이블 추가 (BR-52 요구, 엔터티 12 -> 13)
6. 테스트 모듈 10 -> 11 (`test_orchestrator.py` 추가)
7. `config/msds_manifest.json` 추가 (BR-04 크롤링 회피)

**⚠️ 문서 갱신 필요 2건** (code-summary.md §5):
- `domain-entities.md` 에 `worker_heartbeat` 반영
- `business-rules.md` §13 파라미터 목록을 실제 환경변수 23종과 대조

**미검증 10건을 Build & Test 로 이월**: 테스트 실행 / Docker 빌드·기동 / 마이그레이션 적용 /
공공 API 응답 / MSDS 파싱 성공률 / 임베딩 모델 / 바인드 마운트 권한 / 루프백 바인딩 /
동시 기동 / 워커 스케일

**추적성**: FR 16건 미구현 0건, BR 62건 전건 구현 위치 존재
(단위 테스트 검증 48건 / Build & Test 이월 14건)

---

## Code Generation Part 2 (u1) — Approval
**Timestamp**: 2026-08-20T04:35:00Z
**AI Prompt**: "코드를 승인하고 Build & Test (u1) 으로 진행할까요?"
**User Response**: "승인 및 계속"
**Status**: **Approved** — 조정 7건 포함 전체 승인.
**Context**: CONSTRUCTION - Code Generation (u1) 승인 완료.

---

## Build and Test Stage (u1)
**Timestamp**: 2026-08-20T10:10:00Z
**Build Status**: **Success**
**Test Status**: **Pass** — 163 passed, 0 failed
**Context**: CONSTRUCTION - Build and Test / u1 / Step 9 승인 게이트

**Files Generated** (`construction/build-and-test/`):
- build-instructions.md
- unit-test-instructions.md
- integration-test-instructions.md
- performance-test-instructions.md
- security-test-instructions.md
- build-and-test-summary.md

**실측 환경**: Python 3.14.6 / Docker 29.7.2 / Windows 10 Pro

**주요 실측 결과**:
- 단위 테스트 163 passed (최초 152 + 회귀 11 추가), ruff All checks passed
- Docker 이미지 **743MB** (초기 5.81GB -> CPU torch 전환으로 87% 감소)
- 컨테이너 5종 기동, migrate 선행 확인, `/healthz` 4항목 전부 ok
- 마이그레이션 적용: 테이블 14개(13+alembic), 인덱스 17개
- 파이프라인 종단: 실제 BGE-M3 로 MSDS 16청크 / 법령 7청크 색인, dim=1024
- **BR-30 오프셋 무결성 위반 0행** (u2 인용의 전제)
- BR-26 섹션=청크 실측 일치 (msds 16/16, law 7/7)
- 법령 섹션: 제1조, 제2조, 제12조, 제12조의2, 제13조, 부칙, 별표1
- **NFR-18 실측 확정**: LAN IP(192.168.0.2:8300) 접속 거부, DB·큐 호스트 미노출
- NFR-30 비루트 uid=10001, NFR-31 볼륨 영속화 확인
- 워커 메모리 1.52GiB/4GiB (38%)

**발견·수정된 결함 7건 + 부수 4건**:
1. 🔴 청킹이 섹션 경계를 넘어 병합 (16섹션 -> 14청크) — 인용 정확도. BR-31 정정
2. 🔴 `Authorization: Bearer <token>` 미마스킹 — 보안
3. 🔴 `extra` 최상위 비밀 필드 미마스킹 — 보안
4. 🟠 이미지 5.81GB (CUDA torch) -> 743MB
5. 🟠 워커 크래시 루프 (`cron_jobs` staticmethod) — BR-52 하트비트가 탐지
6. 🟠 작업 전체가 단일 트랜잭션 — DD-24/BR-53 위반, FR-6·FR-8 무력화
7. 🟡 재개 시 `original_path` 유실 — 재개 경로가 재개 근거를 파괴
부수: `ref_key` 과잉 마스킹, `input_tokens` 과잉 마스킹, Hypothesis 픽스처, ruff B008

**⚠️ CON-2 정정**: 호스트 포트 8200 -> **8300**.
`trip-app` 이 이미 8200 점유 중이었음 (ID-16 6축 조사가 trip 프로젝트 누락).
나머지 5축 충돌 없음 실측 확인.

**⚠️ 설계 예상 대비 차이**:
- 모델 볼륨 실측 **4.3GB** (예상 2GB) — 디스크 요구 재산정 필요
- `app` 메모리 임베딩 로드 시 1.70GiB/2GiB (85%) — **u2 리랭커 배치 재검토 필요**

**미해소 3건** (전부 R-1/R-2 의존): 공공 API 응답 형식 / MSDS 파싱 성공률 / NFR-4·NFR-9 성능
**열린 위험 1건**: `/admin` 무인증 노출 (u5까지 유지, 루프백 바인딩으로 완화·실측 확인)

**문서 정정 반영**: requirements.md CON-2 / business-rules.md BR-31·BR-59 /
domain-entities.md E13(`worker_heartbeat`)

---

## Session Paused
**Timestamp**: 2026-08-20T10:40:00Z
**User Input**: "내일 하게 정리해줘"
**AI Response**: "u1 Build & Test 승인 게이트에서 세션 중단. 환경 정리 및 재개 지점 기록."
**Context**: CONSTRUCTION - Build and Test (u1) / 승인 대기 중 중단

**정리 내역**:
- Docker 스택 정지 (`docker compose down`). 볼륨 `safeenv_pgdata`·`safeenv_models` 보존
- 결함 7(재개 시 original_path 유실)로 손상된 검증 문서 2건 및 원본 파일 제거
- 검증 증적 1건(`fix-check:doc-a`, 16청크/16벡터)은 보존
- `job` 테이블 정리
- `aidlc-state.md` 최상단에 재개 지점 배너 추가

**재개 시 첫 결정**: u1 Build & Test 승인 여부.
승인 시 다음은 `u2-rag-qa` Functional Design (2/5).

**진행 차단 요인 (사용자 조치 필요)**:
- 공공 API 인증키 3종 미보유 (R-1) — 실제 수집 및 NFR-4·NFR-9 측정 불가
- 공개 MSDS PDF 샘플 미확보 (R-2) — 파싱 성공률 측정 불가

---
## CONSTRUCTION — Defect Fix (u1) : 화학사고 소스 인증 불가
**Timestamp**: 2026-08-22T00:00:00Z
**User Input**: "2. INCIDENT_API_KEY — 화학사고 사례 이건 api키 활용이 안됩니다 해결 조치 해주세요"
**AI Response**: "설정된 엔드포인트가 실존하지 않아 인증키가 발급되어도 사용할 수 없었음. 실제 서비스 계약 확인 후 정정."
**Context**: CONSTRUCTION - Build and Test (u1) / 승인 게이트 대기 중 결함 수정

### 근본 원인
`config/sources.yaml` 의 `incident_data` 가 가리키던
`https://apis.data.go.kr/1480523/ChemicalAccidentService` 는 **공개된 서비스가 아니다.**
위험 R-1(인증키 미보유로 실계약 검증 불가)이 예측한 그대로, 가정으로 작성한 주소가 틀렸다.
공공데이터포털에 `fileData` 로 등록된 화학사고 정보(15069200)는 CSV 배포라 인증키가 아예 없고,
오픈API 는 별도 데이터셋 **15072446 (화학물질안전원_화학사고정보)** 로 1480802 네임스페이스에 있다.

### 조치 (결함 8~12)
| # | 심각도 | 결함 | 조치 |
|---|---|---|---|
| 8 | 🔴 | 존재하지 않는 엔드포인트 — 어떤 인증키로도 수집 불가 | `base_url` → `https://apis.data.go.kr/1480802/iciscsc`, `list_path` → `/csclist`, 실제 필드(`dataNo`/`cscDe`/`cscTy`/`area`/`place`/`chem`/`cause`/`summary`)로 `field_map` 교체 |
| 9 | 🔴 | **사고개요 전면 소실** — 실제 API 필드명을 그대로 내보내 구조화기가 인식하지 못했고, 섹션 밖 텍스트는 청킹되지 않음(BR-26). 구버전 로직 실측 **169자 중 76자만 색인, `summary` 0% 반영** | 어댑터 `_project()` 로 물리→논리 필드명 변환. 구조화기에 `incident_summary`/`incident_type`/`incident_area` 추가 (BR-25 개정) |
| 10 | 🔴 | 인증 파라미터명을 `serviceKey` 로 하드코딩 — 3개 소스 중 2개가 불일치(화학사고=`ServiceKey`, 국가법령정보=`OC`) | `sources.yaml` 에 소스별 `auth_param` 도입, `_auth_params()` 가 설정을 읽음 |
| 11 | 🟠 | 인증 실패가 HTTP 200 + 오류 본문으로 오는데 "no item list in response" 로만 보고 → 원인 진단 불가 | `raise_for_service_error()` 추가. 코드 20/30/31/32 → `ApiKeyMissingError`(permanent, 변수명 명시), 22 → `SourceUnavailableError`(transient, BR-41) |
| 12 | 🟠 | 응답 봉투 미대응 — `_dig` 가 2단계만 탐색해 표준 `response>body>items>item` 을 놓침. 또한 이 서비스는 포맷 파라미터가 없어 XML 응답 가능성이 큰데 XML 을 하드 실패 처리 | `_dig` 재귀화, `_rows` 가 `items.item` 언랩, `get_json` 에 XML→dict 폴백 추가 |

부가: 사고사례 섹션이 **줄 단위**로 끊겨 여러 줄 값(사고개요)이 첫 줄에서 잘리던 문제를
"다음 라벨 시작 지점까지"로 변경. 섹션 사이 공백이 사라져 텍스트 누락 경로가 닫힘.

### 검증
- 신규 테스트 `tests/unit/test_source_adapters.py` **35건** 추가 → 전체 **198건 통과**, ruff clean
- 구버전 로직 재현으로 결함 9 실증: `summary` 미색인 확인
- 실제 API 필드 1건 파이프라인 통과 → 7청크, BR-30 오프셋 무결성 유지

### 남은 사용자 조치
- `INCIDENT_API_KEY` = 공공데이터포털 인증키 (15072446 활용신청). `NCIS_API_KEY` 와 **동일 값**
- `LAW_API_KEY` = open.law.go.kr 의 **OC 값(가입 이메일 ID 부분)**, 발급키 아님

### 후속 결정 필요 (u1 승인 게이트에 포함)
사고사례 1건이 필드당 1청크(7청크, 각 4~15토큰)로 색인된다. 검색 단위로는 지나치게 작아
u2 리트리버 품질에 영향. "사고 1건 = 청크 1개" 로 바꿀지 BR-26 예외로 결정 필요.

---
## CONSTRUCTION — Live Contract Verification (u1)
**Timestamp**: 2026-08-24T02:00:00Z
**User Input**: "진행해주세요" (실제 수집 실행 승인)
**AI Response**: "인증키 3종 확보 후 실 API 호출로 위험 R-1 해소. 결함 13~18 발견 및 수정."
**Context**: CONSTRUCTION - Build and Test (u1) / 승인 게이트 대기 중, 실계약 검증

### 배경
사용자가 인증키 3종을 `.env` 에 설정 완료. 위험 R-1(인증키 미보유로 실제 API 계약 검증 불가)을
처음으로 해소할 수 있게 되어 3개 소스를 실제 호출했다. **가정으로 작성한 계약은 대부분 틀렸다.**

### 소스별 결과
| 소스 | 결과 |
|---|---|
| `incident_data` | ✅ 정상. `resultCode=00`, 총 **1,143건**. 12건 수집 성공(실패 0) |
| `law_api` | ✅ OC 인증 정상. 화학물질관리법 조문 **92개** 확인 |
| `ncis_substance` | ❌ **엔드포인트 폐기/부재** (`NO_OPENAPI_SERVICE_ERROR`, 코드 12) |
| `msds_pdf` | ✅ 매니페스트 8건 등록, 파싱 8/8 성공 |

### 조치 (결함 13~18)
| # | 심각도 | 결함 | 조치 |
|---|---|---|---|
| 13 | 🔴 | **법령 전체가 조문 0개·단일 청크.** 화학물질관리법 95,632자가 하나의 청크로 색인됨. `_flatten` 이 모든 줄에 `법령: ` 접두어를 붙여 `^제N조` 앵커가 무효화됨. 조 단위 인용(BR-21)이 통째로 소실 | `app/processing/law_json.py` 신설. API 가 이미 제공하는 `조문단위[]`(조문내용/항내용/호내용)를 그대로 렌더링. **0개 → 97섹션 / 102청크** (제7조의2 등 가지번호 포함) |
| 14 | 🔴 | 법령 상세 조회 404. 소문자 `id` 를 보냈으나 `lawService.do` 는 대문자 `ID` + `target` 요구 | `detail_id_param`, `detail_params` 설정 도입 |
| 15 | 🟠 | 법령 목록 파싱 실패. 응답이 `LawSearch.law` 인데 `item/items/row` 만 탐색 | `rows_key` 설정 도입 (관례 키는 폴백으로 유지) |
| 16 | 🟠 | 사고사례 `published_at` 이 항상 NULL → 수집 워터마크 미동작, 매 실행이 전량 재수집 (FR-7, BR-13) | `published_at: cscDe` 매핑 추가 |
| 17 | 🟠 | `제N항` 교차참조 오염. `「폐기물관리법」 제25조제5항` 때문에 제3조가 없는 제5항을 보유한다고 기록 (NFR-8 위반, u2 가 존재하지 않는 조항을 인용할 수 있음) | 조 번호로 한정된 항(`제N조제M항`)은 제외. **같은 조 내 자기참조(`제1항`)는 유지** — 기존 테스트가 이를 요구 |
| 18 | 🟡 | `pageNo` 를 무시하는 소스에서 `list_targets` 무한 루프 가능. `since` 가 전 행을 거르면 `seen` 도 증가하지 않아 종료 조건 없음 | 이미 반환한 식별자만 담긴 페이지를 만나면 경고 로그 후 종료 |

부가 발견: 명세에 없는 `addr`(상세주소) 필드가 실제 응답에 포함됨 → 매핑 추가.
`_project()` 가 미매핑 필드를 보존하도록 설계한 것이 유효했음이 확인됨.

### 실측 검증 (Docker 실환경)
- 화학사고 **12문서 / 84청크 / 7섹션 전건**, `incident_summary` 에 실제 사고 서술 확인
- **BR-30 오프셋 무결성 위반 0건** (실데이터)
- 수집 워터마크 기록 확인 (`last_collected_at`)
- 원본 보존 확인 (`original_path IS NOT NULL`)
- 벡터 100건 (신규 84 + 기존 16)

### 운영 주의
`/data/originals` 는 `app` 에 **읽기 전용**, `worker` 에 읽기·쓰기로 마운트되어 있다(설계대로).
`app` 컨테이너에서 수집을 직접 실행하면 원본이 조용히 보존되지 않고(`original_not_stored` 경고만)
해당 문서는 재색인 불가 상태가 된다(BR-44). **수집은 반드시 워커에서 실행할 것.**

### 남은 차단 요인
`NCIS_API_KEY` 로 사용할 **물질 정보 API 엔드포인트 미확정.** 인증키 자체는 유효하나
데이터셋별 활용신청이 필요하며, 어느 데이터셋을 신청했는지 확인 후 `sources.yaml` 정정 필요.

---
## CONSTRUCTION — Live Contract Verification, 2차 (u1)
**Timestamp**: 2026-08-24T03:00:00Z
**User Input**: "신청 완료 했습니다" (물질정보 데이터셋 활용신청 완료)
**AI Response**: "물질 API 정상 확인. 처리·성능 결함 3건(19~21) 발견 및 수정."
**Context**: CONSTRUCTION - Build and Test (u1) / 승인 게이트 대기 중

### 물질 API 확인
`15072442 화학물질안전관리정보` 활용신청 승인 후 정상 응답. `resultCode=00`, **총 7,189종**.
증상·흡입·피부·눈·경구 영향을 제공. 엔드포인트는 신청 전 코드 30("등록되지 않은 서비스키")으로
**존재가 미리 확인**되어 있었고(없는 서비스는 코드 12), 승인만으로 코드 변경 없이 동작했다.

### 조치 (결함 19~21)
| # | 심각도 | 결함 | 조치 |
|---|---|---|---|
| 19 | 🔴 | **물질 레코드가 섹션 없는 단일 청크.** 16절 MSDS 구조화기에 걸려 아무것도 인식하지 못하고 542토큰 통짜 청크(`section_code=NULL`)가 됨. 노출 경로별 인용 불가 — u2 가 "흡입 시"와 "피부 접촉 시"를 구분해 답할 수 없음 | 구조화기를 필드 테이블 기반으로 공용화(`structure/record.py`) 후 `structure/substance.py` 추가. **0섹션 → 7섹션** (식별·증상·흡입·피부·눈·경구·기타). MSDS 16절 파싱 실패 시에만 폴백하며, 노출 경로가 하나도 없으면 unstructured 유지 |
| 20 | 🔴 | **문서 1건당 임베딩 모델 1회 재적재.** `IndexingService` 가 문서마다 생성되는데(DD-24) 그때마다 BGE-M3(2.3GB)를 디스크에서 재적재. 실측: MSDS 8문서 → 8회 적재, 워커 3.999/4 GiB, `OOMKilled=true`. BR-61/62 중복제거 캐시도 문서마다 폐기되어 **설계 의도대로 동작한 적이 없음** | `shared_adapter()` 로 프로세스당 1개 공유. **8회 → 1회**. 캐시가 프로세스 수명 동안 유지되므로 LRU 상한(`embedding_cache_size`, 기본 4096) 동시 도입 |
| 21 | 🟠 | **배치 32 가 컨테이너 메모리 한계 초과.** 결함 20 수정 후에도 첫 법령 처리 중 OOM 재발 | 격리 측정(32청크×1530자): batch 32 = peak **3.05 GiB**, batch 8 = **2.43 GiB**, 처리량 차이 3%. `EMBED_BATCH_SIZE` 기본 32→8. `.env` 도 갱신(기본값만 바꾸면 `.env` 가 덮어씀 — 테스트가 이를 먼저 검출) |

부가: `EMBED_MAX_SEQ_LENGTH=2048` 신설. 처리량에는 무관하나(8192/2048/1024 측정 결과 노이즈 범위),
BR-27 이 문단 경계에서만 분할하므로 문단 구분이 없는 긴 절은 분할되지 않는다 — 그 상한을 두기 위함.

### 기각한 가설 (측정으로 반증)
`max_seq_length` 기본값 8192 가 성능·메모리 원인이라고 판단했으나 **틀렸다.**
sentence-transformers 는 배치 내 최장 시퀀스에 맞춰 패딩하므로 8192 자체는 비용이 아니다.
`seq=8192/2048/1024` × `batch=32` 측정: 45.88s / 44.35s / 46.82s — 유의차 없음.

### 성능 실측 (NFR-4, NFR-9)
BGE-M3 CPU 추론 = **청크당 1.4~2.4초**. 모델 선택의 결과이며 결함이 아니다.
- 법령 9건 ≈ 918청크 ≈ 20~30분
- 물질 7,189종 ≈ 50,000청크 ≈ **20시간 이상**

u2 는 여기에 리랭커가 더해진다. 승인 게이트에서 다음 중 결정 필요:
(a) 더 작은 한국어 임베딩 모델, (b) GPU, (c) 초기 코퍼스 규모 축소(`INITIAL_SUBSTANCE_TARGET`).

### 실측 검증 (결함 13 수정 효과)
```
화학물질관리법 → structured, 102청크, BR-30 위반 0건
제1조(목적) 89t / 제2조(정의) 667t / 제3조(적용범위) 678t / ...
```
수정 전 동일 문서는 **95,632자 단일 청크, 조문 0개**였다.

### 검증 상태
테스트 **237건 통과**, ruff clean. 신규 테스트 파일 `tests/unit/test_live_contract_regressions.py`.

### 운영 주의 (추가)
`docker compose exec` 로 워커 컨테이너 안에 별도 파이썬 프로세스를 띄우면 임베딩 모델이
**두 번 적재**되어 메모리 한계에 도달한다. 수집은 반드시 큐(`start_and_enqueue`)로 넘길 것.

---
## CONSTRUCTION — Live Contract Verification, 3차 (u1) : 워커 구조 결함
**Timestamp**: 2026-08-24T04:00:00Z
**Context**: CONSTRUCTION - Build and Test (u1) / 실수집 중 발견

### 조치 (결함 22~23)
| # | 심각도 | 결함 | 조치 |
|---|---|---|---|
| 22 | 🔴 | **긴 작업 중 워커 liveness 상실.** 원인 2개가 겹쳐 있었다. ①`run_ingest` 가 `async def` 인데 동기 코드를 직접 호출해 arq 이벤트 루프를 작업 내내 점유 → Redis 연결 관리 불가 → `redis.exceptions.TimeoutError` 로 프로세스 사망. ②하트비트가 arq **크론 잡**이라 `max_jobs=1` 에 막혀 실행 중인 수집 작업 뒤에서 대기. 실측: 9건 법령 수집 37분간 하트비트 0회, 이후 133초까지 낡아 `/healthz` 가 정상 작동 중인 워커를 down 으로 보고 — **BR-52 가 막으려던 오판이 정확히 반대로 발생** | ①`asyncio.to_thread` 로 블로킹 작업 분리 ②크론 잡 제거하고 독립 asyncio 태스크로 전환. 기동 시 1회 즉시 비트하여 프로브가 바로 통과 |
| 23 | 🟠 | **워커가 통과 불가능한 헬스체크를 상속.** 이미지의 `HEALTHCHECK` 가 `http://127.0.0.1:8000/healthz` 를 호출하는데 그것은 웹 프로세스만 제공하고 워커는 arq 를 실행 → 아무리 정상이어도 영구 `unhealthy` | `app/worker_probe.py` 신설, compose 에 워커 전용 헬스체크 지정. 하트비트 신선도로 판정 |

### 검증 (수정 전/후 실측 대비)
```
수정 전 (작업 중):  하트비트 73초 → 103초 → 134초 (임계 120초),  health=unhealthy
수정 후 (작업 중):  하트비트 3~27초 유지,                        health=healthy
```

### 최종 코퍼스 및 불변식 (실데이터)
```
law         9문서 / 1,140청크    화관법·화평법·산안법 (본법+시행령+시행규칙)
msds       49문서 /   435청크    공개 PDF 8 + 물질 40 + 검증문서 1
incident   12문서 /    84청크
─────────────────────────────────────────
합계       70문서 / 1,659청크 / 1,659벡터

BR-30 오프셋 위반      0
DD-23 벡터 없는 청크    0
BR-32 source_url 누락  0
BR-44 원본 미보존       0
unstructured 문서       0
/healthz  {"app":"ok","db":"ok","queue":"ok","worker":"ok"}
```

### BR-54 / BR-09 멱등성 (실데이터)
동일 소스 재수집(job 15) → **40건 전부 `skipped`**. 콘텐츠 해시 변경 감지 정상.

### 성능 실측 정정
임베딩 속도는 청크 크기에 크게 좌우된다.
- 물질 청크(50~140토큰): **258 ms/청크**
- 법령 청크(최대 1000토큰): **1,400~2,400 ms/청크**

앞서 기록한 "청크당 1.4~2.4초"는 법령 기준이며 전 코퍼스 평균이 아니다.
`INITIAL_SUBSTANCE_TARGET` 을 `.env`/`.env.example` 에 명시 노출했다(현재 40, 예시 기본 1000).

### 검증 상태
테스트 **247건 통과 + 1 스킵**(호스트에 `arq` 미설치, NFR-28 의도된 구성), ruff clean.

---
## CONSTRUCTION — Build and Test (u1) : **APPROVED**
**Timestamp**: 2026-08-24T05:00:00Z
**User Input**: "진행"
**AI Response**: "u1 승인. 미결 결정 3건은 권장안대로 반영 후 u2 착수."
**Context**: CONSTRUCTION - Build and Test (u1) 승인 게이트 → 통과

### 승인 근거
- 결함 **1~23** 전건 수정, 각각 회귀 테스트 보유
- 테스트 **258건 통과 + 1 스킵**(호스트에 `arq` 미설치, NFR-28 의도), ruff clean
- 4개 소스 전부 실제 API 수집 성공 (위험 R-1 해소), 공개 MSDS PDF 8건 파싱 (R-2 해소)
- 실데이터 불변식: BR-30 위반 0 / DD-23 벡터누락 0 / BR-32 URL누락 0 / BR-44 원본미보존 0

### 미결 결정 3건 — 권장안 반영
| # | 결정 | 반영 |
|---|---|---|
| 1 | 청킹 입도 | **BR-31a 신설.** 섹션 크기 중앙값이 `MIN_CHUNK_TOKENS` 미만이고 문서가 `MAX_CHUNK_TOKENS` 이내면 문서 전체를 청크 1개로 만들고 `section_code=NULL`. 사고사례 7청크 → **1청크**, 물질은 7청크 유지 |
| 2 | 2단 편집 MSDS PDF | **BR-20a 신설.** 섹션 번호가 오름차순이 아니면 `unstructured` 강등. 실측 8건 중 2건 강등, 문단 단위 색인은 유지되어 데이터 손실 없음 |
| 3 | 임베딩 성능 | 모델 교체·GPU 도입 없이 **`INITIAL_SUBSTANCE_TARGET` 로 코퍼스 규모를 명시 제어.** BGE-M3 유지 — 근거 인용 시스템에서 검색 품질이 처리 시간보다 중요하다는 판단. u2 착수 시 리랭커 배치와 함께 재검토 |

### 결정 1 설계 경과 (기록)
처음에는 조각 단위로 "미달 섹션끼리 병합, 라벨 포기"를 구현했으나 실데이터에서 실패했다.
`incident_area` 가 정확히 20토큰(= 최솟값)으로 단독 청크가 되어 병합 흐름이 끊기고 206자 레코드가
**4조각**으로 나뉘었다. 임계값에 걸친 한 필드가 문서 전체의 결과를 좌우하는 것은 잘못된 설계이므로,
조각 단위 규칙을 되돌리고(BR-31 의 교차 병합 금지 복원) **문서 단위 판단**으로 대체했다.
중앙값을 쓰는 이유가 이것이다.

### 다음 단계
**`u2-rag-qa` Functional Design (2/5)** 착수.

---
## CONSTRUCTION — u1 결정 반영 후 전체 재색인 검증
**Timestamp**: 2026-08-24T06:00:00Z
**Context**: u1 승인 후 BR-20a·BR-31a 를 실데이터에 반영

### 결과
```
재색인 job 16:  70/70 성공, 실패 0, 워커 재시작 0회, health 유지

incident   structured     12문서 /    12청크   (BR-31a: 기존 84청크 → 문서당 1청크)
law        structured      9문서 / 1,140청크
msds       structured     47문서 /   396청크
msds       unstructured    2문서 /    16청크   (BR-20a: 2단 편집 PDF 강등)
──────────────────────────────────────────
합계                      70문서 / 1,564청크 / 1,564벡터

BR-30 오프셋 위반 0 / DD-23 벡터없는 청크 0 / 고아 벡터 0
BR-32 URL 누락 0 / BR-44 원본 미보존 0
/healthz {"app":"ok","db":"ok","queue":"ok","worker":"ok"}
```

### 의의
- **결함 22 최종 검증**: 시스템에서 가장 긴 작업(70문서 재색인)을 워커 재시작 없이 완주.
  수정 전에는 법령 9건 작업에서도 Redis 타임아웃으로 프로세스가 사망했다.
- **BR-44 / FQ-8=A 검증**: 보존된 원본만으로 전 코퍼스를 재수집 없이 재구성. 파싱 규칙 변경
  (BR-20a·BR-31a)을 소스 재호출 없이 적용한 것이 이 설계의 목적이었고, 70문서 규모로 실증되었다.
- 청크 1,659 → 1,564 (사고사례 -72, MSDS 재분할 -23). 벡터가 정확히 동수이고 고아 0건이므로
  DD-23(청크·벡터 동일 트랜잭션)이 재색인 경로에서도 유지된다.

---
## CONSTRUCTION — Functional Design (u2-rag-qa)
**Timestamp**: 2026-08-24T07:00:00Z
**User Input**: "권장안대로 진행"
**AI Response**: "FQ2-1~20 권장안 확정 후 산출물 4종 생성."
**Context**: CONSTRUCTION - Functional Design / 유닛 `u2-rag-qa` (2/5)

### 답변 (FQ2-1 ~ FQ2-20)
`a a a b a a a a a a a a a a a a a a a a` — FQ2-4 만 (b), 나머지 전부 (a)

| # | 확정 사항 |
|---|---|
| FQ2-1 | RRF 융합, `k=60` |
| FQ2-2 | 각 30건 → 융합 20건 → 최종 5건 |
| FQ2-3 | 문서 유형별 최소 할당 (법령 편중 대응) |
| **FQ2-4** | **리랭커 기본 OFF + 별도 컨테이너 분리** — `app` 메모리 실측 85% |
| FQ2-5 | 질의 임베딩 LRU 캐시 |
| FQ2-6~7 | 최상위 스코어 임계값, 환경변수 + 운영 화면 조정 |
| FQ2-8~10 | LLM 판정 2단 검증, 미지지 문장만 제거, 전멸 시 거부 전환 |
| FQ2-11~13 | `{sentences:[{text, chunk_ids}]}` 구조화 출력, 근거 0건은 재시도 1회, 본문만 스트리밍 |
| FQ2-14 | Anthropic Claude API |
| FQ2-15~16 | `prompts/<name>/<semver>.md` + `index.yaml`, 추적에 버전 기록 |
| FQ2-17~18 | 청크 오프셋 구간 그대로, 라벨 없으면 "섹션 정보 없음" 명시 |
| FQ2-19~20 | 단가 미등록 시 비용 NULL, 질의 로그 보존기간 설정화 |

### 산출물
`construction/u2-rag-qa/functional-design/` — 4종
- `domain-entities.md` — 신규 엔터티 **E14~E18**, 값 객체 V1~V4, Enum 5종, 리비전 `0002_query`
- `business-logic-model.md` — 워크플로 **W7~W11**
- `business-rules.md` — **BR-63 ~ BR-96** (34건)
- `frontend-components.md` — 화면 P5·P6, 요소 FE-14~FE-23, SSE 이벤트 규격

### 설계 중 확인한 외부 제약 (claude-api 레퍼런스)
- 모델 `claude-opus-5` (1M 컨텍스트, $5/$25 per 1M tok)
- 구조화 출력은 `client.messages.parse(output_format=...)` → `parsed_output`
- **Anthropic 네이티브 citations 기능은 `output_config.format` 과 동시 사용 불가(400)** →
  네이티브 인용을 쓰지 않고 BR-30 오프셋을 사용하기로 확정(BR-83). 네이티브 인용은 우리가 넘긴
  문서 내 문자 위치만 주지만, BR-30 오프셋은 원본 `extracted_text` 기준이라 원문 링크까지 이어진다
- `stop_reason = "refusal"` 처리 필요 → `RefusalReason.provider_refusal` 신설(BR-77)
- 토큰 수는 응답 `usage` 사용. u1 의 청크 크기용 휴리스틱을 과금에 쓰지 않는다

### 설계 중 발견한 u1 과의 충돌
**BR-54(재색인 시 청크 전량 교체) ↔ 인용 보존.** 재색인하면 과거 답변이 인용한 청크가 사라진다.
CASCADE 면 인용이 조용히 소멸하고 SET NULL 이면 "근거 없는 문장"이 남는다 — 둘 다 정직하지 않다.
→ **E17 `citation_snapshot`** 으로 답변 확정 직후 인용을 동결(BR-92). u1 `ChunkRepo.replace_for_document`
에 동결 확인 단계 추가가 필요하며 Code Generation 에서 반영한다.

### 다음 단계
산출물 검토 → 승인 → **NFR Design** (프롬프트 인젝션 방어, NFR-16)

---
## CONSTRUCTION — 결함 24 : `MAX_CHUNK_TOKENS` 미강제 (u1 회귀)
**Timestamp**: 2026-08-25T05:00:00Z
**User Input**: "임베딩 청킹시 최대 토큰수를 1000 오버랩이 0인데 이유가 있을까요?"
**Context**: u2 FD 승인 대기 중 사용자 질의 → 실코퍼스 측정 → u1 결함 발견

### 질문에 대한 답 (값 자체는 타당)
`MAX_CHUNK_TOKENS=1000` · `CHUNK_OVERLAP=0` 은 FQ-1=A / FQ-2=A 로 확정된 값이며 근거가 있다.
청킹 단위는 토큰이 아니라 **섹션**(BR-26)이고, 1000 은 "모델 한계"가 아니라 **한국 법령 조문이
온전히 들어가는 크기**다(제2조 정의 667t, 제3조 678t). 512 였다면 정의 조항이 조문 중간에서
잘려 "제2조"라는 인용 단위가 깨진다.

오버랩 0 의 근거 3가지 중 결정적인 것은 **인용 정확도**다. 오버랩이 있으면 같은 문장이 두
청크에 존재해 **하나의 근거가 두 개의 독립 출처인 것처럼 인용**될 수 있다. 안전 도메인에서
이는 중복이 아니라 근거의 상호보강을 위조하는 것이다.

### 오버랩 재검토 → 불필요 (실측)
| doc_type | 섹션 총계 | 분할된 섹션 | 비율 | 절단면 청크 |
|---|---|---|---|---|
| law | 1,110 | 26 | 2.3% | 30 |
| msds | 379 | 5 | 1.3% | 16 |
| incident | — | 0 | 0% | 0 |

절단면 청크 46 / 전체 1,564 = **2.9%**. 나머지 97% 는 섹션 경계가 곧 청크 경계라 잃을 문맥이
없다. 인접 청크 확장(BR-72a 제안)은 **보류** — 2.9% 를 위해 u2 검색 경로를 복잡하게 만들 이유가 없다.

### 그러나 — 상한이 강제되지 않고 있었다 (결함 24)
```
1000 초과 27청크 / 최댓값 8,111토큰 (상한의 8배)
2048(EMBED_MAX_SEQ_LENGTH) 초과 7청크
```
BR-27 이 문단 경계를 `\n\n` 로만 정의했는데 이 코퍼스에 빈 줄이 없다.
- 법령 **부칙** — API 가 한 덩어리로 반환. 줄바꿈 **0개**, 마침표 154개
- **msds_11**(독성정보) — 단일 줄바꿈 81개 + `○` 불릿 26개가 있는데 빈 줄이 없어 미인식

**단순한 크기 초과가 아니다.** 7청크는 뒤쪽이 벡터에 반영되지 않은 채(8,111토큰 청크는 약 75%
누락) 저장되었고, BR-30 오프셋은 구간 전체를 가리킨다 → **검색으로 도달할 수 없는 텍스트를
인용 스니펫으로는 표시**하는 상태. u2 인용 신뢰성의 전제와 어긋난다. 조용히 실패한다는 점이 특히 나쁘다.

### 조치 — BR-27a 신설 + BR-31 보강
**BR-27a**: 경계 사다리 — 빈 줄 → 단일 줄바꿈 → 문장 경계 → (최후) 토큰 절단.
각 단계는 윗 단계로 상한을 못 지킬 때만 발동하므로 구조가 있는 문서는 영향 0.

**BR-31 보강**: 병합 결과가 상한을 넘으면 병합하지 않는다. 두 규칙 충돌 시 상한이 이긴다.

### ⚠️ 오진 기록 — 재색인 2회 낭비
1차 재색인 후 최댓값 8,111 → 1,018 로 떨어졌으나 **15청크가 1~18토큰 초과.** 초과폭이 전부
`MIN_CHUNK_TOKENS`(20) 미만이어서 BR-31 병합을 원인으로 지목하고 2차 재색인까지 돌렸으나
**결과가 15건 그대로**였다. 가정이 틀렸다.

실제 원인은 **분할 조각을 다시 묶을 때 "조각들의 토큰 수 합"으로 판정한 것.**
청크가 저장하는 `token_count` 는 `text[start:end]` 를 센 값이고, 이 구간에는 조각 사이의
**구분자**(공백·줄바꿈)가 포함되며 반올림도 한 번만 일어난다.
실측: 문장 39개 → 조각 합 **858** vs 실제 구간 **864** (6토큰 차이).
**판정은 항상 실제 구간을 센다.** BR-31 보강은 이번 원인은 아니었으나 동일한 잠재 경로이므로 유지.

**교훈**: 3차부터는 재색인 전에 **전 코퍼스 건식 시뮬레이션**으로 먼저 검증했다.
35분짜리 재색인을 가정 검증에 쓰지 않는다.

### 검증 (3차 재색인 = job 19)
```
70/70 성공, 실패 0

incident   structured     12문서 /    12청크   max   150
law        structured      9문서 / 1,173청크   max   999
msds       structured     47문서 /   396청크   max   998
msds       unstructured    2문서 /    17청크   max   947
────────────────────────────────────────────────────────
합계                      70문서 / 1,598청크 / 1,598벡터

상한 초과 0 / 최댓값 999 / EMBED_MAX_SEQ_LENGTH 초과 0
BR-30 위반 0 / 벡터 누락 0 / 고아 벡터 0 / BR-32 0 / BR-44 0
```
사전 시뮬레이션 예측(1,598청크 / 최댓값 999 / 초과 0)과 **정확히 일치**.

테스트 **266 통과 + 1 스킵**, ruff clean. 신규 `TestBoundaryLadder` 6건 + 속성 테스트 강화
(구분자가 많은 알파벳, 200 examples — 이 버그가 숨어 있던 자리).

---
## CONSTRUCTION — Functional Design (u2-rag-qa) : 검토 지적 3건 반영
**Timestamp**: 2026-08-25T06:00:00Z
**User Input**: "3건 다 반영해주세요"
**Context**: FD 산출물 검토 → 결함 1건 + 관찰 2건 반영

### 1. E16 `chunk_id` RESTRICT → **nullable + ON DELETE SET NULL** (결함)
RESTRICT 는 참조가 남은 청크의 DELETE 를 거부한다 → **한 번이라도 인용된 문서는 영구 재색인 불가.**
스냅샷을 떠도 FK 는 풀리지 않으므로 E17 만으로는 해소되지 않는다.

재색인은 이 시스템의 핵심 운영 경로다 — BR-44 가 존재하는 이유가 "소스 재호출 없이 파싱 규칙
변경을 적용"이고, BR-20a·BR-31a·**BR-27a** 가 전부 그 경로로 배포되었다. u2 가 그 능력을 없애서는 안 된다.

SET NULL 기각 근거("근거 없는 문장이 남는다")는 **E17 도입 이전의 판단**이었다. E17 은
`source_url`·`snippet` 이 NOT NULL 인 완전한 기록이므로 표시는 스냅샷이 담당한다.
→ **BR-92a 신설**: 인용 표시는 `citation_snapshot` 만 읽고 `chunk` 를 조인하지 않는다.
→ **u1 `ChunkRepo.replace_for_document` 변경 불필요**로 정정.

### 2. 인용 동결을 답변 확정 트랜잭션에 포함
W8-7 이 "동결 실패 시 답변은 반환하되 경고"였다. 그러면 스냅샷 없는 인용이 남고, 표시 경로가
E17 만 읽으므로(BR-92a) 화면에 아무것도 못 띄우며, 재색인이 지나가면 복구 불가.
→ E15+E16+E17 단일 트랜잭션. 실패 시 전부 롤백하고 `error`. **BR-92 보강.**

### 3. 2단 검증 비용 명시 — **BR-86a 신설**
질의당 호출 = `1 + 문장 수`. 답변 3~6문장이면 호출 4~7배. `E18.purpose` 분리 집계와
P6 용도별 분해가 이 비용을 감추지 못하게 하는 장치임을 규칙으로 고정.

### 부수 정정
`/api/chunks/{id}/snippet` → **`/api/citations/{id}/snippet`**. 청크 ID 는 재색인 시
재사용되므로 인용 카드가 **다른 문서 본문**을 보여줄 수 있었다.
u1 관계표에 **BR-44 행** 추가 — 재색인 능력을 u2 가 막아서는 안 된다는 것을 명문화.

---
## CONSTRUCTION — NFR Design (u2-rag-qa) : **APPROVED**
**Timestamp**: 2026-08-25T07:00:00Z
**User Input**: "승인. 다음 진행해주세요"
**Context**: CONSTRUCTION - NFR Design / 유닛 `u2-rag-qa` (2/5)

### 답변 (FQ3-1 ~ FQ3-16)
`A A B A A A A A A A A A B A A A` — **FQ3-3 · FQ3-13 만 (b)**, 나머지 (a)

| # | 확정 |
|---|---|
| FQ3-1~2 | system=지시 / user=근거, `<evidence id=…>` XML 구획 |
| **FQ3-3** | **이스케이프 + 요청별 nonce 구분자** |
| FQ3-4~5 | 색인 시점 탐지 → 플래그만, **제외하지 않음** |
| FQ3-6 | 검증자는 질문을 보지 않는다. enum 구조화 출력 |
| FQ3-7~8 | 질의문도 구획 격리, 2,000자 상한 |
| FQ3-9~11 | 지연 예산표, 리랭커 HTTP 1,200ms |
| FQ3-12 | 질의 임베딩 LRU 1,024 |
| **FQ3-13** | **2단 검증 동시성 상한 4** |
| FQ3-14~16 | 재시도 3종 분류, `llm_pricing.yaml`, 질의문 90일 보존 |

### 설계의 핵심 발견
새 패턴을 세기 전에 **FD 가 이미 확보한 방어를 셈했다.** BR-79(구조화 출력)·BR-81(ID
화이트리스트)·BR-92a(스냅샷 표시) 때문에 **출력 측 유출 경로가 구조적으로 없다** — 답변
스키마에 URL 이 들어갈 자리가 없고 링크는 서버가 붙인다. 전형적인 RAG 유출 시나리오가
성립하지 않는다. 인용 정확도 때문에 도입한 규칙이 결과적으로 가장 강한 인젝션 방어였다.

남은 빈틈 2개만 새로 설계: **구분자 위조**(SP-3), **검증자도 같은 오염 텍스트를 본다**(SP-6).

### 직관과 반대인 결정 — SP-5
탐지된 청크를 **근거에서 제외하지 않는다.** MSDS 본문은 정상적으로 지시문 투성이다
("즉시 다량의 물로 씻어내십시오"). 탐지를 제외로 연결하면 **정당한 안전 정보를 지우는 방어**가 된다.

### 산출물
`construction/u2-rag-qa/nfr-design/` — 2종
- `nfr-design-patterns.md` — 위협 모델, **SP-1~9 / PP-1~6 / CP-1~3**
- `logical-components.md` — 컨테이너 1, 컴포넌트 N1~N6, 환경변수 12

### 다음 단계
**Code Generation (u2)**

---
## CONSTRUCTION — Code Generation (u2) : 첫 실질의에서 발견된 결함 25~27
**Timestamp**: 2026-08-25T09:00:00Z
**Context**: u2 웹 계층 완성 후 Docker 실환경에서 첫 질의 실행

세 결함 모두 **단위 테스트와 컨테이너 기동 점검을 통과한 상태**였다. 실제 질문을
실제 코퍼스에 던져야만 드러났다. **u1 의 검색 경로는 한 번도 실행된 적이 없었다** —
u1 단위 테스트는 세션을 모킹했고 Build & Test 는 색인만 검증했다.

### 결함 25 — `to_tsvector` 인자 타입 (u1 잔존 결함, 심각)
```
function to_tsvector(character varying, text) does not exist
```
설정 인자는 `regconfig` 인데 `literal(FTS_CONFIG)` 가 VARCHAR 로 바인딩했다.
**키워드 검색이 처음부터 한 번도 동작한 적이 없다.** `literal(..., type_=REGCONFIG)` 로 수정.

### 결함 26 — BR-72(한쪽 검색 실패 허용)가 실현 불가능했다
두 검색이 Session 을 공유하므로, 한쪽이 SQL 오류를 내면 PostgreSQL 이
`InFailedSqlTransaction` 상태가 되어 **다른 쪽도 반드시 실패**한다.
실제 로그: 키워드가 결함 25 로 죽자 벡터가 "current transaction is aborted" 로 죽었다.
try/except 는 올바르게 보였지만 규칙은 성립하지 않았다.
→ 각 경로를 `begin_nested()` **세이브포인트**로 격리.

### 결함 27 — 거부 임계값이 잘못된 신호를 읽고 있었다 (설계 결함)
BR-73 의 1단 거부가 **융합 RRF 점수**를 임계했다. RRF 는 순위 통계라
**무관한 질의의 1위와 좋은 질의의 1위가 같은 점수**를 받는다. 보정으로 고칠 수 없다.

실측 (BGE-M3 코사인 유사도, 실코퍼스 1,598청크):
```
질의                          vec_top   vec_5th
황산 취급 시 보호구는?            0.6596    0.5707
화학물질 취급자의 교육 의무는?      0.7063    0.6314
오늘 점심 메뉴 추천해줘            0.4168    0.4132
asdfgh qwerty zxcvbn         0.4225    0.3846
```
코사인 유사도는 분리한다 — 적합 0.66~0.71 / 무관 ~0.42.
→ 순위는 RRF 유지, **거부 판정만 코사인 유사도**로 변경. 기본값 0.02 → **0.50**.
→ 키워드 전용 후보(유사도 없음)는 **0 으로 취급하지 않는다.** CAS 완전일치는 가장
   정밀한 신호이고(BR-38), 0 으로 보면 이 코퍼스가 가장 잘 답하는 질의를 거부한다.

### 부수 발견 — 한국어 키워드 검색이 자연어 문장에 무력했다
`plainto_tsquery` 는 AND 로 묶고 `simple` 은 형태소 분석을 하지 않는다. 결과적으로
"황산 취급 시 보호구는?" 은 `황산 & 취급 & 시 & 보호구는` 이 되어 색인의 "보호구" 와
영원히 매칭되지 않는다.
```
수정 전:  "황산 취급 시 보호구는?"  →  키워드 0건 (문장) / 5건 (단어 "보호구")
수정 후:  "황산 취급 시 보호구는?"  →  키워드 30건
          "오늘 점심 메뉴 추천해줘"   →  키워드 0건  ← 올바른 동작
```
→ OR 결합 + 조사 절단(`_tsquery_terms`). `ts_rank` 가 더 많이 매칭된 문서를 위로 올린다.
   하이브리드 검색이 사실상 벡터 전용으로 반쪽 동작 중이었고, 아무것도 실패를 보고하지 않았다.

### 실측 검증
```
질의 "황산 취급 시 보호구는?"
  retrieval 5건 / 콜드 14,897ms (모델 로드) → 웜 339ms  ← NFR-2 예산 2,500ms 대비 여유
  근거 1위: 황산 MSDS msds_08 (노출방지 및 개인보호구) — 정확
  → generation 단계에서 ANTHROPIC_API_KEY 미설정으로 중단 (BR-02 정상 동작)

질의 "오늘 점심 메뉴 추천해줘"
  → refused / below_threshold + 원문 링크 5건 (BR-75)
```

테스트 **377 통과 + 1 스킵**, ruff clean. 신규 회귀 `tests/unit/test_retrieval_regressions.py` 18건.

### 교훈
u1 Build & Test 는 "Docker 기동 + 색인 파이프라인 종단"을 검증했지만 **검색을 실행하지
않았다.** DoD(UD-7)의 "Docker 기동 실측"이 기동만을 뜻한다면 부족하다. u2 Build & Test
에서는 **실질의 종단**을 명시적 항목으로 둔다.

---
## CONSTRUCTION — LLM 제공자 전환: Anthropic → Google Gemini (무료 티어)
**Timestamp**: 2026-08-25T10:00:00Z
**User Input**: "ANTHROPIC_API_KEY 말고 무료 api키를 사용하고 싶습니다." → Gemini 선택 + 검증 계층 추가
**Context**: CONSTRUCTION - Code Generation (u2) / NFR-21 검증

### 선택 기준 — BR-79 를 지킬 수 있는가
무료 제공자 후보 중 **스키마 강제**가 판별 기준이었다. BR-79 는 편의 기능이 아니다:
문장 단위 인용(SC-2)과 결정론적 근거 검증(DD-8)의 전제이며, **가장 바깥쪽 인젝션
방어**다(SP §1.4 — 지시 탈취가 성공해도 스키마 밖으로 나갈 수 없다).
Gemini 는 `responseSchema` 로 이를 제공하고 스트리밍도 지원한다.

### NFR-21 이 값을 했다
`LLMPort` 는 u1 이 **구현 없이 먼저 정의**한 것이다(DD-6, DD-21). 전환에서
`rag/` 의 규칙·워크플로·테스트가 **한 줄도 바뀌지 않았다.** 추가된 것은 어댑터
1개와 팩토리 1개다.

### 산출물
- `app/adapters/llm_gemini.py` — `GeminiLLMAdapter` (동기·구조화·스트리밍)
- `app/adapters/llm_factory.py` — `LLM_PROVIDER` 로 어댑터 선택. 알 수 없는 값은
  **기본값으로 넘어가지 않고 실패한다** — 오타가 한국어 안전 텍스트 품질이 평가되지
  않은 모델을 조용히 쓰게 두면 R-6 이다
- `app/rag/schema_guard.py` — **제공자 독립 스키마 검증** + Gemini 방언 변환
- `config/llm_pricing.yaml` — 무료 티어 모델을 **0.00 으로 등록**
- 테스트 23건 (`test_schema_guard.py`)

### 제공자 차이를 규칙별로 어떻게 지켰나
| 규칙 | Anthropic | Gemini |
|---|---|---|
| BR-79 스키마 | `output_config.format` | `responseSchema` (+ `additionalProperties` 제거 변환) |
| BR-94 캐시 | 블록별 `cache_control` | 접두사 기반 암묵 캐시 — **레이아웃 자체가 메커니즘** |
| PP-4 적중 측정 | `cache_read_input_tokens` | `cached_content_token_count` |
| BR-77 거부 | `stop_reason="refusal"` | `finish_reason` ∈ {SAFETY, BLOCKLIST, …} → 같은 `ProviderRefusal` |
| FQ3-14 재시도 | SDK 예외 타입 | HTTP 상태 코드 |

### 검증 계층을 제공자와 무관하게 둔 이유
사용자 선택은 "스키마 강제를 못 하는 제공자면 검증·재시도 계층 추가"였으나,
**Gemini 가 강제를 지원함에도 계층을 그대로 넣었다.** 이유: 제공자가 강제하면 이 검증은
절대 발동하지 않고 비용이 0 이다. 그러나 넣지 않으면 **BR-79 의 보장이 그때그때 설정된
제공자의 것**이 된다. BR-79 는 제공자 기능이 아니라 이 시스템의 계약이다.

Gemini 가 `additionalProperties` 를 거부해 변환에서 제거하는데, **제공자가 더 이상
거부하지 않게 된 그 키가 정확히 우리가 직접 확인해야 하는 키**다. 이것만으로도
계층의 값이 증명된다.

### 무료 티어와 BR-96
무료 모델을 `0.00` 으로 **등록**했다. **0 을 적는 것과 항목을 비워 두는 것은 다르다** —
여기서 0 은 실제로 0 이고(NFR-20 의 로컬 임베딩과 같은 성격), 미등록은 "모른다"는
뜻이다. 유료 티어 전환 시 이 값만 바꾼다.

### 검증
```
컨테이너: google-genai import ok / adapter=GeminiLLMAdapter / model=gemini-2.5-flash
스키마 변환: additionalProperties 제거, propertyOrdering 생성 확인
BR-02: "GEMINI_API_KEY is not set..." — 앱은 기동, 질의만 비활성
```
테스트 **400 통과 + 1 스킵**, ruff clean.

### 남은 것
`.env` 에 `GEMINI_API_KEY` 설정 → Build and Test (u2 증분).
발급: https://aistudio.google.com/apikey

---
## CONSTRUCTION — u2 종단 검증 (Gemini) : 성공 + 결함 28~30
**Timestamp**: 2026-08-25T11:00:00Z
**User Input**: "키 설정 완료"
**Context**: `GEMINI_API_KEY` 설정 후 첫 실제 답변 생성

### ✅ u2 MVP 종단 성공 (query_id 12)
```
질의: "황산 취급 시 보호구는?"
outcome: answered / removed 0 / 문장 6개 전부 supported
  [0] 눈 노출 가능성이 있는 경우 KOSHA 인증 화학물질용 보안경 착용        → 근거 7001
  [1] 비산물·유해액체 보호를 위해 보안경 위에 겹쳐 쓰는 보안면 착용        → 근거 7012
  [2] 손 보호를 위한 내화학성 장갑                                    → 근거 7012
  [3] 신체 보호를 위한 내화학성 보호의                                 → 근거 7012
  [4] 호흡보호구는 KOSHA 검정품                                      → 근거 7001, 7012
  [5] 미지농도·IDLH 시 전면형 공기호흡기 또는 복합식 에어라인 마스크      → 근거 7001, 7012
근거: 황산 MSDS msds_08 (노출방지 및 개인보호구) — 정확
스트리밍: token 이벤트 308~340개. 증분 JSON 파서가 한국어 문장을 정상 추출
```
**SC-2(문장 단위 인용) · SC-3(근거 부족 시 거부) · FQ2-13(본문 스트리밍) 실증 완료.**

### BR-86a 가 숫자로 확인됨
```
purpose | calls | in_tok | out_tok
verify  |     6 |  9,208 |      72
answer  |     1 |  4,597 |     326
entity  |     1 |    396 |      61
```
**검증의 입력 토큰이 생성의 2배다.** 질의당 호출 8회 = `1 + 문장 6 + entity 1`.
무료 티어에서 이 비용은 돈이 아니라 **할당량**으로 나타났다 — 429 RESOURCE_EXHAUSTED.

### 모델 선정 (실측)
```
gemini-3.7-flash      503 UNAVAILABLE (지속)
gemini-flash-latest   503  ← 별칭이 사용 불가 모델을 가리킴
gemini-3.6-flash      OK  3,268ms   ← 채택
gemini-3.5-flash      OK  3,628ms
gemini-3.1-flash-lite OK    971ms
```
`-latest` 별칭을 쓰지 않고 버전을 고정하기로 한 판단이 **첫날에** 값을 했다.

### 결함 28 — 선택적 단계가 지연 예산을 파괴할 수 있었다
C30 엔티티 추출은 **최적화**다(BR-64: 규칙으로 해석되면 LLM 미호출). 그런데
메인 재시도 정책을 공유해, 503 모델을 만나자 **339ms 검색을 69초로** 만들었다.
NFR-2 예산은 2.5초다. → `build_entity_llm()` — 재시도 0, 타임아웃 2초.

### 결함 29 — Gemini 클라이언트에 타임아웃이 전달되지 않았다
`genai.Client(api_key=...)` 만 넘겨 `llm_timeout_seconds` 가 **무시되고 있었다.**
결함 28 의 수정이 실제로는 적용되지 않았다는 뜻이다(retrieval 18.3s 실측).
→ `http_options=types.HttpOptions(timeout=...)` 추가.

### 결함 30 — `llm_call` 이 한 건도 기록되지 않았다 (FR-41·FR-42 무력화)
`LlmCallRepo` 와 E18 테이블은 있었으나 **아무도 호출하지 않았다.** u1 의 `TracedLLM`
은 인메모리 `TraceRepo` 에 쓰고, u2 는 그것을 실테이블로 승격하고도 데코레이터를
연결하지 않았다. P6 사용량 화면이 영원히 0 을 보여줄 상태였다.
→ `adapters/llm_trace.py` 신설. `purpose` 를 래퍼별로 고정해 **`verify` 비용이
`answer` 안에 숨지 못하게** 한다(BR-86a).

### 부수 정정 — `query_log.top_score` 가 판정과 다른 값을 기록했다
결함 27 로 거부 판정을 코사인 유사도로 바꿨는데 로그는 RRF 융합 점수를 계속 적고
있었다(0.0325 vs 0.6596). **판정에 쓴 값과 기록하는 값이 다르면 로그로 임계값을
캘리브레이션할 수 없다**(BR-74, u4 전제). 이제 `relevance` 를 기록한다.

### ⚠️ 미해소 — 실패한 질의는 흔적을 남기지 않는다
`session_scope` 가 예외 시 전체를 롤백하므로, 질의가 실패하면 `query_log` 행과
`llm_call` 행이 **함께 사라진다.** 관측이 가장 필요한 순간에 관측이 없다.

이는 결함 26(BR-72)과 **같은 부류**다 — 규칙은 올바르게 읽히지만 트랜잭션 구조상
성립할 수 없다. BR-78("거부는 query_log 에 기록")과 BR-95("실패한 호출도 기록")가
오류 경로에서 달성 불가능하다.

구분이 필요하다: **BR-92 의 전부-아니면-전무는 답변 내용에 대한 것**이고,
`query_log`·`llm_call` 은 **관측**이므로 실패를 견뎌야 한다. 별도 세션·커밋이 필요하며
Build and Test 항목으로 남긴다.

### 남은 성능 격차
```
retrieval_ms  5,667 ~ 18,323 ms   (NFR-2 예산 2,500ms)
total_ms     25,909 ~ 36,085 ms   (NFR-1 예산 20,000ms)
```
결함 29 수정 후 재측정이 필요하다. 429 로 3회 시도가 실패해 아직 확보하지 못했다.

### 검증 상태
테스트 **400 통과 + 1 스킵**, ruff clean.

---
## CONSTRUCTION — 결함 31 해소 : 관측이 관측 대상과 운명을 공유했다
**Timestamp**: 2026-08-26T01:00:00Z
**User Input**: "문제 1"
**Context**: u2 종단 검증에서 미해소로 남긴 항목

### 문제
`session_scope` 가 예외 시 전체를 롤백하므로, 질의가 실패하면 `query_log` 행과
`llm_call` 행이 **함께 사라졌다.** 실측(2026-08-25): 429 로 3회 실패한 질의가
`query_log` 0행 / `llm_call` 0행을 남겼다. **관측이 가장 필요한 순간에 관측이 없다.**

결함 26(BR-72)과 **같은 부류**다 — 규칙은 올바르게 읽히지만 트랜잭션 구조상 성립할 수
없다. BR-78("거부는 오류가 아니라 기록되는 결과")과 BR-95("실패한 호출도 기록")가
오류 경로에서 도달 불가능했다.

### 해결 — 무엇이 원자적이어야 하는지 구분했다
| 대상 | 트랜잭션 | 근거 |
|---|---|---|
| **답변 내용** E15·E16·E17 | 전부-아니면-전무 | BR-92. 스냅샷 없는 인용은 표시도 복구도 불가 |
| **시도했다는 사실** E14·E18 | 독립 커밋 | BR-78·BR-95. 실패를 견뎌야 한다 |

**이 비대칭이 설계다.** 근거를 보여줄 수 없는 답변은 존재해서는 안 되지만,
시도했다는 사실은 무엇에도 살아남아야 한다.

- `db/engine.py` — `observability_scope()` 신설. 같은 엔진, 별도 트랜잭션.
  커밋 실패가 원래 오류를 가리지 않도록 삼키고 경고만 남긴다
- `QueryRepo(session, log_session)` — E14 는 로그 세션, E15~E17 은 콘텐츠 세션.
  `commit_log()` 는 저장소에 트랜잭션 제어가 등장하는 유일한 지점이고, 두 번째 세션의
  존재 이유가 바로 그것이므로 의도된 것이다.
  **세션을 공유하면(테스트) `commit_log()` 는 아무것도 하지 않는다** — 조기 커밋은
  BR-92 를 깬다
- `QueryService.answer` → `_answer` 분리. `answer` 는 로그 행을 **검색 전에 커밋**하고
  (이후 무슨 일이 나도 남도록, 그리고 `answer_sentence.query_id` 가 참조할 대상이 되도록),
  예외를 잡아 `mark_error` 후 다시 커밋하고 재전파한다
- 라우터는 `observability_scope` 를 `session_scope` **바깥에** 연다

### 검증 (실패 주입 = 존재하지 않는 모델명)
```
실패 질의 17 (outcome=error, retrieval_ms=29,788, total_ms=30,149)
  query_log 행        1   ← 남았다
  llm_call  행        2   ← 남았다 (entity 실패 2건, error_kind=ClientError)
  answer_sentence     0   ← 롤백됐다 (BR-92 유지)
  answer_citation     0   ← 롤백됐다

전체: query_log 8 / llm_call 11 / 실패 호출 3 / error 질의 1
스냅샷 없는 인용: 0   ← BR-92 불변식 유지
```
**두 성질이 동시에 성립한다** — 그것이 분리의 목적이었다.

테스트 **410 통과 + 1 스킵**, ruff clean.
신규 `tests/unit/test_observability_survives_failure.py` 10건 (세션 분리, 조기 커밋 금지,
커밋 실패가 원래 오류를 가리지 않음, 거부 사유→outcome 매핑).

---
## CONSTRUCTION — 문제 2 : 성능 예산 초과 해소 (결함 32~34)
**Timestamp**: 2026-08-26T02:00:00Z
**User Input**: "문제 2 진행하세요"

### 측정이 먼저였다 — 검색 자체는 문제가 아니었다
단계별 실측 (웜, `docker compose exec`):
```
normalize          0.0 ms
entity extract   133.2 ms   ← 유일한 변수
keyword           18.4 ms
vector             4.2 ms
chunk_metadata     1.9 ms
fusion+spread      0.2 ms
resolve_evidence   1.5 ms
────────────────────────
엔티티 제외 합계   ~26 ms     (NFR-2 예산 2,500ms)
```
5,667~18,323ms 는 **전부 C30 엔티티 추출의 LLM 호출**이었다.

### 결함 32 — 값을 하지 못하는 LLM 호출이 예산을 먹고 있었다
C30 이 규칙으로 못 만드는 유일한 출력은 `substance_names` 인데, 이를 해석하려면
`substance_synonym`(BR-65)이 필요하고 **u1 은 그 표를 비워 둔다** — u3 를 위한
선반영이다(DD-21, UD-6). `substance`·`substance_synonym`·`document_substance` 전부 0행.

3개 질의 A/B 실측:
```
질의                          규칙만      LLM경로     doc_type_hint   최종 근거
황산 취급 시 보호구는?          46.0 ms   582.5 ms   msds  (정확)     동일
화학물질 취급자의 교육 의무는?   0.8 ms   116.5 ms   law   (정확)     동일
염산 누출 사고 사례             0.7 ms   139.0 ms   incident (정확)  동일
```
규칙 힌트가 3/3 정확하고 **최종 근거 집합이 동일**하다.
→ `ENTITY_LLM_ENABLED=false` 기본. **모델에 대한 판단이 아니라 전제조건**이다 —
물질 마스터가 채워지면 켠다. 건너뛸 때 조용히 넘어가지 않고 로그로 말한다:
보이지 않는 비활성 기능은 고장난 것과 구분되지 않는다.

### 무료 티어 할당량의 정체 (실측)
```
GenerateRequestsPerDayPerProjectPerModel-FreeTier
limit: 20, model: gemini-3.6-flash
```
**모델당 하루 20요청.** BR-86a(`1 + 문장 수`)와 곱하면 6문장 답변 하나가 7요청이다.

### 결함 33 — 검증이 생성과 같은 할당량 풀을 놓고 경쟁했다
할당량이 **모델당**이므로 검증에 다른 모델을 주면 풀이 분리된다.
경량 모델이 타협이 아니라 적합인 이유: SP-6 이 검증자에게 문장 1개·자기 근거·enum 만
주고 **질문은 보여주지 않는다.** 실측 971ms vs 3,268ms.
→ `VERIFY_MODEL=gemini-3.1-flash-lite`.

**다만 벽은 남는다.** 분리는 검증이 생성을 굶기는 것을 막을 뿐이고,
`20 ÷ 문장 수` 는 여전히 **하루 약 3질의**다. 이것은 코드 결정이 아니라
유료 전환 여부의 문제이므로 팀 판단으로 남긴다.

### 결함 34 — 타임아웃이 예산이 아니라 SDK 기본값에서 왔다
- `retry-after` 34초를 그대로 따라 한 질의가 **64.6초**를 썼다. 20초 예산 안에서
  34초를 자는 것은 재시도가 아니라 같은 실패로 끝나는 정지다 →
  `MAX_RETRY_AFTER_SECONDS=5` 초과 시 즉시 실패
- `llm_timeout_seconds=60` 이 남아 실패까지 **60.6초** →
  **NFR-1 의 20초에서 유도**: 생성 10초 / 검증 5초.
  최악 = `10 + ceil(문장수/4) × 5` ≈ 20초

### 결과
```
검색 지연 (거부 경로 5회):  12, 12, 12, 23, 14 ms      NFR-2 예산 2,500ms
검색 지연 (온토픽):          26 ~ 168 ms
실패까지 소요:               60.6s → 5.2s
```
**NFR-2 충족.** NFR-1 전체는 할당량 소진으로 정상 경로 재측정 대기 —
근거 있는 최악은 약 20초이나 실측이 아니다. **"충족"이라고 쓰지 않는다.**

테스트 **422 통과 + 1 스킵**, ruff clean.
신규 `tests/unit/test_entity_extraction.py` 12건 (규칙 우선 단락, 게이팅, 힌트 3종,
동의어 해석, 미해석어 보존).

---
## CONSTRUCTION — 개발용 운영 확정 + 결함 35 (자초한 회귀)
**Timestamp**: 2026-08-26T03:00:00Z
**User Input**: "개발용"
**Context**: 무료 티어 하루 ~3질의 제약을 개발용으로 수용

### 결정
유료 전환하지 않는다. **하루 약 3질의**로 개발한다. 따라서 **할당량 소진이
"고장"처럼 보이지 않는 것**이 요건이 된다 — 이것이 개발 세션의 평범한 끝이다.

### 할당량을 그 자체의 조건으로 승격
429 가 `transient` 로 뭉뚱그려져 화면에 원시 Gemini JSON 이 그대로 떴다.
"기다리세요"와 "고장났습니다"가 같게 읽히면 안 된다.
- `QuotaExhaustedError` 신설 (여전히 TRANSIENT — 실제로 회복되므로) +
  `retry_after_seconds`
- SSE `error.kind = "quota"` / 화면은 "할당량을 모두 사용했습니다. 약 N초 후..."

### 검증 실패도 두 가지를 구분한다
검증 중 할당량이 떨어지면 문장이 `unverified` 로 제거되는데(BR-87, 옳다),
화면에는 "근거가 확인되지 않았다"로만 보였다 — **판정한 것과 물어보지 못한 것이
같게 읽힌다.**
→ `VerifiedSentence.unverified_by_quota`. 제거는 그대로지만(BR-87 은 굽히지 않는다)
   화면이 "그중 N개는 판정 결과가 아니라 할당량 소진으로 확인하지 못한 것"이라고 밝힌다.

BR-96(미등록 단가를 0 으로 쓰지 않는다)·BR-87(미검증을 지지로 보지 않는다)과 같은
원칙이다: **서로 다른 두 사실을 하나로 적지 않는다.**

### 결함 35 — 타임아웃을 예산에서 유도한 것이 회귀였다 (자초)
직전 커밋에서 `llm_timeout_seconds` 를 NFR-1 의 20초에서 유도해 **10초**로 잡았다.
그 뒤 `llm_call` 실측을 보니:
```
purpose  ok  count  min_ms   avg_ms   max_ms   avg_in
answer   t       1  11,582   11,582   11,582    4,597
verify   t       6   2,202    2,905    3,588    1,535
entity   t       1   5,809    5,809    5,809      396
```
**성공한 생성이 11,582ms.** 10초 상한은 동작하던 질의를 실패로 바꾼다.

**타임아웃의 일은 정지를 끊는 것이지, 못 지키는 SLO 를 강제하는 것이 아니다.**
둘이 어긋나면 NFR-1 미달을 기록할 일이지 미달을 오류처럼 보이게 할 일이 아니다.
→ **실측 + 여유**로 정정: 생성 20초 / 검증 8초.

### NFR-1 상태 — 미달 (실측 1건)
```
성공 질의 12: total_ms 36,085 ms   (NFR-1 예산 20,000ms)
  구성(실측): entity 5,809 + answer 11,582 + verify 6회(동시 4 → 2라운드) ≈ 7,200
              + 검색 168 + 오버헤드
```
엔티티 비활성화로 **약 5.8초가 빠진다**(실측 기준). 나머지는 할당량 회복 후
재측정해야 한다. **현 시점 NFR-1 은 충족이 아니다.** 근거 없이 "충족"이라고 쓰지 않는다.

### 상태 요약
| NFR | 상태 |
|---|---|
| NFR-2 검색 P95 2.5초 | ✅ **충족** — 12~168ms 실측 |
| NFR-1 전체 20초 | ❌ **미달** — 36.1초 실측 1건. 엔티티 제거분 반영 후 재측정 대기 |

테스트 **425 통과 + 1 스킵**, ruff clean.

---
## CONSTRUCTION — NFR-1 재측정 : **충족** + 결함 36~38
**Timestamp**: 2026-08-26T05:00:00Z
**User Input**: "할당량 회복 후 NFR-1 재측정"

### 결함 36 — 모델 선택이 예산의 전부였다
같은 프롬프트(근거 5건, 입력 4,597토큰)를 세 모델에 던진 실측:
```
gemini-3.1-flash-lite     4,133 ms   6문장, 인용 정확
gemini-3.6-flash         73,258 ms
gemini-3.5-flash         78,178 ms
```
**18배 차이**다. 부하가 걸린 무료 티어에서 지연이 프롬프트 크기에 매우 나쁘게
스케일하는데, 소형 모델은 그 문제가 없다.

thinking 을 의심해 `thinking_budget=0`(400 거절)·`thinking_level=low`(119,673ms —
오히려 악화)를 시험했다. **원인이 아니었다.** 가설을 코드가 아니라 측정으로 기각했다.

검증 프롬프트(1,593자)도 같은 방향: lite 2,269ms vs 3.6-flash 9,297ms.

### 앞서 세운 할당량 분리 논리를 측정이 뒤집었다
검증에 다른 모델을 주어 20/day 풀을 분리하려 했으나(결함 33), 실측 결과
- 분리: 하루 ~3.3질의 / NFR-1 **22.7초 (미달)**
- 동일: 하루 ~2.8질의 / NFR-1 **8.7초 (충족)**

**지연 예산 충족이 하루 0.5질의보다 값지다.** 둘 다 lite 로 둔다.
`verify_model` 설정은 유지 — 대안 모델이 비슷하게 빨라지면 분리가 다시 유리해진다.

### 결함 37 — 제공자 최소 데드라인 (몰랐던 제약)
```
400 INVALID_ARGUMENT  "Manually set deadline 8s is too short.
                       Minimum allowed deadline is 10s"
```
`VERIFY_LLM_TIMEOUT_SECONDS=8` 이 **모든 검증 호출을 실패**시켰고, BR-87 이 그것을
올바르게 `unverified` 로 제거해 **답변이 통째로 비워졌다**(3질의 모두 `refused_unsupported`,
문장 0). 설정값 하나가 규칙을 통해 답변을 지운 것이다.
→ 어댑터가 10초로 클램프하고 **경고를 남긴다.** 조용히 받아들이면
`entity_llm_timeout_seconds=2` 가 효력 있어 보이는데 제공자가 무시하는 상태가 된다.
⚠️ 결과적으로 엔티티의 "2초 목줄"은 Gemini 에서 존재하지 않는다 — 재시도 0 만 유효하다.

### 결함 38 — 클라이언트 lazy 초기화 경합
```
"Cannot send a request, as the client has been closed."   8건 중 3건
```
검증은 스레드 풀에서 돈다(PP-5). `_get_client()` 에 락이 없어 두 스레드가 각자
클라이언트를 만들고, 한 대입이 이기면 진 쪽 클라이언트가 그것을 쓰던 스레드 아래에서
수거됐다. BR-87 이 그 문장들을 정확히 제거했으므로 **경합이 근거 문제처럼 보였다.**
→ double-checked locking.

### ✅ 최종 실측 — NFR-1 충족
```
id | outcome  | retrieval_ms | total_ms | 유지 | 제거
51 | answered |          124 |    4,181 |    6 |    0
52 | answered |          132 |    2,154 |    1 |    0

purpose  calls  avg_ms  max_ms  failed
answer       2   1,582   2,065       0
verify       7   1,060   1,381       0
```
| NFR | 예산 | 실측 | 상태 |
|---|---|---|---|
| NFR-2 검색 P95 | 2,500 ms | **109~151 ms** | ✅ 충족 |
| NFR-1 전체 | 20,000 ms | **2,154~4,181 ms** | ✅ **충족** |

답변(query 51) 6문장 전부 `supported`, 제거 0, 인용은 황산 MSDS `msds_08`
(노출방지 및 개인보호구):
```
0. 화학물질용 보안경 착용
1. 보안경 위에 겹쳐 쓰는 보안면
2. 내화학성 보호의
3. 내화학성 장갑
4. KOSHA 검정 호흡용 보호구
5. 미지농도·IDLH 시 송기마스크 또는 전면형 공기호흡기
```

### 미해소
- **PP-4 프롬프트 캐시 적중 0** — `cache_read_tokens` 가 NULL 이다. Gemini 암묵 캐시는
  최소 토큰 수 조건이 있고 우리 프롬프트가 그 아래이거나, nonce(SP-3)가 매 요청 바뀌는
  근거 블록 때문일 수 있다. **가설이며 측정하지 않았다.** BR-94 배치 자체는 유지된다.
- 비용은 0.000000 / 미산정 0 — 무료 티어를 실제 0 으로 등록한 것이 정상 동작(BR-96).

테스트 **425 통과 + 1 스킵**, ruff clean.

---
## CONSTRUCTION — Build and Test (u2) : 결함 34a·39 + 전 코퍼스 검증
**Timestamp**: 2026-08-26T07:00:00Z
**User Input**: "진행"

### 통합 테스트 계층 신설
`tests/integration/` — 마커 `integration`, 기본 실행에서 제외(NFR-28 유지).
호스트에서 `docker-compose.override.yml` 의 `127.0.0.1:5433` 으로 접속한다.
**6 passed, 1 skipped** (건너뛴 1건은 호스트에 `google-genai` 부재, 컨테이너에서 별도 확인).

존재 이유를 파일 docstring 에 남겼다: 결함 26·31·37·38 은 전부 같은 모양이었다 —
규칙이 옳게 읽히고, 단위 테스트가 통과하고, **실제 트랜잭션·스레드 풀·실제 제공자가
개입해야만** 드러났다. 각 경우에 **모킹된 그것이 바로 틀린 대상**이었다.

### 결함 39 — 리랭커 진입점이 한 번도 실행된 적 없었다
```
ImportError: cannot import name 'configure_logging' from 'app.core.logging'
```
실제 함수명은 `configure` 다. `rerank_service.py` 를 쓰고 컨테이너를 한 번도 띄우지
않았기 때문에 드러나지 않았다. 결함 25(u1 의 `to_tsvector`)와 같은 모양이다.

### 결함 34a — 리랭커 실패가 질의마다 3.4초
소켓 타임아웃이 실패 전체를 묶지 못한다. 컨테이너가 내려간 상태에서 이름 해석만으로
**3,402ms**(타임아웃 1,200ms, 검색 예산 2,500ms). 결함 28·29 와 같은 부류 —
**선택적 구성요소가 자기가 개선하려는 것의 예산을 파괴해서는 안 된다.**
→ 실패 후 60초 쿨다운. 실측 1회차 3,402ms → 2·3회차 0.0ms.

### ⚠️ 리랭커는 예산 안에서 쓸 수 없다 (측정 결론)
```
기동·격리·품질    ✅  보호구 섹션 1위 (0.0164 vs 0.0000/0.0005), 메모리 1.475/2 GiB
최초 호출         264 s (모델 다운로드 포함)
웜 호출 (문서 5)  2,121 ~ 2,830 ms      ← 예산 1,200 ms
```
켜면 매 호출이 타임아웃 → 폴백이므로 **얻는 것 없이 1.2초만 잃는다.**
bge-reranker-v2-m3 는 CPU 에서 NFR-2 안에 들어가지 않는다.
**BR-70 의 기본 OFF 에 이제 측정 근거가 있다.** 켜려면 타임아웃 상향 + NFR-2 재검토,
또는 GPU 가 필요하다.

### N3 스캐너 전 코퍼스 — 오탐 0%
재색인 1회로 1,598청크에 플래그를 채웠다.
```
incident   12 → 0 flagged      law  1,173 → 0      msds  413 → 0
합계    1,598 → 0 flagged (0.0%)     meta 필드 1,598/1,598 (스캐너 적용 확인)
```
양성 대조는 정상 발동(role_hijack / delimiter_shape / output_directive).
**적대적 텍스트에는 발동하고 실코퍼스에는 발동하지 않는다** — SP-5 가 걱정한
"안전 정보를 지우는 방어"가 실데이터로 반증됐다.

다만 정직하게: 운영 데이터에서 이 스캐너가 발동한 적은 **아직 없다.** 탐지율의 근거는
단위 테스트뿐이고 실데이터 근거는 없다. u5 업로드가 열리면 그때가 첫 실측이다.

### 재색인 후 불변식
`70문서 / 1,598청크 / 1,598벡터 / 상한 초과 0 / BR-30 위반 0`

### 산출물
`construction/build-and-test/u2-build-and-test-summary.md`

---
## CONSTRUCTION — Build and Test (u2-rag-qa) : **APPROVED**
**Timestamp**: 2026-08-26T08:00:00Z
**User Input**: "승인"
**Context**: CONSTRUCTION - Build and Test (u2) 승인 게이트 → 통과

### 승인 근거
- 단위 **425 통과 + 1 스킵**, 통합 **6 통과 + 1 스킵**(실 PostgreSQL), ruff clean
- **NFR-1 충족** (예산 20,000ms / 실측 2,154~4,181ms)
- **NFR-2 충족** (예산 2,500ms / 실측 109~151ms)
- **SC-2 · SC-3 · SC-7 달성** — 문장 단위 인용, 근거 부족 시 거부, LLM 사용량 조회
- 결함 **25~39 (15건)** 전건 수정, 각각 회귀 테스트 보유
- 실데이터 불변식: 70문서 / 1,598청크 / 1,598벡터 / 상한 초과 0 / BR-30 위반 0
- N3 인젝션 스캐너 전 코퍼스 오탐 **0%**, 양성 대조 정상

### ⭐ u2 완료 = 계획상 "단독 완결 포트폴리오 최소 목표" 도달
Workflow Planning(2026-08-20)이 정한 최소 목표 지점이다. 수집·색인 위에
**출처가 추적되고 근거가 없으면 답하지 않는** 질의응답이 올라갔고, 실제로 동작한다.

### 이 유닛에서 배운 것 — 결함 15건의 공통 구조
| 부류 | 결함 | 공통점 |
|---|---|---|
| **한 번도 실행된 적 없음** | 25(`to_tsvector`), 39(리랭커 진입점) | 코드가 존재하고 테스트가 초록불인데 그 경로가 돈 적이 없다 |
| **규칙이 구조상 성립 불가** | 26(BR-72), 31(관측 롤백) | try/except 는 옳게 읽히지만 트랜잭션이 그것을 허용하지 않는다 |
| **틀린 신호를 읽음** | 27(RRF vs 코사인), 30(`llm_call` 미기록) | 보정으로 못 고친다. 무엇을 재는지가 틀렸다 |
| **선택적인 것이 필수의 예산을 파괴** | 28, 29, 32, 34a | 실패해도 되는 단계가 실패하는 데 예산 전체를 쓴다 |
| **제약을 몰랐음** | 36(모델 18배), 37(최소 데드라인) | 측정하지 않으면 알 수 없다 |
| **자초** | 34(예산에서 타임아웃 유도) | 옳아 보이는 원칙이 실측과 어긋날 때 실측이 이긴다 |

**가장 값진 방법론적 결과**: `tests/integration/` 계층을 만든 것. 결함
26·31·37·38 은 전부 단위 테스트를 통과했고, **모킹된 그것이 바로 틀린 대상**이었다.

### 다음 단계
**`u4-evaluation` (3/5)** — 골든 QA 셋. NFR-5(인용 정확도 ≥95%)와
NFR-6(faithfulness ≤5%)을 **처음으로 수치로 만든다.** BR-74 거부 임계값
캘리브레이션, QG-4·QG-5 도 여기서 해소된다.

### 승인 시 함께 기록한 미결
1. **무료 티어 하루 ~3질의** — 개발용 수용(2026-08-26). u4 평가셋 실행 규모에 제약이 된다
2. **리랭커 사용 불가** — CPU 에서 2,121~2,830ms vs 예산 1,200ms
3. **PP-4 캐시 적중 0** — 원인 미측정, 가설만 존재
4. **u1 물질 마스터 공백** — `substance` 등 3개 표 0행. BR-38·BR-65 가 사실상 비활성이며
   u3 범위와 겹친다. **u4 착수 전 u3 순서 재검토 여지**

---
## CONSTRUCTION — 유닛 순서 변경 : u4 → **u3 먼저** + 결함 40
**Timestamp**: 2026-08-26T09:00:00Z
**User Input**: "u3 먼저 진행"
**Context**: u2 승인 후 다음 유닛 선택

### 순서 변경 근거
Workflow Planning(2026-08-20)은 `u2 → u4 → u3` 을 정했고 근거는 타당했다 —
"평가 하네스를 u2 직후 확보하면 이후 모든 변경의 품질 회귀를 즉시 수치로 감지".

그러나 그때 **알려지지 않았던 사실**이 u2 Build & Test 에서 드러났다:
`substance` · `substance_synonym` · `document_substance` 가 **전부 0행**이고,
그 결과 **BR-38(CAS·UN·물질명 완전일치)과 BR-65(동의어 해석)가 사실상 비활성**이다.

이 상태에서 골든셋을 만들면 **"물질 검색이 죽어 있는 상태"를 정답으로 굳힌다.**
평가 하네스의 가치는 기준선이 옳다는 전제 위에 있고, 지금 기준선은 옳지 않다.

**부수 이점**: u3 은 **LLM 을 사용하지 않는다**(unit-of-work.md §u3). 무료 티어
하루 ~3질의 제약이 u3 에는 전혀 걸리지 않는다 — u4 에는 정면으로 걸린다.

### 결함 40 — BR-33·BR-37 이 구현된 적 없다 (u1, FR-1)
```
SubstanceRepo.upsert()      호출부 0
SubstanceRepo.add_synonyms() 호출부 0
IndexingService._resolve_substances() → get_by_cas() 만 호출 (읽기 전용)
```
`SubstanceRepo` 와 스키마는 u1 에 있고 **쓰기 경로만 없다.** 따라서
- `substance` 0행 → BR-33 미구현 (FR-1 물질정보 수집)
- `document_substance` 0행 → BR-37 미구현 (`get_by_cas` 가 항상 None 이므로)
- `chunk.meta.cas_number` 0건 → BR-38 완전일치가 매칭할 대상이 없음

u1 Build & Test 는 `stats.substances = 0` 을 보고도 통과했다. **0 이 "아직 수집
안 함"으로 읽혔지, "수집해도 마스터가 안 채워짐"으로 읽히지 않았다.**
결함 25(`to_tsvector`)·39(리랭커 진입점)와 같은 부류 — **그 경로가 돈 적이 없다.**

### 재수집은 필요 없다 — 설계가 맞았다
원본 40건이 `data/originals/ncis_substance/*.json` 에 보존되어 있고
`cas_number` · `name_ko` · `name_en` 을 갖고 있다. 필요한 것은 **보존된 원본에서
마스터로의 투영**이며, 이는 BR-44(원본 보존)가 존재하는 이유 그 자체다.
unit-of-work.md §u3 의 "재수집이 발생하지 않습니다"는 여전히 참이다 —
다만 그 전제가 "이미 채워져 있다"가 아니라 "채울 재료가 남아 있다"였을 뿐이다.

### u3 범위에 미치는 영향
결함 40 수정이 u3 Functional Design 의 **선행 조건**이 된다. 카드가 조회할 대상이
없으면 FR-23~26 이 성립하지 않는다.

---
## CONSTRUCTION — Functional Design (u3-substance-card)
**Timestamp**: 2026-08-26T10:00:00Z
**User Input**: "권장안대로 진행"
**Context**: CONSTRUCTION - Functional Design / 유닛 `u3-substance-card` (3/5)

### 답변 (FQ4-1 ~ FQ4-14)
`A A A B A A A A A A A A A A` — **FQ4-4 만 (b)**, 나머지 전부 (a)

| # | 확정 사항 |
|---|---|
| FQ4-1~2 | 마스터 투영은 **색인 경로 안에서**. 기존 코퍼스는 재색인 1회 |
| FQ4-3 | 동의어는 `name_ko`·`name_en` 만. **이명을 생성하지 않는다** |
| **FQ4-4** | **한 항목의 출처가 여럿이면 전부 싣는다** |
| FQ4-5 | u2 표기 규약 재사용, `citation_snapshot` 은 쓰지 않는다 |
| FQ4-6 | 이름 모호 시 후보 목록. **시스템이 고르지 않는다** |
| FQ4-7 | 응급조치는 노출경로 4종을 하위 항목으로 |
| FQ4-8 | 7항목 전부 표시 + 결측 개수 고지 |
| FQ4-9~11 | u1 정규화 재사용, 직접 조회, UN 은 "데이터 없음" |
| FQ4-12~14 | `/substances`, P5 연결 없음, 평범한 JSON |

### 설계 중 확인한 실측 (계획서 §실측 데이터)
```
물질 원본 40건:  cas_number 40/40 · name_ko 40/40 · name_en 40/40
                inhale/skin/eyeball 40/40 · oral 39/40
                GHS · 신호어 · H·P · 물리화학적 성질 · 적용법령 · 이명  → 전부 없음
MSDS 16섹션 구조 문서: 약 7건
```
→ **FR-24 의 7항목 중 6개가 MSDS 출처**이므로 물질 40건 중 대부분은 항목 대부분이
비어 있다. 이는 결함이 아니라 **FR-25 가 예상한 상황**이다.

### 세 가지 판단
**1. 없는 데이터를 만들지 않는다.** 이명 생성(FQ4-3=B)은 "이명"이 아니라 우리가 만든
문자열이고, `term_type` 이 둘을 구분하지 못하면 카드가 근거 없는 이름을 사실처럼
보여준다. 구조화 GHS 컬럼도 같은 이유로 비워 둔다(BR-108) — MSDS 2번 섹션 파싱이
어긋나면 **잘못된 GHS 분류가 구조화된 사실로** 저장된다. 본문 인용이면 틀려도
사용자가 원문에서 확인할 수 있다.

**2. 빠진 것을 말한다.** 7항목을 항상 표시하고 결측 수를 고지한다(BR-106).
빈 항목을 빼면 카드가 완전해 보이고, 사용자는 "이 물질은 정보가 없다"와 "이 시스템이
안 보여준다"를 구분할 수 없다. u2 의 BR-88·BR-96 과 같은 원칙이다.
`MatchKind` 의 `un`·`alias` 도 열거에서 지우지 않는다 — 지우면 FR-26 미충족 2종이
요구사항에서 사라진 것처럼 보인다(BR-110).

**3. 카드는 답변이 아니다.** `citation_snapshot` 을 쓰지 않는다(BR-107). 스냅샷은
답변이 인용한 시점을 동결하는 장치인데(BR-92), 카드는 **현재 상태 조회**다.
동결하면 원본이 개정돼도 **낡은 안전 정보를 계속 보여준다.**

### 산출물
`construction/u3-substance-card/functional-design/` — 4종
- `domain-entities.md` — **새 테이블 0개**. 값객체 V1~V3, Enum 4종
- `business-logic-model.md` — 워크플로 **W12~W14**
- `business-rules.md` — **BR-97 ~ BR-110** (14건)
- `frontend-components.md` — 화면 P7·P7-1, 요소 FE-24~34

### u3 이 u2 에 주는 부수 효과
BR-97 이 마스터를 채우면 **u2 의 규칙 둘이 함께 되살아난다**:
- **BR-38** CAS 완전일치 — 현재 `chunk.meta.cas_number` 0건이라 매칭 대상이 없다
- **BR-64·65** 동의어 해석 — `ENTITY_LLM_ENABLED` 를 켤 전제가 생긴다

u4 골든셋을 이 이후에 만들어야 하는 이유가 이것이다.

### 다음 단계
산출물 검토 → 승인 → **Code Generation (u3)**

---
## CONSTRUCTION — Functional Design (u3-substance-card) : **APPROVED**
**Timestamp**: 2026-08-26T10:30:00Z
**User Input**: "승인"

### 승인 근거
- 새 테이블 0개 — u1 선반영(DD-21, UD-6) 회수 확인
- BR-97~BR-110 (14건), 실측 데이터 기반
- 결함 40 해소 경로가 색인 안에 들어감 (분리된 쓰기 경로가 결함의 원인이었으므로)

### 다음 단계
**Code Generation (u3)** — LLM 미사용이므로 무료 티어 제약 없음

---
## CONSTRUCTION — Code Generation (u3) : 결함 40 해소 + 결함 41~43
**Timestamp**: 2026-08-26T12:00:00Z
**Context**: u3 Functional Design 승인 후 구현

### 결함 40 은 세 얼굴이었다
FD 를 쓸 때는 "쓰기 경로가 없다" 하나로 보였다. 실제로는 셋이다.

| # | 얼굴 | 증상 |
|---|---|---|
| ① | `SubstanceRepo.upsert()` 호출부 0 | `substance` 0행 |
| ② | `_resolve_substances` 가 `ref.extra["cas_number"]` 를 봄 (어댑터는 `extra["row"]`) | `document_substance` 0행 |
| ③ | `base_meta.cas_number` 도 같은 자리 | `chunk.meta.cas_number` 0건 → **BR-38 매칭 대상 없음** |

②③ 은 **읽기 경로**다. 쓰기만 붙였으면 마스터만 채워지고 연결과 색인 메타는
여전히 비어 있었을 것이다. 셋 다 `raw.payload` 기준으로 정정 —
신규 수집과 재색인(BR-44) 양쪽에서 같은 자리다.

```
                    전    후
substance            0    40
substance_synonym    0    80    (ko 40 + en 40, alias 0 — BR-99)
document_substance   0    40
chunk cas_number     0   273
chunk substance_ids  0   273
```

### 결함 41 — 물질명에 출처의 목록 표시자
`·아이소프로필아민`·`·Isopropylamine`, 40건 전부. 화학물질명의 일부가 아니라
출처가 목록 항목으로 렌더한 것이다.

**BR-99(이명 생성 금지)와 구분해 적었다**: 불릿 제거는 이름 생성이 아니다. 다만
**앞머리 불릿만** 떼고 이름 안쪽은 건드리지 않는다.
처음에 `-`·`—`·`*` 까지 넣었다가 되돌렸다 — 화학물질명의 일부일 수 있고 **실제
데이터에서 관측되지 않았다.** 관측된 것만 남기는 것이 데이터를 고치지 않는 것이다.

### 결함 42 — BR-98 멱등성이 동의어에 적용되지 않았다
이름 정리 후 재색인하니 동의어 **160건**(80 신규 + 80 구). `add_synonyms` 는 완전
중복만 건너뛰므로 `·Isopropylamine` 이 살아남아 **아무도 검색해서는 안 될 철자가
유효한 조회 키로** 남았다.
→ `replace_synonyms()`. BR-54 가 청크를 전량 교체하는 것과 같은 이유 —
파생 데이터는 누적이 아니라 교체다.

### 결함 43 — `delete-orphan` 에서 컬렉션을 비워야 한다 (자초)
`replace_synonyms` 를 자식마다 `session.delete()` 로 썼더니 80이 아니라 **0**이 됐다.
관계가 `delete-orphan` 이라 `.clear()` 해야 하고, 개별 삭제는 객체를 컬렉션에 남겨
뒤이은 append 까지 함께 지운다.

**모킹된 저장소로는 볼 수 없다** — 가짜 저장소는 호출을 기록할 뿐이다.
u2 에서 만든 통합 테스트 계층이 잡았다.

### 검증
```
검색(이름) 1건 name_ko / 검색(CAS) 1건 cas / 검색(UN) 0건 + unsupported 고지
카드: has_msds=false, missing_count=6/7, 응급조치 4건(노출경로)
HTML: card-item 7개, missing-notice 1개
NFR-3: 6.7~27 ms  (예산 1,000 ms)  ✅
불변식: 70문서 / 1,598청크 / 1,598벡터 / 상한 초과 0 / BR-30 위반 0
```
단위 **449 통과 + 1 스킵**, 통합 **22 통과 + 1 스킵**, ruff clean.

### u2 가 함께 살아났다
`chunk.meta.cas_number` 273건과 동의어 80건이 생기면서 **BR-38 완전일치와 BR-65
동의어 해석이 처음으로 매칭 대상을 갖는다.** u4 골든셋을 이 이후에 만들기로 한
순서 변경의 근거가 실측으로 확인됐다.

---
## CONSTRUCTION — 결함 44 : BR-08 물질 선정 전략 미구현
**Timestamp**: 2026-08-26T13:00:00Z
**Context**: u3 실조회 검증 중 발견

### 증상 — 물질 카드 40건 전부가 6/7 결측
```
물질 마스터 40건 중 MSDS 를 가진 것: 0건
```
FD 는 "~7 물질은 MSDS 가 있다"고 적었다. **틀렸다.** "16섹션 구조 MSDS 문서가 약
7건"에서 추론했는데, 그 문서들이 마스터의 물질에 *관한* 것인지 확인하지 않았다.

```
MSDS PDF 8건   메탄올 · 황산 · 염산 · 톨루엔 · 폴리에틸렌 · 혼합물
물질 마스터 40건  아이소프로필아민 · 테트라메틸실리케이트 · 스트렙토마이신 …
                 (물질 API 목록의 앞 40개)
→ 교집합 0
```

### 원인 — BR-08 이 구현되지 않았다
> **BR-08**: 초기 수집 대상 물질은 **① 사고 사례에 등장한 물질 ② `is_regulated=true`
> 물질** 순으로 선정하며, `INITIAL_SUBSTANCE_TARGET` 도달 시 중단한다

```python
# adapters/sources/api_sources.py:238
limit = self._settings.initial_substance_target   # 단순 절단. 순서 로직 없음
```
**규칙도 있고 파라미터도 있는데 정렬 로직이 없다.** 결함 40(쓰기 경로 없음)·
결함 25(경로가 돈 적 없음)와 같은 부류다.

### BR-08 이 있었다면 달랐다 — 실측으로 확인
사고사례 12건이 **황산(1건)과 톨루엔(1건)을 언급**한다. 둘 다 MSDS PDF 를 갖고 있다.
BR-08 의 ① 순서를 따랐다면 이들이 마스터에 들어왔고, 카드가 실질적으로 채워졌을 것이다.

### 범위 판단
u3 범위 밖이다. BR-08 은 u1 **수집** 규칙이고, 고치면 물질 목록이 바뀌므로
**재색인이 아니라 재수집**이 필요하다(보존 원본에 없는 물질을 가져와야 한다).

카드 기능 자체는 정상 동작한다 — 결측을 정직하게 고지하는 것이 FR-25 이고 그렇게
동작한다. 다만 **시연 가치가 낮다**: 40건 전부가 응급조치 1항목만 보여준다.

### 선택지 (팀 판단 필요)
| 안 | 내용 | 비용 |
|---|---|---|
| A | BR-08 구현 후 재수집 | 물질 API 재호출. 사고사례 물질 우선 |
| B | `INITIAL_SUBSTANCE_TARGET` 상향 | 황산이 목록 어디쯤인지 모름. 임베딩 시간 급증 |
| C | 현행 유지 | 카드는 응급조치만. u4 골든셋도 그 전제로 만들어짐 |

**C 를 택하면 u4 골든셋이 "카드가 비어 있는 상태"를 정답으로 굳힌다** — u3 를 먼저
한 이유와 같은 문제가 한 겹 안쪽에서 반복된다.

---
## CONSTRUCTION — u3 전체 재색인 검증 + CAS 종단 + 결함 45
**Timestamp**: 2026-08-26T14:00:00Z
**User Input**: "재색인 끝나면 검증하고 실조회 종단 확인해주세요" / "CAS 번호로 u2 질의도 같이 확인해주세요"

### 전체 재색인 후 (실제 서비스 경로)
```
substance 40 / synonym 80 / stale 0 / doc_link 40 / chunk_cas 273
70문서 / 1,598청크 / 1,598벡터 / 상한 초과 0 / BR-30 0 / 벡터누락 0 / 고아인용 0
```
**동의어가 160이 아니라 80** — `IndexingService` 를 통한 실제 경로에서 BR-98 멱등성
성립. 직접 `project()` 호출뿐 아니라 `reindex_document` 2회 반복도 80 유지 확인.

### BR-38·BR-64·BR-65 가 처음으로 동작한다
```
BR-38 CAS 완전일치      75-31-0  → 키워드 7건   (수정 전 전부 0건)
                       681-84-5 → 키워드 7건
                       7664-93-9 → 0건   ← 황산은 마스터에 없음 (결함 44)

BR-64/65 규칙 해석      "75-31-0 취급 시…"        resolved_by_rules=True, CAS 추출
                       "아이소프로필아민 노출 시…"  resolved_by_rules=True, 동의어 해석 ✅
                       "황산 취급 시…"            False  ← 마스터에 없음
```
**동의어 해석이 성공한 것은 이번이 처음이다.** u2 의 `ENTITY_LLM_ENABLED=false` 근거
(결함 32: "마스터가 비어 `substance_names` 를 해석할 대상이 없다")가 마스터가 있는
물질에 한해 더 이상 성립하지 않는다. 켜는 것이 값을 하는지는 **미측정**.

### 결함 45 — 완전일치를 코사인 점수가 뒤집었다
CAS 질의가 **정확한 문서를 찾고도 거부**됐다.
```
질의: "CAS 75-31-0 물질에 노출되면 어떻게 해야 하나요?"
  키워드 완전일치 7건 (document 39 = 아이소프로필아민)
  코사인 0.481  <  임계값 0.50
  → refused / below_threshold
```
CAS 번호는 **사용자가 입력한 사실**이지 유사도 신호가 아니다. "CAS 75-31-0 물질에
노출되면"이라는 문장의 임베딩이 물질 레코드와 가까울 이유가 없고, 유사도가 완전일치를
뒤집을 근거도 없다.

`refusal.decide` 는 "키워드 전용 후보는 무관으로 취급하지 않는다"를 이미 갖고 있었으나,
**벡터 경로도 후보를 냈을 때는 임계값이 적용**됐다 — 더 강한 신호가 있는데도.
→ 완전일치가 있으면 임계값을 건너뛴다. `EXACT_MATCH_SCORE` 상수로 표식을 명시화.
결함 27(틀린 신호를 읽음)과 같은 부류다.

### CAS 종단 성공 (query 71)
```
outcome: answered / 제거 0 / 8문장 전부 supported
  0. CAS 번호 75-31-0인 물질은 아이소프로필아민입니다.
  1~3. 흡입 시 증상 …
  4. 삼키면 …
  5. 피부 접촉 시 …
  6~7. 안구 접촉 시 …
근거: substance_identity · substance_symptom · substance_inhale · substance_skin · substance_eye
total_ms 18,021 (콜드 임베딩 포함)
```
**CAS 번호가 물질로 해석되고, 노출경로별 근거가 문장마다 붙었다.** BR-38 이 대상을
갖게 된 것은 u3 이 마스터를 채웠기 때문이다 — u3 를 먼저 하기로 한 순서 변경이
실측으로 값을 했다.

테스트 **453 통과 + 1 스킵**, ruff clean.

---

---

## CONSTRUCTION — 결함 44 해소 : BR-08 구현 + 재수집, 결함 46
**Timestamp**: 2026-08-27T04:40:00Z
**Context**: 사용자 선택 A(BR-08 구현 후 재수집). 승인 발언: "A로 진행"

### 설계 결정 1 — BR-08 ② 는 **데이터가 없다**
`/kischemlist` 응답 필드는 `dataNo · casNo · chemKo · chemEn` + 응급조치 4경로가
전부다. **규제 여부를 나타내는 필드가 없다.** 정렬 기준을 만들어낼 수 없으므로
지어내지 않고 기록한다 — FR-26(UN/별칭 데이터 없음)과 같은 처리다.

대신 ① 을 **"코퍼스가 이미 말하는 물질"** 로 넓혔다. 사고 사례의 `substances` 구간에
더해 **이미 수집된 MSDS 문서의 제목**까지 본다. 종류가 같은 기준이고
(= 이 시스템이 그 물질에 관한 문서를 갖고 있다) 목적도 같다 — 내용이 있는 카드.

| BR-08 원문 | 처리 |
|---|---|
| ① 사고 사례에 등장한 물질 | ✅ 구현 + MSDS 제목까지 확장 |
| ② `is_regulated = true` | ❌ **소스에 해당 필드 없음.** 미구현으로 기록 |

### 설계 결정 2 — **완전일치만** 매칭한다 (부분일치는 실측으로 폐기)
7,189행 전량 스캔으로 먼저 재본 결과다.

```
"톨루엔" 을 포함하는 마스터 항목  68건  (2-브로모톨루엔 · 2,4-다이클로로톨루엔 …)
"황산"   을 포함하는 마스터 항목  56건  (황산구리 · 황산니켈 · 황산알루미늄 …)
```
부분일치로 정렬하면 **40건 예산이 유도체로 가득 차고 정작 톨루엔·황산은 못 들어온다.**
결함 44 와 같은 결과에 다른 경로로 도착하는 셈이다. → 정규화 후 완전일치만 인정.

정규화는 실측이 요구한 것만 넣었다.
```
·톨루엔          → 톨루엔        불릿은 원문 렌더링의 마크업 (결함 41 과 같은 것)
4,4‛-…  vs  4,4’-…             사고 원문과 마스터가 서로 다른 프라임 코드포인트
메틸에틸케톤  vs  메틸 에틸 케톤    공백은 축약이 아니라 제거해야 만난다
```
`,` 는 **구분자가 아니다**. "N,N-디메틸포름아미드"·"4,4'-디이소시안산 디페닐메탄"에서
이름의 일부다 — 초안이 `,` 로 쪼개 "4‛-디이소시안산 디페닐메탄"을 만들었고 아무것도
매칭되지 않았다. 농도 괄호 안(혼합물)에서만 `,` 로 나눈다.

### 설계 결정 3 — 배치: 어댑터는 DB 를 보지 않는다
용어는 DB(사고 구간·MSDS 제목)에서 나온다. **DB 를 조회하는 소스 어댑터는 더 이상
소스 어댑터가 아니다.** 그래서 `IngestionService` 가 읽어서 주입하고
(`adapter.priority_terms`), 비어 있으면 어댑터는 예전과 **완전히 동일하게** 소스 순서로
동작한다. 다른 두 어댑터와 모든 기존 테스트가 그 경로다.

```
DocumentRepo.substance_mentions()   사고 substances 구간 12 + MSDS 제목 8 = 20
  → substance_selection.candidate_terms()          32개 용어
  → SubstanceApiAdapter.list_targets()  전량 스캔 후 정렬·절단
```
`INITIAL_SUBSTANCE_TARGET` 로 하드와이어돼 있던 절단을 `_iter_listing(since, limit)`
인자로 분리했다. 선정은 **보관하는 것보다 많이 봐야** 한다.
새 설정 `SUBSTANCE_SCAN_CAP=10000` — 목록이 한 자릿수 배 커져도 수집이 무한 스캔이
되지 않게 하는 상한.

### 결함 46 — 목록 소진 시 `items: ""` (한 번도 실행된 적 없는 경로)
전량 스캔을 붙이자마자 터졌다.
```
page 73 : {"items": "", "numOfRows":100, "pageNo":73, "totalCount":7189}
          → _rows() : SchemaMismatchError "item list is not a list"
```
data.go.kr 은 마지막 페이지 다음을 **빈 리스트가 아니라 빈 문자열**로 답한다.
호출부는 빈 반환을 "중단"으로 읽으므로, 여기서 예외를 던지면 **전량 수집이 맨 끝에서
실패한다.** 지금까지 걸리지 않은 이유는 `INITIAL_SUBSTANCE_TARGET`(40)이 항상 먼저
루프를 끊었기 때문 — 결함 25·39·40 과 같은 **"그 경로가 돈 적이 없다"** 부류다.
→ 빈 문자열만 소진으로 처리하고, 내용이 있는 문자열은 여전히 스키마 오류다.

### 재수집 실측 (2026-08-27T04:39, job 24)
```
substance_selection  scanned 7,189 / terms 32 / matched 9 / selected 40
job 24 succeeded — 성공 9 / 건너뜀 31 / 실패 0
```
새로 들어온 9건이 **코퍼스가 실제로 문서를 가진 물질**이다.
```
108-88-3  톨루엔        Toluene              ← MSDS PDF 2건 + 사고 1건
7664-93-9 황산          Sulfuric acid        ← MSDS PDF 2건
67-56-1   메틸알코올     Methanol             ← MSDS PDF 1건 ("메탄올"로는 못 찾는다)
7664-41-7 암모니아       Ammonia              ← 사고 3건
7782-50-5 염소          Chlorine             ← 사고 1건
1333-74-0 수소          Hydrogen             ← 사고 1건
79-10-7   아크릴산       Acrylic acid         ← 사고 1건
78-93-3   메틸 에틸 케톤  Methyl ethyl ketone  ← 사고 1건(혼합물 내부)
```
**"메탄올"은 마스터에 없다.** 마스터는 `메틸알코올`로 부른다 — 제목의 영문명
`Methanol` 이 아니었으면 못 찾았다. MSDS 제목까지 본 결정이 값을 한 지점이다.

### 여전히 못 찾는 것 — 지어내지 않고 기록
| 코퍼스가 부르는 이름 | 마스터 |
|---|---|
| 염산 | 그 이름으로 없음 (마스터는 염화수소 계열로 부르는 것으로 보임) |
| 사염화티타늄 / N,N-디메틸포름아미드 / 2-메톡시프로판올 | 마스터에 해당 이름 0건 |
| 폐산(지정폐기물) / PVC 폴리머 / 하이큐 프라서페 PS-220 | 물질명이 아님 |

### 마스터가 40 이 아니라 **49** 인 이유
기존 40건은 재수집으로 **삭제되지 않는다**(수집은 삭제 경로를 갖지 않는다).
새 선정 40 = 매칭 9 + 소스 순서 31 이고, 그 31 은 기존 40 의 앞부분이다.
결과적으로 `substance` 49행. 카드 커버리지에는 이득이고, 다만
`INITIAL_SUBSTANCE_TARGET` 이 마스터 크기의 상한은 아니라는 뜻이다.

### 테스트
신규 `tests/unit/test_substance_selection.py` 27건 + 어댑터 9건.
입력은 **실제 12건 사고 원문과 8건 MSDS 제목 그대로**다 — 혼합물 괄호, 다른
프라임 코드포인트 같은 까다로운 경우는 가정이 아니라 소스가 실제로 담고 있는 것이다.
**단위 487 통과 + 1 스킵, ruff clean.**

### 결함 47 — 파일 문서는 물질에 **연결된 적이 없다** (결함 44 의 나머지 절반)
BR-08 을 고치고 재색인을 걸기 **직전에** 연결 로직을 읽어보고 발견했다. 마스터에
황산이 생겨도 카드는 여전히 비었을 것이다.

```python
# indexing_service._resolve_substances (수정 전)
cas = payload.get("cas_number") or raw.ref.extra.get("cas_number")
if not cas:
    return []          # PDF 는 여기서 항상 끝난다
```
`document_substance` 49행 = **물질 API 레코드 49건의 자기 자신 링크**. MSDS PDF 8건은
한 건도 없다. 카드는 `document_substance` 를 통해서만 MSDS 섹션에 닿으므로,
황산 카드는 같은 코퍼스 안의 황산 MSDS 2건에 **닿을 방법이 없었다.**

식별자는 본문에 있다 — 모든 데이터시트 3항(구성성분)에 CAS 가 적혀 있다.
→ 페이로드에 CAS 가 없으면 **본문을 스캔**하고, **마스터에 있는 CAS 만** 링크한다.
`CAS_PATTERN` 은 느슨하고, 엄격한 필터는 마스터다 (BR-08 매칭과 같은 구조).

**관계는 문서당이 아니라 물질당으로 바뀌었다.** 제목이 그 물질을 부르면 문서 타입의
관계(MSDS→subject), 아니면 `mentioned`. 혼합물 데이터시트는 구성성분 14종을 나열하는데
그중 어느 것의 데이터시트도 아니다 — 한 문서 한 관계로는 이걸 표현할 수 없다.

여기서는 **부분일치가 옳다**. BR-08 선정에서는 부분일치가 예산을 훔치기 때문에
배제했지만, 제목 판정은 `mentioned` 를 문서 타입 관계로 **올려주기만** 한다.

### 건식 시뮬레이션 (재색인 전, u1 에서 배운 절차)
실제 추출 텍스트 8건 × 실제 마스터 49건에 `CAS_PATTERN` 을 그대로 적용했다.
```
20 황산 - 남해화학       CAS 2건 → 7664-93-9 황산      [subject]
21 황산 - 코리아케미칼    CAS 2건 → 7664-93-9 황산      [subject]
22 염산 - 덕산약품       CAS 2건 → (없음)  7647-01-0 은 마스터에 없다
23 톨루엔 - SK케미칼     CAS 1건 → 108-88-3 톨루엔     [subject]
24 톨루엔 - 한화토탈      CAS 1건 → 108-88-3 톨루엔     [subject]
25 메탄올 - Methanex    CAS 1건 → 67-56-1 메틸알코올   [subject]  ← 영문 제목이 살렸다
26 폴리에틸렌 - 한화토탈   CAS 1건 → (없음)
38 하이큐 … (혼합물)     CAS 13건 → 108-88-3 톨루엔    [mentioned] ← 제목 규칙이 일한 곳
                                                    총 6개 링크
```
날짜 오탐은 0이다. `\b\d{2,7}-\d{2}-\d\b` 의 단어 경계가 "2020-12-01" 을 거른다 —
경계 없는 POSIX 정규식으로 재봤을 때 나왔던 `2008-04-0` 류가 사라진다.

**35분짜리 재색인은 가설 검증에 쓰지 않는다**(u1 에서 두 번 낭비하고 배운 것).
BR-08 재수집 직후 걸었던 재색인은 이 결함을 모른 채 시작한 것이라 20/79 에서 중단하고,
결함 47 을 고친 뒤 한 번만 돌렸다.

### 테스트
단위 **496 통과 + 1 스킵** (결함 47 9건 추가), 통합에 MSDS 링크 3건 추가. ruff clean.

---

## CONSTRUCTION — 재색인 검증 + 카드·CAS 종단 (결함 44·47 해소 확인)
**Timestamp**: 2026-08-27T05:40:00Z
**Context**: BR-08 재수집 + 결함 47 수정 후 전 코퍼스 재색인 (job 26, 79/79 성공)

### 코퍼스·불변식
```
문서 79 / 청크 1,649 / 벡터 1,649 / 물질 49 / 동의어 98 / doc_link 56 / chunk cas 324
상한 초과 0 (최장 999 / 1,000 토큰)   BR-30 빈 청크 0   벡터 누락 0   고아 링크 0
```

### 결함 47 — 링크 6건, 건식 시뮬레이션과 **완전히 일치**
```
20 황산 - 남해화학      subject    7664-93-9 황산
21 황산 - 코리아케미칼   subject    7664-93-9 황산
23 톨루엔 - SK케미칼    subject    108-88-3 톨루엔
24 톨루엔 - 한화토탈     subject    108-88-3 톨루엔
25 메탄올 - Methanex   subject    67-56-1 메틸알코올
38 하이큐 … (혼합물)    mentioned  108-88-3 톨루엔     ← 제목 규칙이 일한 곳
```

### 결함 44 — 카드가 채워졌다
| 물질 | 결측 | MSDS |
|---|---|---|
| 황산 (7664-93-9) | **0/7** | ✅ 2건 |
| 메틸알코올 (67-56-1) | **0/7** | ✅ 1건 |
| 톨루엔 (108-88-3) | **1/7** (물리화학적 특성) | ✅ 2건 |
| 암모니아 (7664-41-7) | 6/7 | ❌ 코퍼스에 MSDS 없음 — 정직한 결측 |
| 아이소프로필아민 (75-31-0) | 6/7 | ❌ 변화 없음(원래 그런 물질) |

값마다 출처 문서·URL 이 붙는다(BR-105). `/substances?q=황산` → 카드 P7 렌더 200,
"정보 없음" 0회.

### CAS 종단 (query 81)
```
"CAS 7664-93-9 물질 취급 시 착용해야 하는 보호구는?"
outcome answered / total_ms 4,215 / 검색 277ms / 후보 5
"CAS 번호 7664-93-9인 황산의 작업 환경에서는 적절한 보호 장갑을 착용하도록 요구됩니다."
근거: substance_identity · substance_skin (문서 86, 물질 API 레코드)
```
CAS → 물질 해석은 동작한다. 다만 **근거가 MSDS 8항(보호구)이 아니라 물질 API 의
피부 접촉 항목**이다 — 완전일치 CAS 히트가 상위를 채우고 msds_08 이 밀렸다.
답은 근거가 있고 검증도 통과했으므로 결함으로 올리지 않고 관찰로 남긴다
(무료 티어 하루 ~3질의라 재현 실험 비용이 실제로 든다).

### 결함 48 — **통합 테스트가 실코퍼스를 갉아먹는다**
검증 중 청크 수가 1,649 → 1,648 로 줄어 발견했다.
```python
# test_query_persistence.py — live_chunk_id 는 실제 코퍼스의 첫 청크다
chunk = session.get(ChunkRow, live_chunk_id)
session.delete(chunk)          # 복구 없음. 커밋된다.
```
BR-54 재색인이 청크를 지울 때 인용 링크가 SET NULL 되는지 보는 테스트인데,
**검증 대상인 데이터를 지우면서 검증한다.** 실행할 때마다 코퍼스가 청크 1개와
벡터 1개씩 영구히 줄고, 아무것도 그것을 보고하지 않는다.
→ 전용 `disposable_chunk_id` 픽스처(테스트가 만들고 테스트가 지운다)로 교체.
실행 전후 1,648 → 1,648 확인. 잃었던 청크는 문서 39 부분 재색인으로 복구(1,649).

### ⚠️ 결정 필요 — 공개 코퍼스에 **가상의 MSDS 문서**가 있다
`document 4` 는 실제 문서가 아니다.
```
source_id NULL   source_url https://example.test/a.txt   owner_id NULL(공개)
"제품명: 황산 (Sulfuric acid) / 공급업체: 예시화학 주식회사 / 긴급연락처: 02-000-0000"
16 청크 · 16 섹션 · structured
```
결함 47 로 물질 링크가 생기면서 **황산 카드 7개 항목 전부에 출처로 올라왔다**
(카드 페이지에 `example.test` 7회 노출). 확인 불가능한 URL 을 근거로 제시하는 것은
BR-105·NFR-8 과 정면으로 어긋난다.

- u2 답변이 이 문서를 인용한 적은 **0회**다 (전체 인용 46건 중).
- 삭제하면 황산 카드는 **0/7 → 2/7 결측** (GHS·유해위험문구는 이 문서만 갖고 있다).
- 데이터 삭제는 되돌리기 어려우므로 **사용자 승인 없이 실행하지 않는다.**

### 가상 MSDS 문서 삭제 (2026-08-27T06:10Z, 사용자 승인: "삭제 해주세요")
```
document 4  https://example.test/a.txt  /data/originals/fix-check/doc-a.txt
  → 문서 1 · 청크 16 · 섹션 16 · 추출텍스트 1 · 물질링크 1 · 인용 0
DB 삭제(BR-56 캐스케이드) + 보관 원본 파일·디렉터리 삭제
```
`data/originals/fix-check/` 는 2026-08-20 u1 Build & Test 때 수동 확인용으로 만든
것이 정리되지 않고 남아 공개 코퍼스에 섞여 있었다.

```
문서 79 → 78 / 청크 1,649 → 1,633 / 벡터 1,633
example.test 문서 0 · source 없는 문서 0 · 고아 섹션 0 · 고아 청크 0 · 벡터 누락 0
카드 페이지 example.test 노출 7회 → 0회
```

**황산 카드는 예고대로 0/7 → 2/7 결측**(GHS·유해위험문구). 근거를 잃은 것이 아니라
**애초에 근거가 아니었던 것**이 빠졌다.

### 남은 결측의 진짜 원인 — MSDS PDF 2건이 구조화에 실패했다
```
20 황산 (SULFURIC ACID) - 남해화학   unstructured  섹션 0   ← 황산 GHS 가 여기 있다
24 톨루엔 (Toluene) - 한화토탈        unstructured  섹션 0   ← 톨루엔 물리화학 특성
나머지 6건                          structured   섹션 14~16
```
섹션이 0이면 `_MSDS_SECTION_FOR` 가 닿을 곳이 없어 카드 항목을 채우지 못한다.
황산 GHS 2/7 결측과 톨루엔 물리화학 1/7 결측은 **같은 원인 하나**다.
PDF 파싱 성공률은 R-2 로 이미 등록된 위험이고, 8건 중 6건(75%)이 구조화됐다.
u3 범위 밖이므로 결함으로 올리지 않고 관찰로 남긴다.

### 최종 상태
```
단위 496 통과 + 1 스킵 / 통합 25 통과 + 1 스킵 / ruff clean
코퍼스 78문서 / 1,633청크 / 1,633벡터 / 물질 49 / 동의어 98 / doc_link 55
카드  메틸알코올 0/7 · 톨루엔 1/7 · 황산 2/7 · 암모니아 6/7(MSDS 없음)
```

---

## CONSTRUCTION — Build and Test (u3-substance-card)
**Timestamp**: 2026-08-27T07:00:00Z
**Deliverables**: `build-and-test/u3-build-and-test-summary.md`, `u3-test-instructions.md`

### 결과
```
빌드 4컨테이너 healthy / 마이그레이션 0002_query (u3 신규 테이블 0개)
단위 496 통과 + 1 스킵 · 통합 25 통과 + 1 스킵 · ruff clean
NFR-3 카드 P95  예산 1,000ms  실측 47.4ms  ✅ (21배 여유)
NFR-28          도달 불가 호스트로 단위 496건 전부 통과  ✅
BR-102·105·106  카드 49건 전수 위반 0
BR-107          카드 49건 조회 전후 citation_snapshot 51 → 51
보안            반사 XSS·주입 6종 전부 이스케이프, 원문 반사 0
```

### 전수 검사로 바꾼 이유
카드 40건이 전부 비어 있던 결함 44 를 **첫 번째 물질 하나를 보는 통합 테스트가
통과시켰다.** 그래서 이 단계의 규칙 검증은 49건 전수다.
```
결측 분포 {0: 1, 1: 1, 2: 1, 6: 44, 7: 2}
```

### ⚠️ 발견 — BR-31a 와 BR-104 가 짧은 문서에서 충돌한다
7/7 결측 2건의 원인이 서로 다르다.
```
메틸 에틸 케톤 (78-93-3)   출처 레코드에 응급조치가 비어 있다      → 정직한 결측
4-tert-뷰틸벤조산 (98-73-7) 섹션 7개에 내용이 있는데 카드가 못 읽는다 → 아래
```
```
문서 69  structured  섹션 7  청크 1  section_id NULL
문서 86  structured  섹션 7  청크 7  섹션별 1개
```
BR-31a: 섹션 중앙값이 `MIN_CHUNK_TOKENS`(20) 미만이면 문서를 섹션 없는 청크 하나로
접는다. 카드는 `section_code` 로만 항목을 찾으므로(BR-104) **접히는 순간 그 문서의
내용 전부가 카드에서 사라진다.**

전 코퍼스 영향: 섹션 2개 이상인데 섹션 있는 청크가 0개인 문서 **13건**
= incident_data 12(카드가 읽지 않는 타입, 영향 없음) + ncis_substance 1(**카드 1/49**).

**결함으로 올리지 않는다.** 코드가 규칙을 어긴 것이 아니라 두 규칙의 경계가 만난
것이고, 어느 쪽으로 갈지는 설계 결정이다(요약 5절에 선택지 A/B/C).

### 미충족 (요약 8절)
FR-26 UN·이명 데이터 없음 / BR-08 ② 데이터 없음 / FR-24 는 49건 중 3건에서만 충족
(MSDS 보유 물질이 3건) / MSDS PDF 구조화 6-8건(75%) / BR-31a↔BR-104 1건.

**FR-24 를 "충족"이라고 쓰지 않는다.** 카드 구조는 완성됐고 채울 문서가 3건뿐이다 —
코드 문제가 아니라 코퍼스 문제이며 늘리는 방법도 안다(MSDS 추가 수집).

### Ready for Operations — 조건부. **승인 대기**

---

## CONSTRUCTION — Build and Test (u3-substance-card) : **APPROVED**
**Timestamp**: 2026-08-27T07:20:00Z
**승인 발언**: "승인. u4 진행해주세요"

u3 완료. 남은 미충족은 전부 **데이터 제약**이며 코드 문제가 아니다 —
FR-26 UN·이명(출처에 필드 없음), BR-08 ②(출처에 필드 없음),
FR-24(MSDS 보유 물질 3건), MSDS PDF 구조화 6/8, BR-31a↔BR-104(카드 1/49).

---

## CONSTRUCTION — Functional Design 계획 (u4-evaluation)
**Timestamp**: 2026-08-27T07:30:00Z
**산출물**: `plans/u4-evaluation-functional-design-plan.md` — **FQ5-1~14, 답변 대기**

### 이 유닛의 지배적 제약은 무료 티어다 (실측)
`llm_call` 전수:
```
answered              15건   질의당 5.25 호출  (생성 1 + 문장별 검증 ~4, BR-86a)
refused_low_relevance 33건   질의당 0.03 호출  ← 1단계 거부는 LLM 이전에 결정된다
```
```
무료 티어 모델당 하루 20 요청
FR-36 의 30문항 중 답변형 25건 = 131 호출 = 7일
50문항이면 42건 답변형 = 11일 → 한 번 돌리는 데 2주
```
**튜닝으로 줄일 수 있는 값이 아니라 구조다.**

### 그러나 지표의 절반은 LLM 이 필요 없다
```
Recall@k · MRR · 거부 정확도   →  LLM 0 호출. 30문항 전체를 매일 수초에 무료로
정답률 · 인용 정확도 · 충실도   →  답변이 필요하다
```
근거는 u2 실측이다 — 결함 27(RRF 를 임계값으로 읽음)·결함 45(완전일치를 코사인이
뒤집음)는 **둘 다 LLM 앞단**에서 생겼고 앞단 지표로 잡힌다.
→ FQ5-5 권장안: `--retrieval-only`(매일)과 `--full`(재개 가능)의 2계층 분리.

### 코퍼스가 골든셋에 거는 제약
```
law_api        1,173청크  ← 가장 풍부
ncis_substance   324청크
msds_pdf         124청크  ← MSDS 기반 질문은 황산·톨루엔·메틸알코올 3물질에서만
incident_data     12청크
거부형 질문                무제한
```

### 명시적으로 배제한 선택지와 이유
| 선택지 | 배제 이유 |
|---|---|
| 평가 중 검증(BR-87) 끄기 — 호출 5.25→1 | **아무도 실행하지 않는 파이프라인을 측정**하게 된다. DD-22 위반. 결함 37 이 검증도 품질의 일부임을 보였다 |
| 정답 근거를 청크 ID 로 표기 | 재색인 한 번에 골든셋 전체 무효. 이 프로젝트는 이미 4회 재색인했다 |
| 인용 정확도를 문장별 심판으로 판정 | 문항당 5~9 호출 추가 → 무료 티어에서 실행 불가 |
| 골든셋 LLM 자동 생성 | 평가 대상 모델이 정답을 만드는 구조 |
| 절대 임계값(95%/5%) 단독 회귀 판정 | 아직 한 번도 측정된 적이 없다. 첫 실행이 그 아래면 CI 영구 빨간불 |

**u4 는 신규 테이블이 필요하다** — 0002 이후 첫 마이그레이션(`0003_evaluation`).

---

## CONSTRUCTION — Functional Design (u4-evaluation) : 산출물 생성
**Timestamp**: 2026-08-27T08:10:00Z
**승인 발언**: "권장안대로 진행" — FQ5-1~14 전부 권장안

### 산출물 5종
```
construction/u4-evaluation/functional-design/
  domain-entities.md      evaluation_run · evaluation_item · 마이그레이션 0003_evaluation
  business-rules.md       BR-111 ~ BR-130
  business-logic-model.md C44~C48 · S5 · 워크플로 W15~W18 · CLI 종료코드
  evaluation-metrics.md   지표별 계산식·비용·한계
eval/golden-set.yaml      골든셋 초안 30문항
```

### 골든셋 초안 — 실 코퍼스 검증 통과
LLM 을 쓰지 않고 SQL 조회로 만들었다. 평가 대상 모델이 정답을 만들면 회귀 감지력이
원리적으로 떨어진다.
```
문항 30건  law 10 / substance 8 / msds 4 / incident 3 / refusal 5
기대       answer 25 / refusal 5
DB 대조 검증 (소스·문서·섹션 실재 확인)  실패 0건
```
문서는 `source` + `external_id` 로 가리킨다 — 청크 ID 는 재색인 한 번에 무효가 되고
이 프로젝트는 이미 네 번 재색인했다. 사고 3문항은 BR-31a 로 섹션이 접혀 있어
문서 단위로 채점한다(BR-113).

거부 5문항 중 **ref-04(카드뮴)·ref-05(벤젠)** 가 핵심이다. 코퍼스 밖 잡담을 거부하는
것은 쉽고, **도메인 안이지만 근거가 없는 질문**을 거부하는 것이 SC-3 이 요구하는 것이다.
ref-05 는 마스터에 "1-클로로-2,4-다이나이트로벤젠"이 있어 결함 45(완전일치가 코사인을
뒤집음)와 같은 부류의 회귀를 노린다.

### 비용 구조가 설계를 결정했다
```
지표 계산     30문항 전체     LLM 25 호출 (심판, 정답률+충실도 동시)
답변 생성     25문항          LLM 131 호출  ← 비용의 84%
```
→ `--retrieval-only`(LLM 0, 수초, 매일)와 `--full`(재개 가능)의 2계층 분리.
Recall@k·MRR·거부 정확도는 **LLM 앞단**에서 결정되고, u2 결함 27·45 가 바로 거기서
생겼다.

### 명시적으로 기록한 근사 (BR-125)
인용 정확도를 "정답 근거 섹션 소속"으로 판정한다. NFR-5 의 문자 그대로는 문장마다
심판 호출이 필요해 무료 티어에서 실행 불가능하다. **이 근사는 과대평가 방향이다** —
정답 근거를 인용했지만 그 문장이 다른 내용을 말할 수 있다. 리포트에 그렇게 적는다.
충실도가 다른 각도에서 같은 것을 보므로, 두 지표가 갈리면 사람이 본다.

### 회귀 임계값은 초안이다
첫 기준선이 생기기 전까지 실측이 없다. 실측 없는 임계값은 결함 34(예산에서
타임아웃을 유도했다가 성공한 호출을 죽임)와 같은 종류의 실수다. 첫 `--full` 실행 후
재검토한다. 다만 **거부 정확도만 허용 하락 0** — 30문항에 5건뿐이라 한 건이 0.20 이고,
SC-3 은 안전 도메인의 핵심 약속이다.

**다음: 사용자의 골든셋 검토 (R-5) → Code Generation**

---

## CONSTRUCTION — Code Generation (u4-evaluation) + 결함 49
**Timestamp**: 2026-08-28T12:30:00Z
**승인 발언**: "그대로 진행" (골든셋 검토 생략)
**산출물**: `u4-evaluation/code/{code-summary,traceability}.md`, 신규 12 / 수정 8

### 마이그레이션 `0003_evaluation` 적용 완료
```
alembic_version  0002_query → 0003_evaluation
evaluation_run · evaluation_item 생성.  u1~u3 테이블 변경 0
```

### 설계 문서 대비 정정 2건
1. **`RetrievalConfig` 는 존재하지 않는다.** `services.md` 가 만들어진 적 없는 타입을
   가리켰다. 설정 스냅샷은 `Settings` 에서 뽑는다 — 없는 타입을 지금 만들면 u2 를
   건드려야 하고 이 유닛에 그럴 이유가 없다.
2. **`QueryResult` 가 검색 결과를 내보내지 않았다.** Recall@k 는 인용된 것이 아니라
   검색된 것을 본다. S5 가 `retrieve()` 를 한 번 더 부르면 **지표가 답변과 다른 실행을
   재게 되므로**, `QueryResult.retrieved` 를 추가했다(가산적, 동작 무변경).

### `_NoLLM` — 설정에 기대는 규칙은 규칙이 아니다
BR-119(`--retrieval-only` 는 LLM 0)를 `llm=None` 으로 구현하면 "`ENTITY_LLM_ENABLED`
가 false 인 동안"만 참이다. 호출되면 즉시 터지는 가드 객체를 넘긴다 — 규칙이 깨지면
청구서가 아니라 테스트에서 드러난다.

### 첫 실측 — `evaluate --retrieval-only` (실행 2)
```
문항 30 / 채점 30 / 실패 0 / LLM 호출 0        (수초)
Recall@5   0.700     Recall@10  --      MRR  0.546
거부 정확도  0.400     오거부율     0.000
```

### 결함 49 — Recall@10 은 구조상 측정할 수 없다 (부류 ②)
첫 실행에서 Recall@5 와 Recall@10 이 **완전히 같았다.**
```sql
select jsonb_array_length(retrieved) from evaluation_item;  -- 30건 전부 5
```
파이프라인은 `final_top_k=5` 개의 근거만 내보낸다. 5건짜리 목록의 Recall@10 은
**이름만 다른 Recall@5** 이고, BR-124 가 노린 "두 값의 차이로 순위 문제를 진단한다"는
**차이가 날 수 없는 두 수를 비교하는 일**이 된다. 결함 26(BR-72 가 공유 세션에서
성립 불가)과 같은 부류다.
→ 후보 깊이를 실측해 `depth < 10` 이면 `None` 을 내고 이유를 리포트에 적는다.
같은 수를 두 이름으로 내는 것보다 안 내는 것이 정직하다.

### 거부 정확도 0.400 — u4 가 존재하는 이유
```
ref-01 날씨 · ref-02 파이썬        ✅ 거부
ref-03 두통 의료 진단              ❌ 답변
ref-04 카드뮴 급성 독성            ❌ 답변
ref-05 벤젠 응급조치               ❌ 답변
```
FD 에서 예고한 그대로다 — 코퍼스 밖 잡담은 쉽고 **도메인 안이지만 근거가 없는 질문**이
어렵다. 1단계 거부는 코사인 0.50 임계값 하나로 판정하는데(BR-73), "벤젠 응급조치"는
다른 물질의 응급조치 섹션과 충분히 가깝다.
**u4 의 결함이 아니라 u4 가 발견한 품질 사실이다.**

### 유형별 Recall@5 (답변형 25)
```
사고   3/3     법령 7/10 (law-07·08·09 = MSDS 작성·게시·공정안전보고서)
MSDS  3/4     물질 3/8  (sub-02·03·05·06·08)
```
**CAS 번호로 물으면 전부 적중(sub-01·04·07), 물질명으로 물으면 대부분 실패.**
BR-38 완전일치는 동작하고 물질명 → 노출경로 섹션 경로가 약하다.
**기준선 없는 상태의 튜닝은 측정이 아니라 추측**이므로 지금 손대지 않는다 —
그것이 u4 를 먼저 만든 이유다.

### 테스트
```
단위 559 통과 + 1 스킵  (496 → +63)
통합  39 통과 + 1 스킵  (25 → +14)
ruff clean
```

### ⚠️ 아직 한 번도 실행되지 않은 것
`evaluate --full` 이 돌지 않았다(131 호출 = 7일). 따라서 **심판(C47)·정답률·인용
정확도·할당량 재개·회귀 판정 종단이 전부 미검증**이다. 코드는 있고 실행 증거가 없다.

u1·u2 에서 "테스트는 초록불인데 그 경로가 한 번도 돈 적이 없다"가 결함 25·39·40·46·47
다섯 건을 만들었다. **지금 같은 자리에 서 있다는 것을 기록해 둔다** —
Build & Test 의 첫 과제가 이것이다.

---

## CONSTRUCTION — Build and Test (u4-evaluation) + 결함 50~53
**Timestamp**: 2026-08-28T13:20:00Z
**산출물**: `build-and-test/u4-build-and-test-summary.md`, `u4-test-instructions.md`

### Code Generation 때 "실행 증거가 없다"고 적은 4건이 전부 실행됐다
심판(C47) · 정답률·충실도 · 인용 정확도 · 할당량→`partial`→재개.

### 🔴 전제 정정 — 병목은 생성이 아니라 심판이다
FD 전체가 "무료 티어 = 모델당 하루 20"에서 나왔다(7일, 2계층 분리, 재개).
```
gemini-3.1-flash-lite   answer 21 + verify 47 = 68 호출   할당량 오류 없음
gemini-3.6-flash (심판)  20번째에서 429                     20/일 확인
```
"20/일"은 심판 모델에는 맞고 답변 모델에는 **틀렸다.** u2 에서 받은 오류 메시지
하나를 모든 모델에 일반화한 것이 원인이다.

| | 문서 가정 | 실측 |
|---|---|---|
| 병목 | 답변+검증 131 호출 | **심판 25 호출** |
| 전체 1회 | 7일 | **2일** |
| 질의당 답변 비용 | 5.25 | **3.4** |

**설계는 옳고 근거만 바뀐다.** 2계층 분리·재개는 한도가 20이든 68이든 필요하다.
BR-122 도 유지되지만 **이유가 반대다** — 심판이 답변을 잠식하는 게 아니라
**답변이 심판을 굶긴다.** BR-118·BR-122 에 정정을 적어 넣었다.
u2 결함 34(예산에서 타임아웃을 유도)와 같은 부류다: 측정하지 않은 숫자로 세운 설계.

### 실측 — `--retrieval-only` (실행 2, 30문항, LLM 0, 수초)
```
Recall@5 0.700 / MRR 0.546 / 거부 정확도 0.400 / 오거부율 0.000
사고 3/3 · 법령 7/10 · MSDS 3/4 · 물질 3/8
CAS 번호 질의 3/3, 물질명 질의 3/8   ← BR-38 완전일치는 동작, 물질명 경로가 약하다
거부: 날씨·파이썬 ✅ / 의료·카드뮴·벤젠 ❌   ← 도메인 안 근거 없는 질문이 샌다
```

### 실측 — `--full` (실행 10, 21/30 채점)
```
정답률 0.762 / 인용 정확도 0.489 / 충실도 1.000 / 오거부율 0.045
```
**충실도 1.000 — 틀린 답 5건이 전부 `faithful: true` 였다.**
근거에 충실했는데 엉뚱한 근거를 받은 것이다. 심판의 말:
```
law-07  "…근거 본문의 내용(공단에 제출)을 충실히 반영하고 있어 충실성은 참이지만,
         기대 답변의 핵심 기관명(고용노동부장관)과 다른 기관을 제시했으므로 정확성은 거짓"
```
**NFR-6(위반 ≤5%)은 측정 범위에서 0% 로 충족.** 그리고 이 실행이 말하는 것은 하나다 —
**실패 원인은 생성이 아니라 검색이다.**

**인용 정확도 0.489 는 NFR-5(≥95%)에 크게 미달**한다. 두 가지를 같이 읽어야 한다:
BR-125 근사는 **과대평가 방향**이라 참값은 그 이하이고, 동시에 이 지표는 Recall 0 인
문항에서 0이 될 수밖에 없어 **검색 성능에 종속**돼 있다. 인용 로직이 아니라 검색이
길이다.

> 부분 실행의 지표를 전체와 비교하면 안 된다 — 채점된 21문항에 거부형이 하나도 없다
> (골든셋 뒤에 몰려 있다). `partial` 을 기준선으로 승격하지 않는 이유이기도 하다.

### 할당량 → partial → 재개 → 종료코드 4 (설계대로)
```
--full     20문항 → 심판 429 → msds-03 quota_exhausted → partial + 재개 안내
--resume   msds-03 부터 이어서 1문항 → 다시 429 → exit=4
종료코드 실측: --list 0 / 없는 골든셋 2 / 코퍼스 불일치 2 / 모드 미지정 3 / partial 4
```
**4가 1이 아닌 것이 핵심이다.** 할당량 소진은 품질 문제가 아니고, 실패로 취급하면
무료 티어에서 CI 가 항상 빨간불이 된다.

### 결함 50~53
| # | 결함 | 부류 |
|---|---|---|
| 50 | **비용 집계가 84%를 빠뜨렸다** — `llm_calls` 가 심판 1건만 세고 생성·검증을 안 셌다(기록 1 / 실제 3) | 틀린 신호를 읽음 |
| 51 | **심판 호출이 추적되지 않았다** — BR-95 를 심판만 벗어나 `/usage` 가 과소 보고 | 규칙 예외를 몰랐음 |
| 52 | **`문항 21`** — 골든셋 크기가 아니라 기록된 행 수를 표시 | 틀린 신호를 읽음 |
| 53 | **통합 테스트가 기준선을 남겼다** — 실행 10 이 테스트가 승격한 실행과 비교돼 `incomparable` | 자초 (결함 48과 동형) |

**결함 50·51 은 둘 다 "비용"이고, 비용은 이 유닛 설계 전체의 근거였다.**
전제 오류까지 합치면 u4 는 **자기가 서 있는 숫자를 세 군데에서 잘못 알고 있었다.**
실행해 보지 않았으면 셋 다 몰랐다.

결함 53 은 결함 48 과 같은 모양 — **테스트가 자기가 검증하는 상태를 조용히 바꾼다.**
이번엔 데이터가 아니라 기준선이었다. 컨텍스트 매니저로 원복하고, 테스트가 만든
실행에는 `note='integration-test'` 를 붙인다.

### 테스트
```
단위 573 통과 + 1 스킵  (496 → +77)    통합 40 통과 + 1 스킵  (25 → +15)   ruff clean
```

### Ready for Operations — 조건부. **승인 대기**
남은 제약: 심판 20/일(전체 1회 = 2일) · 인용 정확도 0.489 · 거부 정확도 0.400 ·
기준선 미승격(회귀 판정 아직 미작동) · BR-124 Recall@10 측정 불가(결함 49).

---

## CONSTRUCTION — Build and Test (u4-evaluation) : **APPROVED**
**Timestamp**: 2026-08-29T00:10:00Z
**승인 발언**: "승인. 내일 재개하고 완주하면 기준선 승격해줘"

u4 완료. 남은 지시 두 건을 이어서 수행한다.
1. 심판 할당량 회복 후 `--resume 10` 으로 완주
2. 완주하면(`succeeded`) 실행 10 을 기준선으로 승격 (BR-129 — 사람의 명시적 지시)

> BR-129 는 "기준선은 사람이 올린다"이고, 이 승격은 그 조건을 만족한다 —
> 자동 승격이 아니라 **완주를 조건으로 한 사람의 사전 지시**다.
> 다만 `partial` 이면 승격하지 않는다. 부분 실행은 문항 구성이 편향돼 있다
> (채점된 문항에 거부형이 없었다).

---

## OPERATIONS — 실행 10 완주 시도 (2026-08-29) + 결함 54
**Timestamp**: 2026-08-29T05:00:00Z
**지시**: "내일 재개하고 완주하면 기준선 승격해줘"

### 결과 — 완주하지 못했다. **기준선 승격은 하지 않는다.**
```
--resume 10   inc-01 채점 (심판 1회 성공) → inc-02 에서 다시 429
실행 10 — partial   골든셋 30 / 채점 23 / 미채점 7
Recall@5 0.609 / MRR 0.407 / 정답률 0.773 / 인용 정확도 0.513 / 충실도 1.000
```
지시는 **"완주하면"** 이 조건이었고 완주하지 못했다. `partial` 을 승격하면 문항
구성이 편향된 실행이 기준선이 된다 — 미채점 7건에 **거부형 5건이 전부 들어 있다.**

### 할당량 창은 KST 자정에 리셋되지 않는다 (실측)
```
08-28 21:42~21:55 KST   심판 ~21회 성공 → 429
08-29 13:40    KST   심판  1회 성공 → 429
```
KST 로 하루가 바뀌었는데 **1회만 열렸다.** 창이 KST 자정 정렬도 아니고 완전한
롤링 24시간도 아니다(어제 첫 호출은 16시간 전이다).

**규칙을 단정하지 않는다 — 이 데이터로는 알 수 없다.** 세 번째로 같은 자리에 왔다:
"모델당 하루 20"도 측정 없이 일반화한 것이었고(어제 정정), 이번에는 리셋 시점을
모른다는 사실 자체가 측정 결과다. Google 무료 티어 일일 한도가 태평양 시간 자정
기준이라면 **16:00 KST 경**이 되지만, 그것은 가설이고 실측이 아니다.

**남은 작업은 심판 2회뿐이다** — inc-02·inc-03. 거부형 5건은 심판을 부르지 않는다.

### 결함 54 — 재채점이 타임스탬프를 옮기지 않았다
```
inc-01   08-29 에 채점됐는데 evaluated_at 은 08-28 을 가리킨다
```
`server_default=now()` 는 INSERT 에만 걸린다. 재개가 행을 UPDATE 하므로, 할당량으로
실패한 날짜가 그대로 남는다. **시간에 따른 변화를 귀속시키는 것이 이 유닛의 목적**인데
측정 시점을 잘못 적는 것은 사소한 문제가 아니다.
→ `record()` 가 매번 `evaluated_at` 을 갱신한다. 통합 테스트 1건 추가.

### 부수 확인 — 결함 51 수정이 실환경에서 동작한다
```
llm_call   judge | gemini-3.6-flash | ok=t     ← 성공한 심판 호출
           judge | gemini-3.6-flash | ok=f | QuotaExhaustedError
```
심판 호출이 성공·실패 모두 `llm_call` 에 남는다. 어제까지는 한 줄도 없었다.

### 테스트
통합 **41 통과 + 1 스킵**, 단위 573 + 1 스킵, ruff clean.

---

## OPERATIONS — 실행 10 완주 + 기준선 승격 + 결함 55
**Timestamp**: 2026-08-29T07:15:00Z
**지시**: "16시 이후에 재개해줘" (선행: "완주하면 기준선 승격해줘")

### 완주 — `succeeded` 30/30
16:10 KST 재개, 심판 할당량이 열려 있었다. **가설이 맞았다** — 태평양 시간 자정
(16:00 KST) 경계였다. 다만 이번에도 단정하지 않는다: 두 점(13:40 실패, 16:10 성공)
사이 어디인지만 안다.

```
실행 10 — succeeded    골든셋 30 / 채점 30 / 미채점 0 / 실패 0 / LLM 호출 40
Recall@5 0.700 / MRR 0.546 / 정답률 0.792 / 인용 정확도 0.553 / 충실도 1.000
거부 정확도 0.600 / 오거부율 0.040
```

### 유형별 (기준선이 될 숫자)
| 유형 | Recall@5 | MRR | 인용 정확도 | 정답 |
|---|---|---|---|---|
| 사고 | **1.000** | 1.000 | 1.000 | 3/3 |
| 법령 | 0.700 | 0.412 | 0.650 | 8/10 |
| MSDS | 0.750 | 0.500 | 0.500 | 2/3 |
| 물질 | **0.375** | 0.281 | 0.285 | 6/8 |
| 거부 | 1.000 | 1.000 | — | — |

**물질 유형이 가장 약하다.** CAS 번호는 맞히고 물질명이 안 되는 것과 같은 이야기다.

### 검증이 임계값이 놓친 거부를 하나 잡았다
```
                검색전용(실행 2)      전체(실행 10)
ref-04 카드뮴    answered            refused_unsupported   ← BR-87 2단계 검증
```
거부 정확도 **0.400 → 0.600**. 1단계 거부(코사인 0.50)가 통과시킨 것을 문장별 근거
검증이 걸러냈다 — BR-76("아무 문장도 살아남지 못하면 그것은 거부다")이 설계대로
동작한 실측이다. u2 결함 37 이 이 경로를 죽였을 때 모든 답변이 비었던 것과 같은
경로가, 이번에는 옳게 작동했다.

### 기준선 승격 (BR-129)
```
safeenv evaluate --promote 10      →  실행 10 (full, succeeded, 30문항)
```
지시가 "완주하면"이었고 완주했다. 어제 `partial` 일 때는 승격하지 않았다.

### 결함 55 — 기준선이 하나면 매일 돌리는 가드가 영원히 동작하지 않는다
승격 직후 `--retrieval-only` 를 돌려보고 발견했다.
```
실행 48 vs 기준선 10
  Recall@5   0.700 → 0.700   +0.000     ← 같은 검색을 두 번 재면 같은 수가 나온다
  거부 정확도  0.600 → 0.400   -0.200  ← 회귀
  ⚠ answer_model / judge_model / prompt_versions 가 기준선과 다릅니다
판정: incomparable
```
검색전용 실행은 답변 모델·심판 모델·프롬프트 버전을 기록하지 않는다. `full` 기준선과
비교하면 **항상 세 필드가 달라 매번 `incomparable`** 이고, 2계층 분리가 존재하는
이유인 **매일의 회귀 가드가 단 한 번도 발화하지 못한다.**

거부 정확도의 -0.200 도 회귀가 아니다 — 2단계 검증이 없는 것뿐이다.
**다른 양의 파이프라인을 뺄셈한 결과**다.

→ 기준선을 **모드별로** 둔다. `latest_baseline(mode)`, 승격도 같은 모드 안에서만
배타적이다. 검색전용 기준선과 전체 기준선은 서로 다른 것을 재므로 둘 다 필요하다.

부수로 결함 53 의 원복 헬퍼도 모드별로 고쳤다(기준선이 둘이 되면서 한쪽만 복구했다).

### 남은 것
- **검색전용 기준선이 없다.** `full` 기준선(실행 10)은 섰지만 매일의 가드는 아직
  비교 대상이 없다. 후보는 실행 73(30문항, Recall@5 0.700, MRR 0.546).
  **BR-129 대로 사람이 승격한다** — 자동으로 올리지 않는다.
- 테스트가 만든 실행이 이력에 다수 남아 있다(라벨링됨).

### 테스트
단위 **573 통과 + 1 스킵** / 통합 **42 통과 + 1 스킵** / ruff clean.

---

## CONSTRUCTION — Functional Design 계획 (u5-account-upload)
**Timestamp**: 2026-08-29T08:00:00Z
**산출물**: `plans/u5-account-upload-functional-design-plan.md` — **FQ6-1~14, 답변 대기**

### 착수 전 실측 — 문서가 약속한 것이 실제로 있다
설계 문서가 "스키마 변경·검색 시그니처 변경 없이 격리를 도입한다"고 적었고,
**확인했더니 사실이다.**
```
owner_id 컬럼:  document · chunk · query_log      (전부 항상 NULL)
apply_scope():  owner_id IS NULL  OR  owner_id = :caller     ← u1 이 이미 구현
Scope:          모든 검색 메서드의 필수 인자 (DD-19)
```
**FR-28 의 질의 경로는 이미 구현되어 있다.** u5 가 할 일은 `owner_id` 에 값을 넣는
것이지 격리 로직을 만드는 것이 아니다.

> u4 에서는 `RetrievalConfig` 가 문서에만 있고 코드에 없었다. 이번은 반대다.
> 어느 쪽이든 **시작 전에 확인한다**는 절차가 같다.

### 없는 것도 확인했다
```
인증 의존성 0   jwt·bcrypt·argon2·passlib 어느 것도 pyproject 에 없다
사용자 테이블 0
FR-34 동의 기록   u2 는 면책 상시표시(FR-35)만 구현. "1회 동의·기록 저장"은 미구현
라우터 인증 훅 0  get_session() 만 있다
```
u2 의 `google-genai` 이후 **첫 신규 런타임 의존성**이 들어온다.

### u4 평가가 흔들릴 경로는 없다 — 확인
```
EvaluationService: Scope(owner_id=None) 2곳(retrieve·answer), 다른 형태 없음
```
업로드 문서가 골든셋 지표에 섞이지 않는다. FD 에서 규칙으로 고정한다.

### 이 유닛의 성격
Q27=A(Security Baseline 활성)가 겨냥한 유닛이다 — 비밀번호·토큰·업로드·격리를
한꺼번에 다룬다. 그래서 **정직하게 범위를 좁히는 결정**이 많다.

FQ6-7("악성 파일 차단"의 범위)이 대표적이다. 확장자·MIME 만 보는 것은 검증이라
부를 수 없고, 안티바이러스 연동은 컨테이너와 정의 파일 갱신을 운영에 얹어 NFR-29
(단일 명령 기동)와 충돌한다. 권장안은 **매직 바이트·파서 성공·JavaScript/
EmbeddedFile/Launch 액션 거부**까지이고, **이것을 "악성 파일 차단 완료"라고 쓰지
않는다** — 무엇을 보고 무엇을 안 보는지 적는다. 가장 큰 방어는 이 시스템이 업로드
파일을 **실행하지 않고 텍스트만 추출**한다는 사실이다.

FQ6-12(익명 질의 유지)도 같은 성격이다. 요구사항 어디에도 "질의에 로그인이
필요하다"는 말이 없으므로 **지금 동작하는 공개 질의를 없애지 않는다.** 대신
익명 질의 이력은 아무의 이력도 아니라는 사실을 결함이 아니라 설계로 적는다.

---

## OPERATIONS — 검색전용 기준선 승격, 매일 가드 가동
**Timestamp**: 2026-08-29T08:40:00Z
**지시**: "처리해줘"

```
safeenv evaluate --promote 73     →  실행 73 (retrieval_only, succeeded, 30문항)

기준선 현황
  10  full            succeeded  30문항
  73  retrieval_only  succeeded  30문항
```

### NFR-26 회귀 판정이 처음으로 실제 동작했다
```
실행 74 vs 기준선 73
  Recall@5    0.700 → 0.700   +0.000
  MRR         0.546 → 0.546   +0.000
  거부 정확도   0.400 → 0.400   +0.000
  오거부율      0.000 → 0.000   +0.000
판정: ok        exit=0
```
`incomparable` 경고가 하나도 없다 — 같은 모드, 같은 모델·프롬프트·설정·코퍼스다.
**결함 55 를 고치기 전에는 이 자리에 세 줄의 경고와 `incomparable` 이 있었다.**

같은 검색을 두 번 재서 같은 수가 나온다는 것도 함께 확인됐다(실행 73 → 74,
그리고 실행 10 의 전체 실행과도 Recall@5·MRR 일치). 지표가 재현 가능하다는
뜻이고, 그것이 회귀 판정의 전제다.

회귀를 **감지하는** 쪽 경로는 단위 테스트가 덮는다
(`test_a_large_drop_is_a_regression`, `test_a_single_missed_refusal_is_a_regression`).
실환경에서 인위적으로 품질을 떨어뜨려 확인하지는 않았다 — 설정을 바꾸면
`config` 가 달라져 `incomparable` 이 되므로(설계대로), 그 방법으로는 회귀를
재현할 수 없다. **기록해 둔다.**

### u4 의 남은 미결 항목이 닫혔다
```
✅ full 기준선            실행 10  (2026-08-29 승격)
✅ retrieval_only 기준선   실행 73  (2026-08-29 승격)
✅ 매일의 회귀 가드         동작 확인 (exit 0 / 판정 ok)
```

---

## CONSTRUCTION — Functional Design (u5-account-upload) : 산출물 생성
**Timestamp**: 2026-08-30T01:00:00Z
**승인 발언**: "권장안대로 진행" — FQ6-1~14 전부 권장안

### 산출물 4종
```
construction/u5-account-upload/functional-design/
  domain-entities.md       user_account(E21) · document 업로드 컬럼 3 · 0004_account
  business-rules.md        BR-131 ~ BR-152
  business-logic-model.md  C51~C55 · S6·S7 · 워크플로 W19~W24
  frontend-components.md   P8 로그인·가입 / P9 문서 관리 / P10 질의 이력
```

### 이 유닛의 성격 — 격리를 만드는 것이 아니라 값을 넣는 것
```
로그인 → 토큰 → 인증된 사용자 → Scope(owner_id=id) → 기존 검색·색인 경로
                                    ↑ 여기서 값이 생긴다
```
`apply_scope`·`Scope` 필수 인자·`DocType.USER_UPLOAD` 는 u1 이 이미 넣어 두었다.
따라서 위험은 "새 격리 코드가 틀릴 위험"이 아니라 **"어딘가에서 `Scope` 를 안
만들거나 잘못 만들 위험"** 이고, C55 와 BR-145 가 그 하나를 겨냥한다.

**세 파일이 안 바뀐다**: `query_service.py`(scope 인자를 이미 받는다)·
`indexing_service.py`(owner_id 를 이미 받는다)·`vector_index.py`(apply_scope 구현됨).
u1·u2 설계가 값을 한 지점이다.

### 정직하게 범위를 좁힌 결정들

**BR-140 — "악성 파일 차단"이라고 쓰지 않는다.** 매직 바이트·파서 성공·페이지 수·
`/JavaScript`·`/EmbeddedFile`·`/Launch`·`/OpenAction` 거부까지 본다. 안티바이러스가
아니고, 알려진 악성 코드를 탐지하지 않으며, 새 PDF 파서 취약점을 막지 못한다 —
그것을 적는다. **가장 큰 방어는 규칙이 아니라 구조다: 이 시스템은 업로드 파일을
실행하지 않고 텍스트만 추출한다.**

**BR-151 — 익명 질의를 없애지 않는다.** 요구사항 어디에도 질의에 로그인이 필요하다는
말이 없다. 결과로 익명 질의 이력은 아무의 이력도 아니게 되는데, 그것을 결함이 아니라
설계로 적는다.

**BR-146 — 남의 문서에 403 이 아니라 404.** 403 은 "그 문서는 존재한다"를 알려 주고,
문서 id 는 연속된 정수라 열거할 수 있다.

**BR-134 — 로그인 실패 이유를 구분하지 않고, 없는 계정에도 해시를 검증한다.**
구분하면 가입 여부 확인 도구가 되고, 검증을 건너뛰면 응답 시간이 같은 정보를 흘린다.

### 설계 중 드러난 스키마 사실 2건
1. **`document.source_url` 이 NOT NULL 이라 업로드에도 값이 필요하다.**
   `upload://` 는 인용 화면에서 깨진 링크가 되고 빈 문자열은 형식적 만족이다.
   → `/documents/{uuid}` — **소유자가 실제로 열어볼 수 있는 경로**. BR-105("확인
   가능한 출처")를 지킨다. 타인에게는 404 이고 그것이 격리다.
2. **`UNIQUE (source_id, external_id)` 는 업로드에서 일을 하지 않는다.**
   `source_id` 가 NULL 이면 PostgreSQL 이 튜플을 비교하지 않는다. UUID 충돌은
   무시할 만하므로 제약을 더하지 않되, **제약이 지켜 주고 있다고 착각하지 않도록**
   적어 둔다.

### FR-34 의 나머지 절반이 닫힌다
u2 는 면책 **상시 표시**(FR-35, BR-84)만 구현했다. "1회 동의·기록 저장"은 계정이
없어 미구현이었고 BR-152 가 그것을 닫는다. 다만 익명 사용자는 계정이 없어 동의를
남기지 못하며, **익명에 대한 고지는 상시 표시가 전부**라고 적었다.

### 다음 — NFR Design
u2 이후 두 번째 NFR Design 단계다. 인증·업로드 통제가 대상이다.

---

## CONSTRUCTION — Functional Design (u5-account-upload) : **APPROVED**
**Timestamp**: 2026-08-30T01:40:00Z
**승인 발언**: "승인"

---

## CONSTRUCTION — NFR Design 계획 (u5-account-upload)
**Timestamp**: 2026-08-30T01:45:00Z
**산출물**: `plans/u5-account-upload-nfr-design-plan.md` — **FQ7-1~11, 답변 대기**

### FD 에서 정한 것은 다시 묻지 않는다
해싱(BR-131)·토큰 전달(BR-135)·만료(BR-136)·업로드 한도(BR-139)·검증 순서(BR-140)·
저장 경로(BR-141)·404 정책(BR-146)은 확정이다. 이 단계는 **그것들이 실제로 성립하게
만드는 배치와 패턴**을 정한다.

### 실측 — 이미 있는 방어와 없는 것
```
있다:  NFR-14 마스킹 (core/logging.py) — password·token·authorization 을 잡는다
없다:  레이트 리밋 · 사용자별 용량 한도 · /data/uploads 볼륨 · 인증 의존성
```
마스킹이 **`Cookie: session=...` 은 못 잡는다** — 그 안에 JWT 가 통째로 들어 있다.
FQ7-11 이 그것을 겨냥한다.

성능 예산은 이 유닛에 직접 걸리지 않는다. NFR-1~3 은 질의·카드 예산이고 로그인·
업로드에 대응하는 항목이 없으며, NFR-4(색인 처리량)는 색인 경로를 그대로 쓰므로
이미 검증된 경로다. → **새 예산을 발명하지 않고 관측 가능하게만 만든다.**

### 이 단계의 중심 — FQ7-8 격리를 어떻게 **증명**하는가
규칙을 적는 것과 그것이 지켜지는 것은 다르다. 이 프로젝트는 **"테스트는 초록불인데
그 경로가 한 번도 돈 적이 없다"로 결함 5건**(25·39·40·46·47)을 만들었고, 격리는
그 실패가 가장 비싼 자리다 — 조용히 깨지고, 깨진 것을 아무도 모른다.

권장안은 **세 겹**이다:
```
① 두 사용자 픽스처로 교차 접근 통합 테스트   ← 실제로 새는지
② C55 밖에서 Scope( 직접 생성 금지 (정적)   ← 새 라우터가 규칙을 우회하는 것
③ 검색 경로별 owner_id 필터 단위 테스트      ← 경로마다 실제로 걸리는지
```
②가 필요한 이유: ①은 **테스트가 커버하는 경로만** 본다. 새 화면이
`Scope(owner_id=...)` 를 직접 만들면 ①은 통과하고 ②만 잡는다.

### 명시적으로 배제한 선택지
| 선택지 | 배제 이유 |
|---|---|
| 계정 잠금(5회 실패 15분) | **공격자가 남의 계정을 잠글 수 있는 DoS 도구**가 된다. 이메일만 알면 된다 |
| IP 레이트 리밋 | 프록시·NAT 뒤 사용자를 함께 막고, `127.0.0.1` 바인딩이라 IP 다양성 자체가 없다 |
| 토큰 블랙리스트/epoch | 모든 요청이 상태 조회를 하게 되어 무상태 토큰의 이점이 사라진다 |
| 색인 실패 시 자동 삭제 | **사용자가 올린 것을 시스템이 조용히 지운다.** 원인이 일시적일 수 있다 |
| 내용 해시로 업로드 중복 거부 | `content_hash`(BR-09)는 수집 변경 감지용이다. 개정판을 같은 이름으로 올리는 것은 정상 |
| 공개 코퍼스에 owner_id 를 붙여 테스트 | **실코퍼스 변조** — 결함 48·53 과 같은 부류를 자초한다 |

### 정직하게 남길 것 (요약 4절)
1. 탈취된 토큰은 **최대 12시간 유효**하다. "무효화 지원"이라고 쓰지 않는다
2. 레이트 리밋은 무차별 대입을 **늦출 뿐 막지 않는다**
3. 격리는 **테스트가 커버하는 경로에서만** 증명된다 — 그래서 정적 검사가 같이 간다
4. `/usage` 는 로그인만 요구하고 **역할을 구분하지 않는다**. FR 에 역할이 없다

---

## CONSTRUCTION — NFR Design (u5-account-upload) : 산출물 생성
**Timestamp**: 2026-08-30T02:30:00Z
**승인 발언**: "권장안대로 진행" — FQ7-1~11 전부 권장안

### 산출물 2종 (u2 와 같은 구성)
```
construction/u5-account-upload/nfr-design/
  nfr-design-patterns.md   AP-1~4(인증) · UP-1~4(업로드) · IP-1~3(격리) · OP-1~2(관측)
  logical-components.md    C51~C55 배치 · 인증 의존성 체인 · 환경변수 11 · 볼륨 · 검증 11항목
```
**신규 컨테이너 없음.** u2 의 `reranker` 와 달리 기존 `app`·`worker` 안에서 끝난다.

### 새로 생긴 위협 중 가장 큰 것에 새 방어가 필요 없다
**업로드 텍스트가 답변에 인용된다** — u2 가 코퍼스에 대해 세운 위협 모델의
사용자 통제 버전이다. 그런데 SP-3(이스케이프+nonce)·SP-4(색인 시 스캔)·
SP-5(탐지해도 제외 안 함)가 **색인 경로에 붙어 있고**, 업로드는 같은 색인 경로를
쓴다(BR-142).
**"같은 경로로 색인한다"가 보안 결정이기도 한 이유가 여기다.**
그리고 격리가 폭발 반경을 제한한다 — 업로드 텍스트는 올린 사람의 질의에만 들어간다.

### 각 패턴에 "막지 못하는 것"을 함께 적었다
| 패턴 | 막지 못하는 것 |
|---|---|
| AP-2 지수 백오프 | **무차별 대입을 막지 않는다. 늦출 뿐이다.** 분산·저빈도 시도에 거의 무력 |
| AP-3 무상태 토큰 | **탈취된 토큰은 최대 12시간 유효.** "무효화 지원"이라 쓰지 않는다 |
| UP-1 업로드 검증 | 악성 코드 시그니처를 탐지하지 않고, 새 `pypdf` 취약점을 막지 못한다 — **파싱 자체가 공격면** |
| IP-3 격리 증명 | ①은 **테스트가 커버하는 경로만** 본다. 그래서 ② 정적 검사가 같이 간다 |

방어 심층도 표에서 **3차가 비어 있는 줄이 셋**이다(토큰 무효화·CSRF·용량).
채워진 것처럼 보이게 쓰지 않는다.

### 설계 중 늘어난 것 — 문서 간 정합
`user_account.failed_attempts` · `last_failed_at` 는 **NFR Design 에서 AP-2 를 정하며
생긴 컬럼**이고 FD 의 `domain-entities.md` 에는 없었다. 두 문서를 맞췄고,
"FD 이후에 늘었다"는 사실을 남겼다.

용량 한도는 **집계 컬럼을 두지 않는다** — `SUM(upload_size_bytes)` 로 계산한다.
집계 컬럼은 삭제·실패 경로마다 갱신을 잊을 수 있고, 잊으면 **한도가 실제와 어긋난 채
조용히 동작**한다.

### 가장 쉽게 잊히는 검증
`JWT_SECRET` 을 비우고 기동해 **실패하는지** 본다. 기본값이 있으면 테스트는 통과하고
배포는 비밀 없이 나간다 — BR-02(인증키 없으면 잡을 만들지 않는다)와 같은 태도다.

### 다음 — Code Generation
마이그레이션 `0004_account`. 신규 의존성 2종(`argon2-cffi`·`PyJWT`) — u2 의
`google-genai` 이후 처음이다.

---

## CONSTRUCTION — Code Generation (u5-account-upload)
**Timestamp**: 2026-08-30T05:30:00Z
**승인 발언**: "승인" (NFR Design)
**산출물**: `u5-account-upload/code/{code-summary,traceability}.md`, 신규 22 / 수정 12

### 마이그레이션 `0004_account` 적용 완료
```
alembic_version  0003_evaluation → 0004_account
user_account 생성 · document 에 upload_* 컬럼 3개.  u1~u4 테이블 변경 0
```
신규 런타임 의존성 2종(`argon2-cffi`·`pyjwt`) — u2 의 `google-genai` 이후 처음.

### 격리는 만든 것이 아니라 값을 넣은 것 — 세 파일이 안 바뀌었다
```
services/query_service.py     변경 없음 (scope 인자를 이미 받는다)
services/indexing_service.py  변경 없음 (owner_id 를 이미 받는다)
indexing/vector_index.py      변경 없음 (apply_scope 가 이미 구현)
```
설계가 약속한 그대로다. **바뀐 곳은 `web/routers/query.py` 하나이고, 그것이
없었으면 결함이 됐을 자리**다 — 스트리밍 질의만 공개 스코프로 하드코딩돼 있어
같은 질문에 SSR 은 내 업로드를 찾고 스트리밍은 못 찾았을 것이다.
**정적 검사(IP-3 ②)가 잡았다.** 통합 테스트만 있었다면 그 경로를 덮는 테스트가
없어 통과했을 것이다.

### 돌려봐서 나온 것 5건 (문서를 읽어서가 아니라)

**① 마스킹 정규식에 백스페이스가 들어가 전체가 무력화될 뻔했다.**
편집 중 `\b` 가 0x08 로 들어가 `_SECRET_PARAM` 이 아무것도 매칭하지 않았다 —
`api_key=...` 조차 로그에 그대로 남는 상태. **패턴을 눈으로 읽으면 정상으로 보인다.**
동작을 실제로 확인해서 잡았다.

**② `JWT_SECRET` 이 짧아도 통과했다.** PyJWT 가 테스트 중
`InsecureKeyLengthWarning`(11바이트 < 32)을 냈다. **로그의 경고는 통제가 아니다** —
`require_jwt_secret()` 이 32자 미만을 거부한다(RFC 7518 §3.2).
라이브러리가 말해 주고 있었고 아무도 읽지 않았다.

**③ 로그인 리다이렉트에 Location 헤더가 없었다.** `HTTPException(303)` 은 FastAPI 가
JSON 본문으로 렌더한다 — **303 인데 갈 곳이 없다.** 예외 핸들러로 `/login?next=` 로 보낸다.

**④ 색인 실패가 사용자에게 보이지 않았다.** 빈 PDF 로 확인:
`ExtractionError: PDF produced no usable text` 가 워커 로그에만 남고 문서는 청크 0으로
남아 화면은 **영원히 "색인 중"**. FQ7-6 이 "상태만 표시"라고 정했는데 표시할 상태가
없었다 → 업로드마다 `job`+`job_item` 을 만들어 u1 의 FR-6·FR-8 기계를 그대로 쓴다.
**스캔 MSDS 는 흔하다 — 예외가 아니라 평범한 경우다.**

**⑤ 워커의 읽기 전용 마운트가 실제로 강제된다.** 정리 스크립트를 워커에서 돌렸더니
`upload_file_delete_failed` — 설계대로다(UP-3). 삭제는 `app` 의 일이다(BR-144).

### 검증 10항목 (Build & Test 로 미루지 않고 수행)
```
단위 618 통과 + 1 스킵 (573 → +45)     통합 53 통과 + 1 스킵 (40 → +13)   ruff clean
JWT_SECRET 없이 기동 → RuntimeError 로 실패 ✅
공개 코퍼스 불변 → 익명 조회 정상, 78문서 / 1,633청크 그대로 ✅
가입→로그인→업로드→목록 종단 ✅   교차 접근 차단 ✅   업로드 거부 5종 ✅
/data/uploads 권한 700 appuser ✅
```

**u4 지표 불변이 이 유닛의 핵심 증거다.**
```
실행 88 vs 기준선 73
  Recall@5 0.700 → 0.700  +0.000     MRR 0.546 → 0.546  +0.000
  거부 정확도 0.400 → 0.400  +0.000    오거부율 0.000 → 0.000  +0.000
판정: ok
```
"검색 경로를 건드리지 않았다"를 **숫자로 확인**했고 정확히 같은 값이 나왔다.

> 검증 중 만든 테스트 계정 4개·업로드 2건은 삭제했다. `user_account` 0행,
> 문서 78, 청크 1,633 — 착수 전과 같다. 결함 48·53 에서 배운 습관이다.
> (중간에 corpus_fingerprint 가 달라 `incomparable` 이 나온 것도 설계대로였다.)

### 미충족 — 정직하게
탈취 토큰 최대 12시간 유효 / 백오프는 늦출 뿐 / 업로드 검증은 안티바이러스 아님 /
`/usage` 역할 구분 없음 / 익명 질의 이력은 아무의 이력도 아님 /
비밀번호 재설정·계정 삭제 미구현(FR 에 없다).

---

## CONSTRUCTION — Build and Test (u5-account-upload) + 결함 56
**Timestamp**: 2026-08-30T07:00:00Z
**산출물**: `build-and-test/u5-build-and-test-summary.md`, `u5-test-instructions.md`

### 결과
```
빌드 docker compose down && up 단일 명령, 4컨테이너 healthy (NFR-29)
마이그레이션 0004_account (u1~u4 테이블 변경 0)
단위 618 통과 + 1 스킵 · 통합 53 통과 + 1 스킵 · ruff clean
NFR-28 도달 불가 호스트로 618건 전부 통과
격리 3겹: 통합 11 · 정적 4 · HTTP 종단 5
u4 지표 전 항목 +0.000, 판정 ok
볼륨 재기동 후 /data/uploads 700 appuser 유지
```

### 정적 검사가 실제로 일을 했다
`Scope(` 를 C55 밖에서 만드는 코드를 금지하는 검사가 **`web/routers/query.py` 의
하드코딩된 공개 스코프**를 찾아냈다. 통합 테스트만 있었다면 통과했을 것이다 —
그 경로를 덮는 테스트가 아직 없었기 때문이다. 스트리밍 질의만 내 업로드를 못 찾는
상태가 됐을 것이고, 같은 질문에 SSR 과 스트리밍의 답이 달라졌을 것이다.

**"테스트가 커버하는 경로에서만 증명된다"는 IP-3 의 전제가 그대로 실증됐다.**

### 보안 실측
```
CSRF 없음/불일치            400
세션 쿠키                  HttpOnly · SameSite=lax · Secure=false(로컬 HTTP)
오픈 리다이렉트 //evil…      / 로 무력화
로그인 실패 응답시간         존재 97.5ms / 없음 89.0ms   (8.5ms 차)
지수 백오프                시도 7 = 1,079ms, 시도 8 = 2,091ms, 정상 비번은 즉시 성공
업로드 거부 6종            전부 사유와 함께 400
이스케이프                 폼 3종 · 파일명 XSS → 원문 반사 0
JWT_SECRET 없이 기동        RuntimeError
```
**응답 시간이 완전히 같지는 않다**(8.5ms, 약 9%)는 것을 그대로 적는다. argon2 비용이
지배하기 때문이고, AP-1 이 없으면 없는 계정은 1ms 안에 돌아왔을 것이다.

**백오프가 잠금이 아니라는 것도 실측으로 보였다** — 8회 실패 뒤에도 올바른
비밀번호로 즉시 로그인된다. 공격자가 남의 계정을 잠글 수 없다.

### 로그 — 마스킹이 지운 것이 아니라 애초에 없다
```
/logs/safeenv.log 최근 400KB
  세션 쿠키 0 · argon2 해시 0 · 이메일 0 · JWT 형태 0
  isolation_denied 3 · login_failed 19 · login_succeeded 1
  upload_rejected 4 · upload_accepted 5
```
로그는 `user_id` 를 남기고 이메일을 남기지 않는다. 마스킹 확장은 실수로
흘러들어갔을 때의 2차 방어로 남는다.
**`isolation_denied` 3건이 기록된 것이 중요하다** — 격리가 막은 순간을 볼 수 없으면
격리가 도는지 사후에 알 방법이 없다. 0건과 로그 없음은 밖에서 구분되지 않는다.

### 결함 56 — 업로드 원본 링크가 한 번도 열린 적이 없다
목록의 "원본" 링크가 `/documents/{문서 id}/file` 인데 라우트는 **UUID** 로 찾는다.
`external_id == "151"` 은 아무것도 매칭하지 않으므로 **소유자에게도 404** 였다.

같은 실수가 `source_url` 에도 있었다 — `/documents/{uuid}` 는 존재하지 않는 경로다
(`/file` 이 빠졌다). **업로드 문서를 인용한 답변의 출처 링크가 전부 죽은 링크**가
되고, BR-105("모든 값에 확인 가능한 출처")를 정면으로 어긴다.

**링크를 따라가 보고 나서야 발견했다. 화면은 정상으로 보였다.**
결함 25·39·40·46·47 과 같은 부류 ① — 그 경로가 한 번도 돈 적이 없다.
→ 수정 후 소유자 200 · `application/pdf` · 431바이트, 타인 404.

### u4 지표 불변 — 핵심 증거
```
실행 88 vs 기준선 73   전 항목 +0.000   판정 ok   incomparable 경고 없음
```
중간에 테스트 업로드가 남아 있을 때는 `corpus_fingerprint 가 다릅니다` 경고와 함께
`incomparable` 이 나왔다 — 그것도 설계대로다.

### 정리
테스트가 만든 계정 10개·업로드 4건 삭제. `user_account` 0행 / 문서 78 / 청크 1,633 —
착수 전과 같다. 이번에는 **통합 테스트 자체에 원복을 넣어** 두었다(결함 48·53 의 교훈).
파일 삭제는 `app` 에서 한다 — 워커는 읽기 전용 마운트라 실패하고, 그것이 설계다.

### Ready for Operations — 조건부. **승인 대기**
남은 제약: 탈취 토큰 12시간 유효 · 역할 개념 없음 · 업로드 검증은 안티바이러스 아님 ·
`127.0.0.1` 바인딩 유지(계정이 생겼다고 외부 노출을 전제하지 않았다).

---

## CONSTRUCTION — Build and Test (u5-account-upload) : **APPROVED**
**Timestamp**: 2026-08-30T07:30:00Z
**승인 발언**: "진행"

**CONSTRUCTION 5/5 완료.** u1 수집·색인 → u2 질의응답 → u3 물질 카드 →
u4 평가 → u5 계정·업로드. FR 48건 전부 배정된 유닛에서 처리됐고, 미충족은
전부 **데이터 제약**이거나 **명시적으로 범위를 좁힌 결정**이다.

---

## OPERATIONS — 운영 문서 색인
**Timestamp**: 2026-08-30T07:40:00Z
**산출물**: `aidlc-docs/operations/operations.md`

실행 계획이 이 단계를 "PLACEHOLDER — 본 프로젝트에서는 **운영 문서 색인 역할**"로
정의했다. 그대로 따랐다 — **새 설계를 하지 않고**, 다섯 유닛에 흩어진 운영 정보를
한 곳에 모았다. 문서의 모든 숫자는 각 유닛에서 실측되고 승인된 것이다.

### 담은 것
```
1. 지금 무엇이 서 있는가   78문서·1,633청크·물질 49 / 기준선 2개(10 full · 73 retrieval)
2. 매일·주기 작업         evaluate --retrieval-only(매일, LLM 0) / 재색인 35분 규칙
3. 기동에 필요한 것        JWT_SECRET 없으면 앱이 뜨지 않는다
4. 알고 운영할 제약        심판 20/일 = 전체 평가 2일 / 리랭커 불가 / 역할 없음 /
                        **할당량 리셋 시점은 모른다**(KST 자정이 아니다)
5. 자주 나는 실패          스캔 PDF·카드 결측·incomparable·종료코드 4
6. 보안 운영              무엇을 막고 **무엇을 막지 못하는가**
7. 백업·복구
8. 문서 색인
9. 반복한 실패 여섯 가지
10. 다음에 할 만한 일 (제안, 미착수)
```

### 9절 — 결함 57건이 여섯 모양으로 되풀이됐다
```
① 한 번도 실행된 적 없음    25·39·40·46·47·56    ← 가장 많고 가장 비싸다
② 규칙이 구조상 성립 불가   26·31·49·55
③ 틀린 신호를 읽음         27·30·45·50·52
④ 선택적인 것이 필수의 예산 28·29·32·34a
⑤ 제약을 몰랐음           36·37·51 · u4 할당량 전제 오류
⑥ 자초 (테스트가 대상 변경) 34·48·53
```
**①의 대응은 하나뿐이었다 — 실제 데이터로 끝까지 돌려보는 것.**
결함 56 은 링크를 따라가 보고 나서야 나왔고 화면은 그때까지 정상으로 보였다.

### 10절 — 다음 우선순위는 실측이 정한다
**MSDS 추가 수집이 가장 크고 가장 싸다** — 카드 결측·인용 정확도(0.553)·FR-24 가
전부 여기에 묶여 있고 코드 변경이 0이다. 그다음이 물질명 검색(CAS 3/3 vs 물질명 3/8),
거부 정확도(0.400), BR-31a↔BR-104(카드 1/49), 문서 20·24 재파싱이다.

**AI-DLC 전 단계 완료.**

---

## OPERATIONS — MSDS 추가 수집 (operations.md 10절 1번)
**Timestamp**: 2026-08-30T13:50:00Z
**지시**: "MSDS 추가 수집 진행해줘"

### 선정 — 코드가 아니라 코퍼스가 카드를 비운다
물질 마스터 49건 중 MSDS 를 가진 것이 3건뿐이라 카드 46건이 6/7 이상 결측이었다.
**마스터에 있고 · 사고 사례에 등장하고 · MSDS 가 0건**인 5종을 목표로 잡았다.
```
암모니아 7664-41-7 · 염소 7782-50-5 · 수소 1333-74-0 · 메틸에틸케톤 78-93-3 · 아크릴산 79-10-7
```

### 건식 검증 후 추가 — 재색인 규칙과 같은 태도
수집 전에 후보 URL 을 그대로 파이프라인에 태워 봤다(코퍼스 무변경).
```
암모니아  taekyunggnt.co.kr    316KB 10p 섹션14 structured CAS 있음   ✅
염소     hcc.hanwha.co.kr     830KB 17p 섹션16 structured CAS 있음   ✅
수소     skens.com            691KB 12p 섹션16 structured CAS 있음   ✅
MEK     skchemicals.com      332KB  9p 섹션16 structured CAS 있음   ✅
MEK     duksanchemical.com    44KB  9p 섹션 0 unstructured CAS 없음  ❌ 탈락
아크릴산  (SK 패턴 추정 URL)     PDF 아님 (HTML)                      ❌ 탈락
```
**탈락 2건이 이 절차의 값이다.** duksanchemical 은 `pypdf` 가 `/UniKS-UTF16-H`
인코딩을 지원하지 않아 텍스트가 0이었다 — R-2 의 실제 사례다. 아크릴산은 URL 을
추측했고 HTML 이 돌아왔다.

**아크릴산은 같은 조건의 국문 PDF 를 찾지 못해 제외했다.** 영문 SDS 는 있었지만
코퍼스가 국문이고, 없는 것을 지어내지 않는다.

### 수집 결과
```
job 31 succeeded — 성공 12 / 건너뜀 0 / 실패 0
문서 78 → 82 · 청크 1,633 → 1,697 · 벡터 1,697
신규 4건 전부 structured (섹션 14·18·16·16)
SP-4 injection_signals_flagged: 염소·수소 각 1청크 — 탐지하되 제외하지 않는다(SP-5)
skens.com 은 robots.txt 미게시 → decision "unknown", 차단 아님(BR-05)
```

### 카드 커버리지 — 목표한 개선이 나왔다
```
결측 분포   이전 {0:1, 1:1, 2:1, 6:44, 7:2}
           이후 {0:4, 1:2, 2:1, 6:41, 7:1}
```
| 물질 | 이전 | 이후 |
|---|---|---|
| 염소 · 수소 | 6/7 | **0/7** |
| **메틸 에틸 케톤** | **7/7** | **0/7** |
| 암모니아 | 6/7 | **1/7** |

**메틸에틸케톤이 가장 극적이다** — 물질 API 레코드가 통째로 비어 7/7 결측이었는데
(u3 에서 "정직한 결측"으로 기록한 그 건), MSDS 가 붙어 전 항목이 찼다.

### ⚠️ 대가 — 검색 지표가 내려갔다
```
실행 114 vs 기준선 73
  Recall@5  0.700 → 0.667  -0.033      MRR 0.546 → 0.525  -0.021
  판정: incomparable (corpus_fingerprint 가 다르다)
```
문항별로 보면 셋이 움직였다.
```
law-03  MRR 0.200 → 0.333   개선
sub-04  MRR 0.250 → 0.500   개선
sub-07  Recall 1.000 → 0.000   상실
```
**sub-07("CAS 7782-50-5 흡입 시")의 상위 5건이 전부 새 염소 MSDS 로 채워졌다.**
```
rank 0 msds_03 · 1 msds_04 · 2 msds_02 · 3 msds_11 · 4 msds_08  (전부 한화 염소 MSDS)
```
골든셋이 지정한 정답 근거는 물질 API 의 `substance_inhale` 인데 그것이 밀렸다.
`ensure_doc_type_spread` 가 갈라주지 못한 이유는 **물질 레코드와 MSDS 가 둘 다
`doc_type=msds`** 이기 때문이다.

**이것이 품질 저하인지 골든셋의 한계인지는 사람이 판단할 문제다.**
msds_04(응급조치)·msds_11(독성)은 "흡입하면 어떻게 되나"에 대한 정당한 근거다 —
답은 여전히 좋을 수 있고, 골든셋이 한 곳만 정답으로 고정했을 뿐이다.

**골든셋을 고치지 않았다.** 새 동작에 맞춰 정답을 넓히는 것은 BR-111 이 경계한
"정답을 느슨하게 고치는 것"과 구분되지 않는다. R-5 대로 사람이 결정할 일이다.

### 기준선도 승격하지 않았다
코퍼스가 바뀌었으므로 기준선 73(문서 78 기준)과는 비교 대상이 아니다.
새 기준선은 사람이 명시적으로 올린다(BR-129).

### 테스트
단위 618 통과 + 1 스킵 / 통합 53 통과 + 1 스킵.

---

## OPERATIONS — `doc_type` 세분화 검토 (operations.md 10절 7번)
**Timestamp**: 2026-08-30T15:10:00Z
**지시**: "doc_type 세분화 검토 먼저 해주세요"
**산출물**: `aidlc-docs/operations/doc-type-split-review.md` — **실행 전 승인 대기**

### 문제를 눈으로 확인했다
sub-07 의 융합 후보 20건을 전부 뽑아 봤다.
```
0~6  msds_pdf  염소 MSDS (msds_03·04·02·11·08·08·11)   ← 절단선은 4와 5 사이
7    ncis_substance  substance_inhale   ← 골든셋의 정답 근거
20건 전부 doc_type=msds
```
**정답 근거는 후보 안에 있다. 7위에서 잘렸을 뿐이다.**
BR-69 `ensure_doc_type_spread` 는 상위에 없는 **타입**을 끌어올리는데, 20건이
전부 같은 타입이라 끌어올릴 것이 없다. BR-69 의 원래 근거는 "법령이 69%라 한
타입이 모든 슬롯을 채운다"였고, 지금은 **한 문서가 모든 슬롯을 채운다** — 같은
실패에 축만 다르다.

### 혼동은 이미 두 곳에서 우회되고 있다
```python
# structure.py — MSDS 구조화기가 실패하면 물질 구조화기로 흘린다
# card.py::_has_msds — "Both arrive as doc_type=msds; the section codes are what separate them"
```
**코드가 이미 "둘은 다른 것"이라고 적어 놓고 섹션 코드로 구분하고 있다.**
세분화는 새 아이디어가 아니라 이미 지불 중인 비용을 드러내는 일이다.

### 시뮬레이션 — DB 를 바꾸지 않고 측정
물질 청크의 `doc_type` 만 메모리에서 바꿔 spread 를 다시 돌리고 30문항을 재채점했다.
```
현재      Recall@5 0.667   MRR 0.525
세분화 후  Recall@5 0.700   MRR 0.532
변화 문항 1건: sub-07  Recall 0.000 → 1.000, MRR 0.000 → 0.200
```
**MSDS 추가로 잃은 0.033 이 정확히 회복되고, 부작용 문항이 0건이다.**
MRR 이 기준선 0.546 에 못 미치는 것은 sub-07 이 1위가 아니라 5위로 들어오기 때문이다.

건식 시뮬레이션을 먼저 돌리는 절차가 또 값을 했다 — 재색인 없이 답이 나왔다.

### 비용
코드 5곳(`DocType` · `sources.yaml` · `structure.py` · `_RELATION_BY_DOC_TYPE` ·
`_has_msds` docstring) · 데이터 49문서 · **부분 재색인 약 8분**(전 코퍼스 35분 불필요).
u1~u5 의 규칙은 하나도 바뀌지 않는다.

⚠️ **순서가 규칙이다**: `document.doc_type` UPDATE → 그다음 부분 재색인.
`reindex_document` 가 행의 `doc_type` 을 읽으므로 반대로 하면 조용히 아무 일도 안 난다.

### 부수 발견 — `doc_type_hint` 는 아무 데도 쓰이지 않는다
```
grep -rn doc_type_hint app/ → entities.py 에서 만들고 types.py 에 담고 끝.
검색·융합·필터 어디에서도 읽지 않는다.
```
BR-66("가중치이지 필터가 아니다")을 위반하지는 않는다 — 필터로 쓰이지 않는다는
조건은 만족한다. 그러나 **u2 가 만든 값이 네 유닛을 지나도록 소비자가 없다.**
결함으로 올리지 않고(동작 영향 0, 힌트를 쓰는 게 나은지도 미측정)
`operations.md` 10절 8번으로 남긴다.

지금 세분화해도 **잃을 가중치가 없다**는 점이 이 검토의 부수 소득이다.

### 권고
**찬성.** 측정됐고(부작용 0), 이미 지불 중인 비용을 드러내며, 비용의 경계가 뚜렷하다.
다만 **MSDS 를 더 넣을 계획이면 그때 한 번에 하는 것**도 방어 가능하다 —
재색인 횟수가 줄어든다. 실행 여부는 사람이 정한다.

---

## OPERATIONS — `doc_type` 세분화 실행 + `retype` 명령 신설
**Timestamp**: 2026-08-30T15:40:00Z
**승인 발언**: "실행하고 MSDS 추가시에도 변환 가능하게 바꿔 주세요. 재색인 횟수를
늘리더라도 그게 낫습니다"

### 일회성 SQL 이 아니라 명령으로 만들었다
```bash
safeenv retype            # 무엇이 바뀔지만 보여준다 (기본)
safeenv retype --apply    # document.doc_type 갱신 → 그 문서만 재색인
```
`config/sources.yaml` 이 권위이고 명령이 행을 거기에 맞춘다. **수집 경로는 이미
매번 선언된 타입을 쓰므로 새 문서는 항상 옳다** — 어긋나는 것은 스펙이 바뀌기 전에
수집된 행뿐이다. 사용자 요청대로 **다음에 타입이 또 갈릴 때 마이그레이션을 새로
쓰지 않는다.** MSDS 를 더 넣어도 같은 명령 하나면 된다.

순서는 코드가 강제한다: **행 갱신 → 재색인**. `reindex_document` 가 행의 `doc_type`
을 읽으므로 반대로 하면 조용히 아무 일도 일어나지 않는다 — 검토 5절 ③의 위험을
사람의 절차가 아니라 코드로 막았다.

### 변경
```
core/types.py                DocType.SUBSTANCE 추가
config/sources.yaml          ncis_substance: doc_type msds → substance
processing/stages/structure  SUBSTANCE 는 물질 구조화기로 직접.
                             MSDS→물질 폴백은 USER_UPLOAD 용으로 남긴다
                             (업로드가 물질 레코드일 수 있고 그건 우리가 선언하지 않는다)
indexing_service             _RELATION_BY_DOC_TYPE[SUBSTANCE] = SUBJECT
                             retype_documents() 신설
cli.py                       retype 하위명령
card.py                      _has_msds docstring 갱신 (로직은 섹션 코드 기반 유지)
```

### 적용 실측
```
불일치 49건 → 재색인 성공 49 / 실패 0   (약 4분)
재실행 → 불일치 0건 (멱등)
doc_type   substance 49 · msds 12 · law 9 · incident 12
청크 메타   law 1,173 · substance 324 · msds 188 · incident 12
```

### 예측 대비 실측 — 시뮬레이션이 하나를 놓쳤다
| | 시뮬레이션 | 실측 |
|---|---|---|
| Recall@5 | 0.700 | **0.700** 정확히 일치 |
| MRR | 0.532 | 0.529 |
| 변화 문항 | 1건 | **2건** |
```
sub-07  Recall 0.000 → 1.000   목표 달성 (MSDS 추가로 잃은 것을 되찾았다)
law-02  MRR   0.333 → 0.250   Recall 은 1.000 그대로  ← 시뮬레이션이 못 본 것
```
재색인으로 청크가 다시 만들어지며 융합 순위가 미세하게 달라졌고, 물질 후보가 하나
올라오며 법령 청크를 한 칸 밀었다. **시뮬레이션은 방향이 맞았고 약간 낙관적이었다** —
그 차이를 적어 둔다. 건식 시뮬레이션이 재색인을 대체하지는 않는다는 뜻이기도 하다.

### 바뀌지 않은 것 — 확인함
```
카드 결측 분포 {0:4, 1:2, 2:1, 6:41, 7:1}  세분화 전후 동일
단위 629 통과 + 1 스킵 (618 → +11)  ·  통합 53 통과 + 1 스킵  ·  ruff clean
```
카드가 그대로인 이유는 `_MSDS_SECTION_FOR`·`_has_msds` 가 **섹션 코드**를 보기
때문이다 — 검토 4절의 예상대로다.

신규 단위 테스트 11건(`test_doc_type_split.py`)은 **타입이 존재하는지**가 아니라
**BR-69 가 이제 둘을 가를 수 있는지**를 고정한다. 특히
`test_every_doc_type_has_a_relation` 은 다음에 타입을 추가하는 사람이
`_RELATION_BY_DOC_TYPE` 을 빠뜨리면 잡는다 — 런타임 KeyError 로만 드러났을 실수다.

### 남은 것
- **기준선 재승격은 사람이** (BR-129). 코퍼스가 두 번 바뀌었다
- `doc_type_hint` 는 여전히 소비자가 없다 (`operations.md` 10절 8번)

---

## OPERATIONS — 기준선 재승격 + 결함 58 (2026-08-30)

**승인 발언**: "승격해주세요"

### 승격
```
evaluate --promote 127
실행 127 을 기준선으로 승격했습니다.

기준선 2개   10(full, 2026-08-28)  ·  127(retrieval_only, 2026-08-30)
실행 73 은 자동 강등 — 모드당 하나만 유지된다(set_baseline)
```

승격 전에 실행 127 이 **지금 코퍼스를 측정한 것인지** 지문으로 확인했다.

| | documents | chunks |
|---|---|---|
| 실행 10 · 73 (구 기준선) | 78 | 1,633 |
| **실행 127** | **82** | **1,697** |
| **현재 코퍼스** | **82** | **1,697** |

`full` 기준선은 실행 10 그대로 둔다. 코퍼스가 바뀌어 이미 비교 불가지만,
**대체할 `full` 실행이 없다** — 심판 할당량으로 2일이 걸린다. 없는 것을 있는 척
하느니 낡은 것을 낡은 채로 두고 상태에 적는다.

### 결함 58 — 컨테이너가 저녁 내내 구 이미지로 돌고 있었다

승격이 실제로 작동하는지 보려고 검색전용을 한 번 더 돌렸더니 **0.667** 이 나왔다.
방금 승격한 실행 127 은 0.700 이다. 같은 코퍼스·같은 골든셋인데 값이 다르다.

로그가 이유를 대고 있었다.
```
WARNING unknown_doc_type  chunk_id 17402  value "substance"   (×수십 건)
```
```
docker compose exec app python -c "print([t.value for t in DocType])"
['msds', 'law', 'incident', 'user_upload']        ← substance 가 없다
```

```
safeenv-app        sha256:b7b84c8…   Up 5 hours     ← 구 이미지
safeenv-app:latest 363b2791f028      23:24 빌드     ← 새 이미지, 아무도 안 씀
safeenv-migrate    safeenv-app:latest              ← 이것만 새 이미지로 돌았다
```

**이미지는 다시 빌드됐고 컨테이너는 재생성되지 않았다.** `app` 과 `worker` 는
`DocType.SUBSTANCE` 가 없는 코드로 5시간을 돌았다. 그 코드에서 `DocType("substance")`
는 `ValueError` 이고, 청크는 후보에 남되 **타입 분산에서 제외**된다 — 세분화가
겨냥한 바로 그 기계가 꺼져 있었다.

`docker compose up -d app worker` 로 재생성한 뒤:
```
실행 141   Recall@5 0.700   MRR 0.529   거부 0.400   오거부 0.000
실행 141 vs 기준선 127   전 지표 +0.000   판정 ok
```
**실행 127 과 완전히 일치한다.** 즉 비결정성이 아니었고, 기준선은 옳다.
0.667 을 낸 실행 140 이 예외였다.

> 실행 127(0.700)이 새 코드로 측정된 이유는 그때 `docker compose run` 계열 경로가
> `safeenv-app:latest` 를 집었기 때문이다. 같은 스택 안에서 **두 벌의 코드가 동시에
> 돌고 있었다** — `exec` 는 구 이미지, 일회성 컨테이너는 새 이미지.

### 결함 유형 — ① "한 번도 실행되지 않았다"의 배포판
지금까지 여섯 유형 중 ①은 *코드가 호출되지 않는* 경우였다. 이번은 **코드가 배포되지
않은** 경우다. 같은 유형이고 층만 다르다. 단위 629건과 통합 53건은 전부 통과했다 —
테스트는 호스트에서 새 코드로 돌고, 애플리케이션은 컨테이너에서 구 코드로 돌았다.
**테스트가 도는 코드와 서비스가 도는 코드가 다를 수 있다.**

### 고친 것 — `evaluate --list` 가 사람이 읽을 수 있게 됐다
BR-129 는 승격을 **사람의 행위**로 정했는데, 사람이 읽는 화면이 이랬다.
```
 137  retrieval_only succeeded  문항  30  LLM    0
 136  full           succeeded  문항  30  LLM    0
```
141개 실행 중 **103개가 통합 테스트가 만든 것**이다. 테스트는 `note` 에
`integration-test` 를 성실히 달아 두었는데(`_mark`), **`--list` 가 그 값을 출력하지
않았다.** 라벨이 사람이 보는 유일한 곳에서 보이지 않았다.

지표도 없어서, 승격할 실행을 고르려면 매번 `--compare` 를 따로 돌려야 했다.

```
 141  retrieval_only succeeded  문항  30  LLM    0  R@5 0.700  MRR 0.529
 140  retrieval_only succeeded  문항  30  LLM    0  R@5 0.667  MRR 0.522
 137  retrieval_only succeeded  문항  30  LLM    0  R@5 0.433  MRR 0.337 [integration-test]
 127  retrieval_only succeeded  문항  30  LLM    0  R@5 0.700  MRR 0.529 ★기준선
```
스텁 코퍼스로 도는 테스트 실행이 0.433 이라는 것도 이제 한눈에 보인다.
**결함 58 의 증거(140 vs 141)가 이력에 그대로 남는다.**

### 검증
```
단위 629 통과 + 1 스킵 · ruff clean
재빌드 → 재생성 → 실행 141 = 기준선 127 과 전 지표 +0.000
기준선 2개: 10(full) · 127(retrieval_only)
```

### 남은 것
- `full` 기준선은 낡았다. 새 코퍼스로 `--full` 완주가 필요하다(심판 할당량 2일)
- 코드 변경 후 **재빌드만 하고 재생성을 잊으면 같은 일이 또 난다.**
  `operations.md` 주기 작업에 확인 절차를 넣었으나, 이것은 절차이지 강제가 아니다.
  실행 스냅샷에 이미지 식별자를 넣으면 `incomparable` 이 잡아내지만, 재빌드마다
  비교 불가가 되는 대가가 있다 — **결정하지 않고 제안으로 남긴다**

---

## OPERATIONS — 재빌드 후 재생성 강제 구조 (2026-08-31)

**승인 발언**: "재빌드 후 재생성 강제하는 구조 만들어줘"

결함 58 은 절차로 막혀 있었다 — `operations.md` 에 "재생성까지 해야 한다"고 적어 둔 것이
전부였다. 그것은 강제가 아니라 부탁이다. 아래는 그 부탁을 네 겹의 구조로 바꾼 기록이다.

### 원칙 — 스탬프를 굽지 않고 디스크를 해싱한다

빌드 시점에 이미지 안에 식별자를 구워 넣는 방법을 먼저 검토했고 **버렸다.** 스탬프는
그 자체로 낡을 수 있다: 빌드가 재생성을 잊으면 옛 정체를 자신 있게 보고한다. 결함 58 이
정확히 "낡은 것이 자신 있게 답한" 사고인데, 그 해법으로 같은 성질의 물건을 하나 더
만드는 셈이다.

대신 **지금 디스크에 있는 파일을 해싱한다.** 디스크에 무엇이 있는지에 대해서는 틀릴 수
없다.

```python
TRACKED = ("app", "config", "migrations", "prompts", "eval", "pyproject.toml")
```
Dockerfile 이 `COPY` 하는 것과 정확히 같은 여섯 항목이다. 이 집합 밖의 것은 컨테이너
동작을 작업 트리와 다르게 만들 수 없고, 안의 것은 만들 수 있다. 호스트 163개 / 컨테이너
163개로 일치를 실측했다.

### 네 겹

| 겹 | 무엇 | 어디 |
|---|---|---|
| ① **정체** | 트리 해시 12자. 경로+내용을 해싱해 이름 변경도 잡는다 | `app/core/build.py` |
| ② **가시성** | `/healthz` 의 `build` · `stats` 의 `build:` · `evaluate --list` 의 코드 열 | 3곳 |
| ③ **기록** | `evaluation_run.build_id` — 어떤 코드가 그 수를 냈는지 | 마이그레이션 `0005_build_id` |
| ④ **집행** | 통합 테스트가 붉어진다 · 승격이 거부된다 | `test_deployed_code_is_current.py` · `promote_baseline` |

④가 핵심이다. **스크립트는 기억해서 돌리는 것이고, 통합 테스트는 이 프로젝트에서
붉으면 아무것도 승인되지 않는 것이다.**

### 집행 ①: 배포 최신성이 테스트다
```
tests/integration/test_deployed_code_is_current.py
  app 컨테이너 == 작업 트리
  worker 컨테이너 == 작업 트리
  app == worker            (한 이미지가 둘을 섬긴다, UD-3)
```

**만들자마자 실패시켜 봤다.** 컨테이너가 낡은 상태에서:
```
app 컨테이너는 식별 코드 자체가 없습니다 (이 검사보다 오래된 이미지),
작업 트리는 1353cb2a38c0 입니다.
  docker compose up -d --build app worker
FAILED test_app_matches_the_working_tree
FAILED test_worker_matches_the_working_tree
```

### 집행 ②: 승격이 거부된다 — BR-129 의 선행 조건
기준선은 이후 모든 실행이 대조되는 값이다. **지금 도는 코드가 재현할 수 없는 수를
기준선으로 세우면, 존재하지 않는 값을 상대로 회귀를 판정하게 된다.**
```
$ evaluate --promote 127
설정 오류: 실행 127 은 코드 미기록 로 측정됐고 지금 도는 코드는 1353cb2a38c0 입니다.
  재빌드 후 컨테이너를 재생성하지 않으면 이 상태가 됩니다 (결함 58):
    docker compose up -d --build app worker
  그 뒤 다시 측정해 승격하십시오. 검색전용 실행은 20초입니다.
  --full 은 측정에 이틀이 드므로 --accept-stale 로 넘길 수 있습니다.
종료코드 3
```
`--accept-stale` 를 남긴 이유는 `--full` 이 심판 할당량으로 **이틀**이 걸리기 때문이다.
그 사이 코드가 바뀌는 것은 정상이다. 다만 기본값이 아니고, 넘길 때 실행 `note` 에
`accept-stale: 측정 … / 승격 시점 …` 이 남는다. **예외를 없애는 대신 기록되게 했다.**

### 하지 않은 것 — `build_id` 는 비교 가능성 필드가 아니다
`_COMPARABLE_FIELDS` 에 넣지 **않았다.** 넣으면 코드가 바뀔 때마다 모든 실행이
`incomparable` 이 되고, **코드 변경의 영향을 잡는 것이 존재 이유인 가드가 다시는
발화하지 않는다.** 결함 55(기준선이 하나뿐이라 매번 incomparable)와 같은 모양이다.

실측으로 확인했다 — 새 코드의 실행 170 이 구 코드의 기준선 127 과:
```
Recall@5 0.700 → 0.700  +0.000   MRR 0.529 → 0.529  +0.000   판정: ok
```

### 만들면서 잡은 결함 — 검사가 자기 대상 앞에서 초록불이었다
첫 판 `test_deployed_code_is_current.py` 는 낡은 컨테이너 앞에서 **3건 전부 skip** 했다.
`docker compose exec` 가 실패하면 "컨테이너가 없다"로 읽었는데, 실제로는
**`app/core/build.py` 자체가 없는 낡은 이미지**여서 프로브가 죽은 것이었다.

즉 **이 검사가 존재하는 바로 그 상황에서 조용히 통과했다.** 결함 유형 ③(틀린 신호를
읽음)이고, 새로 만든 검사에서 같은 유형을 반복했다.

고친 방법: 애플리케이션 코드가 필요 없는 프로브(`print('alive')`)로 생존을 먼저 확인한
뒤 정체를 묻는다. **"떠 있지 않다"와 "너무 낡아서 대답을 못 한다"를 다른 답으로 분리**했다.
후자는 skip 이 아니라 실패다.

> 이것을 잡은 이유는 하나다 — **검사를 만든 뒤 실패해야 할 상태에서 먼저 돌려 봤다.**
> 초록불을 확인하는 것으로 끝냈으면 이 검사는 영원히 아무것도 안 잡았을 것이다.

### 부수: 재개도 코드가 바뀌면 기록한다
`--full` 은 이틀에 걸친다. 재개 시점의 코드가 다르면 거부하지 않되(이미 채점된 문항은
유효하다) `note` 에 `resume: 시작 … / 재개 …` 를 남기고 경고 로그를 찍는다.
**행이 아는 것보다 더 주장하지 않게** 하는 것이 목적이다.

### 검증
```
단위 641 통과 + 1 스킵  (629 → +12, test_build_identity.py)
통합  60 통과 + 1 스킵  (53 → +7: 배포 3 · 승격 게이트 4)
ruff clean · 마이그레이션 0005_build_id 적용

컨테이너 build 1353cb2a38c0 == 호스트 build 1353cb2a38c0
/healthz → {"app":"ok","db":"ok","queue":"ok","worker":"ok","build":"…"} (200)
```

`/healthz` 는 함정이 하나 있었다. 기존 코드가 `any(v != "ok" for v in report.values())`
로 503 을 정하는데, 여기에 `build` 를 그냥 넣으면 **모든 프로브가 503** 이 된다. 상태
판정은 컴포넌트 dict 만 보고, `build` 는 응답 본문에만 더한다. 더 많이 보고하기 시작해서
헬스체크가 죽는 것 — 그 자체가 거짓 신호다.

### 남은 것
- 기준선 127 은 `build_id` 가 NULL 이다(컬럼 이전에 측정됨). 비교는 정상 동작하므로
  급하지 않지만, **재승격하면 기준선도 코드 정체를 갖는다.** 사람이 정한다(BR-129)
- 이 구조는 `app`·`worker` 를 본다. `reranker` 는 프로파일 서비스라 제외했다 —
  꺼진 컨테이너는 낡은 코드를 서빙할 수 없다

---

## OPERATIONS — 기준선 재승격(코드 정체 포함) + `0001_base` 린트 (2026-08-31)

**승인 발언**: "남은것 진행해주세요"

### 순서를 구조가 정했다
`0001_base.py` 를 고치면 **소스 지문이 바뀐다.** 먼저 측정·승격하고 나중에 린트를
고쳤다면 방금 세운 기준선이 그 순간 낡은 코드의 것이 된다.

```
① 린트 수정 → ② 재빌드·재생성 → ③ 통합 60 통과 → ④ 측정 → ⑤ 승격
```
어제 만든 구조가 **작업 순서를 강제했다.** 절차를 기억해서 지킨 것이 아니라, 반대로
했으면 ⑤에서 거부당했을 것이다.

### ① 린트
```
python -m ruff check migrations/   → 1건 (0001_base.py, I001)
diff: 한 줄 이동 (pgvector < sqlalchemy). 의미 변화 0
```
u1 때부터 있던 것이고 **`migrations/` 를 린트 대상에 넣은 적이 없어서** 보이지 않았다.
`operations.md` 의 표준 명령을 `ruff check app/ tests/ migrations/` 로 고쳤다 —
범위에 없으면 통과하는 것이 아니라 **보지 않는 것**이다.

### ②③ 배포
```
app d983dcbbf1e1 == worker d983dcbbf1e1 == 작업 트리 d983dcbbf1e1
통합 60 통과 + 1 스킵 (배포 최신성 3건 포함)
```

### ④⑤ 재승격
```
실행 219   Recall@5 0.700 · MRR 0.529 · 거부 0.400 · 오거부 0.000 · 코드 d983dcbbf1e1
evaluate --promote 219 → 승격.  실행 127 자동 강등

기준선   10(full, 코드 미기록) · 219(retrieval_only, d983dcbbf1e1)
```

**기준선이 처음으로 코드 정체를 갖는다.** 127 은 `build_id` 가 NULL 이었다 — 컬럼
이전에 측정됐으므로 그것이 정직한 값이고, 이제 그 상태를 벗어났다.

가드가 도는 것도 확인했다:
```
실행 220 vs 기준선 219   전 지표 +0.000   판정 ok   종료코드 0
```

### 남은 것 — `full` 기준선
실행 10 은 코퍼스 78/1,633 기준이라 `--full` 실행은 계속 `incomparable` 로 돌아온다.
갱신하려면 **심판 할당량으로 이틀**이 든다. 지표를 올리는 일이 아니라 **비교 가능성을
되찾는 일**이고, 그 이틀 동안 답변 모델 할당량(하루 ~3질의)을 함께 쓴다 —
시작 여부는 사람이 정한다.

---

## OPERATIONS — `full` 기준선 갱신 완주 + 승격 (2026-09-01)

**승인 발언**: "full 기준선 갱신 시작해줘" → "16시 이후에 재개해줘" → "완주하면 승격해줘"

### 이틀에 걸친 실행, 설계대로
```
9/1 오전   14문항 채점 → 할당량 소진 → partial (종료코드 4)
9/1 16:0x  재개 1차 → 4문항 추가(18/30) → 다시 소진 → partial
9/1 16:3x  재개 2차 → 12문항 완주 → succeeded 30/30, 실패 0
```
할당량 리셋이 16시 정각에 완전하지 않다는 것이 다시 실측됐다(전 기록: 13:40 실패 →
16:10 성공). 재시도 로직이 그 간극을 흡수했다.

### 결과 — 실행 221, `full` 기준선으로 승격
```
                   실행 10 (구)     실행 221 (신)
코퍼스              78 / 1,633      82 / 1,697
코드                미기록           d983dcbbf1e1
Recall@5           0.700           0.700
MRR                0.546           0.529
정답률              0.792           0.870
인용 정확도          0.553           0.556
충실도              1.000           1.000
거부 정확도          0.600           0.400
오거부율            0.040           0.080
```
기준선 2개 모두 코드 정체를 가진다: **219(retrieval_only) · 221(full), 둘 다
d983dcbbf1e1.** 부분 표본에서 낮아 보이던 검색 지표(0.556/0.326)는 완주 시
검색전용 실측(0.700/0.529)에 정확히 수렴했다 — 채점 순서가 물질명 질의 구간을
지나는 동안의 착시였다.

### 지표에서 읽어야 할 것 — 좋아진 것과 나빠진 것을 같이 적는다
- **정답률 0.792 → 0.870.** 판정 모델과 코퍼스가 함께 바뀌었으므로 원인 분해는 불가
- **거부 정확도 0.600 → 0.400** (2/5). ref-03·04·05 가 임계값을 넘는다 — u4 때부터
  알려진 미해결(operations 10절 3번)이고 이번 실행이 재확인했다
- **오거부율 0.040 → 0.080** (sub-04·sub-06 이 `refused_unsupported`).
  물질명 질의 약세(3/8)와 같은 뿌리로 보인다 — 검색이 근거를 5위 안에 못 올리면
  임계값 미달로 거부된다. **결함으로 올리지 않고 기록한다**: 거부는 규칙대로
  동작했고, 문제는 검색 순위다(operations 10절 2번과 동일 원인)

### 모니터 스크립트에서 반복한 유형 ③ 한 건
1차 재개 예약이 `no configuration file provided` 로 죽었다 — 백그라운드 태스크의
작업 디렉터리가 저장소가 아니었다. 스크립트는 이것을 "할당량 미리셋 추정"으로
보고했다: **명령 불능과 할당량 소진을 구분하지 않았다.** 어제 배포 검사에서 잡은
것과 같은 유형을 감시 스크립트에서 반복했다. 고침: cd 실패 즉시 중단,
DB 조회 실패("확인 불가")와 할당량(출력 문구 확인)을 다른 답으로 분리.

### 상태
- `--full` 실행이 이제 `incomparable` 없이 판정된다 — **비교 가능성 회복**이 이
  작업의 목적이었다
- 실행 10 은 자동 강등. 이력에 남는다

---

## OPERATIONS — 물질명 검색 개선 (BR-65a) (2026-09-01)

**승인 발언**: "물질명 검색 개선 진행해줘"
**결과**: Recall@5 **0.700 → 0.833** (+4문항) · MRR **0.529 → 0.609** · 재색인 0회 · LLM 0콜

### 진단 — 추측이 아니라 구조를 찾았다
u4 실측의 비대칭(CAS 질의 3/3, 물질명 질의 0/5)의 원인 셋:
1. **`substance_names` 는 만들어지고 소비되지 않았다.** BR-65 가 동의어를 정규화해
   `QueryIntent` 에 담는데, grep 결과 정의·직렬화 지점뿐 — 읽는 검색 경로가 없었다.
   `doc_type_hint` 와 같은 사문화인데 이쪽은 5문항 0.000 이라는 실비용이 있었다
2. **물질 청크에는 물질명이 없다.** 황산 흡입 청크는 "·심각한 기도 자극…"뿐,
   이름은 마스터에만 있다. 텍스트·벡터 어느 쪽도 이름과 청크를 잇지 못한다.
   CAS 만 `chunk.meta['cas_number']` 정확일치로 뚫린다 (49레코드 × 7청크 전부 보유)
3. **"메탄올"은 동의어 테이블에 없다.** BR-99("출처가 싣는 이름만")대로 소스가
   메틸알코올만 준다 — 규칙은 옳고, 질의 쪽이 비어 있었다

### 3단 수정 — 각 단은 그 앞 단의 실측이 요구했다

**① 이름 → CAS → 기존 정확일치 경로 (BR-65a)**
`Retrievers._cas_for_names`: 해석된 이름을 마스터에서 CAS 로 바꿔, 타이핑된 CAS 가
쓰는 바로 그 `lookup_exact` 에 태운다. + `config/query_aliases.yaml`(질의 전용 별칭,
메탄올→메틸알코올 — DB 미저장, 카드 미노출, BR-99 그대로).
→ 실행 238: 0.767. sub-03·05 회복, **msds-01 1.000→0.000 회귀** (7청크가 전부
1.0 으로 밀고 들어와 MSDS 근거를 밀어냄), sub-02·06·08 여전히 0 (동점 7청크의
임의 순서 — 정답 섹션이 5위 밖)

**② 경로 섹션 우선 + 상한 3**
질의의 노출경로 단어(흡입/눈/피부/삼킴)로 섹션 동점을 깨고, 이름 해석 히트를
상위 3개로 제한한다. 타이핑된 CAS(BR-38)는 명시적 요청이므로 무제한 유지.
→ 실행 239: 0.800. **msds-01 회귀 치유**, sub-08 회복. sub-02·06 여전히 0 —
회수 목록을 보니 **상위 4건이 전부 다른 물질의 같은 섹션**: "눈·손상" 같은
경로 단어가 49종 전체를 양 경로에서 점화시켜, 두 경로 합산(RRF)이
한 경로짜리 정확일치를 구조적으로 이긴다

**③ 주제 보장 `ensure_subject_presence` — BR-69 와 대칭**
사용자가 지목한 물질(타이핑 CAS·해석된 이름 공통)의 청크가 상위 5에 없으면
풀에서 최선 하나를 인상한다. 식별은 BR-38 이 "하류가 구분하라"고 만들어 둔
`EXACT_MATCH_SCORE` 마커 그대로. 실제 히트가 있어야만 인상한다(NFR-8).
→ 실행 240: **0.833 / 0.609**. sub-06 회복. sub-07(CAS)이 분산 운으로 5위였던
것도 원칙이 됐다

### 남은 것 — 멈춘 이유를 적는다
- **sub-02 만 0 이 남았다.** 상위 5건에 황산이 **둘** 있다(증상 섹션 1위 + 황산
  MSDS). 질문이 "흡입하면 어떤 **증상**이"라서 벡터가 증상 섹션을 1위로 올렸고,
  골든셋은 흡입 섹션만 인정한다. 검색 실패가 아니라 **골든셋 근거 판정 문제**일
  수 있다 — sub-07 전례대로 골든셋은 수정하지 않고 사람 판단으로 남긴다(R-5).
  기계적으로 더 밀면 한 물질이 5칸 중 3칸을 차지하는 지표 과적합이다
- law-07·08·09, msds-02 의 0 은 기준선에서도 0 — 이 작업 범위 밖
- 부작용 잔여 1건: msds-03 MRR 0.500→0.333 (Recall 1.000 유지, 한 칸 밀림)
- `meta.substance_names` 는 1,697청크 전부 빈 배열 — 색인이 쓰지 않는 필드를
  만들어 둔 것. 이번 수정은 그것 없이 성립하므로 손대지 않았다

### 검증
```
단위 656 통과 + 1 스킵 (+12: 별칭 3 · 경로 추론 6에서 7 · 주제 보장 5)
통합  66 통과 + 1 스킵 (+6: 이름 질의 4종 키워드 도달 + 별칭 파일 정직성)
ruff clean · 배포 = 작업 트리 · 판정 ok (회귀 없음)
문항별: 개선 5 (sub-03·05·06·08 R 0→1, msds-02 는 238에서만) / 악화 0 / MRR 한 칸 1
```

### 기준선은 승격하지 않았다
0.833 은 후보다. BR-129 대로 사람이 올린다.

---

## OPERATIONS — 검색전용 기준선 승격: 실행 240 (2026-09-01)

**승인 발언**: "승격해주세요"

```
evaluate --promote 240 → 승격 (게이트 통과: 측정 코드 f35850dcd83f == 배포 코드)
실행 219 자동 강등

기준선   221(full,           d983dcbbf1e1, R@5 0.700 · MRR 0.529)
        240(retrieval_only, f35850dcd83f, R@5 0.833 · MRR 0.609)
승격 직후 재실행 → 전 지표 +0.000 / 판정 ok
```

두 기준선의 검색 지표가 이제 **의도적으로 갈라져 있다**: 240 은 BR-65a 이후,
221 은 이전 코드의 측정이다. `--full` 기준선은 코퍼스·모드가 같아 `incomparable`
은 아니지만, 다음 `--full` 완주 때 갱신하는 것이 맞다(심판 할당량 하루치)고
승격 보고에 적었다.

---

## OPERATIONS — 골든셋 판단(B·B) + 문서 20·24 두 컬럼 구원 (2026-09-01)

**승인 발언**: "권장안대로 B 유지하고 문서 20 재파싱 진행해줘"

### 골든셋: 둘 다 B (현행 유지)
sub-02·sub-07 근거 무변경. 판단 자료와 결정은
`operations/golden-set-judgment-sub02-sub07.md`. `golden_set_hash` 불변 —
기준선 비교 가능성 유지.

### 진단 — BR-20a 가 옳게 거부한 것을 추출에서 살렸다
문서 20(황산·남해화학)·24(톨루엔·한화토탈)는 **두 컬럼 조판**이다. pypdf 가
오른쪽 컬럼을 먼저 읽어 헤더 16개가 전부 인식되고도 순서가 뒤집힌다:
```
문서 20   순서 2,1,4,3,6,5,8,7,11,10,9,…   역전 8
문서 24   순서 2,1,3,4,…,16                역전 1
```
BR-20a 의 강등(틀린 라벨보다 무라벨)은 옳았다. 고칠 것은 판정이 아니라
**추출 순서**였다 — u1 이 "2 of 8" 로 측정해 두고 강등으로 봉인한 그 두 문서다.

### 구현 — 실패를 트리거로, 기하학은 구원에만
1. `extract_pdf_columns`: 좌표 기반 컬럼 분리. 두 컬럼으로 판정된 페이지만
   재구성, 단일 컬럼 페이지는 pypdf 원출력 그대로
2. `PipelineRunner._retry_two_column`: **1차 구조화가 실패한 PDF 만** 재추출,
   **재시도가 구조화에 성공할 때만** 채택. 실패 시 기존 결과(BR-28 비구조화
   색인) 그대로 — 나빠질 수 없는 구원

기하학을 1차 경로로 쓰지 않는 이유는 실측이다: 전수 건식 검증에서
`autorefinishes-ps220` 가 **역전 0→2 로 악화**했다 — 표 많은 페이지를 두 컬럼으로
오판한다. 건강한 10건은 1차에서 구조화되므로 이 코드에 도달하지 않고,
텍스트가 바이트 단위로 불변임을 같은 검증으로 확인했다.

> 시제품의 첫 판은 페이지를 한 줄로 이어붙여 `^` 앵커를 죽였고(인식 0),
> 전수 검증 없이 통합했다면 autorefinishes 악화를 몰랐을 것이다.
> **검사 전수 실측이 이번에도 두 번 값을 했다.**

### 결과
```
문서 20·24: unstructured 9·8청크 → structured 16·16청크 (extractor pypdf-columns)
코퍼스 82문서 · 1,697 → 1,712청크

카드   황산 결측 7→0 · 톨루엔 결측 6→0   분포 {0:4,1:2,2:1,6:41,7:1} → {0:6,1:1,6:41,7:1}
검색   Recall@5 0.833 → 0.867 · MRR 0.609 → 0.630
       law-07 0→1.000 (비구조화 청크가 오염시키던 자리) · msds-01 MRR 0.5→1.0
       악화: msds-03 MRR 한 칸 (Recall 유지)
```

### 틀린 예측을 그대로 적는다
판단 문서에 "sub-02 의 근본 개선 경로는 문서 20 재파싱"이라 썼는데 **틀렸다** —
sub-02 는 여전히 0.000 이다. 병목은 문서 20 이 아니라 물질 레코드 간 순위
경쟁(황산 inhale 이 다른 물질들의 inhale 에 밀림)이고, 재파싱의 이득은 카드와
law-07·msds-01 에서 났다. 남은 0: law-08·09, msds-02, sub-02.

### 검증
```
단위 660 통과 + 1 스킵 (+4 test_pdf_columns) · 통합 66 통과 + 1 스킵 · ruff clean
배포 == 작업 트리 · 판정 incomparable (코퍼스 변경 — 옳은 동작)
```

### 기준선
코퍼스가 바뀌어 실행 258 은 기준선 240 과 `incomparable`. **재승격은 사람이**(BR-129).
후보: 검색전용 258 (0.867/0.630). `full` 221 도 구 코퍼스가 됐다.

---

## OPERATIONS — 검색전용 기준선 승격: 실행 258 (2026-09-02)

**승인 발언**: "검색전용만 먼저 승격해주세요"

```
evaluate --promote 258 → 승격 (게이트 통과: fcedc13a361a == 배포)
실행 240 자동 강등 · 승격 직후 재실행 → 전 지표 +0.000 / 판정 ok

기준선   221(full,           d983dcbbf1e1, 코퍼스 1,697, R@5 0.700 · MRR 0.529)
        258(retrieval_only, fcedc13a361a, 코퍼스 1,712, R@5 0.867 · MRR 0.630)
```

**두 기준선이 코퍼스·코드 모두 다른 시점을 가리킨다** — 사용자가 "검색전용만
먼저"로 명시 선택한 상태다. `--full` 실행은 221 대비 `incomparable` 로 돌아온다
(코퍼스 1,697 vs 1,712). 다음 `--full` 완주(심판 하루치)가 221 을 갱신할 때까지
그 경고가 유지되며, 그것이 옳은 동작이다.

---

## OPERATIONS — `full` 완주 + 기준선 221 → 276 갱신 (2026-09-02)

**승인 발언**: "full 완주하고 221 갱신해줘" (완주 조건부 승격 사전 승인, "그렇게 해")

### 완주 — 하루 안에 6구간
```
14:32 시작 → 9 → 10 → 10 → 17 → 20 → 30/30 (17:4x, succeeded, 실패 0)
심판 25콜이 리셋 구간(15~16시대)을 걸쳐 소화됐다. 30분 간격 자동 재개 6회
```

### 승격 — 두 기준선이 다시 같은 시점을 가리킨다
```
기준선   258(retrieval_only) · 276(full)
        둘 다 코퍼스 1,712 · 코드 fcedc13a361a
221 자동 강등. full 가드의 incomparable 해소
```

### 실행 276 vs 구 221 — 참고용 (코퍼스·코드가 다르므로 원인 분해 불가)
```
Recall@5   0.700 → 0.867   MRR    0.529 → 0.630     ← BR-65a + 문서 20·24 구원
정답률      0.870 → 0.917   인용    0.556 → 0.610
오거부율    0.080 → 0.040   (sub-04·06 오거부가 BR-65a 로 해소된 것과 일관)
충실도      1.000 → 0.958   ← 유일한 하락. law-09 단독 (판정: 부정확+불충실)
거부 정확도  0.400 그대로   (ref-03·04·05 — 기지 미해결)
```
충실도 0.958 은 24문항 중 1건(law-09)이다. law-09 는 검색 자체가 0(기지 잔여
4건 중 하나)이라 약한 근거로 답을 만들다 불충실 판정을 받은 것으로 보인다 —
**새 회귀가 아니라 기지 검색 공백의 하류 증상**이다. 다음 검색 개선 후보.

### 검증
```
승격 게이트 통과 (fcedc13a361a == 배포) · 실패 0 · LLM 119콜
```

---

## OPERATIONS — law-08·09 검색 개선: 조문 제목 층 (2026-09-02)

**승인 발언**: "law-08·09 검색 개선 진행해줘"
**결과**: Recall@5 **0.867 → 0.933** · MRR **0.630 → 0.708** · **Recall 회귀 0**

### 진단
둘 다 "맞는 법령의 옆 조문"이 뜨는 근접 실패였고, 근인은 달랐다:
- **law-09**: 정답 제43조가 키워드로 **도달 불가**. 'simple' 설정은 어간 처리가
  없어 색인 토큰이 "공정안전보고서**의**"로 저장되고, 조사를 뗀 질의 토큰
  "공정안전보고서"와 정확일치가 영영 안 된다. 실측: plain 13청크 / prefix 29청크,
  정답은 prefix 로만 잡힌다 — u2 가 질의 쪽만 고친 문제의 **색인 쪽 절반**
- **law-08**: 도달은 되나(게시 plain 일치) 순위 밀림

### 다섯 번 실측하고 다섯 번 버렸다 (실행 277~282)
| 변형 | 결과 |
|---|---|
| 전 용어 prefix | law-08 회복, **inc-01·law-04 1.0→0** |
| 3글자+ 게이트 | law-04·msds-03 상실 |
| 4글자+ 게이트 | 동일 (MRR 은 최고 0.682) |
| ×0.5 할인 2층 | **regression 판정** — 할인 점수가 plain 대역과 겹쳐 4문항 회귀 |
| 위치 분리+예약석/순수추가 | law-03 상실 또는 무이득 |

**본문 ts_rank 재편은 제로섬이다.** OR-공통어 빈도는 약한 순위 신호라 어떤
재편이든 한계 문항을 맞바꾼다. 20초짜리 무료 측정이 있었기에 다섯 번 버리는
비용이 쌌다 — 이것이 u4 를 먼저 지은 값이다.

### 채택 — 조문 제목 층
법령 질문은 조문 **제목**을 바꿔 말한 것이다:
```
law-08 "…어떻게 관리해야"        → 제114조 (물질안전보건자료의 게시 및 교육)
law-09 "…제출해야 하는 업종"      → 제43조 (공정안전보고서의 제출 대상)
```
`meta.section_title` LIKE 부분일치 — 조사 문제가 구조적으로 없다. 5글자+ 복합명사만
참여(짧은 어간은 수십 제목에 있어 재편 재발), 상한 5(BR-65a 홍수 교훈), 점수 0.3
(식별자 1.0 과 본문 0.03~0.10 사이 — 제목 일치는 빈도보다 강하고 식별자보다 약하다).

### 문항별 (258 → 283)
```
law-08  0 → 1.000 (MRR 1.0, 1위)     law-09  0 → 1.000 (5위)
law-06·07·10  MRR → 1.000
악화: law-03·04·05 MRR 한 칸 (Recall 전부 유지)
남은 0: msds-02·sub-02 (기존, 범위 밖)
```

### 검증
```
단위 660 통과 + 1 스킵 · 통합 70 통과 + 1 스킵 (+4 title 층) · ruff clean
코퍼스 불변(1,712) — 기준선 258 과 비교 가능, 판정 ok
```

### 기준선은 승격하지 않았다
실행 283(0.933/0.708)이 후보다. BR-129 — 사람이 올린다.

---

## OPERATIONS — 검색전용 기준선 승격: 실행 283 (2026-09-02)

**승인 발언**: "승격"

```
evaluate --promote 283 → 승격 (게이트 통과: e0f763d6cb27 == 배포)
실행 258 자동 강등 · 재실행 → 전 지표 +0.000 / 판정 ok

기준선   276(full,           fcedc13a361a, R@5 0.867 · MRR 0.630)
        283(retrieval_only, e0f763d6cb27, R@5 0.933 · MRR 0.708)
```

두 기준선의 검색 지표 차이(0.933 vs 0.867)는 코드만의 차이다 — 코퍼스·골든셋이
같아 비교 자체는 유효하고, `full` 재완주는 불필요하다. 다음 `--full` 을 돌릴
일이 생기면 그때 276 이 자연히 따라온다.

---

## OPERATIONS — msds-02 검색 개선: 질의 주제→MSDS 섹션 지도 (2026-09-02)

**승인 발언**: "msds-02 검색 개선 진행해줘"
**결과**: Recall@5 **0.933 → 0.967** · MRR **0.708 → 0.766** · 회귀 0
**남은 검색 0 은 sub-02 하나 — 골든셋 B 결정으로 의도 유지 중인 그 문항이다.**

### 진단 — 이전 수정의 그림자였다
"황산은 어떻게 저장해야 하나요"의 상위에 문서 20 의 **법적규제(15)·참고사항(16)·
환경영향(12)** 이 1.0 으로 떠 있었다. 경위:
1. BR-65a 의 이름 인상은 `meta.cas_number` 로 청크를 고른다
2. 재파싱된 황산 MSDS(문서 20)의 16청크도 같은 CAS 를 달고 있다 (합계 23청크)
3. "저장"은 노출경로 지도에 없어 우선순위 동점 → **행 순서로 임의 선발**
4. 잡섹션이 정확일치 점수를 달고 상위를 점령, 정답(koreachem msds_07)은 밀림

문서 20 재파싱(카드를 고친 그 작업)이 이 조합을 만들었다 — 비구조화 시절엔
선발할 섹션 자체가 없었다. **개선은 다른 개선의 전제를 바꾼다.**

### 수정 둘
1. **질의 주제 → MSDS 섹션 지도** (`_MSDS_TOPIC_PATTERNS`): 저장·보관·취급→07,
   보호구·노출기준→08, 응급→04, 화재→05, 누출→06, 폐기→13, 운송→14, 물리화학→09.
   노출경로 지도(substance_*)의 MSDS 쪽 절반이다 — 저장 정보는 물질 레코드에
   아예 없으므로 이 지도 없이는 정답 섹션이 지목될 수 없었다
2. **무일치 청크는 인상하지 않는다**: 주제·경로·폴백 어디에도 못 낀 청크는
   임의 동점으로 선발하지 않는다. **임의 인상은 작은 정답이 아니라 정확일치
   점수를 뒤집어쓴 소음이다**

### 문항별 (300 → 333)
```
msds-02  0 → 1.000 (1위, MRR 1.0)
msds-03  MRR 0.250 → 1.000   ← 보너스: "노출기준"→msds_08 지도
악화 0
```

### 부수: 테스트가 제 결함을 먼저 잡혔다
`test_no_topic_lifts_no_junk` 첫 판은 **인상(1.0)과 정상 텍스트 매칭(0.03~0.1)을
구분하지 않고** 잡섹션 존재만 검사해 실패했다 — 잡섹션이 "황산" 텍스트 일치로
정당하게 들어온 것까지 오탐. `min_score=1.0` 로 인상만 검사하도록 고쳤다.
유형 ③을 테스트 안에서 반복한 셈이다.

### 인프라 잡음 1건 (기록만)
측정 중 Docker Desktop 이 재시작해 API 500·전 컨테이너 재기동·호스트 5433
프록시 단절이 있었다. 컨테이너 내부 경로는 무사했고, `postgres` 재시작으로
프록시 복구. 재기동 후 **배포 정체 확인부터** 했다(042322be1757 == 작업 트리) —
결함 58 의 구조가 절차로 자리잡았다.

### 검증
```
단위 668 통과 + 1 스킵 (+8) · 통합 72 통과 + 1 스킵 (+2) · ruff clean
코퍼스 불변(1,712) · 판정 ok · 기준선 283 대비 회귀 0
```

### 기준선은 승격하지 않았다
실행 333(0.967/0.766)이 후보다. BR-129.

---

## OPERATIONS — 검색전용 기준선 승격: 실행 333 (2026-09-02)

**승인 발언**: "승격해주세요"

```
evaluate --promote 333 → 승격 (게이트 통과: 042322be1757 == 배포)
실행 283 자동 강등 · 재실행 366 → 전 지표 +0.000 / 판정 ok

기준선   276(full,           fcedc13a361a, R@5 0.867 · MRR 0.630)
        333(retrieval_only, 042322be1757, R@5 0.967 · MRR 0.766)
```

### u4 착수 이래 검색 지표 이력
```
0.667  u4 최초 측정 (MSDS 4건 추가 직후)
0.700  doc_type 세분화 (물질/MSDS 분리, BR-69 가 둘을 가를 수 있게)
0.833  BR-65a 물질명 검색 (이름→CAS→정확일치 + 경로 섹션 + 주제 보장)
0.867  문서 20·24 두 컬럼 구원 (BR-20a 가 옳게 거부한 것을 추출에서 복구)
0.933  조문 제목 층 (law-08·09)
0.967  질의 주제→MSDS 섹션 지도 (msds-02)
```
**골든셋은 한 번도 고치지 않았다.** 지표는 전부 검색이 실제로 옮긴 것이고,
sub-02 의 0.000 은 B 결정에 따라 의도적으로 남아 있다.

거부 정확도 0.400 은 이 여섯 단계 내내 불변이다 — 검색과 무관한 미해결(10절 3번).

---

## OPERATIONS — 거부 정확도 개선: BR-73a 주제 없는 물질 근거 (2026-09-02)

**승인 발언**: "거부 정확도 개선 진행해줘"
**결과**: 거부 정확도 **0.400 → 1.000** · 오거부 **0.000 유지** · 검색 지표 불변

### 이것은 지표 문제가 아니라 안전 문제였다
실패한 세 문항이 무엇을 하고 있었는지 실측했다.
```
ref-04 "카드뮴의 급성 독성 기준은?"   → 톨루엔·염소 등의 msds_11(독성정보)로 답변
ref-05 "벤젠에 노출되면 응급조치는?"  → 다른 물질들의 msds_04(응급조치)로 답변
카드뮴·벤젠은 마스터에도 코퍼스에도 없다.
```
**한 물질의 독성·응급조치 자료를 다른 물질의 것으로 제시하고 있었다.** 이 시스템이
낼 수 있는 최악의 실패이고(R-6), 침묵보다 나쁘다 — 답처럼 보이기 때문이다.

### 임계값으로는 불가능하다 — 측정으로 확정
```
ref-05 (거부해야 함)   0.631
msds-02 (답해야 함)    0.627   ← 더 낮다
ref-04 0.586 · ref-03 0.512 · law-08 0.738 · ref-01 0.411
```
**어떤 임계값도 ref-05 를 잡으면 msds-02 를 죽인다.** 점수가 재는 것은 주제이고
두 질문의 주제는 같다 — 결함 27(RRF 점수를 임계값으로 읽음)과 같은 모양, 한 축 옆.

### BR-73a — 주제(subject)로 가른다
다른 것은 **주제**다. MSDS·물질 레코드는 *한 물질에 관한 문서*다. BR-38 의
정확일치 단축(타이핑 CAS 또는 BR-65a 로 해석된 이름)이 먼저 반환하므로, 이 줄에
도달했다는 것은 **지목된 물질이 없다**는 뜻이다. 그때 최상위 후보가 물질 범위
문서면 거부한다.

**`all()` 이 아니라 최상위 후보로 판정한다.** 처음엔 `all()` 로 짰고 ref-05 가
살아남았다 — BR-69 타입 분산이 제90조 청크를 5위로 끌어올려 조건을 깼다.
**분산 규칙이 거부 규칙을 구조적으로 무력화한다**: 스프레드 후보는 답해서가 아니라
구성상 거기 있다. 0.800 → 1.000 은 이 한 줄의 차이다.

법령·사고 문서는 제외한다: "사업주는 물질안전보건자료를 어떻게 관리해야"는 물질을
지목하지 않고 지목할 필요도 없다. 사용자 업로드도 제외 — 남이 올린 문서가 무엇인지
우리가 선언할 수 없고, 자기 문서를 되돌려 거부하는 것은 이 트레이드의 반대편이다.

### 대가를 골든셋 밖에서 측정했다 — 숨기지 않는다
거부 문항이 5건뿐이라 과적합 위험이 실재한다. 별도 프로브를 돌렸다.
```
거부  카드뮴 급성 독성            ← 의도한 것
거부  벤젠 응급조치               ← 의도한 것
거부  "MSDS 는 몇 개 항목인가요?"   ← 대가
거부  "보호구는 어떻게 선택하나요?" ← 대가
답변  법령 일반 2건 · 사고 사례 · 황산 저장
```
**물질을 지목하지 않은 일반 MSDS 질문 2건이 거부된다.** 코퍼스 빈도로 가르려
했으나 실패했다(카드뮴 2 · 벤젠 10 · "선택" 5 — 물질명이 일반어보다 흔하다).
LLM 없이 물질명 여부를 판별할 수단이 없으므로 이것은 **제거 가능한 결함이 아니라
트레이드**다.

그래서 거부 문구를 막다른 길이 아니라 **되묻기**로 썼다:
> "어떤 물질에 대한 질문인지 확인하지 못했습니다. 물질명이나 CAS 번호를 함께
> 적어 주시면 해당 물질의 자료로 답변합니다."

물질명을 덧붙이면 즉시 답이 되고, 근거 링크는 BR-75 대로 함께 나간다.

### 부수 — 문구 지도가 두 곳에 있었다
SSR(`pages.py`)과 스트리밍 클라이언트(`query.js`)가 각자 `REFUSAL_TEXT` 를 들고
있다. 서버만 고쳤다면 스트리밍 경로는 조용히 일반 문구로 떨어졌을 것이다. 둘을
고치고 **두 지도가 모든 `RefusalReason` 을 담는지 검사하는 단위 테스트**를 넣었다
(임포트 없이 텍스트 파싱 — NFR-28).

### 기존 테스트 3건이 깨진 것은 옳은 신호였다
`TestRefusalUsesRelevanceNotRank` 픽스처가 `doc_type=MSDS` 기본이라 전부 거부됐다.
그 테스트들의 의도는 "RRF 아닌 관련도가 결정한다"로 BR-73a 와 무관하므로 픽스처
기본값을 LAW 로 바꿨다 — **픽스처가 결정을 대신하지 않게** 하는 것이 목적이고,
통과시키려는 조정이 아니다. 프로브가 말한 것과 같은 얘기를 테스트가 먼저 했다.

### 검증
```
단위 676 통과 + 1 스킵 (+8) · 통합 72 통과 + 1 스킵 · ruff clean
코퍼스 불변 · 배포 03bab957bade == 작업 트리 · 판정 ok
```

### 기준선은 승격하지 않았다
실행 385(거부 1.000)가 후보. BR-129.

---

## OPERATIONS — 검색전용 기준선 승격: 실행 385 (2026-09-02)

**승인 발언**: "승격"

```
evaluate --promote 385 → 승격 (게이트 통과: 03bab957bade == 배포)
실행 333 자동 강등 · 재실행 386 → 전 지표 +0.000 / 판정 ok

기준선   276(full,           fcedc13a361a, R@5 0.867 · MRR 0.630 · 거부 0.400)
        385(retrieval_only, 03bab957bade, R@5 0.967 · MRR 0.766 · 거부 1.000)
```

### 검색전용 기준선이 지키는 것 (u4 착수 대비)
```
Recall@5     0.667 → 0.967      MRR   0.529 → 0.766
거부 정확도    0.400 → 1.000      오거부  0.000 유지
골든셋 무수정 · 코퍼스 82문서 1,712청크
```

### `full` 276 은 이제 세 세대 뒤처졌다
조문 제목 층·MSDS 주제 지도·**BR-73a** 이전 코드다. 앞의 둘은 검색만 바꿨지만
BR-73a 는 **답변 경로의 동작을 바꾼다** — 거부가 늘면 정답률·인용·충실도의 분모가
달라진다. `--full` 재완주(심판 하루치)의 가치가 이전 두 번보다 크다.

---

## OPERATIONS — 저장소 이전 + GitHub Actions CI (2026-09-02)

**승인 발언**: "data/ 넣어주세요. aidlc-docs/포함 좋습니다" → "B로 진행하고 내일 실행 재개 설정해주세요"

### 왜 옮겼나 — 결함 58 의 재발 방지
`safeenv/`(작업·Docker)와 `chemical_safe/`(깃 저장소)가 따로 있으면 **CI 가 실제로
도는 코드가 아닌 것을 검사한다.** 테스트가 도는 코드 ≠ 서비스가 도는 코드,
결함 58 과 정확히 같은 모양이다. 사용자가 B(작업을 저장소로 이전)를 선택했다.

### 이전 — DB 는 명명 볼륨이라 그대로 넘어갔다
```
이전 전 확인   지문 3곳 일치 (safeenv · chemical_safe · 컨테이너 = 03bab957bade)
.env · docker-compose.override.yml 복사 (둘 다 .gitignore 대상 — 커밋 안 됨)
logs/ · backups/ 생성

이전 후   바인드 마운트 C:\Users\403\IDE\chemical_safe\data\originals ✅
         DB 문서 82 · 청크 1,712 · 실행 387 partial · 기준선 276·385 전부 보존
         /healthz 200 · build 03bab957bade == 작업 트리
         통합 72 통과 + 1 스킵
```
compose 의 `name: safeenv` 덕분에 컨테이너·볼륨 이름이 유지돼 **데이터 이관 작업이
아예 없었다.** 프로젝트 이름을 경로에서 유추하지 않도록 고정해 둔 것이 값을 했다.

> **이전 중 실수 1건**: `cd` 를 빠뜨려 옛 경로에서 한 번 기동했다. 에코는
> "chemical_safe 에서 기동"이라고 출력했지만 실제로는 아니었다. `docker inspect`
> 의 바인드 마운트 경로로 잡았다 — **명령이 무엇을 했다고 말하는 것과 실제로 한
> 것은 다르다.** 이 세션에서 같은 교훈이 세 번째다(결함 58 · 검증 스크립트가 파일
> 0개 검사 · 이번).

### CI — 측정이 설계를 정했다
```
깨끗한 venv, ml 엑스트라 없음 (torch·sentence_transformers 미설치)
  → 단위 677 통과 / 10초 · ruff clean · 자격증명 0 · DB 0 · 네트워크 0
```
NFR-28("단위 테스트는 DB·네트워크·모델에 닿지 않는다")이 CI 를 1분짜리로 만든다.
설계 시점의 규칙이 여기서 값을 한다.

부수 측정 둘:
- **CI 가 개발 호스트보다 테스트를 하나 더 돌린다** — 호스트에 `arq` 가 없어
  `importorskip` 으로 건너뛰던 테스트가 깨끗한 환경에서는 실행된다 (676+1skip → 677)
- **`pip install -e .` 는 실패한다** — 최상위 디렉터리가 여럿이라 setuptools 자동
  탐색이 안 된다. Dockerfile 이 의존성만 뽑아 설치하는 이유가 이것이다. CI 도
  같은 방식이라 `pyproject.toml` 을 건드릴 필요가 없었다 — **건드렸다면 빌드
  지문이 바뀌어 내일 실행 387 승격이 막혔을 것이다**(pyproject 는 TRACKED 다)

### 넣지 않은 것 — 이유와 함께
| 항목 | 이유 |
|---|---|
| 통합 테스트 72건 | 실제 코퍼스(82문서·1,712청크) 전제. CI 에서 채우려면 재색인 35분 + 모델 2GB 가 매번 |
| 평가 하네스 | 같은 이유 + LLM 할당량 |
| **CD** | **배포 대상이 없다.** `127.0.0.1` 바인딩은 의도된 설계다(NFR-18). 없는 배포처를 위한 파이프라인은 형식만 남는다 |

### 워크플로 검증 — YAML 파싱으로 끝내지 않았다
`run:` 블록 안의 heredoc 은 YAML 블록 스칼라의 들여쓰기 제거와 상호작용한다.
파일에서 해당 스텝을 **추출해 실제로 실행**해 `ci-requirements.txt` 22줄이 나오는
것을 확인했다. 이 프로젝트가 이스케이프로 반복해 데인 지점이다.

### 남은 것
- `safeenv/` 는 백업으로 남긴다. 스택이 가리키지 않으므로 혼동 방지를 위해
  완주·승격 확인 후 정리를 권한다
- 내일 재개 예약을 `chemical_safe` 경로로 재생성했다 (작업 c60d6120)

---

## OPERATIONS — 커밋 계획 (2026-09-02)

**승인 발언**: "내일부터 커밋을 하루에 10개씩 해서 올릴수 있게 세팅해주세요"

### 착수하며 발견한 상태
```
95677a9  2026-09-02 19:18  "msds관련 안전 조사:"  392파일 1커밋
origin/main = 95677a9 — 이미 푸시됨 (사용자가 직접)
푸시된 트리 재확인: .env·override·logs·캐시 0건
```

### 무엇을 만들었나
`operations/backlog.md` — **각 항목이 커밋 하나가 되도록 크기를 맞춘 실행 목록.**
A 진행 중(2~3) · B 보안(8~12) · C 품질(6~10) · D 정리(5~8) = **25~35커밋**.
우선순위는 측정된 영향이 정하고, 지표를 움직이지 않는 항목은 그렇다고 적었다.

커밋 규약도 함께 적었다: 무엇을 측정했고 지표가 어떻게 움직였는지를 본문에 쓴다.
움직이지 않았으면 그것도 쓴다.

### 하지 않기로 한 것
**빈 커밋 · 커밋 수를 맞추기 위한 인위적 분할 · `GIT_AUTHOR_DATE` 소급.**
이력은 실제로 한 일을 적는 곳이다. 하루 10커밋은 목표가 아니라 백로그를 소화하는
속도의 결과여야 한다 — 재료가 없는 날은 10개가 안 나온다.

### 초기 커밋 분할은 권하지 않았다
392파일 한 커밋을 40~60개로 쪼개려면 **푸시된 이력 재작성 + force 푸시**가 필요하다.
개인 저장소라 위험은 낮지만 되돌릴 수 없고, 앞으로의 작업만으로 25~35커밋이 나온다.
사용자가 원하면 별도 지시로 진행한다(백로그 E4).

### 부수 정리
`operations.md` 10절의 중복 항목 5번(문서 20·24 재파싱, 4b 로 이미 수행)을 정리하고,
10절에서 백로그로 가는 링크를 걸었다.

---

## OPERATIONS — 첫 커밋 배치일 (2026-09-03)

**승인 발언**: "내일 첫 배치 시작해줘" + "지금 미커밋 5개도 내일 배치에 포함해줘"

### 결과: 4커밋. 10개가 아니다 — 이유가 있다
```
5ce48f5  docs: 저장소 이전·CI·커밋 백로그 기록
9f6e2c5  docs: 익명 노출면에 /api 추가
7552c03  docs: 줄바꿈이 빌드 지문을 바꾼다는 실측 기록
(+ 본 기록)
```

### 체인이 심판 할당량 하나에 묶여 있었다
```
16:07 재개 → 5/30 → 27/30 (리셋 통과, 심판 20콜)
16:46 재개 → 27/30 진전 없음
오늘 심판 사용량 정확히 20 = 문서화된 일일 한도. 남은 3문항(law-07·msds-01
·sub-07)은 전부 답변형이라 심판 3콜이 더 필요하다.
```
재시도 4회가 남아 있었지만 **소진이 확인된 이상 무의미**하므로 중단했다.
30분마다 실패를 반복하는 것은 인내가 아니라 낭비다.

그리고 이것이 오늘 전체를 막았다:
- A(평가) — 완주 불가 → 승격 불가
- B(관리 화면 인증) — `app/` 을 고치면 빌드 지문이 바뀌어 **내일 승격이 막힌다**.
  이틀치 할당량이 들어간 실행을 지키려면 손대지 않는 것이 맞다
- C(코퍼스) — 수집은 `corpus_fingerprint` 를 바꿔 진행 중인 실행을 오염시킨다
- D3(패키징) — `pyproject.toml` 이 지문에 포함된다

**남은 것이 문서뿐이었다.** 10커밋은 목표가 아니라 결과여야 한다고 적어 뒀고,
오늘이 그 원칙이 실제로 값을 치른 날이다. 빈 커밋으로 채우지 않았다.

### 오늘 확인한 것 — CI 가 실제로 돈다
```
GitHub Actions API: CI success · Docker build success (95677a9)
```
어제 워크플로를 넣고 푸시했지만 결과를 본 적이 없었다. 통과를 **확인**했다.

### 오늘 찾은 것 — 줄바꿈이 빌드 지문을 바꾼다
D4(`.gitattributes`)가 단순 정리인 줄 알았는데 아니었다. `core.autocrlf=true`
이고 작업 트리가 혼재(app/ LF, pyproject.toml CRLF)라, LF 113파일이 CRLF 가 되면
지문이 `03bab957bade` → `7b008836585f` 로 바뀐다. **체크아웃 한 번이 코드를 안
고치고 승격을 막는다.**

내가 만든 빌드 지문 설계(원시 바이트 해싱)의 대가다. 설계는 여전히 옳다 —
Docker 는 바이트를 복사하고, 정규화해 지우면 이미지와 트리의 실제 차이를 못 본다.
다만 Windows + autocrlf 와의 상호작용은 몰랐고, 이제 문서에 있다.

### 푸시
추적 393파일 × 비밀값 6종 → 0건 확인 후 `95677a9..9f6e2c5` 푸시.
7552c03 은 다음 푸시에 포함된다.

### 내일
1. `--resume 387` → 3문항 → 승격 (심판 3콜이면 된다)
2. 승격 확인 후 B2a → B1 → B2 → B4
3. 그 다음 D4 (재정규화가 안전해진 시점)

---

## OPERATIONS — `full` 기준선 387 승격 + law-09 진단 판정 (2026-09-04)

**승인 발언**: "내일 첫 배치 시작해줘" (완주 시 승격은 사전 승인)

### 완주 — 첫 시도에 3문항
```
scripts/resume_and_promote.sh 387
시도 1: succeeded 30/30 (남은 law-07·msds-01·sub-07, 심판 3콜)
승격 → 실행 276 자동 강등 → 재현 확인 전 지표 +0.000 / ok
기준선   385 retrieval_only · 387 full   둘 다 코드 03bab957bade · 코퍼스 1,712
```

### 지표 — 276 → 387
```
Recall@5      0.867 → 0.967   +0.100
MRR           0.630 → 0.766   +0.136
정답률         0.917 → 1.000   +0.083   ← 25문항 전부 정답
인용 정확도     0.610 → 0.717   +0.107
거부 정확도     0.400 → 1.000   +0.600
오거부율        0.040 → 0.040    0.000
충실도         0.958 → 0.917   -0.041   ← 유일한 하락
```

### law-09 진단 판정: **맞았다**
276 의 충실도 0.958 은 law-09 단독이었고, 진단은 "검색이 0 이라 약한 근거로
답을 지어냈다"였다. 조문 제목 층으로 law-09 검색을 고친 뒤:
```
law-09   불충실·오답 → 충실·정답   ✅ 진단대로 사라졌다
msds-02  오답 → 정답              (MSDS 주제 지도)
```

### 그런데 충실도는 오히려 내려갔다 — 새 하락 2건
```
sub-07  충실 → 불충실   answered_partial
sub-08  충실 → 불충실   answered_partial
```
`answered_partial` 은 **2단계 검증이 근거 없는 문장을 걷어냈다**는 뜻이다.
시스템은 설계대로 동작했다(BR-87: 제거하고 그 사실을 밝힌다). 충실도 지표는
"제거된 문장이 있었다"를 불충실로 센다.

둘 다 염소 질문이고, BR-65a 의 주제 보장·섹션 지도가 이 둘의 근거 구성을 바꿨다.
근거가 달라지자 모델이 더 많은 주장을 했고 검증이 그중 일부를 걷어낸 것으로 보인다.
**검색을 고치니 답변 쪽의 다른 곳이 드러났다.**

원인 분해는 불가능하다 — 276 이후 조문 제목 층·MSDS 주제 지도·BR-73a 가 함께
들어갔고 거부가 3건 늘어 분모도 달라졌다. 백로그에 조사 항목으로 남긴다.

### 판정 요약
진단은 맞았고(law-09 회복), 순증은 -0.041 이며, 그 차액은 **새로 드러난
sub-07·sub-08 이다.** 예측이 절반만 맞았다는 뜻이고, 그대로 적는다.

---

## OPERATIONS — B 그룹 완료 · D4 · D5 · 백로그 재정리 (2026-09-04)

### B 그룹 — 실측된 노출면을 닫았다
```
착수 전                              변경 후
/api/sources·jobs·stats   익명 200  →  401
POST /api/{id}/ingest     도달      →  401   ← 수집 실행이 열려 있었다
/admin · /admin/*         익명 200  →  303
/usage                    익명 200  →  303
/healthz · / · /substances  200 유지 · 컨테이너 healthy 유지
```

**B3 의 두 결정.** 역할은 DB 에서 읽는다 — `current_user` 가 토큰만 보므로
페이로드에 넣으면 강등이 최대 12시간 늦는다. 쿠키 하나로 재로그인 없이
확인했다: 승격 후 nav 4→8, 강등 후 4. 부트스트랩은 CLI `grant-admin` 이다 —
"첫 가입자를 관리자로"는 노출 시 먼저 가입한 사람이 관리자가 된다.

**B2a 의 결정.** JSON 경로에 리다이렉트를 쓰지 않았다. `require_admin` 의 303 을
따르는 클라이언트는 로그인 페이지를 **200 + HTML** 로 받는다 — 거부가 성공
응답으로 도착한다. 노출 조사에서 `/api` 가 "익명 200"으로 읽힌 것이 그 모양이었다.
`/api` 는 라우터 수준에 의존성을 걸어 **닫힌 쪽을 기본값**으로 뒀다.

### D4 — 줄바꿈이 지문을 바꾸던 문제를 닫았다
```
착수 전 실측  추적 400 중 LF 300 · CRLF 73, 그중 43개가 지문 대상
조치         .gitattributes eol=lf · 작업 트리 73파일 정규화
지문         9b28088f237a → d9fdd7511c15 · 컨테이너 재빌드로 재일치
```
이제 어느 OS 에서 클론해도 지문이 같다. 9/3 에 이 위험을 재고 승격 이후로
미뤄 둔 것이 순서대로 값을 했다.

### D5 — 증명한 뒤에 지웠다
검사 3개(스택이 옛 경로를 안 쓰는가 · safeenv 유일 파일 0개 · 커밋 존재) 통과 후
실행. 운영 로그 3.5MB 는 `logs/safeenv-pre-migration.log` 로 보존, 24MB 삭제.
삭제 후 스택 healthy · `/healthz` 200 확인.

### 백로그 재정리 — 순서가 바뀌었다
착수 25~35커밋 → 남은 **12~20커밋(2~3일치)**. 절반 이상 소화됐다.

**1순위가 보안에서 답변 품질로 옮겨갔다.** 검색은 갈 데까지 갔고(검색 0 인
문항은 의도적으로 남긴 sub-02 하나뿐), 유일하게 내려간 지표가 충실도다.
새 항목 **C7 — sub-07·sub-08 충실도 하락 조사**를 1순위에 올렸다.

새 항목 **E5 — 관리자 계정 생성**도 추가했다. 계정이 0개라 지금 관리 화면에
아무도 못 들어간다. 이것은 결함이 아니라 B3 의 설계이고, 사람이 한 번 해야 하는
일이다.

### 검증
```
단위 691 · 통합 108 (72 → +36) · ruff clean
기준선 385·387 · 코퍼스 82/1,712 · 계정 0행(테스트 정리 확인)
```

---

## OPERATIONS — 관리자 계정 생성 및 종단 확인 (2026-09-04)

**승인 발언**: "관리자 계정 만들고 /admin 들어가지는지 확인해줘"

B3 이 도입한 부트스트랩 절차를 실제로 밟았다. 가입 폼(CSRF 포함) → CLI 승격 →
로그인 → 각 화면 접근을 HTTP 로 확인했다.

```
가입      POST /register    303   (user_account 601, role=user)
승격      grant-admin       mpsddd@gmail.com user → admin
로그인    POST /login       303

관리자로            익명 대조
/admin          200      303
/admin/sources  200       -
/admin/jobs     200       -
/usage          200      303
/api/stats      200      401
/documents      200      303

nav 링크   관리자 8개 · 익명 4개
대시보드   문서 82 · 청크 1,712 · 물질 49 — 실제 값이 렌더된다
/api/stats {"documents":82,"chunks":1712,"substances":49,...}
```

**역할이 화면과 라우트 양쪽에서 동시에 작동한다.** B3 의 "역할은 DB 에서 읽는다"
결정 덕에 승격이 재로그인 없이 즉시 반영됐다 — 같은 쿠키로 nav 가 4개에서
8개가 됐다.

### 남는 제약
비밀번호 재설정이 없다(B6 미구현). 분실하면 계정을 지우고 다시 만들어야 한다:
```
docker compose exec -T postgres psql -U safeenv -d safeenv \
  -c "delete from user_account where email='...'"
```
백로그 E5 를 완료 처리했다.

---

## OPERATIONS — C7 검증 1일차 (2026-09-05)

**승인 발언**: "내일 full 재측정해서 충실도 확인해줘"

### 완주하지 못했다 — 판정은 내일
```
실행 549 (--full, 코드 a06337a6a809 = C7 수정 반영)
시도 1  17/30 → Docker Desktop 재시작으로 중단
시도 2  19/30 → 심판 일일 한도 20 소진 (오늘 사용 17+3)
남은 11문항: msds-02·03·04 · inc-01·02·03 · ref-01~05
  그중 답변형 6개 → 내일 심판 6콜이면 완주한다
```

### 그래도 가설은 확인됐다 — 대상 두 문항이 뒤집혔다
```
        387 (수정 전)      549 (수정 후)
sub-07  충실 false    →    충실 true
sub-08  충실 false    →    충실 true
law-09  충실 true     →    충실 true  (유지)
```
C7 의 가설은 "sub-07·sub-08 의 불충실은 심판이 근거를 못 본 탓이고, 근거 중복을
없애면 상한 안에 들어와 회복된다"였다. **두 문항 모두 회복했다.**

다만 **집계 충실도는 아직 판정할 수 없다.** 11문항이 남았고, 그중 답변형 6개가
집계에 들어간다. 런북 6절의 판정표는 완주한 값으로 읽어야 한다 — 문항 두 개가
회복한 것과 지표가 1.000 이 되는 것은 다른 주장이다.

### 인프라 — 가드가 제 일을 했다
시도 1 직후 Docker Desktop 이 재시작해 전 컨테이너가 내려갔다. 스크립트가
DB 조회 빈 값을 **"할당량"이 아니라 "인프라 문제"로 분류**하고 즉시 중단했다.
둘을 같게 다뤘다면 30분마다 죽은 스택에 재시도를 반복했을 것이다 — 9/2 에
감시 스크립트에서 저지른 실수를 스크립트에 옮겨 담아 둔 것이 값을 했다.

복구 후 지문(`a06337a6a809`)이 컨테이너·작업 트리·실행 셋 다 일치하는 것을
확인하고 재개했다.

### 내일
```
scripts/resume_and_promote.sh 549 --no-promote
```
심판 6콜이면 완주한다. 완주 후 런북 6절 판정표대로 읽고, 승격 여부는 사람이 정한다.

---

## OPERATIONS — C4 측정 스크립트와 실측 (2026-09-06)

**승인 발언**: "C4 검토도 스크립트로 남겨줘"

### 코드를 고치지 않고 잴 수 있었다
`final_top_k` 는 `Settings` 필드라 **환경변수로 바뀐다**(`FINAL_TOP_K=10`).
빌드 지문은 파일을 해싱하므로 env 변경으로는 바뀌지 않는다. 임시 패치를 붙였다
떼는 방식이었다면 실패 시 작업 트리가 더러워지고 승격이 막혔을 텐데,
**되돌릴 코드가 없다는 것이 이 측정의 안전성 전부다.**
`--retrieval-only` 라 LLM 0콜 — 몇 번을 돌려도 할당량이 줄지 않는다.

### 실측 — 예상과 달랐다
```
깊이 5    Recall@5 0.967   Recall@10 --      MRR 0.766   (실행 550)
깊이 10   Recall@5 0.933   Recall@10 1.000   MRR 0.766   (실행 551)
```

**둘 다 예상 밖이다.**

1. **Recall@10 = 1.000.** 30문항 전부의 정답 근거가 깊이 10 안에 있다.
   이 지표는 "잴 수 없는 값"이 아니라 **잴 수 있고 무언가를 말한다** —
   결함 49 는 "5건짜리 목록에서는 @10 이 @5 와 같다"고 옳게 적었지만,
   그것은 목록이 5건일 때의 이야기였다.

2. **Recall@5 가 0.967 → 0.933 으로 내려갔다.** `final_top_k` 를 올리면
   `ensure_doc_type_spread(fused, limit)` 의 결과가 달라져 **상위 5의 구성이
   바뀐다.** 두 지표는 중첩되지 않는다.

### 문항 단위 — 제로섬이다
```
sub-02   Recall@5 0.000 → 1.000   (5위로 진입)
sub-06   Recall@5 1.000 → 0.000   (9위로 밀림, 깊이 10 안에는 있다)
sub-07   Recall@5 1.000 → 0.000   (8위로 밀림, 깊이 10 안에는 있다)
```
하나를 얻고 둘을 잃는다. law-08·09 때 본 것과 같은 모양이다 — **순위 재편은
제로섬**이고, 분산 규칙이 무엇을 상위로 올릴지 다시 정한다.

### 이것이 검토에 주는 것
- 선택지 (c) "`final_top_k` 상향"은 **공짜가 아니다.** 지금 설정에서는
  Recall@5 를 0.034 잃는다. 생성기가 보는 근거도 함께 바뀐다는 비용은 별도다.
- 선택지 (b) "융합 중간 결과만 관측"이 흥미로워졌다. 파이프라인은 5건을
  그대로 넘기고 측정만 10건을 보는 것 — 그러면 Recall@5 를 잃지 않고
  Recall@10 = 1.000 을 알 수 있다. **BR-115/DD-22 를 어기는지가 판단의 핵심**이고,
  같은 계산의 이미 있는 중간 산출물을 관측하는 것이 "평가 전용 경로"인지는
  검토가 정한다.
- sub-02 가 깊이 10 안에 있다는 것은 **골든셋 B 결정(E1)과도 닿는다** —
  근거가 없는 것이 아니라 5위 밖에 있을 뿐이다.

### 측정 실행에 표시를 남긴다
`evaluate --list` 를 읽는 사람이 측정용과 진짜 실행을 구별하지 못하면 승격할
것을 고르는 일이 추측이 된다. 스크립트가 `measure-recall FINAL_TOP_K=n` 을
`note` 에 적는다 — 통합 테스트가 자기 실행에 라벨을 다는 것과 같은 이유다
(9/2 에 103/141 이 라벨 없이 섞여 있던 것을 고쳤다).

### 남은 것
검토 문서(`operations/recall-at-10-review.md`)는 아직 없다. 측정은 끝났고,
선택지·대가·권고를 쓰고 결정란을 비워 두는 일이 남았다.

---

## OPERATIONS — C7 판정: 진단 적중 + `full` 기준선 549 승격 (2026-09-06)

**승인 발언**: "내일 완주하면 승격까지 진행해줘"

### 판정: **충실도 0.917 → 1.000. 진단이 맞았다.**
런북 6절에 미리 적어 둔 표의 "1.000 = 진단 적중" 칸이다.

```
        387(C7 이전)   549(C7 이후)
Recall@5   0.967    →    0.967    +0.000
MRR        0.766    →    0.766    +0.000
충실도      0.917    →    1.000    +0.083   ← 이 수정의 목표
거부 정확도  1.000    →    1.000    +0.000
정답률      1.000    →    0.958    -0.042   ← 아래 참조
인용 정확도  0.717    →    0.712    -0.005
오거부율     0.040    →    0.040    +0.000
```

문항 단위로도 확인된다 — **sub-07·sub-08 이 둘 다 불충실 → 충실**로 뒤집혔고,
그것이 C7 이 겨냥한 정확히 그 두 문항이다. 충실도는 22/24 → **24/24** 다.

### 정답률 하락은 C7 의 대가가 아니다 — 분모가 움직였다
두 실행이 심판한 문항 수는 24로 같지만 **같은 24가 아니다.**

```
387   sub-06 이 refused_unsupported → 심판 안 함.  나머지 24 전부 정답 = 1.000
549   law-05 가 refused_unsupported → 심판 안 함.  sub-06 은 답변됐고 오답 = 23/24
```

거부된 답변형 문항은 두 실행 모두 **정확히 1개**(오거부율 0.040 동일)인데,
**그 1개가 서로 다른 문항이다.** `refused_unsupported` 는 2단계 검증이 모든
문장을 걷어냈다는 뜻이고, 그것은 생성·검증 LLM 호출의 산물이다. C7 은
**심판이 보는 근거만** 바꿨을 뿐 검증기를 건드리지 않았다.

즉 이것은 **경계선 문항에서 거부 판정이 실행마다 흔들린다**는 관측이지
C7 의 효과가 아니다. 정답률 1.000 과 0.958 을 뺄셈으로 비교하면 안 된다 —
서로 겹치되 같지 않은 집합을 잰 두 수다.

### 그래도 승격한다 — 이유
549 는 **지금 배포된 코드가 내는 값**이고, 387 은 C7 이전 코드라 지금은
재현되지 않는다. 기준선은 "지금까지 본 최고값"이 아니라 "이 코드가 내는 값"이며,
재현 불가능한 기준선을 붙들면 매일의 가드가 무엇과 비교하는지 알 수 없게 된다.
정답률이 표면상 내려간 채로 승격하며, 그 이유를 위에 적었다.

```
기준선   385 retrieval_only (03bab957bade)
        549 full           (a06337a6a809)   ← 387 자동 강등
승격 후 재현 확인: 전 지표 +0.000 / 판정 ok
```

### 새로 안 것 — 거부 경계가 실행마다 흔들린다
오거부율 0.040 은 두 실행에서 같지만 대상 문항이 sub-06 → law-05 로 바뀌었다.
지표가 같아도 **같은 것을 재고 있다는 뜻이 아니다.** 백로그에 관측 항목으로 남긴다.

---

## OPERATIONS — C8 검토: 거부 경계가 흔들린다 (2026-09-06)

**승인 발언**: "검토 문서 지금 써줘"

### 측정 — 실제 `--full` 실행 7건
```
 10  거부 1  msds-01          221  거부 2  sub-04·sub-06
 17  거부 0                   276  거부 1  sub-06
 26  거부 0                   387  거부 1  sub-06
                              549  거부 1  law-05
```
개수도 대상도 움직인다.

### 원인 — 온도가 지정돼 있지 않다
`llm_gemini.py` 의 `_config()` 는 `system_instruction` 과 `response_schema` 만
설정한다. 제공자 기본값이므로 생성도 검증도 표집이고, 답변 문장이 **전부**
검증에 떨어지는지는 경계선에서 동전 던지기가 된다.

387 → 549 사이의 코드 변경(B3·B1/B2/B2a·D4·C7·nav) 중 **생성기·검증기를
건드린 것은 없다.** C7 은 심판이 보는 근거만 바꿨다. 즉 이 뒤집힘은 코드의
효과가 아니라 같은 코드가 두 번 다르게 답한 것이다.

### 왜 문제인가 — 허용오차와 만난다
```
answer.accuracy 허용 0.05    문항 1개 = 1/24 = 0.042
한 문항 흔들림 → 통과(0.042 < 0.05) · 두 문항 → 발화(0.083 > 0.05)
```
계산된 여유가 아니라 우연이다. `reporter.py` 주석이 이미 "완주가 나오기
전까지는 추측"이라고 적어 뒀고, **이제 완주가 7건 있다.**

오늘 실제로 오독할 뻔했다 — 정답률 1.000 → 0.958 을 "C7 의 대가"로 읽을
뻔했고, 분모를 세어 보고서야 겹치되 같지 않은 집합이었음을 알았다.

### 측정하지 못한 것을 적어 둔다
**흔들림의 크기를 모른다.** 깨끗한 관측은 387 vs 549 **한 쌍뿐**이다 —
나머지는 코드나 코퍼스가 함께 달라져 노이즈만 떼어 낼 수 없다. n=1 로는
"흔들린다"까지만 말할 수 있고 "얼마나"는 말할 수 없다.

### 권고: (a) 온도 0 → 그다음 (b) 허용오차 재교정
순서에 이유가 있다. (b) 를 먼저 하면 큰 노이즈를 큰 허용오차로 덮는 셈이고
진짜 회귀도 함께 덮인다. 그리고 안전 도메인에서 "같은 질문에 같은 답"은
지표를 위한 편의가 아니라 제품의 성질이다.

**(a) 가 답이 아닐 수 있다는 것도 적었다** — 온도 0 에서도 제공자가 같은
출력을 보장하지 않으면 원인은 표집이 아니라 검증 임계 자체가 경계선에
있다는 뜻이고, 다른 문제가 된다.

결정란은 비워 뒀다.

---

## OPERATIONS — C4(b)·C8(a) 구현 (2026-09-07)

**승인 발언**: "권장안대로 진행해줘"

### C4(b) — 관측 창을 넓혔지 경로를 만들지 않았다
`QueryResult.retrieved` 를 소비하는 곳은 `evaluation_service` 와 `reporter`
뿐이고 `query_log` 에 저장되지도 않는다 — **이미 관측 전용 창구**다. 답변·인용·
거부는 여전히 상위 5로만 결정된다. BR-115 가 막으려던 "평가가 아무도 안 쓰는
것을 잰다"는 상황이 아니라, 제품이 실제로 계산하는 것을 더 정확히 재게 됐다.

```
Recall@5   0.967 → 0.967   불변 (30문항 전부 상위 5가 순서까지 동일)
Recall@10    --   → 1.000
MRR        0.766 → 0.772   sub-02 의 6위 적중이 이제 보인다
```
설계의 전부는 머리를 안 건드리는 것이었다. `FINAL_TOP_K` 상향은 분산 규칙이
머리를 재편해 Recall@5 를 0.034 잃었는데(제로섬), 머리 5건을 순서 그대로 두고
융합 꼬리만 덧붙이면 그 손실이 없다.

`config` 스냅샷에 `observation_top_k` 를 넣었다 — 구현자가 누락을 보고했고
타당했다. Recall@10 이 이 값을 직접 읽으므로 빠뜨리면 관측 깊이만 다른 두
실행이 같은 것을 잰 것처럼 비교된다. 그래서 지금 기준선 385 대비
`incomparable` 이고, **그것이 옳은 동작이다.**

### C8(a) — 온도 0
모든 목적에 적용. 효과는 `--retrieval-only` 로 안 보이고(LLM 0콜) 다음 `--full`
완주가 판정이다 — 거부 문항이 고정되는지가 첫 신호다.

### 구현자가 잡은 것 둘 — 둘 다 내가 만든 위험이었다
1. **CRLF 오염**: 문서를 파이썬 `write_text` 로 쓰면 Windows 에서 CRLF 가 된다.
   `.gitattributes` 가 `eol=lf` 를 강제하고 빌드 지문이 원시 바이트를 해싱하므로,
   커밋 시 git 이 정규화하면 작업 트리 지문이 바뀌어 컨테이너가 낡은 것으로
   판정됐을 것이다(결함 58 의 모양). 구현자가 되돌리고 검증을 재실행했다.
2. 그럼에도 내 문서 4건이 CRLF 로 남아 있었다(`aidlc-state` `backlog`
   `operations` `runbook`). **다행히 빌드 지문 대상 0건**이라 무해했지만,
   같은 습관이 `app/` 을 건드리는 날 지문이 흔들린다. LF 로 정리했다.
   **앞으로 문서를 쓸 때 `newline="\n"` 을 명시한다.**

### 통합 테스트 1차 실패는 인프라였다
호스트 5433 포워드가 죽어 58 failed/32 errors 가 났다. `docker compose exec` 는
정상이었고 postgres 로그에 접속 시도 자체가 없었다. `restart postgres` 로 복구
후 113 통과. 9/2·9/5 에 이어 세 번째다 — Docker Desktop 이 포워드를 잃는다.

### 검증
```
단위 698 → 715 (+17) · 통합 113 · ruff clean
지문 f3f6b9235c8a (컨테이너 == 작업 트리)
```

### 남은 것 — C8(b)
허용오차 재교정은 노이즈 크기를 알아야 하고, 그것은 같은 코드로 `--full` 을
여러 번 돌려야 나온다(한 번이 하루). 권고한 순서대로 (a) 를 먼저 했다.
