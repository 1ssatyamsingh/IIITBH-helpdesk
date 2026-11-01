from pathlib import Path

import pymupdf

from app.domain.documents.models import (
    ExtractionStatus,
    PageClassification,
    PdfClassification,
)
from app.infrastructure.chunking.langchain_chunker import LangChainDocumentChunker
from app.infrastructure.extraction.digital_pdf_extractor import PyMuPDFDocumentExtractor
from app.infrastructure.extraction.pymupdf_classifier import PyMuPDFClassifier
from app.infrastructure.extraction.txt_loader import TxtDocumentLoader


def _create_image_pdf(path: Path) -> None:
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 120, 120), 0)
    pixmap.clear_with(230)
    image_bytes = pixmap.tobytes("png")
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_image(pymupdf.Rect(50, 50, 350, 350), stream=image_bytes)
    doc.save(path)
    doc.close()


def test_classifies_digital_pdf(tmp_path: Path) -> None:
    path = tmp_path / "digital.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "IIIT Bhagalpur official academic information " * 8)
    doc.save(path)
    doc.close()

    result = PyMuPDFClassifier().classify(path)

    assert result.classification == PdfClassification.DIGITAL
    assert result.digital_pages == 1
    assert result.scanned_pages == 0
    assert result.rule_version == "pymupdf-page-heuristic-v1"


def test_classifies_scanned_pdf_and_marks_vlm_required(tmp_path: Path) -> None:
    path = tmp_path / "scanned.pdf"
    _create_image_pdf(path)

    result = PyMuPDFClassifier().classify(path)
    extracted = PyMuPDFDocumentExtractor().extract(path)

    assert result.classification == PdfClassification.SCANNED
    assert result.scanned_pages == 1
    assert extracted.pages[0].extraction_status == ExtractionStatus.REQUIRES_VLM
    assert extracted.metadata["pdf_scanned_pages"] == 1
    assert extracted.metadata["pdf_classification_rule_version"] == result.rule_version
    assert extracted.pages[0].metadata["image_count"] > 0


def test_classifies_mixed_pdf_page_by_page(tmp_path: Path) -> None:
    path = tmp_path / "mixed.pdf"
    doc = pymupdf.open()
    page1 = doc.new_page()
    page1.insert_text((72, 72), "Digital text content " * 10)
    page2 = doc.new_page()
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 120, 120), 0)
    pixmap.clear_with(210)
    page2.insert_image(pymupdf.Rect(40, 40, 340, 340), pixmap=pixmap)
    doc.save(path)
    doc.close()

    result = PyMuPDFClassifier().classify(path)
    extracted = PyMuPDFDocumentExtractor().extract(path)

    assert result.classification == PdfClassification.MIXED
    assert [page.classification for page in extracted.pages] == [
        PageClassification.DIGITAL,
        PageClassification.SCANNED,
    ]
    assert extracted.pages[0].text
    assert extracted.pages[1].extraction_status == ExtractionStatus.REQUIRES_VLM


def test_txt_loader_and_langchain_chunker_preserve_provenance(tmp_path: Path) -> None:
    path = tmp_path / "sample.txt"
    path.write_text("IIIT Bhagalpur information. " * 100, encoding="utf-8")

    loaded = TxtDocumentLoader().load(path)
    chunks = LangChainDocumentChunker(chunk_size=160, chunk_overlap=20).chunk(
        loaded, document_id="doc-test"
    )

    assert loaded.pages[0].text
    assert len(chunks) > 1
    assert all(chunk.source_file == "sample.txt" for chunk in chunks)
    assert all(chunk.page_number is None for chunk in chunks)
    assert all(chunk.document_id == "doc-test" for chunk in chunks)
    assert all(chunk.metadata["selected_encoding"] == "utf-8-sig" for chunk in chunks)
    assert all(chunk.metadata["chunker_config_version"] == "1" for chunk in chunks)


def test_sparse_selectable_text_is_not_discarded_as_blank(tmp_path: Path) -> None:
    path = tmp_path / "sparse.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Fee")
    doc.save(path)
    doc.close()

    result = PyMuPDFClassifier(min_text_characters_per_page=30).classify(path)

    assert result.classification == PdfClassification.DIGITAL
    assert result.digital_pages == 1
    assert result.empty_pages == 0
