#!/usr/bin/env bash
# 중단된 `--full` 평가를 이어서 완주시키고, 완주하면 기준선으로 승격한다.
#
# 시간에 쫓기는 기계적인 일이라 스크립트로 남긴다. 심판 할당량은 하루 20콜이고
# 리셋 구간이 13:40~16:10 사이 어딘가로 실측돼 있어(정확한 시각 불명), 창을
# 놓치면 하루를 잃는다.
#
# 사용:
#   scripts/resume_and_promote.sh 387          # 재개 + 완주 시 승격
#   scripts/resume_and_promote.sh 387 --no-promote
#   scripts/resume_and_promote.sh new          # 새 --full 실행을 시작해 완주까지
#   scripts/resume_and_promote.sh new --no-promote
#
# `new` 는 측정이 목적일 때 쓴다 — 수정이 지표를 움직였는지 확인하는 경우처럼.
# 그때는 대개 `--no-promote` 가 맞다: 승격은 결과를 보고 사람이 정한다(BR-129).
#
# 종료코드
#   0  완주(+승격). 또는 할당량 소진으로 오늘 몫을 다 씀 — 실패가 아니다(BR-118)
#   1  인프라 문제. 로그를 볼 것
#   2  사용법 오류
#   3  배포 정체 불일치 — 컨테이너가 작업 트리와 다른 코드다(결함 58)
set -uo pipefail

RUN_ID="${1:-}"
PROMOTE=1
[ "${2:-}" = "--no-promote" ] && PROMOTE=0
if [ "$RUN_ID" != "new" ] && ! [[ "$RUN_ID" =~ ^[0-9]+$ ]]; then
  echo "사용법: $0 <RUN_ID|new> [--no-promote]" >&2
  exit 2
fi

# 저장소 루트로 고정한다. 2026-09-02 에 cd 를 빠뜨려 옛 경로에서 스택을 기동한
# 적이 있다 — 명령이 무엇을 했다고 말하는 것과 실제로 한 것은 다르다.
cd "$(dirname "$0")/.." || { echo "저장소 루트 진입 실패" >&2; exit 1; }

LOG="$(mktemp -t resume387.XXXXXX.log)"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-4}"
WAIT_SECONDS="${WAIT_SECONDS:-1800}"

psql_q() {
  docker compose exec -T postgres psql -U safeenv -d safeenv -A -t -c "$1" 2>/dev/null \
    | tr -d '[:space:]'
}

echo "저장소: $(pwd)"
echo "로그:   $LOG"

# ---- 배포 정체 확인 -------------------------------------------------------
# 실행은 특정 코드로 측정 중이다. 컨테이너가 다른 코드면 이어붙이는 것 자체가
# 두 코드의 결과를 한 실행에 섞는 일이고, 승격도 게이트에서 막힌다.
container_build="$(docker compose exec -T app python -c \
  'from app.core.build import build_id; print(build_id())' 2>/dev/null | tr -d '[:space:]')"
tree_build="$(python -c \
  'import sys; sys.path.insert(0,"."); from app.core.build import build_id; print(build_id())' \
  2>/dev/null | tr -d '[:space:]')"
if [ "$RUN_ID" = "new" ]; then
  # 새 실행은 지금 배포된 코드로 측정된다. 아래 지문 검사는 컨테이너와 작업
  # 트리가 같은지만 보면 되고, 실행 지문 비교는 실행이 생긴 뒤에 한다.
  echo "새 --full 실행을 시작한다"
  docker compose exec -T app python -m app.cli evaluate --full >"$LOG" 2>&1
  RUN_ID="$(psql_q "select id from evaluation_run where mode='full' order by id desc limit 1")"
  if ! [[ "$RUN_ID" =~ ^[0-9]+$ ]]; then
    echo "실패: 새 실행의 id 를 조회하지 못했다. 로그: $LOG" >&2
    exit 1
  fi
  echo "실행 $RUN_ID 생성"
fi
run_build="$(psql_q "select coalesce(build_id,'') from evaluation_run where id=$RUN_ID")"

if [ -z "$container_build" ] || [ -z "$tree_build" ]; then
  echo "실패: 빌드 지문을 읽지 못했다 (컨테이너가 떠 있는가?)" >&2
  exit 1
fi
echo "지문: 컨테이너 $container_build / 작업트리 $tree_build / 실행 ${run_build:-미기록}"
if [ "$container_build" != "$tree_build" ]; then
  echo "실패: 컨테이너와 작업 트리의 코드가 다르다 (결함 58)." >&2
  echo "      docker compose up -d --build app worker" >&2
  exit 3
