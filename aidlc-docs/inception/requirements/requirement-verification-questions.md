# Requirements Verification Questions — safeenv

**프로젝트**: safeenv — 화학 안전·규제 근거 기반 질의응답(RAG) 시스템
**단계**: INCEPTION / Requirements Analysis (Step 6 — GATE)
**생성 시각**: 2026-08-20T01:28:02Z

---

## 답변 방법

각 질문 아래 `[Answer]:` 태그 뒤에 **선택지 문자(A, B, C…)** 를 적어 주세요.
제시된 선택지가 모두 맞지 않으면 마지막 **X) Other** 를 고르고 `[Answer]: X - 설명…` 형태로 직접 기술해 주세요.
전부 작성하신 뒤 채팅으로 "완료"라고 알려 주시면 답변을 읽고 모순·모호성을 검증한 후
`requirements.md` 를 생성합니다.

**참고**: 각 질문의 *권장* 표시는 직전 대화에서 논의된 목표(화학공학 전공을 살린 백엔드/AI 엔지니어
포트폴리오)에 비추어 유리한 선택지를 의미하며, 강제 사항이 아닙니다.

---

# 1부. 프로젝트 범위와 목표

## Question 1
워크스페이스 루트 설정을 확인해 주세요. 현재는 `c:\Users\403\IDE\safeenv` 를 프로젝트 루트로,
`safeenv/aidlc-docs/` 를 문서 루트로 설정했습니다. (상위 `IDE` 폴더에는 news / purchase_agent / trip 등
별개의 AI-DLC 프로젝트가 이미 존재합니다.)

A) 그대로 진행 — `safeenv/` 를 독립 워크스페이스 루트로 사용 *(권장)*

B) 다른 경로를 루트로 사용하고 싶음

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2
이 프로젝트의 1차 목적은 무엇입니까? (이 답이 이후 모든 단계에서 "무엇을 깊게 만들지"를 결정합니다)

A) 취업 포트폴리오 — 기술 폭·설계 깊이·문서화 품질 증명이 최우선

B) 실사용 도구 — 본인 또는 현업 지인이 실제로 쓸 수 있는 수준

C) 둘 다 — 포트폴리오이되 "실제로 동작하는 품질"을 타협하지 않음 *(권장)*

X) Other (please describe after [Answer]: tag below)

[Answer]: C

## Question 3
주 사용자(페르소나)는 누구입니까?

A) 화학물질 취급 사업장의 안전보건관리자 — 법정 의무 이행과 현장 조치 판단이 목적

B) 연구실 연구원·대학원생 — 실험 전 물질 위험성과 보호구 확인이 목적

C) 규제 준수 담당자 — 화학물질관리법·화평법 신고 의무 판정이 목적

D) A + B 를 하나의 "화학물질 취급자" 페르소나로 통합 *(권장 — 범위 관리에 유리)*

X) Other (please describe after [Answer]: tag below)

[Answer]: D

## Question 4
MVP(1차 완성본)의 **중심 기능** 하나를 고른다면 무엇입니까? 나머지는 후속 순위로 배치합니다.

A) 자연어 질의응답 — "황산을 취급할 때 필요한 보호구와 응급조치는?" 에 근거 인용과 함께 답변

B) 물질 안전 카드 — 물질명 또는 CAS 번호 입력 시 GHS 분류·유해성·취급·응급조치를 구조화 요약

C) 규제 준수 체크 — 사업장이 취급하는 물질 목록을 입력하면 적용 법령과 의무사항을 자동 판정

D) 혼합 위험성 판정 — 두 개 이상 물질의 동시 보관·취급 시 상충(혼촉 위험) 여부 판정

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 5
Question 4에서 고르지 않은 기능들은 어떻게 처리할까요?

A) MVP 범위에서 완전히 제외 — 문서에 "향후 확장"으로만 기록

B) 2순위 1개만 MVP에 포함 (아래 [Answer] 에 어떤 것인지 함께 기재)

C) 전부 포함 — 규모가 커지더라도 종합 시스템으로 구축

X) Other (please describe after [Answer]: tag below)

[Answer]: B - Question 4의 B(물질 안전 카드)를 2순위 기능으로 MVP에 포함

