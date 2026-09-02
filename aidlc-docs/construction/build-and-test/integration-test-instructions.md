# Integration Test Instructions — safeenv

**작성일**: 2026-08-20
**대상**: 유닛 `u1-ingestion-index`

> u1 은 단일 유닛이므로 "유닛 간 통합"이 아니라 **애플리케이션과 실제 인프라
> (PostgreSQL + pgvector, Redis, 컨테이너 토폴로지) 사이의 통합**을 검증합니다.

---

## 1. 환경 준비

```bash
cp .env.example .env          # POSTGRES_PASSWORD 채우기
mkdir -p data/originals logs backups
docker compose up -d
docker compose ps             # 5개 서비스 상태 확인
```

`migrate` 는 종료된 상태(`Exited (0)`)가 정상입니다 — 일회성 서비스입니다.

---

## 2. 시나리오

### I-1. 기동과 헬스체크 (NFR-29, FR-43)

```bash
curl -s http://127.0.0.1:8300/healthz
```

**기대**: `{"app":"ok","db":"ok","queue":"ok","worker":"ok"}` / HTTP 200

`worker` 가 `down` 이면 하트비트가 `WORKER_STALE_THRESHOLD`(120초)를 넘긴 것입니다.
`docker compose logs worker` 로 확인하십시오.

**부분 실패 확인**: `docker compose stop worker` 후 2분 뒤 다시 호출하면
`worker: down` 과 **HTTP 503** 이 나와야 합니다. 단일 boolean 이 아닌 이유가 이것입니다.

---

### I-2. 마이그레이션 적용 (ID-10)

```bash
docker compose logs migrate
docker compose exec postgres psql -U safeenv -d safeenv -c "\dt"
```

**기대**: 13개 테이블
`source` `substance` `substance_synonym` `document` `extracted_text`
`document_section` `chunk` `chunk_embedding` `document_substance`
`job` `job_item` `policy_check` `worker_heartbeat`

```bash
docker compose exec postgres psql -U safeenv -d safeenv -c "\di chunk*"
```

**기대**: `ix_chunk_fts`(GIN), `ix_chunk_meta_cas`, `ix_chunk_meta_un`,
`ix_chunk_meta_doc_type`, `ix_chunk_embedding_hnsw`

**기동 순서 확인**: `migrate` 의 완료 시각이 `app`·`worker` 시작 시각보다 앞서야 합니다.

---

### I-3. 선반영 스키마 확인 (DD-21)

u1 이 사용하지 않는 컬럼이 **지금** 존재하는지 확인합니다. 나중에 추가하면
수십만 청크에 대한 `ALTER TABLE` 과 전체 재색인이 발생합니다.

```bash
docker compose exec postgres psql -U safeenv -d safeenv -c "\d chunk" | grep owner_id
docker compose exec postgres psql -U safeenv -d safeenv -c "\d substance_synonym"
```

**기대**: `chunk.owner_id` 존재(nullable), `substance_synonym` 테이블 존재

---

### I-4. 소스 카탈로그 동기화 (FR-1~5, BR-02, BR-03)

```bash
docker compose exec app python -m app.cli sources
```

**기대 출력 형태**
```
ncis_substance  msds      policy=unknown  key=MISSING:NCIS_API_KEY
law_api         law       policy=unknown  key=MISSING:LAW_API_KEY
incident_data   incident  policy=unknown  key=MISSING:INCIDENT_API_KEY
msds_pdf        msds      policy=unknown  key=-
```

**검증 포인트**: 인증키가 없어도 **앱은 정상 동작**하고 소스별 상태만 보고합니다 (BR-02).

---

### I-5. 인증키 없는 소스의 수집 거부 (BR-02)

```bash
curl -s -X POST http://127.0.0.1:8300/api/sources/ncis_substance/ingest \
     -H "Content-Type: application/json" -d '{}'
```

**기대**: HTTP **409**, `detail` 에 `인증키 미설정: NCIS_API_KEY ...`

```bash
docker compose exec postgres psql -U safeenv -d safeenv -c "SELECT count(*) FROM job;"
```

**기대**: **작업이 생성되지 않음.** 실패할 수밖에 없는 작업을 남기지 않는 것이 의도입니다.

---

### I-6. 정책 검사 기록 (FR-5, CON-3)

