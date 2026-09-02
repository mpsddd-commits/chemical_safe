# Code Summary — u2-rag-qa

**유닛**: `u2-rag-qa` (2/5)
**작성일**: 2026-08-25
**선행 승인**: Functional Design (지적 3건 반영) · NFR Design
**테스트**: **400 통과 + 1 스킵**, ruff clean

---

## 1. 산출물

### 신규 파일 (26)

| 경로 | 줄 | 책임 |
|---|---:|---|
| `app/rag/types.py` | 167 | 값객체 V1~V4, 구조화 출력 스키마 |
| `app/rag/sanitize.py` | 34 | N2 — 근거 XML 이스케이프 (SP-3) |
| `app/rag/prompts.py` | 55 | N4 — 프롬프트 저장소·버전 해석 (BR-93) |
| `app/rag/assembler.py` | 123 | N1 — 역할 분리·nonce 구획 (SP-1·2·3·7) |
| `app/rag/entities.py` | 120 | C30 — 규칙 우선 엔티티 추출 (BR-64~66) |
| `app/rag/refusal.py` | 85 | C39 — 1단 거부 (BR-73~75) |
| `app/rag/generator.py` | 132 | C38 — 생성 + ID 화이트리스트 (BR-79~83, SP-8) |
| `app/rag/verifier.py` | 100 | C40 — 2단 검증 (BR-85~87, SP-6, PP-5) |
| `app/rag/streaming.py` | 193 | 부분 JSON → 문장 텍스트 증분 추출 (FQ2-13) |
| `app/rag/citations.py` | 173 | C41 — 근거 해석·인용 표시 (BR-89~92a) |
| `app/rag/pricing.py` | 86 | N5 — 단가표, 미등록 시 NULL (CP-1, BR-96) |
| `app/rag/retrieval/fusion.py` | 101 | C33 — RRF·문서유형 할당 (BR-68·69) |
| `app/rag/retrieval/retrievers.py` | 165 | C31·C32 — 두 검색 경로 + 질의 임베딩 캐시 |
| `app/rag/retrieval/rerank_client.py` | 87 | C34 — 리랭커 HTTP 클라이언트 (PP-2) |
| `app/rerank_service.py` | 74 | `reranker` 컨테이너 진입점 |
| `app/services/query_service.py` | 292 | S3 — W7·W8·W9 오케스트레이션 |
| `app/services/observability_service.py` | 59 | S8 — W10·W11 |
| `app/db/repositories/queries.py` | 167 | E14~E17, 확정 저장 단일 트랜잭션 (BR-92) |
| `app/db/repositories/traces.py` | 167 | E18, 사용량 집계 (BR-95·96) |
| `app/processing/injection_scan.py` | 86 | N3 — 색인 시점 탐지 (SP-4·5) |
| `migrations/versions/0002_query.py` | 160 | 테이블 5, 인덱스 4 |
| `app/web/routers/query.py` | 168 | SSE 질의, 인용 스니펫 |
| `app/web/routers/usage.py` | 81 | P6 + `/api/usage` |
| `app/web/routers/pages.py` | 112 | P5 + 무JS 답변 경로 |
| `app/web/templates/query.html` · `usage.html` | — | P5 · P6 |
| `app/web/static/query.js` | — | SSE 클라이언트 |
| `prompts/{answer,verify,entity}/1.0.0.md` + `index.yaml` | — | BR-93 |
| `config/llm_pricing.yaml` | — | CP-1 |

### 수정 파일 (8)

| 경로 | 변경 |
|---|---|
| `app/core/config.py` | 환경변수 12종 + 검증기 4종 |
| `app/core/types.py` | Enum 5종, `ChunkMeta.suspected_injection` |
| `app/adapters/llm_anthropic.py` | `NotImplementedError` → 실제 구현 + 스트리밍 |
| `app/adapters/tracing.py` | 하드코딩 단가표 → `PricingTable` 위임 |
| `app/db/models.py` | E14~E18 ORM |
| `app/processing/runner.py` | 청킹 직후 `InjectionScanner` 호출 |
| `app/indexing/keyword_index.py` | **결함 25·부수 발견 수정** (§4) |
| `app/main.py` · `app/web/routers/admin.py` · `base.html` | 라우터 등록, `/` 를 P5 에 양보 |

