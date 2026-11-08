# IIIT Bhagalpur Institute Knowledge Assistant

A source-grounded institutional RAG application for asking questions about IIIT Bhagalpur documents. The project combines a FastAPI backend, document ingestion and extraction pipeline, Qdrant vector search, local Qwen embeddings, and a React + TypeScript chat interface.

## Features

- PDF and TXT document ingestion with page-level provenance.
- Digital, scanned and mixed PDF classification.
- Vision-model extraction for scanned pages.
- Configurable chunking and local Qwen3 embeddings through llama.cpp.
- Qdrant vector retrieval with citation-aware answer generation.
- React chat UI with Markdown, tables and LaTeX math rendering.
- Ingestion job status and retry support.

## Architecture

- `backend/app/api`: FastAPI routes.
- `backend/app/application`: ingestion and query orchestration.
- `backend/app/domain`: document and retrieval models.
- `backend/app/infrastructure`: extraction, chunking, embeddings, generation and Qdrant adapters.
- `backend/app/workers`: background ingestion worker.
- `frontend/src`: React application.
- `docs`: product requirements, architecture and implementation notes.
- `scripts`: local preflight and ingestion helpers.

## Requirements

- Windows 10/11 (the included startup scripts target Windows).
- Python 3.13.
- Node.js 20.19+ or 22.12+ and npm.
- Git.
- A Qdrant collection configured for 1,024-dimensional cosine vectors.
- Groq API access for answer generation and scanned-page VLM extraction.
- llama.cpp `llama-server` for local Qwen embeddings.

## Setup

### 1. Backend

Open PowerShell:

```powershell
cd .\backend
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
Copy-Item .env.example .env
```

Edit `backend/.env` locally and provide your own provider credentials and Qdrant configuration. Never commit `.env` or place provider secrets in frontend environment variables.

### 2. Frontend

```powershell
cd .\frontend
npm install
Copy-Item .env.example .env.local
```

The frontend environment file should contain only non-secret settings such as the API base URL.

### 3. Start the local stack

From the repository root, run:

```powershell
.\start-local.cmd
```

The helper starts the local embedding server, FastAPI backend, ingestion worker and Vite development server where configured.

Default local endpoints:

| Service | URL |
| --- | --- |
| Frontend | http://127.0.0.1:5174 |
| FastAPI | http://127.0.0.1:8018 |
| API documentation | http://127.0.0.1:8018/docs |
| Local embedding API | http://127.0.0.1:8088 |

### 4. Verify

Backend checks:

```powershell
cd .\backend
.\.venv\Scripts\python.exe -m ruff check app tests scripts
.\.venv\Scripts\python.exe -m pytest -q
```

Frontend checks:

```powershell
cd .\frontend
npm run build
npm run lint
```

## Ingest documents

The backend supports PDF and TXT files. Use the preflight helper before submitting a folder, then submit only after checking the preflight output:

```powershell
python .\scripts\smoke_process_rag_ready.py --help
python .\scripts\submit_rag_ready.py --help
```

The helper scripts accept command-line options; use `--help` to inspect them. Keep source documents and ingestion databases outside version control.

## Configuration and security

- Copy `backend/.env.example` to `backend/.env` and fill credentials locally.
- Copy `frontend/.env.example` to `frontend/.env.local`; frontend variables are public at build time.
- Do not commit API keys, tokens, passwords, local databases, uploaded documents, logs, model weights, virtual environments or dependency folders.
- Rotate any credential that has been accidentally exposed.
- The Qdrant collection is external; this repository does not contain institute source documents or indexed vectors.

## Notes

This is a local-development oriented project. Review deployment security, authentication, rate limiting, observability, backups and worker scaling before exposing it to the public internet.


## Live web search, query reformulation and safety

