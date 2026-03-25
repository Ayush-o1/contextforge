"""Pydantic Settings configuration loaded from .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration.

    All values can be overridden via environment variables or a .env file.
    """

    # --- LLM Provider Keys ---
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # --- Redis ---
    redis_url: str = "redis://localhost:6379"

    # --- Semantic Cache ---
    similarity_threshold: float = 0.92
    cache_ttl_seconds: int = 86400

    # --- Context Compression ---
    context_compression_threshold_tokens: int = 2000
    compression_min_turns: int = 6

    # --- Model Routing ---
    preferred_provider: str = "openai"

    # --- Logging ---
    log_level: str = "INFO"

    # --- Storage Paths ---
    sqlite_db_path: str = "./data/telemetry.db"
    faiss_index_path: str = "./data/faiss.index"

    # --- OpenAI base URL (for testing / custom endpoints) ---
    openai_base_url: str = "https://api.openai.com/v1"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


# Context compression
compress_threshold: int = 2000
compress_keep_recent: int = 4
compress_min_turns: int = 6
compress_summary_model: str = "gpt-3.5-turbo"