---

## 2. 계획 대비 조정 3건

**(1) `retrieval/keyword.py` · `vector.py` → `retrievers.py` 하나로 통합.**
u1 의 `KeywordIndex` · `VectorIndex` 가 이미 검색을 제공하므로 두 파일은 얇은 래퍼가
될 뿐이었다. 질의 임베딩 캐시(PP-3)와 세이브포인트 격리를 한곳에 모았다.

**(2) 대시보드가 `/` 에서 `/admin` 으로 이동.**
P5 가 `/` 로 명세되어 있다(FD 화면 목록). 루트는 이 시스템이 존재하는 이유인 질의
화면이 갖고, 운영 대시보드는 그것을 돌리기 위한 도구다.

**(3) `/api/chunks/{id}/snippet` → `/api/citations/{id}/snippet`.**
FD 검토에서 정정된 사항의 구현(BR-92a).

---

## 3. 설계 판단 기록

### 3.1 인젝션 방어는 이미 절반이 있었다

새 패턴을 세기 전에 FD 가 확보한 방어를 셈했더니, **출력 측 유출 경로가 구조적으로
없었다**. 답변 스키마(BR-79)에 URL 이 들어갈 자리가 없고 링크는 서버가 붙인다(BR-92a).
인용 정확도를 위해 도입한 규칙이 결과적으로 가장 강한 인젝션 방어였다.

새로 만든 것은 남은 빈틈 두 곳뿐이다 — 구분자 위조(SP-3)와 검증자 오염(SP-6).

### 3.2 SP-6 을 주석이 아니라 시그니처로 강제

```python
def for_verification(self, sentence: str, evidence: list[Evidence]) -> AssembledPrompt
def verify_one(self, sentence: AnswerSentence, evidence_by_id: dict[int, Evidence])
```

검증자에게 질문을 넘길 **방법 자체가 없다.** 규약을 문서에 적어두면 언젠가 깨지지만,
인자가 없으면 깨지지 않는다.

### 3.3 스트리밍은 표시 전용

BR-79 가 스키마를 강제하므로 모델이 흘리는 것은 산문이 아니라 부분 JSON 이다.
`streaming.py` 가 `sentences[].text` 를 증분 추출하되, **권위 있는 답변은 완성된 JSON
에서 파싱**한다. 이것은 한계가 아니라 안전 속성이다 — 스트림에서 나온 것은 어느 것도
ID 화이트리스트(SP-8)와 검증(BR-85~87)을 통과하기 전까지 답변이 아니다.
인용 배지는 `final` 이후에만 붙는다.

### 3.4 실패 정책이 클래스 구조에 드러난다

검색·순위는 **낮춰서 진행**하고(BR-71·72), 근거의 정확성은 **낮추지 않는다**.
`QueryRepo.finalise` 만 전면 롤백하는 유일한 지점인 이유가 이것이다 —
근거를 보여줄 수 없는 답변은 이 시스템에서 답변이 아니다(SC-2).

### 3.5 제공자 전환이 어댑터 하나였다 (NFR-21)

사용자 요청으로 기본 LLM 제공자를 **Anthropic → Google Gemini 무료 티어**로 바꿨다.
`rag/` 의 규칙·워크플로·테스트가 **한 줄도 바뀌지 않았다.** u1 이 구현 없이 `LLMPort`
를 먼저 정의한 것(DD-6, DD-21)이 값을 한 지점이다.

스키마 검증(`rag/schema_guard.py`)은 **제공자와 무관하게** 둔다. 두 제공자 모두
서버 측에서 강제하므로 이 검증은 실제로는 발동하지 않지만, 넣지 않으면 **BR-79 의
보장이 그때그때 설정된 제공자의 것**이 된다. BR-79 는 제공자 기능이 아니라 계약이다.

Gemini 가 `additionalProperties` 를 거부해 변환에서 제거하는데, **제공자가 더 이상
거부하지 않게 된 그 키가 정확히 우리가 직접 확인해야 하는 키**다.

### 3.6 u1 단가표를 함께 고쳤다

`adapters/tracing.py` 의 `_RATES` 가 미등록 모델에 **0.0 을 반환**하고 있었고,
`claude-opus-5` 단가가 $15/$75 로 **틀려 있었다**(실제 $5/$25). u1 에서는 LLM 호출이
없어 무해했지만 u2 가 호출을 시작하는 순간 BR-96 위반이다.

