# 검토 — `doc_type` 세분화 (물질 API 레코드를 MSDS 와 분리)

**일자**: 2026-08-30
**발단**: MSDS 4건 추가 수집 후 sub-07 의 정답 근거가 밀렸다 (Recall@5 0.700 → 0.667)
**상태**: **검토 완료 → 2026-08-30 실행 완료.** 결과는 8절

---

## 1. 문제

`ncis_substance` 물질 레코드와 `msds_pdf` MSDS 문서가 **둘 다 `doc_type=msds`** 다.

sub-07("CAS 7782-50-5 흡입 시")의 융합 결과 20건을 전부 뽑아 봤다.

```
   0 msds  msds_pdf        msds_03             염소 - 한화솔루션
   1 msds  msds_pdf        msds_04             염소 - 한화솔루션
   2 msds  msds_pdf        msds_02             염소 - 한화솔루션
   3 msds  msds_pdf        msds_11             염소 - 한화솔루션
   4 msds  msds_pdf        msds_08             염소 - 한화솔루션   │ 절단선(final_top_k=5)
   5 msds  msds_pdf        msds_08             염소 - 한화솔루션
   6 msds  msds_pdf        msds_11             염소 - 한화솔루션
   7 msds  ncis_substance  substance_inhale    (물질 API)   ← 골든셋의 정답 근거
   8 msds  ncis_substance  substance_symptom   (물질 API)
   …
  20건 전부 doc_type=msds
```

**정답 근거는 후보에 있다.** 융합 20건 안의 7위다. 잘린 것뿐이다.

BR-69 `ensure_doc_type_spread` 는 상위 5건에 없는 **타입**을 아래에서 하나 끌어올린다.
그런데 20건이 전부 같은 타입이라 `missing` 이 비고, **끌어올릴 것이 없다.**

> BR-69 의 원문 근거는 "법령이 청크의 69%라 법률 어투 질문이 모든 슬롯을 법령으로
> 채운다"였다. 지금은 **한 문서가 모든 슬롯을 채운다** — 같은 실패이고 축만 다르다.

---

## 2. 이 혼동은 이미 두 곳에서 우회되고 있다

세분화는 새 아이디어가 아니라 **이미 지불 중인 비용을 드러내는 일**이다.

```python
# processing/stages/structure.py — MSDS 구조화기가 실패하면 물질 구조화기로 흘린다
if doc_type is DocType.MSDS or doc_type is DocType.USER_UPLOAD:
    sections, status = msds_structure.find_sections(text, settings.msds_min_sections)
    if status is StructureStatus.UNSTRUCTURED:
        # "not every msds-typed document is a 16-section document"
        sections, status = substance_structure.find_sections(text)
```

```python
# substances/card.py::_has_msds
"""A real MSDS document, not a substance record.

Both arrive as `doc_type=msds`; the section codes are what separate them …
"""
```

**코드가 이미 "둘은 다른 것"이라고 적어 놓고 섹션 코드로 구분하고 있다.**

---

## 3. 효과 — DB 를 바꾸지 않고 측정했다

물질 레코드 청크의 `doc_type` 만 메모리에서 다른 값으로 바꿔 `ensure_doc_type_spread`
를 다시 돌리고, 골든셋 30문항의 지표를 재계산했다. **코퍼스는 손대지 않았다.**

```
현재      Recall@5 0.667   MRR 0.525
세분화 후  Recall@5 0.700   MRR 0.532
변화 문항 1건
  sub-07   Recall 0.000 → 1.000    MRR 0.000 → 0.200
```

| | 값 |
|---|---|
| **Recall@5 가 MSDS 추가 이전 값(0.700)으로 정확히 회복된다** | ✅ |
| MRR 은 0.525 → 0.532 (기준선 0.546 에는 못 미친다) | sub-07 이 1위가 아니라 5위로 들어오기 때문 |
| **부작용 문항 0건** | 나머지 29문항은 소수점까지 동일 |

**한 문항만 움직이고, 그 방향이 옳다.**

---

## 4. 무엇을 바꿔야 하는가

### 코드 5곳
| 파일 | 변경 |
|---|---|
| `core/types.py` | `DocType.SUBSTANCE = "substance"` 추가 |
| `config/sources.yaml` | `ncis_substance` 의 `doc_type: msds` → `substance` |
| `processing/stages/structure.py` | `SUBSTANCE` → 물질 구조화기로 직접. MSDS 폴백은 `USER_UPLOAD` 용으로 남긴다 |
| `services/indexing_service.py` | `_RELATION_BY_DOC_TYPE[SUBSTANCE] = SUBJECT` |
| `substances/card.py` | `_has_msds` 의 docstring 갱신 (로직은 섹션 코드 기반이라 그대로 동작) |

