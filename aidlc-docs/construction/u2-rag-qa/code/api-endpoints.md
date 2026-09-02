# API Endpoints — u2-rag-qa

**작성일**: 2026-08-25
**기준**: 실행 중인 애플리케이션의 `/openapi.json` (2026-08-25 실측)

> ⚠️ **인증 없음.** u5 까지 `127.0.0.1` 바인딩(NFR-18)이 유일한 접근 통제이며,
> u1 Build & Test 에서 실측 확인되었다. 아래 모든 경로에 해당한다.

---

## 1. u2 신규 경로

| 메서드 | 경로 | 용도 |
|---|---|---|
| `POST` | `/api/query` | 질의 접수 — **SSE 스트림** |
| `GET` | `/api/query/{query_id}` | 확정된 답변·인용 조회 |
| `GET` | `/api/citations/{citation_id}/snippet` | 인용 스니펫 단건 |
| `GET` | `/api/usage` | 기간별 LLM 사용량 (FR-42) |
| `GET` | `/` | **P5 질의 화면** |
| `POST` | `/query` | P5 무JS 답변 경로 (HTML) |
| `GET` | `/usage` | **P6 사용량 화면** |

### u1 경로 변경 1건

| 이전 | 현재 | 사유 |
|---|---|---|
| `GET /` (대시보드) | **`GET /admin`** | 루트는 P5 가 갖는다 (FD 화면 목록) |

`/admin/sources`, `/admin/jobs`, `/api/jobs`, `/api/sources`, `/api/stats`,
`/healthz` 는 변경 없다.

---

## 2. `POST /api/query`

### 요청

```json
{ "question": "황산 취급 시 보호구는?" }
```

`question` 은 서버에서 검증한다(SP-9): 제어문자 제거, 공백 정리,
`QUERY_MAX_CHARS`(기본 2,000) 초과 시 **422**. 클라이언트 측 `maxlength` 는 편의일 뿐이다.

### 응답 — `text/event-stream`

```
event: retrieval
data: {"count": 5, "ms": 339}

event: token
data: {"sentence": 0, "text": "분진·미스트 발생 시 "}

event: verifying
data: {"sentences": 3}

event: final
data: {"outcome": "answered_partial", "query_id": 12,
       "sentences": [{"ordinal": 0, "text": "…", "chunk_ids": [4193]}],
       "citations": [{"sentence_ordinal": 0, "rank": 0, "chunk_id": 4193,
                      "title": "황산 MSDS — 남해화학", "section_code": "msds_08",
                      "snippet": "…", "source_url": "https://…"}],
       "removed": 1}
```

### 이벤트 계약

| 이벤트 | 시점 | 보장 |
|---|---|---|
| `retrieval` | 검색 완료 | 항상 1회 (오류 전이면) |
| `token` | 생성 중 | 0회 이상. **잠정 텍스트** |
| `verifying` | 2단 검증 시작 | 답변 경로에서만 |
| `final` | 확정 | `refused` 와 **배타** |
| `refused` | 거부 확정 | `final` 과 **배타** |
| `error` | 실패 | 종료 |

> **`final` 과 `refused` 중 하나는 반드시 전송된다.** 클라이언트는 **스트림이 끝났다는
> 것만으로 성공을 추정해서는 안 된다** — 연결이 끊긴 것과 답변이 완료된 것이 구분되지
> 않고, 여기서 그 차이는 "사용자가 검증되지 않은 답변을 믿는다"이다.

### ⚠️ `token` 은 잠정 텍스트다

`token` 으로 흘러나온 문장은 **아직 ID 화이트리스트(SP-8)를 통과하지 않았고 2단
검증(BR-85~87)도 받지 않았다.** 클라이언트는 이를 **인용 배지 없이** 표시해야 하며,
배지와 근거 카드는 `final` 에서만 렌더링한다(FE-16).

검증에서 제거될 문장에 배지를 먼저 붙이면, 사용자가 곧 철회될 인용을 읽고 신뢰한다.
`final` 수신 시 잠정 노드를 **버리고 다시 그린다** — 살아남은 것이 흘러나온 것과 다를
수 있고, 제자리에서 맞춰 나가는 것이 둘이 조용히 어긋나는 경로다.

### 거부 응답

```
event: refused
data: {"reason": "below_threshold",
       "links": [{"document_id": 20, "title": "황산 MSDS — 남해화학",
                  "section_code": "msds_08", "source_url": "https://…"}]}
```

`reason` 은 내부 코드다. 화면에는 사용자 언어로 옮겨 표시한다.

| `reason` | 의미 |
|---|---|
| `no_candidates` | 검색 결과 없음 |
| `below_threshold` | 최상위 **코사인 유사도**가 임계값 미달 (BR-73) |
| `all_sentences_unsupported` | 2단 검증 후 남은 문장 0 (BR-76) |
| `provider_refusal` | LLM 이 `stop_reason=refusal` 반환 (BR-77) |

**`links` 는 항상 포함된다**(BR-75). 문서 단위로 중복 제거한다 — 같은 법령의 청크
5개는 갈 곳 하나이고, 5번 나열하면 거부 화면이 검색 결과처럼 보인다.

**거부는 오류가 아니다**(BR-78). HTTP 200 이며 오류 지표에 넣지 않는다.

### 오류

```
event: error
data: {"kind": "configuration", "message": "ANTHROPIC_API_KEY is not set. …"}
```

