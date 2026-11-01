from pathlib import Path

from app.infrastructure.persistence.sqlite_job_repository import SQLiteJobRepository


def _file(file_id: str, status: str = "received") -> dict:
    return {
        "file_id": file_id,
        "original_filename": f"{file_id}.txt",
        "storage_path": f"data/uploads/{file_id}.txt",
        "file_type": "txt",
        "status": status,
    }


def test_job_repository_persists_and_claims_files(tmp_path: Path) -> None:
    repository = SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    repository.create_job("job-1", [_file("file-1")])

    created = repository.get_job("job-1")
    assert created["status"] == "queued"
    assert created["files"][0]["status"] == "received"

    claimed = repository.claim_next_file()
    assert claimed["file_id"] == "file-1"
    assert claimed["status"] == "validating"

    processing = repository.get_job("job-1")
    assert processing["status"] == "processing"

    repository.update_file("file-1", "completed", metadata={"chunk_count": 3})
    completed = repository.get_job("job-1")
    assert completed["status"] == "completed"
    assert completed["files"][0]["metadata"]["chunk_count"] == 3


def test_job_repository_marks_missing_provider_configuration_as_blocked(
    tmp_path: Path,
) -> None:
    repository = SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    repository.create_job("job-2", [_file("file-2")])
    repository.claim_next_file()
    repository.update_file(
        "file-2",
        "blocked",
        error="Hugging Face endpoint URL is not configured.",
    )

    result = repository.get_job("job-2")
    assert result["status"] == "blocked"
    assert result["files"][0]["error"]


def test_job_repository_supports_partial_batch_success(tmp_path: Path) -> None:
    repository = SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    repository.create_job("job-3", [_file("file-3a"), _file("file-3b")])

    first = repository.claim_next_file()
    second = repository.claim_next_file()
    assert {first["file_id"], second["file_id"]} == {"file-3a", "file-3b"}

    repository.update_file("file-3a", "completed")
    repository.update_file("file-3b", "failed", error="Invalid PDF")

    result = repository.get_job("job-3")
    assert result["status"] == "completed_with_errors"


def test_job_repository_marks_partial_success_with_blocked_file_as_errors(
    tmp_path: Path,
) -> None:
    repository = SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    repository.create_job("job-4", [_file("file-4a"), _file("file-4b")])
    repository.claim_next_file()
    repository.claim_next_file()
    repository.update_file("file-4a", "completed")
    repository.update_file("file-4b", "blocked", error="Provider configuration missing.")

    result = repository.get_job("job-4")
    assert result["status"] == "completed_with_errors"


def test_job_repository_can_retry_blocked_file(tmp_path: Path) -> None:
    repository = SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    repository.create_job("job-retry", [_file("file-retry")])
    repository.claim_next_file()
    repository.update_file(
        "file-retry",
        "blocked",
        error="Configure provider credentials.",
        metadata={"page_count": 4},
    )

    repository.retry_file("job-retry", "file-retry")
    result = repository.get_job("job-retry")

    assert result["status"] == "queued"
    assert result["files"][0]["status"] == "received"
    assert result["files"][0]["error"] is None
    assert result["files"][0]["metadata"]["page_count"] == 4


def test_job_repository_rejects_retry_for_successful_file(tmp_path: Path) -> None:
    repository = SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    repository.create_job("job-no-retry", [_file("file-done")])
    repository.claim_next_file()
    repository.update_file("file-done", "completed")

    try:
        repository.retry_file("job-no-retry", "file-done")
    except ValueError as error:
        assert "Only failed or blocked files" in str(error)
    else:
        raise AssertionError("A successful file must not be requeued.")


def test_job_repository_rejects_retry_from_another_job(tmp_path: Path) -> None:
    repository = SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    repository.create_job("job-a", [_file("file-a")])
    repository.create_job("job-b", [_file("file-b")])
    repository.claim_next_file()
    repository.update_file("file-a", "failed", error="Test failure.")

    try:
        repository.retry_file("job-b", "file-a")
    except KeyError:
        pass
    else:
        raise AssertionError("A file must not be retried through another job ID.")