```bash
docker compose exec postgres psql -U safeenv -d safeenv \
  -c "SELECT url, decision, left(reason,60) FROM policy_check ORDER BY checked_at DESC LIMIT 5;"
```

**기대**: 수집을 시도한 모든 소스에 대해 판정 행이 존재.
`blocked` 인 소스는 **수집 시도 기록이 없고 차단 기록만** 있어야 합니다.

---

### I-7. 색인 파이프라인 종단 검증 (FR-9~12)

인증키 없이 파이프라인을 검증하려면 MSDS 매니페스트에 공개 PDF URL 을 넣습니다.

```bash
# config/msds_manifest.json 에 documents 항목 추가 후
docker compose exec app python -m app.cli ingest --source msds_pdf
docker compose exec app python -m app.cli stats
```

**기대**
```
documents: N
chunks: M   (M > N)
embedding_model: BAAI/bge-m3   또는   deterministic-hash-1024
```

`deterministic-hash-*` 로 나오면 모델이 아직 준비되지 않은 것이며,
**벡터 검색 결과가 의미를 갖지 않습니다.**

---

### I-8. 청크 오프셋 무결성 (BR-30) — 인용의 근간

```sql
SELECT c.id
FROM chunk c
JOIN extracted_text e ON e.document_id = c.document_id
WHERE substring(e.text FROM c.start_offset + 1 FOR c.end_offset - c.start_offset) <> c.text
LIMIT 5;
```

**기대**: **0행.**
한 행이라도 나오면 u2 의 모든 인용 스니펫이 잘못된 구간을 가리키게 됩니다.

---

### I-9. 식별자 정확 매칭 (FR-12, BR-38)

```sql
SELECT count(*) FROM chunk WHERE meta->>'cas_number' = '7664-93-9';
EXPLAIN SELECT id FROM chunk WHERE meta->>'cas_number' = '7664-93-9';
```

**기대**: `ix_chunk_meta_cas` 인덱스 스캔 사용.
전문검색 토크나이저가 `7664-93-9` 를 분해하지 않는지 확인하는 것이 목적입니다.

---

### I-10. 부분 실패와 재개 (FR-8, BR-40~45)

매니페스트에 **유효한 PDF 2건 + 깨진 URL 1건**을 넣고 실행합니다.

```bash
docker compose exec app python -m app.cli ingest --source msds_pdf
```

**기대**
- 종료 상태 `partial`, 종료 코드 **0** (일부 성공은 성공)
- `/admin/jobs/{id}` 화면에서 실패 항목의 `failure_kind`·사유·시도 횟수 확인 가능
- 같은 명령 재실행 시 성공 항목은 `skipped`(변경 없음), 실패 항목만 재시도 (BR-45)

---

### I-11. 멱등 재색인 (FR-13, BR-54)

```bash
docker compose exec app python -m app.cli stats          # chunks = M
docker compose exec app python -m app.cli reindex --scope all
docker compose exec app python -m app.cli stats          # chunks = M (동일해야 함)
```

**기대**: 청크 수가 **변하지 않음**. 늘어나면 삭제-후-삽입이 아니라 중복 삽입입니다.

---

### I-12. 볼륨 영속화 (NFR-31)

```bash
docker compose down          # -v 없이
docker compose up -d
docker compose exec app python -m app.cli stats
```

**기대**: 문서·청크 수가 보존됨.

---

### I-13. 백업·복원 (ID-9)

```bash
./scripts/backup.sh
docker compose down -v
docker compose up -d
./scripts/restore.sh ./backups/safeenv-<timestamp>.dump
docker compose exec app python -m app.cli stats
```

**기대**: 복원 후 문서·청크 수가 백업 시점과 일치.

---

## 3. 정리

```bash
docker compose down          # 데이터 보존
docker compose down -v       # ⚠️ 볼륨까지 삭제 — 백업 먼저
```

---

## 4. 현재 상태

**I-1 ~ I-13 중 실제로 실행 가능한 범위는 인프라 기동 여부에 달려 있습니다.**
실행 결과는 `build-and-test-summary.md` §3 에 기록되어 있습니다.
공공 API 인증키가 필요한 시나리오(I-7 의 API 소스 부분)는 **R-1 로 미해소** 상태입니다.
