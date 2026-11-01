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
