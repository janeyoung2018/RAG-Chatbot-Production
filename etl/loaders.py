"""Data loading utilities."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator


def read_jsonl(path: Path) -> Iterator[dict]:
    """Yield JSON objects from a line-delimited file."""
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            yield json.loads(line)
