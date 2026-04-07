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
    gemini_api_key: str = ""
    groq_api_key: str = ""
    mistral_api_key: str = ""
    cohere_api_key: str = ""
    xai_api_key: str = ""
    # --- Ollama ---
    ollama_base_url: str = "http://localhost:11434"
    # --- Default model tiers (used by router & compressor) ---
    simple_model: str = "gpt-3.5-turbo"
    complex_model: str = "gpt-4o"
    # --- Redis (connection URL for ContextForge's semantic cache) ---
    redis_url: str = "redis://localhost:6379"
    # --- Redis (discrete params for LiteLLM's built-in cache) ---
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    # --- LiteLLM response cache ---
    enable_cache: bool = False          # set True in .env to activate Redis cache
    # --- Semantic Cache ---
    similarity_threshold: float = 0.92
    cache_ttl_seconds: int = 86400
    # --- Context Compression ---
    compress_threshold: int = 2000
    compress_keep_recent: int = 4
    compress_min_turns: int = 6
    compress_summary_model: str = "gpt-3.5-turbo"
    # --- Model Routing ---
    preferred_provider: str = "openai"
    # --- Logging ---
    log_level: str = "INFO"
    # --- Storage Paths ---
    sqlite_db_path: str = "./data/telemetry.db"
    faiss_index_path: str = "./data/faiss.index"
    # --- OpenAI base URL (for testing / custom endpoints) ---
    openai_base_url: str = "https://api.openai.com/v1"
    # --- Adaptive Threshold ---
    adaptive_threshold_enabled: bool = True
    adaptive_threshold_window: int = 100
    adaptive_threshold_min: float = 0.70
    adaptive_threshold_max: float = 0.98
    # --- Test Mode ---
    test_mode: bool = False
    # --- OpenTelemetry ---
    enable_otel: bool = False                            # set True in .env to activate
    otel_endpoint: str = "http://localhost:4317"         # OTLP gRPC collector endpoint

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # --- Property aliases for backward compatibility & Phase 4 spec ---
    @property
    def context_compression_threshold_tokens(self) -> int:
        return self.compress_threshold

    @property
    def compression_min_turns(self) -> int:
        return self.compress_min_turns

    @property
    def compression_recent_turns_to_keep(self) -> int:
        return self.compress_keep_recent


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
