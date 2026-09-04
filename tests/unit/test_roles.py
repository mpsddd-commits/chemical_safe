"""B3 roles — `require_admin`, the token's silence about roles, and the CLI.

No database and no network (NFR-28). The session is a stand-in that answers one
question, `UserRepo(session).get(id)`, because that is the only thing the code
under test asks a database for.

What is worth pinning here is not "an admin passes". It is the three things a
future change could quietly take away:

  * a signed-in non-admin gets **403 and not a redirect** — a redirect would
    send a signed-in person to the login form they already came through;
  * the role is **not in the token** — if it ever is, `revoke-admin` stops
    working for up to `jwt_expire_hours` and nothing fails visibly;
  * `grant-admin` on an unknown address **exits non-zero** — a silent success
    leaves an operator believing an admin exists.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.auth.types import AuthenticatedUser
from app.core.types import Role
from app.web.deps import LoginRequired, is_admin, require_admin, require_user

USER = AuthenticatedUser(id=7, email="a@example.com")


class FakeSession:
    """Answers `Session.get(UserAccount, id)` and nothing else.

    `UserRepo.get` is a one-line `self._s.get(...)`, so this is the whole
    surface the dependency touches. A real session here would make the test a
    database test, which NFR-28 says these are not.
    """

    def __init__(self, account=None) -> None:
        self._account = account
        self.gets: list[int] = []

    def get(self, _model, pk):
        self.gets.append(pk)
        return self._account


def _account(role: str, user_id: int = 7):
    return SimpleNamespace(id=user_id, email="a@example.com", role=role)


class TestRequireAdmin:
    def test_anonymous_is_a_login_redirect_not_a_403(self):
        """`require_user` runs first, so being signed out is still a redirect.

        The two failures are different situations and must stay different
        answers: nobody is signed in (go and sign in) versus this person is
        signed in and not allowed (nothing to do here).
        """
        with pytest.raises(LoginRequired):
            require_admin(user=require_user(None), session=FakeSession())

    def test_a_signed_in_non_admin_gets_403(self):
        """403, not a redirect to /login.

        A redirect would show the login form to someone already holding a valid
        cookie; they would sign in and land back on the same 403. The only exit
        from that loop is clearing the cookie, which is not a thing a user knows
        to do.
        """
        with pytest.raises(HTTPException) as caught:
            require_admin(user=USER, session=FakeSession(_account(Role.USER)))
        assert caught.value.status_code == 403

    def test_an_admin_passes_through_unchanged(self):
        session = FakeSession(_account(Role.ADMIN))
        assert require_admin(user=USER, session=session) is USER
        # The role came from the database, not from the caller.
        assert session.gets == [7]

    def test_a_token_for_a_deleted_account_is_not_an_admin(self):
        """The row is gone; the signature is still valid. That is not an admin.

        Nor is it a login prompt - `require_user` already accepted the token,
        so redirecting would be the loop above with an extra step.
        """
        with pytest.raises(HTTPException) as caught:
            require_admin(user=USER, session=FakeSession(None))
        assert caught.value.status_code == 403

    def test_an_unknown_role_string_is_not_admin(self):
        """The column is a String, so it can hold something nobody planned for.

        `== Role.ADMIN` is an allowlist. `!= Role.USER` would have been a
        denylist, and would promote every typo.
        """
        with pytest.raises(HTTPException):
            require_admin(user=USER, session=FakeSession(_account("administrator")))


class TestIsAdminFlag:
    def test_anonymous_never_reaches_the_database(self):
        """The navigation flag on the public query screen must cost nothing.

        `/` is the busiest page and needs no session of its own; if the flag
        made one, every anonymous visit would open a transaction to learn
        something it already knows.
        """
        session = FakeSession(_account(Role.ADMIN))
        assert is_admin(session, None) is False
        assert session.gets == []

    def test_the_flag_agrees_with_the_dependency(self):
        assert is_admin(FakeSession(_account(Role.ADMIN)), USER) is True
        assert is_admin(FakeSession(_account(Role.USER)), USER) is False


class TestRoleIsNotInTheToken:
    def test_the_payload_carries_no_role(self, settings):
        """AP-3's cost is bounded by keeping the role out of the token.

        `current_user` verifies a JWT and touches no database. A role in the
        payload would therefore survive `revoke-admin` until the token expired -
        up to `jwt_expire_hours` (12) of a demoted admin still being an admin,
        with nothing failing to show it. Measured by reading the payload rather
        than by trusting the issuer's signature.
        """
        import jwt as pyjwt
        from pydantic import SecretStr

        from app.auth.tokens import TokenService

        secret = "test-secret-" + "x" * 32
        service = TokenService(settings.model_copy(update={"jwt_secret": SecretStr(secret)}))
        payload = pyjwt.decode(service.issue(7, "a@example.com"), secret, algorithms=["HS256"])
        assert "role" not in payload
        assert set(payload) == {"sub", "email", "iat", "exp"}

    def test_the_value_object_carries_no_role_either(self):
        """`AuthenticatedUser` is built from the token and nothing else.

        A role attribute on it would be filled by the routes that happen to look
        one up and empty on the rest, and no reader could tell "not an admin"
        from "nobody asked".
        """
        assert not hasattr(AuthenticatedUser(id=1, email="a@example.com"), "role")


class FakeRepoSession:
    """Enough of a session for `_set_role`: find a row, mutate it, flush."""

    def __init__(self, account=None) -> None:
        self.account = account
        self.flushed = 0

    def scalar(self, _stmt):
        return self.account

    def flush(self) -> None:
        self.flushed += 1


class TestGrantAndRevoke:
    """The bootstrap path. Without it B1/B2 lock everyone out of `/admin`."""

    @staticmethod
    def _run(monkeypatch, argv, account):
        import contextlib

        import app.cli as cli

        session = FakeRepoSession(account)

        @contextlib.contextmanager
        def fake_scope():
            yield session

        monkeypatch.setattr(cli, "session_scope", fake_scope)
        args = cli.build_parser().parse_args(argv)
        return args.func(args), session

    def test_grant_sets_the_admin_role(self, monkeypatch, capsys):
        account = _account(Role.USER)
        code, session = self._run(monkeypatch, ["grant-admin", "a@example.com"], account)
        assert code == 0
        assert account.role == Role.ADMIN
        assert session.flushed == 1
        assert "admin" in capsys.readouterr().out

    def test_revoke_puts_it_back(self, monkeypatch):
        account = _account(Role.ADMIN)
        code, _ = self._run(monkeypatch, ["revoke-admin", "a@example.com"], account)
        assert code == 0
        assert account.role == Role.USER

    def test_an_unknown_address_exits_non_zero(self, monkeypatch, capsys):
        """Silence here would be an operator believing an admin exists.

        Exit code 2 rather than 1 for the same reason the evaluate commands
        separate their codes: "you asked for something that is not there" is not
        "the thing you asked for failed".
        """
        code, session = self._run(monkeypatch, ["grant-admin", "nobody@example.com"], None)
        assert code == 2
        assert session.flushed == 0
        assert "nobody@example.com" in capsys.readouterr().err

    def test_the_address_is_normalised_before_the_lookup(self, monkeypatch, capsys):
        """BR-132 - registration lower-cases, so this must look up lower-cased.

        Two normalisations that disagree are the same bug as having none: the
        operator types the address off a sign-up email and is told no such
        account exists.
        """
        account = _account(Role.USER)
        code, _ = self._run(monkeypatch, ["grant-admin", "  A@Example.COM "], account)
        assert code == 0
        assert "a@example.com" in capsys.readouterr().out

    def test_granting_twice_reports_no_change(self, monkeypatch, capsys):
        """Idempotent, and it says so rather than pretending it did something."""
        account = _account(Role.ADMIN)
        code, _ = self._run(monkeypatch, ["grant-admin", "a@example.com"], account)
        assert code == 0
        assert "바뀐 것 없음" in capsys.readouterr().out

    def test_no_subcommand_makes_an_admin_by_itself(self):
        """There is no "first account is the admin" path, and there must not be.

        On an exposed instance that rule hands the role to whoever registers
        first. This asserts the registration path never writes a role at all -
        the column default (`'user'`) is the only thing that sets one.
        """
        import inspect

        from app.db.repositories.accounts import UserRepo

        assert "role" not in inspect.getsource(UserRepo.create)
