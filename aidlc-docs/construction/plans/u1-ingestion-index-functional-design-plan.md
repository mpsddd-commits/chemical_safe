# Functional Design Plan — u1-ingestion-index

**프로젝트**: safeenv
**단계**: 🟢 CONSTRUCTION / Functional Design — 유닛 `u1-ingestion-index`
**작성일**: 2026-08-20
**상태**: 답변 확정 + 산출물 4종 생성 완료

---

## 답변 방법

**2부 설계 질문(FQ-1 ~ FQ-18)** 의 `[Answer]:` 태그 뒤에 선택지 문자를 적어 주세요.
*(권장)* 표시는 요구사항·설계 결정에 비추어 유리한 선택지입니다.

**"권장안대로 진행"** 이라고 하시면 *(권장)* 선택지로 채운 뒤 설계 산출물 3종을 생성합니다.

---

## 유닛 컨텍스트

| 항목 | 내용 |
|---|---|
| **유닛** | `u1-ingestion-index` — 수집 · 문서처리 · 색인 (기반) |
| **FR** | FR-1~13, FR-40, FR-43, FR-48 — **16건** |
| **NFR 검증** | NFR-4, 9, 10, 14, 17, 20, 21, 23, 29, 30, 31 |
| **컴포넌트** | C1~C29, C58, C59, C60 — **32종** |
| **서비스** | S1 `IngestionService`, S2 `IndexingService` |
| **완료 시 시연** | 운영 화면에서 수집 실행 → 진행률·부분 실패 확인 → 물질 1,000종의 청크·벡터 적재 |
| **주요 위험** | R-1 API 키·스펙 / R-2 PDF 파싱 실패율 / R-3 임베딩 속도 |

### 이 단계에서 확정할 이월 항목 (`components.md` §15 의 1~6번)

1. DB 스키마 상세 (테이블·컬럼·인덱스·제약)
2. 청킹 크기·중첩·경계 판정 규칙
3. MSDS 16섹션 매핑 규칙 및 섹션 인식 실패 처리
4. 법령 조·항·호 분해 규칙
5. 문서 유형별 필수 메타데이터와 누락 시 처리
6. 재시도 정책 파라미터 및 오류 분류 체계

---

# 1부. 설계 실행 계획 (체크리스트)

### 1. 컨텍스트 로드
- [x] 1.1 `unit-of-work.md` — u1 정의, DoD, 코드 조직 전략, 마이그레이션 전략
- [x] 1.2 `unit-of-work-story-map.md` — u1 의 FR 16건 및 NFR 검증 항목
- [x] 1.3 `application-design/` — C1~C29 책임과 메서드 시그니처, DD-1~DD-25

### 2. 도메인 엔터티 설계
- [x] 2.1 핵심 엔터티 식별 (물질, 동의어, 문서, 추출텍스트, 섹션, 청크, 작업, 작업항목, 소스)
- [x] 2.2 엔터티 속성·타입·제약 정의
- [x] 2.3 엔터티 관계 및 카디널리티 정의
- [x] 2.4 Enum 및 코드 값 정의 (문서유형, 작업상태, 항목상태, 실패분류, 정책판정)
- [x] 2.5 인덱스 설계 (CAS·물질명 정확 매칭, 벡터 인덱스, 전문검색 인덱스)
- [x] 2.6 **u3·u5 선반영 요소 반영** — `chunk.owner_id`, `substance_synonym` (DD-21, UD-6)

### 3. 비즈니스 로직 모델 설계
- [x] 3.1 수집 워크플로 (정책검사 → 대상목록 → 변경감지 → 수집 → 기록)
- [x] 3.2 문서 처리 파이프라인 워크플로 (Fetch → Extract → Normalize → Structure → Chunk)
- [x] 3.3 색인 워크플로 (임베딩 → 벡터적재 → 키워드색인)
- [x] 3.4 재색인 워크플로 (문서 단위 / 전체)
- [x] 3.5 작업 상태 전이 모델 (Job / JobItem)
- [x] 3.6 부분 실패 및 재개 흐름
- [x] 3.7 운영 화면 구성 및 조회 흐름

### 4. 비즈니스 규칙 정의
- [x] 4.1 수집 정책 규칙 (BR)
- [x] 4.2 변경 감지 규칙
- [x] 4.3 문서 유형별 구조 분해 규칙 (MSDS 16섹션 / 법령 조·항·호 / 사고사례)
- [x] 4.4 청킹 규칙 (크기·중첩·경계)
- [x] 4.5 메타데이터 필수·선택 규칙 및 누락 처리
- [x] 4.6 재시도·오류 분류 규칙
- [x] 4.7 작업 최종 상태 판정 규칙
- [x] 4.8 멱등성 및 중복 처리 규칙
- [x] 4.9 로깅·마스킹 규칙

