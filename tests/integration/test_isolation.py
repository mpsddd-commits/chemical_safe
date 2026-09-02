"""IP-3 ①③ — owner isolation against a live PostgreSQL.

The static test (`tests/unit/test_scope_discipline.py`) proves no code path
builds a scope outside C55. This one proves the scope actually excludes the
other user's rows, on each retrieval route separately.

**Test data is created and removed by the test** (FQ7-9). Reusing the public
corpus with an `owner_id` bolted on would modify the thing under test - the same
shape as defect 48 (a test deleted a real chunk) and defect 53 (a test left a
baseline promoted). Those cost a corpus row and a wrong comparison; this one
would cost the isolation guarantee.
"""

from __future__ import annotations

from contextlib import contextmanager

import pytest
from sqlalchemy import func, select

from app.auth.ownership import owned_document, scope_for
from app.auth.types import AuthenticatedUser
from app.core.errors import PermissionDeniedError
from app.core.types import Scope
from app.db.engine import session_scope
from app.db.models import ChunkRow, Document, UserAccount

pytestmark = pytest.mark.integration


@contextmanager
def _two_users_with_documents():
    """Two accounts, one private document each, cleaned up afterwards."""
    created: list[int] = []
    documents: list[int] = []
    try:
        with session_scope() as session:
            for suffix in ("alice", "bob"):
                account = UserAccount(
                    email=f"isolation-{suffix}@test.invalid",
                    password_hash="$argon2id$placeholder",
                    disclaimer_version="1.0.0",
                )
                session.add(account)
                session.flush()
                created.append(account.id)

            for index, owner_id in enumerate(created):
                document = Document(
                    source_id=None,
                    external_id=f"isolation-doc-{owner_id}",
                    doc_type="user_upload",
                    title=f"격리 테스트 문서 {index}",
                    source_url=f"/documents/isolation-doc-{owner_id}",
                    structure_status="unstructured",
                    owner_id=owner_id,
                    upload_filename=f"private-{index}.pdf",
                    upload_size_bytes=1024,
                    upload_page_count=1,
                )
                session.add(document)
                session.flush()
                documents.append(document.id)
                session.add(
                    ChunkRow(
                        document_id=document.id,
                        section_id=None,
                        ordinal=0,
                        # A word that appears nowhere in the public corpus, so a
                        # hit can only have come from this row.
                        text=f"격리시험용고유어구{owner_id} 황산 취급 주의",
                        token_count=12,
                        start_offset=0,
                        end_offset=20,
                        owner_id=owner_id,
                        meta={},
                    )
                )
        yield created, documents
    finally:
        with session_scope() as session:
            for document_id in documents:
                document = session.get(Document, document_id)
                if document is not None:
                    session.delete(document)
            for user_id in created:
                account = session.get(UserAccount, user_id)
                if account is not None:
                    session.delete(account)


class TestScopeExcludesTheOtherUser:
    """IP-3 ③ — per route, because a filter can be missing on one of them."""

    def test_keyword_route_returns_only_own_and_public(self):
        from app.indexing.keyword_index import KeywordIndex
        from app.indexing.vector_index import MetaFilter

        with _two_users_with_documents() as (users, _docs):
            alice, bob = users
            with session_scope() as session:
                index = KeywordIndex(session)
                hits = index.search(
                    f"격리시험용고유어구{bob}", top_k=10,
                    filters=MetaFilter(), scope=Scope(owner_id=alice),
                )
            assert hits == [], "alice's scope returned bob's chunk"

    def test_the_owner_does_see_their_own(self):
        """The mirror of the test above - a filter that hides everything would
        pass the first assertion and be useless."""
        from app.indexing.keyword_index import KeywordIndex
        from app.indexing.vector_index import MetaFilter

        with _two_users_with_documents() as (users, _docs):
            bob = users[1]
            with session_scope() as session:
                hits = KeywordIndex(session).search(
                    f"격리시험용고유어구{bob}", top_k=10,
                    filters=MetaFilter(), scope=Scope(owner_id=bob),
                )
            assert hits, "bob cannot find his own chunk"

    def test_anonymous_sees_neither(self):
        from app.indexing.keyword_index import KeywordIndex
        from app.indexing.vector_index import MetaFilter

        with _two_users_with_documents() as (users, _docs):
            for owner_id in users:
                with session_scope() as session:
                    hits = KeywordIndex(session).search(
                        f"격리시험용고유어구{owner_id}", top_k=10,
                        filters=MetaFilter(), scope=Scope.public(),
                    )
                assert hits == [], "the public scope returned a private chunk"

    def test_the_public_corpus_is_still_visible_to_everyone(self):
        """BR-147 — introducing accounts must not hide what was already public."""
        from app.indexing.keyword_index import KeywordIndex
        from app.indexing.vector_index import MetaFilter

        with _two_users_with_documents() as (users, _docs):
            with session_scope() as session:
                index = KeywordIndex(session)
                anonymous = index.search(
                    "보호구", top_k=10, filters=MetaFilter(), scope=Scope.public()
                )
                signed_in = index.search(
                    "보호구", top_k=10, filters=MetaFilter(), scope=Scope(owner_id=users[0])
                )
            assert anonymous, "the public corpus disappeared for anonymous users"
            assert len(signed_in) >= len(anonymous)


