"""RAG orchestration powered by LangChain and LangGraph."""
from __future__ import annotations

from typing import Any, TypedDict

try:
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:  # pragma: no cover - optional dependency
    ChatOpenAI = None
    ChatPromptTemplate = None
    RecursiveCharacterTextSplitter = None

try:
    from langgraph.graph import END, StateGraph
except ImportError:  # pragma: no cover - optional dependency
    StateGraph = None
    END = "END"

from ..core.config import get_settings
from .observability import span
from .products import Product, ProductCatalogError, get_catalog
from .vectorstore import InMemoryVectorStore, WeaviateVectorStore, VectorStoreNotAvailable


class ContextItem(TypedDict, total=False):
    """Structured context returned to the caller and LLM."""

    type: str
    id: str | None
    title: str | None
    text: str
    score: float | None
    source: str | None
    metadata: dict[str, Any]


class RAGPipeline:
    """A configurable retrieval-augmented generation pipeline."""

    def __init__(self) -> None:
        settings = get_settings()
        try:
            self._vector_store = WeaviateVectorStore()
        except VectorStoreNotAvailable:
            self._vector_store = InMemoryVectorStore()
        self._llm_model_name = settings.llm_model
        self._chunk_size = settings.chunk_size
        self._chunk_overlap = settings.chunk_overlap
        self._openai_api_key = settings.openai_api_key
        self._openai_api_base = settings.openai_api_base
        self._prompt_template = ChatPromptTemplate.from_template(
            """
You are an assistant for a sustainable fashion brand. Use the provided context to answer the question.

Context:
{context}

Question: {question}
"""
        ) if ChatPromptTemplate else None
        try:
            self._product_catalog = get_catalog()
        except ProductCatalogError:
            self._product_catalog = None

    def build_ingest_splitter(self, chunk_size: int | None = None, chunk_overlap: int | None = None):
        """Return a text splitter for document ingestion."""
        if RecursiveCharacterTextSplitter is None:
            msg = "langchain-text-splitters is required for chunking"
            raise RuntimeError(msg)
        size = chunk_size or self._chunk_size
        overlap = chunk_overlap or self._chunk_overlap
        return RecursiveCharacterTextSplitter(
            chunk_size=size,
            chunk_overlap=overlap,
            separators=["\n\n", "\n", " ", ""],
        )

    def ingest(self, records: list[dict[str, Any]]) -> int:
        """Chunk and upsert records into the vector store."""
        splitter = self.build_ingest_splitter()
        chunked_docs: list[dict[str, Any]] = []
        with span("chunk_documents", count=len(records)):
            for record in records:
                text = record.get("text") or ""
                base_metadata = {k: v for k, v in record.items() if k != "text"}
                for idx, chunk in enumerate(splitter.split_text(text)):
                    chunked_docs.append(
                        {
                            "text": chunk,
                            "doc_id": record.get("doc_id"),
                            "section_index": idx,
                            **base_metadata,
                        }
                    )
        return self._vector_store.upsert_documents(chunked_docs)

    def _build_graph(self):
        """Construct a LangGraph state machine for retrieval and generation."""
        if StateGraph is None:
            msg = "langgraph is required to execute the RAG graph"
            raise RuntimeError(msg)
        graph = StateGraph(dict)

        def retrieve(state: dict[str, Any]) -> dict[str, Any]:
            query = state["question"]
            product_filters = state.get("product_filters") or {}
            top_k = state.get("top_k")
            if top_k is None:
                top_k = 5
            results = self.retrieve(query, top_k=top_k, product_filters=product_filters)
            return {"context": results}

        def generate(state: dict[str, Any]) -> dict[str, Any]:
            question = state["question"]
            context_docs = state.get("context", [])
            return {"answer": self.generate_answer(question, context_docs)}

        graph.add_node("retrieve", retrieve)
        graph.add_node("generate", generate)
        graph.set_entry_point("retrieve")
        graph.add_edge("retrieve", "generate")
        graph.add_edge("generate", END)
        return graph.compile()

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        product_filters: dict[str, str | None] | None = None,
    ) -> list[ContextItem]:
        """Retrieve documents and enrich them with catalog metadata."""
        contexts: list[ContextItem] = []
        with span("vector_retrieve", query=query, top_k=top_k):
            payloads = self._vector_store.query(query, top_k=top_k)
        contexts.extend(self._format_document_payloads(payloads))
        contexts.extend(self._build_product_context(query, product_filters))
        return contexts

    def _format_document_payloads(self, payloads: list[dict[str, Any]]) -> list[ContextItem]:
        formatted: list[ContextItem] = []
        for payload in payloads:
            metadata = payload.get("payload", {})
            formatted.append(
                ContextItem(
                    type="document",
                    id=payload.get("id"),
                    title=metadata.get("title") or metadata.get("doc_id"),
                    text=metadata.get("text", ""),
                    score=payload.get("score"),
                    source="vector_store",
                    metadata={k: v for k, v in metadata.items() if k != "text"},
                )
            )
        return formatted

    def _build_product_context(
        self,
        query: str,
        product_filters: dict[str, str | None] | None,
    ) -> list[ContextItem]:
        if self._product_catalog is None:
            return []
        filters = {k: v for k, v in (product_filters or {}).items() if v}
        matches: list[Product] = []
        if filters:
            matches = self._product_catalog.search(**filters)
        if not matches:
            matches = self._product_catalog.lookup_from_text(query)
        contexts: list[ContextItem] = []
        for product in matches[:3]:
            contexts.append(
                ContextItem(
                    type="product",
                    id=product.product_id,
                    title=product.name,
                    text=self._format_product_summary(product),
                    score=None,
                    source="product_catalog",
                    metadata=product.model_dump(),
                )
            )
        return contexts

    @staticmethod
    def _format_product_summary(product: Product) -> str:
        return (
            f"Brand: {product.brand}\n"
            f"Category: {product.category}\n"
            f"Materials: {product.materials}\n"
            f"Care: {product.care}\n"
            f"Sizes: {', '.join(product.sizes) if product.sizes else 'N/A'}\n"
            f"Tags: {', '.join(product.tags) if product.tags else 'None'}"
        )

    def generate_answer(self, question: str, context_docs: list[ContextItem]) -> str:
        """Generate an answer using the configured LLM or a deterministic fallback."""
        context_text = self._render_prompt_context(context_docs)
        if not context_text:
            return "I could not find supporting information for that question."
        if ChatOpenAI is None or self._prompt_template is None or not self._openai_api_key:
            return self._fallback_answer(context_docs)
        init_kwargs: dict[str, Any] = {"model": self._llm_model_name, "temperature": 0.2}
        if self._openai_api_key:
            init_kwargs["api_key"] = self._openai_api_key
        if self._openai_api_base:
            init_kwargs["base_url"] = self._openai_api_base
        llm = ChatOpenAI(**init_kwargs)
        chain = self._prompt_template | llm
        with span("llm_generate", question_length=len(question)):
            response = chain.invoke({"question": question, "context": context_text})
        return response.content if hasattr(response, "content") else str(response)

    @staticmethod
    def _fallback_answer(context_docs: list[ContextItem]) -> str:
        snippets = [item.get("text", "") for item in context_docs if item.get("text")]
        if not snippets:
            return "I could not find supporting information for that question."
        preview = "\n\n".join(snippets[:2])
        return (
            "I'm operating without an LLM backend right now, but here is the most relevant information I found:\n\n"
            f"{preview}"
        )

    @staticmethod
    def _render_prompt_context(context_docs: list[ContextItem]) -> str:
        segments: list[str] = []
        for item in context_docs:
            text = item.get("text", "")
            if not text:
                continue
            title = item.get("title") or item.get("type", "Context")
            segments.append(f"{title}:\n{text}")
        return "\n\n".join(segments)

    def run(
        self,
        question: str,
        *,
        top_k: int | None = None,
        product_filters: dict[str, str | None] | None = None,
    ) -> dict[str, Any]:
        """Execute the graph for a given question."""
        graph = self._build_graph()
        state = {
            "question": question,
            "product_filters": product_filters or {},
            "top_k": top_k if top_k is not None else 5,
        }
        with span("rag_run", question=question, top_k=state["top_k"]):
            result = graph.invoke(state)
        result.setdefault("context", [])
        if "answer" not in result:
            result["answer"] = self.generate_answer(question, result["context"])
        return result
