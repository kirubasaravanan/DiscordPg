from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    database_echo: bool = False

    # No default — a JWT secret must be explicit per environment, never baked in.
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # Storage backend (docs/ARCHITECTURE.md §4.6) — "local" for dev (default,
    # no external dependency), "s3" for Cloudflare R2 / AWS S3 in production.
    storage_backend: Literal["local", "s3"] = "local"
    storage_presigned_url_expire_seconds: int = 900

    # Local backend only.
    storage_local_path: str = "./storage_data"
    storage_local_base_url: str = "http://localhost:8000"

    # S3/R2-compatible backend only — all optional since they're unused in
    # local mode. storage_s3_endpoint_url is what makes this work against R2
    # instead of real AWS: set it to the R2 account endpoint and region to
    # "auto"; leave both unset (the boto3 default) for real AWS S3.
    storage_s3_bucket: str | None = None
    storage_s3_endpoint_url: str | None = None
    storage_s3_region: str = "auto"
    storage_s3_access_key_id: str | None = None
    storage_s3_secret_access_key: str | None = None

    # Discord notification delivery (docs/ARCHITECTURE.md §9, §12) — the same
    # bot token discord_bot/ uses to receive commands also sends outbound
    # notifications via plain REST, no gateway connection needed for that.
    # Optional: unset until Phase 6 wires actual scheduled jobs to call it.
    discord_bot_token: str | None = None
    discord_management_channel_id: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
