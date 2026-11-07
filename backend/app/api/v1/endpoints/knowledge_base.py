from pathlib import Path
from threading import Lock
from time import monotonic
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.core.config import Settings, get_settings
from app.infrastructure.persistence.sqlite_job_repository import SQLiteJobRepository
from app.infrastructure.vectorstores.qdrant_store import QdrantVectorStore

router = APIRouter(prefix="/knowledge-base", tags=["knowledge-base"])
_catalog_cache: dict[tuple[str, str], tuple[float, list[dict]]] = {}
_catalog_cache_lock = Lock()
_CATALOG_CACHE_TTL_SECONDS = 60


def _store(settings: Settings) -> QdrantVectorStore:
    if not settings.qdrant_url:
        raise HTTPException(status_code=503, detail="Qdrant is not configured.")
    return QdrantVectorStore.from_settings(settings)


@router.get("/documents", summary="List unique documents indexed in the knowledge base")
def list_knowledge_documents(
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="source_file", pattern="^(source_file|chunk_count|page_count)$"),
    order: str = Query(default="asc", pattern="^(asc|desc)$"),
    refresh: bool = False,
    settings: Settings = Depends(get_settings),
) -> dict:
    cache_key = (settings.qdrant_url, settings.qdrant_collection)
    store = None
    try:
        with _catalog_cache_lock:
            cached = _catalog_cache.get(cache_key)
            if not refresh and cached and monotonic() - cached[0] < _CATALOG_CACHE_TTL_SECONDS:
                documents = list(cached[1])
            else:
                store = _store(settings)
                documents = store.list_documents()
                _catalog_cache[cache_key] = (monotonic(), list(documents))
        documents.sort(
            key=lambda item: (
                str(item.get(sort_by, "")).casefold()
                if sort_by == "source_file"
                else int(item.get(sort_by, 0) or 0)
            ),
            reverse=order == "desc",
        )
        total = len(documents)
        page = documents[offset : offset + limit]
        next_offset = offset + len(page) if offset + len(page) < total else None
        return {
            "collection": settings.qdrant_collection,
            "document_count": total,
            "documents": page,
            "limit": limit,
            "offset": offset,
            "has_more": next_offset is not None,
            "next_offset": next_offset,
            "sort_by": sort_by,
            "order": order,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail="Could not read the Qdrant document catalogue."
        ) from exc
    finally:
        if store is not None:
            store.client.close()


@router.delete("/documents/{document_id}", summary="Delete a document and all its vectors")
def delete_knowledge_document(
    document_id: str,
    confirm_delete: str = Header(default="", alias="X-Confirm-Delete"),
    settings: Settings = Depends(get_settings),
) -> dict:
    if confirm_delete != document_id:
        raise HTTPException(
            status_code=400, detail="Explicit document deletion confirmation is required."
        )
    store = _store(settings)
    repository = SQLiteJobRepository(settings.data_dir / "ingestion.sqlite3")
    stored_file = None
    try:
        record = store.get_document_record(document_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Document not found in the knowledge base.")
        job_id = record.get("ingestion_job_id")
        source_file = record.get("source_file")
        if job_id and source_file:
            job = repository.get_job(str(job_id))
            if job:
                stored_file = next(
                    (
                        item
                        for item in job["files"]
                        if unquote(item["original_filename"]) == unquote(str(source_file))
                    ),
                    None,
                )
                if stored_file and stored_file["status"] in {
                    "received",
                    "validating",
                    "classifying",
                    "extracting",
                    "chunking",
                    "embedding",
                    "indexing",
                }:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "This document is still being processed. "
                            "Try again after ingestion finishes."
                        ),
                    )
        deleted_chunks = store.delete_document(document_id)
        with _catalog_cache_lock:
            _catalog_cache.pop((settings.qdrant_url, settings.qdrant_collection), None)
    except HTTPException:
        raise
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail="Document not found in the knowledge base."
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail="Qdrant could not complete and verify the document deletion."
        ) from exc
    finally:
        store.client.close()

    local_file_deleted = False
    if stored_file:
        try:
            repository.delete_file_record(str(job_id), str(stored_file["file_id"]))
            storage_path = stored_file.get("storage_path")
            if storage_path:
                path = Path(storage_path).resolve()
                upload_root = (settings.data_dir / "uploads").resolve()
                if upload_root in path.parents and path.is_file():
                    path.unlink()
                    local_file_deleted = True
        except Exception:
            # Qdrant deletion has already been verified; never report it as rolled back.
            local_file_deleted = False
    return {
        "deleted": True,
        "document_id": document_id,
        "deleted_chunks": deleted_chunks,
        "local_upload_deleted": local_file_deleted,
        "message": "Document vectors removed from Qdrant.",
    }
