# Traceability — u3-substance-card

**작성일**: 2026-08-26
**범위**: FR 5건 / BR-97~110 (14건) / 엔터티 신규 0 / 컴포넌트 C49·C50 + S4

---

## 1. FR → 구현

| FR | 내용 | 구현 | 테스트 |
|---|---|---|---|
| **FR-1** *(u1)* | 물질정보 수집 | `substances/projection.py` | 단위 24 / 통합 4 |
| FR-23 | 카드 반환 | `services/substance_service.py` | 통합 5 |
| FR-24 | 7개 항목 | `substances/card.py` | 통합 2 |
| FR-25 | 항목별 출처 · 결측 표시 | `card.py`, `types.py` | 통합 2 |
| FR-26 | 동의어 검색 | `substances/lookup.py` | 통합 4 |
| FR-45 | 카드 화면 | `templates/substances*.html` | 실측 (HTML 마커) |

> **FR-1 이 u3 표에 있는 이유**: u1 요구사항이고 u1 규칙(BR-33·37)이지만 구현된 적이
> 없었다(결함 40). 여기서 처음 구현된다.

---

## 2. BR → 구현

### 투영 (BR-97~99) — 결함 40

| BR | 구현 | 비고 |
|---|---|---|
| **BR-97** 색인 경로 안에서 투영 | `IndexingService._project_substance` | 분리된 쓰기 경로가 결함의 원인이었다 |
| **BR-98** CAS 기준 upsert, 멱등 | `SubstanceRepo.upsert` + `replace_synonyms` | **결함 42·43** |
| **BR-99** 이명 생성 금지 | `SubstanceFacts.synonym_terms` | ko·en 만. 단위 5건 |

### 조회 (BR-100·101)

| BR | 구현 | 비고 |
|---|---|---|
| BR-100 색인과 같은 정규화 | `lookup.search` → u1 `normalize()` | |
| **BR-101** 모호하면 목록, 고르지 않음 | `lookup._by_name` + `matched_on` | 부분일치로 이웃을 노출 |

### 카드 (BR-102~107)

| BR | 구현 | 비고 |
|---|---|---|
| **BR-102** 7항목 고정 순서 | `card.build` → `for key in CardItemKey` | 통합 1 + HTML 실측 |
| **BR-103** 다중 출처 전부 | `card._values_for` | |
| BR-104 원문 그대로 | `card._value` | 요약 없음 |
| BR-105 출처 표기 | `ItemValue` 필수 필드 | 통합 1 |
| **BR-106** 결측 고지 | `SubstanceCard.missing_count` | 데이터에 실려 다닌다 |
| **BR-107** 스냅샷 미사용 | `card.py` — E17 참조 없음 | 카드는 현재 상태 조회 |

### 미충족 고지 (BR-108~110)

| BR | 구현 | 비고 |
|---|---|---|
| **BR-108** 구조화 GHS 컬럼 미기입 | `SubstanceFacts` 에 필드 없음 | 단위 1 |
| **BR-109** UN 은 "데이터 없음" | `lookup.search` UN 분기 유지 | 통합 1 |
| **BR-110** `un`·`alias` 열거 유지 | `core.types.MatchKind` | 미충족을 숨기지 않는다 |

---

## 3. u1·u2 규칙에 준 영향

| 규칙 | 이전 | 이후 |
|---|---|---|
| **BR-33** 물질 저장 | 미구현 | ✅ 40건 |
| **BR-37** 문서↔물질 연결 | 0행 | ✅ 40건 |
| **BR-38** CAS 완전일치 (u1) | `meta.cas_number` 0건 → **매칭 대상 없음** | ✅ **273건** |
| **BR-65** 동의어 해석 (u2) | 표 0행 → 항상 미해석 | ✅ **80건** |
| **BR-64** 규칙 우선 (u2) | 규칙이 아무것도 못 찾음 → 항상 LLM | ✅ 물질명이 해석된다 |
| BR-44 원본 보존 | — | 투영의 재료. 재수집 0 |
| BR-54 재색인 전량 교체 | — | BR-98 이 같은 철학을 동의어에 적용 |

