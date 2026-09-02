# API Endpoints — u3-substance-card

**작성일**: 2026-08-26

> ⚠️ **인증 없음.** u5 까지 `127.0.0.1` 바인딩(NFR-18)이 유일한 통제다.

---

## 1. 경로

| 메서드 | 경로 | 용도 |
|---|---|---|
| `GET` | `/api/substances?q=…` | 검색 — 후보 0..N |
| `GET` | `/api/substances/{id}` | 안전 카드 |
| `GET` | `/substances` | **P7 검색 화면** |
| `GET` | `/substances/{id}` | **P7-1 카드 화면** |

**SSE 가 아니라 평범한 JSON 이다**(FQ4-14). 스트리밍할 것이 없고, LLM 이 경로에
없어 한 번에 끝난다 — 실측 6.7~27ms (NFR-3 예산 1,000ms).

---

## 2. `GET /api/substances`

```json
{
  "query": "아이소프로필아민",
  "matches": [
    {"substance_id": 1, "cas_number": "75-31-0",
     "name_ko": "아이소프로필아민", "name_en": "Isopropylamine",
     "matched_on": "name_ko"}
  ],
  "unsupported_keys": ["un", "alias"]
}
```

### `matched_on` 이 있는 이유
이름 검색은 여러 물질에 걸릴 수 있고, **시스템은 고르지 않는다**(BR-101).
사용자가 고르려면 왜 이것이 후보인지 알아야 한다. "황산"으로 검색해 황산구리가
나왔다면 그 사실이 보여야 한다 — 잘못된 물질의 카드를 읽는 사용자는 그것을 알
방법이 없고, 이 도메인에서 그것은 R-6 다.

| `matched_on` | 상태 |
|---|---|
| `cas` | 동작 |
| `name_ko` · `name_en` | 동작 |
| `un` | **데이터 없음** — 항상 0건 (BR-109) |
| `alias` | **데이터 없음** — 출처에 이명이 없다 (BR-99) |

### `unsupported_keys` 가 모든 응답에 있는 이유
FR-26 은 5종을 요구하고 2종은 데이터가 없다. 이 목록이 응답에 실려 있어야
**클라이언트가 그 사실을 조용히 빠뜨릴 수 없다**(BR-110). u2 의 `unpriced_calls`
(BR-96)와 같은 장치다.

> UN 번호로 검색하면 0건이 온다. 이것은 "지원하지 않음"이 아니라 **"데이터 없음"**
> 이며, 경로를 지우면 미충족 요구사항이 요구된 적 없는 것처럼 보인다.

---

## 3. `GET /api/substances/{id}`

```json
{
  "substance": {"substance_id": 1, "cas_number": "75-31-0",
                "name_ko": "아이소프로필아민", "name_en": "Isopropylamine"},
  "has_msds": false,
  "missing_count": 6,
  "items": [
    {"key": "ghs", "label": "GHS 분류 및 신호어", "values": []},
    {"key": "hp_codes", "label": "H·P 문구", "values": []},
    {"key": "physical", "label": "물리화학적 성질", "values": []},
    {"key": "ppe", "label": "권장 개인보호구", "values": []},
    {"key": "first_aid", "label": "응급조치 요령", "values": [
      {"text": "inhale: 액체 미스트의 다량 흡입은 …",
       "document_id": 39, "document_title": null,
       "section_code": "substance_inhale", "section_title": "흡입",
       "source_url": "https://www.data.go.kr/…",
       "origin": "substance_api", "route": "inhale"}
    ]},
    {"key": "storage", "label": "저장·취급 주의사항", "values": []},
    {"key": "regulations", "label": "적용 법령", "values": []}
  ]
}
```

### `items` 는 **항상 7개, 항상 같은 순서**다 (BR-102)

실측상 물질 40건 중 MSDS 를 가진 것은 약 7건이다. 나머지는 7항목 중 6개가 빈다.

**`"values": []` 는 오류가 아니라 정상 상태다.** 빈 항목을 응답에서 빼면 카드가
완전해 보이고, 소비자는 "이 물질은 보호구 정보가 없다"와 "이 API 가 보호구 항목을
안 준다"를 구분할 수 없다.

### `missing_count` 와 `has_msds`

계산해서 숨길 수 없도록 응답에 실려 있다(BR-106). u2 의 `removed`(BR-88)와 같다.
`has_msds=false` 는 화면이 **왜** 비었는지 말할 수 있게 한다 —
"이 물질은 MSDS 문서가 없어 6개 항목이 비어 있습니다".

### `values` 가 여럿일 때

**전부 나열한다**(BR-103). 두 MSDS 가 다른 보호구를 지시하면 **그 불일치 자체가
사용자가 알아야 할 사실**이고, 하나를 골라 감추면 그 사실이 사라진다.

### `route` — 응급조치에만

물질 API 의 노출경로 4종(`inhale`·`skin`·`eye`·`oral`). **40건 전부가 갖고 있는
유일한 폭넓은 데이터**다. 하나로 합치지 않는 이유는 사고 상황에서 필요한 것이
"어디로 노출됐는가"에 달려 있기 때문이다.

### `citation_snapshot` 을 쓰지 않는다 (BR-107)

u2 의 인용은 **답변이 인용한 시점을 동결**한다(BR-92). 카드는 답변이 아니라
**현재 상태 조회**이므로 항상 최신을 보여준다 — 동결하면 원본이 개정돼도
낡은 안전 정보를 계속 보여주게 된다.

### 404
존재하지 않는 `id` 만 404 다. **결측 항목은 404 가 아니다.**

---

## 4. 화면

| 경로 | 화면 | JS 필요 |
|---|---|---|
| `GET /substances` | P7 검색 | ❌ 폼 GET |
| `GET /substances/{id}` | P7-1 카드 | ❌ 서버 렌더링 |

u2 의 P5 와 달리 JavaScript 가 전혀 필요 없다 — 스트리밍이 없기 때문이다.

### 화면이 반드시 지키는 것
1. **7항목 전부 표시**, 빈 것은 "정보 없음" (BR-102·106)
2. **결측 개수 고지** — `missing_count > 0` 일 때만
3. **UN·이명 미지원 상시 표시** — 조용히 0건을 주면 사용자는 자기 입력을 의심한다
4. **면책 문구는 접히지 않는다** (FR-35)
5. **후보가 2건 이상이면 목록**, 시스템이 고르지 않는다 (BR-101)
