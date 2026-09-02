# Domain Entities — u3-substance-card

**유닛**: `u3-substance-card` (3/5)
**작성일**: 2026-08-26
**근거 답변**: FQ4-1~14 (권장안, FQ4-4 = b)

---

## 0. 새 테이블이 없다

u3 은 **영속 엔터티를 하나도 추가하지 않는다.** 필요한 세 표가 u1 에 이미 있다.

| 표 | 상태 | u3 에서의 역할 |
|---|---|---|
| `substance` (E2) | 스키마 존재, **0행** | 카드의 뼈대. 결함 40 으로 채워진다 |
| `substance_synonym` (E3) | 스키마 존재, **0행** | 이름 조회 (BR-65 와 공유) |
| `document_substance` (E10) | 스키마 존재, **0행** | 물질 → 근거 문서 |
| `document` · `document_section` · `chunk` | 채워짐 | 카드 항목의 본문과 출처 |

**마이그레이션 리비전이 없다.** u1 이 선반영한 것(DD-21, UD-6)이 여기서 회수된다 —
`unit-of-work.md` §u3 의 "재수집이 발생하지 않습니다"가 정확히 이 뜻이었다.

> 다만 그 문장은 **"이미 채워져 있다"가 아니라 "채울 재료가 남아 있다"**를 뜻했다.
> 쓰기 경로가 없었다는 사실이 u2 Build & Test 에서야 드러났다(결함 40).

---

## 1. 결함 40 이 채우는 것

### `substance` (E2) — 물질 API 원본에서 투영

| 컬럼 | 원본 필드 | 실측 보유 |
|---|---|---|
| `cas_number` | `cas_number` | **40/40** |
| `name_ko` | `name_ko` | **40/40** |
| `name_en` | `name_en` | **40/40** |
| `un_number` | — | **없음.** 항상 NULL (FQ4-11) |
| `ghs_classification` · `signal_word` · `h_codes` · `p_codes` | — | **없음.** 항상 NULL |
| `physical_properties` | — | **없음.** 항상 NULL |
| `is_regulated` | — | 기본 false |

BR-33 은 `cas_number` · `name_ko` · `name_en` 중 최소 1개를 요구하고, 40건 전부가
셋 다 갖고 있다. **투영은 무조건 성공한다.**

> **NULL 컬럼을 채우지 않는 것이 설계다.** GHS·H/P 문구는 물질 API 에 없고 MSDS
> 본문에만 있다. 구조화 컬럼에 넣으려면 MSDS 2번 섹션을 파싱해 코드로 뽑아야 하는데,
> 그것은 파싱 실패 시 **잘못된 GHS 분류를 구조화 사실처럼** 저장하게 된다.
> 카드는 그 항목을 **본문 인용으로** 보여준다(§2 V2).

### `substance_synonym` (E3) — 두 개뿐

`term_type` 별 등록:

| `term_type` | 값 | 출처 |
|---|---|---|
| `name_ko` | 국문명 | 원본 |
| `name_en` | 영문명 | 원본 |

**이명(異名)은 등록하지 않는다** (FQ4-3=A). 원본에 없고, 규칙으로 만들어낸 변형은
이명이 아니라 우리가 만든 문자열이다. `term_type` 이 그 둘을 구분하지 못하면
**카드가 근거 없는 이름을 사실처럼 보여준다**(NFR-8).

### `document_substance` (E10) — BR-37

`relation` 은 문서 유형이 정한다: `msds` → `subject` / `incident` → `mentioned` /
`law` → `regulated`.

---

## 2. 값 객체 (비영속)

### V1. `SubstanceRef` — 조회 결과 후보

```
substance_id: int
cas_number:   str | None
name_ko:      str | None
name_en:      str | None
matched_on:   MatchKind        # 무엇으로 걸렸는지
```

`matched_on` 이 있는 이유: 이름 검색이 여러 물질에 걸릴 때(FQ4-6) 사용자가 고르려면
**왜 이것이 후보인지**를 알아야 한다. "황산"으로 검색해 "황산구리"가 나왔다면
그 사실이 보여야 한다.

### V2. `CardItem` — 카드의 한 항목

```
key:      CardItemKey
label:    str                  # 화면 표시명
values:   list[ItemValue]      # 비어 있을 수 있다
```

**`values` 가 비어 있는 것이 정상 상태다.** 40건 중 대부분은 MSDS 가 없어 항목
대부분이 빈다. 화면은 그것을 "정보 없음"으로 **표시**하며 감추지 않는다(FQ4-8=A).

```
ItemValue:
  text:          str           # 본문 그대로. 요약하지 않는다
  document_id:   int
  document_title:str | None
  section_code:  str | None    # NULL 가능 — BR-20a·BR-31a
  section_title: str | None
  source_url:    str
  origin:        ValueOrigin   # msds | substance_api | law
```

**여러 출처를 전부 싣는다**(FQ4-4=B). 안전 정보에서 "다른 문서는 뭐라고 하는가"는
정보다. 값이 서로 다르면 그 불일치 자체가 사용자가 알아야 할 사실이다.

