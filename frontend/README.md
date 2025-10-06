# RAG Chatbot Frontend

React (Vite) single-page app that interacts with the FastAPI backend to surface retrieval-augmented answers and evidence.

## Prerequisites

- Node.js 20+
- pnpm, npm, or yarn (examples below use npm)

## Development

```bash
cd frontend
npm install
npm run dev
```

The dev server runs on [http://localhost:5173](http://localhost:5173) and proxies API requests to the backend at `http://backend:8000` when started via Docker Compose.

## Production Build

```bash
cd frontend
npm install
npm run build
npm run preview
```

The Dockerfile executes `npm run build`, producing static assets in `dist/` that are served by nginx (see `frontend/Dockerfile`).

## Environment & Auth

- The UI prompts for an API key and stores it in `localStorage` (`rag_api_key`) so requests include the required `X-API-Key` header.
- Optional filters (brand, category, tag, size) narrow product-aware retrieval.
- Evidence cards display both vector-store snippets and product catalog matches, along with Phoenix trace links returned by the backend.

## Helpful Scripts

- `npm run lint` — run ESLint (if configured).
- `npm run test` — placeholder for component tests (not yet defined).

## Troubleshooting

- Build error `Could not resolve entry module "index.html"`? Ensure `frontend/index.html` exists at the project root (Vite expects it there).
- When the backend is offline, UI requests fail with rate limit/auth errors; start the backend (and provide the API key) before chatting.

