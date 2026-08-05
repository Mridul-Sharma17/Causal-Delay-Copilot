from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed process settings for the profile-neutral Core tracer bullet."""

    model_config = SettingsConfigDict(
        env_prefix="CORE_",
        extra="ignore",
    )

    database_path: Path = Field(default=Path("state/core.sqlite3"))
    gemini_enabled: bool = False
    spa_dist_dir: Path | None = None
