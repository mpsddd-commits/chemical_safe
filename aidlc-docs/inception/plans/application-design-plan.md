# Application Design Plan — safeenv

**프로젝트**: safeenv — 화학 안전·규제 근거 기반 질의응답(RAG) 시스템
**단계**: INCEPTION / Application Design (설계 계획 + 설계 질문 — GATE)
**작성일**: 2026-08-20
**상태**: 사용자 답변 대기

---

## 답변 방법

아래 **2부 설계 질문(DQ-1 ~ DQ-18)** 의 `[Answer]:` 태그 뒤에 선택지 문자를 적어 주세요.
*(권장)* 표시는 요구사항(FR/NFR)과 방향 (a) 단계적 진행에 비추어 유리한 선택지입니다.

**"권장안대로 진행"** 이라고 하시면 *(권장)* 선택지로 전부 채운 뒤 설계 산출물을 생성합니다.

---

# 1부. 설계 실행 계획 (체크리스트)

### 1. 컨텍스트 분석
- [x] 1.1 `inception/requirements/requirements.md` 로드 — FR 48 / NFR 32 / CON 8 / OOS 10
- [x] 1.2 `inception/plans/execution-plan.md` 로드 — 유닛 5개 분해 및 실행 순서
- [x] 1.3 핵심 비즈니스 역량 식별 — 수집 / 문서처리 / 색인 / 검색 / 생성·인용 / 평가 / 계정·업로드 / 관측
- [x] 1.4 유닛 경계와 컴포넌트 경계의 정합성 확인 (방향 (a) 단계적 진행의 전제)

### 2. 컴포넌트 식별
- [x] 2.1 수집 계층 컴포넌트 정의 (소스 어댑터, 정책 검사기, 수집 오케스트레이터)
- [x] 2.2 문서 처리 계층 컴포넌트 정의 (파서, 정규화기, 구조 분해기, 청커)
- [x] 2.3 색인 계층 컴포넌트 정의 (임베더, 벡터 저장소, 키워드 인덱스)
- [x] 2.4 검색 계층 컴포넌트 정의 (키워드 검색기, 벡터 검색기, 융합기, 리랭커, 엔티티 추출기)
- [x] 2.5 생성 계층 컴포넌트 정의 (프롬프트 빌더, LLM 포트, 인용 매퍼, 거부 판정기, 근거 검증기)
- [x] 2.6 평가 계층 컴포넌트 정의 (평가셋 로더, 지표 계산기, LLM 심판, 리포터)
- [x] 2.7 계정·문서 계층 컴포넌트 정의 (인증, 업로드 처리기, 소유권 필터)
- [x] 2.8 횡단 관심사 컴포넌트 정의 (설정, 로깅, LLM 호출 추적기, 작업 큐, 저장소 리포지터리)
- [x] 2.9 각 컴포넌트를 유닛(u1~u5)에 배정

### 3. 컴포넌트 메서드 설계
- [x] 3.1 각 컴포넌트의 공개 메서드 시그니처 정의 (입출력 타입 포함)
- [x] 3.2 포트(추상 인터페이스) 정의 — LLM / 임베딩 / 리랭커 / 소스 어댑터 (NFR-21)
- [x] 3.3 세부 비즈니스 규칙은 Functional Design 으로 이월 표시

### 4. 서비스 계층 설계
- [x] 4.1 서비스 식별 및 책임 정의 (오케스트레이션 단위)
- [x] 4.2 서비스 간 상호작용 및 트랜잭션 경계 정의
- [x] 4.3 동기 경로(질의응답)와 비동기 경로(수집·색인·업로드) 분리 설계

### 5. 의존 관계 설계
- [x] 5.1 컴포넌트 의존 매트릭스 작성
- [x] 5.2 순환 의존성 0건 검증
- [x] 5.3 데이터 흐름도 작성 (수집→색인 / 질의→답변 / 평가 루프)
- [x] 5.4 유닛 간 의존 방향이 실행 순서(u1→u2→u4→u3→u5)와 모순되지 않는지 검증

### 6. 산출물 생성
- [x] 6.1 `inception/application-design/components.md` — 컴포넌트 정의와 책임
- [x] 6.2 `inception/application-design/component-methods.md` — 메서드 시그니처
- [x] 6.3 `inception/application-design/services.md` — 서비스 정의와 오케스트레이션
- [x] 6.4 `inception/application-design/component-dependency.md` — 의존 매트릭스와 데이터 흐름
- [x] 6.5 `inception/application-design/application-design.md` — 통합 문서 및 설계 결정(DD) 목록

