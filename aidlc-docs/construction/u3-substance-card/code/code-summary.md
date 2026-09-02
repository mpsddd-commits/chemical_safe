# Code Summary — u3-substance-card

**유닛**: `u3-substance-card` (3/5)
**작성일**: 2026-08-26
**테스트**: 단위 **449 통과 + 1 스킵** / 통합 **22 통과 + 1 스킵**, ruff clean

---

## 1. 산출물

### 신규 (8)

| 경로 | 책임 |
|---|---|
| `app/substances/projection.py` | **결함 40 해소** — BR-97~99 |
| `app/substances/types.py` | 값객체 V1~V3, 항목 라벨 |
| `app/substances/lookup.py` | C49 조회 — BR-100·101·109·110 |
| `app/substances/card.py` | C50 카드 조립 — BR-102~108 |
| `app/services/substance_service.py` | S4. **LLM 없음** |
| `app/web/routers/substances.py` | P7·P7-1 + JSON API |
| `templates/substances.html` · `substance_card.html` | 화면 |

### 수정 (5)

| 경로 | 변경 |
|---|---|
| `app/core/types.py` | Enum 4종 |
| `app/db/repositories/catalog.py` | `replace_synonyms()` 신설 |
| `app/services/indexing_service.py` | 투영 호출 + payload 기준 정정 ×2 |
| `app/main.py` · `base.html` | 라우터 등록, `물질` 탭 |

**마이그레이션 없음.** 세 표가 u1 에 이미 있었다 — DD-21·UD-6 선반영 회수.

---

## 2. 결함 40 은 세 얼굴이었다

FD 를 쓸 때는 "쓰기 경로가 없다" 하나로 보였다. 실제로는 셋이었다.

| # | 얼굴 | 증상 |
|---|---|---|
| ① | `SubstanceRepo.upsert()` 호출부 0 | `substance` 0행 |
| ② | `_resolve_substances` 가 `ref.extra["cas_number"]` 를 봄 | 어댑터는 `extra["row"]` 에 넣는다 → `document_substance` 0행 |
| ③ | `base_meta.cas_number` 도 같은 자리를 봄 | `chunk.meta.cas_number` 0건 → **BR-38 완전일치가 매칭할 대상 없음** |

②③ 은 **읽기 경로**다. 쓰기를 붙였어도 ②③ 을 고치지 않았으면 마스터만 채워지고
연결과 색인 메타는 여전히 비어 있었을 것이다.

셋 다 `raw.payload` 기준으로 정정했다 — 신규 수집과 재색인(보존 원본, BR-44) 양쪽에서
같은 자리다.

### 실측
```
                    수정 전    수정 후
substance                0        40
substance_synonym        0        80   (ko 40 + en 40, alias 0 — BR-99)
document_substance       0        40
chunk.meta.cas_number    0       273
chunk.meta.substance_ids 0       273
```

---

## 3. 실행이 드러낸 것 3건

### 3.1 물질명에 출처의 목록 표시자가 붙어 있었다
`·아이소프로필아민` · `·Isopropylamine` — 40건 전부. 화학물질명의 일부가 아니라
출처가 목록 항목으로 렌더한 것이다.

**BR-99(이명 생성 금지)와 구분해서 적었다**: 불릿을 떼는 것은 이름을 만드는 것이
아니다. 다만 **앞머리의 불릿만** 제거하며 이름 안쪽은 건드리지 않는다 —
`3,3-Dimethyl-2-butanone` 은 그대로 남아야 한다.

처음에 `-`·`—`·`*` 까지 넣었다가 되돌렸다. **화학물질명의 일부일 수 있고 실제
데이터에서 관측되지 않았다.** 관측된 것만 남기는 것이 데이터를 고치지 않는 것이다.

### 3.2 BR-98 멱등성이 동의어에 적용되지 않았다
이름 정리 후 재색인하니 동의어가 **80이 아니라 160**이었다. `add_synonyms` 는 완전
중복만 건너뛰므로 `·Isopropylamine` 이 `Isopropylamine` 옆에 살아남아 **아무도
검색해서는 안 될 철자가 유효한 조회 키로** 남았다.

