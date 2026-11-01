from pathlib import Path
from typing import Protocol

from app.domain.documents.models import DocumentExtractionResult


class DocumentExtractor(Protocol):
    def extract(self, file_path: Path) -> DocumentExtractionResult:
        """Extract text while preserving document and page provenance."""
        ...
