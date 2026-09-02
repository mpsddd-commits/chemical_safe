"""C51 hashing and C52 tokens — no database, no network (NFR-28).

The interesting assertions are not "hashing works". They are the two properties
that are easy to write code for and easy to lose: a login that reveals nothing
about who is registered, and a signing key that cannot default into production.
"""

from __future__ import annotations

import time

import pytest
from pydantic import SecretStr

from app.auth import hashing
from app.auth.tokens import TokenService
from app.core.errors import ValidationError

GOOD = "Correct-Horse-9"


class TestPasswordPolicy:
    def test_a_compliant_password_passes(self):
        hashing.validate_policy(GOOD)

    @pytest.mark.parametrize("password", ["Short-9", "aB3-", ""])
    def test_too_short_is_rejected(self, password):
        with pytest.raises(ValidationError, match="10자"):
            hashing.validate_policy(password)

    @pytest.mark.parametrize("password", ["alllowercase", "ALLUPPERCASE", "1234567890"])
    def test_one_character_class_is_rejected(self, password):
        with pytest.raises(ValidationError, match="3종류"):
            hashing.validate_policy(password)

    def test_three_classes_is_enough(self):
        """BR-133 asks for three of four, not all four."""
        hashing.validate_policy("abcdefgh1A")

    def test_no_upper_length_limit(self):
        """A cap on length is a cap on strength, and argon2 has no 72-byte trap."""
        hashing.validate_policy("a1B" + "x" * 500)


class TestHashing:
    def test_the_stored_value_is_not_the_password(self):
        stored = hashing.hash_password(GOOD)
        assert GOOD not in stored
        assert stored.startswith("$argon2")

    def test_the_same_password_hashes_differently_each_time(self):
        """Salted. Two identical passwords must not produce identical rows."""
        assert hashing.hash_password(GOOD) != hashing.hash_password(GOOD)

    def test_verification_round_trip(self):
        assert hashing.verify_password(GOOD, hashing.hash_password(GOOD))

    def test_a_wrong_password_fails(self):
        assert not hashing.verify_password("Wrong-Horse-9", hashing.hash_password(GOOD))

    def test_a_missing_account_still_costs_a_verification(self):
        """BR-134 — the timing must not answer "is this address registered?".

        `stored=None` is the no-such-account case; it verifies against a dummy
        hash and returns False. The assertion here is that it takes real time,
        because a fast `return False` is a disclosure channel that no wording of
        the error message can close.
        """
        started = time.perf_counter()
        assert not hashing.verify_password(GOOD, None)
        elapsed = time.perf_counter() - started
        # argon2 defaults are tens of milliseconds; a short-circuit would be
        # microseconds. The bar is deliberately far below the real cost so the
        # test does not become a performance assertion.
        assert elapsed > 0.005, f"no-such-account returned in {elapsed*1000:.2f}ms"

    def test_an_empty_stored_hash_is_treated_as_missing(self):
        assert not hashing.verify_password(GOOD, "")


class TestTokens:
    def _service(self, settings, **over):
        return TokenService(
            settings.model_copy(update={"jwt_secret": SecretStr("test-secret-" + "x" * 32), **over})
        )

    def test_round_trip(self, settings):
        service = self._service(settings)
        user = service.verify(service.issue(7, "a@example.com"))
        assert user is not None
        assert user.id == 7
        assert user.email == "a@example.com"

    def test_a_missing_secret_is_a_startup_failure(self, settings):
        """BR-137 — no default, ever.

        A development default travels to deployment, and a signing key with a
        default is not a key. This fails at construction rather than on the
        first login, so the problem surfaces before anyone has an account.
        """
        with pytest.raises(RuntimeError, match="JWT_SECRET"):
            TokenService(settings.model_copy(update={"jwt_secret": SecretStr("")}))

    def test_a_short_secret_is_refused(self, settings):
        """PyJWT only warns below 32 bytes; a warning in a log is not a control.

        Found by running these tests - the library said the key was weak and
        nothing was reading what it said.
        """
        with pytest.raises(RuntimeError, match="짧습니다"):
            TokenService(settings.model_copy(update={"jwt_secret": SecretStr("short")}))

    def test_a_token_signed_with_another_key_is_rejected(self):
        from app.core.config import Settings

        issuer = TokenService(
            Settings(postgres_password="x", jwt_secret=SecretStr("key-one-" + "a" * 32))
        )
        verifier = TokenService(
            Settings(postgres_password="x", jwt_secret=SecretStr("key-two-" + "b" * 32))
        )
        assert verifier.verify(issuer.issue(1, "a@example.com")) is None

    def test_an_expired_token_is_rejected(self, settings):
        service = self._service(settings, jwt_expire_hours=-1)
        assert service.verify(service.issue(1, "a@example.com")) is None

    @pytest.mark.parametrize("token", [None, "", "not-a-jwt", "a.b.c"])
    def test_every_malformed_token_is_none(self, settings, token):
        """One answer for every failure.

        Expired, tampered, absent and malformed all leave the caller with the
        same thing to do; telling them apart only produces a response that
        describes the token to whoever supplied it.
        """
        assert self._service(settings).verify(token) is None

    def test_the_payload_does_not_carry_the_password(self, settings):
        import jwt as pyjwt

        service = self._service(settings)
        token = service.issue(3, "a@example.com")
        payload = pyjwt.decode(token, "test-secret-" + "x" * 32, algorithms=["HS256"])
        assert set(payload) == {"sub", "email", "iat", "exp"}

    def test_max_age_matches_the_configured_expiry(self, settings):
        assert self._service(settings, jwt_expire_hours=12).max_age_seconds == 12 * 3600


class TestAuthenticatedUserScope:
    def test_the_user_carries_its_own_scope(self):
        """The only failure mode of isolation is building the wrong scope.

        Asking the user object for its scope means there is one place to get it
        wrong instead of one per call site.
        """
        from app.auth.types import AuthenticatedUser

        user = AuthenticatedUser(id=42, email="a@example.com")
        assert user.scope.owner_id == 42

    def test_anonymous_gets_the_public_scope(self):
        from app.auth.ownership import scope_for

        assert scope_for(None).owner_id is None
