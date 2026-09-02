# Logical Components — u2-rag-qa

**유닛**: `u2-rag-qa` (2/5)
**작성일**: 2026-08-25
**대응 패턴**: `nfr-design-patterns.md` SP-1~9 / PP-1~6 / CP-1~3

---

## 1. 신규 컨테이너 — `reranker`

FQ2-4 · PP-2 에 따라 리랭커를 `app` 에서 분리합니다.

| 항목 | 값 | 근거 |
|---|---|---|
| 이미지 | `safeenv-app:latest` (동일 이미지, 다른 command) | UD-3 단일 이미지 모놀리스 유지 |
| command | `uvicorn app.rerank_service:app --port 8100` | |
| 포트 | **내부 전용** — 호스트 미노출 | NFR-18 |
| 네트워크 | `safeenv_net` | |
| 메모리 한도 | **2g** | 모델 0.5~0.8 GiB + 인코딩 피크 여유 |
| 볼륨 | `safeenv_models:/models` | 모델 캐시 공유 |
| 헬스체크 | `GET /healthz` | |
| 기본 상태 | **미기동 가능** — `RERANKER_ENABLED=false` 가 기본 | BR-70 |
| `depends_on` | 없음 | 없어도 `app` 이 동작해야 한다 (BR-71) |

> **`app` 이 `reranker` 에 의존하지 않는 것이 설계 요점입니다.** `depends_on` 을 걸면
> 리랭커 장애가 앱 기동 실패가 됩니다. BR-71 이 "리랭커 실패 시 융합 순위 사용"이라고
> 정한 이상, 기동 의존도 두지 않아야 일관됩니다.

### ⚠️ 인프라 이월 항목 동시 해소

u1 Build & Test 에서 이월된 2건을 이 컨테이너 추가와 함께 처리합니다.

| 이월 항목 | 조치 |
|---|---|
| `app` 에 `safeenv_models` 볼륨 미마운트 | **마운트 추가.** 질의 임베딩(PP-3)이 `app` 에서 실행되므로 이제 필수 |
| 모델 볼륨 실측 4.3 GiB (예상 2 GiB) | 리랭커 모델분 추가. **디스크 요구 재산정 → 6~7 GiB 로 상향** |

---

## 2. 신규 애플리케이션 컴포넌트

기존 C30~C43 (Application Design) 에 더해, NFR 대응으로 생기는 컴포넌트입니다.

| ID | 컴포넌트 | 책임 | 패턴 |
|---|---|---|---|
| **N1** | `PromptAssembler` | system/user 턴 구성, nonce 생성, 근거·질의문 이스케이프 및 구획 래핑 | SP-1, SP-2, SP-3, SP-7 |
| **N2** | `EvidenceSanitizer` | 근거 본문에서 태그 유사 문자열 이스케이프. **본문을 삭제하지 않는다** — 인용 스니펫은 원문 그대로여야 한다(BR-89) | SP-3 |
| **N3** | `InjectionScanner` | 색인 시점 휴리스틱 스캔 → `chunk.meta.suspected_injection` | SP-4, SP-5 |
| **N4** | `PromptRepository` | `prompts/index.yaml` 로딩, `name` → 활성 semver 해석, 본문 캐시 | CP-2, BR-93 |
| **N5** | `PricingTable` | `config/llm_pricing.yaml` 조회. **미등록 시 None** | CP-1, BR-96 |
| **N6** | `TracedLlm` | `LLMPort` 데코레이터 — 토큰·지연·비용·프롬프트 버전 기록 | CP-3, BR-95 |

### N2 의 경계 — 중요

`EvidenceSanitizer` 는 **프롬프트에 넣는 사본만** 변형합니다. `chunk.text` 와
`citation_snapshot.snippet` 은 **원문 그대로**입니다.

> 이스케이프된 텍스트를 인용 스니펫으로 보여주면 사용자가 보는 근거가 원문과 달라집니다.
> BR-89(스니펫 = `extracted_text` 구간)와 BR-30 이 깨지는 지점이므로, 변형은
> **프롬프트 조립 경로 안에서만** 일어나고 밖으로 새어 나가지 않습니다.

### N3 의 배치 — u1 경로에 삽입

`InjectionScanner` 는 **u1 청킹 직후**에 실행되어 `chunk.meta` 를 채웁니다. u2 질의
경로에는 추가 비용이 0 입니다(SP-4).

> 이는 **u1 코드에 대한 유일한 변경**입니다. E16 을 SET NULL 로 바꾼 결과
> `ChunkRepo.replace_for_document` 변경은 불필요해졌으므로(FD 정정 2026-08-25),
> u1 변경은 이 스캐너 한 곳으로 줄었습니다.
>
> 기존 코퍼스에는 **재색인 1회**로 플래그가 채워집니다. BR-44(원본 보존) 덕분에
> 소스 재호출은 필요 없습니다 — BR-20a·BR-31a·BR-27a 와 같은 경로입니다.

---

## 3. 신규 환경변수 (NFR-23)