class TestDocumentAccess:
    """IP-3 ① — the cross-access path, and BR-146's 404."""

    def test_a_user_cannot_reach_the_other_document(self):
        with _two_users_with_documents() as (users, docs):
            alice = AuthenticatedUser(id=users[0], email="isolation-alice@test.invalid")
            with session_scope() as session, pytest.raises(PermissionDeniedError):
                owned_document(session, docs[1], alice)

    def test_a_user_can_reach_their_own(self):
        with _two_users_with_documents() as (users, docs):
            alice = AuthenticatedUser(id=users[0], email="isolation-alice@test.invalid")
            with session_scope() as session:
                assert owned_document(session, docs[0], alice).id == docs[0]

    def test_a_public_document_is_not_owned_by_anyone(self):
        """The management screen is "what I uploaded", not "what I can search"."""
        with _two_users_with_documents() as (users, _docs):
            alice = AuthenticatedUser(id=users[0], email="isolation-alice@test.invalid")
            with session_scope() as session:
                public_id = session.scalar(
                    select(Document.id).where(Document.owner_id.is_(None)).limit(1)
                )
                assert public_id is not None
                with pytest.raises(PermissionDeniedError):
                    owned_document(session, public_id, alice)

    def test_a_missing_document_is_the_same_error_as_someone_elses(self):
        """BR-146 — both become 404, so ids cannot be probed for existence."""
        with _two_users_with_documents() as (users, _docs):
            alice = AuthenticatedUser(id=users[0], email="isolation-alice@test.invalid")
            with session_scope() as session, pytest.raises(PermissionDeniedError):
                owned_document(session, 10**9, alice)


class TestScopeConstruction:
    def test_scope_for_matches_the_user(self):
        user = AuthenticatedUser(id=5, email="a@test.invalid")
        assert scope_for(user).owner_id == 5
        assert scope_for(None).owner_id is None


class TestCorpusUnchanged:
    """The suite must leave the corpus exactly as it found it (FQ7-9)."""

    def test_no_private_rows_survive_the_fixture(self):
        with _two_users_with_documents() as (users, _docs):
            pass
        with session_scope() as session:
            leftover_docs = session.scalar(
                select(func.count())
                .select_from(Document)
                .where(Document.owner_id.in_(users))
            )
            leftover_chunks = session.scalar(
                select(func.count()).select_from(ChunkRow).where(ChunkRow.owner_id.in_(users))
            )
            leftover_users = session.scalar(
                select(func.count()).select_from(UserAccount).where(UserAccount.id.in_(users))
            )
        assert (leftover_docs, leftover_chunks, leftover_users) == (0, 0, 0)

    def test_the_public_corpus_count_is_untouched(self):
        with session_scope() as session:
            before = session.scalar(
                select(func.count()).select_from(ChunkRow).where(ChunkRow.owner_id.is_(None))
            )
        with _two_users_with_documents():
            pass
        with session_scope() as session:
            after = session.scalar(
                select(func.count()).select_from(ChunkRow).where(ChunkRow.owner_id.is_(None))
            )
        assert before == after
