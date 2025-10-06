"""Utility script to push documents to the backend ingestion endpoint."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import requests


def load_documents(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> None:
    default_path = Path(os.getenv("DOCUMENTS_PATH", "../data/documents.jsonl"))
    parser = argparse.ArgumentParser(description="Ingest documents into the backend")
    parser.add_argument("--endpoint", default=os.getenv("INGEST_ENDPOINT", "http://localhost:8000/api/ingest"))
    parser.add_argument("--path", type=Path, default=default_path)
    parser.add_argument("--api-key", default=os.getenv("API_KEY"))
    args = parser.parse_args()

    documents = load_documents(args.path)
    headers = {"X-API-Key": args.api_key} if args.api_key else None
    response = requests.post(args.endpoint, json={"documents": documents}, headers=headers, timeout=120)
    response.raise_for_status()
    print(response.json())


if __name__ == "__main__":
    main()
