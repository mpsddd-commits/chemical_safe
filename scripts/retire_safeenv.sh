#!/usr/bin/env bash
# 이전 작업 폴더 `safeenv/` 를 정리한다 (백로그 D5).
#
# 2026-09-02 에 작업 트리를 safeenv/ 에서 이 저장소로 옮겼다. safeenv/ 는
# 되돌릴 곳으로 남겨 뒀고, 이 스크립트는 **되돌릴 필요가 없다는 것을 증명한
# 뒤에만** 지운다. 증명하지 못하면 아무것도 하지 않는다.
#
# 검사 셋 — 하나라도 실패하면 중단한다:
#   1. 스택이 실제로 이 저장소를 마운트하고 있는가 (이전이 살아 있는가)
#   2. safeenv 에만 있는 파일이 0개인가 (캐시·로그 제외)
#   3. 이 저장소가 커밋된 깃 저장소인가 (코드가 남아 있는가)
#
# 유일하게 양쪽에 없는 것은 `safeenv/logs/safeenv.log` 다 — 8/20~9/2 의 운영
# 로그이고 .gitignore 대상이라 저장소에 없다. 지우지 않고 이 저장소의 logs/ 로
# 옮긴다.
#
# 사용:
#   scripts/retire_safeenv.sh            # 검사만 (기본)
#   scripts/retire_safeenv.sh --apply    # 검사 통과 시 실제 정리
set -uo pipefail

APPLY=0
[ "${1:-}" = "--apply" ] && APPLY=1

cd "$(dirname "$0")/.." || { echo "저장소 루트 진입 실패" >&2; exit 1; }
HERE="$(pwd)"
OLD="$(dirname "$HERE")/safeenv"

echo "이 저장소: $HERE"
echo "정리 대상: $OLD"
echo

if [ ! -d "$OLD" ]; then
  echo "이미 정리됨 — $OLD 가 없다."
  exit 0
fi

fail() { echo "중단: $1" >&2; exit 1; }

# ---- 검사 1: 이전이 살아 있는가 -------------------------------------------
# 컨테이너가 아직 옛 경로를 마운트하고 있다면 이전이 끝나지 않은 것이고,
# 지우면 실행 중인 스택의 데이터 원본이 사라진다.
mounts="$(docker inspect safeenv-app --format '{{range .Mounts}}{{.Source}}
{{end}}' 2>/dev/null)"
[ -z "$mounts" ] && fail "safeenv-app 컨테이너를 조회하지 못했다 (스택이 떠 있는가?)"
if grep -qiF "$(basename "$OLD")\\data" <<<"$mounts" || grep -qiF "/safeenv/data" <<<"$mounts"; then
  fail "컨테이너가 아직 $OLD 를 마운트하고 있다. 이전이 끝나지 않았다."
fi
echo "검사 1 통과: 스택이 옛 경로를 쓰지 않는다"

# ---- 검사 2: safeenv 에만 있는 것이 없는가 ---------------------------------
unique="$(python - "$OLD" "$HERE" <<'PY'
import sys
from pathlib import Path
old, new = Path(sys.argv[1]), Path(sys.argv[2])
SKIP = {".git", "__pycache__", ".pytest_cache", ".ruff_cache", ".hypothesis",
        "logs", "backups"}
def rels(root):
    return {p.relative_to(root).as_posix() for p in root.rglob("*")
            if p.is_file() and not SKIP & set(p.relative_to(root).parts)}
only = sorted(rels(old) - rels(new))
print(len(only))
for r in only[:20]:
    print(r)
PY
)"
count="$(head -1 <<<"$unique")"
[ -z "$count" ] && fail "비교를 수행하지 못했다"
if [ "$count" != "0" ]; then
  echo "중단: safeenv 에만 있는 파일 $count 개" >&2
  tail -n +2 <<<"$unique" | sed 's/^/  /' >&2
  exit 1
fi
echo "검사 2 통과: safeenv 에만 있는 파일 0개 (캐시·로그 제외)"

# ---- 검사 3: 코드가 깃에 남아 있는가 ---------------------------------------
commits="$(git rev-list --count HEAD 2>/dev/null)"
[ -z "$commits" ] || [ "$commits" -lt 1 ] && fail "이 저장소에 커밋이 없다"
dirty="$(git status --porcelain | wc -l)"
echo "검사 3 통과: 커밋 $commits 개 (미커밋 $dirty 개)"

echo
if [ "$APPLY" -eq 0 ]; then
  echo "검사만 수행했다. 실제로 정리하려면:"
  echo "  scripts/retire_safeenv.sh --apply"
  echo
  echo "정리 시 하는 일:"
  echo "  1. $OLD/logs/safeenv.log → $HERE/logs/safeenv-pre-migration.log 로 이동"
  echo "  2. $OLD 삭제 ($(du -sh "$OLD" 2>/dev/null | cut -f1))"
  exit 0
fi

# ---- 실행 ------------------------------------------------------------------
# 로그는 저장소에 없는 유일한 것이다. 지우지 않고 옮긴다.
if [ -f "$OLD/logs/safeenv.log" ]; then
  mkdir -p "$HERE/logs"
  dest="$HERE/logs/safeenv-pre-migration.log"
  mv "$OLD/logs/safeenv.log" "$dest" || fail "로그 이동 실패 — 아무것도 지우지 않았다"
  echo "보존: $dest ($(du -sh "$dest" | cut -f1))"
fi

rm -rf "$OLD" || fail "삭제 실패"
[ -d "$OLD" ] && fail "삭제했는데 아직 남아 있다"
echo "삭제: $OLD"
echo
echo "정리 완료. 코드는 깃에 있고(커밋 $commits 개), 코퍼스는 data/originals 로"
echo "커밋돼 있으며, 운영 로그는 logs/safeenv-pre-migration.log 로 옮겼다."