> **`citation_snapshot`(E17)을 쓰지 않는다**(FQ4-5=A). 스냅샷은 답변이 인용한 시점을
> 동결하는 장치다(BR-92). 카드는 답변이 아니라 **현재 상태 조회**이므로 항상 최신을
> 보여주는 것이 맞다. 동결하면 **낡은 안전 정보를 보여주게 된다.**

### V3. `SubstanceCard`

```
substance:      SubstanceRef
items:          list[CardItem]      # 항상 7개. 순서 고정
missing_count:  int                 # values 가 빈 항목 수
has_msds:       bool
```

`missing_count` 와 `has_msds` 가 값 객체에 있는 이유는 화면이 그것을 **계산해서
숨길 수 없게** 하기 위해서다 — u2 의 `unpriced_calls`(BR-96)·`removed`(BR-88)와
같은 장치다.

---

## 3. Enum

### `MatchKind` — 무엇으로 찾았는가

| 값 | 의미 |
|---|---|
| `cas` | CAS 완전일치 |
| `un` | UN 완전일치 — **현재 데이터 없음**, 항상 0건 (FQ4-11) |
| `name_ko` | 국문명 |
| `name_en` | 영문명 |
| `alias` | 이명 — **현재 데이터 없음**, 항상 0건 (FQ4-3) |

> `un` 과 `alias` 를 **열거에서 지우지 않는다.** FR-26 이 5종을 요구하고, 둘은
> 미충족이다. 열거에서 빼면 미충족이 요구사항에서 사라진 것처럼 보인다.
> 값이 들어오면 코드 변경 없이 동작한다.

### `CardItemKey` — FR-24 의 7항목. 순서 고정

| 값 | 라벨 | 주 출처 | 실측 커버리지 |
|---|---|---|---|
| `ghs` | GHS 분류 및 신호어 | MSDS 2 | ~7 물질 |
| `hp_codes` | H·P 문구 | MSDS 2 | ~7 |
| `physical` | 물리화학적 성질 | MSDS 9 | ~7 |
| `ppe` | 권장 개인보호구 | MSDS 8 | ~7 |
| `first_aid` | 응급조치 요령 | MSDS 4 **+ 물질 API 4필드** | ~7 + **40** |
| `storage` | 저장·취급 주의사항 | MSDS 7 | ~7 |
| `regulations` | 적용 법령 | MSDS 15 + `law` | ~7 |

**순서가 고정인 이유**: 같은 물질을 두 번 조회했을 때 항목 순서가 달라지면 사용자가
"뭔가 바뀌었나"를 의심한다. 그리고 빈 항목이 빠지면서 순서가 흔들리면 결측이
눈에 띄지 않는다.

### `ValueOrigin`

| 값 | 의미 |
|---|---|
| `msds` | MSDS 문서 섹션 |
| `substance_api` | 물질 API 원본 필드 (노출경로 4종) |
| `law` | 법령 조문 |

### `ExposureRoute` — 응급조치 하위 구분 (FQ4-7=A)

| 값 | 원본 필드 | 보유 |
|---|---|---|
| `inhale` | `inhale` | 40/40 |
| `skin` | `skin` | 40/40 |
| `eyeball` | `eyeball` | 40/40 |
| `oral` | `oral` | **39/40** |

**40건 전부가 갖고 있는 유일한 실질 데이터**다. 하나로 합치지 않고 경로별로
남기는 이유는, 사고 상황에서 필요한 것이 "어디로 노출됐는가"에 달려 있기 때문이다.

---

## 4. u1·u2 규칙과의 관계

| 규칙 | u3 에서의 의미 |
|---|---|
| **BR-33** 물질 저장 조건 | **결함 40 으로 처음 구현된다.** 40건 전부 충족 |
| **BR-37** 문서↔물질 연결 | 동상. `get_by_cas` 가 이제 값을 찾는다 |
| **BR-38** CAS·UN·물질명 완전일치 | 마스터가 채워지면 **비로소 매칭 대상이 생긴다** |
| **BR-65** 동의어 해석 (u2) | 같은 표를 쓴다. u2 의 엔티티 추출이 함께 살아난다 |
| **BR-89~91** 출처 표기 (u2) | 표기 규약만 재사용. `citation_snapshot` 은 쓰지 않는다 |
| **BR-90** 라벨 없으면 "섹션 정보 없음" | 카드 항목 출처에도 그대로 적용 |
| **BR-44** 원본 보존 | 투영의 재료. 재수집이 없는 이유 |

---

## 5. 추적성

| FR | 엔터티 |
|---|---|
| FR-23 카드 반환 | V3 `SubstanceCard` |
| FR-24 7개 항목 | `CardItemKey`, V2 `CardItem` |
| FR-25 항목별 출처 · 결측은 "정보 없음" | `ItemValue`, `missing_count` |
| FR-26 동의어 검색 | `MatchKind`, `substance_synonym` |
| FR-45 카드 화면 | `frontend-components.md` P7 |