> **u3 이 u2 를 되살렸다.** `ENTITY_LLM_ENABLED` 를 껐던 근거(결함 32: "물질 마스터가
> 비어 `substance_names` 를 해석할 대상이 없다")가 이제 성립하지 않는다.
> 켜는 것이 값을 하는지는 **재측정이 필요하며, 아직 하지 않았다.**

---

## 4. 엔터티

| 엔터티 | 표 | 마이그레이션 | 상태 |
|---|---|---|---|
| E2 `substance` | u1 | 없음 | ✅ 40행 |
| E3 `substance_synonym` | u1 | 없음 | ✅ 80행 |
| E10 `document_substance` | u1 | 없음 | ✅ 40행 |

**신규 0개.** u1 선반영(DD-21, UD-6) 회수.

---

## 5. 컴포넌트

| ID | 컴포넌트 | 파일 |
|---|---|---|
| C49 | SubstanceLookup | `substances/lookup.py` |
| C50 | SubstanceCardBuilder | `substances/card.py` |
| S4 | SubstanceService | `services/substance_service.py` |
| — | 투영 (u1 규칙) | `substances/projection.py` |

---

## 6. 미매핑 점검

| 검사 | 결과 |
|---|---|
| FR 미구현 | **0** |
| BR-97~110 미구현 | **0** |
| 엔터티 미생성 | **0** (신규 없음) |
| u1·u2 규칙 위반 | **0** — BR-54 재색인 경로 무변경 |
| 순환 의존 | **0** — `substances` → `db`·`core`·`processing` |
| LLM 의존 | **0** — 이 유닛은 LLM 을 호출하지 않는다 |

---

## 7. 미충족 (숨기지 않고 기록)

| 항목 | 상태 | 근거 |
|---|---|---|
| **FR-26 UN 번호** | ❌ 데이터 없음 | 출처에 `un_number` 필드가 없다 (BR-109) |
| **FR-26 이명** | ❌ 데이터 없음 | 출처에 이명이 없다. 생성하지 않는다 (BR-99) |
| **FR-24 항목 6종** | ⚠️ 부분 | MSDS 보유 물질(~7건)에서만 채워진다. FR-25 가 예상한 상황 |
| **BR-108 구조화 컬럼** | ⚠️ 의도적 NULL | 신뢰할 수 있는 출처가 생기면 채울 자리 |
| **BR-08 ② `is_regulated`** | ❌ 데이터 없음 | `/kischemlist` 응답에 규제 여부 필드가 없다 (2026-08-27) |

> FR-26 의 5종 중 3종이 동작한다. 이를 "충족"이라고 쓰지 않는다.

---

## 8. u1 규칙 BR-08 구현 (2026-08-27, 결함 44 해소)

u3 의 산출물이 아니라 **u3 가 드러낸 u1 의 미구현**이다. 물질 카드 40건이 전부
6/7 결측이었고, 원인은 카드 로직이 아니라 마스터에 코퍼스가 문서를 가진 물질이
**한 건도 없었다**는 것이었다.

| 규칙 | 이전 | 이후 |
|---|---|---|
| BR-08 ① 사고 물질 우선 | 미구현 (단순 절단) | ✅ 사고 `substances` 구간 + **MSDS 문서 제목** |
| BR-08 ② 규제 물질 | 미구현 | ❌ 소스에 필드 없음 — 위 표에 기록 |

**매칭은 정규화 후 완전일치.** 부분일치는 7,189행 전량 스캔으로 재보고 폐기했다
("톨루엔" 68건 / "황산" 56건의 부분문자열 → 예산이 유도체로 찬다).

신규 `app/ingestion/substance_selection.py` (순수 함수), `DocumentRepo.substance_mentions()`,
`SubstanceApiAdapter.priority_terms`. 어댑터는 DB 를 보지 않는다 — 용어는
`IngestionService` 가 읽어 주입하고, 비어 있으면 이전과 완전히 동일하게 동작한다.

부수로 **결함 46**: 목록 소진 시 data.go.kr 이 `items: ""` 를 보내 `_rows()` 가
스키마 오류를 던졌다. 전량 수집이 맨 끝에서 실패하는 경로이고, 목표 건수가 항상
먼저 루프를 끊었기 때문에 한 번도 실행된 적이 없었다.
