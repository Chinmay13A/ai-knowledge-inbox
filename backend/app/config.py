"""Application settings, loaded from environment variables and `.env`."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.models.chunk import ChunkingConfig


class Settings(BaseSettings):
    # env_ignore_empty: a blank `KEY=` line in .env means "use the default".
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", env_ignore_empty=True
    )

    app_env: str = "development"
    log_level: str = "INFO"
    # Kept as a comma-separated string so it can be set as a plain env var.
    cors_origins: str = "http://localhost:5173"
    db_path: str = "data/inbox.db"

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

    @property
    def chunking(self) -> ChunkingConfig:
        return ChunkingConfig(size=self.chunk_size_chars, overlap=self.chunk_overlap_chars)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
