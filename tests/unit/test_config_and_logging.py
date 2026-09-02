"""Configuration and logging — NFR-14, NFR-23, BR-57 ~ BR-60.

Secret handling is tested here rather than left to review because it is the kind
of thing that regresses silently: a stray `log.info("config", extra=settings)`
would leak every key and nothing would visibly break.
"""

from __future__ import annotations

import json
import logging

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.logging import JsonFormatter, bind, mask_secrets


class TestValidation:
    def test_bad_log_level_is_rejected_at_startup(self):
        """NFR-23 — fail fast and say what is wrong, not later and vaguely."""
        with pytest.raises(ValidationError) as exc:
            Settings(postgres_password="x", log_level="CHATTY")
        assert "LOG_LEVEL" in str(exc.value)

    def test_non_numeric_backoff_is_rejected(self):
        with pytest.raises(ValidationError) as exc:
            Settings(postgres_password="x", retry_backoff_seconds="1,soon,16")
        assert "RETRY_BACKOFF_SECONDS" in str(exc.value)

    def test_empty_backoff_is_rejected(self):
        with pytest.raises(ValidationError):
            Settings(postgres_password="x", retry_backoff_seconds=" , ")

    def test_absurd_chunk_ceiling_is_rejected(self):
        with pytest.raises(ValidationError):
            Settings(postgres_password="x", max_chunk_tokens=10)

    def test_log_level_is_normalised(self):
        assert Settings(postgres_password="x", log_level="debug").log_level == "DEBUG"

    def test_backoff_parses_to_floats(self):
        s = Settings(postgres_password="x", retry_backoff_seconds="1, 4 ,16")
        assert s.backoff_schedule == [1.0, 4.0, 16.0]


class TestSecrets:
    def test_password_is_not_in_repr(self):
        s = Settings(postgres_password="hunter2")
        assert "hunter2" not in repr(s)

    def test_database_url_still_resolves_the_password(self):
        s = Settings(postgres_password="hunter2")
        assert "hunter2" in s.database_url

    def test_missing_password_raises_only_when_db_is_needed(self):
        """BR-02 spirit: startup should not die over something not yet used."""
        s = Settings(postgres_password="")
        with pytest.raises(RuntimeError) as exc:
            s.require_db_password()
        assert "POSTGRES_PASSWORD" in str(exc.value)

    def test_api_key_lookup_returns_none_when_unset(self):
        """BR-02 — an unset key is a per-source condition, not a crash."""
        s = Settings(postgres_password="x", ncis_api_key="")
        assert s.api_key_for("NCIS_API_KEY") is None

    def test_api_key_lookup_returns_value_when_set(self):
        s = Settings(postgres_password="x", ncis_api_key="abc123")
        assert s.api_key_for("NCIS_API_KEY") == "abc123"

    def test_unknown_env_name_returns_none(self):
        s = Settings(postgres_password="x")
        assert s.api_key_for("NOT_A_SETTING") is None


class TestMasking:
    @pytest.mark.parametrize(
        "raw",
        [
            "https://api.test/list?serviceKey=SECRET123&page=1",
            "Authorization: Bearer SECRET123",
            "api_key=SECRET123",
            "token: SECRET123",
            "password=SECRET123",
        ],
    )
    def test_secret_values_are_masked(self, raw):
        masked = mask_secrets(raw)
        assert "SECRET123" not in masked
        assert "***" in masked

    def test_non_secret_text_is_untouched(self):
        assert mask_secrets("page=3&numOfRows=100") == "page=3&numOfRows=100"


class TestJsonFormatter:
    def _record(self, **extra) -> logging.LogRecord:
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname=__file__, lineno=1,
            msg="event_happened", args=(), exc_info=None,
        )
        for key, value in extra.items():
            setattr(record, key, value)
        return record

    def test_output_is_json_with_event(self):
        payload = json.loads(JsonFormatter().format(self._record()))
        assert payload["event"] == "event_happened"
        assert payload["level"] == "INFO"

    def test_extra_fields_are_included(self):
        payload = json.loads(JsonFormatter().format(self._record(job_id=7, stage="chunk")))
        assert payload["job_id"] == 7
        assert payload["stage"] == "chunk"

    def test_secret_keyed_fields_are_masked(self):
        """BR-59 — even if someone passes a key through `extra`."""
        payload = json.loads(JsonFormatter().format(self._record(api_key="SECRET123")))
        assert payload["api_key"] == "***"

    def test_secret_inside_a_url_field_is_masked(self):
        payload = json.loads(
            JsonFormatter().format(self._record(url="https://a.test/x?serviceKey=SECRET123"))
        )
        assert "SECRET123" not in payload["url"]

    def test_nested_dict_is_scrubbed(self):
        payload = json.loads(
            JsonFormatter().format(self._record(config={"password": "SECRET123", "port": 5432}))
        )
        assert payload["config"]["password"] == "***"
        assert payload["config"]["port"] == 5432

    def test_correlation_id_is_attached(self):
        """BR-57 — one id ties a whole job together across processes."""
        bind("job-42")
        payload = json.loads(JsonFormatter().format(self._record()))
        assert payload["correlation_id"] == "job-42"


class TestMaskingPrecision:
    """Regression guard for a defect found in Build & Test.

    The first masking implementation used a substring check, which also matched
    `input_tokens` / `output_tokens` — the exact numbers FR-41 exists to record.
    Masking those would have silently emptied the LLM cost tracking that u2 is
    built on.
    """

    def _record(self, **extra) -> logging.LogRecord:
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname=__file__, lineno=1,
            msg="model_call", args=(), exc_info=None,
        )
        for key, value in extra.items():
            setattr(record, key, value)
        return record

    def test_token_counts_are_not_masked(self):
        payload = json.loads(
            JsonFormatter().format(
                self._record(input_tokens=1200, output_tokens=340, token_count=57)
            )
        )
        assert payload["input_tokens"] == 1200
        assert payload["output_tokens"] == 340
        assert payload["token_count"] == 57

    def test_secret_named_fields_are_still_masked(self):
        payload = json.loads(
            JsonFormatter().format(
                self._record(access_token="A", ncis_api_key="B", db_password="C")
            )
        )
        assert payload["access_token"] == "***"
        assert payload["ncis_api_key"] == "***"
        assert payload["db_password"] == "***"

    def test_bearer_scheme_does_not_shield_the_token(self):
        assert "SECRET123" not in mask_secrets("Authorization: Bearer SECRET123")
        assert "SECRET123" not in mask_secrets("authorization: Basic SECRET123")

    def test_identifier_fields_ending_in_key_are_not_masked(self):
        """`ref_key` names the document a job item failed on.

        A bare `_key` suffix in the mask list turned every `job_item_failed`
        log line into `"ref_key": "***"`, which is precisely the field an
        operator needs to diagnose a partial run (FR-8).
        """
        payload = json.loads(
            JsonFormatter().format(
                self._record(ref_key="msds_pdf:doc-42", cache_key="abc", partition_key="p1")
            )
        )
        assert payload["ref_key"] == "msds_pdf:doc-42"
        assert payload["cache_key"] == "abc"
        assert payload["partition_key"] == "p1"

    def test_real_key_fields_are_still_masked(self):
        payload = json.loads(
            JsonFormatter().format(
                self._record(service_key="S", ncis_api_key="S", secret_key="S", private_key="S")
            )
        )
        assert all(
            payload[k] == "***"
            for k in ("service_key", "ncis_api_key", "secret_key", "private_key")
        )