### 7. 검증
- [x] 7.1 FR 48건 전건이 하나 이상의 컴포넌트에 매핑되는지 확인 (미매핑 0건)
- [x] 7.2 NFR 32건 중 설계에 영향을 주는 항목의 반영 위치 명시
- [x] 7.3 Functional Design 으로 이월할 항목 목록 작성
- [x] 7.4 Security Baseline 확장 관점의 설계 검토 (NFR-11~18)

---

# 2부. 설계 질문

## 컴포넌트 식별 및 조직

### DQ-1
**패키지(모듈) 구성 기준**은 무엇으로 합니까?

A) 계층 기준 — `api/`, `services/`, `domain/`, `infra/` 상위 분리

B) 기능(도메인) 기준 — `ingestion/`, `indexing/`, `retrieval/`, `generation/`, `evaluation/`, `accounts/`
   상위 분리 후 각 모듈 내부에서 계층 분리 *(권장 — 유닛 경계와 패키지 경계가 일치해 단계적 진행에 유리)*

C) 혼합 — 도메인 모듈 + 공용 계층(`core/`, `infra/`) 병존

X) Other (please describe after [Answer]: tag below)

[Answer]: B

### DQ-2
**데이터 소스 어댑터**를 어떻게 추상화합니까? (FR-1~4: 물질정보 API / 법령 API / 사고사례 / MSDS PDF)

A) 공통 `SourceAdapter` 프로토콜 1개 + 소스별 구현체 — 수집 오케스트레이터가 소스를 몰라도 동작 *(권장)*

B) 소스 유형별로 완전히 독립된 수집기 — 공통 추상화 없음

C) 구조화 API용 어댑터와 문서(PDF)용 어댑터 두 계열로 분리

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### DQ-3
**문서 처리 파이프라인**의 구조는?

A) 명시적 단계 객체 체인 — `Fetch → Extract → Normalize → Structure → Chunk → Embed → Persist`
   각 단계가 독립 컴포넌트. 재시도·부분 실패·중간 재개 지점 제어 가능 *(권장 — FR-7, FR-8 요구에 부합)*

B) 서비스 메서드 순차 호출 — 단일 서비스가 절차적으로 처리

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### DQ-4
**문서 원문 보존 수준**은? (FR-19 인용 스니펫 하이라이트에 원문이 필요합니다)

A) 3계층 보존 — 원본 파일(또는 원본 URL) + 추출 텍스트 + 청크. 스니펫은 추출 텍스트의
   오프셋으로 역참조 *(권장)*

B) 2계층 — 추출 텍스트 + 청크만 보존 (원본 파일 미보관, 저장 공간 절약)

C) 청크만 보존 (스니펫은 청크 전문을 그대로 표시)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## 검색·생성 컴포넌트

### DQ-5
**검색기 구성**은? (FR-15 하이브리드 + FR-16 리랭커)

A) 단일 `Retriever` 컴포넌트가 하이브리드와 리랭킹을 내부에 포함 — 호출부 단순

B) 독립 컴포넌트 조립 — `KeywordRetriever` / `VectorRetriever` / `Fusion` / `Reranker` 를 각각 분리하고
   조합기가 결합. 리랭커 on/off 전환과 구성 실험이 설정만으로 가능 *(권장 — R-4 완화, u4 평가에 필수)*

X) Other (please describe after [Answer]: tag below)

[Answer]: B

### DQ-6
**외부 AI 모델 추상화(포트)** 를 어떻게 나눕니까? (NFR-21)

A) 단일 `AIPort` — 생성·임베딩·리랭킹을 한 인터페이스에 통합

B) 3개 포트로 분리 — `LLMPort`(생성) / `EmbeddingPort`(임베딩) / `RerankerPort`(재정렬).
   각각 제공자·수명주기·비용 특성이 다름 *(권장)*

X) Other (please describe after [Answer]: tag below)

[Answer]: B

### DQ-7
**프롬프트 관리** 방식은? (NFR-22)

A) 저장소 내 템플릿 파일 + 버전 식별자. 평가 결과에 사용된 프롬프트 버전을 함께 기록 *(권장 — u4 평가와 연동)*

B) DB에 저장하고 화면에서 편집

C) 코드 내 상수로 관리

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### DQ-8
**인용(citation) 생성 방식**은? — FR-19·FR-21의 구현 난이도를 좌우하는 핵심 결정입니다.

A) LLM이 **구조화 출력(JSON)** 으로 `{문장, 근거 청크 ID 목록}` 배열을 반환.
   서버가 이를 렌더링하고 검증 *(권장 — 검증이 결정론적으로 가능)*

B) LLM이 본문에 `[1]`, `[2]` 마커를 직접 삽입한 자연어 텍스트를 반환. 서버가 마커를 파싱

