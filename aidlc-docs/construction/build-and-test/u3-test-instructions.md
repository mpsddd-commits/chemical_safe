# u3 재현 절차 — 물질 카드

u2 절차(`u2-test-instructions.md`)를 대체하지 않는다. u3 에서 **추가된 것만** 적는다.

| 계층 | 대상 | 기본 실행 | 무엇을 확인하는가 |
|---|---|---|---|
| 단위 | 없음 | ✅ | 규칙 자체 |
| 통합 | PostgreSQL | ❌ (`-m integration`) | 마스터·링크·카드가 실제로 채워지는가 |
| 성능 | 실행 중인 앱 | ❌ 수동 | NFR-3 |
| 보안 | 실행 중인 앱 | ❌ 수동 | 이스케이프·잘못된 식별자 |

---

## 0. 전제

```bash
cd safeenv
docker compose up -d
docker compose ps          # app·postgres·redis·worker 가 healthy
```

카드에 내용이 있으려면 **물질 마스터와 코퍼스가 겹쳐야 한다**(결함 44). 빈 DB 에서
시작한다면 순서가 중요하다 — BR-08 선정은 이미 수집된 문서에서 물질명을 읽는다.

```bash
docker compose run --rm worker python -m app.cli ingest --source incident_data
docker compose run --rm worker python -m app.cli ingest --source msds_pdf
docker compose run --rm worker python -m app.cli ingest --source ncis_substance   # ← 마지막
```
마지막 단계 로그에 이 줄이 나와야 한다.
```json
{"event": "substance_selection", "scanned": 7189, "terms": 32, "matched": 9, "selected": 40}
```
`matched: 0` 이면 선정이 아무것도 못 했다는 뜻이고, 경고 한 줄이 따로 나간다.

---

## 1. 단위 — 496 passed, 1 skipped

```bash
python -m pytest tests/unit -q && python -m ruff check app tests
```

**NFR-28 증명** — 규칙을 주장하지 말고 도달 불가능한 주소로 돌린다.
(203.0.113.0/24 는 RFC 5737 문서화 전용 대역이다.)

```bash
POSTGRES_HOST=203.0.113.1 REDIS_URL=redis://203.0.113.1:6379 python -m pytest tests/unit -q
```

---

## 2. 통합 — 25 passed, 1 skipped

DB 는 기본적으로 호스트에 노출되지 않는다(ID-12). `docker-compose.override.yml` 이
`127.0.0.1:5433` 을 여는 로컬 전용 예외다.

```bash
export POSTGRES_PASSWORD="$(grep -m1 '^POSTGRES_PASSWORD=' .env | cut -d= -f2-)"
export POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5433
python -m pytest tests/integration -m integration -q
```

> 비밀번호를 화면에 찍지 말 것(NFR-14). `conftest.py` 가 테스트값으로 `setdefault`
> 하므로 실제 값을 환경변수로 앞세워야 한다.

**이 통합 테스트는 코퍼스를 바꾸지 않는다.** 예전에는 실행마다 실제 청크를 1개씩
영구 삭제했다(결함 48). 확인하려면 전후 개수를 비교한다.

```bash
docker compose exec -T postgres psql -U safeenv -d safeenv -At -c "select count(*) from chunk;"
# 통합 테스트 실행
docker compose exec -T postgres psql -U safeenv -d safeenv -At -c "select count(*) from chunk;"
# 두 값이 같아야 한다
```

---

## 3. 규칙 전수 검사 — 카드 49건

첫 번째 물질 하나로 통과하는 테스트는 카드 40건이 전부 비어 있던 결함 44 를 잡지
못했다. 전수로 돌린다.

```bash
docker compose run --rm --no-deps -T worker python - <<'PY'
from sqlalchemy import select
from app.core.types import CardItemKey
from app.db.engine import session_scope
from app.db.models import Substance
from app.services.substance_service import SubstanceService

with session_scope() as s:
    svc = SubstanceService(s)
    ids = [r[0] for r in s.execute(select(Substance.id).order_by(Substance.id)).all()]
    bad_order = bad_source = bad_missing = 0
    dist = {}
    for sid in ids:
        card = svc.card(sid)
        if [i.key for i in card.items] != list(CardItemKey):
            bad_order += 1
        if card.missing_count != sum(1 for i in card.items if i.is_empty):
            bad_missing += 1
        for item in card.items:
            for v in item.values:
                if not (v.source_url and v.document_id):
                    bad_source += 1
        dist[card.missing_count] = dist.get(card.missing_count, 0) + 1
    print(f"카드 {len(ids)}건 / BR-102 {bad_order} / BR-105 {bad_source} / BR-106 {bad_missing}")
    print("결측 분포", dict(sorted(dist.items())))
PY
```
기대: `BR-102 0 / BR-105 0 / BR-106 0`, 분포 `{0: 1, 1: 1, 2: 1, 6: 44, 7: 2}`.