---

# 2부. 데이터 — 이 프로젝트의 성패를 좌우하는 부분

## Question 6
지식 베이스로 사용할 **문서 범위**는 어디까지입니까?

A) MSDS(물질안전보건자료) 중심 — 물질별 유해성·취급·응급조치

B) MSDS + 국내 화학 법령 조문 (화학물질관리법 / 화평법 / 산업안전보건법)

C) MSDS + 법령 + 화학사고 사례 (사고 이력 기반 근거까지) *(권장 — 도메인 차별성이 가장 큼)*

D) 법령 조문만 — 규제 해석 특화

X) Other (please describe after [Answer]: tag below)

[Answer]: C

## Question 7
문서·데이터를 **어떻게 확보**할 계획입니까?

A) 공공 오픈데이터·API 수집 파이프라인 구현 (공공데이터포털, 화학물질정보시스템 NCIS,
   국가법령정보센터 API 등) — 구조화 데이터 중심

B) 공개 MSDS PDF를 내려받아 파싱하는 파이프라인 구현 — 비정형 문서 처리 역량 증명

C) 샘플 문서 소량을 저장소에 직접 포함 — 수집은 생략하고 RAG 품질에만 집중

D) A + B 혼합 — 구조화 데이터와 PDF 문서를 모두 다루는 통합 파이프라인 *(권장 — 백엔드 어필 최대)*

X) Other (please describe after [Answer]: tag below)

[Answer]: D

## Question 8
초기 인덱싱 목표 **데이터 규모**는?

A) 소규모 — 물질 50~100종 (개발·데모에 충분, 빠른 반복)

B) 중규모 — 물질 1,000종 내외 *(권장 — 검색 품질 문제가 실제로 드러나는 규모)*

C) 대규모 — 공개 데이터 전량 (수만 종). 인프라 부담과 수집 시간 증가

X) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 9
외부 데이터 수집 시 **이용약관·로봇 정책** 처리 방침은?
(직전 news 프로젝트에서 robots.txt 로 인해 수집 자체가 차단되는 문제를 겪은 바 있습니다)

A) 로봇 정책·이용약관을 엄격히 준수하고, 차단된 소스는 사용하지 않음 — 공개 API·오픈데이터만 사용 *(권장)*

B) 준수하되, 차단 시 사용자가 직접 업로드한 문서로 대체 가능하게 설계

C) 정책 검사 없이 수집 (개인 학습 목적)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 10
사용자가 **자체 문서를 업로드**하는 기능이 필요합니까?
(사업장마다 자사 MSDS·작업표준을 보유하므로 실사용 가치가 큽니다)

A) 필요 — PDF 업로드 후 즉시 인덱싱되어 질의 대상에 포함

B) 불필요 — 시스템이 수집한 공개 데이터만 사용

C) 필요하지만 후순위 — 설계에만 반영하고 구현은 나중에

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

# 3부. AI / RAG 설계

## Question 11
**LLM 제공자**는 무엇을 사용합니까?

A) Anthropic Claude API

B) OpenAI API

C) 로컬 오픈소스 모델 (Ollama 등) — API 비용 없음, 품질·속도 제약

D) 교체 가능한 추상화 레이어를 두고 기본값은 Claude *(권장 — 설계 역량 어필)*

X) Other (please describe after [Answer]: tag below)

[Answer]: D

## Question 12
**임베딩 모델**은 무엇을 사용합니까? (한국어 화학 용어 검색 품질에 직결됩니다)

A) 한국어 지원 오픈소스 임베딩을 로컬 실행 (BGE-M3, KURE 등) — 비용 0, 초기 다운로드 필요

B) 상용 API 임베딩 (OpenAI, Voyage 등) — 간편, 호출당 비용 발생

C) 교체 가능한 추상화 + 기본값은 로컬 오픈소스 *(권장)*

X) Other (please describe after [Answer]: tag below)

[Answer]: C

## Question 13
**벡터 저장소**는 무엇을 사용합니까?

A) PostgreSQL + pgvector — 관계형 데이터(물질·법령 메타데이터)와 한 DB에서 통합 *(권장)*

B) 전용 벡터 DB (Qdrant, Weaviate 등) — 별도 컨테이너