fi
if [ -n "$run_build" ] && [ "$run_build" != "$container_build" ]; then
  echo "실패: 실행 $RUN_ID 은 코드 $run_build 로 측정 중인데 지금은 $container_build 다." >&2
  echo "      이어붙이면 서로 다른 코드의 결과가 한 실행에 섞인다." >&2
  exit 3
fi

# ---- 재개 루프 ------------------------------------------------------------
for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
  # 상태를 먼저 본다. `new` 로 시작한 실행이 곧바로 완주했는데 --resume 을
  # 부르면 "partial 만 재개할 수 있습니다" 오류가 로그에 남아, 성공한 실행이
  # 실패한 것처럼 읽힌다.
  status="$(psql_q "select status from evaluation_run where id=$RUN_ID")"
  if [ "$status" = "succeeded" ]; then
    scored="$(psql_q "select count(*) from evaluation_item where run_id=$RUN_ID and status='done'")"
    echo "시도 $attempt: 상태 succeeded / 채점 ${scored:-?}/30 (재개 불필요)"
    break
  fi

  docker compose exec -T app python -m app.cli evaluate --resume "$RUN_ID" >"$LOG" 2>&1

  status="$(psql_q "select status from evaluation_run where id=$RUN_ID")"
  scored="$(psql_q "select count(*) from evaluation_item where run_id=$RUN_ID and status='done'")"

  # 빈 값은 "할당량"이 아니라 DB 를 못 읽었다는 뜻이다. 둘을 같게 다루면
  # 인프라 장애를 조용히 재시도하게 된다 — 2026-09-02 에 저지른 실수다.
  if [ -z "$status" ]; then
    echo "실패: DB 조회 불가 — 인프라 문제. 로그: $LOG" >&2
    exit 1
  fi

  echo "시도 $attempt: 상태 $status / 채점 ${scored:-?}/30"

  case "$status" in
    succeeded) break ;;
    failed)
      echo "실패: 실행이 failed 로 끝났다. 로그: $LOG" >&2
      exit 1 ;;
    partial)
      if ! grep -aq "할당량" "$LOG"; then
        echo "실패: partial 인데 할당량 언급이 없다 — 다른 원인이다. 로그: $LOG" >&2
        exit 1
      fi
      if [ "$attempt" -lt "$MAX_ATTEMPTS" ]; then
        echo "  할당량 소진 확인 — ${WAIT_SECONDS}초 후 재시도"
        sleep "$WAIT_SECONDS"
      fi ;;
    *)
      echo "실패: 예상하지 못한 상태 '$status'. 로그: $LOG" >&2
      exit 1 ;;
  esac
done

status="$(psql_q "select status from evaluation_run where id=$RUN_ID")"
scored="$(psql_q "select count(*) from evaluation_item where run_id=$RUN_ID and status='done'")"

if [ "$status" != "succeeded" ]; then
  echo
  echo "오늘 몫 소진 — 채점 $scored/30, 상태 $status."
  echo "실패가 아니다(BR-118). 내일 같은 명령으로 이어서:"
  echo "  scripts/resume_and_promote.sh $RUN_ID"
  echo
  echo "⚠️  승격 전까지 app/ · config/ · migrations/ · prompts/ · eval/ ·"
  echo "    pyproject.toml 을 고치지 말 것 — 빌드 지문이 바뀌면 승격이 막힌다."
  exit 0
fi

echo
echo "완주: $scored/30"
grep -aE "^  (Recall@5|MRR|정답률|인용 정확도|충실도|거부 정확도|오거부율)" "$LOG" | head -8

if [ "$PROMOTE" -eq 0 ]; then
  echo "--no-promote 로 승격은 건너뛴다."
  exit 0
fi

echo
echo "승격:"
docker compose exec -T app python -m app.cli evaluate --promote "$RUN_ID" 2>&1 \
  | grep -av '"level"' | tail -3

echo
echo "기준선:"
docker compose exec -T postgres psql -U safeenv -d safeenv -A -F'|' \
  -c "select id, mode, coalesce(build_id,'미기록') build,
             metrics->'retrieval'->>'recall_at_5' r5,
             metrics->'retrieval'->>'mrr' mrr,
             metrics->'refusal'->>'accuracy' refusal
      from evaluation_run where is_baseline order by id;" 2>&1 | tail -4

echo
echo "승격 후 재현 확인 — 전 지표 +0.000 이어야 한다:"
docker compose exec -T app python -m app.cli evaluate --retrieval-only 2>&1 \
  | grep -aE "^실행|Recall@5|MRR|거부 정확도|오거부율|판정" | tail -8
