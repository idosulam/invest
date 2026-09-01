"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── Database ──
    db_host: str = "db"
    db_port: int = 5432
    db_user: str = "market"
    db_password: str = "market_secret"
    db_name: str = "market_platform"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    # ── Redis ──
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_url: str = "redis://redis:6379/0"

    # ── MinIO ──
    minio_endpoint: str = "minio:9000"
    minio_root_user: str = "minioadmin"
    minio_root_password: str = "minioadmin"
    minio_bucket: str = "market-data"
    minio_use_ssl: bool = False

    # ── API ──
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_env: str = "development"
    secret_key: str = "change-me-to-a-random-secret-key-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # ── Data Sources ──
    yahoo_finance_enabled: bool = True
    sec_edgar_user_agent: str = "MarketPlatform/0.1 (dev@example.com)"
    sec_edgar_enabled: bool = True
    alpha_vantage_api_key: str = ""
    alpha_vantage_enabled: bool = False

    # ── LLM ──
    llm_provider: str = "ollama"
    llm_model: str = "qwen2.5:7b"
    llm_base_url: str = "http://localhost:11434"

    # ── Observability ──
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    prometheus_port: int = 9090
    log_level: str = "INFO"
    log_format: str = "json"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def password(self) -> str:
        return self.db_password

    @property
    def is_production(self) -> bool:
        return self.api_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
