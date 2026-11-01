from typing import Any

from pydantic import BaseModel


class IngestionFileResponse(BaseModel):
    file_id: str
    original_filename: str
    file_type: str | None
    status: str
    error: str | None = None
    metadata: dict[str, Any]
    created_at: str
    updated_at: str


class IngestionJobResponse(BaseModel):
    job_id: str
    status: str
    created_at: str
    updated_at: str
    files: list[IngestionFileResponse]
