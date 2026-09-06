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
    # --- Gateway Authentication ---
    # Comma-separated list of accepted bearer tokens for calls to this gateway
    # (checked against the `Authorization: Bearer <token>` header, distinct
    # from the upstream provider keys above). Empty = auth disabled, which is
    # the right default for local single-user development. Set this before
    # exposing ContextForge beyond localhost.
    contextforge_api_keys: str = ""
    # --- CORS ---
    # Comma-separated list of allowed origins, or "*" for any origin.
    # Credentialed CORS (cookies) is never enabled here — this gateway is
    # authenticated via bearer token, not cookies, so wildcard origins are
    # safe without allow_credentials.
    cors_allow_origins: str = "*"

    @property
    def api_keys(self) -> list[str]:
        """Parsed, non-empty list of accepted gateway bearer tokens."""
        return [k.strip() for k in self.contextforge_api_keys.split(",") if k.strip()]

    @property
    def auth_enabled(self) -> bool:
        """Whether gateway bearer-token auth is active."""
        return bool(self.api_keys)

    @property
    def cors_origins(self) -> list[str]:
        """Parsed CORS allow-origins list."""
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
