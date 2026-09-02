"""Which code is this process actually running? (defect 58)

On 2026-08-30 the image was rebuilt and the containers were not recreated.
`app` and `worker` ran five-hour-old code for an evening: `DocType.SUBSTANCE`
did not exist in it, so the type-spread rule the whole `doc_type` split was for
never ran, and an evaluation measured 0.667 where the same corpus measured
0.700. Unit tests (629) and integration tests (53) were green throughout,
because they run on the host against the working tree. **The code the tests
exercise and the code the service runs are two different things**, and nothing
in the system could tell them apart.

The fingerprint is computed from the file tree rather than read from a stamp
written at build time. A stamp is one more thing that can be stale - it would
have to be regenerated correctly on every build, and a build that forgot would
report the old identity confidently. Hashing what is actually on disk cannot
be wrong about what is actually on disk.

`EvaluationRun`'s own docstring already said a run is useless unless you can
tell what moved - "the model, the prompt, the corpus, or the code". The code
was the one thing it did not record.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

# Exactly the paths the Dockerfile COPYs into the image. Anything outside this
# set cannot make a container's behaviour differ from the working tree, and
# anything inside it can. If those COPY lines change, this tuple changes with
# them or the check quietly stops covering the difference.
TRACKED: tuple[str, ...] = (
    "app",
    "config",
    "migrations",
    "prompts",
    "eval",
    "pyproject.toml",
)

# `.dockerignore` drops these, so they are not in the image and must not be in
# the host's hash either - otherwise every local test run reports itself stale.
_IGNORED_DIRS = frozenset({"__pycache__"})
_IGNORED_SUFFIXES = (".pyc", ".pyo")

# `/app` in the container, the repository root on the host. Both hold the same
# six entries; that is what makes the two fingerprints comparable at all.
CONTAINER_ROOT = Path("/app")


def default_root() -> Path:
    """The container's `/app` when running there, else the repository root.

    `app/core/build.py` -> `app/core` -> `app` -> root.
    """
    root = Path(__file__).resolve().parents[2]
    return root


def iter_tracked_files(root: Path) -> Iterator[Path]:
    """Every file that ends up in the image, in a stable order.

    Sorted by POSIX-relative path so Windows and Linux agree. Without that the
    host and the container would hash the same bytes in a different order and
    disagree about identical code.
    """
    found: list[Path] = []
    for entry in TRACKED:
        target = root / entry
        if target.is_file():
            found.append(target)
            continue
        if not target.is_dir():
            # A missing entry is a real difference, not something to paper over:
            # it changes the hash, which is exactly what should happen.
            continue
        for path in target.rglob("*"):
            if not path.is_file():
                continue
            if _IGNORED_DIRS.intersection(path.parts):
                continue
            if path.suffix in _IGNORED_SUFFIXES:
                continue
            found.append(path)
    yield from sorted(found, key=lambda p: p.relative_to(root).as_posix())


def source_fingerprint(root: Path | None = None) -> str:
    """A sha256 over the tracked tree: relative path and raw bytes of each file.

    Raw bytes, not text. Docker copies bytes, so a line-ending change is a real
    difference between the image and the working tree and the hash should say
    so rather than normalise it away.

    The path goes into the hash alongside the content so that renaming a file
    changes the fingerprint - concatenating contents alone would not notice.
    """
    root = root or default_root()
    digest = hashlib.sha256()
    for path in iter_tracked_files(root):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


@lru_cache(maxsize=1)
def build_id() -> str:
    """This process's code identity, short form.

    Cached for the life of the process. A container's files cannot change under
    it (the image is immutable and nothing writes to `/app`), and the host-side
    callers - the CLI and the tests - are short-lived. `/healthz` is probed
    every 30 seconds and hashing 162 files each time would be waste, not care.
    """
    return short_build_id(source_fingerprint())


def short_build_id(fingerprint: str) -> str:
    """Twelve characters. Long enough not to collide here, short enough to read.

    A full sha256 in a list of evaluation runs is unreadable, and unreadable is
    how the `[integration-test]` label went unseen for 103 rows.
    """
    return fingerprint[:12]
