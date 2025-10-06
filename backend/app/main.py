"""FastAPI application entry point."""
from __future__ import annotations

import logging
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .core.config import get_settings
from .core.logging import configure_logging


settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("rag_chatbot.api")

app = FastAPI(title=settings.app_name, version=settings.api_version)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Emit structured logs for each request."""
    start = perf_counter()
    response = await call_next(request)
    duration_ms = (perf_counter() - start) * 1000
    logger.info(
        "request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "client_ip": request.client.host if request.client else None,
        },
    )
    return response


@app.get("/")
def root() -> dict[str, str]:
    """Return a simple welcome message."""
    return {"message": "RAG chatbot backend is running"}