→ `replace_synonyms()`. BR-54 가 청크를 전량 교체하는 것과 같은 이유다 —
파생 데이터는 누적이 아니라 교체다.

### 3.3 `delete-orphan` 에서는 컬렉션을 비워야 한다 (자초)
`replace_synonyms` 를 자식마다 `session.delete()` 로 썼더니 **80이 아니라 0**이 됐다.
관계가 `delete-orphan` 을 갖고 있어 컬렉션 자체를 `.clear()` 해야 하고, 개별 삭제는
객체를 컬렉션에 남겨 뒤이은 append 까지 함께 지운다.

**모킹된 저장소로는 볼 수 없다** — 가짜 저장소는 호출을 기록할 뿐이다.
통합 테스트가 잡았다.

---

## 4. 설계 판단

### 4.1 투영이 색인 안에 있다 (BR-97)
결함 40 이 **분리된 쓰기 경로의 모양**이었다. 별도 백필 명령을 두면 "색인은 했는데
백필은 안 돌렸다"가 다시 가능해진다.

### 4.2 소스 ID 로 분기하지 않는다
물질 레코드와 MSDS PDF 가 둘 다 `doc_type=msds` 로 들어온다. BR-33 이 요구하는 식별
필드가 payload 에 있는지로 판별하므로, 소스가 늘어도 코드가 안 바뀐다.

### 4.3 이름 검색이 부분일치인 이유
"황산"이 황산구리를 후보로 띄워야 사용자가 자기가 고른 게 맞는지 안다. 완전일치면
**다른 화학물질을 조용히 답한다** — 그것이 R-6 다(BR-101).

### 4.4 결측이 데이터에 실려 다닌다
`missing_count` 를 `SubstanceCard` 속성으로 뒀다. 템플릿이 계산하면 빠뜨릴 수 있다 —
u2 의 `unpriced_calls`(BR-96)·`removed`(BR-88)와 같은 장치다.
`unsupported_keys` 도 같은 이유로 API 응답에 싣는다(BR-109·110).

### 4.5 구조화 GHS 컬럼을 비워 둔다 (BR-108)
채우려면 MSDS 2번 섹션을 파싱해 코드로 뽑아야 하고, 어긋나면 **잘못된 GHS 분류가
구조화된 사실로** 저장된다. 본문 인용이면 틀려도 원문에서 확인할 수 있다.

---

## 5. 테스트

| 파일 | 케이스 | 대상 |
|---|---:|---|
| `test_substance_projection.py` | 24 | BR-33·97·98·99, 목록 표시자, 구조화 컬럼 |
| `test_substance_card.py` (통합) | 16 | 마스터 채움, 동의어 멱등, 7항목, 조회 |
| **u3 소계** | **40** | |

---

## 6. 실측

```
검색 (이름)  →  1건, matched_on=name_ko
검색 (CAS)   →  1건, matched_on=cas
검색 (UN)    →  0건 + unsupported_keys=['un','alias']   ← BR-109·110
카드         →  has_msds=false, missing_count=6/7, 응급조치 4건(노출경로)

HTML: card-item 7개, missing-notice 1개, item-value 4개
NFR-3: 6.7 ~ 27 ms   (예산 1,000 ms)   ✅
불변식: 70문서 / 1,598청크 / 1,598벡터 / 상한 초과 0 / BR-30 위반 0
```

---

## 7. 알려진 것

| 항목 | 내용 |
|---|---|
| **대부분의 카드가 6/7 결측** | 물질 40건 중 MSDS 를 가진 것이 ~7건. **FR-25 가 예상한 상황**이며 화면이 고지한다 |
| **UN·이명 미충족** | FR-26 의 5종 중 2종. 데이터가 없다. `MatchKind` 에 남겨 두어 미충족이 보이게 했다 |
| **응급조치 본문에 `inhale:` 접두** | 추출 단계가 payload 를 "key: value" 로 렌더한 결과다. 경로 배지와 중복되지만 **텍스트를 편집하지 않는다**(BR-104) — 편집하면 카드 본문이 색인된 청크와 달라진다 |
| **GHS 등 구조화 컬럼 NULL** | BR-108. 신뢰할 수 있는 출처가 생기면 채울 자리 |
