import hashlib
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from app.application.ingestion.source_metadata import infer_document_category
from app.core.config import get_settings
from app.domain.documents.models import (
    DocumentChunk,
    DocumentExtractionResult,
)
from app.infrastructure.chunking.langchain_chunker import LangChainDocumentChunker
from app.infrastructure.extraction.digital_pdf_extractor import PyMuPDFDocumentExtractor
from app.infrastructure.extraction.groq_qwen_vlm_extractor import GroqQwenVlmExtractor
from app.infrastructure.extraction.hybrid_pdf_extractor import HybridPdfExtractor
from app.infrastructure.extraction.pymupdf_classifier import PyMuPDFClassifier
from app.infrastructure.extraction.txt_loader import TxtDocumentLoader
from app.ports.document_extractor import DocumentExtractor


class DocumentProcessingOutput(BaseModel):
    document_id: str
    content_sha256: str
    extraction: DocumentExtractionResult
    chunks: list[DocumentChunk]
    pages_requiring_vlm: list[int]
    pages_failed_extraction: list[int]


class UnsupportedDocumentError(ValueError):
    pass


class DocumentProcessor:
    """Coordinates local extraction and chunking; provider integrations stay behind adapters."""

    def __init__(
        self,
        txt_loader: TxtDocumentLoader | None = None,
        pdf_extractor: DocumentExtractor | None = None,
        chunker: LangChainDocumentChunker | None = None,
    ) -> None:
        settings = get_settings()
        self.txt_loader = txt_loader or TxtDocumentLoader()
        if pdf_extractor is not None:
            self.pdf_extractor = pdf_extractor
        else:
            digital_extractor = PyMuPDFDocumentExtractor(
                classifier=PyMuPDFClassifier(
                    min_text_characters_per_page=settings.pdf_min_text_characters_per_page
                )
            )
            if settings.groq_api_key:
                self.pdf_extractor = HybridPdfExtractor(
                    digital_extractor=digital_extractor,
                    vlm_extractor=GroqQwenVlmExtractor(
                        api_key=settings.groq_api_key,
                        model_id=settings.groq_vlm_model,
                        render_dpi=settings.groq_render_dpi,
                        max_image_bytes=settings.groq_max_image_mb * 1024 * 1024,
                    ),
                )
            else:
                self.pdf_extractor = digital_extractor

        self.chunker = chunker or LangChainDocumentChunker(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

    def process(self, file_path: Path) -> DocumentProcessingOutput:
        if not file_path.is_file():
            raise FileNotFoundError(file_path)

        suffix = file_path.suffix.lower()
        if suffix == ".txt":
            extraction = self.txt_loader.load(file_path)
        elif suffix == ".pdf":
            with file_path.open("rb") as source:
                if source.read(1024).find(b"%PDF-") < 0:
                    raise UnsupportedDocumentError(
                        f"{file_path.name} has a PDF extension but no PDF signature."
                    )
            extraction = self.pdf_extractor.extract(file_path)
        else:
            raise UnsupportedDocumentError(
                f"Unsupported file type: {suffix or '[no extension]'}. "
                "Only TXT and PDF are supported."
            )

        source_metadata = {
            **infer_document_category(file_path.name),
            "created_at": datetime.now(UTC).isoformat(),
        }
        extraction = extraction.model_copy(
            update={"metadata": {**extraction.metadata, **source_metadata}}
        )

        hasher = hashlib.sha256()
        with file_path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                hasher.update(block)
        digest = hasher.hexdigest()
        document_id = digest
        chunks = self.chunker.chunk(extraction, document_id=document_id)
        pages_requiring_vlm = [
            page.page_number
            for page in extraction.pages
            if page.extraction_status.value == "requires_vlm" and page.page_number is not None
        ]
        pages_failed_extraction = [
            page.page_number
            for page in extraction.pages
            if page.extraction_status.value == "failed" and page.page_number is not None
        ]
        return DocumentProcessingOutput(
            document_id=document_id,
            content_sha256=digest,
            extraction=extraction,
            chunks=chunks,
            pages_requiring_vlm=pages_requiring_vlm,
            pages_failed_extraction=pages_failed_extraction,
        )
