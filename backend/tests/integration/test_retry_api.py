from pathlib import Path

from fastapi.testclient import TestClient

from app.api.dependencies import get_job_repository
from app.core.config import Settings, get_settings
from app.infrastructure.persistence.sqlite_job_repository import SQLiteJobRepository
from app.main import app


def test_retry_endpoint_requeues_a_blocked_file(tmp_path: Path):
    source = tmp_path / "handbook.txt"
    source.write_text("IIIT Bhagalpur official handbook", encoding="utf-8")
    repository = SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    repository.create_job(
        "job-retry-api",
        [
            {
                "file_id": "file-retry-api",
                "original_filename": source.name,
                "storage_path": str(source),
                "file_type": "txt",
            }
        ],
    )
    repository.claim_next_file()
    repository.update_file("file-retry-api", "blocked", error="Provider missing.")
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    app.dependency_overrides[get_job_repository] = lambda: repository
    client = TestClient(app)

    try:
        response = client.post("/api/v1/ingestion/jobs/job-retry-api/files/file-retry-api/retry")

        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "queued"
        assert body["files"][0]["status"] == "received"
        assert body["files"][0]["error"] is None
    finally:
        app.dependency_overrides.clear()


def test_retry_endpoint_rejects_missing_source_file(tmp_path: Path):
    repository = SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    repository.create_job(
        "job-missing",
        [
            {
                "file_id": "file-missing",
                "original_filename": "missing.txt",
                "storage_path": str(tmp_path / "missing.txt"),
                "file_type": "txt",
            }
        ],
    )
    repository.claim_next_file()
    repository.update_file("file-missing", "failed", error="Previous error.")
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    app.dependency_overrides[get_job_repository] = lambda: repository
    client = TestClient(app)

    try:
        response = client.post("/api/v1/ingestion/jobs/job-missing/files/file-missing/retry")
        assert response.status_code == 409
        assert "source file is missing" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()
