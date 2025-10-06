# RAG Chatbot Production

Fashion-focused retrieval-augmented generation stack with FastAPI, React, Weaviate, Phoenix, and Ragas. Everything runs through Docker for local or staged environments.

## System Map

- `backend/` FastAPI service with LangChain/LangGraph pipeline, Phoenix spans, Weaviate client.
- `frontend/` React + Vite chat interface calling `/api` routes.
- `etl/` Offline chunking CLI for document preprocessing.
- `evaluation/` Ragas harness for regression-style quality checks.
- `data/` Synthetic source documents, products, QA pairs.
- `scripts/` Helper utilities such as document ingestion.
- `docker-compose.yml` Orchestration for app, vector store, Phoenix, and eval jobs.

## Run the Stack

1. **Configure secrets**
   ```bash
   cp backend/.env.example backend/.env
   # edit backend/.env and add OPENAI_API_KEY, optional Weaviate/Phoenix overrides
   ```
2. **Start services** (backend, frontend, Weaviate, Phoenix):
   ```bash
   docker compose up --build
   ```
3. **Load knowledge** once the backend is healthy:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install requests
   python scripts/ingest.py --endpoint http://localhost:8000/api/ingest --path data/documents.jsonl
   ```
   The backend handles chunking and upserts each section into Weaviate.
4. **Chat** at http://localhost:3000. Questions travel through LangGraph → Weaviate → LLM response.
5. **Observe** Phoenix traces at http://localhost:6006 for ingestion, retrieval, and generation spans.

## ETL Options

Generate chunked artifacts offline if you want to inspect or tweak splitting parameters:
```bash
cd etl
pip install -r requirements.txt
python cli.py --documents ../data/documents.jsonl --chunk-size 512 --chunk-overlap 50 --output artifacts/chunked_documents.jsonl
```
Use the resulting JSONL to seed Weaviate directly or compare against the online ingest flow.

## Evaluate with Ragas

With the stack running:
```bash
docker compose run --rm eval --backend-url http://backend:8000 --qa-path /app/qa.jsonl
```
Or locally without Docker:
```bash
cd evaluation
pip install -r requirements.txt
python run_ragas.py --backend-url http://localhost:8000 --qa-path ../data/qa.jsonl
```
Metrics reported: answer relevancy, faithfulness, context precision, and context relevancy.

## Product Catalog API

The backend exposes structured product data parsed from `data/products.jsonl`.

- `GET /api/products` supports optional `brand`, `category`, `tag`, `size`, and `query` filters.
- `GET /api/products/{product_id}` returns a single catalog item.

Configure the source file via `PRODUCT_DATA_PATH`; Docker Compose mounts `./data` into the backend container for convenience.

## Next Ideas

- Integrate `products.jsonl` for metadata filtering or product-aware retrieval chains.
- Add authentication, rate limits, or logging sinks before exposing the API.
- Surface retrieved evidence and Phoenix trace links inside the React UI.
- Automate ingestion/evaluation in CI to detect regressions.
