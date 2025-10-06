"""Phoenix observability helpers."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

try:
    from phoenix.trace.dsl import Span
    from phoenix.trace.dsl import Tracer
except ImportError:  # pragma: no cover - optional dependency
    Span = None
    Tracer = None


_tracer: Tracer | None = Tracer() if Tracer else None


def is_enabled() -> bool:
    """Return True if Phoenix tracing is configured."""
    return _tracer is not None


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[None]:
    """Context manager that records a Phoenix span when available."""
    if _tracer is None or Span is None:
        yield
        return
    with _tracer.span(name=name, **attributes):
        yield
