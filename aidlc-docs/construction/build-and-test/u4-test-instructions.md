# u4 재현 절차 — 골든셋 평가

u2·u3 절차를 대체하지 않는다. u4 에서 **추가된 것만** 적는다.

| 계층 | 실행 | LLM | 걸리는 시간 |
|---|---|---|---|
| 단위 | 기본 | 0 | 수초 |
| 통합 | `-m integration` | 0 | 20초 |
| **검색 평가** | `evaluate --retrieval-only` | **0** | **수초** |
| **전체 평가** | `evaluate --full` | 문항당 6.25 | **무료 티어에서 7일** |

---

## 0. 전제

```bash
cd safeenv
docker compose up -d
docker compose exec -T postgres psql -U safeenv -d safeenv -At -c "select version_num from alembic_version;"
# 0003_evaluation 이어야 한다
```

골든셋은 **이미지에 포함된다**(`COPY eval ./eval`). 파일을 고쳤으면 다시 빌드해야
컨테이너 안의 실행이 그 파일을 본다.

```bash
docker compose build worker
```

---

## 1. 단위 — 559 passed, 1 skipped

```bash
python -m pytest tests/unit -q && python -m ruff check app tests
```

u4 분 63건은 DB·네트워크·모델 어디에도 닿지 않는다(NFR-28). 확인:

```bash
POSTGRES_HOST=203.0.113.1 REDIS_URL=redis://203.0.113.1:6379 python -m pytest tests/unit -q
```

---

## 2. 통합 — 39 passed, 1 skipped

```bash
export POSTGRES_PASSWORD="$(grep -m1 '^POSTGRES_PASSWORD=' .env | cut -d= -f2-)"
export POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433
python -m pytest tests/integration -m integration -q
```

> 비밀번호를 화면에 찍지 말 것(NFR-14).

이 중 `test_evaluation.py` 14건이 **실제 골든셋 30문항을 실 코퍼스에 대조**한다.
파싱 규칙이 바뀌어 섹션 코드가 달라지면 여기서 먼저 깨진다.

---

## 3. 검색 평가 — 매일 돌리는 것

```bash
docker compose run --rm worker python -m app.cli evaluate --retrieval-only
```

**LLM 호출 0.** 30문항 전체가 수초에 끝난다. 리포트의 `LLM 호출` 이 0이 아니면
BR-119 가 깨진 것이고, `_NoLLM` 가드가 먼저 `AssertionError` 로 터진다.

기대 (2026-08-28 실측, 실행 2):
```
Recall@5 0.700 / MRR 0.546 / 거부 정확도 0.400 / 오거부율 0.000 / LLM 0
⚠ 후보 목록이 5건이라 Recall@10 은 측정할 수 없습니다 (FINAL_TOP_K=5)
```

이 명령이 잡아내는 것은 **LLM 앞단의 회귀**다 — u2 결함 27(RRF 를 임계값으로 읽음)·
결함 45(완전일치를 코사인이 뒤집음)가 그 자리에서 생겼다.

---

## 4. 전체 평가 — 며칠에 걸쳐

```bash
docker compose run --rm worker python -m app.cli evaluate --full
```

### 산수를 알고 시작할 것

```
답변형 25문항 × (생성 1 + 검증 ~4) = 131 호출   ← 답변 모델
                    + 심판 1 × 25 =  25 호출   ← 심판 모델 (별도 할당량)
무료 티어 = 모델당 하루 20
→ 답변 모델 기준 7일
```

하루치가 끝나면 `partial` 로 멈추고 **종료코드 4**를 낸다. 실패가 아니다.

```bash
docker compose run --rm worker python -m app.cli evaluate --resume <RUN_ID>
```

재개는 `done`·`skipped` 문항을 건너뛴다. 골든셋 파일이 그 사이에 바뀌었으면
**거부한다** — 서로 다른 골든셋으로 매긴 점수가 한 실행에 섞이기 때문이다.

### 하루 분량을 명시적으로 자르려면

```bash
EVALUATION_BATCH_SIZE=3 docker compose run --rm worker python -m app.cli evaluate --full
```

할당량 오류를 기다리지 않고 3문항만 처리하고 멈춘다.

---

## 5. 이력·기준선·회귀

```bash
docker compose run --rm worker python -m app.cli evaluate --list
docker compose run --rm worker python -m app.cli evaluate --promote <RUN_ID>   # BR-129
docker compose run --rm worker python -m app.cli evaluate --compare <RUN_ID>
```

기준선은 **사람이 올린다**. 자동 승격이면 나빠진 실행이 새 기준선이 되어 회귀가
영원히 감지되지 않는다. 승격은 배타적이다 — 한 번에 하나만 기준선이다.

### 종료코드 (UD-10 / NFR-26)

| 코드 | 의미 | CI 에서 |
|---|---|---|
| 0 | 회귀 없음 | 통과 |
| 1 | **회귀** — 기준선 대비 하락 | 실패 |
| 2 | 골든셋 검증 실패 | 실패 |
| 3 | 실행 실패 (DB·설정) | 실패 |
| 4 | `partial` — 할당량 소진 | **실패로 취급하지 말 것** |

4를 1과 구분하는 이유: 할당량 소진은 품질 문제가 아니다. 무료 티어에서 4를 실패로
취급하면 CI 가 항상 빨간불이 된다.

---

## 6. 확인할 것

```bash
# 문항별 결과
docker compose exec -T postgres psql -U safeenv -d safeenv -c "
select question_id, category, expects, outcome, recall_at_5, reciprocal_rank,
       refusal_correct, judge_correct, judge_faithful, llm_calls
from evaluation_item where run_id = <RUN_ID> order by question_id;"

# 심판이 왜 그렇게 봤는지 — 숫자만 남기지 않는 이유
docker compose exec -T postgres psql -U safeenv -d safeenv -c "
select question_id, judge_correct, judge_faithful, judge_reason
from evaluation_item where run_id = <RUN_ID> and judge_reason is not null;"

# 실행이 무엇을 측정했는지
docker compose exec -T postgres psql -U safeenv -d safeenv -c "
select id, mode, status, answer_model, judge_model, prompt_versions,
       corpus_fingerprint, golden_set_hash from evaluation_run order by id desc limit 3;"
```

마지막 질의가 중요하다. **지표가 움직였을 때 모델이 바뀐 것인지, 프롬프트가 바뀐
것인지, 코퍼스가 바뀐 것인지 구분할 수 없으면 그 숫자는 진단에 쓸 수 없다.**
이 값들이 기준선과 다르면 비교는 `incomparable` 이 되고 회귀 판정을 하지 않는다.

---

## 7. 알려진 것

| 현상 | 원인 | 정상인가 |
|---|---|---|
| `Recall@10` 이 `--` | `FINAL_TOP_K=5` 라 후보가 5건뿐 | ⚠️ 결함 49. 같은 수를 두 이름으로 내지 않는다 |
| 거부 정확도 0.400 | 도메인 안 근거 없는 질문(카드뮴·벤젠·의료)이 임계값을 넘는다 | ⚠️ 품질 사실. u2 임계값·라우팅 문제 |
| 물질명 질의 Recall 3/8 | CAS 완전일치는 3/3. 물질명 → 노출경로 섹션 경로가 약하다 | ⚠️ 품질 사실 |
| `--full` 이 곧바로 `partial` | 오늘 할당량이 이미 쓰였다 | ✅ 설계대로 |
