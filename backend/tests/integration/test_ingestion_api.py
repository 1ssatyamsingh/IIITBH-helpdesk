from pathlib import Path

from fastapi.testclient import TestClient

from app.api.dependencies import get_job_repository
from app.core.config import Settings, get_settings
from app.infrastructure.persistence.sqlite_job_repository import SQLiteJobRepository
from app.main import app


def test_multi_file_upload_creates_job_and_rejects_unsupported_type(
    tmp_path: Path,
) -> None:
    settings = Settings(data_dir=tmp_path, max_upload_files=5, max_upload_mb=1)
    repository = SQLiteJobRepository(tmp_path / "ingestion.sqlite3")
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_job_repository] = lambda: repository
    client = TestClient(app)

    try:
        response = client.post(
            "/api/v1/ingestion/jobs",
            files=[
                ("files", ("handbook.txt", b"IIIT Bhagalpur handbook", "text/plain")),
                (
                    "files",
                    ("calendar.pdf", b"%PDF-1.4 fake-pdf-for-upload-test", "application/pdf"),
                ),
                ("files", ("resume.docx", b"unsupported", "application/octet-stream")),
            ],
        )

        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "queued"
        assert len(body["files"]) == 3
        statuses = {item["original_filename"]: item["status"] for item in body["files"]}
        assert statuses["handbook.txt"] == "received"
        assert statuses["calendar.pdf"] == "received"
        assert statuses["resume.docx"] == "rejected"

        stored_files = list((tmp_path / "uploads" / body["job_id"]).iterdir())
        assert len(stored_files) == 2

        status_response = client.get(f"/api/v1/ingestion/jobs/{body['job_id']}")
        assert status_response.status_code == 200
        assert status_response.json()["job_id"] == body["job_id"]
    finally:
        app.dependency_overrides.clear()


def test_upload_size_limit_marks_only_oversized_file_rejected(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, max_upload_files=2, max_upload_mb=1)
    repository = SQLiteJobRepository(tmp_path / "ingestion.sqlite3")
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_job_repository] = lambda: repository
    client = TestClient(app)

    try:
        response = client.post(
            "/api/v1/ingestion/jobs",
            files=[
                ("files", ("too-large.txt", b"x" * (1024 * 1024 + 1), "text/plain")),
                ("files", ("small.txt", b"small", "text/plain")),
            ],
        )

        assert response.status_code == 202
        body = response.json()
        statuses = {item["original_filename"]: item["status"] for item in body["files"]}
        assert statuses["too-large.txt"] == "rejected"
        assert statuses["small.txt"] == "received"
    finally:
        app.dependency_overrides.clear()


def test_pdf_upload_requires_pdf_magic_bytes(tmp_path: Path):
    settings = Settings(data_dir=tmp_path, max_upload_files=5, max_upload_mb=1)
    repository = SQLiteJobRepository(tmp_path / "ingestion.sqlite3")
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_job_repository] = lambda: repository
    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/ingestion/jobs",
            files=[("files", ("not-a-pdf.pdf", b"plain text pretending to be pdf", "application/pdf"))],
        )
        assert response.status_code == 202
        assert response.json()["files"][0]["status"] == "rejected"
        assert "PDF signature" in response.json()["files"][0]["error"]
    finally:
        app.dependency_overrides.clear()
