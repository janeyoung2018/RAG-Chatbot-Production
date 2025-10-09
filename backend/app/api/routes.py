"""API route handlers for the FastAPI backend."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..core.config import get_settings
from ..core.rate_limiting import enforce_rate_limit
from ..core.security import require_api_key
from ..services.products import Product, ProductCatalogError, get_catalog
from ..services.rag import RAGPipeline
from ..services.observability import trace_run


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
    brand: str | None = None
    category: str | None = None
    tag: str | None = None
    size: str | None = None


class ContextItemModel(BaseModel):
    """Structured evidence returned alongside answers."""

    type: str
    id: str | None = None
    title: str | None = None
    text: str = Field(default="")
    score: float | None = None
    source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class QueryResponse(BaseModel):
    """Response for a query to the RAG pipeline."""

    answer: str
    context: list[ContextItemModel]
    trace_id: str | None = None
    trace_url: str | None = None


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Return application health metadata."""
    return HealthResponse(
        app=settings.app_name,
        version=settings.api_version,
        pipeline_ready=pipeline is not None,
    )


@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_api_key), Depends(enforce_rate_limit)],
)
def ingest_documents(payload: IngestRequest) -> IngestResponse:
    """Ingest documents into the vector store."""
    if pipeline is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Pipeline not available")
    count = pipeline.ingest(payload.documents)
    return IngestResponse(records_ingested=count)


@router.post(
    "/query",
    response_model=QueryResponse,
    dependencies=[Depends(require_api_key), Depends(enforce_rate_limit)],
)
def query_pipeline(payload: QueryRequest) -> QueryResponse:
    """Execute a RAG query."""
    if pipeline is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Pipeline not available")
    product_filters = {
        "brand": payload.brand,
        "category": payload.category,
        "tag": payload.tag,
        "size": payload.size,
    }
    with trace_run("rag_query", question=payload.question, top_k=payload.top_k) as trace:
        run_result = pipeline.run(
            payload.question,
            top_k=payload.top_k,
            product_filters=product_filters,
        )
        answer = run_result.get("answer", "")
        results = run_result.get("context", [])
    return QueryResponse(
        answer=answer,
        context=[ContextItemModel.model_validate(item) for item in results],
        trace_id=trace.trace_id,
        trace_url=trace.trace_url,
    )


@router.get(
    "/products",
    response_model=list[Product],
    dependencies=[Depends(require_api_key)],
)
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


@router.get(
    "/products/{product_id}",
    response_model=Product,
    dependencies=[Depends(require_api_key)],
)
def get_product(product_id: str) -> Product:
    """Return a single product by identifier."""
    catalog = _get_product_catalog()
    product = catalog.get(product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product