---

## 4. 실행으로 발견한 결함 3건 (audit 결함 25~27)

세 결함 모두 **단위 테스트와 컨테이너 기동 점검을 통과한 상태**였다.

| # | 결함 | 성격 |
|---|---|---|
| 25 | `to_tsvector(varchar, text)` — 키워드 검색이 **한 번도 동작한 적 없음** | u1 잔존 |
| 26 | BR-72 가 실현 불가능 — Session 공유로 한쪽 실패가 반드시 다른 쪽을 죽임 | 구현 |
| 27 | 거부 임계값이 **RRF 순위 점수**를 읽음 — 보정으로 고칠 수 없는 종류 | 설계 |

부수 발견: `plainto_tsquery` 의 AND 결합 + 형태소 분석 부재로 **자연어 문장 질의가
키워드 0건**이었다. 하이브리드 검색이 사실상 벡터 전용으로 반쪽 동작 중이었고
아무것도 실패를 보고하지 않았다.

상세와 실측치는 `audit.md` 참조.

**교훈**: u1 Build & Test 의 "Docker 기동 실측"은 기동만을 검증했다. u2 Build & Test
에서는 **실질의 종단**을 명시 항목으로 둔다(DoD 보강).

---

## 5. 테스트

| 파일 | 케이스 | 대상 |
|---|---:|---|
| `test_prompt_assembly.py` | 20 | SP-1·2·3·6·7 — 구분자 탈출, nonce, 검증자 격리 |
| `test_injection_scan.py` | 23 | SP-4·5 — **오탐 방지 10건**(실제 MSDS·법령 문장) |
| `test_streaming.py` | 25 | FQ2-13 — 청크 경계 독립성(속성 테스트 100 examples) |
| `test_generation_and_verification.py` | 16 | BR-79~87, SP-8, PP-5 |
| `test_retrieval_regressions.py` | 18 | 결함 25~27 회귀 |
| `test_fusion.py` | 9 | BR-68·69 |
| **u2 소계** | **111** | |
| u1 기존 | 266 | |
| **합계** | **377 통과 + 1 스킵** | |

가장 중요한 테스트 두 개:

```python
def test_verifier_never_sees_the_question(self):
    """SP-6 — "질문에 좋은 답인가"는 검증자의 일이 아니다.
    질문을 알면 설득당할 여지가 생긴다."""

@pytest.mark.parametrize("text", LEGITIMATE)  # 실제 MSDS·법령 문장 10건
def test_legitimate_safety_text_is_not_flagged(text):
    """SP-5 — 과탐지의 대가는 안전 정보를 지우는 방어다."""
```

---

## 6. 실측 (Docker 실환경, 2026-08-25)

```
질의 "황산 취급 시 보호구는?"
  retrieval 5건 / 콜드 14,897ms(모델 로드) → 웜 339ms    NFR-2 예산 2,500ms
  근거 1위: 황산 MSDS msds_08 (노출방지 및 개인보호구)
  → ANTHROPIC_API_KEY 미설정으로 생성 중단 (BR-02 정상 동작)

질의 "오늘 점심 메뉴 추천해줘"
  → refused / below_threshold + 원문 링크 5건 (BR-75)

마이그레이션 0002_query 적용 완료, 테이블 19개
라우트 19개 등록, `/` `/usage` `/admin` 전부 200
```

---

## 7. 미검증 — Build & Test 로 이월

| 항목 | 사유 |
|---|---|
| **실제 답변 생성·인용·2단 검증** | `GEMINI_API_KEY` 미설정 |
| NFR-1 첫 토큰 P95 5초 | 위와 동일 |
| BR-86a 호출 수 배수 실측 | 위와 동일 |
| PP-4 프롬프트 캐시 적중률 | 위와 동일 |
| `reranker` 컨테이너 기동·폴백 | 모델 다운로드 필요. `--profile reranker` |
| BR-92 롤백 실측 | 저장 실패 주입 필요 |
| N3 스캐너 전 코퍼스 적용 | 재색인 1회 필요 (기존 청크는 플래그 없음) |
| NFR-5·NFR-6 수치 | 골든셋이 u4 산출물 |
