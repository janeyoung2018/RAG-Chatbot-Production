"""Application configuration utilities."""
from functools import lru_cache
from pathlib import Path

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """Base settings loaded from environment variables."""

    app_name: str = Field(default="RAG Chatbot Backend")
    api_version: str = Field(default="v1")
    weaviate_url: str = Field(default="http://weaviate:8080")
    weaviate_api_key: str | None = Field(default=None)
    openai_api_key: str | None = Field(default=None)
    phoenix_endpoint: str | None = Field(default="http://phoenix:6006")
    embeddings_model: str = Field(default="text-embedding-3-small")
    llm_model: str = Field(default="gpt-4o-mini")
    product_data_path: Path | None = Field(default=Path("../data/products.jsonl"))

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
