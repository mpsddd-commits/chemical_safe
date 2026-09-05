"""B4 — every guarded route × (anonymous / signed-in user / admin), pinned.

This is the test that would have caught B1/B2/B2a before they were exposure.
The survey that found them was a person running curl by hand; the finding was
real and the method does not repeat itself. What repeats is a table.

**Why the whole matrix and not just "anonymous is refused".** Each column
catches a different way of getting this wrong, and one column alone passes
while the code is broken in the other two:

- anonymous → refused: the guard exists at all
- signed-in non-admin → refused: the guard asks "is this an admin", not merely
  "is anyone here". `require_user` alone would pass an anonymous check and hand
  the ingestion trigger to every account that can register
- admin → allowed: the guard is not simply refusing everyone. A dependency that
  raised unconditionally would satisfy both rows above and lock the operators
  out of their own screens

**The control group is not decoration.** `/healthz`, `/`, `/substances` and
`/documents` are listed here because the plausible failure of this change is
not "the guard was forgotten" - it is "the guard was applied too widely".
`/healthz` under authentication makes the container permanently unhealthy;
`/` and `/substances` under authentication silently repeal BR-147, the public
corpus. Neither of those shows up in a test that only checks the closed doors.

**Accounts are created and removed by the test** (FQ7-9), and `TestNoAccounts
Survive` asserts the removal rather than trusting the fixture - defects 48 and
53 were both a test leaving its subject changed, and this fixture writes to
`user_account`, which is the table the whole feature reads.

Measured 2026-09-04 against the working tree before the B-group commits:
`/api/sources` `/api/jobs` `/api/stats` `/admin` `/admin/sources`
`/admin/jobs` `/usage` all answered anonymous callers 200, and
`POST /api/sources/{id}/ingest` reached its handler.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

import httpx
import pytest
from sqlalchemy import func, select

from app.auth.tokens import COOKIE_NAME, TokenService
from app.core.types import Role
from app.db.engine import session_scope
from app.db.models import UserAccount

pytestmark = pytest.mark.integration

# The running container, not an in-process `TestClient`.
#
# Two reasons, one of them decisive. The decisive one: `TestClient` needs the
# whole web stack importable on the host, and the host environment here has no
# `jinja2` - the templates are the container's job. The test collected as an
# ImportError, which is a red run that says nothing about authorisation.
#
# The better one: authorisation is a property of the deployment. An in-process
# app proves the working tree is guarded; this proves the thing actually
# listening on the port is. `test_deployed_code_is_current.py` keeps the two
# from drifting, so there is no coverage lost by measuring the far side.
#
# 8300 is the host half of the `127.0.0.1:8300:8000` mapping in
# docker-compose.yml. Overridable because the port is deployment configuration,
# not a fact about the routes.
BASE_URL = os.environ.get("SAFEENV_BASE_URL", "http://127.0.0.1:8300")

# A source id that is declared nowhere, so `IngestionService.start` returns
# "unknown or disabled source" before it creates a job or touches the queue.
# The point of the POST row is *reachability*, and a real source id would have
# the admin case start an actual collection - a test that changes the system it
# is measuring, which is the shape of defects 48 and 53. 409 here proves the
# request got past authorisation and was then declined on the merits, which is
# exactly the distinction the exposure survey had to make by hand.
UNKNOWN_SOURCE = "b4-nonexistent-source"
INGEST_PATH = f"/api/sources/{UNKNOWN_SOURCE}/ingest"

ADMIN_JSON = ("/api/sources", "/api/jobs", "/api/stats")
ADMIN_HTML = ("/admin", "/admin/sources", "/admin/jobs", "/usage")


@pytest.fixture(scope="module")
def client() -> Iterator[httpx.Client]:
    # `follow_redirects=False` is the point of the whole file. With redirects
    # followed, an anonymous request to `/admin` returns the login page with
    # status 200, and every assertion below would have to inspect HTML to tell
    # a refusal from a result - which is precisely the confusion that let these
    # routes read as "anonymous 200" for as long as they did.
    with httpx.Client(base_url=BASE_URL, follow_redirects=False, timeout=30.0) as c:
        try:
            c.get("/healthz")
        except httpx.HTTPError as exc:  # pragma: no cover - environment, not logic
            pytest.skip(f"{BASE_URL} 에 앱이 떠 있지 않다 - 확인할 배포가 없다: {exc}")
        yield c


def _email(label: str, batch: str) -> str:
    return f"b4-authz-{batch}-{label}@test.invalid"


@contextmanager
def _two_accounts(batch: str = "main") -> Iterator[dict[str, int]]:
    """One ordinary account and one admin, removed afterwards.

    A context manager with a fixture around it, rather than a fixture alone,
    so that `TestNoAccountsSurvive` can drive the create-and-clean cycle
    itself. A test that asserts the cleanup has to be able to run it.

    `batch` keeps the addresses distinct because that test runs a second cycle
    while the module fixture's accounts are still live, and `user_account.email`
    is unique - without it the cleanup test fails on an insert, which looks
    like a cleanup failure and is not one.
    """
    created: dict[str, int] = {}
    try:
        with session_scope() as session:
            for label, role in (("user", Role.USER), ("admin", Role.ADMIN)):
                account = UserAccount(
                    email=_email(label, batch),
                    password_hash="$argon2id$placeholder",
                    disclaimer_version="1.0.0",
                    role=role.value,
                )
                session.add(account)
                session.flush()
                created[label] = account.id
        yield created
    finally:
        with session_scope() as session:
            for user_id in created.values():
                account = session.get(UserAccount, user_id)
                if account is not None:
                    session.delete(account)


@pytest.fixture(scope="module")
def accounts() -> Iterator[dict[str, int]]:
    with _two_accounts() as created:
        yield created


def _as(label: str, accounts: dict[str, int]) -> dict[str, str]:
    """A real signed token in a real `Cookie` header, not a patched dependency.

    Overriding `current_user` would prove the routers call *something*; it
    would not prove the token the login form issues satisfies it - and against
    a separate process there is nothing to patch anyway. The token is minted
    from the same `JWT_SECRET` the container was started with, so a mismatch
    shows up as a 401 for the admin row rather than as a silent pass.

    The role is deliberately *not* in the token - `require_admin` reads it from
    the database (B3) - so both rows carry the identical token shape and only
    the `user_account` row decides the outcome.
    """
    token = TokenService().issue(accounts[label], _email(label, "main"))
    return {"Cookie": f"{COOKIE_NAME}={token}"}


class TestAnonymousIsRefused:
    """Column 1 - the exposure itself."""

    @pytest.mark.parametrize("path", ADMIN_JSON)
    def test_json_reads_answer_401(self, client, path):
        response = client.get(path)
        assert response.status_code == 401, f"{path} is still open to anonymous"

    def test_the_ingest_trigger_answers_401(self, client):
        """The one that changes state, so it gets its own name in the output.

        A failure line reading "test_json_reads_answer_401[/api/stats]" and one
        reading "the ingest trigger" are not equally alarming, and the runner
        only shows the name.
        """
        response = client.post(INGEST_PATH, json={})
        assert response.status_code == 401

    @pytest.mark.parametrize("path", ADMIN_HTML)
    def test_html_screens_redirect_to_login(self, client, path):
        response = client.get(path)
        assert response.status_code == 303, f"{path} is still open to anonymous"
        # The location matters as much as the code: a 303 with no `Location`
        # leaves the browser where it was and looks like a broken page, which
        # is the defect `create_app`'s `LoginRequired` handler exists to fix.
        assert response.headers["location"] == f"/login?next={path}"

    def test_the_admin_ingest_form_is_refused(self, client):
        response = client.post("/admin/sources/kosha-msds/ingest", data={})
        assert response.status_code == 303
        assert "/login" in response.headers["location"]


class TestAnOrdinaryAccountIsNotAnAdmin:
    """Column 2 - `require_user` would pass every one of these."""

    @pytest.mark.parametrize("path", (*ADMIN_JSON, *ADMIN_HTML))
    def test_signed_in_non_admin_gets_403(self, client, accounts, path):
        response = client.get(path, headers=_as("user", accounts))
        assert response.status_code == 403, f"{path} accepted a non-admin account"

    def test_the_ingest_trigger_rejects_a_non_admin(self, client, accounts):
        response = client.post(INGEST_PATH, json={}, headers=_as("user", accounts))
        assert response.status_code == 403

    def test_403_is_not_a_redirect(self, client, accounts):
        """B3's decision, pinned.

        Sending an already-signed-in person to `/login` produces a loop whose
        only exit is clearing the cookie.
        """
        response = client.get("/admin", headers=_as("user", accounts))
        assert "location" not in response.headers


class TestAnAdminGetsIn:
    """Column 3 - without this, refusing everyone would pass the suite."""

    @pytest.mark.parametrize("path", (*ADMIN_JSON, *ADMIN_HTML))
    def test_admin_reaches_every_guarded_route(self, client, accounts, path):
        response = client.get(path, headers=_as("admin", accounts))
        assert response.status_code == 200, f"{path} refused an admin"

    def test_the_ingest_trigger_is_reachable_and_then_declined(self, client, accounts):
        """409, not 401 or 403.

        This is the assertion the exposure survey turned on: the endpoint used
        to answer 409 to anonymous callers too, and 409 was read as a refusal
        when it was a business answer. Now the two are distinguishable, and
        this line is what keeps them that way.
        """
        response = client.post(INGEST_PATH, json={}, headers=_as("admin", accounts))
        assert response.status_code == 409
        assert UNKNOWN_SOURCE in response.json()["detail"]

    @pytest.mark.parametrize("path", ADMIN_HTML)
    def test_the_page_agrees_about_who_is_looking(self, client, accounts, path):
        """B1/B2 - `user` reaches the template, not just `is_admin`.

        B3 passed the flag alone, so an admin saw the admin navigation above a
        "로그인하지 않음" banner and a "로그인" link: the page rendered the
        viewer as signed out and privileged at the same time. Both halves are
        asserted because passing `user` and dropping `is_admin` would fix the
        banner and delete the navigation.
        """
        body = client.get(path, headers=_as("admin", accounts)).text
        assert 'data-testid="no-auth-warning"' not in body
        assert 'data-testid="account-email"' in body
        assert 'data-testid="nav-dashboard-link"' in body


class TestTheOpenRoutesStayOpen:
    """The control group. This change's plausible failure is over-reach."""

    def test_healthz_needs_no_account(self, client):
        """Docker's healthcheck calls this with no cookie.

        The assertion is "not a refusal", not "200": `/healthz` answers 503
        when a component is down, and pinning 200 would make this test fail for
        a stopped worker - which is the endpoint doing its job, not a
        regression in authorisation.
        """
        response = client.get("/healthz")
        assert response.status_code not in (303, 401, 403)
        assert set(response.json()) >= {"app", "db", "queue", "worker", "build"}

    @pytest.mark.parametrize("path", ("/", "/substances"))
    def test_the_public_corpus_is_still_anonymous(self, client, path):
        """BR-147. Accounts were added without closing what was already open."""
        assert client.get(path).status_code == 200

    def test_documents_still_asks_for_a_login_rather_than_403(self, client):
        """`/documents` is per-user, not admin-only.

        A redirect here and a 403 would both "refuse anonymous", so the codes
        are checked separately: 403 would mean the route had been swept into
        the admin group and no ordinary account could ever upload again.
        """
        response = client.get("/documents")
        assert response.status_code == 303
        assert response.headers["location"] == "/login?next=/documents"

    def test_an_ordinary_account_can_use_its_own_documents(self, client, accounts):
        response = client.get("/documents", headers=_as("user", accounts))
        assert response.status_code == 200


