from pathlib import Path

import pytest

from app.infrastructure.persistence.sqlite_job_repository import SQLiteJobRepository


def test_failed_file_can_be_retried_and_job_returns_to_queue(tmp_path: Path):
    repository = SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    repository.create_job(
        "job-retry",
        [
            {
                "file_id": "file-retry",
                "original_filename": "handbook.txt",
                "storage_path": str(tmp_path / "handbook.txt"),
                "file_type": "txt",
            }
        ],
    )
    repository.claim_next_file()
    repository.update_file("file-retry", "blocked", error="Provider is not configured.")

    repository.retry_file("job-retry", "file-retry")
    result = repository.get_job("job-retry")

    assert result["status"] == "queued"
    assert result["files"][0]["status"] == "received"
    assert result["files"][0]["error"] is None


def test_completed_file_cannot_be_retried(tmp_path: Path):
    repository = SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    repository.create_job(
        "job-complete",
        [
            {
                "file_id": "file-complete",
                "original_filename": "handbook.txt",
                "file_type": "txt",
            }
        ],
    )
    repository.claim_next_file()
    repository.update_file("file-complete", "completed")

    with pytest.raises(ValueError, match="Only failed or blocked"):
        repository.retry_file("job-complete", "file-complete")
