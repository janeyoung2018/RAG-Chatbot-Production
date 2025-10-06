"""CI smoke checks for ingestion and retrieval flows."""
from __future__ import annotations

import argparse
import os
from typing import Sequence

import requests


def run_checks(backend_url: str, api_key: str | None, questions: Sequence[dict[str, str]]) -> None:
    headers = {"X-API-Key": api_key} if api_key else None
    for payload in questions:
        request_body = {"question": payload["question"], "top_k": 3}
        if "brand" in payload:
            request_body["brand"] = payload["brand"]
        if "category" in payload:
            request_body["category"] = payload["category"]
        if "tag" in payload:
            request_body["tag"] = payload["tag"]
        if "size" in payload:
            request_body["size"] = payload["size"]
        response = requests.post(
            f"{backend_url.rstrip('/')}/api/query",
            json=request_body,
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("answer"):
            msg = f"Empty answer returned for question: {payload['question']}"
            raise RuntimeError(msg)
        context = data.get("context") or []
        if len(context) == 0:
            msg = f"No context retrieved for question: {payload['question']}"
            raise RuntimeError(msg)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run smoke checks against the RAG backend")
    parser.add_argument("--backend-url", default=os.getenv("BACKEND_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--api-key", default=os.getenv("API_KEY"))
    args = parser.parse_args()

    questions = [
        {"question": "How should I care for the organic cotton joggers?"},
        {"question": "Do you have recommendations for summer dresses?", "category": "Dresses"},
        {"question": "Show me eco-friendly outerwear options", "tag": "sustainable"},
    ]

    run_checks(args.backend_url, args.api_key, questions)
    print(f"Smoke evaluation passed for {len(questions)} queries.")


if __name__ == "__main__":
    main()
