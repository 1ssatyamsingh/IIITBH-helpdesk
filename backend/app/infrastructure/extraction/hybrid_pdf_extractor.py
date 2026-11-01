from pathlib import Path

from app.domain.documents.models import (
    DocumentExtractionResult,
    ExtractionStatus,
)
from app.infrastructure.extraction.digital_pdf_extractor import PyMuPDFDocumentExtractor
from app.infrastructure.extraction.groq_qwen_vlm_extractor import (
    GroqQwenVlmExtractor,
    VlmExtractionError,
)


class HybridPdfExtractor:
    """Uses PyMuPDF for text pages and Groq Qwen VLM for image-only pages."""

    def __init__(
        self,
        digital_extractor: PyMuPDFDocumentExtractor,
        vlm_extractor: GroqQwenVlmExtractor,
    ) -> None:
        self.digital_extractor = digital_extractor
        self.vlm_extractor = vlm_extractor

    def extract(self, file_path: Path) -> DocumentExtractionResult:
        result = self.digital_extractor.extract(file_path)
        pages = []

        for page in result.pages:
            if page.extraction_status != ExtractionStatus.REQUIRES_VLM:
                pages.append(page)
                continue

            try:
                vlm_page = self.vlm_extractor.extract_page(file_path, page.page_number)
                pages.append(
                    vlm_page.model_copy(update={"metadata": {**page.metadata, **vlm_page.metadata}})
                )
            except VlmExtractionError as exc:
                pages.append(
                    page.model_copy(
                        update={
                            "extraction_status": ExtractionStatus.FAILED,
                            "warnings": [str(exc)],
                        }
                    )
                )

        failed_pages = [
            page.page_number for page in pages if page.extraction_status == ExtractionStatus.FAILED
        ]
        warnings = list(result.warnings)
        if failed_pages:
            warnings.append(
                "VLM extraction failed for page(s): "
                + ", ".join(str(number) for number in failed_pages)
            )

        return result.model_copy(
            update={
                "pages": pages,
                "warnings": warnings,
            }
        )
