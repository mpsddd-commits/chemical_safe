# Infrastructure Design Plan — u1-ingestion-index

**프로젝트**: safeenv
**단계**: 🟢 CONSTRUCTION / Infrastructure Design — 유닛 `u1-ingestion-index`
**작성일**: 2026-08-20
**상태**: 답변 확정 + 산출물 2종 생성 완료

---

## 답변 방법

**2부 인프라 질문(IQ-1 ~ IQ-17)** 의 `[Answer]:` 태그 뒤에 선택지 문자를 적어 주세요.
*(권장)* 표시는 요구사항·설계 결정에 비추어 유리한 선택지입니다.

**"권장안대로 진행"** 이라고 하시면 *(권장)* 선택지로 채운 뒤 산출물 2종을 생성합니다.

---

## 유닛 컨텍스트

| 항목 | 내용 |
|---|---|
| **유닛** | `u1-ingestion-index` — 이 단계에서 **전체 Compose 토폴로지를 확립**합니다 (u2~u5는 인프라 변경 없음) |
| **관련 NFR** | NFR-9(청크 10만), NFR-10(워커 확장), NFR-14(비밀값), **NFR-18(루프백 바인딩)**, NFR-29(단일 명령 기동), NFR-30(비루트), NFR-31(볼륨 영속화) |
| **제약** | CON-2 포트 `127.0.0.1:8200` / CON-4 로컬 Docker Compose / CON-5 로컬 임베딩 모델 다운로드 / CON-7 Security Baseline 활성 |
| **선행 결정** | DD-13 작업 상태는 자체 테이블 / DD-15 PostgreSQL + pgvector / DD-23 벡터·키워드 동일 트랜잭션 / UD-3 단일 이미지 모놀리스 |

### ⚠️ 이 단계에서 해소할 미결 항목

`application-design.md` §6에서 **NFR-18(루프백 바인딩)** 이 Infrastructure Design 으로 이월되었고,
`frontend-components.md` §9에서 **u1 시점 `/admin` 무인증 노출**이 이 단계의 접근 통제에 의존한다고
기록되어 있습니다. 두 항목을 여기서 확정합니다.

---

# 1부. 인프라 설계 실행 계획 (체크리스트)

### 1. 컨텍스트 로드
- [x] 1.1 `functional-design/` 4종 — 엔터티 12종, 워크플로 6종, BR-01~BR-62
- [x] 1.2 `application-design/` — 컴포넌트 계층, 진입점 C56~C60
- [x] 1.3 `unit-of-work.md` §2 — 배포 모델, 디렉터리 구조, 마이그레이션 전략

### 2. 컴퓨트 인프라 설계
- [x] 2.1 컨테이너 구성 및 역할 확정
- [x] 2.2 베이스 이미지 및 빌드 전략
- [x] 2.3 프로세스별 실행 명령 정의
- [x] 2.4 리소스 제한 설정
- [x] 2.5 컨테이너 사용자 및 권한

### 3. 스토리지 인프라 설계
- [x] 3.1 데이터베이스 이미지 및 확장
- [x] 3.2 볼륨 구성 및 마운트 지점
- [x] 3.3 원본 파일 보관 위치
- [x] 3.4 임베딩 모델 캐시 전략
- [x] 3.5 백업·복원 방침

### 4. 메시징 인프라 설계
- [x] 4.1 큐 백엔드 선택
- [x] 4.2 워커 실행 및 확장 방식
- [x] 4.3 작업 가시성 타임아웃 및 중복 실행 방지

### 5. 네트워킹 설계
- [x] 5.1 포트 매핑 및 바인딩 (**NFR-18 확정**)
- [x] 5.2 컨테이너 간 네트워크
- [x] 5.3 외부 통신 경로 (공공 API, 모델 다운로드)

### 6. 관측 인프라 설계
- [x] 6.1 로그 출력 및 수집 방식
- [x] 6.2 헬스체크 구현 방식
- [x] 6.3 컨테이너 상태 확인 절차

### 7. 공유 인프라 검토
- [x] 7.1 상위 워크스페이스의 다른 프로젝트와의 충돌 6축 점검
- [x] 7.2 `shared-infrastructure.md` 생성 필요 여부 판단

