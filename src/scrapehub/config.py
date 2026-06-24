"""Application configuration loaded from environment / ``.env``.

Uses ``pydantic-settings`` so every value is typed, validated and documented in
one place. All variables share the ``SCRAPEHUB_`` prefix.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed runtime configuration.

    Attributes mirror the variables documented in ``.env.example``.
    """

    model_config = SettingsConfigDict(
        env_prefix="SCRAPEHUB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- network / proxies -------------------------------------------------
    proxies: list[str] = Field(
        default_factory=list,
        description="Rotating proxy URLs. Empty means direct connections.",
    )

    # --- concurrency / batching -------------------------------------------
    concurrency: int = Field(default=8, ge=1, le=128)
    batch_size: int = Field(default=20, ge=1, le=1000)

    # --- politeness --------------------------------------------------------
    rate_limit: float = Field(default=4.0, gt=0, description="Requests/sec per host.")
    rate_burst: int = Field(default=8, ge=1, description="Token-bucket burst capacity.")
    timeout: float = Field(default=30.0, gt=0, description="HTTP/browser timeout (s).")
    max_retries: int = Field(default=4, ge=0, le=10)

    # --- output / logging --------------------------------------------------
    output_dir: Path = Field(default=Path("data"))
    log_format: str = Field(default="console")
    log_level: str = Field(default="INFO")

    @field_validator("proxies", mode="before")
    @classmethod
    def _split_proxies(cls, value: object) -> object:
        """Allow a comma-separated string in the env var."""
        if isinstance(value, str):
            return [p.strip() for p in value.split(",") if p.strip()]
        return value

    @field_validator("log_format")
    @classmethod
    def _validate_log_format(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"json", "console"}:
            raise ValueError("log_format must be 'json' or 'console'")
        return normalized

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        normalized = value.upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if normalized not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}")
        return normalized

    def ensure_output_dir(self) -> Path:
        """Create and return the configured output directory."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return self.output_dir


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()
