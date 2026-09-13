"""`scripts/check_secrets.py` must see every file a commit could carry.

It read `git ls-files` only, so a file not yet `git add`-ed was never scanned.
That happened twice (2026-09-08, 409 files instead of 424; 2026-09-13, three new
files pushed unscanned). The rule "the scan ends at 0 before a push" is empty if
the scan does not cover what gets committed.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check_secrets.py"
_spec = importlib.util.spec_from_file_location("check_secrets", _PATH)
cs = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = cs
_spec.loader.exec_module(cs)

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")

FAKE = "fake-jwt-secret-for-scan-test-0001"


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    (tmp_path / ".gitignore").write_text(".env\nlogs/\n", encoding="utf-8")
    (tmp_path / ".env").write_text(f"JWT_SECRET={FAKE}\n", encoding="utf-8")
    (tmp_path / "tracked.py").write_text("print('clean')\n", encoding="utf-8")
    _git(tmp_path, "add", ".gitignore", "tracked.py")
    return tmp_path


def test_a_clean_repo_passes_and_counts_both_kinds(repo, capsys):
    (repo / "new_clean.py").write_text("x = 1\n", encoding="utf-8")

    assert cs.main([], root=repo) == 0

    out = capsys.readouterr().out
    assert "추적 2" in out
    assert "미추적 1" in out


def test_a_secret_in_an_untracked_new_file_is_caught(repo, capsys):
    """(a) The file was never `git add`-ed and is still scanned."""
    (repo / "new_script.py").write_text(f'TOKEN = "{FAKE}"\n', encoding="utf-8")

    assert cs.main([], root=repo) == 1

    err = capsys.readouterr().err
    assert "new_script.py :: JWT_SECRET" in err


def test_gitignored_files_are_not_scanned(repo):
    """(b) `.env` holds the real value and is excluded, as are ignored logs."""
    (repo / "logs").mkdir()
    (repo / "logs" / "app.log").write_text(f"leaked {FAKE}\n", encoding="utf-8")

    scanned = {p.name for p in cs.tracked_files(repo) + cs.untracked_files(repo)}

    assert ".env" not in scanned
    assert "app.log" not in scanned
    assert cs.main(["--quiet"], root=repo) == 0


def test_scanning_nothing_is_still_a_failure(tmp_path, capsys):
    """(c) An empty scan is not a pass (2026-09-02)."""
    _git(tmp_path, "init", "-q")
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    (tmp_path / ".env").write_text(f"JWT_SECRET={FAKE}\n", encoding="utf-8")
    # Ignore the ignore file itself so that nothing at all is left to scan.
    (tmp_path / ".git" / "info" / "exclude").write_text(".gitignore\n", encoding="utf-8")

    assert cs.main([], root=tmp_path) == 2
    assert "0개" in capsys.readouterr().err