### 8. 산출물 생성
- [x] 8.1 `construction/u1-ingestion-index/infrastructure-design/infrastructure-design.md`
- [x] 8.2 `construction/u1-ingestion-index/infrastructure-design/deployment-architecture.md`

### 9. 검증
- [x] 9.1 NFR-14, 18, 29, 30, 31 반영 확인
- [x] 9.2 Security Baseline 관점 검토
- [x] 9.3 u2~u5 인프라 변경 불필요 확인

---

# 2부. 인프라 질문

## 컴퓨트

### IQ-1
**컨테이너 구성**은?

A) **4개** — `app`(웹) / `worker` / `postgres` / `redis`(큐 백엔드)
   *(권장 — Q23=B가 "별도 워커 + 작업 큐"를 선택했고 NFR-10 워커 수평 확장이 요구됨.
   BR-62 임베딩 캐시의 저장소로도 활용 가능)*

B) **3개** — `app` / `worker` / `postgres`. 큐를 PostgreSQL 기반으로 구현
   (`SELECT ... FOR UPDATE SKIP LOCKED`). 컨테이너 1개 절약.
   DD-13으로 작업 상태가 이미 자체 테이블에 있으므로 기술적으로 충분함

C) **2개** — `app`(웹+워커 동일 프로세스) / `postgres`. Q23=B 결정과 배치됨

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### IQ-2
**애플리케이션 베이스 이미지**는?

A) `python:3.12-slim` **멀티스테이지 빌드** — 빌드 의존성을 런타임에 포함하지 않음 *(권장)*

B) `python:3.12` (full) — 빌드 도구 포함, 이미지 큼

C) distroless — 최소 크기이나 디버깅 어려움

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### IQ-3
**리소스 제한**을 설정합니까?

A) 제한 없음 — 로컬 개발이므로 단순하게

B) **메모리 제한 설정** — `postgres` 2G / `app` 2G / `worker` 4G / `redis` 512M
   *(권장 — 임베딩 워커의 메모리 사용이 호스트를 멈추게 하는 상황 방지. 위험 R-3)*

X) Other (please describe after [Answer]: tag below)

[Answer]: B

### IQ-4
**컨테이너 실행 사용자**는?

A) **비루트** `appuser` (uid 10001) *(권장 — NFR-30)*

B) 루트

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## 스토리지

### IQ-5
**PostgreSQL 이미지**는?

A) `pgvector/pgvector:pg16` — pgvector 확장이 포함된 공식 이미지 *(권장)*

B) `postgres:16` + 확장 직접 빌드·설치

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### IQ-6
**임베딩 모델 파일**을 어떻게 확보합니까? (CON-5)

A) **볼륨 캐시** — 최초 기동 시 다운로드하여 볼륨에 저장, 이후 재사용.
   이미지 크기가 작게 유지됨 *(권장)*

B) **이미지 빌드 시 포함** — 오프라인 기동 가능하나 이미지가 수 GB로 증가

C) 별도 init 컨테이너로 사전 다운로드

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### IQ-7
**볼륨 구성**은?

A) **4개 분리** — `pgdata`(DB) / `originals`(원본 보관) / `models`(임베딩 캐시) / `logs`
   *(권장 — 각각 크기 특성과 백업 필요성이 다름)*

B) 2개 — `pgdata` / `appdata`(나머지 통합)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### IQ-8
**원본 파일 보관 위치**는? (BR-12)

A) **호스트 바인드 마운트** `./data/originals` — 파싱 문제 진단 시 원본 PDF를 직접 열어볼 수 있음
   *(권장 — 위험 R-2 대응에 유리)*

B) 명명된 볼륨 — 호스트에서 직접 접근 불가

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### IQ-9
**백업·복원** 방침은?

A) 없음 — 볼륨 영속화로 충분하며, 손실 시 재수집

B) **`pg_dump` 기반 수동 백업·복원 스크립트 제공**
   *(권장 — 초기 색인에 최대 8시간이 걸리므로(NFR-4) 볼륨 손실 비용이 큼. 스크립트 2개로 해결)*

