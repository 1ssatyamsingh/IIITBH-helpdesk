from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class FileType(StrEnum):
    TXT = "txt"
    PDF = "pdf"


class PdfClassification(StrEnum):
    DIGITAL = "digital"
    SCANNED = "scanned"
    MIXED = "mixed"
    EMPTY = "empty"


class PageClassification(StrEnum):
    DIGITAL = "digital"
    SCANNED = "scanned"
    EMPTY = "empty"


class ExtractionMethod(StrEnum):
    TXT_LOADER = "txt_loader"
    PYMUPDF = "pymupdf"
    GROQ_QWEN_VLM = "groq_qwen_vlm"
    NONE = "none"


class ExtractionStatus(StrEnum):
    SUCCESS = "success"
    REQUIRES_VLM = "requires_vlm"
    EMPTY = "empty"
    FAILED = "failed"


class PageInspection(BaseModel):
    page_number: int
    classification: PageClassification
    extracted_characters: int = Field(ge=0)
    image_count: int = Field(ge=0)


class PdfClassificationResult(BaseModel):
    classification: PdfClassification
    page_count: int = Field(ge=0)
    digital_pages: int = Field(ge=0)
    scanned_pages: int = Field(ge=0)
    empty_pages: int = Field(ge=0)
    average_characters_per_page: float = Field(ge=0)
    min_text_characters_per_page: int = Field(ge=1)
    rule_version: str = "pymupdf-page-heuristic-v1"
    pages: list[PageInspection]


class ExtractedPage(BaseModel):
    page_number: int | None
    text: str
    classification: PageClassification | None = None
    extraction_method: ExtractionMethod
    extraction_status: ExtractionStatus
    extracted_characters: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentExtractionResult(BaseModel):
    source_file: str
    file_type: FileType
    pdf_classification: PdfClassification | None = None
    page_count: int = Field(ge=0)
    pages: list[ExtractedPage]
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentChunk(BaseModel):
    chunk_id: str
    document_id: str
    source_file: str
    file_type: FileType
    page_number: int | None
    chunk_index: int = Field(ge=0)
    text: str
    extraction_method: ExtractionMethod
    metadata: dict[str, Any] = Field(default_factory=dict)
