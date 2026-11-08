import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.dependencies import close_cached_query_services
from app.api.v1.router import api_router
from app.core.config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_application: FastAPI):
    settings = get_settings()
    worker_thread = None
    stop_event = threading.Event()

    if settings.embedded_worker:
        from app.infrastructure.persistence.sqlite_job_repository import SQLiteJobRepository
        from app.workers.ingestion_worker import IngestionWorker

        def _worker_loop() -> None:
            logger.info("Embedded ingestion worker thread started.")
            repository = SQLiteJobRepository(settings.data_dir / "ingestion.sqlite3")
            worker = IngestionWorker(repository=repository, settings=settings)
            while not stop_event.is_set():
                try:
                    processed = worker.process_next_file()
                    if not processed:
                        stop_event.wait(timeout=max(settings.worker_poll_interval, 0.5))
                except Exception as exc:
                    logger.exception("Error in embedded ingestion worker: %s", exc)
                    stop_event.wait(timeout=max(settings.worker_poll_interval, 1.0))
            logger.info("Embedded ingestion worker thread stopped.")

        worker_thread = threading.Thread(
            target=_worker_loop,
            daemon=True,
            name="EmbeddedIngestionWorker",
        )
        worker_thread.start()
    yield
    if worker_thread is not None:
        stop_event.set()
        worker_thread.join(timeout=3.0)

    close_cached_query_services()


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Modular, evidence-grounded RAG API for IIIT Bhagalpur.",
        lifespan=lifespan,
    )
    @application.middleware("http")
    async def apply_security_headers(request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Cache-Control", "no-store")
        if settings.app_env.casefold() == "production":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=r"https://.*\.vercel\.app",
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Confirm-Delete"],
    )
    application.include_router(api_router, prefix=settings.api_v1_prefix)
    return application


app = create_app()
