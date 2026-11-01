from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_job_repository
from app.infrastructure.persistence.sqlite_job_repository import SQLiteJobRepository
from app.schemas.ingestion import IngestionJobResponse

router = APIRouter(prefix="/ingestion/jobs", tags=["ingestion"])


@router.get(
    "/{job_id}",
    response_model=IngestionJobResponse,
    summary="Get ingestion job and per-file status",
)
async def get_ingestion_job(
    job_id: str,
    repository: SQLiteJobRepository = Depends(get_job_repository),
) -> IngestionJobResponse:
    job = repository.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Ingestion job not found.")
    return IngestionJobResponse.model_validate(job)
