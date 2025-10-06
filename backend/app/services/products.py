"""Product catalog utilities for structured fashion data."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel, Field

from ..core.config import get_settings


class ProductCatalogError(RuntimeError):
    """Raised when product data is unavailable."""


class Product(BaseModel):
    """Representation of a fashion product."""

    product_id: str
    name: str
    brand: str
    category: str
    materials: str
    description: str
    care: str
    price: float
    sizes: list[str] = Field(default_factory=list)
    color: str | None = None
    tags: list[str] = Field(default_factory=list)


class ProductCatalog:
    """In-memory store for product metadata with simple filtering."""

    def __init__(self, path: Path) -> None:
        self._path = self._resolve(path)
        if not self._path.exists():
            msg = f"Product data file not found at {self._path}"
            raise ProductCatalogError(msg)
        self._products = list(self._load(self._path))

    @staticmethod
    def _resolve(path: Path) -> Path:
        candidate = path.expanduser()
        if candidate.is_absolute():
            return candidate

        service_path = Path(__file__).resolve()
        search_roots = [Path.cwd(), service_path.parents[2], service_path.parents[3]]
        candidates = []
        for root in search_roots:
            resolved = (root / candidate).resolve()
            candidates.append(resolved)
            if resolved.exists():
                return resolved
        return candidates[0]

    @staticmethod
    def _load(path: Path) -> Iterable[Product]:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                data = json.loads(line)
                yield Product.model_validate(data)

    def all(self) -> list[Product]:
        return list(self._products)

    def get(self, product_id: str) -> Product | None:
        product_id_lower = product_id.lower()
        for product in self._products:
            if product.product_id.lower() == product_id_lower:
                return product
        return None

    def search(
        self,
        *,
        brand: str | None = None,
        category: str | None = None,
        tag: str | None = None,
        size: str | None = None,
        query: str | None = None,
    ) -> list[Product]:
        candidates = self._products
        if brand:
            brand_lower = brand.lower()
            candidates = [p for p in candidates if p.brand.lower() == brand_lower]
        if category:
            category_lower = category.lower()
            candidates = [p for p in candidates if p.category.lower() == category_lower]
        if tag:
            tag_lower = tag.lower()
            candidates = [p for p in candidates if any(t.lower() == tag_lower for t in p.tags)]
        if size:
            size_lower = size.lower()
            candidates = [p for p in candidates if any(s.lower() == size_lower for s in p.sizes)]
        if query:
            query_lower = query.lower()
            candidates = [
                p
                for p in candidates
                if query_lower in p.name.lower()
                or query_lower in p.description.lower()
                or query_lower in p.materials.lower()
                or query_lower in p.care.lower()
                or query_lower in p.brand.lower()
            ]
        return list(candidates)


@lru_cache
def get_catalog() -> ProductCatalog:
    settings = get_settings()
    if settings.product_data_path is None:
        raise ProductCatalogError("PRODUCT_DATA_PATH is not configured")
    return ProductCatalog(settings.product_data_path)
