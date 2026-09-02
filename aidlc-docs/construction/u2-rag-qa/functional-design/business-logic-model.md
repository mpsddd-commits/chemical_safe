# Business Logic Model — u2-rag-qa

**유닛**: `u2-rag-qa` (2/5)
**작성일**: 2026-08-24

워크플로 **W7 ~ W11**. (W1~W6 은 u1)

---

## W7. 질의 → 근거 검색 (FR-14, 15, 16, 17)

```
[질의문]
   │
   ├─ 1. 정규화 (u1 C16 재사용)
   │     공백·전각·유니코드 정규화. 검색과 색인이 같은 정규화를 써야 한다
   │
   ├─ 2. 엔티티 추출 (C30, FR-17)
   │     CAS 정규식 → substance / substance_synonym 조회 → 표준 물질명
   │     UN 번호 정규식
   │     문서 유형 힌트 추정 (필터 아님, 가중치 힌트)
   │     └─ 규칙으로 아무것도 못 찾으면 LLM 1회 호출 (purpose=entity)
   │
   ├─ 3. 후보 검색 — 두 갈래를 병렬로
   │     ├─ C31 KeywordRetriever : to_tsvector 전문검색 + meta->>'cas_number' 완전일치
   │     │                          → 상위 30건
   │     └─ C32 VectorRetriever  : 질의 임베딩(캐시) → HNSW 코사인 → 상위 30건
   │
   ├─ 4. 융합 (C33, FQ2-1)
   │     RRF:  score(d) = Σ  1 / (k + rank_i(d)),  k = 60
   │     순위만 사용하므로 두 검색의 스코어 스케일 차이를 신경 쓰지 않아도 된다
   │     → 상위 20건
   │
   ├─ 5. 문서 유형 최소 할당 (FQ2-3)
   │     법령이 코퍼스의 69% (실측). 융합 결과가 법령으로만 채워지면
   │     msds·incident 에서 각 1건씩을 최하위와 교체하여 끌어올린다
   │     └─ 해당 유형에 후보가 아예 없으면 교체하지 않는다 (없는 근거를 만들지 않는다)
   │
   ├─ 6. 리랭크 (C34, FQ2-4) — 기본 OFF
   │     RERANKER_ENABLED=true 일 때만. 별도 컨테이너에 HTTP 호출
   │     타임아웃 시 융합 순위를 그대로 사용하고 경고 로그 (검색을 실패시키지 않는다)
   │     → 상위 5건
   │
   └─ 7. 소유자 스코프 (C55, u5 선반영)
         현재는 owner_id IS NULL 만 조회. u5 에서 확장

[Evidence 목록 (최대 5)]
```

**측정점**: 3~7 구간의 소요 시간이 `query_log.retrieval_ms` (NFR-2, P95 2.5초).

---

## W8. 근거 → 답변 (FR-18, 19, 20, 21)

```
[Evidence 목록]
   │
   ├─ 1. 1단 거부 판정 (C39, FR-20, FQ2-6)
   │     후보 0건               → refused / no_candidates
   │     최상위 스코어 < 임계값  → refused / below_threshold
   │     └─ 거부 시 LLM 을 호출하지 않는다. 원문 링크 목록만 반환
   │
   ├─ 2. 컨텍스트 조립 (C37)
   │     프롬프트 = [시스템(고정)] + [근거 블록] + [질문]
   │     근거는 데이터 영역으로 격리 — 상세는 NFR Design (NFR-16)
   │     캐시 배치: 시스템 프롬프트가 앞, 질문이 맨 뒤
   │       (프롬프트 캐시는 접두사 일치. 매 요청 바뀌는 질문을 앞에 두면 캐시가 죽는다)
   │
   ├─ 3. 구조화 생성 (C38, FQ2-11)
   │     messages.parse(output_format=GeneratedAnswer) → parsed_output
   │     스키마: { sentences: [{ text, chunk_ids }] }
   │     ├─ stop_reason == "refusal"      → refused / provider_refusal
   │     ├─ chunk_ids 가 빈 문장이 있으면  → 1회 재시도 (FQ2-12)
   │     └─ 재시도 후에도 비어 있으면 그 문장 제거
   │
   ├─ 4. 근거 ID 검증
   │     LLM 이 반환한 chunk_id 가 실제로 넘긴 근거에 있는지 확인
   │     없는 ID → 해당 인용 제거. 남은 인용이 0 이면 문장 제거
   │     └─ 존재하지 않는 청크를 인용하는 것이 가장 나쁜 실패다
   │
   ├─ 5. 2단 근거 지지 검증 (C40, FR-21, FQ2-8)
   │     문장마다 [문장 + 인용된 근거 본문] 을 LLM 에 보내 지지 여부 판정
   │     문장들은 병렬 호출 (지연 누적을 막는다)
   │     ├─ supported   → 유지
   │     ├─ unsupported → 제거, removed=true (FQ2-9)
   │     └─ 호출 실패    → unverified → 제거 (지지로 간주하지 않는다)
   │
   ├─ 6. 결과 판정
   │     남은 문장 0        → refused / all_sentences_unsupported (FQ2-10)
   │     제거된 문장 있음    → answered_partial (제거 사실을 화면에 표시)
   │     전부 유지          → answered
   │
   └─ 7. 확정 저장 — 하나의 트랜잭션 (E15 + E16 + E17)
         answer_sentence / answer_citation / citation_snapshot 을 함께 커밋
         └─ 실패하면 전부 롤백하고 error 로 응답한다
            스냅샷 없는 인용 행은 존재해서는 안 된다 — 표시도 못 하고
            재색인이 지나가면 무엇을 가리켰는지도 알 수 없다
         재색인이 청크를 교체하면 chunk_id 가 NULL 로 풀리고,
         표시에 필요한 사실은 이미 스냅샷에 동결되어 있다

[답변 + 인용 + 면책 문구]
```

