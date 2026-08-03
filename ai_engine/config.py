from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """No `database_url` field anywhere in this class — deliberately.

    ai_engine/ has no database credentials in its runtime config, which
    makes docs/ROADMAP.md Phase 6's definition of done ("AI service has no
    database credentials in its runtime config") verifiable by reading
    this file, not just documented. See docs/AI_DESIGN.md §1.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ollama_host: str = "http://localhost:11434"
    # Separate chat/embedding models — see docs/AI_DESIGN.md §3 for why a
    # dedicated embedding model is used instead of Qwen3 8B for embeddings too.
    ollama_chat_model: str = "qwen3:8b"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_timeout_seconds: float = 30.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