| 변수 | 기본값 | 규칙·패턴 |
|---|---|---|
| `ANTHROPIC_API_KEY` | *(없음)* | BR-02 — 미설정 시 질의 기능만 비활성, 앱은 기동 |
| `LLM_MODEL` | `claude-opus-5` | NFR-21 |
| `LLM_MAX_RETRIES` | `1` | FQ3-14 (429 는 별도 최대 2회) |
| `RERANKER_ENABLED` | `false` | BR-70 |
| `RERANKER_URL` | `http://reranker:8100` | PP-2 |
| `RERANKER_TIMEOUT_MS` | `1200` | PP-2, FQ3-10 |
| `QUERY_EMBED_CACHE_SIZE` | `1024` | PP-3, FQ3-12 |
| `VERIFY_CONCURRENCY` | `4` | PP-5, FQ3-13 |
| `REFUSAL_SCORE_THRESHOLD` | *(보수적 기본값, u4 캘리브레이션)* | BR-73, BR-74, NFR-7 |
| `QUERY_MAX_CHARS` | `2000` | SP-7, FQ3-8 |
| `QUERY_LOG_RETENTION_DAYS` | `90` | FQ3-16, NFR-14 |
| `INJECTION_SCAN_ENABLED` | `true` | SP-4 |

전부 `.env.example` 에 노출하고 `app/core/config.py` 에 검증기를 둡니다 — u1 과 동일한 방식입니다.

---

## 4. 데이터 요소 추가

| 대상 | 추가 | 근거 |
|---|---|---|
| `chunk.meta` | `suspected_injection: bool` | SP-4. **스키마 변경 없음** — 기존 JSONB 키 추가 |
| `llm_call` | (E18 에 이미 정의됨) | 변경 없음 |

> `chunk.meta` 가 JSONB 라서 마이그레이션이 필요 없습니다. u1 이 메타를 JSONB 로 둔
> 결정(DD)의 값이 여기서 나옵니다.

---

## 5. 컴포넌트 상호작용

```
POST /api/query
   │
   ├─ SP-9 입력 검증 (길이·제어문자·정규화)
   │
   ├─ C30 EntityExtractor ──(규칙 실패 시)── N6 TracedLlm ─→ LLMPort
   │
   ├─ C31/C32 검색 (병렬)          ← PP-3 질의 임베딩 LRU
   ├─ C33 RRF 융합 + 유형 할당
   ├─ C34 Reranker ──HTTP 1.2s──→ [reranker 컨테이너]     ← PP-2
   │        └ 실패 → 융합 순위 사용 (BR-71)
   │
   ├─ C39 1단 거부 판정                                    ← 여기서 끝나면 LLM 호출 0
   │
   ├─ N1 PromptAssembler
   │     ├ N4 PromptRepository ─→ prompts/answer/<semver>.md
   │     ├ N2 EvidenceSanitizer ─→ 이스케이프 (사본만)
   │     └ nonce 생성 → <evidence-{nonce}> 구획            ← SP-1~3, SP-7
   │
   ├─ C38 AnswerGenerator ─ N6 TracedLlm ─→ LLMPort (structured output)
   │
   ├─ SP-8 chunk_id 화이트리스트 대조                      ← BR-81
   │
   ├─ C40 SupportVerifier ─ 동시 4 ─ N6 TracedLlm ─→ LLMPort  ← SP-6, PP-5
   │
   └─ 확정 저장 (E15+E16+E17, 단일 트랜잭션)               ← BR-92

색인 경로 (u1):
   C22 ChunkStage → N3 InjectionScanner → chunk.meta.suspected_injection
```

---

## 6. 검증 방법 (Build & Test 로 이월)

| 대상 | 검증 |
|---|---|
| SP-3 nonce 구분자 | 본문에 `</evidence>` 를 심은 청크로 경계 탈출 시도 → 실패 확인 |
| SP-5 오탐 방지 | MSDS 응급조치 섹션이 `suspected_injection=true` 로 **제외되지 않는지** 확인 |
| SP-6 검증자 격리 | 검증 프롬프트에 질문·타 근거가 포함되지 않는지 단위 테스트 |
| SP-8 화이트리스트 | 존재하지 않는 `chunk_id` 를 반환하도록 모킹 → 인용 제거 확인 |
| PP-1 지연 예산 | 리랭커 ON/OFF 각각 `retrieval_ms` P95 실측 |
| PP-2 리랭커 폴백 | 컨테이너 정지 상태에서 질의 → 답변 성공 + 경고 로그 |
| PP-4 캐시 적중 | `cache_read_tokens > 0` 확인. **0% 지속은 회귀** |
| PP-5 동시성 | 10문장 답변에서 동시 호출이 4를 넘지 않는지 |
| BR-92 트랜잭션 | 스냅샷 저장 실패 주입 → 답변·인용 전부 롤백 확인 |

> **적대적 회귀 케이스는 u4 골든셋에 포함**됩니다. u2 에서는 위 항목을 수동·단위
> 검증으로 확인하고, u4 에서 자동 회귀로 전환합니다.
