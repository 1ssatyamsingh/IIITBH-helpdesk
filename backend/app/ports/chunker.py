from typing import Protocol

from app.domain.documents.models import DocumentChunk, DocumentExtractionResult


class DocumentChunker(Protocol):
    def chunk(
        self,
        result: DocumentExtractionResult,
        document_id: str,
    ) -> list[DocumentChunk]:
        """Split extracted text without losing source/page provenance."""
        ...
