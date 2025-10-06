"""Application configuration utilities."""
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Base settings loaded from environment variables."""

    app_name: str = Field(default="RAG Chatbot Backend")
    api_version: str = Field(default="v1")
    weaviate_url: str = Field(default="http://weaviate:8080")
    weaviate_api_key: str | None = Field(default=None)
    openai_api_key: str | None = Field(default=None)
    openai_api_base: str | None = Field(default=None)
    phoenix_endpoint: str | None = Field(default="http://phoenix:6006")
    vectorizer: str = Field(default="text2vec-openai")
    embeddings_model: str = Field(default="text-embedding-3-small")
    llm_model: str = Field(default="gpt-4o-mini")
    vector_collection_name: str = Field(default="FashionDocs")
    chunk_size: int = Field(default=512)
    chunk_overlap: int = Field(default=50)
    product_data_path: Path | None = Field(default=Path("../data/products.jsonl"))
    api_key: str | None = Field(default=None)
    rate_limit_per_minute: int = Field(default=60)
    rate_limit_window_seconds: int = Field(default=60)
    log_level: str = Field(default="INFO")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
