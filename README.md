# RAG Chatbot Production

Fashion-focused retrieval-augmented generation stack with FastAPI, React, Weaviate, Phoenix, and Ragas. Everything runs through Docker for local or staged environments.

> Requires Python **3.11+** when running CLI tooling outside Docker. A Conda environment is recommended for dependency isolation.

## Data Snapshot

The `data/` folder includes synthetic showcase datasets you can swap out for real sources:
- `documents.jsonl` — 10 multi-section knowledge docs covering care, sizing, policies, sustainability, and category guides.
- `products.jsonl` — 30 product records with brand, materials, care, sizes, pricing, and tags for metadata-aware responses.
- `qa.jsonl` — 35 evaluation prompts with reference answers and support spans for regression tracking.

Replace these files to tailor the assistant to your own catalog or knowledge base; the ETL and ingestion flows adapt automatically.
Use environment variables (`CHUNK_SIZE`, `CHUNK_OVERLAP`, `VECTOR_COLLECTION_NAME`, `PRODUCT_DATA_PATH`) to align the backend with custom datasets.
Set `DOCUMENTS_PATH`, `INGEST_ENDPOINT`, or `QA_DATA_PATH` when using provided scripts to point at alternate sources.

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
   echo "API_KEY=dev-key" >> backend/.env  # backend requires X-API-Key authentication
   ```
   To use OpenRouter's free tier, set `LLM_MODEL=meta-llama/llama-3.3-8b-instruct:free`,
   point `OPENAI_API_BASE=https://openrouter.ai/api/v1`, and provide your OpenRouter API key.
   Export `BACKEND_VERSION` and `FRONTEND_VERSION` (each defaults to `0.1.0`) before `docker compose up`
   to tag the respective images; `/api/health` reports `BACKEND_VERSION` through `API_VERSION`.
2. **Start services** (backend, frontend, Weaviate, Phoenix):
   ```bash
   docker compose up --build
   ```
3. **Load knowledge** once the backend is healthy:
   ```bash
   conda create -n rag-chatbot python=3.11 -y  # skip if the env already exists
   conda activate rag-chatbot
   pip install requests
   python scripts/ingest.py --endpoint http://localhost:8000/api/ingest --path data/documents.jsonl
   ```
    The backend handles chunking and upserts each section into Weaviate.
    Run this when the vector store is empty (e.g., first boot or after clearing volumes); otherwise you can skip re-ingestion.
    If you bring your own corpus, point `scripts/ingest.py --path` to the new file and adjust backend chunk settings through env vars.
    You can also export `DOCUMENTS_PATH` or `INGEST_ENDPOINT` to change defaults without editing the command.
    The CLI accepts `--api-key` or respects `$API_KEY` to satisfy authenticated endpoints.
4. **Chat** at http://localhost:3000. Questions travel through LangGraph → Weaviate → LLM response.
5. **Observe** Phoenix traces at http://localhost:6006 for ingestion, retrieval, and generation spans.

When running the frontend without Docker, point Vite at the local backend:
```bash
cd frontend
export VITE_BACKEND_URL=http://localhost:8000
npm install
npm run dev
```

## ETL Options

Generate chunked artifacts offline if you want to inspect or tweak splitting parameters:
```bash
conda create -n rag-etl python=3.11 -y  # skip if already created
conda activate rag-etl
cd etl
pip install -r requirements.txt
python cli.py --documents ../data/documents.jsonl --chunk-size 512 --chunk-overlap 50 --output artifacts/chunked_documents.jsonl
```
Use the resulting JSONL to seed Weaviate directly or compare against the online ingest flow.
Override the CLI flags (`--documents`, `--chunk-size`, `--chunk-overlap`, `--output`) when working with custom datasets.
For evaluation, override `QA_DATA_PATH` or pass `--qa-path` to target custom regression suites.

## Evaluate with Ragas

With the stack running:
```bash
docker compose run --rm eval --backend-url http://backend:8000 --qa-path /app/qa.jsonl
```
Or locally without Docker:
```bash
cd evaluation
conda create -n rag-eval python=3.11 -y  # skip if already created
conda activate rag-eval
pip install -r requirements.txt
python run_ragas.py --backend-url http://localhost:8000 --qa-path ../data/qa.jsonl
```
Metrics reported: answer relevancy, faithfulness, context precision, and context relevancy.

## Product Catalog API

The backend exposes structured product data parsed from `data/products.jsonl`.

- `GET /api/products` supports optional `brand`, `category`, `tag`, `size`, and `query` filters.
- `GET /api/products/{product_id}` returns a single catalog item.

Configure the source file via `PRODUCT_DATA_PATH`; Docker Compose mounts `./data` into the backend container for convenience.

## Product-Aware Retrieval

- `products.jsonl` metadata is automatically fused into retrieval answers. The pipeline surfaces relevant catalog entries alongside knowledge base chunks.
- Query requests accept optional `brand`, `category`, `tag`, and `size` filters to bias retrieval toward specific inventory slices.
- The React chat now renders retrieved evidence (documents + products) and links directly to the associated Phoenix trace for deeper debugging.

## Security & Operations

- All non-health endpoints require the `X-API-Key` header; configure `API_KEY` in `backend/.env` and provide it via the UI or CLI flags.
- A lightweight in-memory rate limiter protects `/api/ingest` and `/api/query`; tune `RATE_LIMIT_PER_MINUTE` and `RATE_LIMIT_WINDOW_SECONDS` in the environment.
- Requests are logged with method, path, status, latency, and client metadata to streamline monitoring.
- When OpenAI credentials are absent, the backend gracefully falls back to deterministic summaries so CI and local smoke tests still succeed.

## CI Automation

- `.github/workflows/ci.yml` provisions the backend, ingests `data/documents.jsonl`, and exercises `/api/query` via `scripts/ci_smoke.py` on every push and pull request.
- The smoke script validates answers and ensures context is surfaced, catching regressions in ingestion, routing, or retrieval logic early.

## Next Ideas

- Add reranking (e.g., Cohere or OpenAI re-ranker) to reorder retrieved knowledge chunks.
- Stream tokens to the React UI for faster perceived latency.
- Expand CI to run full ragas evaluations when LLM credentials are supplied via repository secrets.
