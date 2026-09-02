"""Is the code the containers run the code in this working tree? (defect 58)

2026-08-30: the image was rebuilt, the containers were not recreated, and
`app` and `worker` served five-hour-old code for an evening. `DocType.SUBSTANCE`
did not exist in it, so the type-spread rule the `doc_type` split was built for
never ran and an evaluation measured 0.667 where the same corpus measured
0.700. Unit tests (629) and integration tests (53) were green the whole time -
they run the working tree, and the working tree was fine.

This is the check that closes that gap, and it belongs in the integration suite
rather than in a script because a script is something you remember to run.
Nothing in this project gets approved with a red integration run.

It reads and compares. It does not restart anything: a test that fixes the
deployment would hide how often the deployment is wrong, and defect 48 and 53
were both tests quietly changing what they measured.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from app.core.build import build_id

pytestmark = pytest.mark.integration

# `reranker` is a profile service and normally down (BR-71); it is not checked
# because a stopped container cannot serve stale code.
SERVICES = ("app", "worker")

_ALIVE = "print('alive')"
_PROBE = "from app.core.build import build_id; print(build_id())"

# A container old enough to predate `app/core/build.py` cannot answer the probe
# at all. That is staleness, not absence, and the first version of this test
# reported it as a skip - three green skips against the exact deployment the
# check was written for. Defect shape 3: reading the wrong signal.
STALE_BEYOND_PROBE = "probe-missing"


def _compose(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


def _deployed_build(service: str) -> str | None:
    """The container's build id, `STALE_BEYOND_PROBE`, or None when it is down.

    Liveness is established with a probe that needs no application code, so
    "the container is not running" and "the running code is too old to answer"
    stay separate answers.
    """
    if _compose("exec", "-T", service, "python", "-c", _ALIVE).returncode != 0:
        return None
    result = _compose("exec", "-T", service, "python", "-c", _PROBE)
    if result.returncode != 0 or not result.stdout.strip():
        return STALE_BEYOND_PROBE
    return result.stdout.strip().splitlines()[-1].strip()


@pytest.fixture(scope="module")
def deployed() -> dict[str, str]:
    if shutil.which("docker") is None:
        pytest.skip("docker 없음 - 배포 최신성은 확인할 수 없다")
    builds = {}
    for service in SERVICES:
        found = _deployed_build(service)
        if found is None:
            pytest.skip(f"{service} 컨테이너가 떠 있지 않다 - 확인할 배포가 없다")
        builds[service] = found
    return builds


def _explain(service: str, deployed_build: str) -> str:
    running = (
        "식별 코드 자체가 없습니다 (이 검사보다 오래된 이미지)"
        if deployed_build == STALE_BEYOND_PROBE
        else deployed_build
    )
    return (
        f"{service} 컨테이너는 {running}, 작업 트리는 {build_id()} 입니다.\n"
        "재빌드만 하고 컨테이너를 재생성하지 않으면 이 상태가 됩니다 (결함 58):\n"
        "  docker compose up -d --build app worker"
    )


class TestTheContainersRunThisCode:
    def test_app_matches_the_working_tree(self, deployed):
        assert deployed["app"] == build_id(), _explain("app", deployed["app"])

    def test_worker_matches_the_working_tree(self, deployed):
        assert deployed["worker"] == build_id(), _explain("worker", deployed["worker"])

    def test_app_and_worker_run_the_same_code(self, deployed):
        """One image serves both (UD-3), so a split here means one was recreated
        and the other was not - which is how half a stack ends up stale."""
        assert deployed["app"] == deployed["worker"]
