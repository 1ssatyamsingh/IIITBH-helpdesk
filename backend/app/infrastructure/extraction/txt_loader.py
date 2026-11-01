from pathlib import Path

from app.domain.documents.models import (
    DocumentExtractionResult,
    ExtractedPage,
    ExtractionMethod,
    ExtractionStatus,
    FileType,
)


class TxtDocumentLoader:
    """Loads UTF text without dropping content; records the chosen encoding."""

    ENCODINGS = ("utf-8-sig", "utf-16", "cp1252")

    def load(self, file_path: Path) -> DocumentExtractionResult:
        text = None
        selected_encoding = None
        decode_errors: list[str] = []

        for encoding in self.ENCODINGS:
            try:
                text = file_path.read_text(encoding=encoding)
                selected_encoding = encoding
                break
            except UnicodeError as exc:
                decode_errors.append(f"{encoding}: {exc}")

        if text is None or selected_encoding is None:
            raise UnicodeError(
                f"Unable to decode {file_path.name} with supported encodings: "
                + "; ".join(decode_errors)
            )

        cleaned = text.replace("\x00", "").strip()
        warnings = [f"Text decoded using {selected_encoding}."]
        if not cleaned:
            warnings.append("The text file is empty after whitespace normalization.")

        page = ExtractedPage(
            page_number=None,
            text=cleaned,
            extraction_method=ExtractionMethod.TXT_LOADER,
            extraction_status=ExtractionStatus.SUCCESS if cleaned else ExtractionStatus.EMPTY,
            extracted_characters=len(cleaned),
            warnings=warnings,
            metadata={
                "extractor": "txt_document_loader",
                "selected_encoding": selected_encoding,
                "loader_version": "1",
            },
        )
        return DocumentExtractionResult(
            source_file=file_path.name,
            file_type=FileType.TXT,
            page_count=1 if cleaned else 0,
            pages=[page],
            warnings=[] if cleaned else ["The text file contains no usable text."],
            metadata={
                "document_category": "unknown",
                "text_loader_version": "1",
                "selected_encoding": selected_encoding,
            },
        )
