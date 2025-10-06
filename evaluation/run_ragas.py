"""Run RAG evaluation using the ragas library and Phoenix tracing."""
from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from ragas import EvaluationDataset
from ragas.metrics import (
    answer_relevancy,
    faithfulness,
    context_relevancy,
    context_precision,
)
from ragas.evaluation import evaluate


@dataclass
class EvalConfig:
    """Configuration for running the evaluation."""

    backend_url: str
    qa_path: Path
    concurrency: int = 5


async def fetch_answer(client: httpx.AsyncClient, question: str) -> dict[str, Any]:
    """Query the backend API for an answer and retrieved context."""
    response = await client.post("/api/query", json={"question": question, "top_k": 5})
    response.raise_for_status()
    return response.json()


async def build_dataset(config: EvalConfig) -> EvaluationDataset:
    """Assemble a ragas dataset by calling the backend for each question."""
    with config.qa_path.open("r", encoding="utf-8") as handle:
        qa_records = [json.loads(line) for line in handle if line.strip()]

    async with httpx.AsyncClient(base_url=config.backend_url, timeout=30.0) as client:
        tasks = [fetch_answer(client, record["question"]) for record in qa_records]
        responses = await asyncio.gather(*tasks)

    return EvaluationDataset.from_dict(
        {
            "question": [record["question"] for record in qa_records],
            "answer": [response["answer"] for response in responses],
            "contexts": [response.get("context", []) for response in responses],
            "ground_truth": [record.get("ground_truth", "") for record in qa_records],
        }
    )


async def run(config: EvalConfig) -> None:
    dataset = await build_dataset(config)
    result = evaluate(
        dataset,
        metrics=[answer_relevancy, faithfulness, context_precision, context_relevancy],
    )
    print(result)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the RAG system using ragas metrics")
    parser.add_argument("--backend-url", default="http://localhost:8000")
    parser.add_argument("--qa-path", type=Path, default=Path("../data/qa.jsonl"))
    args = parser.parse_args()
    config = EvalConfig(backend_url=args.backend_url, qa_path=args.qa_path)
    asyncio.run(run(config))


if __name__ == "__main__":
    main()
