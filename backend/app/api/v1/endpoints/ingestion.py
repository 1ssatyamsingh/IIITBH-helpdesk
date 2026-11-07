from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.dependencies import get_job_repository
from app.core.config import Settings, get_settings
from app.domain.ingestion.states import FileProcessingStatus
from app.infrastructure.persistence.sqlite_job_repository import SQLiteJobRepository
from app.schemas.ingestion import IngestionJobResponse

router = APIRouter(prefix="/ingestion", tags=["ingestion"])
SUPPORTED_EXTENSIONS = {".txt", ".pdf"}
UPLOAD_CHUNK_BYTES = 1024 * 1024


def _safe_original_filename(filename: str | None) -> str:
    candidate = (filename or "uploaded_document").replace("\\", "/")
    return Path(candidate).name or "uploaded_document"


@router.post(
    "/jobs",
    response_model=IngestionJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a multi-file ingestion job",
)
async def create_ingestion_job(
    files: list[UploadFile] = File(...),
    settings: Settings = Depends(get_settings),
    repository: SQLiteJobRepository = Depends(get_job_repository),
) -> IngestionJobResponse:
    if not files:
        raise HTTPException(status_code=400, detail="Select at least one TXT or PDF file.")
    if len(files) > settings.max_upload_files:
        raise HTTPException(
            status_code=413,
            detail=f"Maximum {settings.max_upload_files} files are allowed per batch.",
        )

    job_id = str(uuid4())
    job_directory = settings.data_dir / "uploads" / job_id
    job_directory.mkdir(parents=True, exist_ok=True)
    file_records: list[dict] = []
    accepted_batch_bytes = 0
    batch_limit_bytes = settings.max_upload_batch_mb * 1024 * 1024

    try:
        for upload in files:
            file_id = str(uuid4())
            original_filename = _safe_original_filename(upload.filename)
            suffix = Path(original_filename).suffix.lower()

            if suffix not in SUPPORTED_EXTENSIONS:
                file_records.append(
                    {
                        "file_id": file_id,
                        "original_filename": original_filename,
                        "file_type": suffix.lstrip(".") or None,
                        "status": FileProcessingStatus.REJECTED.value,
                        "error": "Unsupported file type. Only TXT and PDF are accepted.",
                    }
                )
                await upload.close()
                continue

            stored_path = job_directory / f"{file_id}{suffix}"
            total_bytes = 0
            try:
                with stored_path.open("wb") as destination:
                    while block := await upload.read(UPLOAD_CHUNK_BYTES):
                        total_bytes += len(block)
                        if total_bytes > settings.max_upload_mb * 1024 * 1024:
                            raise ValueError(f"File exceeds the {settings.max_upload_mb} MB per-file limit.")
                        if accepted_batch_bytes + total_bytes > batch_limit_bytes:
                            raise ValueError(
                                f"Batch exceeds the {settings.max_upload_batch_mb} MB aggregate limit."
                            )
                        destination.write(block)
            except ValueError as exc:
                stored_path.unlink(missing_ok=True)
                file_records.append(
                    {
                        "file_id": file_id,
                        "original_filename": original_filename,
                        "file_type": suffix.lstrip("."),
                        "status": FileProcessingStatus.REJECTED.value,
                        "error": str(exc),
                    }
                )
                await upload.close()
                continue

            await upload.close()
            if suffix == ".pdf":
                with stored_path.open("rb") as source:
                    has_pdf_signature = source.read(5) == b"%PDF-"
                if not has_pdf_signature:
                    stored_path.unlink(missing_ok=True)
                    file_records.append(
                        {
                            "file_id": file_id,
                            "original_filename": original_filename,
                            "file_type": "pdf",
                            "status": FileProcessingStatus.REJECTED.value,
                            "error": "Invalid PDF file: missing PDF signature (%PDF-).",
                        }
                    )
                    continue
            if total_bytes == 0:
                stored_path.unlink(missing_ok=True)
                file_records.append(
                    {
                        "file_id": file_id,
                        "original_filename": original_filename,
                        "file_type": suffix.lstrip("."),
                        "status": FileProcessingStatus.REJECTED.value,
                        "error": "The uploaded file is empty.",
                    }
                )
                continue

            accepted_batch_bytes += total_bytes
            file_records.append(
                {
                    "file_id": file_id,
                    "original_filename": original_filename,
                    "storage_path": str(stored_path),
                    "file_type": suffix.lstrip("."),
                    "status": FileProcessingStatus.RECEIVED.value,
                    "metadata": {"size_bytes": total_bytes},
                }
            )

        repository.create_job(job_id, file_records)
    except Exception:
        for upload in files:
            await upload.close()
        if job_directory.exists():
            for stored_file in job_directory.iterdir():
                stored_file.unlink(missing_ok=True)
            job_directory.rmdir()
        raise

    job = repository.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=500, detail="Ingestion job could not be persisted.")
    return IngestionJobResponse.model_validate(job)
