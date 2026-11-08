import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from app.application.ingestion.embedding_pipeline import EmbeddingPipeline
from app.application.ingestion.process_document import (
    DocumentProcessingOutput,
    DocumentProcessor,
)
from app.core.config import Settings, get_settings
from app.infrastructure.embeddings.factory import create_embedding_client
from app.infrastructure.persistence.sqlite_job_repository import SQLiteJobRepository
from app.infrastructure.vectorstores.qdrant_store import QdrantVectorStore

logger = logging.getLogger(__name__)


class IngestionWorker:
    """Processes persisted ingestion files outside the FastAPI request lifecycle."""

    def __init__(
        self,
        repository: SQLiteJobRepository,
        settings: Settings | None = None,
        document_processor: Any | None = None,
        embedding_client_factory: Callable | None = None,
        vector_store_factory: Callable | None = None,
    ) -> None:
        self.repository = repository
        self.settings = settings or get_settings()
        self.document_processor = document_processor or DocumentProcessor()
        self.embedding_client_factory = embedding_client_factory or create_embedding_client
        self.vector_store_factory = vector_store_factory or QdrantVectorStore.from_settings

    def process_next_file(self) -> bool:
        file_record = self.repository.claim_next_file()
        if file_record is None:
            return False

        file_id = file_record["file_id"]
        job_id = file_record["job_id"]
        file_path = Path(file_record["storage_path"])
        try:
            self.repository.update_file(file_id, "classifying")
            result: DocumentProcessingOutput = self.document_processor.process(file_path)
            display_filename = unquote(file_record["original_filename"])
            if result.extraction.source_file != display_filename:
                result = result.model_copy(
                    update={
                        "extraction": result.extraction.model_copy(
                            update={"source_file": display_filename}
                        ),
                        "chunks": [
                            chunk.model_copy(update={"source_file": display_filename})
                            for chunk in result.chunks
                        ],
                    }
                )
            processing_metadata = {
                "document_id": result.document_id,
                "content_sha256": result.content_sha256,
                "file_type": result.extraction.file_type.value,
                "pdf_classification": (
                    result.extraction.pdf_classification.value
                    if result.extraction.pdf_classification
                    else None
                ),
                "page_count": result.extraction.page_count,
                "chunk_count": len(result.chunks),
                "pages_requiring_vlm": result.pages_requiring_vlm,
                "pages_failed_extraction": result.pages_failed_extraction,
                "extraction_warnings": result.extraction.warnings,
                "extraction_metadata": result.extraction.metadata,
                "pdf_page_classifications": [
                    {
                        "page_number": page.page_number,
                        "classification": page.metadata.get("page_classification"),
                        "extraction_method": page.extraction_method.value,
                        "extraction_status": page.extraction_status.value,
                        "extracted_characters": page.extracted_characters,
                    }
                    for page in result.extraction.pages
                    if page.page_number is not None
                ],
            }

            if result.pages_requiring_vlm:
                self.repository.update_file(
                    file_id,
                    "blocked",
                    error=(
                        "Scanned PDF pages require Groq VLM extraction. Configure "
                        "GROQ_API_KEY and retry this file."
                    ),
                    metadata=processing_metadata,
                )
                return True

            if result.pages_failed_extraction:
                self.repository.update_file(
                    file_id,
                    "failed",
                    error=(
                        "Extraction failed for page(s): "
                        + ", ".join(map(str, result.pages_failed_extraction))
                    ),
                    metadata=processing_metadata,
                )
                return True

            if not result.chunks:
                self.repository.update_file(
                    file_id,
                    "failed",
                    error="No usable text chunks were produced from this document.",
                    metadata=processing_metadata,
                )
                return True

            missing_configuration = []
            if self.settings.embedding_provider.strip().lower() == "local":
                if not self.settings.local_embedding_base_url:
                    missing_configuration.append("LOCAL_EMBEDDING_BASE_URL")
            elif self.settings.embedding_provider.strip().lower() == "cloudflare":
                if not self.settings.cloudflare_account_id:
                    missing_configuration.append("CLOUDFLARE_ACCOUNT_ID")
                if not self.settings.cloudflare_api_token:
                    missing_configuration.append("CLOUDFLARE_API_TOKEN")
            else:
                missing_configuration.append("EMBEDDING_PROVIDER (local or cloudflare)")
            if not self.settings.qdrant_url:
                missing_configuration.append("QDRANT_URL")
            if missing_configuration:
                self.repository.update_file(
                    file_id,
                    "blocked",
                    error=(
                        "Configure the following backend settings before indexing: "
                        + ", ".join(missing_configuration)
                    ),
                    metadata=processing_metadata,
                )
                return True

            self.repository.update_file(
                file_id,
                "embedding",
                metadata=processing_metadata,
            )
            embedding_client = self.embedding_client_factory(self.settings)
            embedding_pipeline = EmbeddingPipeline(
                client=embedding_client,
                batch_size=self.settings.embedding_batch_size,
                expected_dimension=self.settings.embedding_dimension,
            )
            vectors = embedding_pipeline.embed_chunks(result.chunks)

            self.repository.update_file(file_id, "indexing")
            vector_store = self.vector_store_factory(self.settings)
            try:
                point_ids = vector_store.upsert_chunks(
                    chunks=result.chunks,
                    vectors=vectors,
                    embedding_model=self.settings.resolved_embedding_model_id,
                    ingestion_job_id=job_id,
                )
            finally:
                vector_store.client.close()

            self.repository.update_file(
                file_id,
                "completed",
                metadata={
                    **processing_metadata,
                    "indexed_point_count": len(point_ids),
                    "qdrant_point_ids": point_ids,
                    "embedding_model": self.settings.resolved_embedding_model_id,
                },
            )
        except Exception as exc:
            logger.exception("Ingestion failed for job %s file %s", job_id, file_id)
            self.repository.update_file(
                file_id,
                "failed",
                error=f"Processing failed: {type(exc).__name__}. Check backend logs.",
            )
        return True
