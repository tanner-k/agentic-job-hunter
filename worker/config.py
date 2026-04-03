from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # LLM config — overridable via .env
    fast_model: str = "ollama/qwen3.5:9b"
    reasoning_model: str = "ollama/gemma4:e4b"
    ollama_base_url: str = "http://localhost:11434"

    # Supabase — required
    supabase_url: str
    supabase_key: str  # anon key — used for regular DB reads/writes
    supabase_service_role_key: str  # service role key — used by worker's Realtime subscription (bypasses RLS)

    # Local file paths (stay on Mac mini, never uploaded)
    resume_path: Path = Path("./worker/personal/resume.pdf")
    personal_data_path: Path = Path("./worker/personal/personal_data.json")

    # Email agent
    email_poll_interval_seconds: int = 7200  # 2 hours

    # Gmail OAuth (credentials stay local)
    gmail_credentials_path: Path = Path("./worker/personal/credentials.json")
    gmail_token_path: Path = Path("./worker/personal/token.json")
    gmail_scopes: list[str] = Field(
        default_factory=lambda: [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.compose",
        ]
    )

    # Logging
    log_level: str = "INFO"


settings = Settings()