**BR-107 (카드는 스냅샷을 만들지 않는다)** — 위 스크립트 전후로 비교한다.
```bash
docker compose exec -T postgres psql -U safeenv -d safeenv -At -c "select count(*) from citation_snapshot;"
```

---

## 4. NFR-3 성능 — 카드 P95 ≤ 1,000 ms

HTTP 왕복·템플릿 렌더까지 포함한 사용자 관점 수치로 잰다.

```bash
python - <<'PY'
import urllib.request, urllib.parse, time, json
def timed(path, n=60):
    lat = []
    for _ in range(n):
        t0 = time.perf_counter()
        with urllib.request.urlopen("http://127.0.0.1:8300"+path, timeout=60) as r:
            r.read()
        lat.append((time.perf_counter()-t0)*1000)
    lat.sort()
    return f"p50 {lat[len(lat)//2]:6.1f}  p95 {lat[int(len(lat)*0.95)]:6.1f}  max {lat[-1]:6.1f}"

with urllib.request.urlopen("http://127.0.0.1:8300/api/substances?q="+urllib.parse.quote("황산")) as r:
    sid = json.loads(r.read())["matches"][0]["substance_id"]
print("카드 JSON", timed(f"/api/substances/{sid}"))
print("카드 HTML", timed(f"/substances/{sid}"))
print("검색 CAS ", timed("/api/substances?q=7664-93-9"))
PY
```
실측 2026-08-27: 카드 JSON P95 **47.4 ms**, HTML **44.4 ms**, 검색 **34.3 ms**.

> 이 유닛은 LLM 을 호출하지 않는다. u2 의 20초 예산은 거의 전부 모델 호출이었고
> 여기에는 그것이 없으므로, 이 수치는 코퍼스가 커져도 크게 변하지 않는다.

---

## 5. 보안 — 이스케이프와 잘못된 식별자

```bash
python - <<'PY'
import urllib.request, urllib.error, urllib.parse
def get(p):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8300"+p, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")

for p in ['<script>alert(1)</script>', '"><img src=x onerror=alert(1)>',
          "'; DROP TABLE substance; --", "A"*5000]:
    s, html = get("/substances?q=" + urllib.parse.quote(p))
    print(s, "원문 반사:", p in html, "::", p[:30])

for p in ["/substances/999999", "/substances/-1", "/substances/abc"]:
    print(p, get(p)[0])

print("DB 무사:", get("/api/substances?q=7664-93-9")[0])
PY
```
기대: 원문 반사 전부 `False`, 404/404/422, 마지막 200.

---

## 6. 화면 눈으로 확인 (P7·P7-1)

| URL | 확인 |
|---|---|
| `/substances?q=황산` | 1건, `matched_on` 이 왜 후보인지 말한다 (BR-101) |
| `/substances?q=7664-93-9` | CAS 완전일치 1건 |
| `/substances?q=UN1830` | 0건 + **"UN 번호·이명은 정보 없음"** (BR-109) |
| `/substances/{황산 id}` | 7항목, 결측 2 (GHS·유해위험문구), 값마다 출처 링크 |
| `/substances/{메틸에틸케톤 id}` | 7항목 전부 "정보 없음" + "7개 항목 중 …" 안내 |

마지막 줄이 중요하다 — **비어 있어도 항목을 지우지 않는다**(BR-102). 지우면
"이 물질은 보호구 정보가 없다"와 "이 화면은 보호구를 안 보여준다"를 구분할 수 없다.

---

## 7. 알려진 재현 조건

| 현상 | 원인 | 정상인가 |
|---|---|---|
| 카드 44건이 6/7 결측 | 그 물질의 MSDS 가 코퍼스에 없다 | ✅ 정직한 결측 |
| 황산 GHS 결측 | 문서 20(남해화학)이 구조화 실패, 섹션 0 | ⚠️ R-2 |
| 톨루엔 물리화학 결측 | 문서 24(한화토탈)가 구조화 실패, 섹션 0 | ⚠️ R-2 |
| 4-tert-뷰틸벤조산 7/7 결측 | BR-31a 로 섹션이 접혀 카드가 못 읽는다 | ⚠️ 요약 5절 |
| 메틸 에틸 케톤 7/7 결측 | 출처 레코드에 응급조치가 비어 있다 | ✅ 정직한 결측 |