- Natural-language questions are reformulated by the configured answer model before embedding and Qdrant retrieval. The original user question is retained for answer generation.
- Time-sensitive queries (for example current director/registrar, latest notices, current schedules and upcoming deadlines) trigger live metasearch through `ddgs`.
- Live search prioritises official `iiitbh.ac.in` results. Web references are shown separately from indexed institute-document references and can be opened as external webpages.
- Static institutional questions remain grounded in the Qdrant collection; the assistant does not force web results into every answer.
- `WEB_SEARCH_ENABLED=true` enables live search. `WEB_SEARCH_MAX_RESULTS=6` controls the maximum number of live references.
- Query guardrails normalize input, cap question length, reject common prompt-injection attempts and protect hidden instructions/credentials. The answer model receives a system-level safety policy and treats all retrieved document/web content as untrusted data.
- Answers must cite only retrieved source IDs. Secret-like output patterns are redacted; unsupported or uncited answers are treated as insufficient evidence.

## Knowledge-base document deletion

The Knowledge base view provides a confirmation-protected delete action. It removes every Qdrant point belonging to the selected `document_id`, verifies that the points are gone, and then removes the corresponding local upload and ingestion-file record when available. Documents still being processed cannot be deleted.


## Docker deployment (complete stack)

The repository includes Docker Compose configuration for the React UI, FastAPI API, ingestion worker, and local llama.cpp Qwen embedding server. Qdrant Cloud and Groq remain managed external services.

### Prerequisites

- Docker Desktop with the Linux engine (WSL2 backend on Windows).
- A configured Qdrant Cloud collection with 1,024-dimensional cosine vectors.
- Groq API key; Langfuse credentials are optional.

### Configure secrets

Copy the backend example environment file and fill in your credentials:

```powershell
Copy-Item backend/.env.example backend/.env
```

Set `QDRANT_URL`, `QDRANT_API_KEY`, and `GROQ_API_KEY` in `backend/.env`. Do not commit this file or add keys to frontend variables. The Compose setup overrides the embedding endpoint to the internal service URL `http://embeddings:8088` and configures the browser frontend to use the same-origin API path `/api/v1`.

### Build and start locally

From the repository root:

```powershell
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
```

Open the web app at http://localhost. API documentation is at http://localhost/docs (or direct API port http://localhost:8018/docs). The Qwen GGUF model downloads on the embedding service's first launch and may take a while and require several GB of disk and RAM.

Compose services:

- `frontend`: Nginx serving the compiled React application and reverse-proxying `/api/` to FastAPI.
- `backend`: FastAPI HTTP API.
- `worker`: background document ingestion worker.
- `embeddings`: llama.cpp Qwen3 embedding service.

Backend and worker share the named `rag_data` volume for uploaded documents and SQLite job records. To inspect logs or stop the stack:

```powershell
docker compose logs -f backend worker embeddings frontend
docker compose down
```

`docker compose down -v` also deletes the persistent `rag_data` volume and its uploads/job records; use only if you intend to erase this data.

### Publish application images to Docker Hub

Authenticate with Docker Hub (using your Docker Hub account):

```powershell
docker login
```

Build and push the backend and frontend images. Replace `<dockerhub-username>` with your account username and make sure the matching repositories exist on Docker Hub:

```powershell
docker build -f backend/Dockerfile -t <dockerhub-username>/iiitbh-rag-backend:1.0.0 .
docker build -f frontend/Dockerfile --build-arg VITE_API_BASE_URL=/api/v1 -t <dockerhub-username>/iiitbh-rag-frontend:1.0.0 .
docker push <dockerhub-username>/iiitbh-rag-backend:1.0.0
docker push <dockerhub-username>/iiitbh-rag-frontend:1.0.0
```

For a deployment host, replace the `build:` blocks for `backend` and `frontend` in `docker-compose.yml` with the respective `image:` tags, transfer the compose file and backend environment file securely, then run `docker compose pull` and `docker compose up -d`. Never publish `backend/.env` or credentials to Docker Hub or source control. The embedding image/model and Qdrant/Groq services must also be accessible in the target environment.

For additional commands and troubleshooting, see [docker-deploy.md](docker-deploy.md).
