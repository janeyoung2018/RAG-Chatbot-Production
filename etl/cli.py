"""Command line interface for ETL routines."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .chunker import Chunker
from .config import ETLConfig, DEFAULT_CONFIG
from .loaders import read_jsonl


def run_chunking(config: ETLConfig) -> Path:
    """Chunk the source documents and persist them to disk."""
    chunker = Chunker(chunk_size=config.chunk_size, chunk_overlap=config.chunk_overlap)
    records = list(read_jsonl(config.documents_path))
    chunked = chunker.transform(records)
    config.output_path.parent.mkdir(parents=True, exist_ok=True)
    with config.output_path.open("w", encoding="utf-8") as handle:
        for item in chunked:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    return config.output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chunk fashion knowledge documents")
    parser.add_argument("--documents", type=Path, default=DEFAULT_CONFIG.documents_path)
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CONFIG.chunk_size)
    parser.add_argument("--chunk-overlap", type=int, default=DEFAULT_CONFIG.chunk_overlap)
    parser.add_argument("--output", type=Path, default=DEFAULT_CONFIG.output_path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = ETLConfig(
        documents_path=args.documents,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        output_path=args.output,
    )
    output = run_chunking(config)
    print(f"Chunked documents written to {output}")


if __name__ == "__main__":
    main()