### 데이터
```
document  49행   doc_type msds → substance
chunk    324행   meta.doc_type 갱신 → 해당 49문서만 부분 재색인 (약 8분)
```
전 코퍼스 재색인(35분)은 필요 없다. `document.doc_type` 을 먼저 갱신하고
그 49건만 `reindex_document` 한다 — `reindex_document` 가 **행의 `doc_type` 을
읽기 때문에** 순서가 그 반대면 아무것도 바뀌지 않는다.

### 바뀌지 않는 것 (확인함)
| 항목 | 이유 |
|---|---|
| `documents.substance_mentions()` | 물질 소스를 이미 제외한다(BR-08). MSDS 제목만 본다 |
| `card.py` 항목 매핑 | `_MSDS_SECTION_FOR`·`_ROUTE_SECTION` 은 **섹션 코드** 기반 |
| u4 골든셋 | 정답 근거가 `source`+`external_id` 다 (BR-112). `doc_type` 을 쓰지 않는다 |
| u5 격리 | `Scope` 는 `owner_id` 만 본다 |
| `apply_meta_filter` | `doc_types` 필터는 호출부가 비워 두고 있다 |

---

## 5. 위험 3건

### ① `doc_type_hint` 는 **아무 데도 쓰이지 않는다**
```
grep -rn doc_type_hint app/ → entities.py 에서 만들고, types.py 에 담고, 끝.
검색·융합·필터 어디에서도 읽지 않는다.
```
그래서 지금 세분화해도 **잃을 가중치가 없다.** 다만 나중에 누가 힌트를 실제
가중치로 구현하면 "응급조치" 같은 질문이 `msds` 로 힌트되어 **물질 레코드가 그
가중치에서 빠진다.** 그때는 힌트를 타입 집합으로 바꿔야 한다 — 지금 적어 둔다.

### ② `entities.py` 의 힌트 enum
`["law", "msds", "incident", None]` 에 `substance` 를 넣을지. 힌트가 쓰이지 않으므로
기능 차이는 없다. **넣지 않는 쪽을 권한다** — 쓰이지 않는 값을 늘리면 나중에 힌트를
구현하는 사람이 이미 동작하는 것처럼 오해한다.

### ③ 재색인 순서
`document.doc_type` UPDATE → 부분 재색인. 반대로 하면 조용히 아무 일도 일어나지
않는다. 실행 절차에 못박아야 한다.

---

## 6. 권고

**실행에 찬성한다.** 근거 셋:

1. **측정됐다.** Recall@5 가 정확히 회복되고 부작용 문항이 0이다. 추측이 아니다.
2. **이미 지불 중인 비용이다.** `structure()` 의 폴백과 `_has_msds` 의 섹션 코드
   판별이 둘 다 이 혼동을 우회하려고 존재한다. 세분화하면 둘 다 정직해진다.
3. **비용이 작고 경계가 뚜렷하다.** 코드 5곳, 데이터 49문서, 부분 재색인 8분.
   u1~u5 의 규칙 중 어느 것도 바뀌지 않는다.

**다만 지금 바로 하지 않는 선택도 방어 가능하다**: MSDS 를 더 넣으면 같은 문제가
다른 물질에서 또 나올 것이고, 그때 한 번에 하는 편이 재색인 횟수를 줄인다.

### 실행하면 이어서 필요한 것
- 부분 재색인 후 `evaluate --retrieval-only` 로 **0.700 회복을 실측 확인**
- 코퍼스가 바뀌었으므로 **기준선 재승격은 사람이** (BR-129)
- BR 번호 부여: 이 규칙은 u1 의 BR-69(타입 분산)에 붙는 정정이다

---

## 7. 부수 발견 — `doc_type_hint` 사문화

BR-66 은 "`doc_type_hint` 는 가중치이지 필터가 아니다"라고 정했고, 코드는 힌트를
**만들기만 하고 쓰지 않는다.** 규칙 위반은 아니다(필터로 쓰이지 않는다는 조건은
만족한다) — 그러나 **u2 가 만든 값이 4개 유닛을 지나도록 소비자가 없다.**