**측정점**: 질의 접수부터 여기까지가 `query_log.total_ms` (NFR-1, 전체 20초).

---

## W9. 인용 → 스니펫 (FR-19, C41)

```
[chunk_id]
   │
   ├─ chunk → document, document_section, extracted_text 조인
   │
   ├─ 스니펫 = extracted_text.text[start_offset : end_offset]      (FQ2-17)
   │     BR-30 이 보장하므로 별도 검색이 필요 없다 — 실데이터 위반 0건
   │
   ├─ 라벨 결정 (FQ2-18)
   │     section_code 있음  → "화학물질관리법 제12조" / "8. 노출방지 및 개인보호구"
   │     section_code NULL  → 문서 제목 + "섹션 정보 없음"
   │        (BR-20a 강등 문서, BR-31a 통합 청크. 없는 라벨을 만들지 않는다 — NFR-8)
   │
   └─ 원문 링크 = document.source_url                              (BR-32)

[인용 표시 단위]
```

---

## W10. LLM 호출 추적 (FR-41, NFR-19)

모든 LLM 호출은 `TracedLlm` 데코레이터를 통과합니다 — u1 의 `TracedEmbedding` 과 같은 구조입니다.

```
호출 전:  시작 시각 기록
호출 후:  llm_call 에 기록
            model, purpose, prompt_name, prompt_version
            input_tokens, output_tokens, cache_read_tokens  (usage 에서)
            latency_ms, ok, stop_reason
            cost_usd = 단가표 조회 성공 시에만 계산, 실패 시 NULL
예외 시:  ok=false, error_kind=classify(exc) 로 기록 후 재전파
```

**비용 계산**: `config/llm_pricing.yaml` 에서 `model` 로 조회.
`(input_tokens × input_per_1m + output_tokens × output_per_1m) / 1_000_000`.
단가가 없으면 **NULL** — 0 이 아닙니다 (FQ2-19).

**토큰 수**: 응답의 `usage` 를 그대로 사용합니다. 사전 추정이 필요하면
`client.messages.count_tokens` 를 쓰고, u1 의 휴리스틱(`processing/tokens.py`)이나
외부 토크나이저를 쓰지 않습니다 — 그것은 청크 크기 산정용이고 과금 단위가 아닙니다.

---

## W11. 사용량 집계 (FR-42, C43, S8)

```
입력: 기간 (from, to), 선택적 purpose
출력:
  호출 수, 성공/실패 수
  입력·출력 토큰 합계, 캐시 적중 토큰 합계
  지연 P50 / P95
  비용 합계  +  단가 미등록으로 합계에서 제외된 호출 수
  purpose 별 · model 별 분해
```

제외 건수를 함께 내보내는 것이 핵심입니다. 비용 합계만 보여주면 "이게 전부"라고
읽히는데, 단가 미등록 호출이 섞여 있으면 사실이 아닙니다.

---

## 서비스 배치

| 서비스 | 워크플로 | 비고 |
|---|---|---|
| **S3 `QueryService`** | W7, W8, W9 | 무상태 (FR-22). 히스토리를 참조하지 않는다 |
| **S8 `ObservabilityService`** | W10, W11 | u1 `TraceRepo` 를 실테이블로 승격 |

---

## 실패 처리 요약

| 지점 | 실패 | 처리 |
|---|---|---|
| 질의 임베딩 | 모델 미가용 | 키워드 검색만으로 진행 + 경고 (검색을 죽이지 않는다) |
| 키워드 검색 | DB 오류 | 벡터 검색만으로 진행 + 경고 |
| 양쪽 모두 실패 | | `error` — 정직하게 실패 |
| 리랭커 | 타임아웃·연결 실패 | 융합 순위 사용 + 경고 |
| 답변 생성 | `refusal` | `refused / provider_refusal` |
| 답변 생성 | 5xx·타임아웃 | 재시도 1회 후 `error` |
| 2단 검증 | 호출 실패 | 해당 문장 `unverified` → 제거 |
| 확정 저장(E15·E16·E17) | 실패 | **전부 롤백 후 `error`** *(2026-08-25 정정)* |

> **확정 저장만 "정직하게 실패"하는 이유**: 다른 실패는 전부 *덜 좋은 답변*으로 낮춰
> 진행할 수 있지만(검색 한쪽만, 리랭커 없이, 문장 몇 개 제거), 이건 그렇지 않습니다.
> 이전 판은 "답변은 반환하되 경고"였는데, 그러면 스냅샷 없는 인용이 남습니다.
> 인용 표시 경로는 E17 만 읽으므로(BR-92a) 그 인용은 화면에 아무것도 띄우지 못하고,
> 재색인이 한 번 지나가면 무엇을 가리켰는지 복원할 방법도 없습니다.
> **근거를 보여줄 수 없는 답변을 반환하는 것은 이 시스템에서 답변이 아닙니다**(SC-2).
