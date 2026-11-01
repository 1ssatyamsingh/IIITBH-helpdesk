from pydantic import BaseModel

from app.domain.documents.models import (
    DocumentExtractionResult,
    PdfClassificationResult,
)


class PdfClassificationResponse(BaseModel):
    source_file: str
    result: PdfClassificationResult


class DocumentInspectionResponse(BaseModel):
    extraction: DocumentExtractionResult
    extracted_text_pages: int
    pages_requiring_vlm: int
