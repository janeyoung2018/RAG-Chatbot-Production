"""Phoenix observability helpers backed by OpenTelemetry instrumentation."""
from __future__ import annotations

import json
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import logging
import socket
from typing import Any, Iterator, Mapping
from urllib.parse import urlparse, urlunparse
from uuid import uuid4

import phoenix as px
from phoenix.otel import register
from opentelemetry.trace import Status, StatusCode


_trace_id_var: ContextVar[str | None] = ContextVar("phoenix_trace_id", default=None)
_tracer: Any | None = None
_phoenix_ui_base: str | None = None
_initialization_attempted = False
_logger = logging.getLogger(__name__)


@dataclass
class TraceHandle:
    """Metadata for an instrumented request that can be surfaced to clients."""

    trace_id: str | None
    trace_url: str | None


class _SpanAdapter:
    """Proxy around an OpenTelemetry span that adds Phoenix helpers."""

    __slots__ = ("_span",)

    def __init__(self, span: Any) -> None:
        self._span = span

    def set_input(self, value: Any, *, label: str | None = None) -> None:
        """Record structured input payloads."""
        try:
            self._span.set_input(label, value)
        except Exception:  # pragma: no cover - defensive guard.
            pass

    def set_output(self, value: Any, *, label: str | None = None) -> None:
        """Record structured output payloads."""
        try:
            self._span.set_output(label, value)
        except Exception:  # pragma: no cover - defensive guard.
            pass


    def _set_attribute_safe(self, key: str, value: Any) -> None:
        try:
            self._span.set_attribute(key, value)
        except Exception:  # pragma: no cover - defensive guard.
            pass

    def __getattr__(self, name: str) -> Any:
        return getattr(self._span, name)


def is_enabled() -> bool:
    """Return True when Phoenix tracing has been configured successfully."""
    _initialize_tracer()
    return _tracer is not None


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[Any | None]:
    """Context manager that records a Phoenix span when available."""
    _initialize_tracer()
    span_attributes = dict(attributes)
    trace_id = span_attributes.get("trace_id") or _trace_id_var.get()
    if trace_id:
        span_attributes["trace_id"] = trace_id
    if _tracer is None:
        yield None
        return
    with _tracer.start_as_current_span(name) as current_span:
        _set_span_attributes(current_span, span_attributes)
        wrapped = _SpanAdapter(current_span)
        try:
            yield wrapped
        except Exception as exc:  # pragma: no cover - defensive guard.
            _record_error(current_span, exc)
            raise


@contextmanager
def trace_run(name: str, **attributes: Any) -> Iterator[TraceHandle]:
    """Establish a root span and propagate a generated trace id."""
    _initialize_tracer()
    fallback_trace_id = uuid4().hex
    if _tracer is None:
        token = _trace_id_var.set(fallback_trace_id)
        try:
            yield TraceHandle(trace_id=fallback_trace_id, trace_url=_build_trace_url(fallback_trace_id))
        finally:
            _trace_id_var.reset(token)
        return
    with _tracer.start_as_current_span(name) as root_span:
        trace_id = _extract_trace_id(root_span) or fallback_trace_id
        token = _trace_id_var.set(trace_id)
        try:
            root_attributes = dict(attributes)
            root_attributes.setdefault("trace_id", trace_id)
            question_value = attributes.get("question")
            if question_value is not None and "openinference.input.query" not in root_attributes:
                root_attributes["openinference.input.query"] = question_value
            _set_span_attributes(root_span, root_attributes)
            handle = TraceHandle(trace_id=trace_id, trace_url=_build_trace_url(trace_id))
            try:
                yield handle
            except Exception as exc:  # pragma: no cover - defensive guard.
                _record_error(root_span, exc)
                raise
        finally:
            _trace_id_var.reset(token)


