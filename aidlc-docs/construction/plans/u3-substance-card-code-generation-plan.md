# Code Generation Plan — u3-substance-card

**단계**: 🟢 CONSTRUCTION / Code Generation — 유닛 `u3-substance-card` (3/5)
**작성일**: 2026-08-26
**선행 승인**: Functional Design (2026-08-26)

---

## 유닛 컨텍스트

| 항목 | 내용 |
|---|---|
| **FR** | FR-23~26, FR-45 (5건) / **BR** BR-97~BR-110 (14건) |
| **엔터티** | **신규 0개.** u1 의 `substance`·`substance_synonym`·`document_substance` 사용 |
| **마이그레이션** | **없음** |
| **LLM** | **사용하지 않는다** — 무료 티어 제약 없음 |

---

## 실측으로 확인한 배선 (계획 수정 사항)

### 결함 40 은 읽기 경로도 어긋나 있었다

```python
# adapters/sources/api_sources.py — 목록이 만드는 것
SourceRef(..., extra={"row": row})          # 레코드는 "row" 아래에 있다

# services/indexing_service.py — 색인이 찾는 것
cas = ref.extra.get("cas_number")           # 최상위. 항상 None
```

`_resolve_substances()` 는 **처음부터 아무것도 찾을 수 없었다.** 쓰기 경로가 없었던
것(BR-33)에 더해, 있는 읽기 경로마저 맞물리지 않았다.

**따라서 투영은 `raw.payload` 에서 읽는다.** 신규 수집(`fetch` 가 row 를 payload 로
반환)과 재색인(보존 원본을 로드) 양쪽에서 같은 자리다.

### 실제 섹션 코드

`substance_identity` · `substance_symptom` · `substance_inhale` · `substance_skin` ·
**`substance_eye`** · `substance_oral` · `substance_etc`
*(FD 초안의 `substance_eyeball` 은 실제 코드가 아니다 — `substance_eye` 다)*

### 물질 문서의 `doc_type` 은 `msds` 다

```
ncis_substance → msds  40건       msds_pdf → msds  8건
```
**소스 ID 로 분기하지 않는다.** BR-33 이 요구하는 식별 필드가 payload 에 있으면
투영하고, 없으면 하지 않는다 — 소스 목록이 늘어도 코드가 안 바뀐다.

---

## 실행 계획

### 1. 결함 40 해소 (선행)
- [ ] 1.1 `app/core/types.py` — Enum 4종 (`MatchKind`·`CardItemKey`·`ValueOrigin`·`ExposureRoute`)
- [ ] 1.2 `app/substances/projection.py` — payload → 물질 필드 (BR-97·99)
- [ ] 1.3 `IndexingService` — 투영 호출 + `_resolve_substances` 를 payload 기준으로 정정
- [ ] 1.4 단위 테스트 — BR-33 미달 시 미저장, 재색인 멱등(BR-98), 이명 미생성(BR-99)

### 2. 조회·조립
- [ ] 2.1 `app/substances/types.py` — V1~V3
- [ ] 2.2 `app/substances/lookup.py` — C49 (BR-100·101, BR-109·110)
- [ ] 2.3 `app/substances/card.py` — C50 (BR-102~108)
- [ ] 2.4 `app/services/substance_service.py` — S4
- [ ] 2.5 단위 테스트

### 3. 웹
- [ ] 3.1 `app/web/routers/substances.py` — `/api/substances`, `/substances`
- [ ] 3.2 `templates/substances.html` · `substance_card.html`
- [ ] 3.3 네비게이션에 `물질` 탭

### 4. 검증
- [ ] 4.1 재색인 1회 → 마스터 채움 (BR-98)
- [ ] 4.2 통합 테스트 (실 DB)
- [ ] 4.3 NFR-3 실측

### 5. 문서
- [ ] 5.1 `construction/u3-substance-card/code/` 3종
- [ ] 5.2 README 갱신

---

## 코드 배치

```
app/substances/          ← u3 신규. 책임 경계이지 유닛 경계가 아니다 (UD-4)
  types.py  projection.py  lookup.py  card.py
app/services/substance_service.py
app/web/routers/substances.py
```

## DoD (UD-7)
- [ ] 코드 + 단위 + 통합 테스트
- [ ] Docker 기동 실측
- [ ] **실조회 종단** — u2 에서 배운 것: "기동"만으로는 그 경로가 돈 적이 없을 수 있다
- [ ] README 갱신