### 5. 프론트엔드 컴포넌트 설계 (FR-48 운영 화면)
- [x] 5.1 화면 구성 및 라우트
- [x] 5.2 화면별 표시 항목과 상호작용
- [x] 5.3 폼 검증 규칙
- [x] 5.4 API 연동 지점

### 6. 산출물 생성
- [x] 6.1 `construction/u1-ingestion-index/functional-design/domain-entities.md`
- [x] 6.2 `construction/u1-ingestion-index/functional-design/business-logic-model.md`
- [x] 6.3 `construction/u1-ingestion-index/functional-design/business-rules.md`
- [x] 6.4 `construction/u1-ingestion-index/functional-design/frontend-components.md`

### 7. 검증
- [x] 7.1 u1 의 FR 16건 전건이 비즈니스 규칙으로 표현되었는지 확인
- [x] 7.2 이월 항목 1~6번 전건 확정 확인
- [x] 7.3 NFR 검증 항목의 설계 반영 확인
- [x] 7.4 u2~u5 확장 지점 선반영 확인

---

# 2부. 설계 질문

## 청킹 및 문서 구조

### FQ-1
**청킹 경계 규칙**은? (이월 2번)

A) **섹션 1개 = 청크 1개**를 기본으로 하되, 최대 크기를 초과할 때만 문단 경계로 분할
   *(권장 — MSDS 16섹션·법령 조 단위가 이미 의미 단위이므로 구조 보존이 검색 품질에 유리)*

B) 고정 크기 슬라이딩 윈도우 — 구조 무시, 일정 토큰 수로 균등 분할

C) 의미 기반 분할 — 임베딩 유사도로 경계 탐지

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### FQ-2
**청크 최대 크기와 중첩**은?

A) 최대 1,000 토큰 / **중첩 없음** — 섹션 경계가 명확하므로 문맥 손실이 적음 *(권장)*

B) 최대 512 토큰 / 15% 중첩

C) 최대 1,500 토큰 / 10% 중첩

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### FQ-3
**MSDS 16섹션 인식에 실패한 문서**는 어떻게 처리합니까? (이월 3번, 위험 R-2)

A) "구조 미상"으로 표시하고 **문단 단위 청킹으로 폴백**. 검색 대상에는 포함하되 섹션 메타는 NULL
   *(권장 — 파싱 실패가 곧 데이터 손실이 되지 않도록)*

B) 색인하지 않고 격리 — 수동 검토 대상으로 분류

C) 색인하되 검색 스코어에 페널티 부여

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### FQ-4
**법령 조문의 분해 단위**는? (이월 4번)

A) **조(條) 단위를 청크**로 하고 항·호는 청크 내 구조와 메타데이터로 보존
   *(권장 — 조 단위가 인용의 자연스러운 단위이며 문맥이 유지됨)*

B) 항(項) 단위를 청크로 — 더 정밀하나 문맥 손실

C) 조 단위와 항 단위를 **이중 색인** — 검색 품질 최상, 저장·색인 비용 2배

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### FQ-5
**스니펫 하이라이트의 기준 텍스트**는? (DD-4 3계층 보존과 연관)

A) **정규화된 추출 텍스트**를 기준으로 오프셋 관리. 청크는 이 텍스트의 구간을 가리키고,
   화면에는 이 텍스트의 스니펫을 표시. 원본 PDF는 링크로 제공 *(권장 — 단순하고 충분)*

B) **PDF 원본 좌표까지 역추적** — 원본 PDF 뷰어에 하이라이트 렌더링. 구현 난이도 크게 상승

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## 데이터 모델

### FQ-6
**문서와 물질의 관계**는? (MSDS는 물질에 귀속되지만 법령·사고사례는 다릅니다)

A) **다대다 관계 테이블** — 법령은 물질 미연결 가능, 사고사례는 언급된 물질 다건 연결,
   MSDS는 통상 1건 연결 *(권장)*

B) 문서당 물질 1개 (nullable) — 단순하나 사고사례의 복수 물질 표현 불가

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### FQ-7
**필수 메타데이터 누락 시** 처리는? (이월 5번)

