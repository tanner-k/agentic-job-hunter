"""Tests for Settings configuration loading from environment variables."""

from pathlib import Path

import pytest

from worker.config import Settings


@pytest.fixture()
def required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set the minimum required env vars so Settings can be instantiated."""
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-anon-key")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")


class TestSettingsDefaults:
    def test_default_fast_model(self, required_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = Settings(
            supabase_url="https://test.supabase.co",
            supabase_key="key",
            supabase_service_role_key="srk",
        )
        assert settings.fast_model == "ollama/qwen3.5:9b"

    def test_default_reasoning_model(self, required_env: None) -> None:
        settings = Settings(
            supabase_url="https://test.supabase.co",
            supabase_key="key",
            supabase_service_role_key="srk",
        )
        assert settings.reasoning_model == "ollama/gemma4:e4b"

    def test_default_resume_path(self, required_env: None) -> None:
        settings = Settings(
            supabase_url="https://test.supabase.co",
            supabase_key="key",
            supabase_service_role_key="srk",
        )
        assert settings.resume_path == Path("./worker/personal/resume.pdf")

    def test_default_email_poll_interval(self, required_env: None) -> None:
        settings = Settings(
            supabase_url="https://test.supabase.co",
            supabase_key="key",
            supabase_service_role_key="srk",
        )
        assert settings.email_poll_interval_seconds == 7200

    def test_default_log_level(self, required_env: None) -> None:
        settings = Settings(
            supabase_url="https://test.supabase.co",
            supabase_key="key",
            supabase_service_role_key="srk",
        )
        assert settings.log_level == "INFO"


class TestSettingsFromEnv:
    def test_supabase_url_read_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SUPABASE_URL", "https://myproject.supabase.co")
        monkeypatch.setenv("SUPABASE_KEY", "anon-key")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")

        settings = Settings(
            supabase_url="https://myproject.supabase.co",
            supabase_key="anon-key",
            supabase_service_role_key="service-key",
        )
        assert settings.supabase_url == "https://myproject.supabase.co"

    def test_custom_fast_model_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FAST_MODEL", "ollama/llama3.2:3b")
        settings = Settings(
            supabase_url="https://test.supabase.co",
            supabase_key="key",
            supabase_service_role_key="srk",
            fast_model="ollama/llama3.2:3b",
        )
        assert settings.fast_model == "ollama/llama3.2:3b"

    def test_custom_log_level(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = Settings(
            supabase_url="https://test.supabase.co",
            supabase_key="key",
            supabase_service_role_key="srk",
            log_level="DEBUG",
        )
        assert settings.log_level == "DEBUG"