X) Other (please describe after [Answer]: tag below)

[Answer]: B

## 메시징

### IQ-10
**마이그레이션 실행 시점**은? (`app` 과 `worker` 가 동시에 기동하면 경합이 발생합니다)

A) `app` 컨테이너 기동 시 자동 실행, `worker` 는 대기 — 단순하나 암묵적 순서 의존

B) **일회성 `migrate` 서비스**를 먼저 실행하고, 완료 후 `app`·`worker` 기동
   (`depends_on: service_completed_successfully`) *(권장 — 경합이 구조적으로 불가능)*

C) 수동 CLI 실행

X) Other (please describe after [Answer]: tag below)

[Answer]: B

### IQ-11
**워커 실행 방식과 확장**은? (NFR-10)

A) 기본 **워커 1개**, `docker compose up --scale worker=N` 으로 확장 가능하게 구성
   *(권장 — BR-61 기본값과 일치하며 확장 경로를 열어 둠)*

B) 고정 2개

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## 네트워킹

### IQ-12
**포트 매핑**은? (**NFR-18 확정 지점**)

A) `app` 만 **`127.0.0.1:8200`** 으로 노출. `postgres`·`redis` 는 **내부 네트워크 전용**
   (호스트 노출 없음) *(권장 — Security Baseline 활성, 최소 노출 원칙.
   DB 툴 접속이 필요하면 `docker-compose.override.yml` 로 개발 시에만 개방)*

B) `app` `127.0.0.1:8200` + `postgres` `127.0.0.1:8232` 노출 — DB 툴 접속 편의

C) 전부 `0.0.0.0` 노출 — **NFR-18 위반**

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### IQ-13
**u1 시점 `/admin` 무인증 노출**에 대한 대응은? (`frontend-components.md` §9)

A) **루프백 바인딩만으로 통제**하고, u5에서 인증 도입 시 `/admin` 을 인증 필수 경로로 전환.
   그때까지 README와 화면 상단에 "인증 없음 — 로컬 전용" 경고 표시 *(권장)*

B) u1 시점에 **기본 인증(Basic Auth)** 을 임시로 적용 — 환경변수로 사용자·비밀번호 설정

C) 대응 없음

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## 관측

### IQ-14
**로그 출력** 방식은? (FR-40, BR-57)

A) **stdout/stderr 로 구조적 JSON 출력** + `logs` 볼륨에 파일 병행 기록
   *(권장 — `docker compose logs` 로 즉시 확인 가능하면서 이력도 보존)*

B) 파일만

C) stdout 만

X) Other (please describe after [Answer]: tag below)

[Answer]: A

### IQ-15
**컨테이너 헬스체크** 구현은?

A) **Python 인터프리터로 HTTP 요청** — slim 이미지에 curl 이 없으므로 추가 설치 불필요 *(권장)*

B) curl 을 설치하여 사용

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## 공유 인프라

### IQ-16
상위 워크스페이스 `c:\Users\403\IDE` 에는 다른 AI-DLC 프로젝트가 존재하며
`news`(8100), `petmate`(8000/5173) 등이 동시 기동될 수 있습니다.

A) **인프라 6축을 전부 분리**하여 충돌을 원천 차단 —
   Compose 프로젝트명 / 네트워크명 / 포트 / 볼륨명 / 이미지명 / 컨테이너명.
   `shared-infrastructure.md` 는 생성하지 않음 *(권장)*

B) 공유 인프라 문서를 작성하고 일부 자원을 공유

X) Other (please describe after [Answer]: tag below)

[Answer]: A

## 자유 기술

### IQ-17
인프라 설계와 관련하여 추가로 반영할 사항이 있습니까?

A) 없음

B) 있음 (아래 [Answer]: 뒤에 기술)

X) Other (please describe after [Answer]: tag below)

[Answer]: A

---

**답변 완료 후 채팅에 "완료" 또는 "권장안대로 진행" 이라고 알려 주세요.**
검증 후 `construction/u1-ingestion-index/infrastructure-design/` 에 산출물 2종을 생성합니다.
