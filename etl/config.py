"""Configuration for the offline ETL pipeline."""
from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field


class ETLConfig(BaseModel):
    """Configuration parameters for ETL runs."""

    documents_path: Annotated[Path, Field(default=Path("../data/documents.jsonl"))]
    chunk_size: int = 512
    chunk_overlap: int = 50
    output_path: Annotated[Path, Field(default=Path("./artifacts/chunked_documents.jsonl"))]


DEFAULT_CONFIG = ETLConfig()
