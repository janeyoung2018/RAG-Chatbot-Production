"""Document chunking utilities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from langchain_text_splitters import RecursiveCharacterTextSplitter


@dataclass
class Chunker:
    """Split raw documents into overlapping chunks."""

    chunk_size: int = 512
    chunk_overlap: int = 50

    def split(self, text: str) -> list[str]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", " ", ""],
        )
        return splitter.split_text(text)

    def transform(self, records: Iterable[dict[str, str]]) -> list[dict[str, str | int]]:
        """Return chunked representation for persistence."""
        chunked: list[dict[str, str | int]] = []
        for record in records:
            text = record.get("text", "")
            base = {key: value for key, value in record.items() if key != "text"}
            for idx, chunk in enumerate(self.split(text)):
                chunked.append({**base, "text": chunk, "chunk_index": idx})
        return chunked
