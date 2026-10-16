"""Application settings, read from environment variables.

Every value the app needs from its surroundings is read here, once, at startup.
If you run the app locally, values can come from backend/.env. In a container or
server, set real environment variables instead (they take priority over .env).
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy.engine import URL, make_url

# Load backend/.env if it exists. override=False (the default) means real
# environment variables are never replaced by values from the file.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class ConfigError(RuntimeError):
    """Raised when a required setting is missing or invalid."""


def _get_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from None


def _get_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from None


def _get_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _build_database_url() -> URL:
    """Use DATABASE_URL if set (handy for tests), else build it from POSTGRES_* vars."""
    explicit = os.environ.get("DATABASE_URL", "").strip()
    if explicit:
        return make_url(explicit)

    password = os.environ.get("POSTGRES_PASSWORD", "")
    if not password:
        raise ConfigError(
            "POSTGRES_PASSWORD is not set. Set it in the environment or in backend/.env "
            "(see backend/.env.example)."
        )

    # URL.create() escapes special characters in the password for us.
    return URL.create(
        drivername="postgresql+psycopg",
        username=os.environ.get("POSTGRES_USER", "postgres"),
        password=password,
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=_get_int("POSTGRES_PORT", 5432),
        database=os.environ.get("POSTGRES_DB", "tasks"),
    )


@dataclass
class Settings:
    database_url: URL
    redis_enabled: bool
    redis_host: str
    redis_port: int
    redis_db: int
    redis_password: Optional[str]
    redis_socket_timeout: float
    cache_ttl_seconds: int
    log_level: str
    db_connect_retries: int
    db_connect_retry_delay: float


def load_settings() -> Settings:
    cache_ttl = _get_int("CACHE_TTL_SECONDS", 60)
    if cache_ttl < 1:
        raise ConfigError("CACHE_TTL_SECONDS must be at least 1")

    return Settings(
        database_url=_build_database_url(),
        redis_enabled=_get_bool("REDIS_ENABLED", True),
        redis_host=os.environ.get("REDIS_HOST", "localhost"),
        redis_port=_get_int("REDIS_PORT", 6379),
        redis_db=_get_int("REDIS_DB", 0),
        redis_password=os.environ.get("REDIS_PASSWORD") or None,
        redis_socket_timeout=_get_float("REDIS_SOCKET_TIMEOUT", 1.0),
        cache_ttl_seconds=cache_ttl,
        log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        db_connect_retries=_get_int("DB_CONNECT_RETRIES", 10),
        db_connect_retry_delay=_get_float("DB_CONNECT_RETRY_DELAY", 2.0),
    )


settings = load_settings()
