# Implementation Status — IIITBH-RAG

Last updated: 2026-11-01

## Completed

### Phase 1 — Foundation
- Python 3.13 virtual environment created at backend/.venv.
- FastAPI application skeleton and versioned API router created.
- Typed environment configuration added through pydantic-settings.
- backend/.env created from backend/.env.example; provider credential values are intentionally blank.
- React + TypeScript + Vite frontend scaffolded.
- frontend/.env.local created from frontend/.env.example.
- Root .gitignore excludes virtual environments, node_modules, build output, local environment files and runtime data.
- Backend dependencies installed and editable package installation verified.
- Frontend dependencies installed.

### Phase 2 — Domain and backend processing foundations
- Domain types added for document, page, ingestion and retrieval state.
- Extractor, chunker, embedding, vector-store and answer-generator ports/adapters separated.
- FastAPI health endpoint implemented.
- Settings added for PDF text threshold, chunk size/overlap, provider URLs and credentials.

### Phase 3 — Local document processing
- TXT loader implemented with UTF-8 BOM, UTF-16 and Windows-1252 decoding fallback.
- PyMuPDF page-aware PDF classifier and digital text extraction implemented.
- Classification metrics and rule version are preserved in document metadata; page-level classifications and image counts are retained.
- Image-only PDF pages are marked requires_vlm; no text is fabricated.
- Groq Qwen VLM page transcription adapter implemented using image input and structured JSON output.
- Hybrid PDF extraction routes text pages to PyMuPDF and image-only pages to the VLM.
- LangChain RecursiveCharacterTextSplitter adapter implemented.
- Document processor validates extensions and PDF signatures, computes streaming SHA-256 identity and creates stable deterministic chunk IDs.
- Page/source provenance is preserved in every chunk.
- TXT encoding, PyMuPDF version, VLM model/prompt version, chunker configuration, category basis and ingestion timestamp are retained in metadata.
- Conservative document-category hints are inferred from filenames; publication dates and academic years are not inferred from filenames.
- Corpus processing smoke script added.

### Phase 4 — Retrieval and ingestion backend
- Hugging Face BGE-M3 dense embedding adapter added; validates 1,024-dimensional responses and batches requests.
- Qdrant adapter added with collection dimension/metric checks, verified upserts, search and document deletion.
- SQLite ingestion job repository added with per-file states, safe claiming and durable progress.
- Multi-file upload API added with extension, file-count, empty-file and per-file size validation.
- Job-status polling API added.
- Failed/blocked file retry endpoint added; retries verify the original stored file still exists and never mutate the uploaded source.
- Separate polling worker added; extraction, embedding and indexing failures are recorded per file.
- Query API added with ranked evidence, source metadata, extraction method and page-level citations.
- Qdrant payload preserves document/page extraction and chunker metadata; query evidence returns that metadata to the UI.
- OpenAI-compatible answer-generation adapter configured for Groq-hosted OpenAI GPT-OSS 120B (`openai/gpt-oss-120b`).
- Answer-generation factory reuses `GROQ_API_KEY` by default, so a separate answer-model key is not required.
- Answer citations are parsed and validated against retrieved evidence IDs; unsupported citation IDs are rejected.
- Evidence-only mode remains available when the final answer model is not configured.

### Phase 5 — React application
- Starter Vite screen replaced with a responsive, branded React application.
- Two main views implemented: Ask the institute and Knowledge ingestion.
- Chat view supports questions, starter prompts, loading/error states and source cards.
- Ingestion view supports multi-file selection, drag/drop, file removal, upload, job polling and per-file status.
- Per-file results display PDF classification, page/chunk counts, category hints and actionable failures.
- Failed/blocked files expose a retry action without re-uploading the source file.
- API client uses the configured Vite environment URL.
- Responsive sidebar, mobile layout, source panels and progress states added.

### Phase 6 — Local runtime and operations
- start-local.cmd launches the API, worker and frontend in separate windows.
- Root README documents local setup, tests, provider configuration and current limitations.
- submit_rag_ready.py added to submit the curated corpus in API-sized batches after provider configuration. It has a dry-run mode.
- Runtime API and worker use separate processes.

## Verification completed

- Backend Ruff lint: passed.
- Backend pytest suite: 59 tests passed after Groq GPT-OSS configuration, full-width citation parsing and deterministic offline PDF tests (latest run).
- Backend pip dependency consistency: passed.
- Frontend TypeScript production build: passed.
- Frontend Oxlint: passed with 0 warnings and 0 errors.
- Live FastAPI health endpoint on port 8018: HTTP 200.
- Live React/Vite page on port 5174: HTTP 200.
- CORS preflight from http://127.0.0.1:5174 to the API: HTTP 200.
- Curated corpus extraction/chunking dry run: 96 files processed (71 TXT + 25 PDF), 525 PDF pages inspected, 1,582 chunks generated, 4 scanned pages require VLM, 0 file errors and 0 page extraction failures.
- Bulk corpus submission script dry run: detected all 96 files and did not upload anything.
- Live Groq GPT-OSS 120B Chat Completions smoke test: passed; GPT-OSS returned a source citation using full-width brackets and the parser correctly extracted `S1`.
- Qdrant Cloud authentication/read-only connectivity: passed; existing `document_rag` collection verified as 1,024-dimensional Cosine, currently 0 points.
- Hugging Face token authentication (`whoami-v2`): passed; a dedicated BGE-M3 Inference Endpoint URL is still missing.
- No Qdrant vectors have been written and no corpus files have been submitted or indexed.

## Runtime endpoints

- React UI: http://127.0.0.1:5174 (5173 was already occupied by another local process)
- FastAPI: http://127.0.0.1:8018
- API docs: http://127.0.0.1:8018/docs
- Health: http://127.0.0.1:8018/api/v1/health

Port 8000 was already occupied by a different local API, so this project deliberately uses 8018.

## Configuration still required for real indexing

1. Deploy `BAAI/bge-m3` as a Hugging Face Inference Endpoint and set `HF_EMBEDDING_ENDPOINT_URL` in `backend/.env` (the Hugging Face token itself is authenticated).
2. Run a real BGE-M3 embedding contract test and verify the 1,024-dimensional output before ingestion.
3. The configured Qdrant Cloud connection is authenticated; `document_rag` is the verified empty 1,024-dimensional Cosine collection.
4. Groq GPT-OSS 120B answer generation is configured and live-smoke-tested. The same Groq key is also configured for scanned-page Qwen VLM extraction; its image transcription path still needs a controlled live test.
5. Representative retrieval evaluation to tune chunk size, top-k and score threshold.

Groq, Qdrant and Hugging Face credentials are configured in the local `backend/.env` (never committed). No corpus files have been uploaded to the API or indexed in Qdrant. The corpus smoke test only performed local extraction and chunking.

## Remaining implementation / production hardening

- Define explicit supersession/retention policy for different content hashes with the same source filename; identical re-ingestion already uses deterministic chunk IDs.
- Add authentication/authorization before exposing the service beyond localhost.
- Add ingestion cancellation and retention/cleanup policies.
- Add operational logging, metrics and a persistent production job queue.
- Run the BGE-M3 embedding contract test and end-to-end retrieval evaluation after the dedicated endpoint is configured.
- Perform browser-based visual QA and accessibility review across desktop/mobile breakpoints.
