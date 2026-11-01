from collections.abc import Generator

from fastapi import Depends, HTTPException

from app.application.query.query_service import QueryService
from app.core.config import Settings, get_settings
from app.infrastructure.answer_generation.factory import create_answer_generator
from app.infrastructure.embeddings.factory import create_embedding_client
from app.infrastructure.persistence.sqlite_job_repository import SQLiteJobRepository
from app.infrastructure.vectorstores.qdrant_store import QdrantVectorStore
from app.infrastructure.web_search.ddgs_search import DDGSWebSearch


def get_job_repository(
    settings: Settings = Depends(get_settings),
) -> SQLiteJobRepository:
    return SQLiteJobRepository(settings.data_dir / "ingestion.sqlite3")


def get_query_service(
    settings: Settings = Depends(get_settings),
) -> Generator[QueryService]:
    if not settings.local_embedding_base_url:
        raise HTTPException(
            status_code=503,
            detail="Query service is not configured: set LOCAL_EMBEDDING_BASE_URL.",
        )
    if not settings.qdrant_url:
        raise HTTPException(
            status_code=503,
            detail="Query service is not configured: set QDRANT_URL.",
        )

    embedding_client = create_embedding_client(settings)
    vector_store = QdrantVectorStore.from_settings(settings)
    try:
        answer_generator = create_answer_generator(settings)
    except ValueError as exc:
        vector_store.client.close()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    try:
        yield QueryService(
            embedding_client=embedding_client,
            vector_store=vector_store,
            answer_generator=answer_generator,
            expected_dimension=settings.embedding_dimension,
            web_search=DDGSWebSearch(settings.web_search_max_results)
            if settings.web_search_enabled
            else None,
            web_search_enabled=settings.web_search_enabled,
        )
    finally:
        vector_store.client.close()
        if answer_generator is not None:
            answer_generator.http.close()
