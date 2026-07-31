"""Application settings, loaded from environment / .env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- app ---
    app_name: str = "SkillAtlas API"
    environment: str = "development"
    debug: bool = True

    # --- database ---
    # SQLite by default so the stack runs with zero infrastructure.
    # Point DATABASE_URL at Postgres to switch; no code changes required.
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'skillatlas.db').as_posix()}"

    # --- auth ---
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # --- cors ---
    # The frontend talks to us through its own Next.js BFF (same-origin), so
    # browsers never call this API cross-origin in normal operation. These
    # origins exist for local tooling and direct /docs usage.
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # --- ollama (AI tutor) ---
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "qwen2.5:7b"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_timeout_sec: int = 180

    # --- gamification ---
    xp_per_hour: int = 10

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
