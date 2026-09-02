"""The code identity that defect 58 needed and nobody had.

On 2026-08-30 the image was rebuilt and the containers were not recreated. For
five hours `app` and `worker` ran code without `DocType.SUBSTANCE`, an
evaluation measured 0.667 where the same corpus measured 0.700, and every test
was green - because the tests run the working tree and the service ran the
image. These tests fix the one property that makes the two comparable: the
fingerprint must cover exactly what the Dockerfile puts in the image.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.core.build import (
    TRACKED,
    iter_tracked_files,
    short_build_id,
    source_fingerprint,
)

ROOT = Path(__file__).resolve().parents[2]


def _tree(tmp_path: Path) -> Path:
    (tmp_path / "app" / "core").mkdir(parents=True)
    (tmp_path / "app" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "app" / "core" / "types.py").write_text("X = 1\n", encoding="utf-8")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "sources.yaml").write_text("sources: []\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    return tmp_path


class TestTheFingerprintAnswersOneQuestion:
    """Is the code here the same code as over there."""

    def test_the_same_tree_hashes_the_same(self, tmp_path):
        root = _tree(tmp_path)
        assert source_fingerprint(root) == source_fingerprint(root)

    def test_a_changed_byte_changes_the_hash(self, tmp_path):
        root = _tree(tmp_path)
        before = source_fingerprint(root)
        (root / "app" / "core" / "types.py").write_text("X = 2\n", encoding="utf-8")
        assert source_fingerprint(root) != before

    def test_a_renamed_file_changes_the_hash(self, tmp_path):
        """Paths go into the hash, not just contents.

        Concatenating file bodies would call a rename identical to no change,
        and a rename is exactly how a module stops being imported.
        """
        root = _tree(tmp_path)
        before = source_fingerprint(root)
        (root / "app" / "core" / "types.py").rename(root / "app" / "core" / "kinds.py")
        assert source_fingerprint(root) != before

    def test_an_added_file_changes_the_hash(self, tmp_path):
        root = _tree(tmp_path)
        before = source_fingerprint(root)
        (root / "app" / "core" / "build.py").write_text("Y = 1\n", encoding="utf-8")
        assert source_fingerprint(root) != before

    def test_untracked_paths_are_invisible(self, tmp_path):
        """`tests/`, `data/`, `logs/` are not in the image and must not count.

        If they did, every local test run would report the deployment stale and
        the check would be ignored within a day.
        """
        root = _tree(tmp_path)
        before = source_fingerprint(root)
        (root / "tests").mkdir()
        (root / "tests" / "test_x.py").write_text("assert True\n", encoding="utf-8")
        (root / "logs").mkdir()
        (root / "logs" / "safeenv.log").write_text("noise\n", encoding="utf-8")
        assert source_fingerprint(root) == before


class TestWhatDockerDropsIsDroppedHere:
    def test_pycache_is_ignored(self, tmp_path):
        root = _tree(tmp_path)
        before = source_fingerprint(root)
        cache = root / "app" / "core" / "__pycache__"
        cache.mkdir()
        (cache / "types.cpython-312.pyc").write_bytes(b"\x00\x01")
        assert source_fingerprint(root) == before

    def test_loose_pyc_is_ignored(self, tmp_path):
        root = _tree(tmp_path)
        before = source_fingerprint(root)
        (root / "app" / "core" / "types.pyc").write_bytes(b"\x00")
        assert source_fingerprint(root) == before

    def test_a_missing_tracked_entry_does_not_raise(self, tmp_path):
        """`prompts/` and `eval/` are absent from this fixture on purpose."""
        assert source_fingerprint(_tree(tmp_path))


class TestTrackedMatchesTheDockerfile:
    """The check is only as good as its file set (defect 58's actual shape).

    A `COPY` added to the Dockerfile without a matching entry here produces a
    fingerprint that agrees while the images differ - a green light that means
    nothing, which is worse than no light.
    """

    def test_every_runtime_copy_is_tracked(self):
        text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        runtime = text.split("stage 2: runtime", 1)[1]
        copied = {
            match.group(1)
            for line in runtime.splitlines()
            if (match := re.match(r"COPY (?!--from)(\S+)", line.strip()))
        }
        assert copied == set(TRACKED), f"Dockerfile COPY 와 TRACKED 불일치: {copied ^ set(TRACKED)}"

    def test_the_real_tree_is_hashable(self):
        files = list(iter_tracked_files(ROOT))
        assert len(files) > 100
        assert all(f.exists() for f in files)

    def test_the_order_is_stable(self):
        """Sorted by POSIX relative path so Windows and Linux agree."""
        first = [p.relative_to(ROOT).as_posix() for p in iter_tracked_files(ROOT)]
        assert first == sorted(first)


class TestShortForm:
    def test_twelve_characters(self):
        assert len(short_build_id("a" * 64)) == 12
