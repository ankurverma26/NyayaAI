"""
tests/test_config.py
─────────────────────
Unit tests for the Settings config module.
Run with: pytest tests/test_config.py -v
"""
from pathlib import Path

from backend.config import Settings, get_settings


def test_settings_defaults(monkeypatch) -> None:
    """All defaults should be sensible without a .env file."""
    monkeypatch.delenv("USE_LLM", raising=False)
    s = Settings(_env_file=None)
    assert s.use_llm is False
    assert s.ollama_model == "qwen2.5:3b"
    assert "sqlite" in s.db_url
    assert s.embed_model == "all-MiniLM-L6-v2"
    assert s.cors_origin == "http://localhost:5173"


def test_settings_env_override(monkeypatch) -> None:
    """Env vars should override defaults."""
    monkeypatch.setenv("USE_LLM", "true")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3:8b")
    # Force a fresh instance (bypassing the lru_cache)
    s = Settings()
    assert s.use_llm is True
    assert s.ollama_model == "llama3:8b"


def test_derived_paths() -> None:
    """Derived path properties should return Path objects."""
    s = Settings()
    assert isinstance(s.data_dir, Path)
    assert isinstance(s.laws_dir, Path)
    assert s.laws_dir.name == "laws"
    assert s.judgments_dir.name == "judgments"
    assert s.sample_contracts_dir.name == "sample_contracts"


def test_get_settings_singleton() -> None:
    """get_settings() should return the same cached object."""
    a = get_settings()
    b = get_settings()
    assert a is b
