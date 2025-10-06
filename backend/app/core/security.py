"""Security helpers for API authentication."""
from __future__ import annotations

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from .config import get_settings


_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(api_key: str | None = Security(_api_key_header)) -> str | None:
    """Validate the API key when one is configured."""
    settings = get_settings()
    expected = settings.api_key
    if expected is None:
        # Authentication disabled
        return None
    if api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return expected
