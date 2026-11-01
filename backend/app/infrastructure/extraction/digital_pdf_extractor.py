from pathlib import Path

import pymupdf

from app.domain.documents.models import (
    DocumentExtractionResult,
    ExtractedPage,
    ExtractionMethod,
    ExtractionStatus,
    FileType,
    PageClassification,
    PdfClassification,
)
from app.infrastructure.extraction.pymupdf_classifier import PyMuPDFClassifier


class PyMuPDFDocumentExtractor:
    def __init__(self, classifier: PyMuPDFClassifier | None = None) -> None:
        self.classifier = classifier or PyMuPDFClassifier()

    def extract(self, file_path: Path) -> DocumentExtractionResult:
        classification = self.classifier.classify(file_path)
        extracted_pages: list[ExtractedPage] = []

        with pymupdf.open(file_path) as pdf:
            for page_index, page in enumerate(pdf):
                page_info = classification.pages[page_index]
                if page_info.classification == PageClassification.DIGITAL:
                    text = page.get_text("text").strip()
                    extracted_pages.append(
                        ExtractedPage(
                            page_number=page_index + 1,
                            text=text,
                            classification=PageClassification.DIGITAL,
                            extraction_method=ExtractionMethod.PYMUPDF,
                            extraction_status=ExtractionStatus.SUCCESS,
                            extracted_characters=len(text),
                            metadata={
                                "page_classification": page_info.classification.value,
                                "image_count": page_info.image_count,
                                "classification_rule_version": classification.rule_version,
                                "extractor": "pymupdf",
                                "pymupdf_version": pymupdf.VersionBind,
                            },
                        )
                    )
                elif page_info.classification == PageClassification.SCANNED:
                    extracted_pages.append(
                        ExtractedPage(
                            page_number=page_index + 1,
                            text="",
                            classification=PageClassification.SCANNED,
                            extraction_method=ExtractionMethod.NONE,
                            extraction_status=ExtractionStatus.REQUIRES_VLM,
                            extracted_characters=0,
                            warnings=["Page appears image-based; VLM extraction is required."],
                            metadata={
                                "page_classification": page_info.classification.value,
                                "image_count": page_info.image_count,
                                "classification_rule_version": classification.rule_version,
                            },
                        )
                    )
                else:
                    extracted_pages.append(
                        ExtractedPage(
                            page_number=page_index + 1,
                            text="",
                            classification=PageClassification.EMPTY,
                            extraction_method=ExtractionMethod.NONE,
                            extraction_status=ExtractionStatus.EMPTY,
                            extracted_characters=0,
                            warnings=["No meaningful text or embedded images were detected."],
                            metadata={
                                "page_classification": page_info.classification.value,
                                "image_count": page_info.image_count,
                                "classification_rule_version": classification.rule_version,
                            },
                        )
                    )

        warnings = []
        if classification.classification in {
            PdfClassification.SCANNED,
            PdfClassification.MIXED,
        }:
            warnings.append("One or more pages require the configured vision extraction service.")
        if classification.classification == PdfClassification.EMPTY:
            warnings.append("The PDF contains no extractable text or detected page images.")

        return DocumentExtractionResult(
            source_file=file_path.name,
            file_type=FileType.PDF,
            pdf_classification=classification.classification,
            page_count=classification.page_count,
            pages=extracted_pages,
            warnings=warnings,
            metadata={
                "document_category": "unknown",
                "pdf_classification": classification.classification.value,
                "pdf_classification_rule_version": classification.rule_version,
                "pdf_page_count": classification.page_count,
                "pdf_digital_pages": classification.digital_pages,
                "pdf_scanned_pages": classification.scanned_pages,
                "pdf_empty_pages": classification.empty_pages,
                "pdf_average_characters_per_page": classification.average_characters_per_page,
                "pdf_min_text_characters_per_page": classification.min_text_characters_per_page,
                "pymupdf_version": pymupdf.VersionBind,
            },
        )