def _initialize_tracer() -> None:
    """Create the Phoenix tracer provider lazily."""
    global _tracer, _phoenix_ui_base, _initialization_attempted
    if _tracer is not None or _initialization_attempted:
        return
    _initialization_attempted = True
    if px is None or register is None:
        _logger.info(
            "Phoenix tracing disabled because the 'phoenix' package is not installed; spans will be no-ops."
        )
        return
    try:
        from ..core.config import get_settings
    except Exception:  # pragma: no cover - defensive guard.
        get_settings = None  # type: ignore[assignment]
    settings = get_settings() if get_settings else None  # type: ignore[operator]
    project_name = getattr(settings, "app_name", None) or "chatbot"
    endpoint_base = getattr(settings, "phoenix_endpoint", None)
    normalized_endpoint = _normalize_endpoint(endpoint_base)
    _phoenix_ui_base = normalized_endpoint
    collector_endpoint = _build_collector_endpoint(normalized_endpoint)
    if collector_endpoint is None:
        _logger.warning("Phoenix tracing disabled because PHOENIX_ENDPOINT is not configured.")
        return
    try:
        px.launch_app()
    except Exception:  # pragma: no cover - best-effort launch.
        pass
    try:
        tracer_provider = register(project_name=project_name, endpoint=collector_endpoint, auto_instrument=False)
    except TypeError:
        tracer_provider = register(project_name=project_name, endpoint=collector_endpoint)
    except Exception as exc:  # pragma: no cover - registration failure.
        _logger.warning("Phoenix tracing registration failed: %s", exc)
        return
    try:
        _tracer = tracer_provider.get_tracer(__name__)
    except Exception as exc:  # pragma: no cover - tracer retrieval failure.
        _logger.warning("Phoenix tracing disabled because tracer could not be created: %s", exc)
        _tracer = None


def _build_collector_endpoint(endpoint: str | None) -> str | None:
    if not endpoint:
        return None
    base = endpoint.rstrip("/")
    if base.endswith("/v1/traces"):
        return base
    return f"{base}/v1/traces"


def _build_trace_url(trace_id: str | None) -> str | None:
    if trace_id is None:
        return None
    endpoint = _phoenix_ui_base
    if not endpoint:
        try:
            from ..core.config import get_settings
        except Exception:  # pragma: no cover - defensive guard.
            return None
        endpoint = get_settings().phoenix_endpoint
    if not endpoint:
        return None
    base = endpoint.rstrip("/")
    return f"{base}/traces/{trace_id}"


def _set_span_attributes(span: Any, attributes: Mapping[str, Any]) -> None:
    for key, value in attributes.items():
        if value is None:
            continue
        try:
            span.set_attribute(key, value)
        except Exception:  # pragma: no cover - attribute assignment failure.
            continue


def _record_error(span: Any, error: Exception) -> None:
    try:
        span.record_exception(error)
    except Exception:  # pragma: no cover - defensive guard.
        pass
    if Status is not None and StatusCode is not None:
        try:
            span.set_status(Status(StatusCode.ERROR))
        except Exception:  # pragma: no cover - defensive guard.
            pass


def _extract_trace_id(span: Any) -> str | None:
    try:
        context = span.get_span_context()
    except Exception:  # pragma: no cover - defensive guard.
        return None
    if context is None:
        return None
    trace_id = getattr(context, "trace_id", 0)
    if not trace_id:
        return None
    try:
        return f"{int(trace_id):032x}"
    except Exception:  # pragma: no cover - defensive guard.
        return None


def _normalize_endpoint(endpoint: str | None) -> str | None:
    if not endpoint:
        return None
    try:
        parsed = urlparse(endpoint)
    except Exception:  # pragma: no cover - defensive guard.
        return endpoint
    host = parsed.hostname
    if not host:
        return endpoint
    try:
        socket.gethostbyname(host)
        return endpoint
    except OSError:
        fallback_host = "127.0.0.1"
        netloc = fallback_host
        if parsed.port:
            netloc = f"{fallback_host}:{parsed.port}"
        normalized = urlunparse(parsed._replace(netloc=netloc))
        _logger.warning(
            "Phoenix endpoint host '%s' is not resolvable; falling back to '%s'.",
            host,
            normalized,
        )
        return normalized


def _serialize_span_value(value: Any) -> Any:
    if isinstance(value, (str, bool, int, float)):
        return value
    try:
        return json.dumps(value, default=str)
    except Exception:  # pragma: no cover - defensive guard.
        return str(value)
