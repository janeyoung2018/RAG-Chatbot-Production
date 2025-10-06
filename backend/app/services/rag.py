"""RAG orchestration powered by LangChain and LangGraph."""
from __future__ import annotations

from typing import Any

try:
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from langchain_core.documents import Document
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.runnables import RunnableLambda, RunnableParallel
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:  # pragma: no cover - optional dependency
    ChatOpenAI = None
    OpenAIEmbeddings = None
    Document = None
    ChatPromptTemplate = None
    RunnableLambda = None
    RunnableParallel = None
    RecursiveCharacterTextSplitter = None

try:
    from langgraph.graph import END, StateGraph
except ImportError:  # pragma: no cover - optional dependency
    StateGraph = None
    END = "END"

from ..core.config import get_settings
from .observability import span
from .vectorstore import WeaviateVectorStore, VectorStoreNotAvailable


def _map_payload_to_documents(payloads: list[dict[str, Any]]) -> list[Any]:
    """Convert vector store payloads into LangChain documents."""
    if Document is None:
        return payloads
    documents: list[Any] = []
    for payload in payloads:
        metadata = payload.get("payload", {})
        documents.append(
            Document(
                page_content=metadata.get("text", ""),
                metadata={k: v for k, v in metadata.items() if k != "text"},
            )
        )
    return documents


class RAGPipeline:
    """A configurable retrieval-augmented generation pipeline."""

    def __init__(self) -> None:
        settings = get_settings()
        self._vector_store = None
        try:
            self._vector_store = WeaviateVectorStore()
        except VectorStoreNotAvailable:
            self._vector_store = None
        self._llm_model_name = settings.llm_model
        self._prompt_template = ChatPromptTemplate.from_template(
            """
You are an assistant for a sustainable fashion brand. Use the provided context to answer the question.

Context:
{context}

Question: {question}
"""
        ) if ChatPromptTemplate else None

    def build_ingest_splitter(self, chunk_size: int = 512, chunk_overlap: int = 50):
        """Return a text splitter for document ingestion."""
        if RecursiveCharacterTextSplitter is None:
            msg = "langchain-text-splitters is required for chunking"
            raise RuntimeError(msg)
        return RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", " ", ""],
        )

    def ingest(self, records: list[dict[str, Any]]) -> int:
        """Chunk and upsert records into the vector store."""
        if self._vector_store is None:
            msg = "Vector store is unavailable; cannot ingest documents"
            raise RuntimeError(msg)
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
            results = self.retrieve(query)
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

    def retrieve(self, query: str, top_k: int = 5) -> list[Any]:
        """Retrieve documents from the vector store."""
        if self._vector_store is None:
            return []
        with span("vector_retrieve", query=query, top_k=top_k):
            payloads = self._vector_store.query(query, top_k=top_k)
        return _map_payload_to_documents(payloads)

    def generate_answer(self, question: str, context_docs: list[Any]) -> str:
        """Generate an answer using the LLM."""
        if ChatOpenAI is None or self._prompt_template is None:
            return "LLM backend is not configured."
        if isinstance(context_docs, list) and context_docs and not isinstance(context_docs[0], str):
            context_text = "\n\n".join(getattr(doc, "page_content", str(doc)) for doc in context_docs)
        else:
            context_text = "\n\n".join(str(doc) for doc in context_docs)
        llm = ChatOpenAI(model=self._llm_model_name, temperature=0.2)
        chain = self._prompt_template | llm
        with span("llm_generate", question_length=len(question)):
            response = chain.invoke({"question": question, "context": context_text})
        return response.content if hasattr(response, "content") else str(response)

    def run(self, question: str) -> dict[str, Any]:
        """Execute the graph for a given question."""
        graph = self._build_graph()
        state = {"question": question}
        with span("rag_run", question=question):
            return graph.invoke(state)
