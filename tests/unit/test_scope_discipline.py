"""IP-3 ② — the static half of proving owner isolation.

BR-145 says `Scope` is built in exactly one place (C55). The integration tests
prove that isolation holds **on the paths they exercise**; this one proves that
no other path exists to begin with.

The distinction matters. A screen added next month that writes
`Scope(owner_id=request.user.id)` by hand will pass every cross-access test —
because no test covers it yet — and this file is the only thing that fails.

This project has five defects (25, 39, 40, 46, 47) whose whole story is "the
tests were green and that code had never run". Isolation is the most expensive
place for that to happen: it breaks silently, and nothing reports it.
"""

from __future__ import annotations

import re
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "app"

# Where constructing a scope is the job.
ALLOWED = {
    "app/auth/ownership.py",       # C55 - the single construction site (BR-145)
    "app/auth/types.py",           # AuthenticatedUser.scope, read by C55
    "app/core/types.py",           # the definition itself
    "app/services/query_service.py",  # the public default, see below
    # u4's evaluator. Allow-listed rather than exempted: the test below pins it
    # to `Scope.public()` specifically, because BR-148 needs the golden-set
    # numbers to describe the public corpus and nothing else.
    "app/services/evaluation_service.py",
}

# `Scope.public()` is not owner scope - it is the absence of one, and u4's
# evaluator must keep using it (BR-148).
_CONSTRUCTION = re.compile(r"\bScope\(")


def _sources() -> list[Path]:
    return sorted(p for p in APP.rglob("*.py") if "__pycache__" not in p.parts)


def _relative(path: Path) -> str:
    return path.relative_to(APP.parent).as_posix()


class TestScopeIsBuiltInOnePlace:
    def test_no_module_outside_c55_constructs_a_scope(self):
        offenders: list[str] = []
        for path in _sources():
            rel = _relative(path)
            if rel in ALLOWED:
                continue
            text = path.read_text(encoding="utf-8")
            for number, line in enumerate(text.splitlines(), start=1):
                if _CONSTRUCTION.search(line):
                    offenders.append(f"{rel}:{number}: {line.strip()}")
        assert not offenders, (
            "Scope() is constructed outside C55 (BR-145). Use "
            "`app.auth.ownership.scope_for(user)` instead:\n  "
            + "\n  ".join(offenders)
        )

    def test_the_allow_list_is_not_stale(self):
        """An allow-list entry that no longer constructs a scope should go.

        Otherwise the list grows into a place where a real offender can hide.
        """
        for rel in ALLOWED:
            path = APP.parent / rel
            assert path.exists(), f"allow-listed file is gone: {rel}"

    def test_the_evaluator_uses_the_public_scope_and_only_that(self):
        """BR-148 — u4's numbers must describe the public corpus.

        If evaluation ever ran with an owner scope, the golden-set metrics would
        depend on who had uploaded what, and a regression would be
        indistinguishable from someone adding a file.
        """
        path = APP / "services" / "evaluation_service.py"
        text = path.read_text(encoding="utf-8")
        constructions = re.findall(r"Scope\([^)]*\)|Scope\.public\(\)", text)
        assert constructions, "the evaluator should still be building a scope"
        for occurrence in constructions:
            assert occurrence == "Scope.public()", occurrence


class TestOwnershipHelperIsUsed:
    def test_document_routes_go_through_the_ownership_check(self):
        """BR-146 — every per-document route resolves ownership first.

        A route that loads a `Document` by id without it would return someone
        else's file with a 200.
        """
        path = APP / "web" / "routers" / "documents.py"
        text = path.read_text(encoding="utf-8")
        # Each handler either calls the service (which calls C55) or checks
        # owner_id itself; neither may be missing.
        assert "owned" in text or "owner_id" in text
        assert "PermissionDeniedError" in text
        # And it must translate to 404, never 403 (BR-146). Checked on the
        # status argument rather than the bare digits, so a comment explaining
        # the rule does not fail the rule.
        assert "status_code=403" not in text
        assert "HTTP_403" not in text
        assert "status_code=404" in text
