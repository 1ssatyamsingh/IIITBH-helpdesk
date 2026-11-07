from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_job_repository
from app.core.config import Settings, get_settings
from app.infrastructure.persistence.sqlite_job_repository import SQLiteJobRepository
from app.schemas.ingestion import IngestionJobResponse

router = APIRouter(prefix="/ingestion/jobs", tags=["ingestion"])


@router.post(
    "/{job_id}/files/{file_id}/retry",
    response_model=IngestionJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Retry a failed or blocked ingestion file",
)
def retry_ingestion_file(
    job_id: str,
    file_id: str,
    repository: SQLiteJobRepository = Depends(get_job_repository),
    settings: Settings = Depends(get_settings),
) -> IngestionJobResponse:
    job = repository.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Ingestion job not found.")

    file_record = next(
        (item for item in job["files"] if item["file_id"] == file_id),
        None,
    )
    if file_record is None:
        raise HTTPException(status_code=404, detail="File not found in this ingestion job.")

    storage_path = file_record.get("storage_path")
    upload_root = (settings.data_dir / "uploads").resolve()
    try:
        resolved_storage_path = Path(storage_path).resolve(strict=True) if storage_path else None
    except (OSError, RuntimeError):
        resolved_storage_path = None
    if (
        resolved_storage_path is None
        or upload_root not in resolved_storage_path.parents
        or not resolved_storage_path.is_file()
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The stored source file is missing or outside the upload directory and cannot be retried.",
        )

    try:
        repository.retry_file(job_id, file_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Ingestion file not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    updated_job = repository.get_job(job_id)
    if updated_job is None:
        raise HTTPException(status_code=500, detail="Ingestion job could not be refreshed.")
    return IngestionJobResponse.model_validate(updated_job)
