# Backend

## Setup (Windows PowerShell)

```powershell
cd .\backend
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
Copy-Item .env.example .env
```

Add provider and Qdrant credentials to `.env` locally. Do not commit it.

## Run

From the backend directory:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8018
```

- Health: http://127.0.0.1:8018/api/v1/health
- API docs: http://127.0.0.1:8018/docs

For the full local stack, use `start-local.cmd` from the repository root.
