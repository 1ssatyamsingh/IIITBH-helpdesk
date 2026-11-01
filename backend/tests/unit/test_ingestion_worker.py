from pathlib import Path

from app.application.ingestion.process_document import DocumentProcessingOutput
from app.core.config import Settings
from app.domain.documents.models import (
    DocumentChunk,
    DocumentExtractionResult,
    ExtractedPage,
    ExtractionMethod,
    ExtractionStatus,
    FileType,
)
from app.infrastructure.persistence.sqlite_job_repository import SQLiteJobRepository
from app.workers.ingestion_worker import IngestionWorker


class FakeDocumentProcessor:
    def __init__(self, result: DocumentProcessingOutput) -> None:
        self.result = result

    def process(self, file_path: Path) -> DocumentProcessingOutput:
        return self.result


class FakeEmbeddingClient:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]


class FakeVectorStore:
    def __init__(self) -> None:
        self.client = self
        self.upsert_args = None
        self.closed = False

    def upsert_chunks(self, **kwargs) -> list[str]:
        self.upsert_args = kwargs
        return [chunk.chunk_id for chunk in kwargs["chunks"]]

    def close(self) -> None:
        self.closed = True


def _processing_result(
    tmp_path: Path,
    pages_requiring_vlm: list[int] | None = None,
) -> DocumentProcessingOutput:
    chunk = DocumentChunk(
        chunk_id="chunk-1",
        document_id="doc-1",
        source_file="knowledge.txt",
        file_type=FileType.TXT,
        page_number=None,
        chunk_index=0,
        text="IIIT Bhagalpur knowledge base",
        extraction_method=ExtractionMethod.TXT_LOADER,
    )
    extraction = DocumentExtractionResult(
        source_file="knowledge.txt",
        file_type=FileType.TXT,
        page_count=1,
        pages=[
            ExtractedPage(
                page_number=None,
                text=chunk.text,
                extraction_method=ExtractionMethod.TXT_LOADER,
                extraction_status=ExtractionStatus.SUCCESS,
                extracted_characters=len(chunk.text),
            )
        ],
    )
    return DocumentProcessingOutput(
        document_id="doc-1",
        content_sha256="sha256",
        extraction=extraction,
        chunks=[chunk],
        pages_requiring_vlm=pages_requiring_vlm or [],
        pages_failed_extraction=[],
    )


def _create_queued_job(repository: SQLiteJobRepository, tmp_path: Path) -> Path:
    source = tmp_path / "knowledge.txt"
    source.write_text("placeholder", encoding="utf-8")
    repository.create_job(
        "job-1",
        [
            {
                "file_id": "file-1",
                "original_filename": source.name,
                "storage_path": str(source),
                "file_type": "txt",
                "status": "received",
            }
        ],
    )
    return source


def test_worker_blocks_scanned_pdf_until_vlm_configuration(tmp_path: Path) -> None:
    repository = SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    _create_queued_job(repository, tmp_path)
    processor = FakeDocumentProcessor(_processing_result(tmp_path, [2]))
    worker = IngestionWorker(
        repository=repository,
        settings=Settings(data_dir=tmp_path),
        document_processor=processor,
    )

    assert worker.process_next_file() is True
    job = repository.get_job("job-1")
    assert job["status"] == "blocked"
    assert job["files"][0]["status"] == "blocked"
    assert "Groq VLM" in job["files"][0]["error"]


def test_worker_indexes_chunks_when_services_are_configured(tmp_path: Path) -> None:
    repository = SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    _create_queued_job(repository, tmp_path)
    fake_store = FakeVectorStore()
    settings = Settings(
        data_dir=tmp_path,
        local_embedding_base_url="http://127.0.0.1:8088",
        qdrant_url="https://qdrant.example.test",
        embedding_dimension=3,
        embedding_batch_size=4,
    )
    worker = IngestionWorker(
        repository=repository,
        settings=settings,
        document_processor=FakeDocumentProcessor(_processing_result(tmp_path)),
        embedding_client_factory=lambda _: FakeEmbeddingClient(),
        vector_store_factory=lambda _: fake_store,
    )

    assert worker.process_next_file() is True
    job = repository.get_job("job-1")
    assert job["status"] == "completed"
    assert job["files"][0]["metadata"]["indexed_point_count"] == 1
    assert fake_store.closed is True
