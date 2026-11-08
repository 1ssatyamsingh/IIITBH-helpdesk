# Docker deployment

## Prerequisites
- Docker Desktop (Windows) with the WSL2 backend enabled.
- Qdrant Cloud URL/API key and Groq API key in `backend/.env`.
- Langfuse credentials (optional) in `backend/.env`.

## Run the complete stack locally
1. Copy `backend/.env.example` to `backend/.env`.
2. Set at least `QDRANT_URL`, `QDRANT_API_KEY`, and `GROQ_API_KEY`. Confirm your Qdrant collection uses 1,024-dimensional cosine vectors. For local Docker, keep `EMBEDDING_PROVIDER=local` and use the Compose-managed llama.cpp service.
3. For a cloud backend that does not run llama.cpp locally, select Cloudflare Workers AI: set `EMBEDDING_PROVIDER=cloudflare`, `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`, and `CLOUDFLARE_EMBEDDING_MODEL_ID=@cf/qwen/qwen3-embedding-0.6b`. Keep `EMBEDDING_DIMENSION=1024` and make sure the target Qdrant collection is also configured with 1,024-dimensional cosine vectors. Create a Cloudflare API token with Workers AI inference permission; never commit the token.
4. From the repository root:

   ```powershell
   docker compose build
   docker compose up -d
   docker compose ps
   ```

5. Open:
   - Web UI: http://localhost
   - API docs: http://localhost/docs
   - Direct API: http://localhost:8018/docs

The embedding service downloads the configured Qwen GGUF model on first startup; this can take time and needs available disk/RAM. Backend and ingestion worker use the same persistent Docker volume for SQLite job state and uploaded documents.

## Logs / stop
```powershell
docker compose logs -f backend worker embeddings frontend
docker compose down
``

Keep the `rag_data` volume when stopping. To remove persistent uploaded/job data too, use `docker compose down -v` (destructive).

## Publish the images to Docker Hub
1. Create a Docker Hub account and a public repository (e.g. `akm1923/iiitbh-rag-backend` and `akm1923/iiitbh-rag-frontend`).
2. Log in:
   ```powershell
   docker login
   ```
3. Build and tag the app images (replace `akm1923` with your Docker Hub username):
   ```powershell
   docker build -f backend/Dockerfile -t akm1923/iiitbh-rag-backend:1.0.0 .
   docker build -f frontend/Dockerfile --build-arg VITE_API_BASE_URL=/api/v1 -t akm1923/iiitbh-rag-frontend:1.0.0 .
   docker push akm1923/iiitbh-rag-backend:1.0.0
   docker push akm1923/iiitbh-rag-frontend:1.0.0
   ```
4. For deployment on another machine/server, update `docker-compose.yml` service build entries to `image: akm1923/iiitbh-rag-backend:1.0.0` and `image: akm1923/iiitbh-rag-frontend:1.0.0` (remove their `build:` blocks), then copy the compose file and backend `.env` securely to that host and run `docker compose pull && docker compose up -d`.

**Never publish backend/.env or credentials in an image/repository.** Docker Hub images contain application code only. Qdrant and Groq are external dependencies and still need credentials/configuration at runtime. The Compose stack includes the API, ingestion worker, UI, and local embedding server; it does not provision Qdrant Cloud or Groq.
