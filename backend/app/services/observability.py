"""Phoenix observability helpers."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterator
from uuid import uuid4

try:
    from phoenix.trace.dsl import Span
    from phoenix.trace.dsl import Tracer
except ImportError:  # pragma: no cover - optional dependency
    Span = None
    Tracer = None


_tracer: Tracer | None = Tracer() if Tracer else None
_trace_id_var: ContextVar[str | None] = ContextVar("phoenix_trace_id", default=None)


@dataclass
class TraceHandle:
    """Metadata for an instrumented request that can be surfaced to clients."""

    trace_id: str | None
    trace_url: str | None


def is_enabled() -> bool:
    """Return True if Phoenix tracing is configured."""
    return _tracer is not None


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[None]:
    """Context manager that records a Phoenix span when available."""
    trace_id = attributes.get("trace_id") or _trace_id_var.get()
    if trace_id:
        attributes.setdefault("trace_id", trace_id)
    if _tracer is None or Span is None:
        yield
        return
    with _tracer.span(name=name, **attributes):
        yield


def _build_trace_url(trace_id: str | None) -> str | None:
    if trace_id is None:
        return None
    try:
        from ..core.config import get_settings
    except Exception:  # pragma: no cover - defensive fallback
        return None
    endpoint = get_settings().phoenix_endpoint
    if not endpoint:
        return None
    base = endpoint.rstrip("/")
    return f"{base}/traces/{trace_id}"


@contextmanager
def trace_run(name: str, **attributes: Any) -> Iterator[TraceHandle]:
    """Establish a root span and propagate a generated trace id."""
    trace_id = uuid4().hex
    token = _trace_id_var.set(trace_id)
    try:
        with span(name, trace_id=trace_id, **attributes):
            yield TraceHandle(trace_id=trace_id, trace_url=_build_trace_url(trace_id))
    finally:
        _trace_id_var.reset(token)