결함으로 올리지 않는다: 동작에 영향이 없고, 힌트를 실제로 쓰는 것이 좋은지도
측정된 바 없다. **`operations.md` 10절에 항목으로 남긴다.**

---

## 8. 실행 결과 (2026-08-30)

**승인 발언**: "실행하고 MSDS 추가시에도 변환 가능하게 바꿔 주세요.
재색인 횟수를 늘리더라도 그게 낫습니다"

### 일회성 SQL 이 아니라 명령으로 만들었다
```bash
safeenv retype            # 무엇이 바뀔지만 보여준다
safeenv retype --apply    # document.doc_type 갱신 → 해당 문서만 재색인
```
`config/sources.yaml` 이 권위이고 명령이 행을 거기에 맞춘다. **수집 경로는 이미
매번 선언된 타입을 쓰므로 새 문서는 항상 옳다** — 어긋나는 것은 스펙이 바뀌기 전에
수집된 행뿐이다. 다음에 타입이 또 갈릴 때 마이그레이션을 새로 쓰지 않아도 된다.

순서는 코드가 강제한다: **행 갱신 → 재색인**. `reindex_document` 가 행의
`doc_type` 을 읽으므로 반대로 하면 조용히 아무 일도 일어나지 않는다.

### 적용
```
불일치 49건 → 재색인 성공 49 / 실패 0   (약 4분)
재실행 → 불일치 0건 (멱등)

doc_type 분포   substance 49 · msds 12 · law 9 · incident 12
청크 메타       law 1,173 · substance 324 · msds 188 · incident 12
```

### 예측 대비 실측
| | 시뮬레이션 | 실측 |
|---|---|---|
| Recall@5 | 0.700 | **0.700** ✅ 정확히 일치 |
| MRR | 0.532 | 0.529 |
| 변화 문항 | 1건 (sub-07) | **2건** |

```
sub-07  Recall 0.000 → 1.000   목표 달성
law-02  MRR   0.333 → 0.250   Recall 은 1.000 그대로
```
**시뮬레이션이 law-02 를 놓쳤다.** 재색인으로 청크가 다시 만들어지면서 융합 순위가
미세하게 달라졌고, 물질 후보가 하나 올라오며 법령 청크를 한 칸 밀어냈다.
시뮬레이션은 방향은 맞았고 약간 낙관적이었다 — 그 차이를 적어 둔다.

MRR 이 기준선 0.546 에 못 미치는 것(0.529)은 sub-07 의 정답 근거가 1위가 아니라
5위로 들어오기 때문이다. 융합 점수로는 MSDS 가 더 위이고, 타입 분산이 마지막
자리를 하나 확보해 준 것이다.

### 바뀌지 않은 것 — 확인함
```
카드 결측 분포  {0:4, 1:2, 2:1, 6:41, 7:1}   세분화 전후 동일
단위 629 통과 + 1 스킵 (618 → +11)  ·  통합 53 통과 + 1 스킵  ·  ruff clean
```
카드가 그대로인 것은 `_MSDS_SECTION_FOR`·`_has_msds` 가 **섹션 코드**를 보기
때문이다 — 검토 4절에서 예상한 대로다.

### 남은 것
- ~~기준선 재승격~~ — **2026-08-30 승격 완료.** 검색전용 실행 **127** (Recall@5 0.700 ·
  MRR 0.529). 승격 직후 재실행이 전 지표 +0.000 으로 재현됐다.
  `full` 기준선(실행 10)은 코퍼스가 달라 비교 불가인 채로 남는다 — 대체 실행 없음
- `doc_type_hint` 는 여전히 소비자가 없다 (`operations.md` 10절 8번)

### 승격 검증에서 나온 결함 58 — 세분화가 실제로는 안 돌고 있었다
승격 뒤 확인 실행이 0.667 을 냈다. 로그가 `unknown_doc_type value="substance"` 를
수십 건 뱉고 있었고, 컨테이너의 `DocType` 에 `substance` 가 없었다 — **이미지는
재빌드됐고 컨테이너는 재생성되지 않았다.**

즉 이 문서 8절의 실측 중 일부는 **세분화가 꺼진 코드** 위에서 나왔을 수 있다.
컨테이너 재생성 후 다시 재면 실행 127 과 정확히 같은 0.700 / 0.529 가 나온다
(실행 141). 결론은 바뀌지 않지만, **어떤 코드가 그 수를 냈는지 확인하지 않았다는
사실**은 남는다. 자세한 것은 `audit.md` 의 결함 58.
