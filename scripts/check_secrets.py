"""커밋될 파일에 `.env` 의 실제 비밀값이 들어갔는지 검사한다.

검사 대상은 추적 파일 + 추적되지 않았지만 `.gitignore` 에 걸리지 않는 파일,
즉 `git add -A` 가 올릴 파일 전부다. 출력은 둘을 나눠 센다.

푸시 전 마지막 관문이다. 종료코드 0 이면 깨끗, 그 외는 푸시하지 말 것.

**검사 대상이 0개면 실패로 간주한다.** 2026-09-02 에 이 검사의 첫 판이
Git Bash 경로(`/c/...`)를 Python 에 그대로 넘겨 **파일 0개를 검사하고
"유출 0건"** 을 보고했다. 통과처럼 보이는 빈 검사였고, 그대로 믿었으면
아무것도 확인하지 않은 채 안전하다고 말할 뻔했다. 비어 있음은 통과가 아니다.

사용:
    python scripts/check_secrets.py          # 저장소 루트에서
    python scripts/check_secrets.py --quiet  # 실패할 때만 출력
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# 값이 노출되면 실제 피해가 있는 것만. POSTGRES_HOST("postgres")나
# TZ("Asia/Seoul") 같은 설정값은 소스에 당연히 있고, 넣으면 매번 오탐이 나서
# 검사 자체를 신뢰하지 않게 된다.
SECRET_KEYS = {
    "GEMINI_API_KEY",
    "ANTHROPIC_API_KEY",
    "JWT_SECRET",
    "POSTGRES_PASSWORD",
    "LAW_API_KEY",
    "NCIS_API_KEY",
    "INCIDENT_API_KEY",
}

MIN_SECRET_LEN = 8


def load_secrets(env_path: Path) -> dict[str, str]:
    if not env_path.is_file():
        return {}
    found: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key in SECRET_KEYS and len(value) >= MIN_SECRET_LEN:
            found[key] = value
    return found


def _git_paths(root: Path, *args: str) -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z", *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout
    return [root / name for name in out.split("\0") if name]


def tracked_files(root: Path) -> list[Path]:
    return _git_paths(root)


def untracked_files(root: Path) -> list[Path]:
    """아직 `git add` 하지 않았지만 `.gitignore` 에 걸리지 않는 파일.

    추적 파일만 보던 때에는 새 파일이 검사에서 빠졌다. 2026-09-08 에는 MSDS PDF
    15건이 미추적이라 409개만 보고 통과했고, 2026-09-13 에는 스캔을 `git add`
    보다 먼저 돌려 새 파일 3개가 빠진 채 푸시됐다. 순서를 조심하는 것으로는
    막히지 않았으니, 검사 대상을 `git add -A` 가 올릴 파일에 맞춘다.

    `--exclude-standard` 가 `.gitignore` 를 적용한다. `.env`·`logs/`·`backups/`
    는 커밋되지 않으니 볼 이유가 없고, `.env` 에는 진짜 비밀이 있어 넣으면
    매번 실패한다.
    """
    return _git_paths(root, "--others", "--exclude-standard")


def main(argv: list[str] | None = None, root: Path | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    quiet = "--quiet" in argv
    root = root or Path(__file__).resolve().parent.parent

    secrets = load_secrets(root / ".env")
    if not secrets:
        # `.env` 가 없는 환경(CI, 새 클론)에서는 대조할 값이 없다. 검사할 것이
        # 없는 것과 검사해서 깨끗한 것은 다르므로, 통과가 아니라 건너뜀이다.
        print("건너뜀: .env 에서 대조할 비밀값을 찾지 못했다 (CI·새 클론이면 정상)")
        return 0

    tracked = [p for p in tracked_files(root) if p.is_file()]
    untracked = [p for p in untracked_files(root) if p.is_file()]
    files = tracked + untracked
    if not files:
        print("실패: 검사 대상 0개 — 검사가 아무것도 보지 않았다", file=sys.stderr)
        return 2

    hits: list[str] = []
    for path in files:
        try:
            text = path.read_bytes().decode("utf-8", errors="ignore")
        except OSError:
            continue
        for key, value in secrets.items():
            if value in text:
                hits.append(f"{path.relative_to(root).as_posix()} :: {key}")

    if hits:
        print(
            f"실패: 비밀값 {len(hits)}건이 커밋 대상 파일에 있다 — 푸시하지 말 것 "
            f"(추적 {len(tracked)}개 + 미추적 {len(untracked)}개 검사)",
            file=sys.stderr,
        )
        for hit in sorted(set(hits)):
            print(f"  {hit}", file=sys.stderr)
        return 1

    if not quiet:
        print(
            f"통과: 파일 {len(files)}개 (추적 {len(tracked)} + 미추적 {len(untracked)}) "
            f"× 비밀값 {len(secrets)}종 → 0건"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
