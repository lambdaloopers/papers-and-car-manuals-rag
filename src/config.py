from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str = Field(alias="OPENAI_API_KEY")
    openai_chat_model: str = Field(default="gpt-4o-mini", alias="OPENAI_CHAT_MODEL")
    openai_embedding_model: str = Field(
        default="text-embedding-3-small",
        alias="OPENAI_EMBEDDING_MODEL",
    )
    openai_vision_model: str = Field(default="gpt-4o-mini", alias="OPENAI_VISION_MODEL")
    database_url: str = Field(alias="DATABASE_URL")

    chunk_size: int = Field(default=1200, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=150, alias="CHUNK_OVERLAP")
    retrieval_k_lexical: int = Field(default=10, alias="RETRIEVAL_K_LEXICAL")
    retrieval_k_vector: int = Field(default=10, alias="RETRIEVAL_K_VECTOR")
    retrieval_k_final: int = Field(default=8, alias="RETRIEVAL_K_FINAL")
    rrf_k: int = Field(default=60, alias="RRF_K")

    data_dir: Path = Field(default=Path("./data"), alias="DATA_DIR")
    assets_dir: Path = Field(default=Path("./data/assets"), alias="ASSETS_DIR")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