C) LLM은 일반 텍스트만 생성하고, 서버가 사후에 문장-근거 유사도 매칭으로 인용을 부여

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### DQ-9
**답변 거부 판정**을 어디서 수행합니까? (FR-20, FR-21)

A) 검색 단계 1회만 — 리랭킹 스코어가 임계값 미달이면 생성하지 않고 거부

B) 2단 판정 — ① 검색 스코어 임계값(생성 전 차단) + ② 생성 후 근거 지지 검증(미지지 문장 제거 또는 전체 거부)
   *(권장 — FR-20과 FR-21이 각각 요구하는 지점)*

X) Other (please describe after [Answer]: tag below)

[Answer]: B

### DQ-10
**물질 안전 카드(FR-23~26)** 의 데이터는 어떻게 만듭니까?

A) 구조화 DB를 직접 조회하여 조립. LLM 미사용. 없는 항목은 "정보 없음" *(권장 — NFR-3 1초, NFR-8 추정 금지)*

B) 검색된 문서를 LLM으로 요약하여 카드 생성

C) 구조화 DB 우선, 비어 있는 항목만 LLM 요약으로 보완 (요약 항목은 출처와 함께 명시 표기)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### DQ-11
**물질명 동의어 매칭(FR-26)** 은 어떻게 구현합니까?

A) 별도 `substance_synonym` 테이블 — 국문명·영문명·이명·CAS·UN번호를 정규화 키로 색인 *(권장)*

B) 벡터 유사도 검색으로 처리

C) 물질 테이블의 배열 컬럼에 이명 저장

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## 서비스 계층 및 의존 관계

### DQ-12
**API 계층과 서비스 계층의 두께**는?

A) Thin router + Fat service — 라우터는 검증·직렬화만, 오케스트레이션은 서비스가 담당 *(권장)*

B) Fat router — 라우터에서 직접 컴포넌트 호출

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### DQ-13
**비동기 작업(수집·색인·업로드)의 상태 관리**는? (FR-6 진행률, FR-7 증분, FR-8 부분 실패)

A) 자체 `Job` / `JobItem` 테이블로 관리 — 진행률, 항목별 부분 실패, 재개 지점을 직접 제어.
   큐 백엔드는 실행만 담당 *(권장 — 큐 교체 가능성 확보)*

B) 큐 백엔드(Celery/ARQ)의 결과 저장소에 상태를 위임

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### DQ-14
**컴포넌트 간 통신 패턴**은?

A) 직접 호출(의존성 주입) + 비동기 경계에서만 큐 사용 *(권장 — 단일 저장소·단일 배포 단위에 적합)*

B) 내부 이벤트 버스 도입 — 컴포넌트 간 느슨한 결합

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### DQ-15
**데이터 접근 계층**은?

A) SQLAlchemy 2.x ORM + Alembic 마이그레이션. pgvector 타입은 확장 라이브러리로 통합 *(권장)*

B) raw SQL + 경량 쿼리 빌더

C) SQLAlchemy Core (ORM 없이)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### DQ-16
**LLM 호출 추적(FR-41)** 은 어디에 배치합니까?

A) `LLMPort` 구현을 감싸는 **데코레이터 컴포넌트** — 모든 호출이 자동 계측되며 호출부는 추적을 모름 *(권장)*

B) 각 서비스에서 명시적으로 추적 코드 호출

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## 프레젠테이션 및 운영

### DQ-17
**인용 스니펫 하이라이트(FR-19)** 의 프론트엔드 구현은?

A) 서버 렌더링 + 최소한의 바닐라 JS — 마커 클릭 시 이미 렌더된 스니펫 영역을 토글 *(권장 — JS 없이도 링크로 열람 가능하게 폴백)*

B) 클릭 시 서버에 요청하여 스니펫을 가져오는 부분 렌더링(HTMX 등)

C) JS 없이 전부 펼쳐진 상태로 렌더링

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### DQ-18
**평가 실행(FR-37~39)** 의 진입점은?

A) CLI 명령을 1차 진입점으로 하고(CI 회귀 테스트 연동 — NFR-26), 결과는 운영 화면에서 조회 *(권장)*

B) API 엔드포인트에서 실행하고 화면에서 조회

C) 둘 다 제공

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

# 3부. 자유 기술

### DQ-19
설계 관련하여 추가로 반영할 제약이나 선호가 있습니까?

A) 없음

B) 있음 (아래 [Answer]: 뒤에 기술)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

**답변 완료 후 채팅에 "완료" 또는 "권장안대로 진행" 이라고 알려 주세요.**
답변의 모호성·모순을 검증한 뒤 `inception/application-design/` 에 설계 산출물 5종을 생성합니다.
