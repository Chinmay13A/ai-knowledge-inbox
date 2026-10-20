"""Application settings, loaded from environment variables and `.env`."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.models.chunk import ChunkingConfig


class Settings(BaseSettings):
    # env_ignore_empty: a blank `KEY=` line in .env means "use the default".
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", env_ignore_empty=True, env_parse_none_str="none"
    )

    app_env: str = "development"
    log_level: str = "INFO"
    # Kept as a comma-separated string so it can be set as a plain env var.
    cors_origins: str = "http://localhost:5173"
    db_path: str = "data/inbox.db"
    # Largest accepted request body; a 50,000-character note is far below this.
    max_request_bytes: int = 1_000_000
    # Re-embed items left "pending" by a restart (background tasks don't survive one).
    recover_pending_on_startup: bool = True

    # URL ingestion
    fetch_timeout_s: float = 10.0
    fetch_max_bytes: int = 5_000_000
    respect_robots_txt: bool = True

    # Chunking (characters; ~4 characters per token)
    chunk_size_chars: int = 800
    chunk_overlap_chars: int = 100

    # Embeddings: switch provider/model here; the code only depends on the Embedder interface.
    embedding_provider: Literal["gemini", "openai_compatible"] = "gemini"
    embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int | None = 768
    embedding_api_key: SecretStr | None = None
    embedding_base_url: str | None = None
    embedding_batch_size: int = 50
    embedding_timeout_s: float = 30.0
    embedding_max_retries: int = 3

    # Answer generation (LLM): same switching model as embeddings.
    llm_provider: Literal["gemini", "openai_compatible"] = "gemini"
    llm_model: str = "gemini-3.5-flash"
    llm_api_key: SecretStr | None = None  # blank + same provider as embeddings -> reuses EMBEDDING_API_KEY
    llm_base_url: str | None = None
    llm_temperature: float = 0.2
    llm_max_output_tokens: int = 1024
    llm_timeout_s: float = 60.0
    llm_max_retries: int = 3
    # Gemini "thinking" tokens count toward the output limit and add latency. 0 = off (default),
    # -1 = dynamic (for models that cannot turn it off), none = don't send it (models without thinking). Gemini only.
    llm_thinking_budget: int | None = 0

    # Retrieval. The min score is a cosine similarity; its useful range depends on the embedding model.
    retrieval_top_k: int = 5
    retrieval_min_score: float = 0.6  # calibrated for gemini-embedding-001@768 (see README)

    @model_validator(mode="after")
    def _check_chunking(self) -> "Settings":
        if self.chunk_size_chars < 100:
            raise ValueError("CHUNK_SIZE_CHARS must be at least 100")
        if not 0 <= self.chunk_overlap_chars < self.chunk_size_chars // 2:
            raise ValueError("CHUNK_OVERLAP_CHARS must be >= 0 and less than half of CHUNK_SIZE_CHARS")
        return self

    @model_validator(mode="after")
    def _check_embeddings(self) -> "Settings":
        if self.embedding_provider == "openai_compatible" and not self.embedding_base_url:
            raise ValueError("EMBEDDING_BASE_URL is required when EMBEDDING_PROVIDER=openai_compatible")
        if self.embedding_batch_size < 1:
            raise ValueError("EMBEDDING_BATCH_SIZE must be at least 1")
        return self

    @model_validator(mode="after")
    def _check_llm(self) -> "Settings":
        if self.llm_provider == "openai_compatible" and not self.llm_base_url:
            raise ValueError("LLM_BASE_URL is required when LLM_PROVIDER=openai_compatible")
        if not 0.0 <= self.llm_temperature <= 2.0:
            raise ValueError("LLM_TEMPERATURE must be between 0 and 2")
        if self.llm_max_output_tokens < 64:
            raise ValueError("LLM_MAX_OUTPUT_TOKENS must be at least 64")
        return self

    @model_validator(mode="after")
    def _check_retrieval(self) -> "Settings":
        if not 1 <= self.retrieval_top_k <= 20:
            raise ValueError("RETRIEVAL_TOP_K must be between 1 and 20")
        if not -1.0 <= self.retrieval_min_score <= 1.0:
            raise ValueError("RETRIEVAL_MIN_SCORE must be between -1 and 1")
        return self

    def llm_api_key_value(self) -> str | None:
        """The LLM key; falls back to the embedding key when both use the same provider (one key to manage)."""
        if self.llm_api_key:
            return self.llm_api_key.get_secret_value()
        if self.embedding_api_key and self.llm_provider == self.embedding_provider:
            return self.embedding_api_key.get_secret_value()
        return None

    @property
    def chunking(self) -> ChunkingConfig:
        return ChunkingConfig(size=self.chunk_size_chars, overlap=self.chunk_overlap_chars)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
