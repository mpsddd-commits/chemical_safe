# Unit Test Execution — safeenv

**작성일**: 2026-08-20
**실측 결과**: **152 passed, 0 failed** (2.4초, 네트워크·DB 비의존)

---

## 1. 실행

```bash
POSTGRES_PASSWORD=test EMBEDDING_DIM=8 pytest
```

`POSTGRES_PASSWORD` 는 `Settings` 검증을 통과시키기 위한 값일 뿐이며,
**단위 테스트는 데이터베이스에 접속하지 않습니다** (DD-20, NFR-28).
`tests/conftest.py` 가 기본값을 주입하므로 환경 변수 없이도 동작합니다.

### 특정 영역만

```bash
pytest tests/unit/test_chunker.py            # 청킹 규칙 BR-26~31
pytest tests/unit/test_structure_msds.py     # MSDS 16섹션 BR-15~20
pytest -k "policy or retry"                  # 정책·재시도
pytest -q --no-header                        # 간결 출력
```

---

## 2. 실측 결과

| 모듈 | 대상 | 케이스 |
|---|---|---|
| `test_retry.py` | BR-41~43, NFR-27 | 16 |
| `test_structure_msds.py` | BR-15~20, 24 | 12 |
| `test_structure_law.py` | BR-21~23 | 12 |
| `test_chunker.py` | BR-26~31, NFR-27 | 12 |
| `test_normalize_and_tokens.py` | BR-14, NFR-27 | 17 |
| `test_change_detector.py` | BR-09~11 | 11 |
| `test_policy.py` | BR-03~05, CON-3 | 11 |
| `test_job_tracker.py` | BR-46~51, 60 | 14 |
| `test_metadata_rules.py` | BR-24, 25, 32, 33, 37, 39 | 12 |
| `test_config_and_logging.py` | NFR-14, 23, BR-57~60 | 25 |
| `test_orchestrator.py` | BR-40~45, 03, 09 | 10 |
| **합계** | | **152** |

**결과: 152 passed, 0 failed, 2.41s**

---

## 3. 속성 기반 테스트 (NFR-27)

Hypothesis 로 탐색하는 불변식입니다. 순수 컴포넌트에만 적용했습니다 (DQ 설계 원칙 4).

| 대상 | 불변식 |
|---|---|
| `RetryPolicy` | 지연은 음수가 될 수 없다 / 총 대기 상한을 넘지 않는다 / TRANSIENT 외에는 어떤 시도 횟수에서도 재시도하지 않는다 |
| `chunk_document` | **모든 청크의 텍스트는 자기 오프셋 구간과 정확히 일치한다** / 빈 청크를 만들지 않는다 / 어떤 입력에도 예외를 던지지 않는다 |
| `count_tokens` | 비어 있지 않은 입력은 항상 1 이상 / 연결은 대략 가산적 |

**청크 오프셋 불변식이 가장 중요합니다.** u2 의 인용 스니펫은 이 오프셋으로
`extracted_text` 를 잘라내어 만들어집니다. 여기가 어긋나면 모든 인용이 틀리되,
원문을 대조해 보기 전까지는 아무도 알아채지 못합니다.

### Hypothesis 와 함수 스코프 픽스처

`@given` 안에서 함수 스코프 픽스처를 쓰면 Hypothesis 가 health check 로 거부합니다.
픽스처가 생성 입력마다 재설정되지 않기 때문입니다.
**health check 를 억제하지 않고** 테스트 내부에서 값을 직접 만들도록 수정했습니다.

---

## 4. 발견·수정된 결함 3건

단위 테스트가 실제 결함을 잡아냈습니다. 상세는 `build-and-test-summary.md` §4 참조.

| # | 결함 | 심각도 |
|---|---|---|
| 1 | **청킹이 섹션 경계를 넘어 병합** — 16섹션이 14청크가 됨 | 🔴 인용 정확도 |
| 2 | **`Authorization: Bearer <token>` 이 마스킹되지 않음** | 🔴 보안 |
| 3 | **`extra` 최상위 비밀 필드가 마스킹되지 않음** | 🔴 보안 |

각각에 회귀 테스트를 추가했습니다 (`TestMaskingPrecision` 3건 포함).

---

## 5. 테스트가 다루지 않는 것

의도적으로 단위 테스트 범위 밖입니다. 통합 테스트 또는 Docker 실측으로 다룹니다.

| 항목 | 이유 | 검증 위치 |
|---|---|---|
| DB 스키마·인덱스 | PostgreSQL 필요 | 통합 테스트 |
| pgvector 벡터 검색 | 확장 필요 | 통합 테스트 |
| 전문검색 인덱스 (BR-38) | PostgreSQL FTS 필요 | 통합 테스트 |
| 트랜잭션 경계 (BR-53) | DB 필요 | 통합 테스트 |
| 실제 임베딩 모델 | 모델 파일·메모리 | Docker 실측 |
| 실제 PDF 파싱 성공률 | 실제 문서 샘플 (R-2) | 미해소 |
| 공공 API 응답 형식 | 인증키 (R-1) | 미해소 |

---

## 6. 커버리지

커버리지 측정 도구는 도입하지 않았습니다. 대신 **추적성으로 대체**합니다:
`code/traceability.md` §2 가 BR-01~BR-62 각각에 대해 구현 위치와 검증 테스트를 매핑하며,
단위 테스트로 검증된 것 48건 / Build & Test 이월 14건으로 집계되어 있습니다.

수치 커버리지가 필요해지면:

```bash
pip install pytest-cov
pytest --cov=app --cov-report=term-missing
```
