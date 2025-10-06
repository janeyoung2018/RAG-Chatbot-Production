"""Utility script to push documents to the backend ingestion endpoint."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests


def load_documents(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest documents into the backend")
    parser.add_argument("--endpoint", default="http://localhost:8000/api/ingest")
    parser.add_argument("--path", type=Path, default=Path("../data/documents.jsonl"))
    args = parser.parse_args()

    documents = load_documents(args.path)
    response = requests.post(args.endpoint, json={"documents": documents}, timeout=120)
    response.raise_for_status()
    print(response.json())


if __name__ == "__main__":
    main()
