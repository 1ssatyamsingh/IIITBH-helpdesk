# Deploying IIITBH Helpdesk Backend on Render

This guide walks you through deploying the FastAPI backend of the IIIT Bhagalpur Institute Knowledge Assistant on [Render](https://render.com).

---

## 1. Cloud Architecture Overview

When deployed locally or via Docker Compose, the backend uses a local `llama.cpp` container for embeddings. In cloud environments like Render:
- **Cloud Embeddings**: Uses Cloudflare Workers AI (`@cf/qwen/qwen3-embedding-0.6b` producing 1,024-dimensional cosine vectors) via `EMBEDDING_PROVIDER=cloudflare`.
- **Vector Database**: Connects to your managed [Qdrant Cloud](https://cloud.qdrant.io) cluster.
- **Answer Generation & OCR**: Connects to [Groq](https://console.groq.com) for fast inference.
- **Ingestion Worker**: Enabled via `EMBEDDED_WORKER=true`, running document processing inside the FastAPI web service as a background worker thread. This eliminates the need to pay for a separate background worker service on Render.
- **Port Binding**: Automatically binds to `$PORT` provided dynamically by Render.

---

## 2. Prerequisites & Credentials

Before deploying on Render, ensure you have:

1. **A GitHub repository** containing this code (e.g., `https://github.com/1ssatyamsingh/IIITBH-helpdesk`).
2. **A Render Account**: [Sign up at render.com](https://render.com).
3. **Qdrant Cloud Cluster**:
   - Create a free cluster at [cloud.qdrant.io](https://cloud.qdrant.io).
   - Create a collection named `document_rag` (or `iiitbh_knowledge`) with **1,024-dimensional Cosine distance**.
   - Copy your **Cluster URL** (e.g. `https://xxxxxx.us-east4-0.gcp.cloud.qdrant.io:6333`) and **API Key**.
4. **Groq API Key**:
   - Obtain an API key from [console.groq.com/keys](https://console.groq.com/keys).
5. **Cloudflare Workers AI Credentials**:
   - In the [Cloudflare Dashboard](https://dash.cloudflare.com), find your **Account ID**.
   - Create an API token under **My Profile -> API Tokens -> Create Token -> Use template: Workers AI (Read)**.

---

## 3. Method 1: Deploy with Render Blueprint (Recommended)

Render Blueprints use the included `render.yaml` to configure the service automatically.

1. **Commit and push** the repository to GitHub:
   ```powershell
   git add .
   git commit -m "Configure backend for Render deployment"
   git push origin main
   ```
2. Open the [Render Dashboard](https://dashboard.render.com).
3. Click **New +** in the top navigation and select **Blueprint**.
4. Connect your GitHub account and select the `IIITBH-helpdesk` repository.
5. Render reads `render.yaml` and displays the service definition:
   - **Service Name**: `iiitbh-rag-backend`
   - **Runtime**: Python 3.13
   - **Plan**: Free
6. Fill in the required environment secrets when prompted by Render:
   - `QDRANT_URL`: `https://<your-cluster-id>.cloud.qdrant.io:6333`
   - `QDRANT_API_KEY`: `<your-qdrant-api-key>`
   - `GROQ_API_KEY`: `gsk_<your-groq-api-key>`
   - `CLOUDFLARE_ACCOUNT_ID`: `<your-cloudflare-account-id>`
   - `CLOUDFLARE_API_TOKEN`: `<your-cloudflare-api-token>`
   - `FRONTEND_ORIGINS`: Comma-separated list of allowed frontend origins (e.g., `https://your-frontend.onrender.com,http://localhost:5173`).
7. Click **Apply**.
8. Render will provision the service, install dependencies, run health checks at `/api/v1/health`, and bring the backend live.

---

## 4. Method 2: Manual Web Service Setup on Render

If you prefer to configure the Web Service manually via Render's web interface:

### Step 1: Create Web Service
1. In the [Render Dashboard](https://dashboard.render.com), click **New +** -> **Web Service**.
2. Connect the `IIITBH-helpdesk` GitHub repository.

### Step 2: Configure Service Settings
- **Name**: `iiitbh-rag-backend`
- **Region**: Choose the region closest to you or your Qdrant cluster (e.g., Oregon, Ohio, Frankfurt, Singapore).
- **Branch**: `main`
- **Root Directory**: `backend`
- **Runtime**: `Python`
- **Build Command**: `pip install --upgrade pip && pip install -r requirements.txt`
- **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Instance Type / Plan**: `Free`

*(Alternative using Docker: leave Root Directory empty, select Runtime `Docker`, set Dockerfile Path to `backend/Dockerfile`, and Context to `.`)*

### Step 3: Health Check
- Scroll down to **Advanced** -> **Health Check Path**.
- Set to: `/api/v1/health`

### Step 4: Environment Variables
Add the following environment variables in the **Environment** tab:

| Variable | Value | Description |
|---|---|---|
| `APP_NAME` | `IIITBH RAG API` | Name of application |
| `APP_ENV` | `production` | Enables HSTS and production headers |
| `LOG_LEVEL` | `INFO` | Application log level |
| `API_V1_PREFIX` | `/api/v1` | Prefix for API routes |
| `EMBEDDED_WORKER` | `true` | Runs ingestion worker thread inside web service |
| `EMBEDDING_PROVIDER` | `cloudflare` | Cloudflare Workers AI for embeddings |
| `CLOUDFLARE_ACCOUNT_ID` | *(your Account ID)* | Cloudflare account identifier |
| `CLOUDFLARE_API_TOKEN` | *(your Workers AI Token)* | Secret API token for Cloudflare |
| `CLOUDFLARE_EMBEDDING_MODEL_ID` | `@cf/qwen/qwen3-embedding-0.6b` | Cloudflare model ID |
| `EMBEDDING_DIMENSION` | `1024` | Must match Qdrant collection dimension |
| `QDRANT_URL` | `https://xxx.cloud.qdrant.io:6333` | Qdrant Cloud URL |
| `QDRANT_API_KEY` | *(your Qdrant key)* | Qdrant API key |
| `QDRANT_COLLECTION` | `document_rag` | Collection name in Qdrant |
| `GROQ_API_KEY` | `gsk_...` | Groq API Key |
| `ANSWER_MODEL_PROVIDER` | `groq` | Provider for answer generation |
| `ANSWER_MODEL_BASE_URL` | `https://api.groq.com/openai/v1` | Groq OpenAI-compatible endpoint |
| `ANSWER_MODEL_ID` | `openai/gpt-oss-120b` | Answer generation model |
| `GROQ_VLM_MODEL` | `qwen/qwen3.8-27b` | Model used for OCR on scanned pages |
| `WEB_SEARCH_ENABLED` | `true` | Enables real-time web search for current info |
| `WEB_SEARCH_MAX_RESULTS` | `6` | Maximum web references |
| `FRONTEND_ORIGINS` | `https://your-frontend.onrender.com,http://localhost:5173` | Allowed CORS origins (no trailing slashes, comma-separated) |

Click **Create Web Service**.

---

## 5. Verification & Testing

Once Render finishes deploying:

1. **Health Check**:
   Open in your browser or curl:
   ```bash
   curl https://<your-service-name>.onrender.com/api/v1/health
   ```
   Expected response:
   ```json
   {"status":"ok","service":"iiitbh-rag-api"}
   ```

2. **Interactive Swagger Documentation**:
   Visit:
   ```
   https://<your-service-name>.onrender.com/docs
   ```
   Verify all endpoints (`/api/v1/query/`, `/api/v1/ingestion/jobs`, `/api/v1/knowledge-base/documents`) appear.

3. **Test a Query Endpoint**:
   Send a sample question via curl or Swagger:
   ```bash
   curl -X POST "https://<your-service-name>.onrender.com/api/v1/query/" \
     -H "Content-Type: application/json" \
     -d '{"question": "What academic programs are offered at IIIT Bhagalpur?"}'
   ```

---

## 6. Connecting Frontend to the Render Backend

When deploying your frontend (on Render Static Site, Vercel, Netlify, etc.):
1. In the frontend environment configuration, set:
   ```env
   VITE_API_BASE_URL=https://<your-backend-service-name>.onrender.com/api/v1
   ```
2. In the Render backend service settings, ensure `FRONTEND_ORIGINS` contains your frontend's production URL:
   ```env
   FRONTEND_ORIGINS=https://<your-frontend-domain>,http://localhost:5173
   ```
3. Redeploy or restart the backend to apply any CORS changes.

---

## 7. Render Free Tier Considerations

- **Spin-down on Inactivity**: Free tier Web Services on Render spin down after 15 minutes of inactivity. When a new request arrives, it takes ~30–50 seconds for the service to wake up.
- **Persistent Storage**: Render Free Web Services use ephemeral storage. SQLite job tracking records and uploaded raw files in `backend/data` reset on redeploy or restart. Vector embeddings and chunks stored in Qdrant Cloud are fully persistent. For permanent local file storage on Render, attach a [Render Persistent Disk](https://render.com/docs/disks) (available on Starter or higher plans) and set `DATA_DIR=/var/data`.

