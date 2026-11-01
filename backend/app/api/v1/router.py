from fastapi import APIRouter

from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.ingestion import router as ingestion_router
from app.api.v1.endpoints.jobs import router as jobs_router
from app.api.v1.endpoints.knowledge_base import router as knowledge_base_router
from app.api.v1.endpoints.query import router as query_router
from app.api.v1.endpoints.retry import router as retry_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(knowledge_base_router)
api_router.include_router(ingestion_router)
api_router.include_router(jobs_router)
api_router.include_router(query_router)
api_router.include_router(retry_router)
