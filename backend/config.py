"""
backend/config.py
─────────────────
Central configuration using pydantic-settings.
All values can be overridden via environment variables or a .env file.
"""
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = two levels up from this file (backend/config.py → project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM ────────────────────────────────────────────────────────────────────
    use_llm: bool = Field(default=False, description="Enable Ollama LLM backend")
    ollama_model: str = Field(default="qwen2.5:3b", description="Ollama model tag")
    ollama_base_url: str = Field(
        default="http://localhost:11434", description="Ollama server URL"
    )

    # ── Database ───────────────────────────────────────────────────────────────
    db_url: str = Field(
        default="sqlite+aiosqlite:///./data/nyaya.db",
        description="SQLAlchemy async database URL",
    )

    # ── Embedding ──────────────────────────────────────────────────────────────
    embed_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="sentence-transformers model name (lazy-loaded)",
    )

    # ── API / CORS ─────────────────────────────────────────────────────────────
    cors_origin: str = Field(
        default="http://localhost:5173",
        description="Allowed CORS origin (React dev server)",
    )

    # ── Logging ────────────────────────────────────────────────────────────────
    log_level: str = Field(default="INFO", description="Python log level")

    # ── Derived paths (not env vars) ───────────────────────────────────────────
    @property
    def data_dir(self) -> Path:
        """Absolute path to the data/ directory."""
        return PROJECT_ROOT / "data"

    @property
    def laws_dir(self) -> Path:
        """Absolute path to data/laws/ — only source of statute text."""
        return self.data_dir / "laws"

    @property
    def judgments_dir(self) -> Path:
        return self.data_dir / "judgments"

    @property
    def sample_contracts_dir(self) -> Path:
        return self.data_dir / "sample_contracts"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of Settings."""
    return Settings()