A) **출처 URL과 문서 유형이 없으면 색인 거부** — "출처를 알 수 없는 데이터는 색인하지 않는다"
   원칙 적용. 나머지 항목(CAS, 발행일 등)은 NULL 허용 *(권장 — requirements.md §5 데이터 원칙)*

B) 전 항목 NULL 허용 — 최대한 많은 데이터를 확보

C) 전 항목 필수 — 완전한 데이터만 색인

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### FQ-8
**원본 파일 보관 범위**는? (DD-4)

A) **PDF 원본은 볼륨에 보관**, API 구조화 데이터는 **원본 응답(JSON/XML)을 보관** —
   파싱 규칙 변경 시 재수집 없이 재파싱 가능 *(권장)*

B) 원본 미보관, 출처 URL만 기록 — 저장 공간 절약, 재파싱 시 재수집 필요

C) PDF만 보관, API 응답은 미보관

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## 수집 동작

### FQ-9
**증분 감지 기준**은? (FR-7)

A) **콘텐츠 해시 우선**, 해시 계산이 불가한 경우(스트리밍·대용량) 발행·개정일로 대체 *(권장)*

B) 발행·개정일 우선

C) 항상 전건 재처리 — 단순하나 NFR-4 위반 위험

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### FQ-10
**재시도 정책 파라미터**는? (이월 6번)

A) 최대 **3회**, 지수 백오프 **1초 / 4초 / 16초**, 항목당 총 대기 상한 60초 *(권장)*

B) 최대 5회, 백오프 2초부터 배증

C) 재시도 없음 — 실패 항목은 재실행 시 재개

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### FQ-11
**오류 분류 체계**는? (이월 6번)

A) **3종** — `transient`(네트워크·타임아웃·5xx) / `permanent`(4xx·파싱 불가·스키마 불일치) /
   `policy_blocked`(robots·이용약관 거부) *(권장 — policy_blocked 는 재시도해서는 안 되는 별개 범주)*

B) 2종 — 재시도 가능 / 재시도 불가

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### FQ-12
**작업 최종 상태 판정 기준**은? (FR-8 부분 성공)

A) 1건 이상 성공 = `partial`, 전건 실패 = `failed`, 전건 성공 = `succeeded` *(권장 — 단순·명확)*

B) 성공률 임계값 기준 — 예: 90% 이상이면 `succeeded`, 그 미만이면 `partial`

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### FQ-13
**공공 API 인증키 미설정** 시 동작은? (위험 R-1)

A) 앱은 정상 기동하되, 해당 소스 수집 시도 시 **명확한 오류 메시지**와 함께 작업 실패
   *(권장 — 일부 소스만으로도 개발·시연 가능)*

B) 인증키가 하나라도 없으면 기동 실패

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### FQ-14
**초기 수집 대상 물질 1,000종**을 어떻게 선정합니까?

A) **사고 사례에 등장한 물질 + 법령 규제 대상 물질**을 우선 선정
   *(권장 — 실제 질의가 발생할 가능성이 높고, 3종 코퍼스가 서로 연결됨)*

B) CAS 번호 순으로 상위 1,000종

C) 무작위 샘플

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## 색인 및 운영

### FQ-15
**임베딩 배치 크기와 워커 수**의 초기값은? (NFR-4, 위험 R-3)

A) 배치 **32**, 워커 **1개**로 시작하고 설정으로 조정 *(권장 — 로컬 환경 메모리 안전)*

B) 배치 128, 워커 2개 — 처리량 우선

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### FQ-16
**수집 실행 트리거**는?

A) **운영 화면 버튼 + CLI** 두 경로 *(권장)*

B) CLI 만

C) 스케줄 자동 실행 추가 — 요구사항에는 없음

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### FQ-17
**u1 시점의 운영 화면(FR-48)** 구성은?

A) **소스 목록**(마지막 수집 시각·정책 상태) + **작업 목록**(상태·진행률) +
   **작업 상세**(항목별 성공/실패/사유) *(권장 — 부분 실패를 사용자가 실제로 진단 가능)*

B) 작업 목록만

C) A + 로그 뷰어

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## 자유 기술

### FQ-18
u1 설계와 관련하여 추가로 반영할 사항이 있습니까?

A) 없음

B) 있음 (아래 [Answer]: 뒤에 기술)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

**답변 완료 후 채팅에 "완료" 또는 "권장안대로 진행" 이라고 알려 주세요.**
답변의 모호성·모순을 검증한 뒤 `construction/u1-ingestion-index/functional-design/` 에
산출물 4종을 생성합니다.