class TestNoAccountsSurvive:
    """FQ7-9 — the fixture's cleanup is asserted, not assumed."""

    def test_the_fixture_leaves_the_table_as_it_found_it(self):
        with session_scope() as session:
            before = session.scalar(select(func.count()).select_from(UserAccount))

        with _two_accounts(batch="cleanup") as account_ids:
            created = list(account_ids.values())
            with session_scope() as session:
                during = session.scalar(select(func.count()).select_from(UserAccount))
            # The mirror assertion: a fixture that silently created nothing
            # would leave nothing behind and pass the cleanup check trivially.
            assert during == before + 2, "the fixture did not create what it claims to"

        with session_scope() as session:
            after = session.scalar(select(func.count()).select_from(UserAccount))
            leftover = session.scalar(
                select(func.count())
                .select_from(UserAccount)
                .where(UserAccount.id.in_(created))
            )
        # Both: the count returning to normal would also be satisfied by the
        # fixture deleting somebody else's row instead of its own.
        assert (after, leftover) == (before, 0)


class TestNavigationHidesWhatIsNotYours:
    """Nav links match what the visitor can actually open (2026-09-05).

    Two rules, opposite in kind. Admin links lead somewhere no amount of
    signing in opens for a normal account, so showing them invites a 403.
    `내 문서`/`이력` lead somewhere a login opens - but the labels are
    possessive, and there is no "mine" until there is a session.

    Neither is the access control. `require_admin` and `require_user` on the
    routes are; this only stops advertising a door.
    """

    def test_anonymous_sees_neither_admin_nor_personal_links(self, client):
        body = client.get("/").text
        for testid in (
            "nav-usage-link",
            "nav-dashboard-link",
            "nav-sources-link",
            "nav-jobs-link",
            "nav-documents-link",
            "nav-history-link",
        ):
            assert testid not in body, f"익명에게 {testid} 가 보인다"

    def test_anonymous_still_sees_the_public_screens(self, client):
        """BR-147 - the corpus is public and must stay reachable."""
        body = client.get("/").text
        assert "nav-query-link" in body
        assert "nav-substances-link" in body

    def test_a_signed_in_user_sees_personal_links_but_no_admin_links(
        self, client, accounts
    ):
        body = client.get("/", headers=_as("user", accounts)).text
        assert "nav-documents-link" in body
        assert "nav-history-link" in body
        assert "nav-dashboard-link" not in body

    def test_an_admin_sees_both(self, client, accounts):
        body = client.get("/", headers=_as("admin", accounts)).text
        assert "nav-documents-link" in body
        assert "nav-dashboard-link" in body
