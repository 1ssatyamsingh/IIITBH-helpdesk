from pathlib import Path

import pymupdf

from app.domain.documents.models import (
    ExtractedPage,
    ExtractionMethod,
    ExtractionStatus,
    PageClassification,
)
from app.infrastructure.extraction.digital_pdf_extractor import PyMuPDFDocumentExtractor
from app.infrastructure.extraction.groq_qwen_vlm_extractor import VlmExtractionError
from app.infrastructure.extraction.hybrid_pdf_extractor import HybridPdfExtractor


class FakeVlmExtractor:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.called_pages: list[int] = []

    def extract_page(self, pdf_path: Path, page_number: int) -> ExtractedPage:
        self.called_pages.append(page_number)
        if self.should_fail:
            raise VlmExtractionError("simulated VLM provider failure")
        text = f"Recognized content on page {page_number}"
        return ExtractedPage(
            page_number=page_number,
            text=text,
            classification=PageClassification.SCANNED,
            extraction_method=ExtractionMethod.GROQ_QWEN_VLM,
            extraction_status=ExtractionStatus.SUCCESS,
            extracted_characters=len(text),
        )


def _create_one_page_scanned_pdf(path: Path) -> None:
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 100, 100), 0)
    pixmap.clear_with(190)
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_image(pymupdf.Rect(30, 30, 300, 300), pixmap=pixmap)
    doc.save(path)
    doc.close()


def test_hybrid_pdf_extractor_replaces_scanned_page_with_vlm_text(tmp_path: Path) -> None:
    pdf_path = tmp_path / "scanned.pdf"
    _create_one_page_scanned_pdf(pdf_path)
    vlm = FakeVlmExtractor()
    extractor = HybridPdfExtractor(PyMuPDFDocumentExtractor(), vlm)

    result = extractor.extract(pdf_path)

    assert vlm.called_pages == [1]
    assert result.pages[0].text == "Recognized content on page 1"
    assert result.pages[0].extraction_method == ExtractionMethod.GROQ_QWEN_VLM
    assert result.pages[0].extraction_status == ExtractionStatus.SUCCESS
    assert result.pages[0].metadata["page_classification"] == "scanned"


def test_hybrid_pdf_extractor_records_page_level_vlm_failure(tmp_path: Path) -> None:
    pdf_path = tmp_path / "scanned.pdf"
    _create_one_page_scanned_pdf(pdf_path)
    vlm = FakeVlmExtractor(should_fail=True)
    extractor = HybridPdfExtractor(PyMuPDFDocumentExtractor(), vlm)

    result = extractor.extract(pdf_path)

    assert result.pages[0].extraction_status == ExtractionStatus.FAILED
    assert "VLM extraction failed for page(s): 1" in result.warnings
