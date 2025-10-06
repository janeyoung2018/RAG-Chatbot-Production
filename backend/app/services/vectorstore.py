"""Abstraction over the Weaviate vector database."""
from __future__ import annotations

from typing import Any, Iterable
from urllib.parse import urlparse

try:
    import weaviate
    from weaviate.classes.init import AuthApiKey
except ImportError:  # pragma: no cover - optional dependency
    weaviate = None
    AuthApiKey = None

from ..core.config import get_settings


class VectorStoreNotAvailable(RuntimeError):
    """Raised when the vector store client is unavailable."""


class WeaviateVectorStore:
    """Simple wrapper around the Weaviate client."""

    def __init__(self) -> None:
        settings = get_settings()
        if weaviate is None:
            msg = "weaviate-client is not installed; install it to use the vector store"
            raise VectorStoreNotAvailable(msg)

        auth = None
        if settings.weaviate_api_key and AuthApiKey:
            auth = AuthApiKey(api_key=settings.weaviate_api_key)

        parsed = urlparse(settings.weaviate_url)
        host = parsed.hostname or "weaviate"
        port = parsed.port or (443 if parsed.scheme == "https" else 8080)
        secure = parsed.scheme == "https"

        self._client = weaviate.connect_to_custom(
            http_host=host,
            http_port=port,
            http_secure=secure,
            auth_client_secret=auth,
        )
        self._collection_name = "FashionDocs"

    def ensure_collection(self) -> None:
        """Ensure the target collection exists."""
        schema = {
            "class": self._collection_name,
            "vectorizer": "text2vec-openai",
            "moduleConfig": {
                "text2vec-openai": {
                    "model": get_settings().embeddings_model,
                }
            },
        }
        if not self._client.collections.exists(self._collection_name):
            self._client.collections.create(schema)

    def upsert_documents(self, documents: Iterable[dict[str, Any]]) -> int:
        """Upsert documents into Weaviate; returns record count."""
        self.ensure_collection()
        collection = self._client.collections.get(self._collection_name)
        count = 0
        for doc in documents:
            collection.data.insert(doc)
            count += 1
        return count

    def query(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Query for the top-k most similar documents."""
        if not query:
            return []
        collection = self._client.collections.get(self._collection_name)
        results = collection.query.near_text(query=query, limit=top_k)
        payloads: list[dict[str, Any]] = []
        for item in results.objects:
            payloads.append(
                {
                    "id": item.uuid,
                    "score": item.distance,
                    "payload": item.properties,
                }
            )
        return payloads
