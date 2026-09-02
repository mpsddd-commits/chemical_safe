# Test Instructions — u2-rag-qa

**작성일**: 2026-08-26
u1 의 `build-instructions.md` · `unit-test-instructions.md` 는 그대로 유효하다.
이 문서는 **u2 가 추가한 것**만 다룬다.

---

## 1. 세 겹으로 나뉜 이유

| 계층 | 의존 | 기본 실행 | 무엇을 잡는가 |
|---|---|---|---|
| 단위 | 없음 | ✅ | 순수 로직 — 규칙이 규칙대로 계산되는가 |
| 통합 | PostgreSQL | ❌ (`-m integration`) | **트랜잭션·동시성** — 규칙이 실제로 성립하는가 |
| 종단 | + LLM 키 | ❌ 수동 | 답변·인용·성능 |

이 구분은 편의가 아니다. **결함 26·31·37·38 은 전부 단위 테스트를 통과한 상태였다** —
규칙은 옳게 읽혔고, 실제 트랜잭션·스레드 풀·실제 제공자가 개입해야만 드러났다.
각 경우에 **모킹된 그것이 바로 틀린 대상**이었다.

---

## 2. 단위 — 425 passed, 1 skipped

```bash
cd safeenv && python -m pytest tests/unit -q && python -m ruff check app tests
```

DB·네트워크에 닿지 않는다(NFR-28). 건너뛴 1건은 호스트에 `arq` 미설치(u1 의도).

---

## 3. 통합 — 6 passed, 1 skipped

DB 는 기본적으로 호스트에 노출되지 않는다(ID-12). `docker-compose.override.yml` 이
`127.0.0.1:5433` 을 여는 로컬 전용 예외다.

```bash
cd safeenv
export POSTGRES_PASSWORD="$(grep -m1 '^POSTGRES_PASSWORD=' .env | cut -d= -f2-)"
export POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433
python -m pytest tests/integration -m integration -q
```

> `conftest.py` 가 `POSTGRES_PASSWORD` 를 `setdefault` 로 테스트값으로 채우므로,
> 실제 값을 **환경변수로 앞세워야** 한다. 비밀번호를 화면에 찍지 말 것(NFR-14).

건너뛴 1건(`google-genai` 부재)은 컨테이너에서 확인한다:

```bash
docker compose exec -T app python -c "
import threading
from app.adapters.llm_gemini import GeminiLLMAdapter
from app.core.config import get_settings
a = GeminiLLMAdapter(get_settings()); seen=[]; b=threading.Barrier(8)
def g(): b.wait(); seen.append(id(a._get_client()))
ts=[threading.Thread(target=g) for _ in range(8)]
[t.start() for t in ts]; [t.join() for t in ts]
assert len(set(seen))==1; print('결함 38 회귀 OK')"
```

---

## 4. 종단 — 실제 질의

`.env` 에 `GEMINI_API_KEY` 필요. 없으면 앱은 기동하되 질의만 `configuration` 오류다(BR-02).

```bash
docker compose up -d
curl -s -N -X POST http://127.0.0.1:8300/api/query \
  -H 'Content-Type: application/json' \
  --data-binary '{"question":"황산 취급 시 보호구는?"}'
```

**⚠️ 임베딩 모델은 첫 질의에서 적재된다(10~35초).** 성능을 재려면 먼저 무관한 질의로
워밍업할 것 — 그 경로는 1단 거부로 끝나 LLM 할당량을 쓰지 않는다.

```bash
# 워밍업 (할당량 미소모)
curl -s -o /dev/null -X POST http://127.0.0.1:8300/api/query \
  -H 'Content-Type: application/json' --data-binary '{"question":"오늘 점심 메뉴 추천해줘"}'
```

### 할당량
무료 티어는 **모델당 하루 20요청**이고 질의당 `1 + 문장 수` 를 쓴다(BR-86a).
**하루 약 3질의**다. 소진되면 `event: error` 의 `kind: "quota"` 로 구분되어 오는데,
이는 고장이 아니라 개발 세션의 평범한 끝이다.

### 결과 확인
```bash
docker compose exec -T postgres psql -U safeenv -d safeenv -c "
select id, outcome, retrieval_ms, total_ms,
       (select count(*) from answer_sentence where query_id=q.id and not removed) kept
from query_log q order by id desc limit 5;
select purpose, count(*), round(avg(latency_ms)) avg_ms, count(*) filter (where not ok) failed
from llm_call group by 1;"
```

---

## 5. 리랭커 (기본 OFF)

```bash
docker compose --profile reranker up -d reranker
```

**최초 호출은 264초가 걸린다** (bge-reranker-v2-m3 다운로드). 그 뒤 웜 호출이
문서 5건에 2,121~2,830ms 인데 **예산은 1,200ms 다** — 켜면 매번 타임아웃되어
융합 순위로 폴백하므로(BR-71) 얻는 것 없이 1.2초를 잃는다. `RERANKER_ENABLED=false`
를 유지하는 것이 현재로선 맞다.

폴백만 확인하려면 컨테이너를 내린 채 `RERANKER_ENABLED=true` 로 호출한다.
첫 실패는 3.4초(이름 해석이 타임아웃 밖), 이후 60초는 0ms(쿨다운)여야 한다.

---

## 6. 인젝션 스캐너 재적용

`N3` 는 **색인 시점**에 돈다(SP-4). 기존 청크에 플래그를 채우려면 재색인 1회가 필요하다.

```bash
docker compose run --rm --no-deps -T worker python -m app.cli reindex --scope all
```

약 35분. 원본이 보존되어 있어 소스 재호출은 없다(BR-44).

```bash
docker compose exec -T postgres psql -U safeenv -d safeenv -c "
select count(*) total,
       count(*) filter (where (meta->>'suspected_injection')::boolean) flagged,
       count(*) filter (where meta ? 'suspected_injection') scanned
from chunk;"
```

`scanned = total` 이어야 스캐너가 실제로 돈 것이다. `flagged = 0` 은 정상이며
실코퍼스 오탐 0% 를 뜻한다 — **탐지가 안 되는 것과 구분해야 하므로 `scanned` 를 함께 본다.**

---

## 7. 성능 재측정 시 주의

측정을 방해하는 것 세 가지:

1. **임베딩 콜드 스타트** — 첫 질의 10~35초. 워밍업 필수
2. **제공자 부하** — 같은 프롬프트가 4초~120초로 흔들린다. 한 번의 측정으로
   시스템을 판단하지 말 것. 결함 36 이 이것 때문에 뒤늦게 드러났다
3. **타임아웃을 예산에서 유도하지 말 것** — 실측보다 짧게 잡으면 동작하던 질의가
   실패한다(결함 34). 타임아웃은 정지를 끊는 장치이지 SLO 강제 장치가 아니다
