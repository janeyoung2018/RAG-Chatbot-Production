"""API route handlers for the FastAPI backend."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from ..core.config import get_settings
from ..services.products import Product, ProductCatalogError, get_catalog
from ..services.rag import RAGPipeline


router = APIRouter()
settings = get_settings()

try:
    pipeline = RAGPipeline()
except RuntimeError:
    pipeline = None


def _get_product_catalog():
    try:
        return get_catalog()
    except ProductCatalogError as exc:  # pragma: no cover - relies on runtime config
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


class HealthResponse(BaseModel):
    """Health check response payload."""

    app: str
    version: str
    pipeline_ready: bool


class IngestRequest(BaseModel):
    """Payload for ingesting knowledge base documents."""

    documents: list[dict[str, Any]]


class IngestResponse(BaseModel):
    """Response after ingesting documents."""

    records_ingested: int


class QueryRequest(BaseModel):
    """Query payload for the RAG pipeline."""

    question: str
    top_k: int | None = 5


class QueryResponse(BaseModel):
    """Response for a query to the RAG pipeline."""

    answer: str
    context: list[Any]


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Return application health metadata."""
    return HealthResponse(
        app=settings.app_name,
        version=settings.api_version,
        pipeline_ready=pipeline is not None,
    )


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
def ingest_documents(payload: IngestRequest) -> IngestResponse:
    """Ingest documents into the vector store."""
    if pipeline is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Pipeline not available")
    count = pipeline.ingest(payload.documents)
    return IngestResponse(records_ingested=count)


@router.post("/query", response_model=QueryResponse)
def query_pipeline(payload: QueryRequest) -> QueryResponse:
    """Execute a RAG query."""
    if pipeline is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Pipeline not available")
    results = pipeline.retrieve(payload.question, top_k=payload.top_k or 5)
    answer = pipeline.generate_answer(payload.question, results)
    return QueryResponse(answer=answer, context=results)


@router.get("/products", response_model=list[Product])
def list_products(
    brand: str | None = Query(None, description="Exact brand match"),
    category: str | None = Query(None, description="Exact category match"),
    tag: str | None = Query(None, description="Exact tag match"),
    size: str | None = Query(None, description="Filter products that include the size"),
    query: str | None = Query(None, description="Full-text search across name, description, materials, and care"),
) -> list[Product]:
    """Return catalog products with optional filters."""
    catalog = _get_product_catalog()
    return catalog.search(brand=brand, category=category, tag=tag, size=size, query=query)


@router.get("/products/{product_id}", response_model=Product)
def get_product(product_id: str) -> Product:
    """Return a single product by identifier."""
    catalog = _get_product_catalog()
    product = catalog.get(product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product