| `kind` | 의미 |
|---|---|
| `configuration` | `ANTHROPIC_API_KEY` 미설정. **앱은 정상 기동 상태**(BR-02) |
| `transient` | 검색 양쪽 실패, LLM 오류 등 |

---

## 3. `GET /api/query/{query_id}`

확정된 답변을 다시 조회한다. **인용은 `citation_snapshot` 에서만 읽는다**(BR-92a).

```json
{
  "query_id": 12, "question": "…", "outcome": "answered_partial",
  "refusal_reason": null, "mode": "hybrid",
  "retrieval_ms": 339, "total_ms": 8420,
  "sentences": [
    {"ordinal": 0, "text": "…", "support": "supported", "removed": false},
    {"ordinal": 1, "text": "…", "support": "unverified", "removed": true}
  ],
  "citations": [
    {"sentence_ordinal": 0, "citation_id": 44, "rank": 0, "chunk_id": null,
     "title": "황산 MSDS", "label": "msds_08 노출방지 및 개인보호구",
     "snippet": "…", "source_url": "https://…", "stale": true}
  ]
}
```

### `chunk_id: null` / `stale: true` 는 오류가 아니다

재색인(BR-54)이 그 청크를 교체했다는 **사실**이다. 표시에 필요한 것은 전부 스냅샷에
NOT NULL 로 있으므로 인용은 완전하다. `stale` 은 "지금도 검색 가능한 청크인가"를
알려줄 뿐이다.

`removed: true` 인 문장도 반환한다(BR-88). 제외 건수만 표시하고 근거 행이 없으면
감사할 수 없다.

---

## 4. `GET /api/citations/{citation_id}/snippet`

인용 카드 지연 로드용. **인용 ID 로 키잉한다** — 청크 ID 가 아니다(BR-92a).

> 이전 설계는 `/api/chunks/{id}/snippet` 이었고 잘못이었다. 재색인은 청크 ID 를
> 재사용하므로 과거 인용이 **다른 문서의 본문**으로 해석될 수 있다.

---

## 5. `GET /api/usage`

| 파라미터 | 기본값 |
|---|---|
| `from` | 7일 전 |
| `to` | 지금 (지정 시 해당 일자 **종료 시각까지**) |
| `purpose` | 전체 (`answer` / `verify` / `entity`) |

```json
{
  "from": "2026-08-18T08:43:32Z", "to": "2026-08-25T08:43:32Z",
  "calls": 1284, "ok_calls": 1271, "failed_calls": 13,
  "input_tokens": 4820113, "output_tokens": 312004,
  "cache_read_tokens": 3110220, "cache_hit_ratio": 0.645,
  "latency_p50_ms": 1900, "latency_p95_ms": 6200,
  "cost_usd": "31.920000", "unpriced_calls": 6,
  "by_purpose": [{"purpose": "verify", "calls": 856, "cost_usd": "7.82", "unpriced": 0}],
  "by_model":   [{"model": "claude-opus-5", "calls": 1278, "cost_usd": "31.92", "unpriced": 0}]
}
```

### `cost_usd` 와 `unpriced_calls` 는 분리해서 읽지 않는다

`cost_usd` 는 단가가 등록된 호출만의 합계다. **`unpriced_calls > 0` 이면 합계는
전부가 아니다**(BR-96). 단가 미등록 호출의 비용은 `null` 이며 **0 이 아니다** — 0 으로
기록하면 화면이 "무료"라고 거짓말한다.

### `verify` 가 `answer` 보다 많은 것은 정상이다

2단 검증은 문장마다 1회 호출한다. 질의당 호출은 `1 + 문장 수` 다(BR-86a).
**비율이 급변하면 답변 길이가 변했다는 신호**로 읽는다.

### `cache_hit_ratio`

BR-94(프롬프트 캐시 배치)가 실제로 동작하는지 확인할 **유일한 방법**이다.
**0% 가 지속되면 회귀**다 — 접두사가 매 요청 깨지고 있다는 뜻이며, 아무것도 오류를
내지 않는다. 호출이 없으면 `null`.

---

## 6. 화면

| 경로 | 화면 | JS 없이 동작 |
|---|---|---|
| `GET /` | P5 질의 | ✅ `POST /query` 로 폴백 |
| `GET /usage` | P6 사용량 | ✅ 서버 렌더링 |

무JS 경로는 **동일한 `QueryService.answer`** 를 호출한다. ID 화이트리스트, 2단 검증,
인용 동결이 전부 같다. 포기하는 것은 텍스트가 흘러나오는 것을 보는 것뿐이다.

### 항상 표시되는 것 (FR-35, BR-84)

면책 문구는 **거부 응답에도** 표시되며 접히지 않는다.

---

## 7. 내부 전용 — `reranker` 컨테이너

| 메서드 | 경로 | 비고 |
|---|---|---|
| `GET` | `http://reranker:8100/healthz` | 모델을 적재하지 **않는다** |
| `POST` | `http://reranker:8100/rerank` | `{query, docs[]}` → `{scores[], model}` |

**호스트에 노출하지 않는다**(NFR-18). `profiles: ["reranker"]` 라 기본 미기동이고,
`RERANKER_ENABLED=false` 가 기본이다.

`scores` 는 **입력 순서대로** 반환한다(정렬하지 않음). 순서와 동점 처리, 그리고
폴백 경로를 호출자가 소유하기 때문이다.

헬스체크가 모델을 적재하지 않는 이유: 재시작마다 2GB 가중치를 받는 동안 unhealthy 로
보고되면, `app` 의 **선택적** 의존이 장애처럼 보인다.
