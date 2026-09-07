"""C1 Config — single source of truth for every operational parameter (NFR-23).

Secrets are injected via environment variables only and are never logged or
persisted (NFR-14). Startup fails fast with a clear message when a required
value is missing.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# HS256 signing keys shorter than this are weak; PyJWT warns and we refuse
# (RFC 7518 3.2).
JWT_SECRET_MIN_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ---- Database ----
    postgres_user: str = "safeenv"
    postgres_password: SecretStr = SecretStr("")
    postgres_db: str = "safeenv"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    # ---- Queue ----
    redis_host: str = "redis"
    redis_port: int = 6379

    # ---- Source API keys (BR-02: absence never blocks startup) ----
    ncis_api_key: SecretStr = SecretStr("")
    law_api_key: SecretStr = SecretStr("")
    incident_api_key: SecretStr = SecretStr("")
    anthropic_api_key: SecretStr = SecretStr("")  # u2 only
    gemini_api_key: SecretStr = SecretStr("")  # u2 only

    # ---- App ----
    app_host: str = "0.0.0.0"  # noqa: S104 - host exposure limited by compose (NFR-18)
    app_port: int = 8000
    log_level: str = "INFO"
    log_dir: Path = Path("/logs")
    tz: str = "Asia/Seoul"

    # ---- Storage ----
    originals_dir: Path = Path("/data/originals")
    model_cache_dir: Path = Path("/models")

    # ---- Embedding ----
    embedding_model_id: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    # Measured on the worker (32 chunks of 1530 Korean characters, the largest
    # MAX_CHUNK_TOKENS produces): batch 32 peaks at 3.05 GiB and batch 8 at
    # 2.43 GiB for a 3% throughput difference. With the container capped at
    # 4 GiB, batch 32 plus the worker's own footprint was an OOM kill.
    embed_batch_size: int = 8
    # A ceiling on the model's sequence length. BGE-M3 defaults to 8192, which
    # costs nothing in the normal case (padding follows the longest sequence in
    # the batch, and measurements at 8192/2048/1024 were within noise) but
    # bounds the pathological one: a section with no paragraph break inside it
    # cannot be split (BR-27) and would otherwise be encoded at full length.
    embed_max_seq_length: int = 2048
    # BR-61/62 identical-text cache. Bounded because the adapter now lives
    # for the whole process: an unbounded dict would grow with every chunk
    # ever embedded and eventually exhaust the worker's memory limit.
    embedding_cache_size: int = 4096

    # ---- Chunking (BR-26~31) ----
    max_chunk_tokens: int = 1000
    min_chunk_tokens: int = 20
    chunk_overlap: int = 0
    msds_min_sections: int = 8

    # ---- Retry (BR-41) ----
    max_retry_attempts: int = 3
    retry_backoff_seconds: str = "1,4,16"
    retry_total_wait_cap: int = 60

    # ---- Collection policy (BR-05, BR-06) ----
    policy_cache_ttl: int = 86400
    request_interval_ms: int = 500
    respect_robots: bool = True

    # ---- Worker (BR-52) ----
    worker_heartbeat_interval: int = 30
    worker_stale_threshold: int = 120

    # ---- Ingestion target (BR-08) ----
    initial_substance_target: int = 1000
    # How much of the substance listing BR-08 selection may read before it
    # ranks. The listing is 7,189 rows at the time of writing; the cap exists
    # so that a source which grows by an order of magnitude cannot turn one
    # collection into an unbounded scan. Below the target it is ignored.
    substance_scan_cap: int = 10_000

    # ---- LLM (u2, NFR-21) ----
    # The port existed from u1, so this is an adapter choice, not a rewrite.
    llm_provider: str = "gemini"
    # Empty means "the provider's default" (see `resolved_llm_model`). Pinning a
    # model here while switching providers is how you get an unhelpful
    # "model not found" at call time.
    llm_model: str = ""
    # FQ3-14. 429 carries its own retry-after and is bounded separately;
    # `refusal` and 4xx are not retried at all - repeating them changes nothing.
    llm_max_retries: int = 1
    llm_rate_limit_retries: int = 2
    # From **measurement plus headroom**, not from the NFR-1 budget.
    #
    # Deriving it from the 20s budget was wrong and briefly shipped: generation
    # measured 11,582ms on a real query (4,597 input tokens, 6 sentences), so a
    # 10s ceiling turned a slow success into a failure. A timeout's job is to
    # stop a hang, not to enforce an SLO the work cannot currently meet - when
    # the two disagree, the honest move is to record that NFR-1 is missed, not
    # to make the miss look like an error.
    #
    # 60s was the other extreme: one query spent a full minute reaching the same
    # failure it would have reached in five seconds.
    llm_timeout_seconds: float = 20.0
    # Verification is one narrow question per sentence and runs in parallel;
    # measured 2,269ms. 10s rather than something tighter because that is the
    # provider's floor - Gemini returns 400 below it, and at 8s *every*
    # verification failed, which BR-87 correctly removed, silently emptying
    # every answer.
    verify_llm_timeout_seconds: float = 10.0
    # Separate from `llm_model` so the two can be split, but **defaulting to the
    # same model**, and the reason is a measurement that overturned the earlier
    # plan recorded here.
    #
    # The free tier meters requests per model (20/day), so a split gives
    # verification its own pool - worth having, since verification is the
    # multiplier (BR-86a). But measured 2026-08-26 on the real verify prompt:
    #     gemini-3.1-flash-lite   2,269 ms
    #     gemini-3.6-flash        9,297 ms
    # Splitting buys ~3.3 queries/day instead of ~2.8, and costs 22.7s against
    # NFR-1's 20s instead of 8.7s. **Meeting the latency budget is worth more
    # than half a query a day**, so both run on the fast model until the
    # alternatives are comparably fast.
    verify_model: str = "gemini-3.1-flash-lite"
    # A `retry-after` longer than this is not honoured. Sleeping 34s inside a
    # 20s answer budget (NFR-1) is not a retry, it is a hang that ends in the
    # same failure - measured, one query spent 64.6s that way.
    max_retry_after_seconds: float = 5.0
    # C30 entity extraction is an *optimisation* (BR-64): it improves ranking and
    # the query works without it. It also runs inside the NFR-2 retrieval budget
    # (2.5s), so it gets its own, much tighter allowance and no retries at all.
    # Measured 2026-08-25: with the shared policy a 503 model turned a 339ms
    # retrieval into 69s of retrying - an optional step blowing the budget of the
    # thing it was meant to improve.
    #
    # ⚠️ Not honoured on Gemini: the provider's floor is 10s, so this is clamped
    # (with a warning). The no-retry half of the leash still works; the short
    # timeout half does not exist on this provider.
    entity_llm_timeout_seconds: float = 2.0
    # Off by default, and the reason is a precondition rather than an opinion
    # about the model: C30's only output the rules cannot already produce is
    # `substance_names`, and resolving those needs `substance_synonym` (BR-65),
    # which u1 leaves empty - it is pre-provisioned for u3 (DD-21, UD-6).
    #
    # Measured 2026-08-26 on three queries: rule-only extraction produced the
    # correct `doc_type_hint` (msds / law / incident) in 3 of 3 and the *same*
    # final evidence set, at 0.7~46ms against the LLM path's 116~582ms. On a
    # free tier that call also competes for the quota `verify` needs, and
    # verification already multiplies calls by `1 + sentences` (BR-86a).
    #
    # Turn this on when the substance master is populated - then
    # `substance_names` has something to resolve against and the call can pay
    # for itself.
    entity_llm_enabled: bool = False

    # ---- Retrieval (u2) ----
    keyword_top_k: int = 30
    vector_top_k: int = 30
    fusion_top_k: int = 20
    final_top_k: int = 5
    # C4(b) - how deep evaluation may *observe*, not how deep the answer reads.
    # `final_top_k` still decides what the generator sees, what gets cited and
    # what the refusal gate judges; this only widens the candidate list handed
    # to `retrieval_metrics` so Recall@10 measures something Recall@5 does not.
    # 10 because that is the k BR-124 names. Capped at `fusion_top_k` below:
    # past that there is nothing to observe, since fusion never ranked it.
    observation_top_k: int = 10
    rrf_k: int = 60
    # PP-3. Queries are far shorter than chunks, so this costs little next to
    # `embedding_cache_size`. The key is the *normalised* query (BR-63) - the
    # same normalisation the index used, which is what makes hits possible.
    query_embed_cache_size: int = 1024

    # ---- Reranker (BR-70, PP-2) ----
    # Off by default, and measurement now backs what memory pressure suggested.
    #
    # Measured 2026-08-26 with the container up and warm, 5 documents (BR-67's
    # final candidate count): **2,121~2,830ms** against this 1,200ms timeout.
    # Turning it on therefore buys nothing - every call would time out and fall
    # back to fusion order (BR-71) while costing 1.2s of a 2,500ms retrieval
    # budget. bge-reranker-v2-m3 on CPU is simply not viable inside NFR-2.
    #
    # Enabling it needs both a larger timeout and a revisit of NFR-2, or a GPU.
    # The container itself works: it ranked the PPE section first (0.0164 vs
    # 0.0000/0.0005) and sat at 1.475GiB of its 2GiB limit.
    reranker_enabled: bool = False
    reranker_url: str = "http://reranker:8100"
    # Equal to its slice of the NFR-2 budget. A reranker that has blown the
    # budget has already broken the SLO, so there is nothing to wait for.
    reranker_timeout_ms: int = 1200
    # After a failure, stop calling for this long. The socket timeout does not
    # bound the whole failure: with the container down, name resolution alone
    # took the call to 3,355ms against a 1,200ms timeout and a 2,500ms retrieval
    # budget (measured 2026-08-26). BR-71 says a reranker failure must not fail
    # the search - it must not cost the search either, and paying that on every
    # query while the container is down is the same mistake as defect 28.
    reranker_cooldown_seconds: float = 60.0

    # ---- Answering (u2) ----
    # BR-73/74, on cosine similarity - not on the fused RRF score, which is a
    # rank statistic and cannot tell a good query from a bad one (see
    # `rag/refusal.decide`). Measured on the real corpus: on-topic queries score
    # 0.66~0.71 at the top, off-topic ones ~0.42. 0.50 sits in that gap.
    # Still provisional until u4's golden set calibrates it (NFR-7).
    refusal_score_threshold: float = 0.50
    # PP-5. Bounded not for latency but for isolation - an unbounded fan-out lets
    # one long answer exhaust the rate limit and fail *other* users' queries.
    verify_concurrency: int = 4
    # SP-7. Without a ceiling the question can outgrow the evidence and become
    # the prompt.
    query_max_chars: int = 2000

    # ---- Query log retention (FQ3-16, NFR-14) ----
    query_log_retention_days: int = 90

    # ---- Injection scanning (SP-4) ----
    injection_scan_enabled: bool = True

    @field_validator("retry_backoff_seconds")
    @classmethod
    def _validate_backoff(cls, v: str) -> str:
        parts = [p.strip() for p in v.split(",") if p.strip()]
        if not parts:
            raise ValueError("RETRY_BACKOFF_SECONDS must contain at least one value")
        for p in parts:
            if not p.replace(".", "", 1).isdigit():
                raise ValueError(f"RETRY_BACKOFF_SECONDS has non-numeric entry: {p!r}")
        return v

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {sorted(allowed)}, got {v!r}")
        return upper

    @field_validator("max_chunk_tokens")
    @classmethod
    def _validate_max_chunk(cls, v: int) -> int:
        if v < 50:
            raise ValueError("MAX_CHUNK_TOKENS must be >= 50")
        return v

    @field_validator("verify_concurrency")
    @classmethod
    def _validate_verify_concurrency(cls, v: int) -> int:
        if v < 1:
            raise ValueError("VERIFY_CONCURRENCY must be >= 1")
        return v

    @field_validator("refusal_score_threshold")
    @classmethod
    def _validate_threshold(cls, v: float) -> float:
        if v < 0:
            raise ValueError("REFUSAL_SCORE_THRESHOLD must be >= 0")
        return v

    @field_validator("llm_provider")
    @classmethod
    def _validate_provider(cls, v: str) -> str:
        allowed = {"gemini", "anthropic"}
        lowered = (v or "").strip().lower()
        if lowered not in allowed:
            raise ValueError(f"LLM_PROVIDER must be one of {sorted(allowed)}, got {v!r}")
        return lowered

    @field_validator("final_top_k")
    @classmethod
    def _validate_final_top_k(cls, v: int) -> int:
        if v < 1:
            raise ValueError("FINAL_TOP_K must be >= 1")
        return v

    @field_validator("observation_top_k")
    @classmethod
    def _validate_observation_top_k(cls, v: int, info) -> int:
        if v < 1:
            raise ValueError("OBSERVATION_TOP_K must be >= 1")
        # Field order matters here: `fusion_top_k` is declared first, so it is
        # already validated and present in `info.data`. Asking for more depth
        # than fusion produced is not a smaller list - it is a setting that
        # silently does nothing, which is the kind of value that later gets
        # read as a measurement.
        ceiling = info.data.get("fusion_top_k")
        if ceiling is not None and v > ceiling:
            raise ValueError(
                f"OBSERVATION_TOP_K must be <= FUSION_TOP_K ({ceiling}), got {v}"
            )
        return v

    # ---- Accounts and uploads (u5, FR-27~33) ----
    # No default, and that is the rule (BR-137). A development default travels
    # to deployment, and a signing key with a default is not a secret. Startup
    # fails instead - the same shape as `require_db_password`.
    jwt_secret: SecretStr = SecretStr("")
    jwt_expire_hours: int = 12
    # Local HTTP development must keep working; production sets this true.
    cookie_secure: bool = False
    uploads_dir: Path = Path("/data/uploads")
    upload_max_bytes: int = 20 * 1024 * 1024
    upload_max_pages: int = 200
    # Per user, not global. A global watermark only tells you the disk is full,
    # never who filled it (UP-4).
    upload_quota_bytes: int = 200 * 1024 * 1024
    upload_quota_documents: int = 50
    # AP-2 - delay, not lockout. A lockout lets anyone who knows an address
    # deny that account service.
    login_backoff_after: int = 5
    login_backoff_max_seconds: float = 30.0
    disclaimer_version: str = "1.0.0"

    # ---- Evaluation (u4, FR-36~39) ----
    golden_set_path: str = "eval/golden-set.yaml"
    # BR-122 - the judge must not share the answer model's daily pool. Free-tier
    # quota is metered per model (20/day, measured 2026-08-26), and a full run
    # already spends 5.25 calls per answered question before grading starts.
    judge_model: str = "gemini-3.6-flash"
    # Nothing waits on a judge call and a full run takes days either way, so it
    # gets the timeout generation cannot afford (NFR-1 does not apply here).
    judge_llm_timeout_seconds: float = 60.0
    # How many questions a single `--full` invocation will attempt before
    # stopping voluntarily. 0 means "until the quota says no". Exists so a run
    # can be paced against the daily cap rather than always ending in an error.
    evaluation_batch_size: int = 0

    # ---- Derived ----
    @property
    def resolved_llm_model(self) -> str:
        """`LLM_MODEL` when set, else the provider's default."""
        if self.llm_model:
            return self.llm_model
        # Pinned, not `gemini-flash-latest`. An alias that silently moves would
        # change safety-answer quality with no code change, and `llm_call.model`
        # (BR-95) exists precisely so a quality regression can be traced to a
        # model change.
        #
        # Measured 2026-08-26 on the real answer prompt (4,597 input tokens,
        # 5 evidence chunks), same prompt to each:
        #     gemini-3.1-flash-lite    4,133 ms   6 sentences, correct citations
        #     gemini-3.6-flash        73,258 ms
        #     gemini-3.5-flash        78,178 ms
        # An 18x difference on identical work, and the lite answer was correct.
        # Latency on the loaded free tier scales badly with prompt size; the
        # small models do not have that problem.
        #
        # 3.7 and the `gemini-flash-latest` alias returned 503 throughout
        # 2026-08-25 - the argument for pinning a version, made concrete.
        return {
            "gemini": "gemini-3.1-flash-lite",
            "anthropic": "claude-opus-5",
        }[self.llm_provider]

    @property
    def database_url(self) -> str:
        pwd = self.postgres_password.get_secret_value()
        return (
            f"postgresql+psycopg://{self.postgres_user}:{pwd}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}"

    @property
    def backoff_schedule(self) -> list[float]:
        return [float(p.strip()) for p in self.retry_backoff_seconds.split(",") if p.strip()]

    def require_jwt_secret(self) -> None:
        """BR-137 - called by processes that authenticate anyone.

        Deliberately not a validator on the field: the CLI and the worker do not
        authenticate, and making them refuse to start without a signing key
        would be a false dependency.
        """
        secret = self.jwt_secret.get_secret_value()
        if not secret:
            raise RuntimeError(
                "JWT_SECRET 이 설정되지 않았습니다. 서명 비밀키는 환경변수로 "
                "주입해야 하며 기본값을 두지 않습니다 (NFR-12, BR-137)."
            )
        # PyJWT warns below this length for HS256 (RFC 7518 §3.2). A warning in
        # a log is not a control - a short key is a weak key, so it is refused.
        # Found by running the tests: the library said so and nothing was
        # reading the warning.
        if len(secret) < JWT_SECRET_MIN_LENGTH:
            raise RuntimeError(
                f"JWT_SECRET 이 너무 짧습니다 ({len(secret)}자). HS256 서명키는 "
                f"{JWT_SECRET_MIN_LENGTH}자 이상이어야 합니다 (RFC 7518 §3.2). "
                "예: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )

    def require_db_password(self) -> None:
        """Called by processes that actually touch the database."""
        if not self.postgres_password.get_secret_value():
            raise RuntimeError(
                "POSTGRES_PASSWORD is not set. Copy .env.example to .env and fill it in."
            )

    def api_key_for(self, env_name: str) -> str | None:
        """BR-02 — resolve a source's API key by its declared env var name.

        Returns None when unset; the caller raises a source-scoped error so that
        other sources remain usable.
        """
        attr = env_name.lower()
        value = getattr(self, attr, None)
        if value is None:
            return None
        raw = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
        return raw or None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
