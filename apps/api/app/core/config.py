from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


def _load_env_file() -> None:
    """
    Load environment variables from the nearest .env file.

    Priority:
    1. CLEARFLOW_ENV_FILE if explicitly provided
    2. apps/api/.env (project root for backend)
    3. current working directory /.env
    """
    explicit = os.getenv("CLEARFLOW_ENV_FILE")
    candidates: list[Path] = []

    if explicit:
        candidates.append(Path(explicit).expanduser())

    current_file = Path(__file__).resolve()
    # .../apps/api/app/core/config.py -> .../apps/api
    api_root = current_file.parents[2]
    candidates.append(api_root / ".env")
    candidates.append(Path.cwd() / ".env")

    for env_path in candidates:
        if env_path.exists():
            load_dotenv(env_path, override=False)
            break


_load_env_file()


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(slots=True)
class Settings:
    app_name: str = field(default_factory=lambda: os.getenv("APP_NAME", "ClearFlow API"))
    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    app_debug: bool = field(default_factory=lambda: _as_bool(os.getenv("APP_DEBUG"), True))
    api_v1_prefix: str = field(default_factory=lambda: os.getenv("API_V1_PREFIX", "/api/v1"))
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./clearflow.db"))
    secret_key: str = field(default_factory=lambda: os.getenv("SECRET_KEY", "replace_me_with_a_long_random_secret"))
    google_oauth_client_id: str = field(default_factory=lambda: os.getenv("GOOGLE_OAUTH_CLIENT_ID", "replace_me"))
    google_oauth_client_secret: str = field(default_factory=lambda: os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "replace_me"))
    google_oauth_redirect_uri: str = field(
        default_factory=lambda: os.getenv(
            "GOOGLE_OAUTH_REDIRECT_URI",
            "http://localhost:8000/api/v1/auth/google/callback",
        )
    )
    frontend_success_url: str = field(
        default_factory=lambda: os.getenv("FRONTEND_SUCCESS_URL", "http://localhost:3000/auth/success")
    )
    dev_oauth_bypass: bool = field(default_factory=lambda: _as_bool(os.getenv("DEV_OAUTH_BYPASS"), False))
    allowed_cors_origins: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.allowed_cors_origins = _split_csv(
            os.getenv("ALLOWED_CORS_ORIGINS", "http://localhost:3000")
        )

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
