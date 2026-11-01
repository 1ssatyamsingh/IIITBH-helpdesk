from pathlib import Path
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.core.config import Settings, get_settings
from app.infrastructure.persistence.sqlite_job_repository import SQLiteJobRepository
from app.infrastructure.vectorstores.qdrant_store import QdrantVectorStore

router = APIRouter(prefix="/knowledge-base", tags=["knowledge-base"])


def _store(settings: Settings) -> QdrantVectorStore:
    if not settings.qdrant_url:
        raise HTTPException(status_code=503, detail="Qdrant is not configured.")
    return QdrantVectorStore.from_settings(settings)


@router.get("/documents", summary="List unique documents indexed in the knowledge base")
def list_knowledge_documents(settings: Settings = Depends(get_settings)) -> dict:
    store = _store(settings)
    try:
        documents = store.list_documents()
        return {
            "collection": settings.qdrant_collection,
            "document_count": len(documents),
            "documents": documents,
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Could not read the Qdrant document catalogue.") from exc
    finally:
        store.client.close()


@router.get("/documents/{document_id}/file", summary="Open the original uploaded source document")
def open_source_document(
    document_id: str,
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    store = _store(settings)
    try:
        offset = None
        payload = None
        while True:
            points, next_offset = store.client.scroll(
                collection_name=settings.qdrant_collection,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            match = next((point.payload or {} for point in points if str((point.payload or {}).get("document_id")) == document_id), None)
            if match is not None:
                payload = match
                break
            if next_offset is None:
                break
            offset = next_offset
        if payload is None:
            raise HTTPException(status_code=404, detail="Source document is not indexed.")
        job_id = payload.get("ingestion_job_id")
        source_file = payload.get("source_file")
        if not job_id or not source_file:
            raise HTTPException(status_code=404, detail="Original upload metadata is unavailable.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Could not locate the source document.") from exc
    finally:
        store.client.close()

    repository = SQLiteJobRepository(settings.data_dir / "ingestion.sqlite3")
    job = repository.get_job(str(job_id))
    if not job:
        raise HTTPException(status_code=404, detail="Original ingestion record is unavailable.")
    matching = next((item for item in job["files"] if unquote(item["original_filename"]) == unquote(str(source_file)) and item.get("storage_path")), None)
    if not matching:
        raise HTTPException(status_code=404, detail="Original uploaded file is unavailable.")
    path = Path(matching["storage_path"]).resolve()
    upload_root = (settings.data_dir / "uploads").resolve()
    if upload_root not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="Source file is no longer available.")
    return FileResponse(path, filename=Path(str(source_file)).name, media_type="application/pdf" if path.suffix.lower() == ".pdf" else "text/plain")
