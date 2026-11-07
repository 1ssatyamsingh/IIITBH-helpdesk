from functools import lru_cache

from fastapi import Depends, HTTPException

from app.application.query.query_service import QueryService
from app.core.config import Settings, get_settings
from app.infrastructure.answer_generation.factory import create_answer_generator
from app.infrastructure.embeddings.factory import create_embedding_client
from app.infrastructure.persistence.sqlite_job_repository import SQLiteJobRepository
from app.infrastructure.vectorstores.qdrant_store import QdrantVectorStore
from app.infrastructure.web_search.ddgs_search import DDGSWebSearch

_query_services: dict[str, QueryService] = {}


def get_job_repository(
    settings: Settings = Depends(get_settings),
) -> SQLiteJobRepository:
    return SQLiteJobRepository(settings.data_dir / "ingestion.sqlite3")


@lru_cache(maxsize=4)
def _cached_query_service(settings_json: str) -> QueryService:
    """Reuse process-scoped API clients across requests with identical configuration."""
    settings = Settings.model_validate_json(settings_json)
    embedding_client = create_embedding_client(settings)
    vector_store = QdrantVectorStore.from_settings(settings)
    try:
        answer_generator = create_answer_generator(settings)
    except ValueError:
        embedding_client.close()
        vector_store.client.close()
        raise

    service = QueryService(
        embedding_client=embedding_client,
        vector_store=vector_store,
        answer_generator=answer_generator,
        expected_dimension=settings.embedding_dimension,
        web_search=DDGSWebSearch(settings.web_search_max_results)
        if settings.web_search_enabled
        else None,
        web_search_enabled=settings.web_search_enabled,
    )
    _query_services[settings_json] = service
    return service


def get_query_service(
    settings: Settings = Depends(get_settings),
) -> QueryService:
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
    try:
        return _cached_query_service(settings.model_dump_json())
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def close_cached_query_services() -> None:
    """Close process-scoped clients at application shutdown."""
    for service in _query_services.values():
        service.embedding_client.close()
        service.vector_store.client.close()
        if service.answer_generator is not None:
            service.answer_generator.http.close()
    _query_services.clear()
    _cached_query_service.cache_clear()
