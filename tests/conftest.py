"""Shared test fixtures.

Nothing here touches the network or a database (NFR-28). The components under
test receive repositories or plain data, which is exactly what DD-20 was for.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Settings must resolve before any app module imports Config.
os.environ.setdefault("POSTGRES_PASSWORD", "test-password")
os.environ.setdefault("LOG_DIR", "")
os.environ.setdefault("EMBEDDING_DIM", "8")

# Source credentials, for the same reason (2026-09-02). The live-contract
# tests build real adapters, and `ApiKeyMissingError` fires while the adapter
# is constructed - before any request would be made, so this is not a test
# reaching the network. Found by running the unit suite from a fresh copy with
# no `.env`: 4 tests failed there and passed here, which is what a clone of
# this repository, or CI, would see. `setdefault` keeps a real key winning
# locally.
os.environ.setdefault("LAW_API_KEY", "test-law-key")
os.environ.setdefault("NCIS_API_KEY", "test-ncis-key")
os.environ.setdefault("INCIDENT_API_KEY", "test-incident-key")

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


@pytest.fixture
def msds_text() -> str:
    from app.processing.stages.normalize import normalize

    return normalize(read_fixture("msds_sample.txt"))


@pytest.fixture
def msds_unstructured_text() -> str:
    from app.processing.stages.normalize import normalize

    return normalize(read_fixture("msds_unstructured.txt"))


@pytest.fixture
def law_text() -> str:
    from app.processing.stages.normalize import normalize

    return normalize(read_fixture("law_sample.txt"))


@pytest.fixture
def incident_text() -> str:
    from app.processing.stages.normalize import normalize

    return normalize(read_fixture("incident_sample.txt"))


@pytest.fixture
def settings():
    from app.core.config import Settings

    return Settings(
        postgres_password="test-password",
        max_chunk_tokens=1000,
        min_chunk_tokens=20,
        msds_min_sections=8,
        embedding_dim=8,
    )
