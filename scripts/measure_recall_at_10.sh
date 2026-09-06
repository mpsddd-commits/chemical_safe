#!/usr/bin/env bash
# C4 — Recall@10 이 잴 수 있는 값인지 실측한다.
#
# 결함 49: `FINAL_TOP_K=5` 라 후보 목록이 5건이고, 5건짜리 목록의 Recall@10 은
# 이름만 다른 Recall@5 다. `reporter.aggregate()` 가 depth<10 이면 None 을
# 내보내므로 이 지표는 영구히 `--` 로 남아 있다.
#
# 그런데 깊이 10의 순위 정보는 **이미 파이프라인 안에 있다** — 융합이 20건을
# 만들고(`FUSION_TOP_K=20`) 그중 5건만 하류로 간다. 그래서 이 측정은 "더 검색"이
# 아니라 "이미 계산된 것을 더 관측"하는 일이다.
#
# **코드를 고치지 않는다.** `final_top_k` 는 Settings 필드라 환경변수로 바뀌고
# (`FINAL_TOP_K=10`), 빌드 지문은 파일을 해싱하므로 env 변경으로는 바뀌지 않는다.
# 되돌릴 코드가 없다는 것이 이 스크립트의 안전성 전부다 — 임시 패치를 붙였다
# 떼는 방식이었다면 실패 시 작업 트리가 더러워지고 승격이 막혔을 것이다.
#
# LLM 을 부르지 않는다(`--retrieval-only`, 0콜). 몇 번을 돌려도 할당량이 줄지 않는다.
#
# 사용:
#   scripts/measure_recall_at_10.sh            # 기본 비교: 5 vs 10
#   scripts/measure_recall_at_10.sh 5 10 20    # 임의 깊이들
#
# 종료코드
#   0  측정 완료
#   1  인프라 문제 (컨테이너·DB)
#   3  배포 정체 불일치 — 컨테이너가 작업 트리와 다른 코드다(결함 58)
set -uo pipefail

cd "$(dirname "$0")/.." || { echo "저장소 루트 진입 실패" >&2; exit 1; }

DEPTHS=("$@")
[ ${#DEPTHS[@]} -eq 0 ] && DEPTHS=(5 10)

psql_q() {
  docker compose exec -T postgres psql -U safeenv -d safeenv -A -t -c "$1" 2>/dev/null \
    | tr -d '[:space:]'
}

# ---- 배포 정체 ------------------------------------------------------------
container_build="$(docker compose exec -T app python -c \
  'from app.core.build import build_id; print(build_id())' 2>/dev/null | tr -d '[:space:]')"
tree_build="$(python -c \
  'import sys; sys.path.insert(0,"."); from app.core.build import build_id; print(build_id())' \
  2>/dev/null | tr -d '[:space:]')"
[ -z "$container_build" ] && { echo "실패: 컨테이너 조회 불가" >&2; exit 1; }
if [ "$container_build" != "$tree_build" ]; then
  echo "실패: 컨테이너와 작업 트리의 코드가 다르다 (결함 58)." >&2
  echo "      docker compose up -d --build app worker" >&2
  exit 3
fi
echo "지문 $container_build (컨테이너 == 작업 트리)"
echo

# ---- 측정 ------------------------------------------------------------------
# 각 깊이마다 별도 실행이 남는다. config 스냅샷에 final_top_k 가 들어가므로
# 기준선과는 `incomparable` 로 나오고, 그것이 옳은 동작이다 — 다른 설정으로
# 잰 두 수를 빼지 않는다.
printf "%-6s %-10s %-10s %-10s %-8s\n" 깊이 Recall@5 Recall@10 MRR 실행
printf "%-6s %-10s %-10s %-10s %-8s\n" ---- -------- --------- --- ----
for depth in "${DEPTHS[@]}"; do
  if ! [[ "$depth" =~ ^[0-9]+$ ]] || [ "$depth" -lt 1 ]; then
    echo "건너뜀: 깊이 '$depth' 는 1 이상의 정수가 아니다" >&2
    continue
  fi
  log="$(mktemp -t recall.XXXXXX.log)"
  docker compose exec -T -e FINAL_TOP_K="$depth" app \
    python -m app.cli evaluate --retrieval-only >"$log" 2>&1
  rid="$(psql_q "select id from evaluation_run where mode='retrieval_only' order by id desc limit 1")"
  if [ -z "$rid" ]; then
    echo "실패: 실행 id 조회 불가 — 인프라 문제. 로그: $log" >&2
    exit 1
  fi
  # 이력에 표시를 남긴다. `evaluate --list` 를 읽는 사람이 측정용 실행과 진짜
  # 실행을 구별하지 못하면 승격할 것을 고르는 일이 추측이 된다 — 통합 테스트가
  # 자기 실행에 `integration-test` 를 다는 것과 같은 이유다(9/2 에 103/141 이
  # 라벨 없이 섞여 있던 것을 고쳤다).
  psql_q "update evaluation_run set note='measure-recall FINAL_TOP_K=$depth' where id=$rid" >/dev/null
  r5="$(psql_q "select coalesce(metrics->'retrieval'->>'recall_at_5','--') from evaluation_run where id=$rid")"
  r10="$(psql_q "select coalesce(metrics->'retrieval'->>'recall_at_10','--') from evaluation_run where id=$rid")"
  mrr="$(psql_q "select coalesce(metrics->'retrieval'->>'mrr','--') from evaluation_run where id=$rid")"
  actual="$(psql_q "select max(jsonb_array_length(retrieved)) from evaluation_item where run_id=$rid")"
  printf "%-6s %-10s %-10s %-10s %-8s (실측 깊이 %s)\n" "$depth" "$r5" "$r10" "$mrr" "$rid" "${actual:-?}"
done

echo
echo "읽는 법:"
echo "  Recall@10 이 Recall@5 와 **같으면** 이 지표는 깊이를 늘려도 진단하지"
echo "  못한다 — 결함 49 의 기록대로 변할 수 없는 비교다."
echo "  **다르면** 반대다. 5건 밖에 정답 근거가 있다는 뜻이고, 그때는"
echo "  FINAL_TOP_K 를 올릴지가 실제 선택지가 된다(생성기가 보는 근거도"
echo "  같이 바뀐다는 대가와 함께)."
echo
echo "이 측정들은 기준선을 건드리지 않았다. 승격하지 않았고, config 가 달라"
echo "기준선 대비 incomparable 로 남는다."