C) 경량 로컬 (Chroma, FAISS 파일) — 설치 부담 최소

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 14
**검색 전략**은? (CAS 번호·물질명은 정확 일치가 중요해 순수 벡터 검색이 약할 수 있습니다)

A) 벡터 검색 단독 — 가장 단순

B) 하이브리드 (BM25 키워드 + 벡터) — CAS 번호·물질명 정확 매칭에 유리

C) 하이브리드 + 리랭커(cross-encoder) — 품질 최상, 지연시간 증가 *(권장 — 개선 과정 자체가 포트폴리오 소재)*

X) Other (please describe after [Answer]: tag below)

[Answer]: C

## Question 15
**근거(출처) 표시 수준**은? — 안전 도메인에서 신뢰성의 핵심입니다.

A) 문장 단위 인용 — 답변의 각 주장마다 출처 문서·섹션 번호 표기

B) 답변 하단에 참조 문서 목록만 표시

C) 문장 단위 인용 + 클릭 시 원문 스니펫 하이라이트 표시 *(권장)*

X) Other (please describe after [Answer]: tag below)

[Answer]: C

## Question 16
검색된 **근거가 불충분할 때** 시스템은 어떻게 동작해야 합니까?

A) "확인할 수 없음"으로 답변을 거부하고 관련 원문 링크만 제시 — 환각 차단 최우선 *(권장 — 안전 도메인)*

B) 낮은 신뢰도 경고와 함께 모델의 일반 지식으로 답변

C) 사용자에게 재질문을 유도하는 명확화 질문 반환

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 17
**면책 고지**(참고용이며 실제 취급은 원본 MSDS와 전문가 확인이 필요하다는 안내)는 어떻게 노출합니까?

A) 모든 답변에 상시 노출

B) 최초 진입 시 1회 동의

C) 둘 다 *(권장 — 안전 도메인 책임 관점)*

X) Other (please describe after [Answer]: tag below)

[Answer]: C

## Question 18
**RAG 품질 평가**를 어떻게 수행합니까? (채용 관점에서 가장 차별화되는 지점입니다)

A) 골든 QA 셋(30~50문항)을 직접 구축해 정답률·인용 정확도를 자동 측정

B) 수동 스팟 체크만 수행

C) 자동 평가 + LLM-as-judge 로 답변 충실도(faithfulness)까지 채점 *(권장)*

X) Other (please describe after [Answer]: tag below)

[Answer]: C

## Question 19
**대화 컨텍스트** 유지가 필요합니까?

A) 단발성 질의 — 이전 대화 참조 없음 (구현 단순)

B) 멀티턴 대화 — 세션 내 이전 질문 참조 ("그럼 그 물질의 보관 온도는?")

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

# 4부. 기술 스택 및 운영

## Question 20
**백엔드 프레임워크**는?

A) Python + FastAPI *(권장 — AI 생태계 통합 및 기존 프로젝트와의 일관성)*

B) Python + Django

C) Java + Spring Boot — 국내 백엔드 채용 시장 대응력

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 21
**프론트엔드**는 어떤 형태입니까?

A) 서버사이드 렌더링 (FastAPI + Jinja2) — 구현 단순, 기존 news 프로젝트와 동일 방식

B) React 또는 Next.js SPA — 프론트 역량까지 어필, 작업량 증가

C) API 만 제공하고 Swagger UI 로 시연 — 백엔드에 100% 집중

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 22
**사용자 인증**이 필요합니까?

A) 없음 — 단일 사용자/데모 용도

B) 이메일 + 비밀번호 (JWT) — 개인별 질의 이력 보관

C) 인증 + 조직·역할 구분 (관리자 / 일반 사용자) — 업로드 문서 권한 분리

X) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 23
문서 수집·파싱·임베딩 같은 **오래 걸리는 작업**은 어떻게 처리합니까?

A) 앱 내장 백그라운드 태스크 (FastAPI BackgroundTasks / APScheduler) — 배포 단순

B) 별도 워커 + 작업 큐 (Celery/Redis 또는 ARQ) — 확장성·재시도 제어 우수, 컨테이너 증가

X) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 24
**실행 환경**과 포트는? (기존 프로젝트가 8000/5173/8100 을 사용 중이므로 충돌 회피가 필요합니다)

A) Docker Compose 로컬 실행, 호스트 포트 `127.0.0.1:8200` *(권장)*

B) Docker Compose 로컬 실행, 다른 포트 지정 (아래에 기재)

C) 클라우드 배포까지 포함 (AWS 또는 GCP) — IaC 및 배포 파이프라인 포함

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 25
**관측성(Observability)** 수준은? (LLM 애플리케이션에서 비용·지연 추적은 실무 필수 역량입니다)

A) 구조적 로깅만

B) 로깅 + LLM 호출 추적 (모델·토큰 수·지연시간·추정 비용 기록 및 조회) *(권장)*

C) 로깅 + LLM 추적 + Prometheus 메트릭 / Grafana 대시보드

X) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 26
**테스트 범위**는?

A) 단위 테스트 중심

B) 단위 + 통합 테스트 (RAG 파이프라인 종단 검증)

C) 단위 + 통합 + 평가셋 회귀 테스트 (품질 저하를 CI 에서 자동 탐지) *(권장)*

X) Other (please describe after [Answer]: tag below)

[Answer]: C

---

# 5부. AI-DLC 확장(Extension) 선택

## Question 27: Security Extensions
Should security extension rules be enforced for this project?
(이 프로젝트에 보안 확장 규칙을 강제 적용할까요?)

A) Yes — enforce all SECURITY rules as blocking constraints (recommended for production-grade applications)
   / 예 — 모든 보안 규칙을 차단성 제약으로 강제

B) No — skip all SECURITY rules (suitable for PoCs, prototypes, and experimental projects)
   / 아니오 — 보안 규칙 생략

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 28: Resiliency Extensions
Should the resiliency baseline be applied to this project?
(복원력(Resiliency) 베이스라인을 적용할까요?)

**이 확장이 하는 일**: AWS Well-Architected Framework(신뢰성 기둥)에서 도출된 **설계 시점의 방향성 있는
모범 사례**를 적용합니다. 요구사항·설계·코드를 내결함성, 고가용성, 관측성, 복구 가능성 방향으로 유도하며
15개 실천 영역을 다룹니다.

**이 확장이 하지 않는 일**: 활성화한다고 해서 워크로드가 프로덕션 준비 상태가 되거나, 특정 가용성/RTO/RPO
목표가 보증되지는 않습니다. 정식 AWS Well-Architected Review 를 대체하지 않는 **출발점**입니다.

A) Yes — apply the resiliency baseline as directional best practices and design-time guidance
   / 예 — 복원력 베이스라인을 설계 지침으로 적용

B) No — skip the resiliency baseline (suitable for PoCs, prototypes, and experimental projects)
   / 아니오 — 생략

X) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 29: Property-Based Testing Extension
Should property-based testing (PBT) rules be enforced for this project?
(속성 기반 테스트(PBT) 규칙을 강제할까요?)

A) Yes — enforce all PBT rules as blocking constraints (recommended for projects with business logic,
   data transformations, serialization, or stateful components)
   / 예 — 모든 PBT 규칙을 차단성 제약으로 강제

B) Partial — enforce PBT rules only for pure functions and serialization round-trips
   / 부분 — 순수 함수와 직렬화 왕복에만 적용

C) No — skip all PBT rules (suitable for simple CRUD applications, UI-only projects, or thin integration
   layers with no significant business logic)
   / 아니오 — 생략

X) Other (please describe after [Answer]: tag below)

[Answer]: B

---

# 6부. 자유 기술

## Question 30
위 질문에서 다루지 않았지만 반드시 반영되어야 할 요구사항, 제약, 또는 "이건 꼭 넣고 싶다"는 항목이 있습니까?

A) 없음 — 위 답변으로 충분

B) 있음 (아래 [Answer]: 뒤에 자유롭게 기술)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

**모든 답변 작성 후 채팅에 "완료" 라고 입력해 주세요.**
답변의 모순·모호성을 검증한 뒤 `requirements.md` (기능 요구사항 / 비기능 요구사항 / 제약 / 범위 제외)를 생성합니다.
