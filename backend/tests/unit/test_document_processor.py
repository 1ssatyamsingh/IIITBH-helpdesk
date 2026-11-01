from pathlib import Path

import pymupdf
import pytest

from app.application.ingestion.process_document import (
    DocumentProcessor,
    UnsupportedDocumentError,
)
from app.infrastructure.extraction.digital_pdf_extractor import PyMuPDFDocumentExtractor


def test_processes_txt_and_generates_stable_document_id(tmp_path: Path) -> None:
    path = tmp_path / "facts.txt"
    path.write_text("IIIT Bhagalpur RAG test content. " * 80, encoding="utf-8")

    processor = DocumentProcessor()
    first = processor.process(path)
    second = processor.process(path)

    assert first.document_id == second.document_id
    assert [chunk.chunk_id for chunk in first.chunks] == [chunk.chunk_id for chunk in second.chunks]
    assert first.extraction.file_type.value == "txt"
    assert first.chunks
    assert first.pages_requiring_vlm == []


def test_rejects_pdf_extension_without_pdf_signature(tmp_path: Path) -> None:
    path = tmp_path / "not-a-pdf.pdf"
    path.write_text("This is plain text, not a PDF.", encoding="utf-8")

    with pytest.raises(UnsupportedDocumentError):
        DocumentProcessor().process(path)


def test_rejects_unsupported_extension(tmp_path: Path) -> None:
    path = tmp_path / "notes.docx"
    path.write_bytes(b"not processed")

    with pytest.raises(UnsupportedDocumentError):
        DocumentProcessor().process(path)


def test_scanned_pdf_reports_pages_requiring_vlm(tmp_path: Path) -> None:
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 100, 100), 0)
    pixmap.clear_with(220)
    path = tmp_path / "scan.pdf"
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_image(pymupdf.Rect(40, 40, 300, 300), pixmap=pixmap)
    pdf.save(path)
    pdf.close()

    # Keep this unit test deterministic even when a real Groq key exists in .env.
    result = DocumentProcessor(pdf_extractor=PyMuPDFDocumentExtractor()).process(path)

    assert result.extraction.pdf_classification.value == "scanned"
    assert result.pages_requiring_vlm == [1]
    assert result.chunks == []


def test_document_processor_adds_conservative_source_category(tmp_path: Path) -> None:
    path = tmp_path / "BTech_Fee_Structure_2025.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "IIIT Bhagalpur fee schedule information " * 10)
    doc.save(path)
    doc.close()

    result = DocumentProcessor().process(path)

    assert result.extraction.metadata["document_category"] == "fee_schedule"
    assert result.extraction.metadata["document_category_basis"] == "filename_rule_v1"
    assert result.extraction.metadata["created_at"]
    assert result.chunks
    assert result.chunks[0].metadata["document_category"] == "fee_schedule"
