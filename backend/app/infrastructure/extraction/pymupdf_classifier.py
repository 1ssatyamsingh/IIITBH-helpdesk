from pathlib import Path

import pymupdf

from app.domain.documents.models import (
    PageClassification,
    PageInspection,
    PdfClassification,
    PdfClassificationResult,
)


class PyMuPDFClassifier:
    """Page-aware PDF classifier. It is a routing heuristic, not ground truth."""

    def __init__(self, min_text_characters_per_page: int = 30) -> None:
        if min_text_characters_per_page < 1:
            raise ValueError("min_text_characters_per_page must be at least 1")
        self.min_text_characters_per_page = min_text_characters_per_page

    def classify(self, file_path: Path) -> PdfClassificationResult:
        inspections: list[PageInspection] = []
        total_characters = 0

        with pymupdf.open(file_path) as pdf:
            page_count = len(pdf)
            for page_index, page in enumerate(pdf):
                text = page.get_text("text").strip()
                character_count = len(text)
                image_count = len(page.get_images(full=True))
                total_characters += character_count

                if character_count >= self.min_text_characters_per_page:
                    page_class = PageClassification.DIGITAL
                elif image_count > 0:
                    page_class = PageClassification.SCANNED
                elif character_count > 0:
                    # Sparse but selectable text is still digital; never discard it as blank.
                    page_class = PageClassification.DIGITAL
                else:
                    page_class = PageClassification.EMPTY

                inspections.append(
                    PageInspection(
                        page_number=page_index + 1,
                        classification=page_class,
                        extracted_characters=character_count,
                        image_count=image_count,
                    )
                )

        digital = sum(p.classification == PageClassification.DIGITAL for p in inspections)
        scanned = sum(p.classification == PageClassification.SCANNED for p in inspections)
        empty = sum(p.classification == PageClassification.EMPTY for p in inspections)

        if digital and scanned:
            document_class = PdfClassification.MIXED
        elif digital:
            document_class = PdfClassification.DIGITAL
        elif scanned:
            document_class = PdfClassification.SCANNED
        else:
            document_class = PdfClassification.EMPTY

        average = total_characters / page_count if page_count else 0.0
        return PdfClassificationResult(
            classification=document_class,
            page_count=page_count,
            digital_pages=digital,
            scanned_pages=scanned,
            empty_pages=empty,
            average_characters_per_page=round(average, 2),
            min_text_characters_per_page=self.min_text_characters_per_page,
            rule_version="pymupdf-page-heuristic-v1",
            pages=inspections,
        )
