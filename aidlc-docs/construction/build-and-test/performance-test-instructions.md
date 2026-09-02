# Performance Test Instructions — safeenv

**작성일**: 2026-08-20
**대상**: 유닛 `u1-ingestion-index`

> u1 에는 사용자 대면 질의 경로가 없습니다. 따라서 부하 테스트가 아니라
> **색인 처리량(NFR-4)** 과 **규모에서의 인덱스 동작(NFR-9)** 이 검증 대상입니다.
> 응답 지연(NFR-1, NFR-2)은 검색 경로가 생기는 u2 에서 측정합니다.

---

## 1. 성능 요구사항 (u1 소관)

| NFR | 목표 | 측정 방법 |
|---|---|---|
| **NFR-4** | 물질 1,000종 초기 색인 **8시간 이내** | 전체 수집 실행 시간 |
| **NFR-9** | 청크 **10만 건** 규모에서 NFR-1~3 성능 유지 | 인덱스 스캔 계획 확인 |
| **NFR-10** | 워커 수평 확장 가능 | `--scale worker=N` |

u2 이후 측정: NFR-1(첫 토큰 5초 / 전체 20초), NFR-2(검색 2.5초), NFR-3(카드 1초)

---

## 2. 색인 처리량 측정 (NFR-4)

### 2.1 구간별 소요 확인

파이프라인 각 단계가 `duration_ms` 를 로깅합니다 (BR-58).

```bash
docker compose logs worker | grep pipeline_stage_done | tail -50
```

```bash
# 단계별 평균 소요 (ms)
docker compose logs worker \
  | grep pipeline_stage_done \
  | python -c "
import sys, json, collections
acc = collections.defaultdict(list)
for line in sys.stdin:
    try: rec = json.loads(line.split(' ', 1)[-1])
    except Exception: continue
    if 'stage' in rec and 'duration_ms' in rec:
        acc[rec['stage']].append(rec['duration_ms'])
for stage, values in acc.items():
    values.sort()
    p95 = values[int(len(values)*0.95)] if values else 0
    print(f'{stage:10} n={len(values):5} avg={sum(values)/len(values):8.1f}ms p95={p95:8.1f}ms')
"
```

**예상 병목**: `embed` 단계. 임베딩이 색인 시간의 대부분을 차지합니다 (위험 R-3).

### 2.2 처리량 환산

```
목표: 물질 1,000종 / 8시간 = 시간당 125종
문서 1건당 청크 약 16개(MSDS 16섹션) 가정 -> 청크 약 16,000개
```

배치 32 기준으로 임베딩 호출 500회. 이 값이 8시간을 크게 밑돌아야 여유가 있습니다.

### 2.3 튜닝 지점

| 파라미터 | 기본 | 영향 |
|---|---|---|
| `EMBED_BATCH_SIZE` | 32 | 크게 하면 처리량↑ 메모리↑ (worker 4G 한도) |
| `WORKER_COUNT` (`--scale`) | 1 | 병렬 문서 처리 |
| `REQUEST_INTERVAL_MS` | 500 | 수집 단계 하한. 공공 API 예의상 낮추지 말 것 (BR-06) |

---

## 3. 워커 확장 검증 (NFR-10)

```bash
docker compose up -d --scale worker=2
docker compose ps | grep worker
docker compose logs worker | grep worker_started
```

**기대**: 워커 2개가 각기 다른 `worker_id` 로 기동하고 큐를 분담.

**핵심 확인**: 같은 `job_item` 이 두 워커에서 중복 처리되지 않아야 합니다.

```sql
SELECT ref_key, count(*) FROM job_item GROUP BY ref_key HAVING count(*) > 1;
```
**기대**: 0행 (`uq_job_item_ref` 제약이 보장)

**메모리 주의**: 워커 1개당 4G 한도이므로 `--scale worker=2` 는 8G 를 요구합니다.
호스트 할당 메모리를 먼저 확인하십시오.

---

## 4. 인덱스 동작 확인 (NFR-9)

규모가 작을 때 PostgreSQL 은 순차 스캔을 선택할 수 있습니다.
**실제 데이터가 쌓인 뒤** 확인해야 의미가 있습니다.

```sql
ANALYZE chunk;

-- CAS 정확 매칭이 표현식 인덱스를 타는가 (BR-38)
EXPLAIN (ANALYZE, BUFFERS)
SELECT id FROM chunk WHERE meta->>'cas_number' = '7664-93-9';

-- 전문검색이 GIN 을 타는가
EXPLAIN (ANALYZE, BUFFERS)
SELECT id FROM chunk
WHERE to_tsvector('simple', text) @@ plainto_tsquery('simple', '보호구');

-- 벡터 검색이 HNSW 를 타는가
EXPLAIN (ANALYZE, BUFFERS)
SELECT chunk_id FROM chunk_embedding
ORDER BY embedding <=> '[0,0, ...]'::vector LIMIT 10;
```

**기대**: 각각 `ix_chunk_meta_cas`, `ix_chunk_fts`, `ix_chunk_embedding_hnsw` 사용.

**HNSW 주의**: 인덱스를 **빈 상태로 생성**했습니다. 대량 적재 후
`REINDEX INDEX ix_chunk_embedding_hnsw` 로 재구축하면 품질이 개선될 수 있습니다.
u2 의 검색 품질 측정 시 확인 대상입니다.

---

## 5. 리소스 관측

```bash
docker stats --no-stream
```

| 컨테이너 | 한도 | 확인 사항 |
|---|---|---|
| `worker` | 4G | 임베딩 중 피크. 한도 근접 시 `EMBED_BATCH_SIZE` 하향 |
| `app` | 2G | u1 에서는 여유. **u2 리랭커 도입 시 재측정 필요** |
| `postgres` | 2G | 대량 색인 중 `shared_buffers` 압박 여부 |
| `redis` | 512M | 큐 길이에 비례 |

---

## 6. 현재 미측정 (사유 명시)

| 항목 | 사유 |
|---|---|
| **NFR-4 실측** | 공공 API 인증키 미보유(R-1)로 1,000종 수집 불가 |
| **NFR-9 실측** | 청크 10만 건 규모 데이터 미확보 |
| 임베딩 실제 속도 | 모델 다운로드·실행 필요 |
| 워커 스케일 실측 | 메모리 8G 요구 |

**이 항목들은 인증키 확보 후 재측정 대상입니다.**
측정 절차는 위에 완비되어 있으므로 데이터만 갖춰지면 바로 실행 가능합니다.
